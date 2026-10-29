# 10 — S3 result: NO-GO at M4 (2026-10-29)

**Verdict.** S3 (Asia-range sweep, London reversal, 09) **loses with statistical confidence** on 2010–2019:
all 8 configs are negative with t from −2.7 to −6.0. It stops here, before validation; 2020–2026 is still unseen.
**With S2 also NO-GO, the stop rule (README §3) applies:** no more variants; we discuss a different approach.

## What was tested

- The 8 frozen configs (W ∈ {4, 8} × entry edge/middle × T1/Tasia), 7 pairs, all costs, M1 fills, 5-pip minimum
  stop, flat 17:00 UK. Trial count now **235**.
- 677–2,087 trades per config.
- **Integrity:** this machine has faulty RAM (bit flips seen in cached files and pointers). The grid was run twice
  and all 8 configs matched trade for trade. Re-running the S1 Stage A pick, the S1 default config and the best S2
  config reproduced their stored runs exactly.

## Results

| Config | Trades | Win rate | EV / trade | t | 95% bootstrap CI | Pairs > 0 |
|---|---|---|---|---|---|---|
| W 8, edge, T1 (best) | 2,087 | 25.2% | −0.213R | −6.0 | −0.28 … −0.14 | 0/7 |
| W 4, edge, T1 | 1,852 | 24.5% | −0.218R | −5.7 | −0.29 … −0.14 | 0/7 |
| W 8, mid, T1 | 1,783 | 24.8% | −0.218R | −5.7 | −0.29 … −0.14 | 0/7 |
| W 4, mid, T1 | 1,578 | 24.1% | −0.227R | −5.5 | −0.30 … −0.15 | 0/7 |
| W 4, mid, Tasia | 677 | 18.8% | −0.217R | −2.7 | −0.37 … −0.07 | 1/7 |
| W 8, mid, Tasia | 717 | 18.7% | −0.221R | −2.9 | −0.37 … −0.07 | 1/7 |
| W 8, edge, Tasia | 800 | 18.6% | −0.251R | −3.6 | −0.39 … −0.11 | 1/7 |
| W 4, edge, Tasia | 753 | 18.6% | −0.253R | −3.5 | −0.40 … −0.10 | 1/7 |

## What broke

| # | Finding | Evidence (W 8, edge, T1) |
|---|---|---|
| 1 | **Worse than random before costs.** | Price-only EV −0.136R. With a 3R target, random entries would land near 0R before costs; fading the Asia sweep is on the wrong side more often than chance. |
| 2 | **Costs add to it but are not the cause.** | 0.077R per trade (median stop 9.6 pips). Stops average −1.13R: small stops pay proportionally more slippage. |
| 3 | **Smaller stops are worse.** | Pre-cost EV by stop size: −0.23R under 8 pips, −0.10R at 8–20 pips, −0.01R above 20 pips. |
| 4 | **Every year loses.** | −0.02R (2015) to −0.41R (2019); no pair is positive. |
| 5 | **The 17:00 exit worked as intended, but the trades did not.** | Only 7% of trades were cut at 17:00 (+0.76R average); 73% hit the stop first. |
| 6 | **The Asia target does not rescue it.** | Targets hit pay +4.1R, but only 15% reach them; EV −0.25R. |

## Where the three strategies leave us

S1, S2 and S3 together: 235 configs and ~105,000 research trades. None has a positive, stable edge after costs. The
best results were near zero before costs (S1 pick +0.10R on 472 trades, not significant; S2 −0.02R; S3 −0.14R).
These are faithful, objective versions of JeaFx's three most-repeated models. On this evidence they do not
deliver 30% wins at 1:3 on the 7 majors with realistic costs.

Files: `reports/m4_s3.csv`, `reports/m4_s3_walk_forward.csv` (local), runs `20261029-0310*` and `-0316*`.
