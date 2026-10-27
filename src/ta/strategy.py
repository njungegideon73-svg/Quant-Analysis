"""S1 rules on top of the detectors (docs/01 §5-9): zone life cycle -> one order episode per zone.

An episode is what one zone would do on its own: the M15 close where its limit order is placed, the close where
the order stops being valid, and the first M15 bar where it could fill. One-setup-per-pair and the portfolio
limits are applied afterwards (backtest.py). An order placed at the close of bar p can fill from bar p+1.
"""
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar
from pandas.tseries.offsets import Easter

from ta.config import DATA, pip_size
from ta.features import atr, equal_levels, htf_index, pivots, structure, zones

NY, LDN = "America/New_York", "Europe/London"


@dataclass(frozen=True)
class Config:
    # Stage A grid (docs/03 §3)
    N: int = 3
    m: float = 1.0
    b: float = 0.10
    K: int = 96
    entry_at: str = "proximal"  # proximal | mid
    target: str = "T1"  # T1 fixed rr | T2 structural >= rr
    # Stage B filters, Stage A defaults
    zone_pick: str = "newest"  # newest | extreme
    min_stop_mode: str = "skip"  # skip | widen
    liq_veto: bool = False
    session: str = "london_ny"  # london_ny | all
    zone_body: bool = False
    htf_location: bool = False
    k: float | None = None
    # fixed
    N_h4: int = 3
    rr: float = 3.0
    min_stop_pips: float = 15.0
    cap_h4_atr: float = 3.0
    liq_atr: float = 2.0
    fill_through_pips: float = 0.1
    slip_pips: float = 0.2
    commission_per_lot: float = 3.5
    swap_pips: float = 0.3
    max_open: int = 4
    max_ccy: int = 2

    def to_dict(self):
        return asdict(self)


def blackout_days(start, end) -> tuple[set, set]:
    """(NY dates, London dates) with no trading: US federal holidays, UK bank holidays, Dec 24 - Jan 2."""
    us = {d.date() for d in USFederalHolidayCalendar().holidays(start, end)}
    uk = set()
    for y in range(pd.Timestamp(start).year, pd.Timestamp(end).year + 1):
        easter = pd.Timestamp(y, 1, 1) + Easter()
        may, aug = pd.date_range(f"{y}-05-01", f"{y}-05-31"), pd.date_range(f"{y}-08-01", f"{y}-08-31")
        uk |= {(easter - pd.Timedelta(days=2)).date(), (easter + pd.Timedelta(days=1)).date(),
               may[may.day_of_week == 0][0].date(), may[may.day_of_week == 0][-1].date(), aug[aug.day_of_week == 0][-1].date()}
        us |= {pd.Timestamp(y, 12, d).date() for d in range(24, 32)} | {pd.Timestamp(y, 1, d).date() for d in (1, 2)}
    return us, uk


def time_masks(ts: pd.Series, session: str):
    """Per M15 bar (by its open time): (fillable, blackout). docs/01 §8 plus the holiday blackout (docs/05)."""
    ny, ldn = ts.dt.tz_convert(NY), ts.dt.tz_convert(LDN)
    us, uk = blackout_days(ts.min() - pd.Timedelta(days=1), ts.max() + pd.Timedelta(days=1))
    black = ny.dt.date.isin(us).to_numpy() | ldn.dt.date.isin(uk).to_numpy()
    mins, wd = (ny.dt.hour * 60 + ny.dt.minute).to_numpy(), ny.dt.day_of_week.to_numpy()
    ok = ~black
    if session == "london_ny":
        ok &= ((ldn.dt.hour >= 7) & (ldn.dt.hour < 17)).to_numpy()
    ok &= ~((mins >= 16 * 60 + 45) & (mins < 17 * 60 + 30))  # rollover
    ok &= ~(((wd == 4) & (mins >= 15 * 60)) | (wd == 5) | ((wd == 6) & (mins < 17 * 60)))  # weekend
    return ok, black


def prepare(pair: str, cfg: Config, root=DATA) -> dict:
    """Everything episodes() needs for one pair: mid/bid/ask M15 arrays, features, H4 context, time masks."""
    m15 = pd.read_parquet(root / "derived" / pair / "M15.parquet")
    h4 = pd.read_parquet(root / "derived" / pair / "H4.parquet")
    return prepare_frames(pair, m15, h4, cfg)


def prepare_frames(pair, m15, h4, cfg: Config) -> dict:
    o, h, l, c = (m15[f"mid_{x}"].to_numpy() for x in "ohlc")
    a = atr(h, l, c)
    piv = pivots(h, l, cfg.N, cfg.k, a)
    ev, _ = structure(h, l, c, piv)
    z = zones(o, h, l, c, ev, a, cfg.m, cfg.zone_body)
    z["leg"] = np.searchsorted(ev.t[ev.kind == "rev"].to_numpy(), z.t_bos.to_numpy(), side="right")
    h4h, h4l, h4c = (h4[f"mid_{x}"].to_numpy() for x in "hlc")
    _, h4bar = structure(h4h, h4l, h4c, pivots(h4h, h4l, cfg.N_h4))
    ix = htf_index(m15.close_ts, h4.close_ts)
    take = lambda arr, fill: np.where(ix >= 0, np.asarray(arr)[ix.clip(0)], fill)
    fill_ok, black = time_masks(m15.ts, cfg.session)
    return {"pair": pair, "ts": m15.ts, "close_ts": m15.close_ts, "o": o, "h": h, "l": l, "c": c,
            "bid_h": m15.bid_h.to_numpy(), "ask_l": m15.ask_l.to_numpy(), "atr": a, "zones": z,
            "eql": equal_levels(h, l, piv, a) if cfg.liq_veto else None,
            "h4state": take(h4bar.state, 0), "h4eq": take(h4bar["eq"], np.nan),
            "h4atr": take(atr(h4h, h4l, h4c), np.nan), "fillable": fill_ok, "blackout": black}


def episodes(f: dict, cfg: Config) -> pd.DataFrame:
    """One row per continuation zone that gets an order: place / end bars (M15 closes), first fillable touch."""
    pip, n, rows = pip_size(f["pair"]), len(f["c"]), []
    ft = cfg.fill_through_pips * pip
    for z in f["zones"].itertuples(index=False):
        if z.kind != "cont" or f["blackout"][z.t]:
            continue
        d, A = z.dir, f["atr"][z.t]
        near, far = (z.high, z.low) if d == 1 else (z.low, z.high)
        entry = near if cfg.entry_at == "proximal" else (z.high + z.low) / 2
        stop = far - d * cfg.b * A
        dist = (entry - stop) * d
        if dist < cfg.min_stop_pips * pip:
            if cfg.min_stop_mode == "skip":
                continue
            dist = cfg.min_stop_pips * pip
            stop = entry - d * dist
        if not dist <= cfg.cap_h4_atr * f["h4atr"][z.t]:
            continue
        s = np.arange(z.t, min(z.t_bos + cfg.K + 1, n - 1) + 1)  # decision closes; expiry fails at t_b+K+1
        ext = f["h"] if d == 1 else -f["l"]
        leg = np.maximum.accumulate(ext[z.origin:s[-1] + 1])[s - z.origin] * d  # leg_high (long) / leg_low (short)
        cond = (entry - (leg + far) / 2) * d <= 0  # discount (long) / premium (short)
        cond &= f["h4state"][s] == d
        if cfg.target == "T2":
            cond &= (leg - entry) * d >= cfg.rr * dist
        if cfg.htf_location:
            cond &= (entry - f["h4eq"][s]) * d <= 0
        if cfg.liq_veto:
            cond &= ~_veto(f["eql"], s, d, far, cfg.liq_atr * A)
        dead = ((f["c"][s] - far) * d < 0) | (s - z.t_bos > cfg.K)
        touch = (f["l"][s] <= near) if d == 1 else (f["h"][s] >= near)
        touch[0] = False  # bars up to creation are clear by the open-range rule
        first = np.flatnonzero(cond | dead | touch)
        if not first.size or dead[first[0]] or touch[first[0]] or not cond[first[0]]:
            continue  # killed or touched before an order could exist
        i = first[0]
        stops = np.flatnonzero(~cond[i + 1:] | dead[i + 1:])
        e = i + 1 + stops[0] if stops.size else len(s) - 1
        act = s[i + 1:e + 1]
        hit = f["ask_l"][act] <= entry - ft if d == 1 else f["bid_h"][act] >= entry + ft
        fills = np.flatnonzero(hit & f["fillable"][act])
        fb = int(act[fills[0]]) if fills.size else -1
        if cfg.target == "T1":
            target = entry + d * cfg.rr * dist
        else:
            target = leg[fb - z.t - 1] if fb >= 0 else np.nan  # leg extreme at the close before the fill
        rows.append((z.t, z.t_bos, d, z.leg, z.low, z.high, int(s[i]), int(s[e]), fb, entry, stop, target, dist))
    return pd.DataFrame(rows, columns=["zone_t", "t_bos", "dir", "leg", "zone_low", "zone_high", "place_bar",
                                       "end_bar", "fill_bar", "entry", "stop", "target", "dist"])


def _veto(eql, s, d, far, width):
    """Unswept equal lows just below a long zone (equal highs above a short) at each decision close."""
    lv = eql[(eql.dir == -d) & ((eql.price - far) * d < 0) & ((far - eql.price) * d < width)]
    out = np.zeros(len(s), bool)
    for r in lv.itertuples(index=False):
        out |= (s >= r.confirm) & ((r.swept < 0) | (s < r.swept))
    return out
