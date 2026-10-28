"""Parquet layout for raw M1 bid/ask data: data/raw/dukascopy/{pair}/{YYYY-MM}.parquet (docs/02 §3)."""
import hashlib
from pathlib import Path

import pandas as pd

from ta.config import DATA, ROOT

MANIFEST = ROOT / "data_manifest.csv"  # committed: the SHA-256 of every stored M1 month
M1_COLUMNS = ["ts", "bid_o", "bid_h", "bid_l", "bid_c", "ask_o", "ask_h", "ask_l", "ask_c", "volume"]


def m1_path(pair: str, year: int, month: int, root: Path = DATA) -> Path:
    return root / "raw" / "dukascopy" / pair / f"{year}-{month:02d}.parquet"


def write_m1(df: pd.DataFrame, pair: str, year: int, month: int, root: Path = DATA) -> Path:
    path = m1_path(pair, year, month, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    df[M1_COLUMNS].to_parquet(tmp, index=False)
    tmp.replace(path)  # atomic: a crash never leaves a half-written month
    return path


def floor_spread(df: pd.DataFrame) -> pd.DataFrame:
    """Bars with ask <= bid (2-decimal JPY quotes in 2010-11, unsynced AUDUSD 2010) get the whole ask bar raised
    to the month's median spread above bid, so no fill ever sees a free or negative spread."""
    spread = df.ask_c - df.bid_c
    floor = spread[spread > 0].median()
    gap = pd.concat([df[f"bid_{k}"] + floor - df[f"ask_{k}"] for k in "ohlc"], axis=1).max(axis=1)
    crossed = pd.concat([df[f"ask_{k}"] <= df[f"bid_{k}"] for k in "ohlc"], axis=1).any(axis=1)
    lift = gap.where(crossed & (gap > 0), 0.0)
    return df.assign(**{f"ask_{k}": df[f"ask_{k}"] + lift for k in "ohlc"})  # same shift on o/h/l/c keeps the bar valid


def read_m1(pair: str, years=None, root: Path = DATA, raw: bool = False) -> pd.DataFrame:
    """raw=True returns the stored quotes untouched (quality checks); otherwise crossed bars are floored."""
    files = sorted((root / "raw" / "dukascopy" / pair).glob("*.parquet"))
    if years is not None:
        files = [f for f in files if int(f.stem[:4]) in set(years)]
    if not files:
        return pd.DataFrame(columns=M1_COLUMNS)
    months = (pd.read_parquet(f) for f in files)
    return pd.concat(months if raw else (floor_spread(m) for m in months), ignore_index=True)


def manifest(root: Path = DATA) -> pd.DataFrame:
    """SHA-256 of every stored M1 month, as file (PAIR/YYYY-MM.parquet) -> sha256."""
    base = root / "raw" / "dukascopy"
    files = sorted(base.glob("*/*.parquet"))
    return pd.DataFrame({"file": [f.relative_to(base).as_posix() for f in files],
                         "sha256": [hashlib.sha256(f.read_bytes()).hexdigest() for f in files]})


def verified_snapshot(root: Path = DATA, path: Path = MANIFEST) -> str:
    """The data snapshot id (docs/02 §7). Refuses to run when a stored file no longer matches the committed
    manifest: silent bit flips were found once (EURUSD 2014-11), and a flip inside a price need not fail to read."""
    now = manifest(root)
    if path.exists():
        ref = pd.read_csv(path)
        both = now.merge(ref, on="file", how="outer", suffixes=("", "_ref"), indicator=True)
        bad = both[(both._merge != "both") | (both.sha256 != both.sha256_ref)].file.tolist()
        if bad:
            raise SystemExit(f"data does not match {path.name} ({len(bad)} files, e.g. {bad[:5]}): re-download them, "
                             "or run `ta data-manifest` if the change is intended")
    return hashlib.sha1("".join(now.file + now.sha256).encode()).hexdigest()[:8]
