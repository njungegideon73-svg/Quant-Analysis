# 08 — S2 result: NO-GO at M4 (2026-10-29)

**Verdict.** S2 (liquidity-sweep reversal, 06 + §11: M15 sweep of equal highs/lows, M1 reversal BOS and zone,
limit, stop beyond the sweep, 3R) has **no edge** on 2010–2019. **It loses even before costs.** It stops here,
before validation; 2020–2026 is still unseen.

## What was tested

- The 4 frozen configs (W ∈ {8, 24} × entry at the zone edge or middle), 7 pairs, all costs, M1 fills.
  Trial count now **227**.
- 755–935 trades per config, so the sample is large enough; the problem is the result, not the count.

## Results

| Config | Trades | Win rate | EV / trade | t | 95% bootstrap CI |
|---|---|---|---|---|---|
| W 8, edge | 879 | 29.4% | −0.057R | −1.1 | −0.15 … +0.06 |
| W 8, middle | 755 | 28.9% | −0.088R | −1.5 | −0.20 … +0.02 |
| W 24, edge | 935 | 29.7% | −0.051R | −1.0 | −0.16 … +0.05 |
| W 24, middle | 804 | 29.4% | −0.074R | −1.3 | −0.18 … +0.04 |

No config has EV > 0, so none is eligible (03 §4). Walk-forward: 128 test trades, −0.12R.

## What broke

| # | Finding | Evidence (W 24, edge, the best config) |
|---|---|---|
| 1 | **The win rate looks on target, but the wins are not 3R.** | 29.7% of trades end positive, but only 19.4% reach the 3R target. Another 15% are closed by the Friday flatten at +0.46R on average. |
| 2 | **No edge before costs.** | Price-only result (no spread, commission, slip or swap): −0.016R per trade. Costs take a further 0.035R. |
| 3 | **Not a cost or stop-size problem.** | Median stop 22 pips (10th percentile 16): costs are small relative to the stop. |
| 4 | **Unstable across years.** | Positive only in 2014, 2016 and 2019 (+0.03 … +0.28R); 2010–2013, 2015 and 2017 are −0.05 … −0.22R. |
| 5 | **No pair carries it.** | Only USDCAD (+0.03R) is above zero; NZDUSD −0.18R, AUDUSD −0.12R. |

## Why the drafted M15 entry was not tested

Count check (06 §10): ≤ 217 trades in 10 years, below the 300 minimum. It could not pass at any win rate, so the
M1 entry (§11) was frozen instead, before any result was seen.

## What carries over to S3

- Engine, data, protocol: unchanged. M1-resolution orders (`fill_min` / `place_ns` in the episodes) are now supported.
- Hypotheses only (not used to tune S3):
  - a 3R target held to the end is reached only ~19% of the time in both S1 and S2;
  - the Friday flatten turns many trades into small wins.

Files: `reports/m4_s2.csv`, `reports/m4_s2_walk_forward.csv` (local), runs `20261029-022030-*`.
