"""Download Dukascopy M1 bid/ask candles into monthly Parquet files (docs/02 §2-3)."""
import calendar
import datetime as dt
import lzma
import random
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests

from ta.data.store import M1_COLUMNS, m1_path, write_m1

URL = "https://datafeed.dukascopy.com/datafeed/{pair}/{y}/{m0:02d}/{d:02d}/{side}_candles_min_1.bi5"
RECORD = np.dtype([("t", ">u4"), ("o", ">u4"), ("c", ">u4"), ("l", ">u4"), ("h", ">u4"), ("v", ">f4")])


def scale(pair: str) -> float:
    return 1e3 if pair.endswith("JPY") else 1e5


def decode(raw: bytes, day: dt.date, divisor: float) -> pd.DataFrame:
    """One day's .bi5 -> DataFrame[ts,o,h,l,c,v]; zero-volume filler minutes are dropped."""
    if not raw:
        return pd.DataFrame(columns=["ts", "o", "h", "l", "c", "v"])
    rec = np.frombuffer(lzma.decompress(raw), dtype=RECORD)
    rec = rec[rec["v"] > 0]
    base = pd.Timestamp(day, tz="UTC")
    return pd.DataFrame({
        "ts": base + pd.to_timedelta(rec["t"].astype(np.int64), unit="s"),
        "o": rec["o"] / divisor, "h": rec["h"] / divisor,
        "l": rec["l"] / divisor, "c": rec["c"] / divisor,
        "v": rec["v"].astype(np.float32),
    })


def fetch(session, url: str, attempts: int = 15, delay: float = 1.0) -> bytes:
    """GET with backoff; the datafeed throws intermittent 503/429. 404 means no data."""
    for i in range(attempts):
        try:
            r = session.get(url, timeout=30)
            if r.status_code == 200:
                time.sleep(delay)
                return r.content
            if r.status_code == 404:
                return b""
        except requests.RequestException:
            pass
        time.sleep(min(60, 2 ** i) + random.random())
    raise RuntimeError(f"giving up after {attempts} attempts: {url}")


def day_frame(session, pair: str, day: dt.date, delay: float = 1.0) -> pd.DataFrame:
    """Merge one day's bid and ask; a minute with ticks on only one side borrows the other side's prices."""
    sides = {}
    for side in ("BID", "ASK"):
        url = URL.format(pair=pair, y=day.year, m0=day.month - 1, d=day.day, side=side)
        sides[side] = decode(fetch(session, url, delay=delay), day, scale(pair)).set_index("ts")
    bid, ask = sides["BID"], sides["ASK"]
    idx = bid.index.union(ask.index)
    bid, ask = bid.reindex(idx), ask.reindex(idx)
    bid, ask = bid.fillna(ask), ask.fillna(bid)
    out = pd.DataFrame({f"bid_{k}": bid[k] for k in "ohlc"} | {f"ask_{k}": ask[k] for k in "ohlc"}, index=idx)
    out["volume"] = bid["v"].astype(np.float32)
    return out.rename_axis("ts").reset_index()[M1_COLUMNS]


def month_frame(pair: str, year: int, month: int, workers: int = 3, delay: float = 1.0) -> pd.DataFrame:
    days = [dt.date(year, month, d) for d in range(1, calendar.monthrange(year, month)[1] + 1)]
    days = [d for d in days if d.weekday() != 5]  # Saturday: market closed all day (UTC)
    with requests.Session() as s, ThreadPoolExecutor(workers) as pool:
        s.headers["User-Agent"] = "Mozilla/5.0"
        frames = list(pool.map(lambda d: day_frame(s, pair, d, delay), days))
    frames = [f for f in frames if len(f)]
    if not frames:
        return pd.DataFrame(columns=M1_COLUMNS)
    return pd.concat(frames, ignore_index=True).sort_values("ts", ignore_index=True)


def complete_months(start_year: int, today: dt.date):
    y, m = start_year, 1
    while dt.date(y, m, calendar.monthrange(y, m)[1]) < today:
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def download(pairs, start_year: int, workers: int = 3, delay: float = 1.0, today: dt.date | None = None) -> list:
    """Download every complete month not already stored. Returns the (pair, year, month) that failed."""
    today = today or dt.datetime.now(dt.UTC).date()
    failed = []
    for pair in pairs:
        for y, m in complete_months(start_year, today):
            if m1_path(pair, y, m).exists():
                continue
            t0 = time.time()
            try:
                df = month_frame(pair, y, m, workers, delay)
            except RuntimeError as e:
                print(f"FAIL {pair} {y}-{m:02d}: {e}", flush=True)
                failed.append((pair, y, m))
                continue
            write_m1(df, pair, y, m)
            print(f"{pair} {y}-{m:02d}: {len(df):>6} bars in {time.time() - t0:5.0f}s", flush=True)
    return failed
