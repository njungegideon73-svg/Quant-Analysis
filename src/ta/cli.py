"""`ta` command line: data pipeline now; backtest/grid/live subcommands arrive in later milestones."""
import argparse
import sys

from ta.config import PAIRS, START_YEAR


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="ta", description="JeaFx price-action system")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("download", help="download Dukascopy M1 bid/ask (resumable)")
    d.add_argument("--pairs", nargs="+", default=PAIRS)
    d.add_argument("--start-year", type=int, default=START_YEAR)
    d.add_argument("--workers", type=int, default=3)
    d.add_argument("--delay", type=float, default=1.0, help="seconds each worker waits after a request")

    j = sub.add_parser("download-jforex", help="download M1 bid/ask via the JForex SDK (needs demo login in .env)")
    j.add_argument("--pairs", nargs="+", default=PAIRS)
    j.add_argument("--start-year", type=int, default=START_YEAR)

    r = sub.add_parser("resample", help="build M15 and H4 bars from stored M1")
    r.add_argument("--pairs", nargs="+", default=PAIRS)

    q = sub.add_parser("quality", help="write reports/data_quality.html")
    q.add_argument("--pairs", nargs="+", default=PAIRS)

    v = sub.add_parser("review", help="chart 30 random S1 candidates -> reports/faithfulness_review.html")
    v.add_argument("--sample", nargs="+", default=["EURUSD=24", "USDJPY=6"], help="PAIR=count ...")
    v.add_argument("--seed", type=int, default=20261027)
    v.add_argument("--out", default="reports/faithfulness_review.html")

    sub.add_parser("review-s4", help="chart 30 random S4 setups, blind to the outcome -> reports/s4_review.html")

    b = sub.add_parser("backtest", help="run S1 (default config) -> runs/<id>/episodes.parquet; prints counts only")
    b.add_argument("--pairs", nargs="+", default=PAIRS)
    b.add_argument("--note", default="", help="why this run was made (stored in runs/registry.csv)")
    b.add_argument("--period", choices=["research", "validation", "holdout"], default="research")
    b.add_argument("--unlock-holdout", action="store_true", help="the one permitted hold-out run (docs/03 §1)")

    g = sub.add_parser("grid", help="Stage A grid (216 configs, docs/03 §3) on the research period; counts only")
    g.add_argument("--pairs", nargs="+", default=PAIRS)
    g.add_argument("--workers", type=int, default=4)
    g.add_argument("--note", default="Stage A grid")
    g.add_argument("--stage", choices=["A", "B", "S2", "S3", "S4", "S5"], default="A",
                   help="A: 216-config grid, B: 7 filter flips from the pick, S2: the 4-config S2 grid (docs/06 §11), S3: 8 configs (docs/09), S4: 12 (docs/11)")

    sub.add_parser("runs", help="list registered runs and the trial count (distinct configs)")

    c = sub.add_parser("control", help="random-entry control: same stops/targets/costs, random entries")
    c.add_argument("--pairs", nargs="+", default=PAIRS)
    c.add_argument("--n", type=int, default=3000)

    h = sub.add_parser("audit", help="re-trace 20 random trades of a run against raw M1 -> reports/hand_audit.html")
    h.add_argument("--run", help="runs/<id> (default: the latest run)")
    h.add_argument("--n", type=int, default=20)

    rp = sub.add_parser("report", help="runs/<id>/report.html: equity, drawdown, metrics (M4 on: shows performance)")
    rp.add_argument("--run", required=True)

    mm = sub.add_parser("m4", help="M4: Stage A results, §4 candidate rule and walk-forward (shows performance)")
    mm.add_argument("--note", default="stage A, 7 pairs, zone = candle + next wick, stop at origin swing")
    mm.add_argument("--stage", choices=["A", "S2", "S3", "S4", "S5"], default="A")

    sub.add_parser("data-manifest", help="write data_manifest.csv: SHA-256 of every stored M1 month (runs verify it)")

    x = sub.add_parser("jforex-check", help="replay a run's orders in Dukascopy's JForex tester; compare fills/exits")
    x.add_argument("--run", help="runs/<id> (default: the latest research run of the default config)")
    x.add_argument("--n-fill", type=int, default=30)
    x.add_argument("--n-nofill", type=int, default=10)
    x.add_argument("--stops", action="store_true", help="sample stop-outs only (stop slippage calibration)")

    a = p.parse_args(argv)
    if a.cmd == "download":
        from ta.data.dukascopy import download
        failed = download(a.pairs, a.start_year, a.workers, a.delay)
        print(f"done; {len(failed)} month(s) failed — re-run to retry" if failed else "done")
        return 1 if failed else 0
    if a.cmd == "download-jforex":
        from ta.data.jforex import download
        return download(a.pairs, a.start_year)
    if a.cmd == "resample":
        from ta.data.resample import build_all
        build_all(a.pairs)
    if a.cmd == "quality":
        from ta.data.quality import write_report
        print(write_report(a.pairs))
    if a.cmd == "review":
        from pathlib import Path

        from ta.review import build
        print(build({k: int(n) for k, n in (s.split("=") for s in a.sample)}, a.seed, Path(a.out)))
    if a.cmd == "backtest":
        from ta.backtest import run
        from ta.data.store import verified_snapshot
        from ta.strategy import Config
        snap = verified_snapshot()
        print(_report(run(Config(), a.pairs, a.period, a.unlock_holdout), Config(), a.pairs, a.period, a.note, snap))
    if a.cmd == "grid":
        import time

        from ta import s2, s3, s4, s5
        from ta.backtest import grid
        from ta.data.store import verified_snapshot
        from ta.strategy import stage_a, stage_b
        cfgs = {"A": stage_a, "B": stage_b, "S2": s2.grid, "S3": s3.grid, "S4": s4.grid, "S5": s5.grid}[a.stage]()
        t0, snap = time.time(), verified_snapshot()
        # S5 (docs/13 §7): each instrument runs alone; FX stages run every config on --pairs
        runs = [([c for c in cfgs if c.instrument == i], [i]) for i in sorted({c.instrument for c in cfgs})] \
            if a.stage == "S5" else [(cfgs, a.pairs)]
        for cs, pairs in runs:
            for eps, cfg in zip(grid(cs, pairs, "research", a.workers), cs):
                print(_report(eps, cfg, pairs, "research", a.note, snap))
        print(f"{len(cfgs)} configs in {time.time() - t0:.0f} s")
    if a.cmd == "review-s4":
        from ta.review import build_s4
        print(build_s4())
    if a.cmd == "report":
        from pathlib import Path

        from ta.report import build
        print(build(Path(a.run)))
    if a.cmd == "m4":
        from ta.m4 import run as m4
        print(m4(a.note, a.stage))
    if a.cmd == "data-manifest":
        from ta.data.store import MANIFEST, manifest
        m = manifest()
        m.to_csv(MANIFEST, index=False)
        print(f"{MANIFEST.name}: {len(m)} files")
    if a.cmd == "runs":
        from ta.registry import rows, trials
        for r in rows():
            print(f"{r['run_id']}  {r['git']:>16}  {r['period']:>8}  {r['pairs']:<24}  episodes={r['episodes']:>5}  "
                  f"filled={r['filled']:>5}  {r['note']}")
        print(f"trials (distinct configs): {trials()} in total (budget: 250 per strategy; the DSR uses the total)")
    if a.cmd == "audit":
        from pathlib import Path

        from ta.audit import build
        from ta.config import ROOT
        print(build(Path(a.run) if a.run else max((ROOT / "runs").glob("2*")), a.n))
    if a.cmd == "jforex-check":
        from pathlib import Path

        from ta.config import ROOT
        from ta.crosscheck import run as crosscheck
        from ta.registry import config_hash, rows
        from ta.strategy import Config
        ids = [r["run_id"] for r in rows() if r["period"] == "research" and r["config_hash"] == config_hash(Config().to_dict())]
        print(crosscheck(Path(a.run) if a.run else ROOT / "runs" / ids[-1], a.n_fill, a.n_nofill, stops=a.stops))
    if a.cmd == "control":
        _control(a.pairs, a.n)
    return 0


def _report(eps, cfg, pairs, period, note, data="") -> str:
    """Counts only (docs/03: results are only looked at in M4)."""
    from ta.registry import save_run, trials
    run_id = save_run(eps, cfg.to_dict(), pairs, period, note, data)
    counts = "  ".join(f"{k}={v}" for k, v in eps.status.value_counts().items())
    return f"runs/{run_id}  {period}  episodes={len(eps)}  {counts}  trials={trials()}"


def _control(pairs, n):
    import numpy as np

    from ta.backtest import random_control
    from ta.broker import M1
    from ta.strategy import Config, prepare
    cfg = Config()
    for pair in pairs:
        r = random_control(prepare(pair, cfg), M1.load(pair), cfg, n=n)
        se = r.R.std() / np.sqrt(len(r))
        gap = r.R.mean() + r.cost_R.mean()
        print(f"{pair}: n={len(r)}  mean R {r.R.mean():+.3f} (±{1.96 * se:.3f})  expected -cost {-r.cost_R.mean():+.3f}  "
              f"gross {r.R_gross.mean():+.3f}  win {np.mean(r.reason == 'target'):.1%}  "
              f"{'OK' if abs(gap) < 1.96 * se else 'CHECK'}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
