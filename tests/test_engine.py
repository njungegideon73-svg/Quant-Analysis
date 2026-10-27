import numpy as np
import pandas as pd
import pytest

from ta.backtest import portfolio, resolve
from ta.broker import M1, Costs, exit_trade, first_fill, trade_r, units
from ta.config import DATA
from ta.data.resample import resample
from ta.data.store import read_m1
from ta.strategy import Config, episodes, prepare_frames, time_masks

C = Costs.for_pair("EURUSD")  # fill-through 0.1 pip, slip 0.2 pip, $3.5/lot/side
ENTRY, STOP, TARGET = 1.1000, 1.0985, 1.1045  # long, 15-pip stop, 3R


def m1(rows, start="2024-01-09 10:00", spread=0.0001):
    """rows: (bid_o, bid_h, bid_l) per minute; ask = bid + spread."""
    ts = pd.date_range(start, periods=len(rows), freq="1min", tz="UTC")
    b = np.array(rows, dtype=float)
    df = pd.DataFrame({"ts": ts, "bid_o": b[:, 0], "bid_h": b[:, 1], "bid_l": b[:, 2],
                       "ask_o": b[:, 0] + spread, "ask_h": b[:, 1] + spread, "ask_l": b[:, 2] + spread})
    return M1.from_frame(df)


FLAT = (1.1010, 1.1015, 1.1005)  # a quiet minute


def test_limit_needs_trade_through():
    assert first_fill(m1([(1.1, 1.1, 1.0999)]), 0, 1, 1, ENTRY, C) == -1  # ask_l = 1.1000 exactly: no fill
    assert first_fill(m1([FLAT, (1.1, 1.1, 1.0998)]), 0, 2, 1, ENTRY, C) == 1  # ask_l 1.0999 = entry - 0.1 pip


def test_stop_fills_with_slip_and_gaps_at_the_open():
    j, why, px = exit_trade(m1([FLAT, FLAT, (1.0990, 1.0990, 1.0984)]), 0, 1, ENTRY, STOP, TARGET, C)
    assert (j, why, px) == (2, "stop", pytest.approx(STOP - 0.00002))
    _, _, px = exit_trade(m1([FLAT, (1.0975, 1.0978, 1.0970)]), 0, 1, ENTRY, STOP, TARGET, C)
    assert px == pytest.approx(1.0975)  # gapped through: the open is worse than stop - slip


def test_target_needs_trade_through_and_pays_no_improvement():
    assert exit_trade(m1([FLAT, (1.1040, 1.1045, 1.1040)]), 0, 1, ENTRY, STOP, TARGET, C) is None
    assert exit_trade(m1([FLAT, (1.1040, 1.1060, 1.1040)]), 0, 1, ENTRY, STOP, TARGET, C)[1:] == ("target", TARGET)


def test_stop_and_target_in_the_same_minute_is_a_stop():
    assert exit_trade(m1([FLAT, (1.1000, 1.1060, 1.0980)]), 0, 1, ENTRY, STOP, TARGET, C)[1] == "stop"


def test_fill_minute_target_does_not_count_but_fill_minute_stop_does():
    assert exit_trade(m1([(1.1000, 1.1060, 1.0999)]), 0, 1, ENTRY, STOP, TARGET, C) is None
    assert exit_trade(m1([(1.1000, 1.1005, 1.0980)]), 0, 1, ENTRY, STOP, TARGET, C) == (0, "stop", pytest.approx(STOP - 0.00002))


def test_short_mirrors_on_the_ask():
    # short at 1.1000, stop 1.1015: ask_h = bid_h + 1 pip reaches the stop before the bid does
    x = exit_trade(m1([FLAT, (1.1010, 1.1014, 1.1008)]), 0, -1, 1.1000, 1.1015, 1.0955, C)
    assert x[1:] == ("stop", pytest.approx(1.1015 + 0.00002))


def test_weekend_flatten_at_friday_1630_ny():
    rows = [FLAT] * 40
    x = exit_trade(m1(rows, start="2024-01-12 21:00"), 0, 1, ENTRY, STOP, TARGET, C)  # 16:00 NY Friday (EST)
    assert x == (30, "flat", pytest.approx(FLAT[0] - 0.00002))


def test_net_r_includes_commission_and_swap():
    mm = m1([FLAT] * 3, start="2024-01-09 21:59")  # 16:59 NY -> crosses the 17:00 rollover
    r = trade_r(mm, 0, 2, 1, ENTRY, STOP, TARGET, C)
    assert r["nights"] == 1
    assert r["R"] == pytest.approx((0.0045 - 2 * 3.5e-5 - 0.3e-4) / 0.0015)
    jpy = Costs.for_pair("USDJPY")
    assert jpy.commission(150.0) == pytest.approx(3.5e-5 * 150)  # USD commission in yen per unit


@pytest.mark.parametrize("pair,entry,stop", [("EURUSD", 1.1, 1.0985), ("USDJPY", 150.0, 149.8), ("USDCAD", 1.35, 1.352)])
def test_sizing_risks_half_a_percent(pair, entry, stop):
    rng = np.random.default_rng(1)
    for eq in rng.uniform(1_000, 1_000_000, 50):
        u = units(pair, eq, entry, stop)
        loss_usd = u * abs(entry - stop) * (1 if pair.endswith("USD") else 1 / entry)
        assert 0.005 * eq - abs(entry - stop) * 2 <= loss_usd <= 0.005 * eq


def features(n=30):
    """One long zone [1.1000, 1.1020] created at bar 5 from origin 2, with a leg high of 1.1050 (discount ok)."""
    ts = pd.Series(pd.date_range("2024-01-09 09:00", periods=n, freq="15min", tz="UTC"))
    h, l, c = np.full(n, 1.1040), np.full(n, 1.1025), np.full(n, 1.1030)
    h[3:6] = 1.1050
    z = pd.DataFrame({"t": [5], "t_bos": [5], "dir": [1], "kind": ["cont"], "origin": [2], "low": [1.1000],
                      "high": [1.1020], "leg": [0]})
    return {"pair": "EURUSD", "ts": ts, "h": h, "l": l, "c": c, "ask_l": l + 0.0001, "bid_h": h, "atr": np.full(n, 0.001),
            "zones": z, "h4state": np.ones(n, int), "h4atr": np.full(n, 0.01), "h4eq": np.full(n, np.nan),
            "fillable": np.ones(n, bool), "blackout": np.zeros(n, bool)}


def test_episode_places_at_creation_and_fills_on_first_touch():
    f = features()
    f["ask_l"][9] = 1.1015
    ep = episodes(f, Config(b=0.1))
    assert ep[["place_bar", "fill_bar"]].values.tolist() == [[5, 9]]
    assert (ep.entry[0], ep.stop[0], ep.target[0]) == pytest.approx((1.1020, 1.0999, 1.1020 + 3 * 0.0021))


def test_episode_discarded_when_touched_before_the_order_exists():
    f = features()
    f["h4state"][5:8] = 0  # bias not yet aligned, so no order
    f["l"][7] = 1.1018  # price taps the zone meanwhile
    assert episodes(f, Config()).empty


def test_episode_cancelled_when_a_close_breaks_the_zone():
    f = features()
    f["fillable"][:] = False  # touches happen outside the session: inactive, no fill
    f["c"][8], f["l"][8], f["ask_l"][8] = 1.0995, 1.0990, 1.0991
    ep = episodes(f, Config())
    assert ep[["place_bar", "end_bar", "fill_bar"]].values.tolist() == [[5, 8, -1]]


def test_min_stop_skip_and_widen():
    f = features()
    f["zones"].loc[0, "low"] = 1.1012  # 8-pip zone -> stop under 15 pips
    assert episodes(f, Config(min_stop_mode="skip")).empty
    assert episodes(f, Config(min_stop_mode="widen")).dist[0] == pytest.approx(0.0015)


def test_time_masks_session_rollover_weekend_holiday():
    ts = pd.Series(pd.to_datetime(["2024-01-09 06:45", "2024-01-09 07:00", "2024-01-09 21:45",  # LDN, NY rollover
                                   "2024-01-12 20:00", "2024-12-25 12:00", "2024-07-04 12:00"], utc=True))
    ok, black = time_masks(ts, "london_ny")
    assert ok.tolist() == [False, True, False, False, False, False]
    assert black.tolist() == [False, False, False, False, True, True]


T0 = 10**18  # arbitrary ns clock for portfolio fixtures
H = 3_600 * 10**9


def eps(rows):
    cols = ["pair", "dir", "leg", "zone_ts", "place_ts", "end_ts", "fill_ts", "exit_ts"]
    return pd.DataFrame([dict(zip(cols, r)) for r in rows])


def test_newest_zone_replaces_pending_and_extreme_keeps_it():
    e = eps([("EURUSD", 1, 0, T0, T0, T0 + 9 * H, T0 + 3 * H, T0 + 4 * H),
             ("EURUSD", 1, 0, T0 + H, T0 + 2 * H, T0 + 9 * H, T0 + 5 * H, T0 + 6 * H)])
    assert portfolio(e, Config()).status.tolist() == ["replaced", "filled"]
    assert portfolio(e, Config(zone_pick="extreme")).status.tolist() == ["filled", "kept_older"]


def test_open_position_blocks_then_waiting_zone_is_replaced_after_exit():
    e = eps([("EURUSD", 1, 0, T0, T0, T0 + 2 * H, T0 + H, T0 + 4 * H),  # position until 4h
             ("EURUSD", 1, 0, T0 + H, T0 + 2 * H, T0 + 9 * H, T0 + 6 * H, T0 + 7 * H),  # waits, fills after
             ("EURUSD", 1, 0, T0 + H, T0 + 2 * H, T0 + 9 * H, T0 + 3 * H, T0 + 8 * H)])  # touched while blocked
    assert portfolio(e, Config()).status.tolist() == ["filled", "filled", "blocked"]


def test_max_open_and_currency_exposure():
    pos = lambda p, d, k: (p, d, 0, T0 + k, T0 + k, T0 + 9 * H, T0 + H + k, T0 + 5 * H)
    e = eps([pos("EURUSD", 1, 0), pos("GBPUSD", 1, 1), pos("AUDUSD", 1, 2)])  # three short-USD
    assert portfolio(e, Config()).status.tolist() == ["filled", "filled", "rejected"]
    e = eps([pos("EURUSD", 1, 0), pos("USDJPY", 1, 1), pos("AUDUSD", -1, 2), pos("USDCHF", -1, 3), pos("NZDUSD", 1, 4)])
    assert portfolio(e, Config(max_ccy=9)).status.tolist() == ["filled"] * 4 + ["rejected"]


@pytest.mark.skipif(not (DATA / "raw" / "dukascopy" / "EURUSD" / "2012-06.parquet").exists(), reason="needs EURUSD 2012")
def test_engine_prefix_invariance_on_real_data():
    raw = read_m1("EURUSD", years=[2012])
    cut = pd.Timestamp("2012-07-01", tz="UTC")

    def run(df):
        m15, h4 = resample(df, "M15"), resample(df, "H4")
        return resolve(prepare_frames("EURUSD", m15, h4, Config()), M1.from_frame(df), Config())

    full, pre = run(raw), run(raw[raw.ts < cut])
    D = cut.value - 2 * 15 * 60 * 10**9  # decisions before the last prefix bar
    f = full[full.place_ts < D].reset_index(drop=True)
    p = pre[pre.place_ts < D].reset_index(drop=True)
    assert len(f) > 10
    cols = ["zone_t", "place_ts", "entry", "stop", "target"]
    pd.testing.assert_frame_equal(f[cols], p[cols])
    filled = (f.fill_ts >= 0) & (f.fill_ts < D)
    assert (f.fill_ts[filled] == p.fill_ts[filled]).all()
    closed = filled & (f.exit_ts >= 0) & (f.exit_ts < D)
    assert np.allclose(f.R[closed], p.R[closed])


def test_registry_counts_distinct_configs(tmp_path):
    from ta.registry import record, rows, trials
    reg = tmp_path / "registry.csv"
    e = pd.DataFrame({"status": ["filled", "cancelled", "filled"]})
    record("a", Config().to_dict(), e, ["EURUSD"], path=reg)
    record("b", Config().to_dict(), e, ["EURUSD", "GBPUSD"], note="rerun", path=reg)
    record("c", Config(b=0.2).to_dict(), e, ["EURUSD"], path=reg)
    assert trials(reg) == 2
    assert [r["filled"] for r in rows(reg)] == ["2"] * 3
    assert "R" not in rows(reg)[0]  # counts only, never performance


def test_access_rules_for_validation_and_holdout(tmp_path):
    from ta.registry import guard, record
    reg, e = tmp_path / "registry.csv", pd.DataFrame({"status": ["filled"]})
    cands = [Config(b=b).to_dict() for b in (0.05, 0.1, 0.2)]
    guard("research", cands * 2, path=reg)  # research is unlimited
    guard("validation", cands[:1], path=reg)
    record("v1", cands[0], e, ["EURUSD"], "validation", path=reg)
    with pytest.raises(PermissionError):
        guard("validation", cands[:1], path=reg)  # once per candidate
    with pytest.raises(PermissionError):
        guard("validation", cands[1:] + [Config(K=48).to_dict()], path=reg)  # at most 3 candidates
    with pytest.raises(PermissionError):
        guard("holdout", cands[:1], path=reg)  # needs the explicit unlock
    guard("holdout", cands[:1], unlock_holdout=True, path=reg)
    record("h1", cands[0], e, ["EURUSD"], "holdout", path=reg)
    with pytest.raises(PermissionError):
        guard("holdout", cands[:1], unlock_holdout=True, path=reg)  # opened once


@pytest.mark.skipif(not (DATA / "raw" / "dukascopy" / "EURUSD" / "2020-01.parquet").exists(), reason="needs EURUSD 2020")
def test_research_load_holds_nothing_after_2019():
    from ta.backtest import load
    end = pd.Timestamp("2020-01-01", tz="UTC")
    m15, h4, m1 = load("EURUSD", "research")
    assert m15.close_ts.max() <= end and h4.close_ts.max() <= end and m1.ts.max() < end.value
    assert m1.ts.min() < pd.Timestamp("2010-02-01", tz="UTC").value  # warm-up starts with the data
