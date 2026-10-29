"""Pessimistic M1 fill and exit simulation (docs/02 §5). Longs buy on ask and sell on bid; shorts mirror.

Prices are in quote currency per unit of base. Results are in R = net P&L per unit / stop distance.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ta.config import CFDS, pip_size
from ta.data.store import read_m1

NY = "America/New_York"
CHUNK = 4096
# Extra stop slippage per unit of the minute's overshoot past the stop. Calibrated on 95 mid-minute stop-outs replayed
# tick by tick in Dukascopy's tester (reports/jforex_stops_analysis.csv): 0.05 is unbiased on average, 0.10 keeps the
# engine worse than the tester on average (-0.28 pip) and better on 13/95 stops instead of 31/95. Cost model, not a
# strategy parameter, so it is not in Config and does not count as a trial.
STOP_OVERSHOOT = 0.10


@dataclass
class M1:
    ts: np.ndarray  # int64 ns, minute open, UTC
    bo: np.ndarray
    bh: np.ndarray
    bl: np.ndarray
    ao: np.ndarray
    ah: np.ndarray
    al: np.ndarray
    flats: np.ndarray  # Friday 16:30 NY (weekend flatten), int64 ns
    rolls: np.ndarray  # 17:00 NY rollovers (swap), int64 ns
    bc: np.ndarray | None = None  # closes, for M1 structure (S2); absent in small test frames
    ac: np.ndarray | None = None

    @classmethod
    def from_frame(cls, df: pd.DataFrame) -> "M1":
        ts = df.ts.astype("datetime64[ns, UTC]").astype("int64").to_numpy()
        days = pd.date_range(df.ts.min().tz_convert(NY).normalize() - pd.Timedelta(days=1),
                             df.ts.max().tz_convert(NY).normalize() + pd.Timedelta(days=8), freq="D")

        def stamp(hh, mm, sel):
            return (days[sel] + pd.Timedelta(hours=hh, minutes=mm)).tz_convert("UTC").as_unit("ns").asi8

        return cls(ts, *(df[c].to_numpy() for c in ("bid_o", "bid_h", "bid_l", "ask_o", "ask_h", "ask_l")),
                   flats=stamp(16, 30, days.day_of_week == 4), rolls=stamp(17, 0, days.day_of_week < 5),
                   **({"bc": df.bid_c.to_numpy(), "ac": df.ask_c.to_numpy()} if "bid_c" in df else {}))

    @classmethod
    def load(cls, pair: str) -> "M1":
        return cls.from_frame(read_m1(pair))


@dataclass(frozen=True)
class Costs:
    pip: float
    usd_quote: bool  # quote currency is USD (EURUSD...), else base is USD (USDJPY...)
    fill_through: float  # price units
    slip: float
    commission_per_lot: float  # USD per 100k base per side
    swap: float  # price units per night against the position

    @classmethod
    def for_pair(cls, pair, fill_through_pips=0.1, slip_pips=0.2, commission_per_lot=3.5, swap_pips=0.3):
        p = pip_size(pair)
        usd_quote = pair.endswith("USD") and pair not in CFDS  # CFDs pay commission on notional (per 100k USD)
        return cls(p, usd_quote, fill_through_pips * p, slip_pips * p, commission_per_lot, swap_pips * p)

    def commission(self, price):
        """Per side, in quote currency per unit of base."""
        return self.commission_per_lot / 1e5 * (1.0 if self.usd_quote else price)


def first_fill(m1: M1, lo: int, hi: int, d: int, entry: float, c: Costs) -> int:
    """First minute in [lo, hi) where a limit at `entry` fills (price must trade through by fill_through)."""
    hit = m1.al[lo:hi] <= entry - c.fill_through if d == 1 else m1.bh[lo:hi] >= entry + c.fill_through
    k = np.flatnonzero(hit)
    return lo + int(k[0]) if k.size else -1


def exit_trade(m1: M1, i: int, d: int, entry: float, stop: float, target: float, c: Costs, flat_by: int = 0):
    """Walk forward from fill minute i. The stop counts from the fill minute itself, the target only from the next
    minute, a stop and target in the same minute is a stop, and the Friday 16:30 NY minute (or the first minute at or
    after `flat_by`, ns, if earlier: S3's 17:00 UK) flattens at its open. Returns (exit_minute, reason, exit_price), or None if the data ends first."""
    flat = m1.flats[np.searchsorted(m1.flats, m1.ts[i], side="right")]
    flat = min(flat, flat_by) if flat_by else flat
    n = len(m1.ts)
    for s in range(i, n, CHUNK):
        e = min(n, s + CHUNK)
        if d == 1:
            sl, tp = m1.bl[s:e] <= stop, m1.bh[s:e] >= target + c.fill_through
        else:
            sl, tp = m1.ah[s:e] >= stop, m1.al[s:e] <= target - c.fill_through
        fl = m1.ts[s:e] >= flat
        if s == i:
            tp[0] = fl[0] = False
        k = np.flatnonzero(sl | tp | fl)
        if not k.size:
            continue
        j = s + int(k[0])
        if fl[j - s]:
            return j, "flat", (m1.bo[j] - c.slip) if d == 1 else (m1.ao[j] + c.slip)
        if sl[j - s]:
            # a gap through the stop fills at the open; hit inside the minute, it also pays part of the overshoot
            if d == 1:
                gap = j > i and m1.bo[j] <= stop
                px = min(stop - c.slip, m1.bo[j]) if gap else stop - c.slip - STOP_OVERSHOOT * (stop - m1.bl[j])
            else:
                gap = j > i and m1.ao[j] >= stop
                px = max(stop + c.slip, m1.ao[j]) if gap else stop + c.slip + STOP_OVERSHOOT * (m1.ah[j] - stop)
            return j, "stop", px
        return j, "target", target
    return None


def trade_r(m1: M1, i: int, j: int, d: int, entry: float, stop: float, exit_px: float, c: Costs) -> dict:
    """Net R plus MAE/MFE (in R) for a trade filled in minute i and closed in minute j."""
    dist = abs(entry - stop)
    nights = int(np.searchsorted(m1.rolls, m1.ts[j], side="right") - np.searchsorted(m1.rolls, m1.ts[i], side="right"))
    gross = (exit_px - entry) * d
    net = gross - c.commission(entry) - c.commission(exit_px) - nights * c.swap
    if d == 1:
        adverse, favour = m1.bl[i:j + 1].min() - entry, m1.bh[i:j + 1].max() - entry
    else:
        adverse, favour = entry - m1.ah[i:j + 1].max(), entry - m1.al[i:j + 1].min()
    return {"R": net / dist, "R_gross": gross / dist, "nights": nights, "mae_R": adverse / dist, "mfe_R": favour / dist}


def units(pair: str, equity: float, entry: float, stop: float, risk_pct: float = 0.005) -> int:
    """Position size in base units so a stop-out loses risk_pct of equity (USD account)."""
    usd_per_quote = 1.0 if pair.endswith("USD") else 1.0 / entry
    return int(np.floor(risk_pct * equity / (abs(entry - stop) * usd_per_quote)))
