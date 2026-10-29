"""S2 rules (docs/06 §1-3, §11): an M15 bar wicks through equal highs/lows and closes back -> within the next W
M15 bars, the first M1 reversal BOS whose leg leaves a valid M1 zone -> limit at that zone, stop beyond the sweep
extreme, target 3R.

Same episode columns as strategy.episodes() (M15 bars), plus the order's M1 timing, which resolve() uses instead
of the M15 bars. Comments describe the bearish case (equal highs swept, short); `side` is the pool's side
(+1 highs) and the trade direction is d = -side.
"""
from dataclasses import dataclass
from itertools import product
from typing import ClassVar

import numpy as np
import pandas as pd

from ta.broker import M1
from ta.config import pip_size
from ta.features import atr, pivots, structure, zones
from ta.strategy import Config

LOOK = 60  # M1 bars before the sweep bar closes, so M1 pivots and ATR exist when the window opens
M15_NS, MIN_NS = 15 * 60 * 10**9, 60 * 10**9
COLS = ["zone_t", "t_bos", "dir", "leg", "zone_low", "zone_high", "swing", "place_bar", "end_bar", "fill_bar",
        "entry", "stop", "target", "dist", "zone_ns", "place_ns", "end_ns", "fill_min", "flat_ns"]


@dataclass(frozen=True)
class S2Config(Config):
    pools: ClassVar[bool] = True  # prepare_frames() builds equal highs/lows
    strategy: str = "S2"
    entry_tf: str = "M1"
    W: int = 8  # M15 bars after the sweep bar in which the M1 BOS must come
    K: int = 48  # expiry: M15 bars after the bar the zone forms in (fixed)
    b: float = 0.10  # stop and invalidation buffer beyond the sweep extreme, in ATR_M15 at the sweep bar (fixed)

    def sweeps(self, f: dict) -> pd.DataFrame:
        """Sweep bar `s` and trade dir `d`, plus S3's `opp` (Tasia target), `noon_ns` (fill deadline), `flat_ns` (time exit)."""
        return pd.DataFrame(sweeps(f), columns=["s", "d"]).assign(opp=np.nan, noon_ns=np.iinfo(np.int64).max, flat_ns=0)


def grid() -> list[S2Config]:
    """The frozen S2 grid (docs/06 §11): 4 configs, T1 and no H4 filter."""
    return [S2Config(W=w, entry_at=e) for w, e in product((8, 24), ("proximal", "mid"))]


def sweeps(f: dict) -> list[tuple[int, int]]:
    """(sweep bar, trade dir) for every M15 bar that wicks through an equal-level pool and closes back (§3)."""
    e, c = f["eql"], f["c"]
    ok = (e.swept >= 0) & ((c[e.swept.clip(lower=0)] - e.price) * e.dir <= 0)
    return sorted(set(zip(e.swept[ok].tolist(), (-e.dir[ok]).tolist())))


def episodes(f: dict, m1: M1, cfg: S2Config) -> pd.DataFrame:
    """One row per S2 order. zone_ns / place_ns: close of the M1 bar the zone forms on (fillable from the next
    minute); end_ns: close of the minute that cancels it, or of the K-th M15 bar; fill_min: M1 index or -1."""
    assert cfg.target in ("T1", "Tasia"), "S2 uses T1 only (docs/06 §11), S3 T1 or Tasia (docs/09 §4)"
    pip, n, rows = pip_size(f["pair"]), len(f["c"]), []
    ft = cfg.fill_through_pips * pip
    bar_ns = f["ts"].astype("datetime64[ns, UTC]").astype("int64").to_numpy()
    ts = m1.ts
    mo, mh, ml, mc = ((getattr(m1, "b" + x) + getattr(m1, "a" + x)) / 2 for x in "ohlc")
    ix15 = np.searchsorted(bar_ns, ts, side="right") - 1
    for sw_ in cfg.sweeps(f).itertuples(index=False):
        s, d = sw_.s, sw_.d
        if s + cfg.W >= n:
            continue
        side, buf = -d, cfg.b * f["atr"][s]
        j0, j1 = np.searchsorted(ts, [bar_ns[s] + M15_NS, bar_ns[s + cfg.W] + M15_NS])  # minutes of bars s+1..s+W
        lo = max(j0 - LOOK, 0)
        sl = slice(lo, min(j1 + 1, len(ts)))  # one extra minute: the FVG may complete just after the BOS
        o, h, l, c = mo[sl], mh[sl], ml[sl], mc[sl]
        x, y = (h if side == 1 else -l), c * side  # beyond the pool = up, in pool space
        ext0 = f["h"][s] if side == 1 else -f["l"][s]
        run = np.maximum.accumulate(np.concatenate([[ext0], x[j0 - lo:]]))[:-1]  # sweep extreme before each minute
        failed = np.flatnonzero(y[j0 - lo:] > run + buf)  # closed beyond the sweep extreme: the sweep failed
        stop_t = min(j1, j0 + failed[0] if failed.size else j1) - lo
        ev, _ = structure(h, l, c, pivots(h, l, cfg.N))
        ev = ev[(ev.dir == d) & (ev.t >= j0 - lo) & (ev.t < stop_t)]
        z = zones(o, h, l, c, ev, atr(h, l, c), cfg.m, cfg.zone_body)
        if z.empty:
            continue
        z = z.iloc[0]
        zt = lo + int(z.t)
        sw = max(ext0, x[j0 - lo:int(z.t) + 1].max()) * side  # sweep extreme (price) up to the zone
        k15 = ix15[zt]
        if f["blackout"][k15]:
            continue
        near, far = (z.high, z.low) if d == 1 else (z.low, z.high)
        entry = near if cfg.entry_at == "proximal" else (z.high + z.low) / 2
        stop = sw - d * buf
        dist = (entry - stop) * d
        if dist < cfg.min_stop_pips * pip:
            if cfg.min_stop_mode == "skip":
                continue
            dist = cfg.min_stop_pips * pip
            stop = entry - d * dist
        if not dist <= cfg.cap_h4_atr * f["h4atr"][k15]:
            continue
        if cfg.target == "T1":
            target = entry + d * cfg.rr * dist
        elif (sw_.opp - entry) * d >= cfg.rr * dist:
            target = sw_.opp
        else:
            continue
        end_ns = min(bar_ns[min(k15 + cfg.K, n - 1)] + M15_NS, sw_.noon_ns)
        act = np.arange(zt + 1, np.searchsorted(ts, end_ns))
        if not act.size:  # the zone formed after the fill deadline
            continue
        beyond = ml[act] < sw if d == 1 else mh[act] > sw
        dead = np.flatnonzero(((mc[act] - far) * d < 0) | beyond)  # a fill in the killing minute comes first
        if dead.size:
            act = act[:dead[0] + 1]
            end_ns = ts[act[-1]] + MIN_NS
        hit = m1.al[act] <= entry - ft if d == 1 else m1.bh[act] >= entry + ft
        fills = np.flatnonzero(hit & f["fillable"][ix15[act]])
        fm = int(act[fills[0]]) if fills.size else -1
        place_ns = ts[zt] + MIN_NS
        end_bar = int(np.searchsorted(bar_ns, end_ns - 1, side="right") - 1)
        rows.append((k15, int(ix15[lo + int(z.t_bos)]), d, s, z.low, z.high, sw, k15, end_bar,
                     int(ix15[fm]) if fm >= 0 else -1, entry, stop, target, dist, place_ns, place_ns, end_ns, fm,
                     sw_.flat_ns))
    return pd.DataFrame(rows, columns=COLS)
