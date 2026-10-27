# 02 — Data & Backtest Engine

## 1. Data requirements

| Item | Spec |
|---|---|
| Instruments | EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, USDCHF, NZDUSD |
| Resolution | **M1, bid and ask OHLC separately**, plus tick volume |
| Range | 2010-01-01 → present (2005+ downloaded if available, for extra robustness checks only) |
| Volume estimate | ~7 pairs × 16 yrs × ~370k bars ≈ 41M rows ≈ 1.5–2 GB Parquet |

## 2. Sources

| Source | Use | Notes |
|---|---|---|
| **Dukascopy** datafeed | Primary research history | `https://datafeed.dukascopy.com/datafeed/{PAIR}/{YYYY}/{MM-1}/{DD}/{BID,ASK}_candles_min_1.bi5`. **Months are 0-indexed.** Each file is an LZMA stream of 24-byte records `>IIIIIf` (sec offset, open, close, low, high, volume); prices ÷1e5 (JPY ÷1e3). Zero-volume records are filler and are dropped. ~74k files in total; the server throws intermittent 503s, so it runs throttled with retries (hours, resumable per month). |
| **Dukascopy JForex SDK** (`ta download-jforex`, demo login) | Same history, much faster | Bit-identical to the datafeed (EURUSD 2010-01/03: all rows, 0 diffs). ~15 s/month vs 100–1,000 s. Java bridge in `jforex/`. Writes the same Parquet files, so both routes resume each other. |
| **Pepperstone cTrader** (Open API) | Live data + execution; parity check vs Dukascopy at M6 | History depth is broker-dependent, so it isn't used for research |
| **Economic calendar** | Later A/B news filter | It must be **point-in-time** (event times as scheduled, not revised). To be sourced at M4+. Not needed for the baseline. |

Broker-feed caveat: Dukascopy is an ECN feed, not Pepperstone's. Spreads and prints differ slightly, which is why the M6 parity check exists and the costs are stress-tested (03 P6).

## 3. Storage & quality

- Layout: `data/raw/dukascopy/{pair}/{YYYY-MM}.parquet` is written only once a month is complete, so a re-run skips it. `data/derived/{pair}/{tf}.parquet` holds resampled M15/H4 mid plus bid/ask OHLC, and can be regenerated.
- Schema (M1): `ts` (UTC, bar open, datetime64[ns, UTC]) · `bid_o bid_h bid_l bid_c ask_o ask_h ask_l ask_c` (float64) · `volume` (float32, Dukascopy bid volume). A minute is stored when either side had ticks; a side with no ticks takes the other side's prices.
- Query with DuckDB straight over the Parquet files. There is no database server.
- **Quality report** (`reports/data_quality.html`, per pair and year):

| Check | Action |
|---|---|
| Duplicate / non-monotonic `ts` | Fail the download |
| `ask < bid`, or `h < max(o,c)` | Drop the bar and count it |
| Gaps outside the weekend/holiday calendar > 5 min | List them; > 0.5% of session minutes → investigate |
| Spread outliers (> 10× the pair-year's median spread for that hour of day) | Keep (they're real costs), flag them, and count them in a "spread event" stat |
| Price spikes (|Δmid| > 15·ATR_M1) with no follow-through | Flag; check manually against Dukascopy |
| Cross-check vs broker (M6) | cTrader M1 vs Dukascopy mid close: median < 0.3 pip, 99th pct < 2 pips |

## 4. Engine architecture

```
           ┌─────────── Strategy (pure, shared with live) ──────────┐
 bars ───► │ features (incremental) ─► S1 rules ─► intents          │
           └────────────────────────────────────────────────────────┘
                                      │ place / cancel / modify
                                      ▼
            Broker simulator (backtest)   |   cTrader adapter (live)
            - M1 intrabar fills            |   - REST orders w/ SL/TP on fill
            - costs, slippage              |   - reconciliation
                                      ▼
                         Portfolio & risk (sizing, limits, equity)
                                      ▼
                         Trade log  →  metrics / reports
```

- **Driver.** It loops over M15 bar closes in time order across all 7 pairs (merged timeline), which keeps the portfolio limits realistic.
- **Features.** Pivots, structure, zones, FVG and equal highs/lows are computed **incrementally** (each bar sees only the past). For speed, a vectorised/numba precompute is allowed *only* if a test proves it gives identical output to the incremental version.
- **Speed.** Features depend only on (N, m, k), so they're computed once per combination and cached. The order/fill simulation per config is a numba kernel. Runs fan out across 4 cores by (pair × config). The target is the full S1 grid ([03 §3](03_VALIDATION.md)) in < 2 h on this machine.

## 5. Fill & cost model (pessimistic by design)

| Event | Long rule (shorts mirror on the other side) |
|---|---|
| Limit buy fill | Inside the M15 bar, step through its M1 bars. Fill on the first M1 bar where `ask_l ≤ entry − fill_through` (`fill_through` = 0.1 pip). Fill price = `entry` (no price improvement). |
| Stop loss | Triggers when `bid_l ≤ stop`. Fill = `stop − slip` (`slip` = 0.2 pip default, stress-tested at ×2 and ×3). Gaps: fill at `bid_o` if that is worse. |
| Take profit | Triggers when `bid_h ≥ target + 0.1 pip`. Fill = `target`. |
| SL and TP in the same M1 bar | **Assume the SL hit first.** |
| Fill and TP in the same M1 bar | Fill counts; the TP can only trigger from the next M1 bar. |
| Fill and SL in the same M1 bar | Both count (immediate loss). |
| Spread | Paid implicitly, because entry and exit are on opposite sides of the book. |
| Commission | `commission_per_lot` per side *(config; set from Pepperstone Razor's cTrader commission schedule at M6; until then stress-tested at $3.5/lot/side)* |
| Financing (swap) | Per-pair nightly cost from config, applied at 17:00 NY if the position is open. Default is a flat stress estimate (0.3 pip/night against us). Positions are mostly intraday, so its impact is reported separately. |
| Weekend flatten | Market close at the Fri 16:30 NY M1 bar: bid for longs, minus slip |

**Result unit.** Each trade is logged in **R** (`(exit − entry)/(entry − stop)` net of all costs) and in account USD. Expectancy, win rate and every pass criterion use **net R**.

## 6. Correctness tests (must pass before M4)

1. **Prefix invariance.** Run on data up to date D, and on the full data. Every decision (zones, orders, fills) with a timestamp ≤ D must be identical. This catches any look-ahead.
2. **Synthetic fixtures.** Hand-built bar sequences with a known pivot, BOS, zone, FVG and equal lows, covering every rule in 01. Expected outputs are asserted.
3. **Fill-ordering tests.** Each row of the §5 table gets a unit test.
4. **Sizing test.** Risk per trade = 0.5% ± rounding for every pair (including JPY and USD-base pairs) at random equity levels.
5. **Hand audit.** 20 random trades are traced on charts against the raw M1 data (`ta audit` → `reports/hand_audit.html`, re-traced by code that does not use the engine). M3 result: 20/20, and 571/571 research-period trades of the smoke run, including 25 Friday flattens. Injected errors (slip, commission, fill minute, stop level) are all caught.
6. **Random-entry control.** The same stops/targets/costs with random entry times must show EV ≈ −costs. If the random strategy "makes money", the engine is wrong.

## 7. Outputs per run

- `runs/{run_id}/config.yaml`, the config's hash, and the data snapshot id (file hashes).
- `trades.parquet` (one row per trade, all §12 fields from 01).
- `report.html` with the equity curve in R, drawdown, the metric table, and per-pair/year/hour breakdowns.
- A row in `runs/registry.csv` (every run, so the full test count is known for multiple-testing correction).
