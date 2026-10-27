# JeaFx Price-Action System — Project Documentation (Phase 2)

Internal, single-user project. The goal is to turn JeaFx's discretionary price-action method into objective rules, then **prove or disprove** that those rules give a 30% win rate at a 1:3 risk-reward after costs. If they do, trade it automatically.

Phase 1 findings: [../research/RESEARCH_REPORT.md](../research/RESEARCH_REPORT.md)

| Doc | Contents |
|---|---|
| [01_STRATEGY_S1.md](01_STRATEGY_S1.md) | Exact rules for Strategy 1 (trend-continuation zone limit), parameters, variants |
| [02_DATA_AND_BACKTEST.md](02_DATA_AND_BACKTEST.md) | Data sources, storage, quality checks, backtest engine, fill and cost model |
| [03_VALIDATION.md](03_VALIDATION.md) | Data splits, parameter grid, statistics, pass/fail criteria, forward test |
| [04_EXECUTION_AND_INFRA.md](04_EXECUTION_AND_INFRA.md) | Forward test on Dukascopy JForex demo (Pepperstone cTrader as the live alternative), risk controls, kill switch, repo layout, ops |

---

## 1. Decisions (locked unless revisited)

| # | Decision | Value | Why |
|---|---|---|---|
| D1 | Instruments | EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, USDCHF, NZDUSD | Tightest spreads; enough trades to reach statistical significance |
| D2 | Timeframes | H4 bias / M15 entry | Stops are usually ≥15 pips, so costs stay ≤ ~0.07R |
| D3 | System type | Research → forward test → fully automated execution | User choice |
| D4 | Data / broker | **Data:** Dukascopy M1 bid/ask (free, 2003+). **Forward test:** Dukascopy **JForex demo** (installed 2026-10-27), via the JForex SDK (Java) bridged to the Python strategy. **Live:** decided at M7 between Dukascopy and Pepperstone Markets Kenya (CMA #128, cTrader Open API) | OANDA doesn't serve Kenya. Dukascopy demo trades on the **same feed the backtest uses**, so the parity check is near-trivial and fills are directly comparable. |
| D5 | Account currency | USD (assumed; change in config) | — |
| D6 | Risk per trade | **0.5% of equity** | A working 30%/3R system has a median max drawdown of ~22R (about 11% at 0.5%) |
| D7 | Targets | **Fixed 3R** and **structural (≥3R)**, both tested | Fixed 3R is the user's spec; structural is the trader's own method |
| D8 | First strategy | **S1 — trend-continuation zone limit** | The most repeated and most mechanical model in the videos |
| D9 | Pass criteria | See [03_VALIDATION.md §5](03_VALIDATION.md) | Taken from the Phase 1 report |
| D10 | Language / stack | Python 3.12, uv, NumPy/pandas, numba, Parquet, DuckDB, SQLite, pytest | Runs on this machine; no cloud needed for research |
| D11 | Internal clock | UTC everywhere; sessions defined in Europe/London time (DST-aware) | Avoids DST bugs |

## 2. Guiding principles

1. **Causality first.** A decision at bar *t* may use only information available at *t*'s close. This is enforced by tests (prefix-invariance test, see 02 §6).
2. **Same code in backtest and live.** The strategy is an `on_bar(bar) → intents` object. The backtester and the live runner are just different drivers for it.
3. **Pessimistic fills.** Bid/ask prices, limits need price to trade through, stops get slippage, and ambiguous bars resolve against us.
4. **Declare before testing.** The parameter grid and pass criteria are written down (03) before the first run. The hold-out data is opened **once**.
5. **A negative result is a result.** If S1 fails, we report it and move on to S2/S3. We do not keep tuning until it passes.

## 3. Milestones

| M | Deliverable | Exit criterion |
|---|---|---|
| **M0** | Repo, `uv` env, lint/test CI (local), config system, run registry | `pytest` green; `ta --help` works |
| **M1** | Data pipeline: Dukascopy M1 bid/ask download 2010→now for 7 pairs, Parquet store, M15/H4 resampling, quality report | Quality report has no unexplained gaps (02 §3). Broker-vs-Dukascopy price parity is checked at M6. |
| **M2** | Feature detectors: pivots, structure/BOS, impulse/FVG, zones, equal highs/lows, premium/discount | Unit tests on synthetic fixtures; prefix-invariance passes; **faithfulness review**: 30 random setups charted and reviewed by you against the videos |
| **M3** | Backtest engine: M15 driver with M1 intrabar resolution, bid/ask fills, costs, portfolio and risk sizing | Engine tests (fill, SL/TP ordering, sizing, costs) pass; hand-checked trade logs |
| **M4** | S1 research on **2010–2019** with the declared grid and internal walk-forward | Up to 3 frozen candidate configs, chosen by robustness rules (03 §4) |
| **M5** | Validation on **2020–2023**, then **hold-out 2024→now (once)** | **GO / NO-GO report** against the pass criteria |
| **M6** | Live runner on the Dukascopy JForex **demo** account: forward test ≥ 3 months | Execution checks in 03 §6 pass; broker M1 prices vs Dukascopy: median mid diff < 0.3 pip |
| **M7** | Live, micro risk 0.1% for 2 months, then 0.5% | Live results inside the Monte Carlo band; no execution incidents |

If M5 is NO-GO, M4–M5 repeat for **S2 (liquidity-sweep reversal)** and then **S3 (Asia-range session model)**, on the same data, engine and protocol.

## 4. What I need from you

| When | Item |
|---|---|
| Before M1 | Nothing: Dukascopy data needs no account |
| Before M6 | Your Dukascopy demo login (done, JForex4 installed) stored by you in the local `.env` as `DUKASCOPY_USER` / `DUKASCOPY_PASSWORD` (never pasted in chat). Demo logins expire, so renew it if needed |
| Before M2 sign-off | About 1 hour to review 30 charted setups: "is this what JeaFx would mark?" |
| Before M7 | Your live account's pricing type (spread-only vs core + commission) and the starting capital |
| Optional | A Telegram bot token for alerts |
