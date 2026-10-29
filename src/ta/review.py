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
from ta.strategy import LDN

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


def _candles(ax, x, o, h, l, c):
    ax.vlines(x, l[x], h[x], color="#555", lw=0.7)
    for xi in x:
        y0, y1 = sorted((o[xi], c[xi]))
        ax.add_patch(Rectangle((xi - 0.35, y0), 0.7, max(y1 - y0, 1e-9), lw=0,
                               color="#2e9d6a" if c[xi] >= o[xi] else "#d0453c"))


def _png(fig) -> str:
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def chart(zr, ctx) -> str:
    o, h, l, c, m15 = ctx["o"], ctx["h"], ctx["l"], ctx["c"], ctx["m15"]
    e = ctx["ev"][ctx["ev"].t == zr.t_bos].iloc[0]
    lo_i, hi_i = max(0, min(e.broken_bar, zr.origin) - 25), min(len(c), zr.t + 49)
    x = np.arange(lo_i, hi_i)
    fig, ax = plt.subplots(figsize=(11, 4.6), dpi=90)
    _candles(ax, x, o, h, l, c)
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
    return _png(fig)


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
    params = ", ".join(f"{k}={v}" for k, v in PARAMS.items())
    intro = f"""<h1>M2 faithfulness review: {len(cards)} S1 candidates</h1>
<p>Continuation zones aligned with the H4 trend, sampled at random (seed {seed}), params {params}.
Freshness, discount, session and stop filters are <b>not</b> applied yet (M3). Filled dots = swings known when the
zone was created; hollow = confirmed later. Dotted orange/green = equal lows/highs known at creation.
Suggested pass mark: at least 24 of 30 (80%) answered "JeaFx would draw this zone".</p>
"""
    return page(cards, "Faithfulness Review", intro, QUESTIONS, "faithfulness-review", out)


def page(cards, title, intro, questions, key, out):
    """Self-contained review page: one chart per card, Y/N per question, notes, verdicts kept in localStorage and
    exportable as CSV. The last question is the one scored."""
    qs = "".join(f"<th>{html.escape(q)}</th>" for q in questions)
    body = ""
    for i, (cid, facts, png) in enumerate(cards, 1):
        cells = "".join(f'<td><label><input type="radio" name="{cid}|{j}" value="yes">Y</label> '
                        f'<label><input type="radio" name="{cid}|{j}" value="no">N</label></td>'
                        for j in range(len(questions)))
        body += (f'<section><h3>{i}. {html.escape(facts)}</h3><img src="data:image/png;base64,{png}" '
                 f'alt="setup {i} chart"><table><tr>{qs}<th>Notes</th></tr><tr data-id="{cid}">{cells}'
                 f'<td><input type="text" name="{cid}|notes" size="30"></td></tr></table></section>')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"""<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>body{{font:14px system-ui;margin:16px;max-width:1040px;background:#fff;color:#222}}img{{max-width:100%}}
section{{border-top:1px solid #ccc;padding:8px 0}}table{{border-collapse:collapse;font-size:12px}}
th,td{{border:1px solid #ddd;padding:3px 6px}}h3{{font-size:14px}}</style></head><body>
{intro}
<p><button onclick="exportCsv()">Export verdicts (CSV)</button> <span id="score"></span></p>{body}
<script>
const K='{key}';
function save(){{const d={{}};document.querySelectorAll('input').forEach(i=>{{if(i.type==='radio'?i.checked:i.value)d[i.name]=i.value}});
try{{localStorage.setItem(K,JSON.stringify(d))}}catch(e){{}}score()}}
function score(){{const r=[...document.querySelectorAll('tr[data-id]')].map(t=>t.querySelector('input[name$="|{len(questions) - 1}"]:checked')).filter(Boolean);
document.getElementById('score').textContent=r.length?`Yes on the last question: ${{r.filter(x=>x.value==='yes').length}}/${{r.length}}`:''}}
function exportCsv(){{const rows=[['setup',...{questions!r},'notes']];document.querySelectorAll('tr[data-id]').forEach(t=>{{const id=t.dataset.id;
rows.push([id,...{list(range(len(questions)))}.map(j=>(t.querySelector(`input[name="${{id}}|${{j}}"]:checked`)||{{}}).value||''),t.querySelector('input[type=text]').value])}});
const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([rows.map(r=>r.map(v=>`"${{String(v).replace(/"/g,'""')}}"`).join(',')).join('\\n')],{{type:'text/csv'}}));
a.download='{out.stem}.csv';a.click()}}
try{{const d=JSON.parse(localStorage.getItem(K)||'{{}}');document.querySelectorAll('input').forEach(i=>{{if(!(i.name in d))return;
if(i.type==='radio')i.checked=d[i.name]===i.value;else i.value=d[i.name]}})}}catch(e){{}}
document.addEventListener('input',save);score();
</script></body></html>""")
    return out


S4_QUESTIONS = ["H4 bias read correctly", "Clean M15 close beyond the Asia range",
                "Entry and stop where JeaFx would put them", "JeaFx would take this trade"]


def s4_context(pair: str) -> dict:
    """prepare_frames() for S4 on the research period only (2010-2019: no validation or hold-out bars)."""
    from ta.s4 import S4Config
    from ta.strategy import prepare_frames
    end = pd.Timestamp("2020-01-01", tz="UTC")
    m15, h4 = (pd.read_parquet(DATA / "derived" / pair / f"{tf}.parquet") for tf in ("M15", "H4"))
    m15, h4 = m15[m15.close_ts <= end].reset_index(drop=True), h4[h4.close_ts <= end].reset_index(drop=True)
    return {"f": prepare_frames(pair, m15, h4, S4Config()), "h4": h4}


def s4_chart(r, zone, ctx) -> str:
    """Left: the last 40 closed H4 bars at the breakout close, with the swings known then. Right: the M15 day from
    00:00 UK up to the bar the order is placed on; nothing after it is drawn (blind to the outcome)."""
    f, h4 = ctx["f"], ctx["h4"]
    d, t, p = int(r.dir), int(r.t_bos), int(r.place_bar)
    fig, (a4, ax) = plt.subplots(1, 2, figsize=(12, 4.6), dpi=90, gridspec_kw={"width_ratios": [1, 2]})
    o4, h4h, h4l, c4 = (h4[f"mid_{x}"].to_numpy() for x in "ohlc")
    k = int(np.searchsorted(h4.close_ts.astype("datetime64[ns, UTC]").astype("int64").to_numpy(), f["close_ts"].astype("datetime64[ns, UTC]").astype("int64").to_numpy()[t], side="right"))  # H4 bars closed
    x4 = np.arange(max(0, k - 40), k)
    _candles(a4, x4, o4, h4h, h4l, c4)
    pv = pivots(h4h[:k], h4l[:k], 3)
    pv = pv[(pv.confirm < k) & (pv.bar >= x4[0])]
    a4.scatter(pv.bar, pv.price, marker="o", s=16, facecolors="none", edgecolors="k", lw=0.8)
    a4.set_title(f"H4 structure at the breakout: {'BULLISH' if d == 1 else 'BEARISH'}", fontsize=9)
    a4.set_xticks([])
    a4.grid(alpha=0.2)
    uk = f["ts"].dt.tz_convert(LDN)
    lo_i = int(np.searchsorted(f["ts"].astype("datetime64[ns, UTC]").astype("int64").to_numpy(), pd.Timestamp(f"{uk[t].date()} 00:00", tz=LDN).value))
    x = np.arange(lo_i, p + 1)
    o, h, l, c = f["o"], f["h"], f["l"], f["c"]
    _candles(ax, x, o, h, l, c)
    asia = x[(uk[x].dt.hour >= 1).to_numpy() & (uk[x].dt.hour < 7).to_numpy()]
    if asia.size:
        ah, al = h[asia].max(), l[asia].min()
        ax.add_patch(Rectangle((asia[0] - 0.5, al), asia[-1] - asia[0] + 1, ah - al, color="#888", alpha=0.15, lw=0,
                               label="Asia range"))
    ax.plot(t, c[t], marker="^" if d == 1 else "v", color="k", ms=9, ls="", label="breakout close")
    ax.plot(r.swing_bar, r.swing, marker="o", color="#8e44ad", ms=7, ls="", label="stop anchor")
    if zone is not None:
        ax.add_patch(Rectangle((zone.zone_bar - 0.5, zone.low), p + 13 - zone.zone_bar, zone.high - zone.low,
                               color="#2e7bd6" if d == 1 else "#d68a2e", alpha=0.25, lw=0, label="M15 zone (zone entry)"))
    for y, col, lab in ((r.entry, "#2e7bd6", "entry (retest)"), (r.stop, "#d0453c", "stop"),
                        (r.entry + d * 3 * r.dist, "#2e9d6a", "3R")):
        ax.hlines(y, p, p + 12, colors=col, lw=1.4, label=lab)
    ax.axvspan(p + 0.5, p + 13, color="#f4f4f4", zorder=-1)
    ax.text(p + 6.5, ax.get_ylim()[0], "after the order: not shown", ha="center", va="bottom", fontsize=7, color="#777")
    ticks = x[::8]
    ax.set_xticks(ticks, [uk[i].strftime("%H:%M") for i in ticks], fontsize=7)
    ax.set_xlim(lo_i - 1, p + 13)
    ax.set_title(f"M15, UK time, {uk[t]:%a %d %b %Y}", fontsize=9)
    ax.legend(fontsize=7, loc="best", ncols=3)
    ax.grid(alpha=0.2)
    return _png(fig)


def build_s4(n_per_pair: int = 4, seed: int = 20261029, out=REPORTS / "s4_review.html", exclude=()):
    """About 30 random S4 setups (retest entry, b = 0.25), 2010-2019, charted blind to the outcome (docs/11 §8)."""
    from ta.config import PAIRS
    from ta.s4 import S4Config, episodes, setups
    cards, rng = [], np.random.default_rng(seed)
    for i, pair in enumerate(PAIRS):
        ctx, pip = s4_context(pair), pip_size(pair)
        f = ctx["f"]
        ep = episodes(f, S4Config()).reset_index(drop=True)
        zs = setups(f, S4Config(entry="zone")).set_index("t")
        z_all = zones(f["o"], f["h"], f["l"], f["c"], pd.DataFrame(
            {"t": zs.index, "dir": zs.d, "kind": "breakout", "origin": zs.org}), f["atr"], 1.0).set_index("t_bos")
        k = n_per_pair + (i < 30 - n_per_pair * len(PAIRS))  # 30 cards in total
        uk_ = f["ts"].dt.tz_convert(LDN).dt.strftime("%Y%m%d%H%M").to_numpy()
        ep = ep[[f"{pair}-{uk_[t]}" not in exclude for t in ep.t_bos]].reset_index(drop=True)  # cards already reviewed
        for r in ep.iloc[np.sort(rng.choice(len(ep), size=min(k, len(ep)), replace=False))].itertuples():
            day = f["ts"].dt.tz_convert(LDN)
            sb = int(np.flatnonzero((day.dt.date == day[r.t_bos].date()).to_numpy())[0])
            seg = slice(sb, r.t_bos + 1)
            swing_bar = sb + int(np.flatnonzero((f["l"] if r.dir == 1 else f["h"])[seg] == r.swing)[-1])
            zone = z_all.loc[r.t_bos] if r.t_bos in z_all.index else None
            rr = {**r._asdict(), "swing_bar": swing_bar}
            ts = day[r.t_bos]
            facts = (f"{pair} · {'LONG' if r.dir == 1 else 'SHORT'} · breakout {ts:%Y-%m-%d %H:%M} UK · "
                     f"entry {r.entry:.5g} · stop {r.dist / pip:.1f} pips · "
                     f"{'has an M15 zone' if zone is not None else 'no valid M15 zone'}")
            cards.append((f"{pair}-{ts:%Y%m%d%H%M}", facts, s4_chart(pd.Series(rr), zone, ctx)))
    intro = f"""<h1>S4 chart review: {len(cards)} setups (docs/11)</h1>
<p>Random S4 setups from 2010-2019 (seed {seed}): H4 bias, Asia range, the first M15 close beyond it on the bias side,
the stop anchor (the further of the London low/high and the opposite Asia side; stop = anchor ± 0.25 ATR), the retest entry at the broken Asia level, and the M15 zone
where one exists. <b>Each chart ends when the order is placed; what happened next is not shown</b>, so judge the setup,
not the outcome. Hollow dots on H4 = swings confirmed by the breakout. Suggested pass mark: 24 of 30 (80%)
"JeaFx would take this trade". Your answers are saved in this browser; export them as CSV when done.</p>
"""
    return page(cards, "S4 Chart Review", intro, S4_QUESTIONS, "s4-review", out)
