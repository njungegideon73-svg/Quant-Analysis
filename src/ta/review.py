"""M2 faithfulness review: chart a random sample of S1 candidate zones for a by-eye check against JeaFx's
method -> reports/faithfulness_review.html (self-contained, verdicts exportable as CSV)."""
import base64
import html
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle

from ta.config import DATA, REPORTS, pip_size
from ta.features import atr, equal_levels, htf_index, pivots, structure, zones

PARAMS = {"N": 3, "k": 0.5, "m": 1.0, "N_h4": 3}  # mid-grid values (docs/03 §3)
QUESTIONS = ["BOS is a body close through a real swing", "Zone = last candle before the impulse",
             "Visible imbalance in the impulse", "JeaFx would draw this zone"]


def candidates(pair: str) -> tuple[pd.DataFrame, dict]:
    """Continuation zones whose direction matches the last closed H4 state, plus what chart() needs."""
    m15 = pd.read_parquet(DATA / "derived" / pair / "M15.parquet")
    h4 = pd.read_parquet(DATA / "derived" / pair / "H4.parquet")
    o, h, l, c = (m15[f"mid_{x}"].to_numpy() for x in "ohlc")
    a = atr(h, l, c)
    piv = pivots(h, l, PARAMS["N"], PARAMS["k"], a)
    ev, bar = structure(h, l, c, piv)
    z = zones(o, h, l, c, ev, a, PARAMS["m"])
    h4h, h4l, h4c = (h4[f"mid_{x}"].to_numpy() for x in "hlc")
    _, h4bar = structure(h4h, h4l, h4c, pivots(h4h, h4l, PARAMS["N_h4"]))
    ix = htf_index(m15.close_ts, h4.close_ts)
    h4state = np.where(ix >= 0, h4bar.state.to_numpy()[ix.clip(0)], 0)
    z = z[(z.kind == "cont") & (h4state[z.t] == z.dir)].reset_index(drop=True)
    ctx = {"m15": m15, "o": o, "h": h, "l": l, "c": c, "atr": a, "piv": piv, "ev": ev, "bar": bar,
           "eql": equal_levels(h, l, piv, a)}
    return z, ctx


def chart(zr, ctx) -> str:
    o, h, l, c, m15 = ctx["o"], ctx["h"], ctx["l"], ctx["c"], ctx["m15"]
    e = ctx["ev"][ctx["ev"].t == zr.t_bos].iloc[0]
    lo_i, hi_i = max(0, min(e.broken_bar, zr.origin) - 25), min(len(c), zr.t + 49)
    x = np.arange(lo_i, hi_i)
    fig, ax = plt.subplots(figsize=(11, 4.6), dpi=90)
    ax.vlines(x, l[x], h[x], color="#555", lw=0.7)
    for xi in x:
        y0, y1 = sorted((o[xi], c[xi]))
        ax.add_patch(Rectangle((xi - 0.35, y0), 0.7, max(y1 - y0, 1e-9), lw=0,
                               color="#2e9d6a" if c[xi] >= o[xi] else "#d0453c"))
    zc = "#2e7bd6" if zr.dir == 1 else "#d68a2e"
    ax.add_patch(Rectangle((zr.zone_bar - 0.5, zr.low), hi_i - zr.zone_bar, zr.high - zr.low, color=zc, alpha=0.18,
                           lw=0, label="zone"))
    ax.hlines(e.broken_price, e.broken_bar, zr.t_bos, colors="k", linestyles="--", lw=1, label="broken swing")
    ax.plot(zr.t_bos, c[zr.t_bos], marker="^" if zr.dir == 1 else "v", color="k", ms=9, ls="", label="BOS close")
    k = zr.fvg_bar
    g0, g1 = (h[k - 1], l[k + 1]) if zr.dir == 1 else (h[k + 1], l[k - 1])
    ax.add_patch(Rectangle((k - 1.5, g0), 3, g1 - g0, color="#9b59b6", alpha=0.35, lw=0, label="FVG"))
    ax.add_patch(Rectangle((zr.impulse - 0.45, l[zr.impulse]), 0.9, h[zr.impulse] - l[zr.impulse], fill=False,
                           ec="k", lw=1.2, label="impulse candle"))
    ax.axvline(zr.t, color=zc, lw=1, ls=":", label="zone created")
    ax.hlines(ctx["bar"]["eq"][zr.t], zr.t, hi_i, colors="#888", linestyles="-.", lw=1, label="EQ (discount line)")
    p = ctx["piv"][(ctx["piv"].bar >= lo_i) & (ctx["piv"].bar < hi_i)]
    for known, face in ((True, "k"), (False, "none")):  # hollow = confirmed only after the zone was created
        q = p[(p.confirm <= zr.t) == known]
        ax.scatter(q.bar, q.price + q.dir * 0.15 * ctx["atr"][zr.t], marker="o", s=14, facecolors=face,
                   edgecolors="k", lw=0.6)
    for r in ctx["eql"][(ctx["eql"].confirm <= zr.t) & (ctx["eql"].bar2 >= lo_i)].itertuples():
        ax.hlines(r.price, r.bar1, hi_i, colors="#e67e22" if r.dir == -1 else "#16a085", linestyles=":", lw=1.2)
    ts = m15.ts.dt.tz_convert("America/New_York")
    ticks = x[::16]
    ax.set_xticks(ticks, [ts[i].strftime("%a %d %b %H:%M") for i in ticks], fontsize=7)
    ax.set_xlim(lo_i - 1, hi_i)
    ax.legend(fontsize=7, loc="best", ncols=4)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def build(sample: dict[str, int], seed: int = 20261027, out=REPORTS / "faithfulness_review.html"):
    cards, rng = [], np.random.default_rng(seed)
    for pair, n in sample.items():
        z, ctx = candidates(pair)
        pip = pip_size(pair)
        for zr in z.iloc[np.sort(rng.choice(len(z), size=min(n, len(z)), replace=False))].itertuples():
            ts = ctx["m15"].ts.dt.tz_convert("America/New_York")[zr.t]
            facts = (f"{pair} · {'LONG' if zr.dir == 1 else 'SHORT'} · created {ts:%Y-%m-%d %H:%M} NY · "
                     f"zone {zr.low:.5g}–{zr.high:.5g} ({(zr.high - zr.low) / pip:.1f} pips) · "
                     f"ATR {ctx['atr'][zr.t] / pip:.1f} pips · FVG {'on BOS+1' if zr.t > zr.t_bos else 'by BOS'}")
            cards.append((f"{pair}-{ts:%Y%m%d%H%M}", facts, chart(zr, ctx)))
    qs = "".join(f"<th>{html.escape(q)}</th>" for q in QUESTIONS)
    body = ""
    for i, (cid, facts, png) in enumerate(cards, 1):
        cells = "".join(f'<td><label><input type="radio" name="{cid}|{j}" value="yes">Y</label> '
                        f'<label><input type="radio" name="{cid}|{j}" value="no">N</label></td>'
                        for j in range(len(QUESTIONS)))
        body += (f'<section><h3>{i}. {html.escape(facts)}</h3><img src="data:image/png;base64,{png}" '
                 f'alt="setup {i} chart"><table><tr>{qs}<th>Notes</th></tr><tr data-id="{cid}">{cells}'
                 f'<td><input type="text" name="{cid}|notes" size="30"></td></tr></table></section>')
    params = ", ".join(f"{k}={v}" for k, v in PARAMS.items())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"""<!doctype html><html><head><meta charset="utf-8"><title>Faithfulness Review</title>
<style>body{{font:14px system-ui;margin:16px;max-width:1040px;background:#fff;color:#222}}img{{max-width:100%}}
section{{border-top:1px solid #ccc;padding:8px 0}}table{{border-collapse:collapse;font-size:12px}}
th,td{{border:1px solid #ddd;padding:3px 6px}}h3{{font-size:14px}}</style></head><body>
<h1>M2 faithfulness review: {len(cards)} S1 candidates</h1>
<p>Continuation zones aligned with the H4 trend, sampled at random (seed {seed}), params {params}.
Freshness, discount, session and stop filters are <b>not</b> applied yet (M3). Filled dots = swings known when the
zone was created; hollow = confirmed later. Dotted orange/green = equal lows/highs known at creation.
Suggested pass mark: at least 24 of 30 (80%) answered "JeaFx would draw this zone".</p>
<p><button onclick="exportCsv()">Export verdicts (CSV)</button> <span id="score"></span></p>{body}
<script>
const K='faithfulness-review';
function save(){{const d={{}};document.querySelectorAll('input').forEach(i=>{{if(i.type==='radio'?i.checked:i.value)d[i.name]=i.value}});
try{{localStorage.setItem(K,JSON.stringify(d))}}catch(e){{}}score()}}
function score(){{const r=[...document.querySelectorAll('tr[data-id]')].map(t=>t.querySelector('input[name$="|3"]:checked')).filter(Boolean);
document.getElementById('score').textContent=r.length?`JeaFx would draw: ${{r.filter(x=>x.value==='yes').length}}/${{r.length}}`:''}}
function exportCsv(){{const rows=[['setup',...{QUESTIONS!r},'notes']];document.querySelectorAll('tr[data-id]').forEach(t=>{{const id=t.dataset.id;
rows.push([id,...[0,1,2,3].map(j=>(t.querySelector(`input[name="${{id}}|${{j}}"]:checked`)||{{}}).value||''),t.querySelector('input[type=text]').value])}});
const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([rows.map(r=>r.map(v=>`"${{String(v).replace(/"/g,'""')}}"`).join(',')).join('\\n')],{{type:'text/csv'}}));
a.download='faithfulness_review.csv';a.click()}}
try{{const d=JSON.parse(localStorage.getItem(K)||'{{}}');document.querySelectorAll('input').forEach(i=>{{if(!(i.name in d))return;
if(i.type==='radio')i.checked=d[i.name]===i.value;else i.value=d[i.name]}})}}catch(e){{}}
document.addEventListener('input',save);score();
</script></body></html>""")
    return out
