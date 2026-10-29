"""Project-wide constants, paths and .env loading (decisions D1, D4, D5, D11 in docs/README.md)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
REPORTS = ROOT / "reports"

PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"]
START_YEAR = 2010


CFDS = {"USA500IDXUSD": 0.1, "USATECHIDXUSD": 0.1, "XAUUSD": 0.1}  # S5 (docs/13): S&P 500, NASDAQ 100, gold; "pip" = 0.1


def pip_size(pair: str) -> float:
    return CFDS.get(pair) or (0.01 if pair.endswith("JPY") else 0.0001)


def load_env(path: Path = ROOT / ".env") -> dict:
    """Read KEY=VALUE lines from .env; real environment variables win."""
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip("'\"")
    env.update({k: v for k, v in os.environ.items() if k.startswith(("CTRADER_", "DUKASCOPY_", "TELEGRAM_"))})
    return env
