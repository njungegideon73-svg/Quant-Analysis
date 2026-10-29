import numpy as np
import pandas as pd
import pytest

from ta.backtest import resolve
from ta.broker import M1
from ta.s4 import S4Config, episodes, grid

N = 96  # one UTC day of M15 bars; January, so UK time = UTC (bar i opens at i * 15 min)


def day():
    """Asia (01:00-07:00 UK, bars 4-27) spans 1.0980-1.1020. London dips to 1.0990 at bar 29 (the London extreme),
    bar 32 (08:00) closes at 1.1030 above Asia (impulse body 2.8 ATR), bar 33 completes the FVG. The M15 zone is
    [1.0997, 1.1003] (bar 31 wicks + bar 32's low), created at bar 33. Price then holds near 1.1030; bar 40 dips to 1.1018.
    Retest long: entry 1.1020; the stop anchor is the Asia low (further than the London dip), stop 1.0980 - 0.25 ATR
    = 1.09775 (42.5 pips), T1 1.11475."""
    o, c, h, l = np.full(N, 1.1000), np.full(N, 1.1000), np.full(N, 1.1003), np.full(N, 1.0997)
    h[10], l[15] = 1.1020, 1.0980
    l[29] = 1.0990
    o[32], h[32], l[32], c[32] = 1.1002, 1.1032, 1.1001, 1.1030
    o[33], h[33], l[33], c[33] = 1.1030, 1.1036, 1.1028, 1.1035
    o[34:], c[34:], h[34:], l[34:] = 1.1030, 1.1030, 1.1033, 1.1027
    l[40] = 1.1018
    ts = pd.Series(pd.date_range("2024-01-09", periods=N, freq="15min", tz="UTC"))
    return {"pair": "EURUSD", "ts": ts, "o": o, "h": h, "l": l, "c": c, "ask_l": l, "bid_h": h,
            "atr": np.full(N, 0.001), "h4state": np.ones(N, int), "h4atr": np.full(N, 0.01),
            "fillable": np.ones(N, bool), "blackout": np.zeros(N, bool)}


def test_retest_entry_at_the_broken_asia_high():
    ep = episodes(day(), S4Config())
    assert ep[["dir", "t_bos", "place_bar", "fill_bar", "end_bar"]].values.tolist() == [[1, 32, 32, 40, 47]]
    assert ep[["entry", "stop", "target", "dist", "swing"]].values[0] == pytest.approx([1.1020, 1.09775, 1.11475, 0.00425, 1.0980])


def test_stop_anchor_is_the_london_extreme_when_it_is_further():
    f = day()
    f["l"][29] = 1.0970  # London dips under the Asia low first (a wick; the close stays inside)
    assert episodes(f, S4Config()).stop[0] == pytest.approx(1.0970 - 0.00025)
    assert episodes(day(), S4Config(target="time")).target[0] == np.inf


def test_zone_entry_at_the_demand_that_caused_the_break():
    f = day()
    f["l"][40] = 1.1000
    ep = episodes(f, S4Config(entry="zone"))
    assert ep[["place_bar", "fill_bar", "zone_low", "zone_high", "entry"]].values.tolist() == [[33, 40, 1.0997, 1.1003, 1.1003]]


def test_first_close_beyond_must_be_on_the_h4_bias_side():
    f = day()
    f["h4state"][:] = -1
    assert episodes(f, S4Config()).empty  # breakout up in an H4 downtrend
    f = day()
    f["l"][30], f["c"][30] = 1.0975, 1.0978  # the low side closes beyond first
    assert episodes(f, S4Config()).empty


def test_unfilled_by_noon_and_close_beyond_the_stop_cancel():
    f = day()
    f["l"][40] = 1.1027
    f["l"][48] = 1.1018  # 12:00 UK bar: too late
    assert episodes(f, S4Config())[["end_bar", "fill_bar"]].values.tolist() == [[47, -1]]
    f = day()
    f["fillable"][36] = False
    f["l"][36] = f["c"][36] = 1.0975  # closes under the stop (1.09775); the touch there is outside the session
    assert episodes(f, S4Config())[["end_bar", "fill_bar"]].values.tolist() == [[36, -1]]


def test_minimum_stop_skips():
    assert episodes(day(), S4Config(min_stop_pips=43.0)).empty  # the stop is 42.5 pips
    assert len(episodes(day(), S4Config(min_stop_pips=42.0))) == 1


def test_time_target_exits_at_17_uk_through_the_engine():
    f = day()
    ts = pd.date_range("2024-01-09", periods=N * 15, freq="1min", tz="UTC")
    rep = lambda a: np.repeat(a, 15)
    m1 = M1.from_frame(pd.DataFrame({"ts": ts, **{f"{s}_{k}": rep(v) for s in ("bid", "ask")
                                                  for k, v in zip("ohlc", (f["o"], f["h"], f["l"], f["c"]))}}))
    r = resolve(f, m1, S4Config(target="time")).iloc[0]
    assert (r.fill_ts, r.exit_ts, r.reason) == (m1.ts[40 * 15], pd.Timestamp("2024-01-09 17:00", tz="UTC").value, "flat")


def test_h1_confirmation_filter():
    f = day()
    f["h1state"] = np.ones(N, int)
    assert len(episodes(f, S4Config(h1=True))) == 1
    f["h1state"][32] = -1  # H1 bearish at the breakout close
    assert episodes(f, S4Config(h1=True)).empty
    assert len(episodes(f, S4Config(h1=False))) == 1


def test_grid_is_the_frozen_12():
    g = grid()
    assert len(set(g)) == 12 and {c.entry for c in g} == {"retest"} and {c.h1 for c in g} == {False, True}


def test_m4_keys_keep_h1_apart():
    from ta.m4 import STAGES, neighbours
    k = (0.25, True, "retest", "T1")
    assert neighbours(k, STAGES["S4"][0]) == [k, (0.1, True, "retest", "T1"), (0.5, True, "retest", "T1")]
