# 11 — Strategy S4: London Breakout of the Asia Range, with the H4 Trend (draft for review)

**Status:** NO-GO at M4 (docs/12). Frozen 2026-10-29 after two blind chart reviews (round 2: 24/29), approved by the user before any S4
run. **The frozen rules are §1–6 with the §5 stop anchor, plus the §12 H1 option and grid (12 configs, retest
only)**; §4's `zone` entry and the §7 grid are superseded. Same protocol (03): research 2010–2019 only,
validation (2020–2023) and hold-out (2024+) untouched until a candidate is frozen. Trial budget: 250 for S4; the
Deflated Sharpe test counts every trial so far (235 + S4's).

**Where the idea comes from, and its risk.** S3 found that fading a London poke beyond the Asia range lost money with
confidence before costs (10 §2). The mirror image is to trade *with* the break. JeaFx also teaches this side: "London
push", the break-and-retest, and buying the demand that caused a break. **The idea was suggested by research-period
data**, which is how people fool themselves. Two safeguards keep the test honest: the out-of-sample years are
untouched, and the significance bar counts all 235 earlier trials.

**What you asked for:**
- **Top-down:** the H4 market structure sets the bias, and only M15 setups in that direction are taken.
- **Short holds:** every trade is closed by 17:00 UK, so trades last minutes to about 9 hours, never overnight.

Everything not stated here is as S1 (01) and S3 (09): data, costs, M1 fills and exits, holiday blackout, position
limits, 0.5% risk, the 3·ATR_H4 stop cap.

## 1. H4 bias (top-down)

The H4 structure state from 01 §3 (pivots N = 3, body-close BOS), read at the last **closed** H4 bar:
bullish (+1), bearish (−1) or none (0). Only longs in a bullish bias and shorts in a bearish one; no trades
with no bias. This is the same top-down filter S1 used.

## 2. Asia range

As S3 (09 §1): high/low of the M15 bars opening 01:00–06:45 UK (UK clock, daylight saving followed).

## 3. Breakout (M15, London 07:00–11:45 UK)

The first M15 bar in the London window that **closes** beyond the Asia range (a wick alone does not count):

- It closes beyond the **bias side** (above the high in a bullish bias, below the low in a bearish one):
  **breakout setup**, the breakout bar.
- It closes beyond the other side first: no trade that day.

The **London extreme** is the lowest low (long) / highest high (short) from 07:00 UK to the breakout bar. It is
the swing the breakout ran from.

## 4. Entry *(param entry ∈ {retest, zone})*

Long case; short mirrors it.

- **retest:** buy limit at the broken Asia high (break and retest).
- **zone:** buy limit at the near edge of the M15 demand that caused the breakout. 01 §4's zone rules apply to the
  leg from the London extreme to the breakout bar: the impulse candle has a body ≥ 1.0·ATR_M15, there is an FVG,
  and an open range is left. No valid zone means no trade.

**Order life:** placed at the close of the breakout bar, or the zone's creation bar if that is later. The fill comes
from M1 bid/ask with the usual 0.1-pip trade-through, first touch only. The order is cancelled:
- at 12:00 UK if unfilled;
- on an M15 close below the stop level (the breakout failed).

## 5. Stop *(param b ∈ {0.1, 0.25, 0.5})*

Below the **stop anchor** minus `b`·ATR_M15 (long). The anchor is the further of the London extreme and the
**opposite side of the Asia range** (the Asia low for a long), so the stop always sits beyond the whole range's
structure, never inside it. Changed after the first chart review (§11). Setups needing a stop under **10 pips** are
skipped: small stops lost in S3 even before costs. The S1 cap of 3·ATR_H4 also applies.

## 6. Target and exit *(param target ∈ {T1, time})*

- **T1:** 3R fixed (your 1:3 RR).
- **time:** no fixed target; the stop or 17:00 UK ends the trade. This lets the London/NY move run within the day
  instead of capping it at 3R.
- **Both:** any open trade is closed at **17:00 UK**, or earlier at the Friday flatten.

## 7. Declared grid: 12 configs

| Param | Values |
|---|---|
| `entry` | retest, zone |
| `target` | T1, time |
| `b` (stop buffer, ATR_M15) | 0.1, 0.25, 0.5 |

Fixed before any S4 run, not tuned on S4:
- H4 pivots N = 3; M15 pivots N = 3; impulse m = 1.0;
- Asia 01:00–07:00 UK; London window 07:00–12:00 UK; flat 17:00 UK;
- minimum stop 10 pips (skip).

**Selection and pass rules:** 03 §4–§5 unchanged; neighbours = ±1 step in `b` at the same entry and target.
Walk-forward as 03 §2. A NO-GO at M4 ends S4.

## 8. Chart review before freezing (option C)

Before you approve, a chart page shows about 30 random S4 setups. Each chart shows:
- the H4 bias;
- the Asia box and the breakout bar;
- the London extreme, the zone (for `zone`), and the entry, stop and 3R lines.

**Each chart stops at the moment the order is placed**, so you judge whether JeaFx would take the trade without
seeing how it ended. The same chart code can later mark live setups for you to trade by your own judgement.

## 9. Left out

His judgement of "fuel" behind a break, partial profits, break-even stops, news filters, the NY reversal trade.

## 10. Feasibility check (counts only, 2026-10-29)

Code: `src/ta/s4.py`, tests `tests/test_s4.py` (7). Counted on 2010–2019: no wins, losses or R computed, nothing in
the registry (trials still 235).

- 8,071 pair-days have a first London close beyond Asia on the H4 bias side; 2,620 of them have a valid M15 zone.
- Orders filled before 12:00 UK (7 pairs, before portfolio limits):

| Entry | b = 0.1 | b = 0.25 | b = 0.5 | Median stop |
|---|---|---|---|---|
| retest | 4,028 | 4,279 | 4,662 | 18.8 pips (10th–90th: 11.5–36.9) |
| zone | 497 | 570 | 706 | 14.4 pips (10.9–25.0) |

P3 needs ≥ 500 trades in 2020–2026, about 0.68× the research count:
- **retest:** about 2,700–3,200. Ample.
- **zone:** about 340–480, below 500 even before portfolio limits. It cannot pass P3.

**Proposed grid: retest only, 6 configs** (target T1/time × b 0.1/0.25/0.5). `zone` is dropped because of the
trade count, not any result. Trial count after the run: 235 + 6 = 241.

Chart review: `ta review-s4` → `reports/s4_review.html` (30 setups, blind to the outcome, §8).

## 11. First chart review (2026-10-29) and the stop change

The user reviewed the 30 charts (seed 20261029; one left blank): 17/29 "JeaFx would take this", below the 80% mark,
so the draft was not frozen. Answers were blind to outcomes, and the comparison below uses only pre-order features.

- **Entry and stop:** 13/29. In accepted setups the London extreme sat near the far side of the Asia range (median 8%
  of the way up the range for a long). In rejected ones it sat mid-range (median 42%), so the stop was inside the
  range. Fix: stop anchor = the further of the London extreme and the opposite Asia side (§5).
- **Clean close:** 19/29. Rejected breaks closed less far past the level (median 0.29 vs 0.59 ATR), but there is no
  clean cut. 3 of the 4 breaks on the 07:00 bar were called unclean; too few cases for a rule. No change.
- **H4 bias:** 24/29, no pattern in the misses. No change.

A second blind review uses a new seed (20261030) and excludes the 30 charts already seen. If it reaches 24/30, S4 is
frozen with the §10 grid.

**Counts with the new stop (counts only):**

| Entry | b = 0.1 | b = 0.25 | b = 0.5 | Median stop |
|---|---|---|---|---|
| retest | 5,914 | 5,945 | 5,977 | 28.2 pips (10th–90th: 15.5–56.2) |
| zone | 901 | 934 | 979 | 22.3 pips (12.4–47.0) |

`zone` now projects to about 610–670 out-of-sample trades: just above P3's 500, before portfolio limits. Whether to
keep it (12 configs) or drop it (6) is decided at the freeze.

## 12. Second chart review (2026-10-29) and the freeze

**Round 2 (seed 20261030, 30 new charts, stop as in §5): 24/29 "JeaFx would take this" (83%), a pass.** One answer
was left blank. Entry and stop rose from 13/29 to 22/29; H4 bias 27/29; clean close 15/29 (several marked unclear
but still taken). Five cards carry the note "not sure if Jea would take the trade".

**The user's top-down process** (in their words): H4 market structure gives the bias; H1 confirms it and shows the
major zones; M30 finds entries that support H4 and H1; M15 executes.

What can be coded objectively, and what cannot:
- **H1 confirms the bias:** yes. The H1 structure state (01 §3 on H1 bars resampled from M15, pivots N = 3) at the
  breakout close equals the H4 bias. In counts only, it keeps 73% of retest fills (4,364 in 2010–2019, about 2,970
  projected for 2020–2026) and 75% of zone fills (704, about 480 projected: below P3).
- **"Major zones" on H1 and M30 entry areas:** not coded. "Major" is a judgement call with no rule in the research
  notes; guessing one would test my rule, not the user's process.

**Frozen grid, 12 configs (approved 2026-10-29):** entry = retest only × `target` {T1, time} × `b` {0.1, 0.25, 0.5} ×
`h1` {off, on}. `h1 = on` requires H1 agreement. `zone` is dropped (trade count). Testing H1 both ways shows whether
the H1 step adds anything. Neighbours = ±1 step in `b` at the same target and `h1`. Trial count after the run:
235 + 12 = 247.
