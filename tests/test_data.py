import datetime as dt
import lzma

import numpy as np
import pandas as pd
import pytest

from ta import config
from ta.cli import main
from ta.data import dukascopy as dk
from ta.data.jforex import read_dump
from ta.data.quality import check, classify_gaps
from ta.data.resample import resample
from ta.data.store import M1_COLUMNS, read_m1, write_m1


def bi5(rows):
    """rows: (sec, o, c, l, h, vol) in integer points -> Dukascopy-style LZMA bytes."""
    return lzma.compress(np.array(rows, dtype=dk.RECORD).tobytes(), format=lzma.FORMAT_ALONE)


def m1_frame(start, minutes, price=1.1000, spread=0.0001):
    ts = pd.date_range(start, periods=minutes, freq="1min", tz="UTC")
    p = price + np.arange(minutes) * 1e-5
    d = {"ts": ts, "volume": np.ones(minutes, np.float32)}
    for side, off in (("bid", 0.0), ("ask", spread)):
        d |= {f"{side}_o": p + off, f"{side}_h": p + off + 2e-5, f"{side}_l": p + off - 2e-5, f"{side}_c": p + off}
    return pd.DataFrame(d)[M1_COLUMNS]


def test_decode_scales_prices_and_drops_filler():
    day = dt.date(2024, 4, 15)
    raw = bi5([(0, 106461, 106471, 106460, 106480, 1.5), (60, 106471, 106471, 106471, 106471, 0.0)])
    df = dk.decode(raw, day, dk.scale("EURUSD"))
    assert len(df) == 1
    assert df.ts[0] == pd.Timestamp("2024-04-15", tz="UTC")
    assert df.o[0] == pytest.approx(1.06461) and df.h[0] == pytest.approx(1.06480)
    assert dk.scale("USDJPY") == 1e3 and dk.decode(b"", day, 1e5).empty


def test_fetch_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(dk.time, "sleep", lambda s: None)

    class Session:
        def __init__(self):
            self.codes = [503, 429, 200]

        def get(self, url, timeout):
            return type("R", (), {"status_code": self.codes.pop(0), "content": b"ok"})()

    assert dk.fetch(Session(), "u") == b"ok"


def test_fetch_gives_up_and_404_is_empty(monkeypatch):
    monkeypatch.setattr(dk.time, "sleep", lambda s: None)
    always = lambda code: type("S", (), {"get": lambda self, u, timeout: type("R", (), {"status_code": code})()})()
    assert dk.fetch(always(404), "u") == b""
    with pytest.raises(RuntimeError):
        dk.fetch(always(503), "u", attempts=3)


def test_day_frame_merges_sides_and_uses_zero_indexed_month(monkeypatch):
    urls = []

    def fake_fetch(session, url, delay=1.0):
        urls.append(url)
        if "BID" in url:
            return bi5([(0, 110000, 110010, 109990, 110020, 2.0), (60, 110010, 110020, 110000, 110030, 1.0)])
        return bi5([(0, 110002, 110012, 109992, 110022, 3.0)])  # no ask ticks in minute 2

    monkeypatch.setattr(dk, "fetch", fake_fetch)
    df = dk.day_frame(None, "EURUSD", dt.date(2024, 4, 15))
    assert all("/2024/03/15/" in u for u in urls)
    assert list(df.columns) == M1_COLUMNS and len(df) == 2
    assert df.ask_o[0] == pytest.approx(1.10002)
    assert df.ask_o[1] == df.bid_o[1]  # missing side borrows the other side


def test_complete_months_excludes_current_month():
    months = list(dk.complete_months(2026, dt.date(2026, 3, 10)))
    assert months == [(2026, 1), (2026, 2)]


def test_store_roundtrip(tmp_path):
    df = m1_frame("2024-01-02 10:00", 5)
    write_m1(df, "EURUSD", 2024, 1, root=tmp_path)
    back = read_m1("EURUSD", root=tmp_path)
    pd.testing.assert_frame_equal(back, df)
    assert read_m1("GBPUSD", root=tmp_path).empty


def test_resample_m15_ohlc():
    df = m1_frame("2024-01-02 10:00", 30)
    bars = resample(df, "M15")
    assert len(bars) == 2 and bars.n.tolist() == [15, 15]
    assert bars.bid_o[0] == df.bid_o[0] and bars.bid_c[0] == df.bid_c[14]
    assert bars.bid_h[0] == df.bid_h[:15].max() and bars.mid_l[1] == pytest.approx(((df.bid_l + df.ask_l) / 2)[15:].min())
    assert bars.close_ts[0] == pd.Timestamp("2024-01-02 10:15", tz="UTC")


@pytest.mark.parametrize("start", ["2024-03-08 12:00", "2024-11-01 12:00"])  # US DST start / end weekends
def test_resample_h4_boundaries_follow_new_york_17h(start):
    df = m1_frame(start, 5 * 24 * 60)
    bars = resample(df, "H4")
    wall = bars.ts.dt.tz_convert("America/New_York").iloc[1:]  # first bar is partial
    assert set(wall.dt.hour) <= {17, 21, 1, 5, 9, 13}
    tiles = bars.close_ts.iloc[1:-1].reset_index(drop=True) == bars.ts.iloc[2:].reset_index(drop=True)
    assert tiles.all()  # bars tile with no overlap or hole
    assert bars.n.sum() == len(df)


def test_quality_flags_problems_and_classifies_gaps():
    a = m1_frame("2024-01-03 10:00", 60)           # Wednesday
    b = m1_frame("2024-01-03 12:00", 60)           # 1h midweek gap -> unexplained
    c = m1_frame("2024-01-07 23:00", 60)           # after the weekend
    df = pd.concat([a, b, c], ignore_index=True)
    df.loc[5, "ask_c"] = df.loc[5, "bid_c"] - 0.001  # crossed quote
    df = pd.concat([df, df.iloc[[10]]], ignore_index=True).sort_values("ts", ignore_index=True)  # duplicate
    r = check(df, "EURUSD")
    assert r["crossed"] == 1 and r["dup_ts"] == 1
    assert r["gaps_unexplained"] == 1
    kinds = classify_gaps(df.ts).kind.tolist()
    assert kinds == ["unexplained", "weekend"]


def test_load_env(tmp_path, monkeypatch):
    monkeypatch.delenv("CTRADER_ENV", raising=False)
    f = tmp_path / ".env"
    f.write_text("# comment\nCTRADER_ENV='demo'\nCTRADER_ACCOUNT_ID=123\n")
    assert config.load_env(f) == {"CTRADER_ENV": "demo", "CTRADER_ACCOUNT_ID": "123"}


def test_cli_help():
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0


def test_jforex_dump_matches_store_schema(tmp_path):
    f = tmp_path / "d.csv"
    f.write_text("ts,bid_o,bid_h,bid_l,bid_c,ask_o,ask_h,ask_l,ask_c,volume\n"
                 "1713139200000,1.06461,1.0648,1.0646,1.06471,1.06463,1.06482,1.06462,1.06473,1.5\n")
    df = read_dump(f)
    assert list(df.columns) == M1_COLUMNS and df.ts[0] == pd.Timestamp("2024-04-15", tz="UTC")
    assert df.dtypes.equals(m1_frame("2024-04-15", 1).dtypes)
