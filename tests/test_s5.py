import datetime as dt

import numpy as np
import pandas as pd
import pytest

from ta.backtest import resolve
from ta.broker import M1
from ta.s5 import S5Config, episodes, grid, nyse_skip

DAY = "2024-01-09"  # a Tuesday in January: ET = UTC-5, so 09:30 ET = 14:30 UTC


def day(day=DAY, start="14:00", end="21:30"):
    """Mid 5000 with a 0.5 spread. The 09:30-09:45 ET range is 4990-5010 (minute 14:35 UTC up, 14:40 down);
    at 15:00 UTC the ask trades 5012, triggering the long. Returns (minute times, mid o/h/l/c arrays, index lookup)."""
    ts = pd.date_range(f"{day} {start}", f"{day} {end}", freq="1min", tz="UTC", inclusive="left")
    n = len(ts)
    mid = {k: np.full(n, 5000.0) for k in "ohlc"}
    at = lambda hhmm: ts.get_loc(pd.Timestamp(f"{day} {hhmm}", tz="UTC"))
    mid["h"][at("14:35")], mid["l"][at("14:40")] = 5010.0, 4990.0
    mid["h"][at("15:00")] = 5011.75
    return ts, mid, at


def frames(ts, mid, pair="USA500IDXUSD", h4=1):
    m1 = M1.from_frame(pd.DataFrame({"ts": ts, **{f"{s}_{k}": mid[k] + (0.25 if s == "ask" else -0.25)
                                                    for s in ("bid", "ask") for k in "ohlc"}}))
    close = pd.Series(pd.date_range(ts[0].floor("15min"), ts[-1], freq="15min") + pd.Timedelta(minutes=15))
    f = {"pair": pair, "close_ts": close, "ts": close - pd.Timedelta(minutes=15), "h4state": np.full(len(close), h4)}
    return f, m1


def test_long_breakout_fills_at_the_stop_price_plus_slippage():
    ts, mid, at = day()
    f, m1 = frames(ts, mid)
    ep = episodes(f, m1, S5Config(slip_pips=2.5))
    assert len(ep) == 1 and ep.dir[0] == 1 and ep.fill_min[0] == at("15:00")
    assert ep[["zone_low", "zone_high", "entry", "stop", "dist"]].values[0] == pytest.approx([4990, 5010, 5010.25, 4990, 20.25])
    assert ep.target[0] == pytest.approx(5010.25 + 3 * 20.25)


def test_short_side_and_gap_through_the_level():
    ts, mid, at = day()
    mid["h"][at("15:00")] = 5000.0
    mid["o"][at("15:10")] = mid["l"][at("15:10")] = 4985.0  # opens below the range low: fills at the open
    f, m1 = frames(ts, mid)
    ep = episodes(f, m1, S5Config(slip_pips=2.5))
    assert ep.dir[0] == -1 and ep.entry[0] == pytest.approx(4984.75 - 0.25) and ep.stop[0] == 5010


def test_close_target_exits_at_1555_et():
    ts, mid, _ = day()
    f, m1 = frames(ts, mid)
    r = resolve(f, m1, S5Config(target="close", slip_pips=2.5)).iloc[0]
    assert r.target == np.inf and r.reason == "flat"
    assert r.exit_ts == pd.Timestamp(f"{DAY} 20:55", tz="UTC").value  # 15:55 ET


def test_h4_bias_keeps_one_side():
    ts, mid, _ = day()
    f, m1 = frames(ts, mid, h4=-1)
    ep = episodes(f, m1, S5Config(bias=True, slip_pips=2.5))
    assert ep.dir.tolist() == [-1] and ep.fill_min.tolist() == [-1]  # the long breakout is not taken
    f, m1 = frames(ts, mid, h4=0)
    assert episodes(f, m1, S5Config(bias=True, slip_pips=2.5)).empty


def test_cost_filter_and_same_minute_skip():
    ts, mid, at = day()
    f, m1 = frames(ts, mid)
    assert episodes(f, m1, S5Config(slip_pips=2.5, max_cost=0.05)).empty  # cost 1.35 > 5% of the 20-point range
    mid["l"][at("15:00")] = 4989.0  # the 15:00 minute also trades through the low
    f, m1 = frames(ts, mid)
    assert episodes(f, m1, S5Config(slip_pips=2.5)).empty


def test_nyse_holidays_and_half_days_are_skipped():
    s = nyse_skip(range(2014, 2026))
    for d in ("2024-01-15", "2024-03-29", "2018-12-05", "2024-07-03", "2024-11-29", "2024-12-24", "2022-06-20",
              "2021-12-24", "2025-01-09"):
        assert dt.date.fromisoformat(d) in s, d
    for d in ("2024-07-05", "2021-06-18", "2024-01-09"):
        assert dt.date.fromisoformat(d) not in s, d
    ts, mid, _ = day("2024-01-15")
    assert episodes(*frames(ts, mid), S5Config(slip_pips=2.5)).empty


def test_grid_is_the_frozen_12():
    g = grid()
    assert len(set(g)) == 12 and {c.instrument for c in g} == {"USATECHIDXUSD"} and {c.slip_pips for c in g} == {5.0}


def test_m4_s5_judges_each_instrument_on_its_years():
    from ta.m4 import STAGES, neighbours, select, stats
    grid_ = STAGES["S5"][0]
    k = (15, "XAUUSD", True, "proximal", "T1")
    assert neighbours(k, grid_) == [k, (5, "XAUUSD", True, "proximal", "T1"), (30, "XAUUSD", True, "proximal", "T1")]
    rows = [{"key": (n, "XAUUSD", True, "proximal", "T1"), "pair": "XAUUSD", "year": y, "R": 0.5 if y < 2019 else -1.0}
            for n in (5, 15, 30) for y in range(2014, 2021) for _ in range(50)]
    s = select(stats(pd.DataFrame(rows)), 300, grid_, "years_pos")
    assert s.years_pos.tolist() == [5, 5, 5] and s.eligible.all()  # one instrument, 5 of 7 years positive
