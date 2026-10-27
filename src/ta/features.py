"""S1 feature detectors (docs/01 §2-4, §7, §9): ATR, swing pivots, market structure/BOS, zones with FVG,
equal highs/lows, H4 alignment.

Causal by construction: every record carries the bar index at which it becomes known (`confirm` or `t`) and
uses no bar after it. Direction is +1 (bull / swing high) or -1 (bear / swing low); shorts mirror longs.
Inputs are numpy arrays of mid prices for one pair and timeframe.
"""
import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as win

RALLY_BODY = 0.5  # an in-direction candle with body >= this·ATR is part of the rally, not the zone candle
OPEN_MIN = 0.3  # open range the zone must keep after the impulse, in ATR (review rounds 1-2: smaller is not visible)


def atr(h, l, c, n=14):
    """Wilder ATR(n); NaN until n true ranges exist."""
    tr = np.concatenate([[h[0] - l[0]], np.maximum(h[1:], c[:-1]) - np.minimum(l[1:], c[:-1])])
    out = np.full(len(h), np.nan)
    if len(h) >= n:
        out[n - 1] = tr[:n].mean()
        for i in range(n, len(h)):
            out[i] = out[i - 1] + (tr[i] - out[i - 1]) / n
    return out


def pivots(h, l, N, k=None, atr_=None) -> pd.DataFrame:
    """Swing highs/lows (§2): strict on the left, >= on the right, known at confirm = bar + N."""
    n = len(h)
    if n < 2 * N + 1:
        return pd.DataFrame({"bar": [], "confirm": [], "dir": [], "price": []}, dtype=np.int64)
    i = np.arange(N, n - N)
    hmax, lmin = win(h, N).max(1), win(l, N).min(1)
    is_hi = (h[i] > hmax[i - N]) & (h[i] >= hmax[i + 1])
    is_lo = (l[i] < lmin[i - N]) & (l[i] <= lmin[i + 1])
    if k is not None:  # size filter, ATR taken at the confirm bar
        is_hi &= h[i] - win(l, 2 * N + 1).min(1)[i - N] >= k * atr_[i + N]
        is_lo &= win(h, 2 * N + 1).max(1)[i - N] - l[i] >= k * atr_[i + N]
    out = pd.concat([pd.DataFrame({"bar": i[is_hi], "dir": 1, "price": h[i[is_hi]]}),
                     pd.DataFrame({"bar": i[is_lo], "dir": -1, "price": l[i[is_lo]]})], ignore_index=True)
    out.insert(1, "confirm", out.bar + N)
    return out.sort_values(["confirm", "dir"], ignore_index=True)


def structure(h, l, c, piv: pd.DataFrame):
    """Close-based structure state machine (§3).

    Returns (events, per_bar). events: one row per BOS with t (the breaking close), dir, kind (cont/rev),
    via (ref = broke the reference swing, flip = closed through the protected level), broken_bar/price,
    origin and protected price. per_bar: state, protected, leg_ext (max high / min low since the origin)
    and eq = (leg_ext + protected) / 2, the premium/discount line.
    """
    n = len(c)
    state, prot, ext = np.zeros(n, np.int8), np.full(n, np.nan), np.full(n, np.nan)
    confirmed = {}
    for r in piv.itertuples(index=False):
        confirmed.setdefault(r.confirm, []).append((r.dir, r.bar, r.price))
    ref = {1: None, -1: None}
    st, protected, leg, events = 0, None, np.nan, []
    for t in range(n):
        for d, b, p in confirmed.get(t, ()):
            ref[d] = (b, p)
        brk = None
        if ref[1] and c[t] > ref[1][1]:
            brk = (1, ref[1], "ref")
        elif ref[-1] and c[t] < ref[-1][1]:
            brk = (-1, ref[-1], "ref")
        elif st == 1 and c[t] < protected[1]:
            brk = (-1, protected, "flip")
        elif st == -1 and c[t] > protected[1]:
            brk = (1, protected, "flip")
        if brk:
            d, (bb, bp), via = brk
            o = bb + int(np.argmin(l[bb:t + 1]) if d == 1 else np.argmax(h[bb:t + 1]))
            protected = (o, l[o] if d == 1 else h[o])
            leg = h[o:t + 1].max() if d == 1 else l[o:t + 1].min()
            events.append((t, d, "cont" if st == d else "rev", via, bb, bp, o, protected[1]))
            st = d
            if via == "ref":
                ref[d] = None  # the next confirmed swing becomes the reference
        elif st:
            leg = max(leg, h[t]) if st == 1 else min(leg, l[t])
        state[t], ext[t] = st, leg
        prot[t] = protected[1] if protected else np.nan
    ev = pd.DataFrame(events, columns=["t", "dir", "kind", "via", "broken_bar", "broken_price", "origin", "protected"])
    return ev, pd.DataFrame({"state": state, "protected": prot, "leg_ext": ext, "eq": (ext + prot) / 2})


def zones(o, h, l, c, events: pd.DataFrame, atr_, m, zone_body=False) -> pd.DataFrame:
    """One zone per BOS (§4). The FVG may complete on the bar after the BOS, so `t` (creation) is the BOS
    close, or the next close when only that bar completes the gap. A BOS with no impulse or no FVG gives none,
    and so does one whose zone was retested after the impulse (no open range of at least OPEN_MIN·ATR left)."""
    rows, n = [], len(c)
    for e in events.itertuples(index=False):
        d, tb, org = e.dir, e.t, e.origin
        js = np.arange(org + 1, tb + 1)
        ok = (c[js] - o[js]) * d >= m * atr_[js]  # NaN ATR compares False
        if not ok.any():
            continue
        j = js[ok.argmax()]
        z = j - 1  # "last candle before the impulse": the small candle before the rally, not a rally candle
        while z > org and (c[z] - o[z]) * d >= RALLY_BODY * atr_[z]:
            z -= 1
        ks = np.arange(j, min(tb + 1, n - 1))  # all three FVG candles inside [j-1, tb+1]
        fvg = l[ks + 1] > h[ks - 1] if d == 1 else h[ks + 1] < l[ks - 1]
        if not fvg.any():
            continue
        k = ks[fvg.argmax()]
        created = max(tb, k + 1)
        if d == 1:
            lo, hi = l[org:j].min(), max(o[z], c[z]) if zone_body else h[z]
        else:
            lo, hi = min(o[z], c[z]) if zone_body else l[z], h[org:j].max()
        after = slice(j + 1, created + 1)  # JeaFx's imbalance: price left the zone and has not come back
        gap = l[after].min() - hi if d == 1 else lo - h[after].max()
        if not gap >= OPEN_MIN * atr_[created]:
            continue
        rows.append((created, tb, d, e.kind, org, j, z, lo, hi, k, gap))
    cols = ["t", "t_bos", "dir", "kind", "origin", "impulse", "zone_bar", "low", "high", "fvg_bar", "open_range"]
    return pd.DataFrame(rows, columns=cols)


def equal_levels(h, l, piv: pd.DataFrame, atr_, tol=0.1) -> pd.DataFrame:
    """Equal highs (dir +1) / lows (dir -1) (§9): two confirmed swings within tol·ATR (at confirm) with
    nothing trading beyond the level between them. Known at `confirm`. `swept` is the first later bar
    trading beyond the level (-1 if never); it is a future fact, so only use it when swept <= now."""
    rows = []
    for d in (1, -1):
        ext = h if d == 1 else -l  # lows become negated highs, so one code path serves both
        live, last = [], -1  # live: [bar, price, highest ext since its confirm]
        for r in piv[piv.dir == d].itertuples(index=False):
            seg = ext[last + 1:r.confirm + 1].max() if r.confirm > last else -np.inf
            last = r.confirm
            for e in live:
                e[2] = max(e[2], seg)
            p, tv = r.price * d, tol * atr_[r.confirm]
            for e in reversed(live):
                level = max(p, e[1])
                if abs(p - e[1]) <= tv and e[2] <= level:
                    rows.append((r.confirm, d, e[0], r.bar, level * d))
                    break
            # shortcut: drops swings exceeded by more than today's tolerance; a later, wider tolerance
            # could in theory still pair them. Upgrade to an unbounded list if the veto proves sensitive.
            live = [e for e in live if e[2] <= e[1] + tv]
            live.append([r.bar, p, -np.inf])
    out = pd.DataFrame(rows, columns=["confirm", "dir", "bar1", "bar2", "price"])
    out["swept"] = [_first_beyond(h, l, r.confirm + 1, r.dir, r.price) for r in out.itertuples(index=False)]
    return out.sort_values(["confirm", "dir"], ignore_index=True)


def _first_beyond(h, l, start, d, price, chunk=2000):
    for s in range(start, len(h), chunk):
        hit = np.flatnonzero(h[s:s + chunk] > price if d == 1 else l[s:s + chunk] < price)
        if hit.size:
            return s + int(hit[0])
    return -1


def htf_index(ltf_close_ts, htf_close_ts):
    """For each lower-timeframe bar, the index of the last higher-timeframe bar closed by its close (-1: none)."""
    return np.searchsorted(np.asarray(htf_close_ts), np.asarray(ltf_close_ts), side="right") - 1
