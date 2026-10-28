"""Per-run performance report (docs/02 §7) -> runs/{run_id}/report.html: equity in R, drawdown, metrics, and
per-pair / year / London-hour breakdowns. Performance is only looked at from M4 on (docs/03), so this is not run
on research results before then; the M3 test feeds it synthetic trades."""
import base64
import io
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

TARGET_WIN, TARGET_R = 0.30, 0.20  # docs/README: 30% wins at 1:3, +0.20R per trade


def trades(eps: pd.DataFrame) -> pd.DataFrame:
    t = eps[(eps.status == "filled") & (eps.exit_ts >= 0)].copy()
    t["exit"] = pd.to_datetime(t.exit_ts, utc=True)
    t["fill"] = pd.to_datetime(t.fill_ts, utc=True)
    return t.sort_values("exit").reset_index(drop=True)


def metrics(r: pd.Series) -> dict:
    eq = r.cumsum()
    dd = eq - eq.cummax().clip(lower=0)
    wins, losses = r[r > 0], r[r <= 0]
    streak = (r <= 0).astype(int).groupby((r > 0).cumsum()).sum().max() if len(r) else 0
    return {"trades": len(r), "win rate": wins.size / len(r) if len(r) else float("nan"),
            "expectancy (R)": r.mean(), "total (R)": r.sum(), "max drawdown (R)": dd.min() if len(r) else 0.0,
            "profit factor": wins.sum() / -losses.sum() if losses.sum() < 0 else float("inf"),
            "avg win (R)": wins.mean(), "avg loss (R)": losses.mean(), "longest losing run": int(streak)}


def _table(t: pd.DataFrame, by) -> str:
    g = t.groupby(by).R
    out = pd.DataFrame({"trades": g.size(), "win rate": g.apply(lambda r: (r > 0).mean()), "expectancy (R)": g.mean(),
                        "total (R)": g.sum()})
    return out.to_html(float_format=lambda v: f"{v:.3f}")


def _chart(t: pd.DataFrame) -> str:
    eq = t.R.cumsum()
    fig, (a, b) = plt.subplots(2, 1, figsize=(11, 5), dpi=90, sharex=True, height_ratios=(3, 1))
    a.plot(t.exit, eq, color="#2e7bd6", lw=1)
    a.set_ylabel("equity (R)")
    b.fill_between(t.exit, eq - eq.cummax().clip(lower=0), 0, color="#d0453c", alpha=0.5, lw=0)
    b.set_ylabel("drawdown (R)")
    for ax in (a, b):
        ax.grid(alpha=0.2)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def build(run_dir: Path) -> Path:
    t = trades(pd.read_parquet(run_dir / "episodes.parquet"))
    if t.empty:
        raise SystemExit(f"{run_dir.name}: no closed trades")
    m = metrics(t.R)
    rows = "".join(f"<tr><td>{k}</td><td>{v:.3f}</td></tr>" if isinstance(v, float) else f"<tr><td>{k}</td><td>{v}</td></tr>"
                   for k, v in m.items())
    ok = m["win rate"] >= TARGET_WIN and m["expectancy (R)"] >= TARGET_R
    cfg = json.loads((run_dir / "config.json").read_text())
    out = run_dir / "report.html"
    out.write_text(f"""<!doctype html><meta charset="utf-8"><title>Run report</title>
<style>body{{font:14px system-ui;max-width:1040px;margin:auto;padding:16px;background:#fff;color:#222}}img{{max-width:100%}}
table{{border-collapse:collapse;margin:8px 0}}td,th{{padding:2px 10px;border-bottom:1px solid #eee;text-align:right}}</style>
<h1>{run_dir.name}</h1>
<p>{len(t)} closed trades, {t.fill.min():%Y-%m-%d} to {t.exit.max():%Y-%m-%d}, net R after costs.
Targets: win rate ≥ {TARGET_WIN:.0%} and expectancy ≥ +{TARGET_R:.2f}R → <b>{"met" if ok else "not met"}</b>.</p>
<img src="data:image/png;base64,{_chart(t)}" alt="Equity and drawdown in R">
<h2>Metrics</h2><table>{rows}</table>
<h2>By pair</h2>{_table(t, "pair")}
<h2>By year (exit)</h2>{_table(t, t.exit.dt.year.rename("year"))}
<h2>By London hour (fill)</h2>{_table(t, t.fill.dt.tz_convert("Europe/London").dt.hour.rename("hour"))}
<h2>Config</h2><pre>{json.dumps(cfg, indent=1, sort_keys=True)}</pre>""")
    return out
