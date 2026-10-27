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
        from ta.review import build
        print(build({k: int(n) for k, n in (s.split("=") for s in a.sample)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
