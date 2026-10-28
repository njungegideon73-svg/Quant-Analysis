"""Data quality checks on stored M1 data -> reports/data_quality.html (docs/02 §3)."""
from pathlib import Path

import numpy as np
import pandas as pd

from ta.config import DATA, REPORTS, pip_size
from ta.data.store import read_m1

NY = "America/New_York"


def classify_gaps(ts: pd.Series, min_gap="5min") -> pd.DataFrame:
    """Gaps between consecutive bars longer than min_gap, labelled weekend / holiday / unexplained."""
    ts = ts.sort_values(ignore_index=True)
    dt_ = ts.diff()
    i = np.flatnonzero(dt_ > pd.Timedelta(min_gap))
    gaps = pd.DataFrame({"start": ts.iloc[i - 1].reset_index(drop=True), "end": ts.iloc[i].reset_index(drop=True)})
    if gaps.empty:
        return gaps.assign(minutes=[], kind=[])
    gaps["minutes"] = (gaps.end - gaps.start).dt.total_seconds() / 60 - 1
    s_ny, e_ny = gaps.start.dt.tz_convert(NY), gaps.end.dt.tz_convert(NY)

    def spans(day_test):  # does any NY calendar day inside the gap satisfy day_test?
        return [any(day_test(d) for d in pd.date_range(a.normalize(), b.normalize())) for a, b in zip(s_ny, e_ny)]

    short = (gaps.minutes <= 4 * 1440).to_numpy()  # a weekend plus a holiday Monday at most; longer is missing data
    weekend = short & spans(lambda d: d.weekday() == 5)
    holiday = short & spans(lambda d: (d.month, d.day) in {(12, 25), (1, 1)})
    gaps["kind"] = np.where(weekend, "weekend", np.where(holiday, "holiday", "unexplained"))
    return gaps


def check(m1: pd.DataFrame, pair: str) -> dict:
    pip = pip_size(pair)
    crossed = sum((m1[f"ask_{k}"] < m1[f"bid_{k}"]).sum() for k in "ohlc")
    bad = sum(((m1[f"{s}_h"] < m1[[f"{s}_o", f"{s}_c"]].max(axis=1)) |
               (m1[f"{s}_l"] > m1[[f"{s}_o", f"{s}_c"]].min(axis=1))).sum() for s in ("bid", "ask"))
    spread = (m1.ask_c - m1.bid_c) / pip
    hour_median = spread.groupby(m1.ts.dt.hour).transform("median")
    mid = (m1.bid_c + m1.ask_c) / 2
    move = mid.diff().abs()
    typical = move.rolling(60, min_periods=10).mean().shift(1)
    # spike = huge 1-min move that mostly reverses on the next bar
    spikes = (move > 15 * typical) & (mid.diff(-1).abs() > 0.5 * move)
    gaps = classify_gaps(m1.ts)
    unexplained = gaps[gaps.kind == "unexplained"]
    return {
        "pair": pair, "rows": len(m1), "first": m1.ts.min(), "last": m1.ts.max(),
        "dup_ts": int(m1.ts.duplicated().sum()),
        "non_monotonic": int((m1.ts.diff() <= pd.Timedelta(0)).sum()),
        "crossed": int(crossed), "bad_ohlc": int(bad),
        "spread_med_pips": round(float(spread.median()), 2),
        "spread_p99_pips": round(float(spread.quantile(0.99)), 2),
        "spread_events": int((spread > 10 * hour_median.clip(lower=0.1)).sum()),
        "spikes": int(spikes.sum()),
        "gaps_unexplained": len(unexplained),
        "gap_unexplained_pct": round(100 * unexplained.minutes.sum() / (len(m1) + unexplained.minutes.sum()), 3),
        "_gaps": unexplained.nlargest(20, "minutes"),
    }


def write_report(pairs, root: Path = DATA, out: Path = REPORTS / "data_quality.html") -> Path:
    rows, details = [], []
    for pair in pairs:
        m1 = read_m1(pair, root=root, raw=True)
        if m1.empty:
            continue
        for year, g in m1.groupby(m1.ts.dt.year):
            r = check(g.reset_index(drop=True), pair)
            r["year"] = year
            details.append(f"<h3>{pair} {year}: largest unexplained gaps</h3>" + r.pop("_gaps").to_html(index=False))
            rows.append(r)
    table = pd.DataFrame(rows)
    out.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(out.with_suffix(".csv"), index=False)
    flag = "> 0.5% unexplained gap minutes, any crossed/dup/non-monotonic → investigate"
    out.write_text(f"<html><body><h1>M1 data quality</h1><p>{flag}</p>"
                   + table.to_html(index=False) + "".join(details) + "</body></html>")
    return out
