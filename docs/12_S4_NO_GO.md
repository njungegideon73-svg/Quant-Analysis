# 12 — S4 result: NO-GO at M4 (2026-10-29)

**Verdict.** S4 (London breakout of the Asia range with the H4 trend, retest entry, flat 17:00 UK, 11) **loses with
statistical confidence** on 2010–2019. All 12 configs are negative, with t from −3.9 to −4.7. No config is eligible,
so the walk-forward has nothing to test. S4 stops here, before validation, and 2020–2026 is still unseen.
**The H1 confirmation step makes it worse, not better.**

## What was tested

- **Grid:** the 12 frozen configs (target T1/time × `b` 0.1/0.25/0.5 × H1 off/on, retest entry).
- **Setup:** 7 pairs, all costs, M1 fills, 10-pip minimum stop. The trial count is now **247**.
- **Size:** 3,535–4,575 trades per config. The median stop is 27–30 pips.
- **Integrity:** the grid was run twice, and all 12 configs matched trade for trade (runs `20261029-1258*` and
  `-1301*`). Before the runs, the data check caught one corrupted cached month (EURUSD 2022-05; the disk copy was
  correct). The month was evicted from the cache and the snapshot re-verified as `0ce189aa`.

## Results

| Config | Trades | Win rate | Reach 3R | EV / trade | t | 95% bootstrap CI | Before costs |
|---|---|---|---|---|---|---|---|
| T1, b 0.25, H1 off (best) | 4,575 | 38.6% | 7.1% | −0.073R | −4.0 | −0.11 … −0.04 | −0.045R |
| T1, b 0.5, H1 off | 4,574 | 39.5% | 6.0% | −0.074R | −4.2 | −0.11 … −0.04 | −0.047R |
| T1, b 0.1, H1 off | 4,574 | 38.2% | 7.3% | −0.075R | −4.1 | −0.11 … −0.04 | −0.046R |
| time, b 0.5, H1 off | 4,569 | 39.1% | – | −0.075R | −4.1 | −0.11 … −0.04 | −0.049R |
| time, b 0.1, H1 off | 4,562 | 37.7% | – | −0.076R | −3.9 | −0.11 … −0.04 | −0.047R |
| time, b 0.25, H1 off | 4,566 | 38.2% | – | −0.077R | −4.0 | −0.11 … −0.04 | −0.049R |
| time, b 0.5, H1 on | 3,542 | 39.1% | – | −0.086R | −4.2 | −0.12 … −0.05 | −0.060R |
| T1, b 0.25, H1 on | 3,540 | 38.6% | 6.5% | −0.087R | −4.3 | −0.13 … −0.05 | −0.059R |
| T1, b 0.5, H1 on | 3,543 | 39.3% | 5.6% | −0.087R | −4.5 | −0.12 … −0.05 | −0.061R |
| time, b 0.25, H1 on | 3,538 | 38.4% | – | −0.087R | −4.1 | −0.13 … −0.04 | −0.060R |
| time, b 0.1, H1 on | 3,535 | 37.7% | – | −0.093R | −4.3 | −0.14 … −0.05 | −0.065R |
| T1, b 0.1, H1 on | 3,539 | 38.0% | 6.7% | −0.096R | −4.7 | −0.13 … −0.06 | −0.067R |

"Win rate" counts every trade closed in profit, including small gains at the 17:00 exit.

## What broke (T1, b 0.25, H1 off, unless stated)

| # | Finding | Evidence |
|---|---|---|
| 1 | **No edge before costs.** | Price-only EV is −0.045R. With stops this wide (median 28 pips), costs are small (0.028R per trade) and are not the cause. |
| 2 | **Breakouts rarely run to 3R within the day.** | Only 7% reach 3R. The median best excursion is +0.66R. 46% are flat at 17:00 (average +0.46R) and 47% are stopped (−1.05R). |
| 3 | **Removing the target does not help.** | With `time`, 53% are flat at 17:00 (average +0.80R), but that does not cover the 47% stopped. EV −0.077R. |
| 4 | **H1 confirmation removes good trades with the bad.** | It keeps 77% of the trades, and every H1-on config is worse than its H1-off twin (−0.010 to −0.021R). |
| 5 | **Nearly every year and pair loses.** | 2016 is the only positive year (+0.02R). USDJPY is the only positive pair (+0.02R, not significant); the other six run from −0.05 to −0.14R. |
| 6 | **The stop buffer does not matter.** | `b` 0.1/0.25/0.5 move EV by ≤ 0.003R. The result does not hinge on one parameter. |

## Where the four strategies leave us

S1–S4 together: **247 configs and about 154,000 research trades**. None has a positive, stable edge after costs.
- S3 faded the London break of Asia and lost before costs (−0.14R).
- S4 traded with the same break and also lost before costs (−0.05R).

Both directions of the session break fail, which points to no exploitable pattern there for these rules on these
pairs. The user's top-down filter (H4 bias, then H1 confirmation) was tested directly in S4 and did not add edge.

These results do not show that discretionary trading of the same ideas cannot work. They show that the objective
versions tested here do not reach 30% wins at 1:3 with realistic costs on the 7 majors.

Files: `reports/m4_s4.csv` and `reports/m4_s4_walk_forward.csv` (local), runs `20261029-1258*` and `-1301*`.
