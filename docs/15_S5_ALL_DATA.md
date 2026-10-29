# 15 — S5 rules on all data, three markets, with and without costs (exploratory, 2026-10-29)

**What this is.** At the user's request, S5's 12 rules (13 §12) were run on **all available data, including the
out-of-sample years 2021–2026**. They ran on the NASDAQ 100 (2014–2026), gold (2014–2026) and GBPUSD (2010–2026),
once **with costs** (as frozen) and once **with zero costs**.

**Protocol note.** This opens the validation and hold-out years for opening-range rules on these three markets. Those
years can no longer give an unbiased test of ORB-type ideas there. These runs are exploration: they are not in the
run registry, and they do not change the S5 verdict (14). Logged in 03 §7.

**Method:**
- **With costs:** exactly the frozen engine (bid/ask fills, slippage, commission, the 10% cost limit).
- **Zero costs:**
  - fills and exits at the mid price;
  - no slippage, commission or stop overshoot;
  - the cost limit is therefore inactive, so **every day trades**.
- **Integrity:** run twice, identical on all three markets; data snapshot `e6a28e13`.

## Headline

| Market | With costs, 2021–2026 | Zero costs, all years | Zero costs, 2021–2026 | Realistic cost per trade (median) |
|---|---|---|---|---|
| **NASDAQ 100** | **+0.06 to +0.07R** (N 15/30, bias off; t 1.6–2.2) | **+0.05 to +0.12R, t 2.2–3.2** (bias off) | +0.06 to +0.14R | 0.12R to 2020, **0.04–0.05R since 2021** |
| **Gold** | −0.13 to +0.24R (small samples, none significant) | **+0.10 to +0.19R, t 3.3–4.3** | +0.02 to +0.13R | 0.27R to 2020, 0.11–0.16R since 2021 |
| **GBPUSD** | −0.05 to +0.40R (40–650 trades, none significant) | +0.00 to +0.06R, t 0.1–1.8 | −0.05 to +0.06R | 0.12–0.16R |

**Answer to "do the statistics change without costs?" Yes, sharply, for the NASDAQ 100 and gold:**
- **Gold** has a clear opening-range breakout effect before costs: every config is positive, with t up to 4.3. But
  costs (0.11–0.27R per trade) are larger than the effect (0.06–0.13R in recent years).
- **The NASDAQ 100** has a smaller effect before costs (+0.05 to +0.12R). In recent years index prices rose and the
  opening ranges widened, so costs shrank to about 0.04–0.05R per trade. **That is the first time in this project
  that a rule set stayed positive after costs out of sample**, at +0.06 to +0.07R.
- **GBPUSD** has no effect even with zero costs.

## NASDAQ 100 in detail

| Config | With costs: 2014–20 | 2021–23 | 2024–26 | 2021–26 trades, t | Zero costs: all years EV, t | Years > 0 (zero) |
|---|---|---|---|---|---|---|
| N 15, 3R, bias off | −0.019R | +0.095R | +0.026R | 1,394, t 1.7 | +0.067R, t 2.7 | 9/13 |
| N 15, close, bias off | −0.039R | +0.094R | +0.031R | 1,394, t 1.6 | +0.071R, t 2.6 | 11/13 |
| N 30, 3R, bias off | −0.065R | +0.093R | +0.043R | 1,379, t 2.2 | +0.047R, t 2.3 | 9/13 |
| N 30, close, bias off | −0.065R | +0.079R | +0.051R | 1,379, t 2.1 | +0.048R, t 2.2 | 10/13 |
| N 5, close, bias off | −0.073R | +0.083R | +0.041R | 1,213, t 1.1 | **+0.118R, t 3.2** | 10/13 |
| N 15, 3R, bias on | −0.027R | +0.036R | +0.042R | 986, t 0.9 | +0.059R, t 2.0 | **13/13** |

The H4 bias again lowers EV in most configs. It does make one config steadier (13 of 13 positive years at zero cost)
with a smaller average.

## Why this is still not a GO

1. **Below the bar.** The best out-of-sample result after costs is +0.069R. The pass rule (03 §5 P2) needs ≥ +0.10R,
   and your target of 30% at 1:3 is +0.20R. Even with zero costs, no market reaches +0.20R out of sample.
2. **Chosen after looking.** These configs were picked after seeing 2021–2026, across 72 views (12 configs × 3 markets
   × 2 cost cases), on top of 259 earlier trials. A t of 2.2 is what the best of many tries often shows by chance.
   The Deflated Sharpe test (P7) would not pass.
3. **It flipped.** NASDAQ was negative in 2014–2020 with costs and positive after. That fits the cost story, since
   ranges widened relative to spreads. It also fits luck.
4. **Zero cost is not tradeable.** It shows the market's behaviour, not a result anyone can trade.

## What it does tell us

- **The opening-range effect is real** on the NASDAQ 100 and on gold, of the size the QQQ paper reported before costs
  (about +0.1R per trade). It is absent on GBPUSD.
- **Costs decide everything.** The edge is about 0.1R per trade. Only cheap execution relative to the stop (wide
  ranges, low spreads) keeps any of it.
- **The useful next question is costs, not rules:**
  - Can you trade the NASDAQ 100 or gold with a smaller spread and commission than Dukascopy's CFDs (for example a
    futures broker, if one serves Kenya)?
  - Could a 2027+ forward test, on data nobody has seen, confirm the NASDAQ result?

Files (local, not committed): the scratchpad runs `s5_all_1`/`s5_all_2` and `s5_all_stats.txt`.

Follow-up on venues: 16 (cheaper execution).
