# Phase 1 — Research & Feasibility Report
**Source:** JeaFx (YouTube) — 5 playlists + 3 standalone videos · **Date:** 2026-10-27

## 0. What was analysed

| Item | Count |
|---|---|
| Playlist entries supplied | 82 (incl. duplicates across playlists) |
| Unique videos | **74** (all 3 standalone videos are in the playlists or covered) |
| Total runtime | ~37 hours |
| Transcribed | **74 / 74** (YouTube captions → `research/transcripts/*.txt`, ~393k words) |
| Rule extraction | Every transcript read in full in 6 batches → `research/notes/b1..b6.md` |
| Spot verification | Key rules and every quoted statistic checked against raw transcripts |

Limitation: transcripts are speech only. The trader points at charts ("this candle here"), so the exact chart a rule was drawn on is not visible. This doesn't block rule definition (he states his rules verbally and repeats them across 30+ videos), but it is why every rule below is a *parameterised proposal* to be tested, not a quote.

---

## 1. Verdict

| Question | Answer |
|---|---|
| Is there enough information to build a system? | **Yes, for the core model.** About 60–70% of what he teaches can be written as objective rules. The rest (the "market narrative", visual "momentum" reads, DXY/Fed bias) cannot be coded and will be left out or tested as optional filters. |
| Is 30% win rate @ 1:3 realistic? | **Plausible, not proven.** It's a much lower bar than he claims (62–64% @ 3R, unaudited). Costs are the main threat, and they decide the timeframe (§4). |
| Can it be proven? | **Yes, with a strict protocol.** That means at least ~500 out-of-sample trades, a hold-out period never touched during design, realistic bid/ask fills, and a live demo forward test (§5). |
| Production-grade? | Yes as an engineering target. Whether to trade it live is decided by the evidence, not up front. |

**Bottom line:** the teaching is a coherent, mostly mechanical **structure → zone → limit-order** model. It's buildable. Whether it has an edge is unknown until we test it, and nothing in the videos is evidence either way: every example is a hand-picked winner.

---

## 2. What he actually teaches (consistent across the playlists)

The same skeleton appears in ~30+ videos:

1. **Bias from swing structure.** HH/HL = bullish, LL/LH = bearish, otherwise consolidation (no trade). A **break of structure (BOS) needs a candle body close** beyond the swing; a wick beyond is a **sweep/rejection**. He rejects "CHoCH" as a term, but uses the first opposite BOS as the reversal signal.
2. **Point of interest = supply/demand zone.** He repeats "*the last candle before the impulse*", drawn wick to wick (found in 32 of 74 transcripts). Valid only if:
   - it caused the impulse that broke structure,
   - there is **unfilled imbalance** between the zone and price (or, in the stricter version, the imbalance has been filled down to the zone),
   - it is **fresh** (first tap only),
   - it is in **discount** (buys below the leg's 50%) or **premium** (sells above it),
   - preferably the **extreme** zone of the leg.
3. **Liquidity filter.** "*Never sell below equal highs, never buy above equal lows.*" Prefer zones where the equal highs/lows, trendline liquidity or Asia range have already been swept.
4. **Entry.** Either a **limit order at the zone** (aggressive), or **"standard confirmation"**: drop 1–2 timeframes, wait for a lower-timeframe body-close BOS in the trade direction, then limit at the new lower-timeframe zone.
5. **Stop** just beyond the zone, or beyond the swing extreme (conservative).
6. **Target.** Structural: previous swing, next opposing unmitigated zone, or liquidity. He screens for **≥3R** and skips anything less.
7. **Risk.** Fixed **1% per trade**. Management (breakeven after the first new BOS, structural trailing) is described loosely in only one video.
8. **Session model** (Bootcamp Ep.11 + 2 others). Mark the Asia range (01–07 UK), London sweeps one side, a lower-timeframe BOS reverses it, target the opposite Asia extreme, flat by 17:00 UK.
9. **Timeframes and pairs.** Bias on 4H/daily, entry on 15m–1H (sometimes 1–5m). Says he mainly trades **GBPUSD and EURUSD**. Examples also show USDJPY, NZDJPY, AUDCAD, EURCHF and XAUUSD.

### His own performance claims (verified in the transcripts, all unaudited)
- "my long term … around 62 to 64%, but I go for three R pretty much all the time" (`1EWdwteWNW0`)
- "53% is the win rate for this account over the past 3 months … 5.85 average" RR, +16% (`Q-jQGto-nic`)
- Elsewhere: "very close to 50%" (`RvO3iQjXui0`), "5 of 10 is fine", "~60% of days" for the session pattern.
- In the maths video he himself says a **6R target ≈ 30% win rate** and an 8R target ≈ 10–15%.

He gives no trade lists, equity curves or sample sizes. A 60% win rate at 3R would be +1.4R per trade, which is far beyond anything a documented retail price-action system shows. **We treat all of these numbers as marketing.** Our 30% target is the conservative, testable version.

---

## 3. Converting it into objective rules (draft spec, everything tunable)

| # | Concept | Objective definition (proposal) | Parameters |
|---|---|---|---|
| R1 | Swing pivot | Fractal high/low with N bars each side, **confirmed only N bars later** (no look-ahead) | N ∈ {2,3,5}; optional min swing size k·ATR |
| R2 | Structure state | State machine: bullish after a body close above the last confirmed swing high, bearish after a body close below the last confirmed swing low | close vs wick (fixed: close) |
| R3 | Impulse | Leg that produced the BOS and has body ≥ m·ATR or leaves a 3-candle imbalance (FVG) | m ∈ {1.0,1.5,2.0} |
| R4 | Zone | Last candle before the impulse leg, high→low (wick to wick); created when the BOS bar closes | zone = candle vs body-only variant |
| R5 | Zone validity | Untouched since creation (first tap), body close through it kills it, lies in discount/premium of the current leg, optional "extreme zone only" | each one A/B tested |
| R6 | Liquidity veto | Equal highs/lows = ≥2 pivots within t·ATR. Skip a sell if unswept equal highs sit between entry and stop (mirror for buys) | t ∈ {0.05,0.1,0.2} |
| R7 | HTF bias | Trade only in the direction of the R2 state on the higher timeframe | HTF/LTF pair |
| R8 | Entry | (a) limit at zone edge, or (b) LTF confirmation: LTF BOS inside the HTF zone, then limit at the LTF zone | variant |
| R9 | Stop / target | Stop = zone extreme + buffer (spread + x·ATR). **Target = fixed 3R** (your spec) vs structural target filtered ≥3R | buffer x |
| R10 | Session/news | Trade window (e.g. London + NY), no entries ±30 min around high-impact news, no rollover hour, no holding over the weekend | windows |
| R11 | Expiry | Cancel a pending limit after K bars or when structure flips | K |

What gets left out (not codable, or only hindsight): the "narrative", the "true zone vs inducement" picks (he chooses using later price), "fuel"-based sweep-vs-break calls, momentum read by eye, and the DXY/Fed bias. The one exception: momentum may come back as a measurable filter (for example pullback speed vs impulse speed in ATR) if it proves itself out-of-sample.

**Contradictions to settle by testing, not opinion:** extreme zone vs BOS-creating zone, limit vs confirmation entry, zone-edge stop vs swing stop, imbalance "unfilled" vs "filled first", and liquidity as a veto vs as a trigger. Each becomes an A/B variant, and we keep the count small to limit data-mining.

---

## 4. The maths that drives the design

### 4.1 Costs decide the timeframe
Assume a round-trip cost of ~1.0 pip (raw-spread account + commission on EURUSD). That cost is a fixed amount in pips, so it eats a larger share of R the tighter the stop:

| Stop size | Cost in R | EV at 30% WR, 3R | Break-even WR |
|---|---|---|---|
| 5 pips | 0.20R | **+0.00R** | 30.0% |
| 10 pips | 0.10R | +0.10R | 27.5% |
| 15 pips | 0.07R | +0.13R | 26.7% |
| 20 pips | 0.05R | +0.15R | 26.2% |
| 30 pips | 0.03R | +0.17R | 25.8% |

➡ The 1–5m "sniper" entries in the videos make the target unreachable after costs. **Recommendation: 4H (or 1H) bias, 15m/1H entry, with a minimum stop of ~15 pips (FX) enforced as a rule.**

### 4.2 How many trades it takes to prove an edge
- To show a 30% win rate is really above the 25% break-even (one-sided α = 5%, 80% power), we need **≈ 480 trades**.
- 95% confidence band on the win rate: ±9% at 100 trades, ±5% at 300, **±4% at 500**, ±2.8% at 1,000.
- One pair on 15m gives perhaps 50–150 setups a year. So we need **multiple pairs and 10+ years of data**, which argues for a basket of 6–8 pairs.

### 4.3 What a *working* 30% / 3R system feels like (Monte Carlo, 500 trades)
- Longest losing streak: **median 15, 95th percentile 22.**
- Max drawdown: **median 22R, 95th percentile 39R.**
- At 1% risk that's a −22% to −39% drawdown. **Not compatible with prop-firm limits (~10%)**, where risk would need to be about 0.25%.

The system can be profitable and still psychologically brutal. That's why the risk-per-trade decision matters as much as the rules.

---

## 5. How we prove it (backtest → forward test)

1. **Data.** Bid/ask M1 candles, 2010 to now, from OANDA v20 (free practice account, history back to ~2005), cross-checked against Dukascopy. Store as Parquet and query with DuckDB.
2. **Causal engine.** Event-driven and bar-by-bar on the trading timeframe, using **M1 bars inside each bar** to resolve whether the stop or the target was hit first. Limits fill only if the **ask/bid trades through** the level (no touch-fills). Costs include spread, commission, slippage on stops, and swap.
3. **Data split.**
   - 2010–2019: design and tuning.
   - 2020–2023: walk-forward validation.
   - **2024–2026: hold-out, opened once, at the end.**
4. **Anti-overfitting.**
   - Parameter grid declared in advance.
   - Results reported as distributions across the grid and across pairs, not as the best cell.
   - Deflated-Sharpe / White's Reality Check-style adjustment.
   - The edge must hold on most pairs, not just one.
5. **Robustness.** Cost ×1.5 and ×2 stress, ±1 bar of latency, parameter perturbation, Monte Carlo on trade order, year-by-year stability.
6. **Pass criteria** (draft, to be agreed with you):
   - out-of-sample win rate ≥ 28% with 95% CI lower bound > break-even,
   - EV ≥ +0.10R after costs,
   - ≥ 500 out-of-sample trades,
   - profit factor ≥ 1.2,
   - positive in at least 2/3 of years and pairs.
7. **Forward test.** The same code runs live on an OANDA practice account for 3–6 months. Live fills are compared with what the backtest would have done on the same days: any slippage or fill-rate gap shows up here.

---

## 6. Candidate strategies (testing order)

| Priority | Strategy | Why |
|---|---|---|
| **1** | **Trend-continuation zone limit**: HTF bias → BOS → fresh imbalanced zone in discount/premium → limit → fixed 3R | Most-repeated model (30+ videos) and the most mechanical |
| 2 | **Liquidity-sweep reversal**: equal-high/low or swing sweep (wick) → LTF body-close BOS → limit at new zone → 3R | Second most-repeated; codable once equal highs/lows have a tolerance |
| 3 | **Asia-range session model**: London sweep of the Asia range → LTF BOS → target the other side, flat by 17:00 UK | Very mechanical; he gives explicit times |
| Filters | Premium/discount, liquidity veto, momentum (ATR-based), news/session windows, Fib 0.71–0.79 | Each must earn its place out-of-sample |

---

## 7. Infrastructure recommendation (internal, single user)

- **Compute.** This machine (4 cores, 15 GB RAM, 139 GB free) is enough for backtesting. 8 pairs × 15 years of M1 data is ~3–4 GB in Parquet. No cloud is needed for research.
- **Stack.** Python 3.12 managed by `uv`, pandas/NumPy + numba for the detectors, a custom event-driven backtester (rules this specific need exact control of intrabar fills; generic frameworks hide that), DuckDB + Parquet, pytest, and Jupyter or a static HTML report for results.
- **Version control.** Git, with every backtest run logged: config hash, data range, results.
- **Forward test and live.** OANDA v20 REST/stream API, running as a small long-lived service: this machine under `systemd`, or a ~$5–10/month VPS for 24/5 uptime. Telegram or email alerts. MT5 would only be needed if you want a specific MT5 broker or prop firm.
- **Security.** API keys in a local `.env`, never committed. Practice-account keys only until the pass criteria are met.

---

## 8. Risks / honest caveats
- **The edge may not exist.** Discretionary SMC/S&D methods often lose most of their apparent edge once made causal: no hindsight pivots, no cherry-picking. A negative result is a legitimate, valuable outcome of this project.
- **Rule drift.** Coding his rules necessarily fixes choices he leaves to judgement. We'll be testing *a* faithful version of his method, not *him*.
- **Regime dependence.** Must hold across 2010–2026 (low vol 2014, COVID, the 2022 USD trend).
- **Fixed 3R vs structural target.** The 30%/3R spec assumes a fixed target. His method uses structural targets. We test both, and the spec may have to be relaxed if structural targets do better.
