import numpy as np
import pandas as pd
import pytest

from ta.backtest import resolve
from ta.broker import M1
from ta.s2 import M15_NS, MIN_NS, S2Config, episodes, grid

X = 2.2  # mirror axis: price p -> X - p turns the bearish fixture into its bullish twin
N15 = 60


def bearish():
    """M15 bar 4 wicks to 1.1060 through equal highs at 1.1050 and closes at 1.1045 (the sweep). On M1 (no spread):
    swing low 1.1035 at minute 65, minute 76 is the impulse closing at 1.1025 (BOS), minute 77 completes the FVG.
    M1 zone [1.1038, 1.1042] forms at minute 77; short at 1.1038, stop 1.1061 (23 pips), target 1.0969.
    Minute 200 trades up to 1.1039 and fills."""
    n1 = N15 * 15
    o, c, h, l = np.full(n1, 1.1040), np.full(n1, 1.1040), np.full(n1, 1.1042), np.full(n1, 1.1038)
    l[65] = 1.1035
    h[70] = 1.1060
    o[76], h[76], l[76], c[76] = 1.1040, 1.1041, 1.1024, 1.1025
    o[77], h[77], l[77], c[77] = 1.1025, 1.1026, 1.1020, 1.1022
    o[78:], c[78:], h[78:], l[78:] = 1.1020, 1.1020, 1.1022, 1.1018
    h[200] = 1.1039
    ts = pd.Series(pd.date_range("2024-01-09 00:00", periods=N15, freq="15min", tz="UTC"))
    h15, l15, c15 = np.full(N15, 1.1042), np.full(N15, 1.1038), np.full(N15, 1.1040)
    h15[4], c15[4] = 1.1060, 1.1045
    f = {"pair": "EURUSD", "ts": ts, "h": h15, "l": l15, "c": c15, "atr": np.full(N15, 0.001),
         "eql": pd.DataFrame({"confirm": [2], "dir": [1], "bar1": [0], "bar2": [1], "price": [1.1050], "swept": [4]}),
         "h4atr": np.full(N15, 0.01), "fillable": np.ones(N15, bool), "blackout": np.zeros(N15, bool)}
    return f, (o, h, l, c)


def build(f, ohlc, mirror=False):
    o, h, l, c = ohlc
    if mirror:
        f = dict(f, h=X - f["l"], l=X - f["h"], c=X - f["c"],
                 eql=f["eql"].assign(dir=-f["eql"].dir, price=X - f["eql"].price))
        o, h, l, c = X - o, X - l, X - h, X - c
    ts = pd.date_range("2024-01-09 00:00", periods=len(o), freq="1min", tz="UTC")
    m1 = M1.from_frame(pd.DataFrame({"ts": ts, **{f"{s}_{k}": v for s in ("bid", "ask")
                                                  for k, v in zip("ohlc", (o, h, l, c))}}))
    return f, m1


@pytest.mark.parametrize("flip", [False, True])
def test_m15_sweep_then_m1_bos_zone_and_order(flip):
    f, m1 = build(*bearish(), mirror=flip)
    ep = episodes(f, m1, S2Config())
    assert ep[["dir", "leg", "zone_t", "t_bos", "fill_bar", "fill_min"]].values.tolist() == [[1 if flip else -1, 4, 5, 5, 13, 200]]
    assert ep.place_ns[0] == m1.ts[77] + MIN_NS
    want = np.array([1.1038, 1.1061, 1.1038 - 3 * 0.0023])
    assert ep[["entry", "stop", "target"]].values[0] == pytest.approx(X - want if flip else want)
    mid = episodes(f, m1, S2Config(entry_at="mid"))
    assert mid.entry[0] == pytest.approx(X - 1.1040 if flip else 1.1040) and mid.fill_min[0] == -1  # 1.1039 < 1.1040


def test_resolve_uses_the_m1_order_times():
    f, m1 = build(*bearish())
    r = resolve(f, m1, S2Config()).iloc[0]
    assert (r.place_ts, r.fill_ts) == (m1.ts[77] + MIN_NS, m1.ts[200]) and r.reason in ("stop", "target", "flat", "open")


def test_body_close_beyond_the_pool_is_a_break_not_a_sweep():
    f, ohlc = bearish()
    f["c"][4] = 1.1055
    assert episodes(*build(f, ohlc), S2Config()).empty


def test_close_beyond_the_sweep_extreme_before_the_bos_kills_it():
    f, (o, h, l, c) = bearish()
    h[75], c[75] = 1.1063, 1.1062  # above 1.1060 + 0.1 ATR
    assert episodes(*build(f, (o, h, l, c)), S2Config()).empty


def test_bos_must_come_within_w_bars():
    f, (o, h, l, c) = bearish()
    o[76:], c[76:], h[76:], l[76:] = 1.1040, 1.1040, 1.1042, 1.1038
    o[76 + 30:] = c[76 + 30:] = 1.1040  # move the BOS pattern to minute 106 (M15 bar 7 = sweep + 3)
    seg = bearish()[1]
    for a, b in zip((o, h, l, c), seg):
        a[106:] = b[76:len(a) - 30]
    assert episodes(*build(f, (o, h, l, c)), S2Config(W=2)).empty
    assert len(episodes(*build(f, (o, h, l, c)), S2Config(W=3))) == 1


def test_min_stop_skip_and_widen():
    f, (o, h, l, c) = bearish()
    f["h"][4], h[70] = 1.1046, 1.1046  # sweep extreme 1.1046 -> stop 9 pips above the entry
    f["eql"].loc[0, "price"], f["c"][4] = 1.1043, 1.1040
    f, m1 = build(f, (o, h, l, c))
    assert episodes(f, m1, S2Config()).empty
    assert episodes(f, m1, S2Config(min_stop_mode="widen")).dist[0] == pytest.approx(0.0015)


def test_order_cancelled_when_price_trades_beyond_the_sweep_extreme():
    f, (o, h, l, c) = bearish()
    f["fillable"][:] = False  # touches outside the session: no fill
    h[150] = 1.1065
    f, m1 = build(f, (o, h, l, c))
    ep = episodes(f, m1, S2Config())
    assert (ep.end_ns[0], ep.fill_min[0], ep.end_bar[0]) == (m1.ts[150] + MIN_NS, -1, 10)


def test_expiry_48_m15_bars_after_the_zone_bar():
    f, (o, h, l, c) = bearish()
    h[200] = 1.1022
    f, m1 = build(f, (o, h, l, c))
    ep = episodes(f, m1, S2Config())
    t0 = f["ts"].astype("datetime64[ns, UTC]").astype("int64").to_numpy()
    assert (ep.end_ns[0], ep.end_bar[0], ep.fill_min[0]) == (t0[5 + 48] + M15_NS, 53, -1)


def test_grid_is_the_frozen_4():
    g = grid()
    assert len(set(g)) == 4 and all(c.target == "T1" and c.K == 48 and c.entry_tf == "M1" for c in g)


def test_m4_neighbours_for_s2_step_in_w_only():
    from ta.m4 import STAGES, neighbours
    assert neighbours((8, "mid", "T1"), STAGES["S2"][0]) == [(8, "mid", "T1"), (24, "mid", "T1")]
