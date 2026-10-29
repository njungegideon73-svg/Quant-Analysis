# 07 — S1 result: NO-GO at M4 (2026-10-29)

**Verdict.** S1 (trend-continuation zone limit, 01) has **no edge we can trust** on 2010–2019. It stops here, before
validation: 2020–2026 has not been looked at, so it stays a clean test for S2 and S3.

## What was tested

- 216 Stage A configs (03 §3) on 7 pairs, 2010–2019, 92,223 trades, all costs, stop-spike slippage, M1 fills.
- 7 Stage B filter flips from the one eligible config. Trial count: **223**.
- Engine checked three ways first (hand audit 20/20, random-entry control, Dukascopy's tester), so the result is
  about the strategy, not the simulator.

## What broke, and where

| # | Finding | Evidence |
|---|---|---|
| 1 | **Most of the grid loses.** | 163/216 configs EV < 0; median −0.10R per trade; the default config −0.11R (25.6% wins, PF 0.86, 1/7 pairs positive). |
| 2 | **Entering at the zone's near edge is the main loser.** | Median config EV −0.13R at the near edge vs −0.01R at the zone midpoint. The first touch of a fresh zone does not hold often enough to pay 3R. |
| 3 | **The best region is thin and not significant.** | Only one config passed 03 §4 (N=5, m=1.5, b=0.2, K=96, mid, T1): 472 trades, 31.1% wins, +0.098R, t = 1.2, bootstrap 95% CI −0.07R … +0.26R. With 216 configs tried, one result like this is expected by luck. |
| 4 | **It fades in recent years.** | That config: 2011 +0.48R, 2015–16 ≈ +0.25R, 2017 −0.03R, 2018 −0.24R, 2019 −0.88R. Every Stage B variant is negative over 2017–19 (−0.13R to −0.88R). |
| 5 | **The selection procedure finds nothing out of sample.** | Walk-forward (03 §2): an eligible config existed in 2 of 6 folds (T1) and 1 of 6 (T2); none from 2016 on. |
| 6 | **More trades means worse trades.** | `min_stop_mode = widen` (keep zones with stops under 15 pips, widened to 15) gives 2,191 trades but EV −0.078R, t = −2.2: the small-stop setups lose with statistical confidence. |
| 7 | **Structural targets look good only on tiny samples.** | Best T2 configs +0.36 … +0.55R on 91–154 trades each, below the 300-trade minimum; none eligible. |
| 8 | **Filters do not rescue it.** | Stage B: `liq_veto` is the only flip that meets the adoption rule (EV +0.122R, 438 trades), but t = 1.4, the CI still includes zero and 2017–19 is −0.24R. `htf_location` and `session=all` are worse; `k=0.5` changes nothing at N=5. |

## Why not send the `liq_veto` variant to validation anyway

A strict reading of 03 §3–4 would allow it as a candidate. It is not sent, because it cannot pass:

- **P3 (≥ 500 out-of-sample trades):** it takes ~44 trades a year, and ~20 a year in 2017–19, so 2020–2026 would give
  roughly 150–300. At best INCONCLUSIVE.
- **P7 (Deflated Sharpe ≥ 0.95 with 223 trials):** needs t well above 3 on its own; it has 1.4.
- Spending a validation run on it would leak 2020–2023 for nothing.

## What carries over to S2 / S3

- Data (checksummed), engine, cost model, cross-checks, registry and protocol: all reused unchanged.
- Lessons, as hypotheses only (not used to tune S2):
  - first-touch near-edge limits had poor follow-through;
  - setups needing a stop under 15 pips were net losers;
  - results weakened after 2016 across the board.

Files: `reports/m4_stage_a.csv`, `reports/m4_walk_forward.csv`, `reports/m4_stage_b.csv`,
`reports/m4_pick_T1_report.html` (local; `reports/` is not in git).
