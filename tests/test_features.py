import numpy as np
import pandas as pd
import pytest

from ta.features import atr, equal_levels, htf_index, pivots, structure, zones

# Hand-built leg (N=1): swing high @2 (1.5), swing low @4 (0.8), bullish BOS @6 with impulse @5 and an FVG
# (l6 > h4); swing high @7 (1.7), swing low @9 (1.25), continuation BOS @10 with no FVG; bearish BOS @11.
H = np.array([1.0, 1.2, 1.5, 1.4, 1.2, 1.3, 1.6, 1.7, 1.65, 1.45, 1.8, 1.76])
L = np.array([0.9, 1.0, 1.2, 1.0, 0.8, 0.9, 1.25, 1.5, 1.3, 1.25, 1.35, 1.1])
C = np.array([0.95, 1.1, 1.3, 1.1, 0.9, 1.25, 1.55, 1.65, 1.35, 1.4, 1.75, 1.15])
O = np.concatenate([[0.95], C[:-1]])
ATR = np.full(len(C), 0.1)


def test_atr_is_wilder():
    h, l, c = np.full(20, 2.0), np.full(20, 1.0), np.full(20, 1.5)
    a = atr(h, l, c)
    assert np.isnan(a[12]) and a[13] == pytest.approx(1.0) and a[-1] == pytest.approx(1.0)


def test_pivots_confirm_n_bars_later_and_tie_rules():
    p = pivots(H, L, 1)
    assert p[p.dir == 1][["bar", "confirm", "price"]].values.tolist()[:2] == [[2, 3, 1.5], [7, 8, 1.7]]
    assert p[p.dir == -1].bar.tolist() == [4, 9]
    flat = pivots(np.array([1, 2, 2, 1.0]), np.zeros(4), 1)
    assert flat[flat.dir == 1].bar.tolist() == [1]  # equal right neighbour allowed, equal left is not


def test_pivot_size_filter():
    assert pivots(H, L, 1, k=100, atr_=ATR).empty


def test_structure_bos_kinds_origin_and_leg():
    ev, bar = structure(H, L, C, pivots(H, L, 1))
    assert ev[["t", "dir", "kind", "via", "broken_bar", "origin"]].values.tolist() == [
        [6, 1, "rev", "ref", 2, 4], [10, 1, "cont", "ref", 7, 9], [11, -1, "rev", "ref", 9, 10]]
    assert bar.state.tolist() == [0] * 6 + [1] * 5 + [-1]
    assert bar.protected[6] == 0.8 and bar.leg_ext[7] == 1.7 and bar["eq"][7] == pytest.approx(1.25)
    assert bar.protected[11] == 1.8


def test_structure_flip_through_protected():
    # bull BOS @5 (origin @2, protected 0.8, not a pivot because of the equal low @1..); the reference low
    # is the older 0.5 swing, so the close at 0.7 flips the trend through the protected level
    h = np.array([1.0, 0.8, 1.2, 1.0, 1.0, 1.3, 1.25])
    l = np.array([0.9, 0.5, 0.8, 0.8, 0.8, 0.9, 0.65])
    c = np.array([0.95, 0.6, 1.1, 0.9, 0.85, 1.25, 0.7])
    ev, _ = structure(h, l, c, pivots(h, l, 1))
    assert ev[["t", "dir", "via", "broken_bar", "origin"]].values.tolist() == [[5, 1, "ref", 2, 2], [6, -1, "flip", 2, 5]]


def test_zones_need_impulse_and_fvg():
    ev, _ = structure(H, L, C, pivots(H, L, 1))
    z = zones(O, H, L, C, ev, ATR, m=1.0)
    assert z[["t", "t_bos", "origin", "impulse", "zone_bar", "fvg_bar"]].values.tolist() == [[6, 6, 4, 5, 4, 5]]
    assert (z.low[0], z.high[0]) == (0.8, 1.2)  # wick to wick, origin low included
    assert zones(O, H, L, C, ev, ATR, m=1.0, zone_body=True).high[0] == max(O[4], C[4])
    assert zones(O, H, L, C, ev, ATR, m=5.0).empty  # no candle big enough


def test_zone_fvg_may_complete_one_bar_after_bos():
    # impulse is the BOS bar itself (@2); the gap low[3] > high[1] only exists at the close of bar 3
    h = np.array([1.0, 1.1, 1.6, 1.7, 1.65])
    l = np.array([0.9, 0.8, 1.05, 1.15, 1.2])
    c = np.array([0.95, 0.9, 1.55, 1.6, 1.3])
    o = np.concatenate([[0.95], c[:-1]])
    ev = pd.DataFrame({"t": [2], "dir": [1], "kind": ["cont"], "origin": [1]})
    z = zones(o, h, l, c, ev, np.full(5, 0.1), m=1.0)
    assert z[["t", "t_bos", "impulse", "zone_bar", "fvg_bar"]].values.tolist() == [[3, 2, 2, 1, 2]]
    assert zones(o[:3], h[:3], l[:3], c[:3], ev, np.full(3, 0.1), m=1.0).empty  # unknown at the BOS close


def test_equal_lows_and_sweep():
    h = np.full(10, 2.0)
    l = np.array([1.5, 1.2, 1.0, 1.3, 1.4, 1.005, 1.3, 1.4, 1.2, 0.9])
    lev = equal_levels(h, l, pivots(h, l, 1), np.full(10, 0.1))
    assert lev[["confirm", "dir", "bar1", "bar2", "price", "swept"]].values.tolist() == [[6, -1, 2, 5, 1.0, 9]]
    l[3] = 0.95  # price traded below the first low in between -> no equal lows
    assert equal_levels(h, l, pivots(h, l, 1), np.full(10, 0.1)).empty


def test_htf_index_uses_last_closed_bar():
    h4 = pd.to_datetime(["2024-01-02 02:00", "2024-01-02 06:00"])
    m15 = pd.to_datetime(["2024-01-02 01:45", "2024-01-02 02:00", "2024-01-02 05:45"])
    assert htf_index(m15, h4).tolist() == [-1, 0, 0]


def test_prefix_invariance_random_walk():
    rng = np.random.default_rng(7)
    c = 1.1 + np.cumsum(rng.normal(0, 1e-3, 4000))
    o = np.concatenate([[c[0]], c[:-1]])
    h = np.maximum(o, c) + rng.uniform(0, 8e-4, c.size)
    l = np.minimum(o, c) - rng.uniform(0, 8e-4, c.size)

    def run(n):
        a = atr(h[:n], l[:n], c[:n])
        p = pivots(h[:n], l[:n], 3, k=0.5, atr_=a)
        ev, bar = structure(h[:n], l[:n], c[:n], p)
        return a, p, ev, bar, zones(o[:n], h[:n], l[:n], c[:n], ev, a, 1.0), equal_levels(h[:n], l[:n], p, a)

    D = 2500
    full, pre = run(4000), run(D)
    assert np.array_equal(full[0][:D], pre[0], equal_nan=True)
    pd.testing.assert_frame_equal(full[1][full[1].confirm < D].reset_index(drop=True), pre[1])
    pd.testing.assert_frame_equal(full[2][full[2].t < D].reset_index(drop=True), pre[2])
    pd.testing.assert_frame_equal(full[3].iloc[:D], pre[3])
    pd.testing.assert_frame_equal(full[4][full[4].t < D].reset_index(drop=True), pre[4])
    fl = full[5][full[5].confirm < D].reset_index(drop=True)
    fl.loc[fl.swept >= D, "swept"] = -1  # sweeps after D are unknown at D
    pd.testing.assert_frame_equal(fl, pre[5])
    assert len(full[2]) > 50 and len(full[4]) > 5 and len(full[5]) > 5  # the check is not vacuous


def bars(rows):
    o, h, l, c = (np.array(x, dtype=float) for x in zip(*rows))
    return o, h, l, c


def test_zone_rejected_when_retested_after_impulse():
    # zone candle @1 (high 1.1), impulse @2, bar 3 wicks back into the zone, the FVG only forms at k=3
    o, h, l, c = bars([(0.95, 1.0, 0.9, 0.95), (0.95, 1.1, 0.8, 0.9), (0.9, 1.55, 0.88, 1.5),
                       (1.5, 1.5, 1.05, 1.4), (1.4, 1.8, 1.6, 1.75)])
    ev = pd.DataFrame({"t": [4], "dir": [1], "kind": ["cont"], "origin": [1]})
    assert zones(o, h, l, c, ev, np.full(5, 0.1), m=1.0).empty
    l[3] = 1.2  # no retest: the open range above the zone survives
    assert zones(o, h, l, c, ev, np.full(5, 0.1), m=1.0).open_range[0] == pytest.approx(0.1)


def test_zone_candle_skips_rally_candles():
    # @2 is already a rally candle (body 0.08 >= 0.5·ATR), so the zone is the small candle @1 before it
    o, h, l, c = bars([(0.95, 1.0, 0.9, 0.95), (0.95, 0.97, 0.8, 0.92), (0.92, 1.02, 0.91, 1.0),
                       (1.0, 1.55, 0.99, 1.5), (1.5, 1.7, 1.1, 1.6)])
    ev = pd.DataFrame({"t": [4], "dir": [1], "kind": ["cont"], "origin": [1]})
    z = zones(o, h, l, c, ev, np.full(5, 0.1), m=1.0)
    assert z[["zone_bar", "impulse", "low", "high"]].values.tolist() == [[1, 3, 0.8, 0.97]]
