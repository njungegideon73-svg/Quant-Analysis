# 09 — Strategy S3: Asia-Range Sweep, London Reversal (draft for review)

**Status:** frozen 2026-10-29 (approved by the user before any S3 run, with the 5-pip minimum stop from §7).
Same protocol (03): research 2010–2019 only, validation and hold-out untouched until a candidate is frozen.
**Last strategy under the stop rule (README §3):** if S3 is NO-GO, we stop and discuss a different approach.

**Source method.** JeaFx's session model (research report §5, rank 3; notes b5 "Asia sweep, London push, NY
reversal", b6 S5): *Asia is a low-volume range that builds liquidity above and below; London often sweeps one side
and reverses; take the lower-timeframe break of structure, sell supply, stop above the sweep high, target the other
side of Asia, be flat by 17:00 UK.* He also says the first side of Asia taken out is the one more likely to reverse.

**Why it differs from S2.** The liquidity is fixed by the clock (the Asia high/low), not by detected equal highs, so
there is exactly one candidate per pair per day. The target is the opposite side of the range, and every trade is
closed by 17:00 UK. That avoids holding for a 3R target through New York and the Friday flatten, which is where S1
and S2 lost most of their wins (07, 08).

Everything not stated here is as S2 (06 §11) and S1 (01): data, costs, M1 fills, the 3·ATR_H4 cap, holiday blackout, position limits, 0.5% risk.

## 1. Asia range

`asia_hi` / `asia_lo` = the highest high / lowest low of the M15 mid bars that open from **01:00 to 06:45
Europe/London** (UK clock, so daylight saving is followed automatically). Known at 07:00 UK.
JeaFx gives 01:00–07:00 twice and 00:00–07:00 once; 01:00 is used.

## 2. Sweep (London, 07:00–12:00 UK)

The first M15 bar opening from 07:00 to 11:45 UK that trades beyond either side of the Asia range:

- **Sweep** if it closes back inside the range (at or below `asia_hi`, or at or above `asia_lo`).
- **Break** if it closes beyond. No trade that day: only the first side taken counts.
- A bar that trades beyond both sides: no trade that day.

## 3. Entry (as S2 §11, on M1)

Bearish case (Asia high swept); the bullish case mirrors it.

1. From the minute after the sweep bar closes, within `W` M15 bars *(param W ∈ {4, 8})*: the first M1 bearish BOS
   whose leg leaves a valid M1 zone (01 §3–4 on M1). Dropped if an M1 close goes above the sweep extreme + 0.1·ATR_M15 first.
2. Sell **limit** at the M1 zone *(param entry_at ∈ {proximal, mid})*.
3. **Stop** = sweep extreme (highest high from the sweep bar to the zone) + 0.1·ATR_M15. Setups needing a stop
   under **5 pips** are skipped (S1/S2 use 15; see §7).
4. **Order life:** cancelled if not filled by **12:00 UK**, on an M1 close above the zone, or on a trade above the sweep extreme.

## 4. Target and exit

*(param target ∈ {T1, Tasia})*

- **T1** = 3R fixed.
- **Tasia** = the opposite side of the Asia range (`asia_lo` for a short), taken only if it is at least 3R from
  the entry; otherwise no trade.
- **Time exit, both targets:** any open trade is closed at **17:00 UK** at the bid (long) / ask (short) plus slip,
  like the Friday flatten. JeaFx: flat by 17:00, "80 to 85% of days" lose direction after it.

So every S3 trade risks 1R for a planned 3R or more. Trades cut at 17:00 can end anywhere between −1R and +3R.

## 5. Declared grid: 8 configs

| Param | Values |
|---|---|
| `W` (M15 bars from sweep to the M1 BOS) | 4, 8 |
| `entry_at` | proximal, mid |
| `target` | T1, Tasia |

No H4 filter (S2 §11: it halved the count). Fixed: Asia 01:00–07:00 UK, London 07:00–12:00 UK, flat 17:00 UK,
M1 pivots N = 3, impulse m = 1.0, buffer 0.1·ATR_M15, minimum stop 5 pips with `min_stop_mode = skip`.
These are set before any S3 run and are not tuned on S3.

**Selection and pass rules:** 03 §4 and §5 unchanged; neighbours = ±1 step in W at the same entry_at and target.
Walk-forward as 03 §2. A NO-GO at M4 ends S3 without validation, and triggers the stop rule.
Trial count after the run: 227 + 8 = 235.

## 6. Left out (not codable, or hindsight)

His New York reversal trade (picking "reversal vs continuation" of London is done after the fact), the
"fill of a gap/supply into the open" judgement, partial profits, and moving the stop to break-even. These stay out,
as in S1 and S2.

## 7. Feasibility check (counts only, 2026-10-29) and the decision needed

Counted on 2010–2019 with S2's tested entry code: no wins, losses or R computed, nothing in the registry
(trials still 227). Each Asia day has a high and a low; 8,090 of 18,213 pair-days give a London sweep
(8,727 are breaks).

**The 15-pip minimum stop (from S1) does not fit this setup.** After an Asia sweep the M1 zone sits right at the
sweep extreme, so the natural stop is small: median 6.6 pips (10th–90th percentile 2.3–17.6). The Asia range itself
has a median of 27 pips. 85% of zones need a stop under 15 pips and are skipped.

Orders filled before 12:00 UK (7 pairs, 10 years). Each cell shows T1 / Tasia (Tasia needs the opposite side ≥ 3R away):

| Minimum stop | W 4, edge | W 4, mid | W 8, edge | W 8, mid |
|---|---|---|---|---|
| 15 pips (as drafted) | 373 / 37 | 300 / 35 | 489 / 45 | 395 / 41 |
| 10 pips | 829 / 178 | 672 / 149 | 1,011 / 198 | 828 / 168 |
| 8 pips | 1,133 / 312 | 940 / 277 | 1,333 / 335 | 1,119 / 302 |
| 5 pips | 1,884 / 760 | 1,598 / 685 | 2,132 / 808 | 1,813 / 726 |

P3 needs ≥ 500 trades in 2020–2026, about 0.68× the research count.

- **15 pips:** fails P3 for every config.
- **8 pips:** works for T1 only.
- **5 pips:** works for both targets, Tasia only just.

**The cost of small stops.** Round-trip costs (spread, commission, slip) are roughly 1.3–2 pips, so about 0.3R on a
5-pip stop and 0.2R on 8 pips, before the stop-overshoot penalty. The engine charges all of this, so a pass would
still be honest. But S3 then needs a large raw edge (≥ 0.5R before costs at 5 pips) to reach +0.2R after costs.
The stop-spike calibration (100 JForex stop-outs) was done on S1's ≥ 15-pip stops; it is less proven on 5-pip stops.

**Decided 2026-10-29:** minimum stop 5 pips, all 8 configs.
