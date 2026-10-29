"""S4 rules (docs/11): H4 structure bias -> the first M15 close beyond the Asia range in the London window, on the
bias side -> limit at the broken Asia level (retest) or at the M15 zone that caused the break (zone), stop beyond the
further of the London extreme and the opposite Asia side, 3R (T1) or no target (time), flat at 17:00 UK.

Episodes have strategy.episodes()' M15 columns plus flat_ns, so resolve() fills them on M1 like S1's.
"""
from dataclasses import dataclass
from itertools import product
from typing import ClassVar

import numpy as np
import pandas as pd

from ta.config import pip_size
from ta.features import zones
from ta.strategy import LDN, Config

COLS = ["zone_t", "t_bos", "dir", "leg", "zone_low", "zone_high", "swing", "place_bar", "end_bar", "fill_bar",
        "entry", "stop", "target", "dist", "flat_ns"]


@dataclass(frozen=True)
class S4Config(Config):
    h1_bias: ClassVar[bool] = True  # prepare_frames() builds the H1 structure state
    strategy: str = "S4"
    entry: str = "retest"  # retest | zone
    target: str = "T1"  # T1 | time (no target: stop or 17:00 UK)
    b: float = 0.25  # stop buffer beyond the London extreme, in ATR_M15
    min_stop_pips: float = 10.0
    h1: bool = False  # True: the H1 structure state must agree with the H4 bias at the breakout close (docs/11 §12)


def grid() -> list[S4Config]:
    """The frozen S4 grid (docs/11 §12): retest entry, 12 configs."""
    return [S4Config(target=t, b=b, h1=h) for t, b, h in product(("T1", "time"), (0.1, 0.25, 0.5), (False, True))]


def breakouts(f: dict) -> pd.DataFrame:
    """docs/11 §1-3, one row per UK day whose first London close beyond the Asia range is on the H4 bias side:
    breakout bar `t`, dir `d`, broken Asia `level`, London extreme `ext` and its bar `org`, stop `anchor` (the further
    of `ext` and the opposite Asia side, docs/11 §5), `noon_ns`, `flat_ns`."""
    ldn = f["ts"].dt.tz_convert(LDN)
    hr = ldn.dt.hour.to_numpy()
    h, l = f["h"], f["l"]
    bars = pd.DataFrame({"day": ldn.dt.date.to_numpy(), "h": h, "l": l, "c": f["c"]})
    asia = bars[(hr >= 1) & (hr < 7)].groupby("day").agg(hi=("h", "max"), lo=("l", "min"))
    lon = bars[(hr >= 7) & (hr < 12)].join(asia, on="day", how="inner")
    start = lon.index.to_series().groupby(lon.day).min()  # first London bar of each day
    out = lon[(lon.c > lon.hi) | (lon.c < lon.lo)]
    rows = []
    for t, r in out[~out.day.duplicated()].iterrows():
        d = 1 if r.c > r.hi else -1
        if f["h4state"][t] != d:  # the first close beyond is against the H4 bias (or there is none): no trade
            continue
        s0 = start[r.day]
        org = s0 + int(np.argmin(l[s0:t + 1]) if d == 1 else np.argmax(h[s0:t + 1]))
        noon, flat = (pd.Timestamp(f"{r.day} {x}", tz=LDN).value for x in ("12:00", "17:00"))
        ext = l[org] if d == 1 else h[org]
        rows.append((t, d, r.hi if d == 1 else r.lo, org, ext, min(ext, r.lo) if d == 1 else max(ext, r.hi), noon, flat))
    return pd.DataFrame(rows, columns=["t", "d", "level", "org", "ext", "anchor", "noon_ns", "flat_ns"])


def setups(f: dict, cfg: S4Config) -> pd.DataFrame:
    """breakouts() plus the order: `place` bar, zone `lo`/`hi` and `entry` (retest: the Asia level; zone: S1's zone
    on the leg from the London extreme to the breakout, near edge). Breakouts without a valid zone are dropped."""
    bo = breakouts(f)
    if cfg.entry == "retest":
        return bo.assign(place=bo.t, lo=bo.level, hi=bo.level, entry=bo.level)
    ev = bo.rename(columns={"d": "dir", "org": "origin"}).assign(kind="breakout")
    z = zones(f["o"], f["h"], f["l"], f["c"], ev, f["atr"], cfg.m, cfg.zone_body)
    z = z.rename(columns={"t": "place", "t_bos": "t", "dir": "d", "origin": "org", "low": "lo", "high": "hi"})
    m = bo.merge(z[["t", "d", "org", "place", "lo", "hi"]], on=["t", "d", "org"])
    return m.assign(entry=np.where(m.d == 1, m.hi, m.lo))


def episodes(f: dict, cfg: S4Config) -> pd.DataFrame:
    """One row per S4 order: placed at the close of `place_bar`, fillable until 12:00 UK, killed by an M15 close
    beyond the stop; `target` is +/-inf for target='time'."""
    pip, n, rows = pip_size(f["pair"]), len(f["c"]), []
    ft = cfg.fill_through_pips * pip
    bar_ns = f["ts"].astype("datetime64[ns, UTC]").astype("int64").to_numpy()
    for r in setups(f, cfg).itertuples(index=False):
        d, p = r.d, r.place
        if f["blackout"][p] or (cfg.h1 and f["h1state"][r.t] != d):
            continue
        stop = r.anchor - d * cfg.b * f["atr"][r.t]
        dist = (r.entry - stop) * d
        if dist < cfg.min_stop_pips * pip or not dist <= cfg.cap_h4_atr * f["h4atr"][p]:
            continue
        s = np.arange(p + 1, min(np.searchsorted(bar_ns, r.noon_ns), n))  # bars opening before 12:00 UK
        if not s.size:
            continue
        dead = np.flatnonzero((f["c"][s] - stop) * d < 0)  # a fill on the killing bar comes first
        e = dead[0] if dead.size else len(s) - 1
        act = s[:e + 1]
        hit = f["ask_l"][act] <= r.entry - ft if d == 1 else f["bid_h"][act] >= r.entry + ft
        fills = np.flatnonzero(hit & f["fillable"][act])
        target = r.entry + d * cfg.rr * dist if cfg.target == "T1" else d * np.inf
        rows.append((p, r.t, d, r.t, r.lo, r.hi, r.anchor, p, int(s[e]), int(act[fills[0]]) if fills.size else -1,
                     r.entry, stop, target, dist, r.flat_ns))  # swing = the stop anchor
    return pd.DataFrame(rows, columns=COLS)
