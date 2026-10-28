"""M3 hand audit (docs/02 §6.5): re-trace random trades from a saved run against the raw M1 data.

The checks are written again here, minute by minute in plain Python, without broker.py or strategy.py, so a bug
in the vectorised engine cannot hide in both places. Output: reports/hand_audit.html, one chart per trade.
"""
import base64
import html
import io
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle

from ta.config import DATA, REPORTS, pip_size
from ta.data.store import read_m1

NY, LDN = "America/New_York", "Europe/London"
RESEARCH = (2010, 2019)  # docs/03 §2: never audit validation or hold-out trades


def _fillable(t: pd.Timestamp) -> bool:
    """Session 07-17 London, no rollover 16:45-17:30 NY, no Fri 15:00 - Sun 17:00 NY (holidays checked apart)."""
    ny, ldn = t.tz_convert(NY), t.tz_convert(LDN)
    m = ny.hour * 60 + ny.minute
    weekend = (ny.day_of_week == 4 and m >= 900) or ny.day_of_week == 5 or (ny.day_of_week == 6 and m < 1020)
    return 7 <= ldn.hour < 17 and not (1005 <= m < 1050) and not weekend


def retrace(t, m1: pd.DataFrame, cfg: dict) -> dict:
    """Walk the raw minutes for one trade; returns what the rules say should have happened."""
    pip, d = pip_size(t.pair), t.dir
    ft, slip = cfg["fill_through_pips"] * pip, cfg["slip_pips"] * pip
    rows = m1[m1.ts >= pd.Timestamp(t.place_ts, tz="UTC")].reset_index(drop=True)
    i = next(k for k, r in enumerate(rows.itertuples(index=False))
             if (r.ask_l <= t.entry - ft if d == 1 else r.bid_h >= t.entry + ft) and _fillable(r.ts.floor("15min")))
    fill = rows.ts[i]
    ny = fill.tz_convert(NY)
    flat = ny.normalize() + pd.Timedelta(days=(4 - ny.day_of_week) % 7, hours=16, minutes=30)
    if flat <= ny:
        flat += pd.Timedelta(days=7)
    out = {"fill_ts": fill}
    for k in range(i, len(rows)):
        r = rows.iloc[k]
        if k > i and r.ts >= flat:
            out |= {"exit_ts": r.ts, "reason": "flat", "exit_px": r.bid_o - slip if d == 1 else r.ask_o + slip}
            break
        if r.bid_l <= t.stop if d == 1 else r.ask_h >= t.stop:
            px = t.stop - slip if d == 1 else t.stop + slip
            if k > i:  # a gap through the stop fills at the open
                px = min(px, r.bid_o) if d == 1 else max(px, r.ask_o)
            out |= {"exit_ts": r.ts, "reason": "stop", "exit_px": px}
            break
        if k > i and (r.bid_h >= t.target + ft if d == 1 else r.ask_l <= t.target - ft):
            out |= {"exit_ts": r.ts, "reason": "target", "exit_px": t.target}
            break
    days = pd.date_range(fill.tz_convert(NY).normalize(), out["exit_ts"].tz_convert(NY).normalize(), freq="D")
    nights = sum(1 for day in days if day.day_of_week < 5 and fill < day + pd.Timedelta(hours=17) <= out["exit_ts"])
    comm = lambda px: cfg["commission_per_lot"] / 1e5 * (1.0 if t.pair.endswith("USD") else px)
    net = (out["exit_px"] - t.entry) * d - comm(t.entry) - comm(out["exit_px"]) - nights * cfg["swap_pips"] * pip
    return out | {"nights": nights, "R": net / abs(t.entry - t.stop)}


def check(t, m1: pd.DataFrame, cfg: dict) -> tuple[dict, list[tuple[str, bool, str]]]:
    pip, d = pip_size(t.pair), t.dir
    x = retrace(t, m1, cfg)
    near, far = (t.zone_high, t.zone_low) if d == 1 else (t.zone_low, t.zone_high)
    zone, place = pd.Timestamp(t.zone_ts, tz="UTC"), pd.Timestamp(t.place_ts, tz="UTC")
    pre = m1[(m1.ts >= zone) & (m1.ts < place)]
    touched = ((pre.bid_l + pre.ask_l) / 2 <= near).any() if d == 1 else ((pre.bid_h + pre.ask_h) / 2 >= near).any()
    live = m1[(m1.ts >= place) & (m1.ts < x["fill_ts"].floor("15min"))]
    closes = live.groupby(live.ts.dt.floor("15min")).last()
    broken = (((closes.bid_c + closes.ask_c) / 2 - far) * d < 0).any()
    cs = [
        ("entry at the near edge", np.isclose(t.entry, near), f"{t.entry:.5f}, zone {t.zone_low:.5f}-{t.zone_high:.5f}"),
        ("stop beyond the far edge, >= 15 pips", (far - t.stop) * d > 0 and t.dist >= 15 * pip - 1e-12,
         f"stop {t.stop:.5f}, {t.dist / pip:.1f} pips"),
        ("target = entry + 3R", np.isclose(t.target, t.entry + d * 3 * t.dist), f"{t.target:.5f}"),
        ("zone not touched before the order", not touched, f"{len(pre)} min from creation to placement"),
        ("no close beyond the far edge while pending", not broken, f"{len(closes)} M15 closes pending"),
        ("fill minute (first trade-through in session)", x["fill_ts"].value == t.fill_ts,
         f"{x['fill_ts'].tz_convert(LDN):%a %d %b %H:%M} London"),
        ("exit minute and reason", x["exit_ts"].value == t.exit_ts and x["reason"] == t.reason,
         f"{x['reason']} at {x['exit_ts'].tz_convert(NY):%a %d %b %H:%M} NY"),
        ("exit price", np.isclose(x["exit_px"], t.exit_px, rtol=0, atol=1e-9), f"{x['exit_px']:.5f}"),
        ("nights of swap", x["nights"] == t.nights, str(x["nights"])),
        ("net R", np.isclose(x["R"], t.R, rtol=0, atol=1e-9), f"{x['R']:+.3f}"),
    ]
    return x, cs


def chart(t, m1: pd.DataFrame, x: dict) -> str:
    w = m1[(m1.ts >= pd.Timestamp(t.zone_ts, tz="UTC") - pd.Timedelta(hours=8)) & (m1.ts < x["exit_ts"] + pd.Timedelta(hours=3))]
    mid = pd.DataFrame({k: (w[f"bid_{k}"] + w[f"ask_{k}"]) / 2 for k in "ohlc"}).assign(ts=w.ts.dt.floor("15min"))
    b = mid.groupby("ts").agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last")).reset_index()
    xi = lambda ts: int(b.ts.searchsorted(ts.floor("15min")))
    fig, ax = plt.subplots(figsize=(11, 4.2), dpi=90)
    ax.vlines(b.index, b.l, b.h, color="#555", lw=0.7)
    for i, r in b.iterrows():
        y0, y1 = sorted((r.o, r.c))
        ax.add_patch(Rectangle((i - 0.35, y0), 0.7, max(y1 - y0, 1e-9), lw=0, color="#2e9d6a" if r.c >= r.o else "#d0453c"))
    z0 = xi(pd.Timestamp(t.zone_ts, tz="UTC")) - 1  # zone_ts is the creation close
    ax.add_patch(Rectangle((z0, t.zone_low), len(b) - z0, t.zone_high - t.zone_low, color="#2e7bd6", alpha=0.18, lw=0))
    for y, col, lab in ((t.entry, "#2e7bd6", "entry"), (t.stop, "#d0453c", "stop"), (t.target, "#2e9d6a", "target")):
        ax.axhline(y, color=col, lw=1, ls="--", label=lab)
    ax.axvline(xi(pd.Timestamp(t.place_ts, tz="UTC")) - 0.5, color="#888", lw=1, ls=":", label="order placed")
    ax.plot(xi(x["fill_ts"]), t.entry, "o", color="k", ms=7, label="fill")
    ax.plot(xi(x["exit_ts"]), x["exit_px"], "X", color="k", ms=9, label=f"exit ({x['reason']})")
    ticks = b.index[::12]
    ax.set_xticks(ticks, [b.ts[i].tz_convert(NY).strftime("%a %d %b %H:%M") for i in ticks], fontsize=7)
    ax.legend(fontsize=7, ncols=6, loc="best")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def build(run_dir: Path, n: int = 20, seed: int = 20261029, out: Path = REPORTS / "hand_audit.html") -> str:
    cfg = json.loads((run_dir / "config.json").read_text())
    eps = pd.read_parquet(run_dir / "episodes.parquet")
    year = pd.to_datetime(eps.fill_ts, utc=True).dt.year
    pool = eps[(eps.status == "filled") & (eps.exit_ts >= 0) & year.between(*RESEARCH)]
    pick = pool.sample(n, random_state=seed).sort_values(["pair", "fill_ts"])
    cache, parts, failed = {}, [], 0
    for t in pick.itertuples(index=False):
        y0, y1 = pd.Timestamp(t.zone_ts, tz="UTC").year, pd.Timestamp(t.exit_ts, tz="UTC").year
        key = (t.pair, y0, y1)
        if key not in cache:
            cache[key] = read_m1(t.pair, years=range(y0, y1 + 1), root=DATA).sort_values("ts").reset_index(drop=True)
        m1 = cache[key]
        x, cs = check(t, m1, cfg)
        bad = [name for name, ok, _ in cs if not ok]
        failed += bool(bad)
        when = pd.Timestamp(t.fill_ts, tz="UTC").tz_convert(LDN)
        print(f"{t.pair} {when:%Y-%m-%d %H:%M}  {'OK' if not bad else 'FAIL: ' + '; '.join(bad)}", flush=True)
        trs = "".join(f"<tr><td>{'✔' if ok else '✘'}</td><td>{html.escape(name)}</td><td>{html.escape(info)}</td></tr>"
                      for name, ok, info in cs)
        parts.append(f"<section><h2>{t.pair} {'long' if t.dir == 1 else 'short'}, filled {when:%Y-%m-%d %H:%M} London"
                     f"</h2><img src='data:image/png;base64,{chart(t, m1, x)}' alt='M15 chart of the trade'>"
                     f"<table>{trs}</table></section>")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"""<!doctype html><meta charset="utf-8"><title>Hand audit</title>
<style>body{{font:14px system-ui;max-width:1040px;margin:auto;padding:16px;background:#fff;color:#222}}
img{{max-width:100%}}td{{padding:2px 8px;border-bottom:1px solid #eee}}section{{margin:28px 0}}</style>
<h1>M3 hand audit: {run_dir.name}</h1>
<p>{n} random filled trades from {RESEARCH[0]}-{RESEARCH[1]}, re-traced minute by minute from raw M1 with code that
does not use the engine. {n - failed}/{n} pass every check.</p>{''.join(parts)}""")
    return f"{out}  {n - failed}/{n} trades pass"
