"""Cross-check the engine's fill model against Dukascopy's own historical tester (jforex/OrderReplay.java).

A sample of orders from a saved run is replayed tick by tick in the headless JForex tester: same limit price,
stop, target, live windows (placement to cancel, inside the session) and Friday flatten. The tester fills on a
touch and exits at tick prices, the engine on M1 bars with trade-through and slippage, so the engine should be
the same or worse, never better. Output: reports/jforex_crosscheck.csv plus an agreement summary (no P&L).
"""
import json
import os
import subprocess
from pathlib import Path

import pandas as pd

from ta.config import DATA, REPORTS, load_env, pip_size
from ta.data.jforex import BRIDGE, java
from ta.data.store import read_m1
from ta.strategy import time_masks

NY = "America/New_York"
M15 = pd.Timedelta(minutes=15)
REASON = {"stop": "sl", "target": "tp", "flat": "flat"}
CACHE = Path.home() / "JForex" / ".cache"  # the tester's tick cache: PAIR/YYYY/MM(0-based)/DD/HHh_ticks.bi5


def orders(eps: pd.DataFrame, session: str) -> pd.DataFrame:
    """One line per order in OrderReplay's CSV format."""
    ms = lambda t: str(t.value // 10**6)
    rows = []
    for k, e in eps.iterrows():
        place, end = pd.Timestamp(e.place_ts, tz="UTC"), pd.Timestamp(e.end_ts, tz="UTC")
        bars = pd.Series(pd.date_range(place, end - M15, freq="15min"))
        ok, _ = time_masks(bars, session)
        spans, start = [], None
        for t, live in zip(bars, ok):
            if live and start is None:
                start = t
            if not live and start is not None:
                spans.append((start, t))
                start = None
        if start is not None:
            spans.append((start, end))
        last = max(end, pd.Timestamp(e.exit_ts, tz="UTC")) if e.exit_ts >= 0 else end
        to = min(last + pd.Timedelta(days=2), place + pd.Timedelta(days=14))
        days = pd.date_range(place.tz_convert(NY).normalize(), to.tz_convert(NY).normalize() + pd.Timedelta(days=1), freq="D")
        flats = [d + pd.Timedelta(hours=16, minutes=30) for d in days if d.day_of_week == 4]
        rows.append({"id": k, "pair": e.pair, "dir": int(e.dir), "entry": repr(float(e.entry)), "stop": repr(float(e.stop)),
                     "target": repr(float(e.target)), "from_ms": ms(place - M15), "to_ms": ms(to),
                     "windows": ";".join(f"{ms(a)}-{ms(b)}" for a, b in spans), "flats": ";".join(ms(f) for f in flats)})
    return pd.DataFrame(rows, index=eps.index)


def replay(od: pd.DataFrame, work: Path) -> pd.DataFrame:
    env = load_env()
    if not env.get("DUKASCOPY_USER") or not env.get("DUKASCOPY_PASSWORD"):
        raise SystemExit("fill DUKASCOPY_USER and DUKASCOPY_PASSWORD in .env first")
    work.mkdir(parents=True, exist_ok=True)
    src, out = work / "orders.csv", work / "tester.csv"
    od.to_csv(src, index=False)
    cp = f"{BRIDGE / 'target' / 'classes'}:{BRIDGE / 'target' / 'lib' / '*'}"
    child_env = os.environ | {k: v for k, v in env.items() if k.startswith("DUKASCOPY_")}
    with (work / "sdk.log").open("w") as log:
        proc = subprocess.Popen([java(), "-cp", cp, "ta.OrderReplay", str(src), str(out)], env=child_env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=BRIDGE)
        for line in proc.stdout:  # the SDK logs heavily; keep only our lines on screen
            log.write(line)
            if line.startswith(("DONE ", "ERROR")):
                print(line, end="", flush=True)
        if proc.wait():
            raise SystemExit(f"OrderReplay failed, see {work / 'sdk.log'}")
    return pd.read_csv(out)


def holes(od: pd.DataFrame) -> dict:
    """Per order id, cached tick hours that are empty although our M1 has prices then. The tester caches a
    failed (HTTP 503) download as a 0-byte file and replays it as an hour without ticks."""
    out = {}
    for pair, g in od.groupby("pair"):
        ts = lambda v: pd.Timestamp(int(v), unit="ms", tz="UTC")
        years = range(ts(g.from_ms.astype(int).min()).year, ts(g.to_ms.astype(int).max()).year + 1)
        traded = set(read_m1(pair, years=years).ts.dt.floor("h"))
        for _, o in g.iterrows():
            files = [CACHE / pair / f"{h.year}" / f"{h.month - 1:02d}" / f"{h.day:02d}" / f"{h.hour:02d}h_ticks.bi5"
                     for h in pd.date_range(ts(o.from_ms).floor("h"), ts(o.to_ms), freq="h") if h in traded]
            bad = [f for f in files if f.exists() and f.stat().st_size == 0]
            if bad:
                out[o.id] = bad
    return out


def replay_complete(od: pd.DataFrame, work: Path, rounds: int = 3) -> pd.DataFrame:
    """replay(), then delete empty cached hours and replay the orders they hit; still incomplete -> data_gap."""
    res = replay(od, work)
    for _ in range(rounds):
        bad = holes(od)
        if not bad:
            break
        for f in {f for fs in bad.values() for f in fs}:
            f.unlink()
        redo = replay(od[od.id.isin(bad)], work)
        res = pd.concat([res[~res.id.isin(redo.id)], redo], ignore_index=True)
    res.loc[res.id.isin(holes(od)), "reason"] = "data_gap"
    return res


def compare(eps: pd.DataFrame, tester: pd.DataFrame) -> pd.DataFrame:
    t = tester.set_index("id")
    minute = lambda v: pd.Timestamp(int(v), unit="ms", tz="UTC").floor("1min").value
    rows = []
    for k, e in eps.iterrows():
        x, pip = t.loc[k], pip_size(e.pair)
        row = {"id": k, "pair": e.pair, "dir": int(e.dir), "engine_fill": e.fill_ts >= 0, "tester_fill": x.fill_ms >= 0,
               "engine_reason": REASON.get(e.reason, e.reason), "tester_reason": x.reason}
        if e.fill_ts >= 0 and x.fill_ms >= 0:
            row |= {"fill_min_diff": (e.fill_ts - minute(x.fill_ms)) / 6e10,
                    "fill_px_diff_pips": (x.fill_px - e.entry) * e.dir / pip}  # > 0: tester filled worse
            if e.exit_ts >= 0 and x.exit_ms >= 0:
                row |= {"exit_min_diff": (e.exit_ts - minute(x.exit_ms)) / 6e10,
                        "exit_px_diff_pips": (e.exit_px - x.exit_px) * e.dir / pip}  # > 0: engine exit better
        rows.append(row)
    return pd.DataFrame(rows)


def run(run_dir: Path, n_fill: int = 30, n_nofill: int = 10, seed: int = 20261030) -> str:
    cfg = json.loads((run_dir / "config.json").read_text())
    eps = pd.read_parquet(run_dir / "episodes.parquet")
    od = orders(eps, cfg["session"])
    eps = eps[(od.windows != "").to_numpy()]  # never live inside the session: nothing to compare
    filled, unfilled = eps[(eps.fill_ts >= 0) & (eps.exit_ts >= 0)], eps[eps.fill_ts < 0]
    pick = pd.concat([filled.sample(min(n_fill, len(filled)), random_state=seed),
                      unfilled.sample(min(n_nofill, len(unfilled)), random_state=seed)]).sort_values("place_ts")
    cmp = compare(pick, replay_complete(od.loc[pick.index], DATA / "tmp" / "jforex" / "crosscheck"))
    REPORTS.mkdir(exist_ok=True)
    cmp.to_csv(REPORTS / "jforex_crosscheck.csv", index=False)
    gaps = int((cmp.tester_reason == "data_gap").sum())
    cmp = cmp[cmp.tester_reason != "data_gap"]  # the tester's tick feed had a hole: no comparison possible
    both = cmp[cmp.engine_fill & cmp.tester_fill]
    closed = both.dropna(subset=["exit_min_diff"]) if "exit_min_diff" in both else both.iloc[:0]
    return "\n".join([
        f"{run_dir.name}: {len(cmp)} orders replayed in the JForex tester ({gaps} more skipped: tick data incomplete)",
        (f"fill decision agrees: {(cmp.engine_fill == cmp.tester_fill).sum()}/{len(cmp)}  (tester-only fills "
        f"{(cmp.tester_fill & ~cmp.engine_fill).sum()}, engine-only fills {(cmp.engine_fill & ~cmp.tester_fill).sum()})"),
        (f"fill minute, both filled: same {(both.fill_min_diff == 0).sum()}/{len(both)}, engine later "
        f"{(both.fill_min_diff > 0).sum()}, engine earlier {(both.fill_min_diff < 0).sum()}"),
        (f"exit reason agrees: {(closed.engine_reason == closed.tester_reason).sum()}/{len(closed)}, "
        f"same exit minute {(closed.exit_min_diff == 0).sum()}"),
        (f"exit price engine - tester (pips, + = engine better): median {closed.exit_px_diff_pips.median():+.2f}, "
        f"max {closed.exit_px_diff_pips.max():+.2f}; engine better on {(closed.exit_px_diff_pips > 0.05).sum()} (expect 0)"),
        f"-> {REPORTS / 'jforex_crosscheck.csv'}"])
