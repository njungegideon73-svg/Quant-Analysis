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

    b = sub.add_parser("backtest", help="run S1 (default config) -> runs/<id>/episodes.parquet; prints counts only")
    b.add_argument("--pairs", nargs="+", default=PAIRS)
    b.add_argument("--note", default="", help="why this run was made (stored in runs/registry.csv)")

    sub.add_parser("runs", help="list registered runs and the trial count (distinct configs)")

    c = sub.add_parser("control", help="random-entry control: same stops/targets/costs, random entries")
    c.add_argument("--pairs", nargs="+", default=PAIRS)
    c.add_argument("--n", type=int, default=3000)

    h = sub.add_parser("audit", help="re-trace 20 random trades of a run against raw M1 -> reports/hand_audit.html")
    h.add_argument("--run", help="runs/<id> (default: the latest run)")
    h.add_argument("--n", type=int, default=20)

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
        from ta.strategy import Config
        print(_save_run(run(Config(), a.pairs), Config(), a.pairs, a.note))
    if a.cmd == "runs":
        from ta.registry import rows, trials
        for r in rows():
            print(f"{r['run_id']}  {r['git']:>16}  {r['period']:>8}  {r['pairs']:<24}  episodes={r['episodes']:>5}  "
                  f"filled={r['filled']:>5}  {r['note']}")
        print(f"trials (distinct configs): {trials()} of the 250 budget")
    if a.cmd == "audit":
        from pathlib import Path

        from ta.audit import build
        from ta.config import ROOT
        print(build(Path(a.run) if a.run else max((ROOT / "runs").glob("2*")), a.n))
    if a.cmd == "control":
        _control(a.pairs, a.n)
    return 0


def _save_run(eps, cfg, pairs, note="") -> str:
    """Store and register a run without printing performance (docs/03: results are only looked at in M4)."""
    import json
    from datetime import datetime

    from ta.config import ROOT
    from ta.registry import config_hash, record, trials
    run_id = f"{datetime.now():%Y%m%d-%H%M%S}-{config_hash(cfg.to_dict())}"
    out = ROOT / "runs" / run_id
    out.mkdir(parents=True)
    (out / "config.json").write_text(json.dumps(cfg.to_dict(), sort_keys=True))
    eps.to_parquet(out / "episodes.parquet")
    record(run_id, cfg.to_dict(), eps, pairs, note=note)
    counts = eps.status.value_counts().to_dict()
    return f"{out}  episodes={len(eps)}  " + "  ".join(f"{k}={v}" for k, v in counts.items()) + f"  trials={trials()}"


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
