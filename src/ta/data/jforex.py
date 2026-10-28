"""Download M1 bid/ask through the Dukascopy JForex SDK (logged-in demo); same files as dukascopy.download."""
import datetime as dt
import glob
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from ta.config import DATA, ROOT, load_env
from ta.data.dukascopy import complete_months
from ta.data.store import M1_COLUMNS, m1_path, write_m1

BRIDGE = ROOT / "jforex"


def java() -> str:
    # shortcut: falls back to the JDK unpacked in ~/.local/opt; set JAVA if it lives elsewhere
    found = os.environ.get("JAVA") or shutil.which("java") or sorted(glob.glob(os.path.expanduser("~/.local/opt/zulu*/bin/java")))
    if not found:
        raise RuntimeError("no java found; set JAVA=/path/to/bin/java")
    return found if isinstance(found, str) else found[-1]


def read_dump(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={c: np.float64 for c in M1_COLUMNS[1:-1]} | {"volume": np.float32})
    df["ts"] = pd.to_datetime(df.ts, unit="ms", utc=True).astype("datetime64[us, UTC]")  # same unit as datafeed files
    return df[M1_COLUMNS]


def download(pairs, start_year: int, today: dt.date | None = None) -> int:
    today = today or dt.datetime.now(dt.UTC).date()
    jobs = [f"{p}:{y}-{m:02d}" for p in pairs for y, m in complete_months(start_year, today) if not m1_path(p, y, m).exists()]
    if not jobs:
        print("nothing to download")
        return 0
    env = load_env()
    if not env.get("DUKASCOPY_USER") or not env.get("DUKASCOPY_PASSWORD"):
        raise SystemExit("fill DUKASCOPY_USER and DUKASCOPY_PASSWORD in .env first")
    tmp = DATA / "tmp" / "jforex"
    tmp.mkdir(parents=True, exist_ok=True)
    cp = f"{BRIDGE / 'target' / 'classes'}:{BRIDGE / 'target' / 'lib' / '*'}"
    child_env = os.environ | {k: v for k, v in env.items() if k.startswith("DUKASCOPY_")}
    proc = subprocess.Popen([java(), "-cp", cp, "ta.HistoryDump", str(tmp), *jobs],
                            env=child_env, stdout=subprocess.PIPE, text=True, cwd=BRIDGE)
    log = (tmp / "sdk.log").open("a")  # the SDK logs heavily to stdout; keep only our lines on screen
    for line in proc.stdout:
        if not line.startswith("DONE "):
            log.write(line)
            if line.startswith(("FAIL", "ERROR")):
                print(line, end="", flush=True)
            continue
        _, pair, ym, *_, secs = line.split()  # the path may contain spaces, so rebuild it
        path = tmp / f"{pair}_{ym}.csv"
        y, m = map(int, ym.split("-"))
        df = read_dump(path)
        path.unlink()
        if df.empty:  # the SDK reports a refused month as done with no bars; leave it missing so the next pass retries
            print(f"FAIL {pair} {ym}: 0 bars", flush=True)
            continue
        write_m1(df, pair, y, m)
        print(f"{pair} {ym}: {len(df):>6} bars in {int(secs):5d}s", flush=True)
    return proc.wait()
