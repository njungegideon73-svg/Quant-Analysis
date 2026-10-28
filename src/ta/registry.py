"""Run registry (docs/03 §3, §5): one row per backtest run, so the number of configs tried is known for the
Deflated Sharpe Ratio. Append-only CSV; a trial is a distinct config hash, however many times it was run."""
import csv
import hashlib
import json
import subprocess
from datetime import UTC, datetime

from ta.config import ROOT

REGISTRY = ROOT / "runs" / "registry.csv"
FIELDS = ["run_id", "created_utc", "git", "config_hash", "period", "pairs", "episodes", "filled", "note", "config", "data"]


def config_hash(cfg: dict) -> str:
    return hashlib.sha1(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:8]


def _git() -> str:
    r = subprocess.run(["git", "-C", str(ROOT), "describe", "--always", "--dirty"], check=False, capture_output=True, text=True)
    return r.stdout.strip() or "unknown"


def record(run_id: str, cfg: dict, eps, pairs, period: str = "all", note: str = "", path=REGISTRY, data: str = "") -> None:
    """Counts only: the registry never holds performance (docs/03: results are read in M4)."""
    # shortcut: no file lock, fine for one process; add one if grid workers ever write rows in parallel
    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="") as fh:
        w = csv.DictWriter(fh, FIELDS)
        if new:
            w.writeheader()
        w.writerow({"run_id": run_id, "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                    "git": _git(), "config_hash": config_hash(cfg), "period": period, "pairs": " ".join(pairs),
                    "episodes": len(eps), "filled": int((eps.status == "filled").sum()), "note": note,
                    "config": json.dumps(cfg, sort_keys=True), "data": data})


def rows(path=REGISTRY) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def trials(path=REGISTRY) -> int:
    return len({r["config_hash"] for r in rows(path)})


def guard(period: str, cfgs: list[dict], unlock_holdout=False, path=REGISTRY) -> None:
    """docs/03 §1 access rules: validation once per config and for at most 3 configs; hold-out opened once."""
    done = [x for x in rows(path) if x["period"] == period]
    hashes = {config_hash(c) for c in cfgs}
    if period == "validation":
        again = hashes & {x["config_hash"] for x in done}
        if again:
            raise PermissionError(f"validation already run for config(s) {sorted(again)}")
        if len(hashes | {x["config_hash"] for x in done}) > 3:
            raise PermissionError("validation is limited to 3 frozen candidates")
    if period == "holdout" and (not unlock_holdout or done or len(hashes) > 1):
        raise PermissionError("the hold-out is opened once, for one final candidate, with unlock_holdout=True")


def save_run(eps, cfg: dict, pairs, period: str, note: str = "", data: str = "") -> str:
    """Store and register a run without printing performance (docs/03: results are only looked at in M4)."""
    run_id = f"{datetime.now():%Y%m%d-%H%M%S}-{config_hash(cfg)}"
    out = ROOT / "runs" / run_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "config.json").write_text(json.dumps(cfg, sort_keys=True))
    eps.to_parquet(out / "episodes.parquet")
    record(run_id, cfg, eps, pairs, period, note, data=data)
    return run_id
