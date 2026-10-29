# 03 — Validation Protocol & Pass Criteria

This document is **frozen before the first S1 backtest**. Changes after that are logged at the bottom with a date and reason, and they count against the trial budget.

## 1. Data splits

| Period | Role | Access |
|---|---|---|
| 2010-01-01 → 2019-12-31 | **Research.** Tuning, diagnostics, internal walk-forward | Unlimited |
| 2020-01-01 → 2023-12-31 | **Validation.** Only frozen candidates (max 3) | One run per candidate |
| 2024-01-01 → latest | **Hold-out.** Final confirmation | **Opened once**, for the final candidate only |

Enforced in code (`ta.backtest.load`, `ta.registry.guard`). A run only loads data up to its period's end, so a research run cannot see 2020+. Earlier data is loaded as warm-up, and only zones created inside the period count. Validation refuses a config that already has a validation row, or a 4th candidate. The hold-out needs `--unlock-holdout` and refuses once any hold-out row exists.

"Out-of-sample" (OOS) below means validation + hold-out (2020 → latest).

## 2. Internal walk-forward (inside 2010–2019)

The goal is to check that the *selection procedure* works, not just one config.

- Rolling folds: train 4 years → test the next 1 year, for test years 2014 … 2019 (6 folds).
- In each fold, choose a config by the §4 rule on the train window only, then record its test-year trades.
- Concatenated walk-forward test trades must have **EV > 0 net**. Otherwise the procedure is unreliable, and S1 goes to NO-GO without touching the validation data.

## 3. Declared parameter grid

**Stage A (core grid, 216 configs).** The filters stay at their defaults.

| Param | Values |
|---|---|
| `N` (M15 pivot) | 2, 3, 5 |
| `m` (impulse body, ×ATR) | 1.0, 1.5 |
| `b` (stop buffer, ×ATR) | 0.05, 0.10, 0.20 |
| `K` (zone expiry, M15 bars) | 48, 96, 192 |
| `entry_at` | proximal, mid |
| `target` | T1 fixed 3R, T2 structural ≥3R |

Fixed in Stage A: `zone_pick=newest`, `min_stop_mode=skip`, `liq_veto=off`, `session=london_ny`, `zone_body=off`, `htf_location=off`, `k=0`.

**Stage B (one-at-a-time filter tests, ≤ 14 configs).** Starting from the Stage A pick for each target type, flip each of `zone_pick`, `min_stop_mode`, `liq_veto`, `session`, `zone_body`, `htf_location` and `k∈{0.5}`, one at a time. A filter is adopted only if it improves EV **and** does not drop the trade count by more than 40%.

**Trial budget:** ≤ 250 configs **per strategy** (changed 2026-10-29, see change log; was 250 in total). The Deflated Sharpe Ratio always uses the **running total across all strategies**, so a later strategy is judged against every config tried before it. Every run is logged in `runs/registry.csv` (`ta runs` prints the count of distinct configs), and the count feeds the Deflated Sharpe Ratio (§5).

## 4. Candidate selection rule (no "best cell" picking)

1. Results are computed per config on 2010–2019, all 7 pairs pooled.
2. **Neighbourhood score** = the median EV of the config and its immediate grid neighbours (±1 step in each numeric param).
3. Eligible configs: all neighbours EV > 0, ≥ 300 research trades, and positive on ≥ 5/7 pairs.
4. Pick the highest neighbourhood score **separately for T1 and T2**. An optional third candidate is the best Stage B variant.
5. Freeze the candidates (config hash recorded) before the validation run.

## 5. Statistics & pass criteria (GO requires all)

| # | Criterion | Measured on |
|---|---|---|
| P1 | **Win rate ≥ 28%** (spec target 30%), and the Wilson 95% lower bound > the realised break-even WR (`avg_loss/(avg_win+avg_loss)`, net R) | OOS, T1 |
| P1′ | For T2: the bootstrap 95% lower bound of mean net R > 0 | OOS, T2 |
| P2 | **EV ≥ +0.10R per trade, net of all costs** | OOS |
| P3 | **≥ 500 OOS trades** | OOS |
| P4 | **Profit factor ≥ 1.2** | OOS |
| P5 | Positive in ≥ 2/3 of calendar years **and** ≥ 5/7 pairs | OOS |
| P6 | EV > 0 with spread and slippage ×2 | OOS |
| P7 | Deflated Sharpe Ratio probability ≥ 0.95, using the registry's trial count | OOS |
| P8 | Hold-out EV > 0, and inside the validation EV's 95% CI (no collapse) | Hold-out |
| P9 | Max drawdown ≤ the 95th percentile of the Monte Carlo drawdown | OOS |

Methods:
- **Bootstrap.** 10,000 resamples with blocks = calendar weeks, which keeps clustered trades together.
- **Wilson** interval for the win rate.
- **Monte Carlo.** Bootstrap OOS trades into 10,000 paths of the expected 12-month trade count. Outputs: the drawdown and losing-streak distributions, and the 5–95% cumulative-R band. These numbers become the live halt thresholds ([04 §3](04_EXECUTION_AND_INFRA.md)).

**Outcomes:**
- **GO:** all criteria pass.
- **INCONCLUSIVE:** everything passes except P3 (too few trades). Extend the forward test and/or add pairs; no live money yet.
- **NO-GO:** any other failure. Write a diagnostic report on what broke and where, then move to S2. The parameters are not re-tuned on OOS data.

## 6. Forward test (M6, Dukascopy JForex demo, ≥ 3 months)

The forward test checks **implementation and execution**. In 3 months it **cannot** prove the edge statistically (for that, see P3).

| Check | Pass |
|---|---|
| Signal parity: replay the backtester over the same live period | ≥ 95% of setups identical (zone, entry/stop/target within ±0.1 pip) |
| Fill-rate parity | Live limit fill rate within ±10 percentage points of the simulated rate |
| Stop slippage | Average ≤ 2× the model `slip` |
| Safety | 100% of positions carry broker-side SL and TP; zero unhandled exceptions; reconnect/restart tested |
| Performance sanity | Cumulative R inside the Monte Carlo 5–95% band for the number of trades taken |

## 7. Change log
| Date | Change | Reason | Trials added |
|---|---|---|---|
| 2026-10-27 | Initial version | — | 0 |
| 2026-10-27 | Broker OANDA → Pepperstone cTrader demo; data → Dukascopy | OANDA unavailable in Kenya | 0 |
| 2026-10-27 | Forward-test venue → Dukascopy JForex demo (same feed as backtest); live venue decided at M7 | User installed JForex4 with a demo account | 0 |
| 2026-10-27 | Zone FVG window `[j−1, t_b]` → `[j−1, t_b+1]`; zone created at `t_b+1` when only that bar completes the gap | M2 detector diagnostics (zone counts only, no P&L seen): 34% of BOS could never form a zone because the impulse candle was the BOS candle. Clarification of the JeaFx rule, not a tuned parameter | 0 |
| 2026-10-27 | Zone candle steps back past rally candles (body ≥ 0.5·ATR); zone needs an open range ≥ 0.1·ATR after the impulse (no retest) | Faithfulness review round 1 ([05](05_FAITHFULNESS_REVIEW.md)), checked against JeaFx's own definitions. Charts only, no P&L seen. Thresholds fixed, not gridded | 0 |
| 2026-10-27 | Open-range minimum 0.1 → 0.3·ATR | Faithfulness review round 2 ([05](05_FAITHFULNESS_REVIEW.md)): sub-0.3·ATR gaps (≤ 2 pips) are not a visible imbalance; applies the reviewer's rejections consistently. Charts only, no P&L seen | 0 |
| 2026-10-27 | M3 engine clarifications: holiday blackout; order geometry fixed at zone creation; T2 ≥3R as a re-checked condition; a cancelled order ends the zone; blocked zones placed at the close of the exit bar | Needed to make docs/01 §5–§8 executable. Decided before any S1 result was looked at (the M3 runs printed counts only) | 0 |
| 2026-10-27 | Run registry is `runs/registry.csv` (append-only) instead of DuckDB | Same content, no extra dependency; DuckDB can still query the CSV. The M3 smoke run is backfilled as trial 1 | 0 |
| 2026-10-27 | Period splits enforced in code; Stage A grid runner (`ta grid`) | docs/03 §1 access rules made mechanical. Grid timing measured with results discarded unseen (no trial used) | 0 |
| 2026-10-29 | Stop slippage: a stop hit inside a minute also pays 0.10 × the minute's overshoot past the stop | Calibrated on 100 stop-outs replayed tick by tick in Dukascopy's tester (engine was better than the tester on 31/95 stops; now 13/95). Cost model; decided from fills only, before any S1 result | 0 |
| 2026-10-29 | Zone = zone candle + next candle's wick; stop, discount EQ and equal-lows veto use the leg's origin swing | Closes docs/05 open issue #28/#29: the origin extension widened 70% of zones (×1.76 median). JeaFx draws one candle and puts his usual stop beyond the swing. Decided from transcripts and zone geometry only | 0 |
| 2026-10-29 | Walk-forward folds apply the §4 rule with the trade minimum pro rata to the 4-year train window (120 instead of 300); neighbours are ±1 step in N, m, b, K with the same entry_at and target, and a neighbour with no trades counts as not EV > 0 | §2/§4 did not say. Fixed in code (`ta m4`) before the first M4 result was computed | 0 |
| 2026-10-29 | S1 Stage B: 7 filter flips from the Stage A T1 pick (no T2 pick existed). S1 declared NO-GO at M4 (docs/07); no validation run | Run as declared in §3 | 7 (total 223) |
| 2026-10-29 | Trial budget 250 per strategy (was 250 total); P7 uses the running total across S1–S3 | S1 used 223, leaving S2 27 and S3 none. Counting every trial in the DSR keeps the change honest: later strategies face a stricter bar. Decided before any S2 run | 0 |
| 2026-10-29 | S2 frozen (docs/06 + §11): entry on M1 after the M15 sweep; grid of 4 (W × entry_at, T1, no H4 filter) | The drafted M15 entry gave ≤ 217 trades in 10 years (counts only), below the §4 minimum. JeaFx takes the entry on the 1–2 minute chart. `htf` and T2 were dropped on trade counts, not results | 0 |
| 2026-10-29 | S2 research grid (4 configs) and M4: NO-GO, no config EV > 0 (best −0.051R, 935 trades), price-only −0.016R. See docs/08 | Stop rule (README §3): S3 is the last strategy before a change of approach | 4 (total 227) |
| 2026-10-29 | S3 frozen (docs/09): Asia sweep + M1 entry, 5-pip minimum stop, flat 17:00 UK; grid of 8 (W × entry_at × T1/Tasia) | At 15 pips no config could reach P3 (counts only, §7). Last strategy under the stop rule | 0 |
| 2026-10-29 | S3 research grid (8 configs, run twice: identical) and M4: NO-GO, all configs EV −0.21 … −0.25R, t −2.7 … −6.0. See docs/10 | S2 and S3 both NO-GO: the stop rule (README §3) ends this line of strategies | 8 (total 235) |
| 2026-10-29 | S4 frozen (docs/11 §12): London breakout of Asia with the H4 bias, retest entry, stop beyond the Asia range, flat 17:00 UK; grid of 12 (target × b × H1 on/off) | User chose to continue with a breakout test after the stop rule (docs/10). Idea partly suggested by S3's research result: the DSR counts all earlier trials. Rules passed a blind chart review (24/29) | 0 |
| 2026-10-29 | S4 research grid (12 configs, run twice: identical) and M4: NO-GO, all configs EV −0.073 … −0.096R, t −3.9 … −4.7, price-only −0.045R at best; H1 confirmation worse in every pair of configs. See docs/12 | No eligible config; validation data stays unseen | 12 (total 247) |
| 2026-10-29 | S5 frozen (docs/13 §12): US open range breakout on the NASDAQ 100 CFD, flat 15:55 ET, 10% cost limit; grid of 12 (N × target × H4 bias). New-instrument splits: research 2014–2020, validation 2021–2023, hold-out 2024+; years replace pairs in §4/P5 | User chose a market change after S4 (docs/12). Idea from published work, not our data. Gold and S&P 500 dropped on trade count only (docs/13 §11) | 0 |
| 2026-10-29 | S5 research grid (12 configs, run twice: identical) and M4: NO-GO, all configs EV −0.019 … −0.141R, t −0.4 … −1.8, price-only −0.006R at best; H4 bias worse in 5 of 6 pairs. See docs/14 | No eligible config; validation data stays unseen | 12 (total 259) |
| 2026-10-29 | **Out-of-sample data opened by user decision:** S5's 12 rules run on all data (2014–2026 NASDAQ 100 and gold, 2010–2026 GBPUSD), with and without costs. Exploratory, not registered. See docs/15 | User request after S5's NO-GO. Validation and hold-out years for ORB-type rules on these 3 markets are no longer clean; a new out-of-sample test must use data after 2026-09 (forward test) | 0 (exploration: 72 views) |
