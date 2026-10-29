# 17 — NASDAQ 100 opening-range rules at micro-futures costs, full engine, 2014–2026 (exploratory, 2026-10-29)

**Question.** The NASDAQ 100 is the only market left with a candidate edge (16). How strong is it when the full engine
runs every S5 config on all data at MNQ micro-futures costs, and judged by tests that do not depend on picking the
best config after looking? Not registered; the 2021–2026 years were already opened (15).

**Setup.** S5 rules unchanged (13). Quotes are the Dukascopy mid M1 ± 0.425 pt: a 1-tick spread (0.25 pt) plus the
MNQ commission (2 × 0.30 pt) folded in, so a round trip costs 1.35 pt with 1-tick stop slippage, 1.85 pt with 2 ticks.
Stop overshoot rule and the 10% cost rule as frozen. Run twice: logs, trades (50,256 rows) and statistics identical.
Scripts: scratchpad `s5_mnq.py`, `s5_mnq_stats.py`.

## Results, 1-tick slippage

| Config | Trades | Win | EV | t | 2014–20 | 2021–23 | 2024–26 | Years > 0 | R per year |
|---|---|---|---|---|---|---|---|---|---|
| N 5, close | 2,229 | 29% | **+0.081R** | 1.9 | +0.040 | +0.137 | +0.068 | 10/13 | +13.9 |
| N 5, close, H4 | 1,789 | 30% | +0.070R | 1.5 | +0.048 | +0.071 | +0.095 | 9/13 | +9.7 |
| N 15, 3R | 2,731 | 40% | +0.039R | 1.5 | −0.015 | +0.115 | +0.059 | 8/13 | +8.2 |
| N 15, close | 2,731 | 39% | +0.036R | 1.3 | −0.020 | +0.114 | +0.058 | 8/13 | +7.6 |
| N 30, 3R | 2,885 | 44% | +0.020R | 1.0 | −0.049 | +0.116 | +0.071 | 8/13 | +4.5 |
| other 7 configs | | | +0.004 to +0.040R | 0.2–1.2 | | | | 3–9/13 | |

With 2-tick slippage every config loses about 0.01R (best +0.068R, t 1.5).

## Tests that do not depend on picking after looking

| Test | Result |
|---|---|
| **All 12 configs averaged** (no selection) | 2014–20 **−0.012R**, 2021–23 +0.081R, 2024–26 +0.064R |
| **Walk-forward selection**: each year, trade the config with the best EV in all earlier years | 2016–26: 1,954 trades, **+0.054R, t 1.2**; 2016–20 +0.017R; 2021–26 +0.071R (t 1.3). Losing years: 2020, 2022, 2026 |
| **Deflated Sharpe** (379 trials: 259 registered + 120 exploration views) | best config, all years: 0.63; walk-forward: **0.41**. N 30/3R on 2021–26 alone: 0.97, but that period and config were chosen after looking. A pass needs ≥ 0.95 on an honest sample |
| **Longs vs shorts** (bias off, 2021–26) | both positive (longs +0.08…+0.15R, shorts +0.02…+0.09R), so it is not only the 2021–26 uptrend |
| **Monte Carlo** (walk-forward trades, 230 a year, 5 years) | median **+11.6R a year**, 5–95%: −34R to +61R; **a losing year 35% of the time**; 5-year max drawdown median 52R (95%: 101R); longest losing run median 17 (95%: 24) |

## Verdict: still not a system

- **The effect appeared after 2020.** Averaged over all configs it was about zero in 2014–2020 at futures cost, and
  about +0.07R since. That may be a lasting change (higher volatility, wider opening ranges) or a regime that ends.
- **Picking a config with only past data gives +0.05R, t 1.2.** That is the honest estimate, and it is not
  significantly different from zero. The Deflated Sharpe test fails (0.41).
- **It is far from 23R a year with comfort.** The median is about +12R a year, with a one-in-three chance of a losing
  year and drawdowns around 50R. At 0.5% risk per trade that is a 25% drawdown; at 1%, 50%.
- **N 5, close has your shape** (29% winners, a few large ones held to the close), but +0.08R, not +0.20R.

**What would change the verdict:** only data nobody has seen, and a forward test cannot settle an edge this small
quickly. Trade results scatter widely (standard deviation about 1.4R per trade at N 15, 3R; about 2R for the
hold-to-close configs). To show +0.05R at t = 2 needs (2 × 1.4 / 0.05)² ≈ 3,100 trades: **about 13 years** at 230 a
year. Even a true +0.10R needs about 3–4 years. A forward test can still catch a clear failure, and check real fills,
but it cannot prove this edge in a useful time.
