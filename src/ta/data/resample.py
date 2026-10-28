"""Resample M1 bid/ask into M15 and H4 bars (docs/01 §1).

H4 bars follow the FX day that ends 17:00 America/New_York, so boundaries sit at 17,21,01,05,09,13 NY
wall-clock time in both EST and EDT. `close_ts` is when a bar becomes usable (its end), in UTC.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from ta.config import DATA
from ta.data.store import read_m1

NY = "America/New_York"
SIDES = ("bid", "ask", "mid")


def _ny_wall_to_utc(wall: pd.Series) -> pd.Series:
    # DST fall-back makes 01:00 ambiguous; the first (EDT) occurrence is the boundary we want.
    return wall.dt.tz_localize(NY, ambiguous=np.ones(len(wall), bool), nonexistent="shift_forward").dt.tz_convert("UTC")


def resample(m1: pd.DataFrame, tf: str) -> pd.DataFrame:
    df = m1.copy()
    for k in "ohlc":
        df[f"mid_{k}"] = (df[f"bid_{k}"] + df[f"ask_{k}"]) / 2
    if tf == "M15":
        key = df["ts"].dt.floor("15min")
    elif tf == "H4":
        wall = df["ts"].dt.tz_convert(NY).dt.tz_localize(None)
        key = (wall - pd.Timedelta(hours=17)).dt.floor("4h") + pd.Timedelta(hours=17)
    else:
        raise ValueError(f"unsupported timeframe {tf}")
    agg = {f"{s}_o": "first" for s in SIDES} | {f"{s}_h": "max" for s in SIDES}
    agg |= {f"{s}_l": "min" for s in SIDES} | {f"{s}_c": "last" for s in SIDES}
    agg |= {"volume": "sum", "ts": "count"}
    out = df.groupby(key.rename("key"), sort=True).agg(agg).rename(columns={"ts": "n"}).reset_index()
    if tf == "M15":
        out["ts"], out["close_ts"] = out["key"], out["key"] + pd.Timedelta(minutes=15)
    else:
        out["ts"] = _ny_wall_to_utc(out["key"])
        out["close_ts"] = _ny_wall_to_utc(out["key"] + pd.Timedelta(hours=4))
    cols = ["ts", "close_ts"] + [f"{s}_{k}" for s in SIDES for k in "ohlc"] + ["volume", "n"]
    return out[cols]


def build_all(pairs, root: Path = DATA) -> None:
    for pair in pairs:
        m1 = read_m1(pair, root=root)
        if m1.empty:
            print(f"{pair}: no M1 data")
            continue
        m1 = m1.sort_values("ts", ignore_index=True)
        out_dir = root / "derived" / pair
        out_dir.mkdir(parents=True, exist_ok=True)
        for tf in ("M15", "H4"):
            bars = resample(m1, tf)
            bars.to_parquet(out_dir / f"{tf}.parquet", index=False)
            print(f"{pair} {tf}: {len(bars)} bars {bars.ts.iloc[0]} → {bars.ts.iloc[-1]}")
