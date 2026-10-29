# 14 — S5 result: NO-GO at M4 (2026-10-29)

**Verdict.** S5 (US open range breakout on the NASDAQ 100 CFD, flat 15:55 ET, 13 §12) has **no edge** on 2014–2020.
- All 12 configs are negative after costs, from −0.019R to −0.141R per trade.
- None is significant on its own (t −0.4 to −1.8).
- No config is eligible, so the walk-forward has nothing to test.

Unlike S2–S4, this is not a confident loss. It is a result indistinguishable from zero or slightly below. S5 stops
here, before validation, and 2021–2026 is still unseen.

## What was tested

- **Grid:** the 12 frozen configs: N {5, 15, 30} × target {3R, close} × H4 bias {off, on}.
- **Setup:** 10% cost limit, M1 bid/ask fills, stop orders with slippage. The trial count is now **259**.
- **Size:** 249–919 trades per config. The median stop is 38–42 points.
- **Integrity:** the grid was run twice and all 12 configs matched trade for trade (runs `20261029-1438*` and
  `-1439*`). Data snapshot `e6a28e13`.

## Results

| Config | Trades | Win rate | Reach 3R | EV / trade | t | 95% bootstrap CI | Before costs | Years > 0 |
|---|---|---|---|---|---|---|---|---|
| N 15, 3R, bias off (best) | 704 | 38.4% | 7.7% | −0.019R | −0.4 | −0.11 … +0.08 | −0.006R | 3/7 |
| N 15, 3R, bias on | 473 | 40.2% | 7.4% | −0.027R | −0.5 | −0.14 … +0.09 | −0.014R | 2/7 |
| N 15, close, bias off | 704 | 37.9% | – | −0.039R | −0.8 | −0.14 … +0.06 | −0.026R | 1/7 |
| N 15, close, bias on | 473 | 39.7% | – | −0.055R | −0.9 | −0.17 … +0.07 | −0.042R | 1/7 |
| N 30, close, bias on | 555 | 42.3% | – | −0.057R | −1.2 | −0.15 … +0.04 | −0.045R | 1/7 |
| N 30, 3R, bias off | 919 | 41.0% | 2.9% | −0.065R | −1.8 | −0.14 … +0.00 | −0.054R | 0/7 |
| N 30, close, bias off | 919 | 41.0% | – | −0.065R | −1.8 | −0.13 … +0.01 | −0.054R | 0/7 |
| N 30, 3R, bias on | 555 | 42.3% | 3.1% | −0.071R | −1.6 | −0.16 … +0.02 | −0.059R | 1/7 |
| N 5, close, bias off | 324 | 26.5% | – | −0.073R | −0.7 | −0.26 … +0.12 | −0.058R | 3/7 |
| N 5, 3R, bias off | 324 | 27.8% | 15.1% | −0.118R | −1.4 | −0.29 … +0.05 | −0.103R | 3/7 |
| N 5, 3R, bias on | 249 | 29.3% | 12.4% | −0.133R | −1.4 | −0.32 … +0.05 | −0.117R | 1/7 |
| N 5, close, bias on | 249 | 28.9% | – | −0.141R | −1.4 | −0.33 … +0.07 | −0.126R | 1/7 |

## What broke

| # | Finding | Evidence |
|---|---|---|
| 1 | **No edge before costs.** | Price-only EV runs from −0.006R to −0.126R. On the days the cost rule allows, costs are small (0.011–0.015R) and are not the cause. |
| 2 | **Breakouts rarely run to 3R.** | N 30: only 3% reach 3R and the median best excursion is +0.59R. 60% end flat at 15:55 (+0.58R average), and 40% are stopped (−1.03R). |
| 3 | **The 5-minute range (the published one) is the worst.** | EV −0.07 to −0.14R; it reaches 3R more often (12–15%), but loses more often too. |
| 4 | **The H4 bias does not help.** | Bias on is worse in 5 of 6 pairs of configs, as H1 was in S4. |
| 5 | **Trades bunch in volatile years.** | The 10% cost rule passes mostly large-range days: N 15 has 19 trades in 2014 and 230 in 2020. The only clearly positive year (2014, +0.70R) rests on 19 trades. |

**One caveat.** The cost rule limits the test to days with a large opening range (a round trip costs about 2.5 points, so
the range must be at least 25 points). The published ORB results covered all days. On ordinary days, Dukascopy CFD costs
would take more than 10% of the risk, and the QQQ replication already found that costs erase the edge there.

## Where five strategies leave us

S1–S5 together: **259 configs and about 160,000 research trades** on 7 FX majors and the NASDAQ 100. None has a
positive, stable edge after costs.
- S2, S3 and S4 lost with confidence.
- S1 and S5 were close to zero, and not significantly different from it.

The user's H4 bias, and in S4 the H1 confirmation, never improved a strategy. The evidence says the intraday
pattern rules tested here, at retail CFD costs, do not reach 30% wins at 1:3.

Files: `reports/m4_s5_USATECHIDXUSD.csv` and `reports/m4_s5_USATECHIDXUSD_walk_forward.csv` (local), runs
`20261029-1438*` and `-1439*`.
