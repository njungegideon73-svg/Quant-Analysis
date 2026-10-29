"""S5 rules (docs/13): the US open range (first `orb` minutes from 09:30 ET) -> a buy stop at its high and a sell stop
at its low until 12:00 ET, first side hit is the day's only trade -> stop at the other side, 3R (T1) or no target
(close), flat at 15:55 ET. Optional H4 bias; days whose costs exceed 10% of the range are skipped.

Episodes have s2's M1-timed columns, so resolve() takes the fill minute and the stop-order fill price as given.
"""
import datetime as dt
from dataclasses import dataclass
from itertools import product

import numpy as np
import pandas as pd
from pandas.tseries.holiday import (
    GoodFriday,
    Holiday,
    USLaborDay,
    USMartinLutherKingJr,
    USMemorialDay,
    USPresidentsDay,
    USThanksgivingDay,
    nearest_workday,
    sunday_to_monday,
)

from ta.broker import M1, Costs
from ta.s2 import COLS
from ta.strategy import NY, Config

SLIP = {"USA500IDXUSD": 2.5, "USATECHIDXUSD": 5.0, "XAUUSD": 1.5}  # half the median US-session spread (probe, docs/13 §0)
NYSE = [Holiday("NewYear", month=1, day=1, observance=sunday_to_monday), USMartinLutherKingJr, USPresidentsDay,
        GoodFriday, USMemorialDay, Holiday("Juneteenth", month=6, day=19, start_date="2022-01-01", observance=nearest_workday),
        Holiday("July4", month=7, day=4, observance=nearest_workday), USLaborDay, USThanksgivingDay,
        Holiday("Christmas", month=12, day=25, observance=nearest_workday)]
MOURNING = {dt.date(2018, 12, 5), dt.date(2025, 1, 9)}  # NYSE closed: Presidents Bush and Carter


@dataclass(frozen=True)
class S5Config(Config):
    strategy: str = "S5"
    instrument: str = "USA500IDXUSD"
    orb: int = 15  # opening range, minutes from 09:30 ET
    target: str = "T1"  # T1 (rr) | close (stop or 15:55 ET)
    bias: bool = False  # True: only in the H4 structure direction
    max_cost: float = 0.10  # skip the day if spread + slippage + commission exceed this share of the range


def grid() -> list[S5Config]:
    """The frozen S5 grid (docs/13 §12): NASDAQ 100 only, 12 configs (gold and the S&P 500 cannot reach P3)."""
    i = "USATECHIDXUSD"
    return [S5Config(instrument=i, orb=n, target=t, bias=b, slip_pips=SLIP[i])
            for n, t, b in product((5, 15, 30), ("T1", "close"), (False, True))]


def nyse_skip(years) -> set:
    """NYSE holidays and half days (Jul 3, the day after Thanksgiving, Dec 24 on weekdays): docs/13 §1."""
    start, end = f"{min(years)}-01-01", f"{max(years)}-12-31"
    out = {d.date() for r in NYSE for d in r.dates(start, end)} | MOURNING
    for y in years:
        thanks = USThanksgivingDay.dates(f"{y}-01-01", f"{y}-12-31")[0]
        out |= {d.date() for d in (pd.Timestamp(y, 7, 3), thanks + pd.Timedelta(days=1), pd.Timestamp(y, 12, 24))
                if d.day_of_week < 5}
    return out


def episodes(f: dict, m1: M1, cfg: S5Config) -> pd.DataFrame:
    """One row per placed day. `entry` is the stop-order fill price (gap-aware, plus slippage), so R is measured from
    the price actually paid; unfilled days keep the first side and the range edge."""
    c = Costs.for_pair(f["pair"], cfg.fill_through_pips, cfg.slip_pips, cfg.commission_per_lot, cfg.swap_pips)
    close_ns = f["close_ts"].astype("datetime64[ns, UTC]").astype("int64").to_numpy()
    first, last = (pd.Timestamp(x, tz="UTC").tz_convert(NY).date() for x in m1.ts[[0, -1]])
    days = [d.date() for d in pd.bdate_range(first, last)]
    skip, rows = nyse_skip(range(first.year, last.year + 1)), []
    for day in days:
        if day in skip:
            continue
        t0, noon, flat = (pd.Timestamp(f"{day} {x}", tz=NY).value for x in ("09:30", "12:00", "15:55"))
        t1 = t0 + cfg.orb * 60 * 10**9
        a, b, e = np.searchsorted(m1.ts, [t0, t1, noon])
        if b - a < 0.8 * cfg.orb or e <= b:  # range minutes missing, or no minutes left to trade
            continue
        hi = ((m1.bh[a:b] + m1.ah[a:b]) / 2).max()
        lo = ((m1.bl[a:b] + m1.al[a:b]) / 2).min()
        cost = (m1.ao[b] - m1.bo[b]) + 2 * c.slip + 2 * c.commission(hi)
        if cost > cfg.max_cost * (hi - lo):
            continue
        k = int(np.searchsorted(close_ns, t1, side="right")) - 1  # last M15 bar closed by the end of the range
        h4 = int(f["h4state"][k]) if k >= 0 else 0
        sides = (h4,) if cfg.bias else (1, -1)
        if 0 in sides:
            continue
        up = (m1.ah[b:e] >= hi) & (1 in sides)
        dn = (m1.bl[b:e] <= lo) & (-1 in sides)
        hit = np.flatnonzero(up | dn)
        if hit.size and up[hit[0]] and dn[hit[0]]:  # both sides in one minute: the order is unknown, skip the day
            continue
        i = b + int(hit[0]) if hit.size else -1
        d = (1 if up[hit[0]] else -1) if hit.size else sides[0]
        level, stop = (hi, lo) if d == 1 else (lo, hi)
        entry = level if i < 0 else max(level, m1.ao[i]) + c.slip if d == 1 else min(level, m1.bo[i]) - c.slip
        dist = (entry - stop) * d
        target = entry + d * cfg.rr * dist if cfg.target == "T1" else d * np.inf
        fill_bar = int(np.searchsorted(close_ns, m1.ts[i], side="right")) if i >= 0 else -1
        rows.append((k, k, d, 0, lo, hi, stop, k, k, fill_bar, entry, stop, target, dist, t1, t1, noon, i, flat))
    return pd.DataFrame(rows, columns=COLS)
