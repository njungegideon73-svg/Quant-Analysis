# 13 — Strategy S5: US Open Range Breakout on the S&P 500, NASDAQ 100 and Gold (draft for review)

**Status:** NO-GO at M4 (docs/14). Frozen 2026-10-29, approved by the user before any S5 run. **The frozen grid is §12: NASDAQ 100 only,
12 configs**, which supersedes the 36 in §7. No S5 result exists yet. Same protocol as 03, adapted for new instruments in §8.

**Why this, and how strong the evidence is.** After four NO-GOs on FX majors (12), the user chose to keep the
intraday style but change the market. The idea comes from published work, not from our data:

| Source | What it found | Caveat |
|---|---|---|
| Gao, Han, Li, Zhou (J. Financial Economics, 2018) | The first half-hour return of the S&P 500 ETF predicts the last half-hour (1993–2013, also 10 other ETFs) | A momentum effect, not a breakout rule |
| Tsai et al. (IEEE Access, 2019) | An opening-range breakout on DJIA, S&P 500, NASDAQ, HSI and TAIEX futures earned > 8% a year, p < 3% in all five (2003–2013) | A variant ORB; older data |
| Zarattini & Aziz (SSRN, 2023) | A 5-minute ORB on QQQ: about 24% wins, +0.13R per trade | An independent replication found the gross edge, but **net of spread and slippage it was zero** |
| Zarattini, Aziz, Barbon (SFI, 2024) | An intraday momentum rule on SPY, flat by the close: Sharpe 1.33 net of costs (2007–2024) | Not an ORB; by the same authors' firm |
| Gold | **No academic ORB study found** | Gold is included as an untested market, not an evidenced one |

So the support is real for the US indices but mixed, and costs decide it. Gold has none.

## 0. Data (probe, 2026-10-29)

Dukascopy CFD history through the JForex bridge (one month per year probed; `HistoryDump` now maps
`USA500IDXUSD` → `USA500.IDX/USD`):

| Instrument | Dukascopy name | History from | Median spread, 09:30–16:00 ET (Mar 2019) |
|---|---|---|---|
| S&P 500 | `USA500.IDX/USD` | about 2014-01 (2013-12 has no bid side) | 0.46 pt (about 0.016%) |
| NASDAQ 100 | `USATECH.IDX/USD` | 2013-12 or earlier | 1.07 pt (about 0.015%) |
| Gold | `XAU/USD` | 2008 or earlier; 2016-03 has no bid side | 0.29 USD (about 0.02%) |

All three trade almost 24 hours. The 09:30–10:00 ET window had bars on every trading day probed.

## 1. Session (US cash open, New York clock, daylight saving followed)

- **Open:** 09:30 ET.
- **Last entry:** 12:00 ET. Orders not filled by then are cancelled.
- **Flat:** 15:55 ET, before the cash close, when CFD spreads widen.
- **Skipped:** NYSE holidays and half days.

In Kenya time this is 16:30–22:55 EAT while the US is on daylight saving (March to early November), and
17:30–23:55 EAT otherwise. Trades last minutes to about 6½ hours and never stay open overnight.

## 2. Opening range *(param N ∈ {5, 15, 30} minutes)*

The high and low of the mid prices over the first N minutes from 09:30 ET.

## 3. Entry

After the range closes, there is a buy stop at the range high and a sell stop at the range low, filled on M1 ask/bid
with the usual trade-through. **The first side hit is the day's only trade**, and the other order is cancelled.

## 4. Stop

The opposite side of the opening range (as Zarattini & Aziz). **Cost filter:** the day is skipped if the round-trip
cost (spread + slippage + commission) is more than 10% of the stop distance. Small ranges are where the QQQ
replication lost its edge to costs.

## 5. Target *(param target ∈ {3R, close})*

- **3R:** a fixed 1:3, your RR.
- **close:** no target; the trade ends at the stop or at 15:55 ET.

## 6. Top-down bias *(param bias ∈ {off, on})*

`on`: trade only in the direction of the H4 structure state (01 §3, pivots N = 3, the last closed H4 bar), the first
step of your process. `off`: both directions. S4 found that H1 confirmation did not help, so only H4 is offered here.

## 7. Grid: 12 configs per instrument, 36 in total

N {5, 15, 30} × target {3R, close} × bias {off, on}, run separately for each instrument. **Each instrument must stand
alone**: three markets are not pooled to hide a weak one. The trial count after the run would be 247 + 36 = **283**,
and the Deflated Sharpe test counts all of them.

## 8. Protocol changes for new instruments (decided before any download)

- **Splits:** research **2014–2020**, validation **2021–2023**, hold-out **2024+**. The FX split (2010–2019) cannot
  be used because the indices start in 2014. Gold uses the same split so the three are comparable.
- **Selection (03 §4):** per instrument, neighbours = ±1 step in N at the same target and bias. Eligible configs
  need all neighbours EV > 0, ≥ 300 research trades, and positive in ≥ 5 of the 7 research years (years replace
  pairs).
- **Pass (03 §5):** P1–P9 unchanged, except that P5 reads "≥ 2/3 of years". P3 (≥ 500 out-of-sample trades) is
  feasible: about 5.8 years × ~230 trades a year ≈ 1,300 per instrument.
- **Walk-forward:** yearly folds inside 2014–2020, as 03 §2.

## 9. Costs and engine work needed before any run

- **Costs:** spread comes from the real bid/ask in the data. Stop slippage uses the FX calibration (0.2 pip plus the
  overshoot rule) converted to each instrument's tick until it can be checked on the JForex tester.
  **Commission: to be confirmed** from Dukascopy's CFD fee schedule or your demo account before the freeze. I could
  not find it published.
- **Engine:** per-instrument tick size, costs and sizing (`pip_size` and `Costs.for_pair` are FX-only today); a New
  York session clock and NYSE holiday list; download plus the data-integrity manifest for the three instruments
  from 2014 (the gold 2016-03 gap re-fetched or marked missing); `src/ta/s5.py` with tests; an M4 stage that groups
  by year instead of by pair.
- **Before the freeze:** a feasibility count (orders and fills only, no R) and a blind chart review as for S4, if
  you want one.

## 10. Left out

The Zarattini "direction of the first candle" entry, the SPY noise-area rule, trailing stops, volume filters,
news-day filters, and other indices (DAX, FTSE).

## 11. Build and feasibility check (counts only, 2026-10-29)

**Built:**
- `src/ta/s5.py` with tests in `tests/test_s5.py` (8).
- Stop-order fills: gap-aware, plus slippage, and R measured from the actual fill.
- The NYSE holiday and half-day list, and the 15:55 ET exit through the engine.
- Per-instrument costs: commission on notional, at the FX rate (3.5 per 100k per side) until confirmed.
- The CFD periods (§8), `ta grid --stage S5` (each instrument alone) and `ta m4 --stage S5` (years replace pairs).

**Data:** 153 months per instrument (2014-01 to 2026-09). Every new file was hashed twice with the page cache
evicted in between, and both reads matched. The manifest now has 1,866 files, and the snapshot is `e6a28e13`.

**Session spread (median, 09:30–16:00 ET, 2014–2020):**

| Instrument | Median spread | Slippage per side (assumed) |
|---|---|---|
| S&P 500 | 0.26–0.54 pt | 0.25 pt |
| NASDAQ 100 | 0.98–2.15 pt | 0.5 pt |
| Gold | 0.23–0.38 USD | 0.15 USD |

**Filled orders, 2014–2020, bias off.** The bias-on counts are 60–80% of these.

| Cost limit | S&P 500 N 5 / 15 / 30 | NASDAQ 100 N 5 / 15 / 30 | Gold N 5 / 15 / 30 |
|---|---|---|---|
| **10% (as drafted)** | 84 / 282 / 471 | 324 / 704 / 919 | 8 / 72 / 148 |
| 15% | 237 / 635 / 901 | 648 / 1,109 / 1,290 | 41 / 231 / 459 |
| 20% | 442 / 964 / 1,228 | 922 / 1,370 / 1,494 | 119 / 468 / 776 |
| none | ~1,700 each | ~1,700 each | ~1,700 each |

**What this means:**
- **Costs bind.** The round trip costs about 1.1 pt on the S&P 500 and about 0.7 USD on gold, so the 10% rule needs
  an 11-point or 7-USD opening range. Most days are smaller.
- **P3 (≥ 500 out-of-sample trades, about 0.82× research):**
  - Gold cannot reach it at any limit up to 20%.
  - The S&P 500 cannot reach it at 10%.
  - The NASDAQ 100 reaches it at N 15 and 30 with bias off (about 580 and 750). With bias on it falls short (about
    390–460).
- **Loosening the limit is not free.** At 20%, costs take about 0.2R from every trade. The QQQ paper's gross edge was
  about 0.13R.

**Decision needed before the freeze:** keep the grid as drafted (36), or drop the instruments that cannot pass P3.

## 12. Freeze (2026-10-29)

**Approved: NASDAQ 100 only, 12 configs.** The grid is N {5, 15, 30} × target {3R, close} × bias {off, on}, with the
10% cost limit, slippage 0.5 pt per side, and commission at 3.5 per 100k notional per side. Gold and the S&P 500 are
dropped because they cannot reach P3 (§11), not because of any result. Trial count after the run: 247 + 12 = **259**.
