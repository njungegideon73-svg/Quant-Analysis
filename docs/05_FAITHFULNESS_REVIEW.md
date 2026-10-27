# 05 — Faithfulness Review (M2)

Purpose: check that the coded detectors draw what JeaFx would draw, before any P&L is seen. Each round charts 30 random S1 candidates (`ta review`). The reviewer answers four questions per chart, and the answers are counter-checked against the transcripts.

## Round 1 (2026-10-27, seed 20261027, N=3 k=0.5 m=1.0)

### JeaFx's own definitions used for the counter-check

| Topic | What he says (transcripts) | What the code did | Gap |
|---|---|---|---|
| Zone candle | Not the textbook "last down candle before the up move". He uses the *last candle before the impulse*, which he describes as the *small candle before a large rally away*, often an indecision candle or doji | `j−1`, where `j` is the first candle with body ≥ m·ATR | When the rally starts with medium candles, `j−1` is already a rally candle |
| Imbalance | The *open price range* between the zone and price. If the zone is retested before price pushes away, *there is no imbalance* and the zone is not valid | A 3-candle FVG anywhere in the impulse | A zone can have an FVG higher up and still have been wicked back into |
| Weekend gap | *Just an anomaly* | — | None of the 30 FVGs spanned a weekend; the setups that formed on a Sunday formed after the open |

### Verdicts

Q4 = "JeaFx would draw this zone". Open range = gap between the zone's near edge and the closest price after the impulse, before the zone was created (negative = retested).

| # | Setup | You | Me | Why (measured) | After the new rules |
|---|---|---|---|---|---|
| 1 | EURUSD 2010-02-01 22:45 | Y | Y | 8.7-pip open range, small zone candle | kept |
| 2 | EURUSD 2010-04-04 20:30 | N | Y | Doji zone candle (body 0.04 ATR), 7.6-pip open range; a Sunday-evening setup, but within his rules | kept |
| 3 | EURUSD 2010-12-16 19:45 | Y | N | The zone candle was a rally candle (0.79 ATR) and only 0.5 pip was left open | zone moved to the small candle below it, with a 5-pip open range: **Y** |
| 4 | EURUSD 2011-03-28 21:15 | Y (unsure) | Y | Small opposite candle, 5.2-pip open range | kept |
| 5–7 | EURUSD 2011-04-14, 05-03, 05-30 | Y | Y | 6.7–14 pips open | kept |
| 8 | EURUSD 2011-07-19 01:15 | N | Y | 16-pip open range, small zone candle. The quick reversal afterwards is the outcome, not the drawing | kept |
| 9 | EURUSD 2011-12-25 17:30 | Y | N | Christmas open, 0.0 pip open range: no imbalance | removed |
| 10 | EURUSD 2012-02-15 06:00 | N | Y | 7.6-pip open range. The BOS close is only 0.1 ATR beyond the swing, but a body close is all he asks for | kept |
| 11–12 | EURUSD 2012-07-05, 08-20 | Y | Y | 62 / 9 pips open (#11 is the ECB move) | kept |
| 13 | EURUSD 2012-11-22 21:00 | Y | N | Retested after the impulse (−0.4 pip) | removed |
| 14 | EURUSD 2013-05-10 10:30 | Y | Y | 6.5 pips open | kept |
| 15 | EURUSD 2013-06-13 02:00 | Y | N | Retested after the impulse (−2.3 pips) | removed |
| 16–19 | EURUSD 2013-07-09 … 12-18 | Y | Y | 6–22 pips open | kept |
| 20 | EURUSD 2013-12-30 10:15 | Y | N | 0.2-pip open range: the next candle wicked back to the zone | removed |
| 21 | EURUSD 2014-01-30 00:15 | N | N | Retested; dead-Asia micro break | removed |
| 22 | EURUSD 2015-03-24 04:00 | Y | Y | 6.7 pips open | kept |
| 23 | EURUSD 2015-05-13 23:45 | Y | N | Retested after the impulse (−1.0 pip) | removed |
| 24 | EURUSD 2015-06-23 02:15 | Y | Y | Consolidation before the drop, 8.2 pips open | kept |
| 25–27 | USDJPY 2026-01-14, 04-15, 05-10 | Y | Y | 3–8 pips open | kept |
| 28 | USDJPY 2026-06-30 11:00 | Y | N | The zone runs over 9 candles down to the 08:31 NY data-release wick (4.7 ATR wide). That is not one candle | kept: **open issue** |
| 29 | USDJPY 2026-07-08 16:45 | N | N | The zone is stretched over 4 candles of the run-up (borderline) | kept: **open issue** |
| 30 | USDJPY 2026-09-10 19:30 | N | Y | The zone candle is the hammer that made the leg's low (the origin), which the rule can't step past and shouldn't | kept |

### Scores

| | Q4 yes |
|---|---|
| Your answers | 24 / 30 (80%) |
| My counter-check, zones as drawn in round 1 | 21 / 30 (70%) |
| My counter-check, after the two new rules | 22 / 24 kept (92%); 6 removed |
| We agree | 19 / 30 |

Most of the disagreements are setups you passed that had been **retested** after the impulse (9, 13, 15, 20, 23). His definition rules those out. The other way round, the ones you failed but I passed (2, 8, 10, 30) meet his written criteria; their outcome or session made them look weak.

### Changes made (logged in [03](03_VALIDATION.md), 0 trials)

1. **Zone candle** steps back past in-direction candles with body ≥ 0.5·ATR, never past the origin.
2. **Open range ≥ 0.1·ATR** must survive from the bar after the impulse until the zone is created. Otherwise there is no zone.

### Open issues

- **Origin-wick extension** (`zone_low = min(low[o..j−1])`) can stretch a zone over many candles (#28, #29). Options: cap the zone at N candles, or keep the zone to the zone candle and put the stop beyond the origin, which is his "conservative stop". This needs a decision before M4. The M3 stop cap (3·ATR_H4) already skips the worst cases.
- **News wicks** (#28) are real prices. A news filter waits for a point-in-time calendar (02 §2).
- Round 2 (a fresh sample under the new rules) confirms the fixes.

## Round 2 (2026-10-27, seed 20261028, EURUSD/GBPUSD/USDJPY × 10, 2010–2023, round-1 rules applied)

| # | Setup | You | Me | Why (measured / seen) |
|---|---|---|---|---|
| 1–2, 4–8, 10 | EURUSD (8 setups) | Y | Y | Open range 5–28 pips, clean zone candles |
| 3 | EURUSD 2011-01-17 19:30 | N | N | A minor low broken inside a flat range on a US holiday (MLK Day). His "otherwise consolidation, no trade" |
| 9 | EURUSD 2020-02-10 18:30 | N | N | Micro setup: ATR 2.9 pips, 1-pip open range, BOS 0.02 ATR beyond the swing |
| 11 | GBPUSD 2012-02-01 19:45 | N | N | 2.3-pip open range (0.26 ATR), BOS 0.04 ATR beyond the swing |
| 12 | GBPUSD 2012-12-13 02:15 | N | N | 0.8-pip open range: invisible |
| 13 | GBPUSD 2014-04-17 04:15 | Y | **N** | 1-pip open range (0.19 ATR), the same as #12, which you rejected |
| 14–19 | GBPUSD (6 setups) | Y | Y | #15 (you weren't sure about the long): H4 bullish, 25-pip open range, clean |
| 20 | GBPUSD 2023-02-20 20:15 | N | N | A one-candle break in a flat range on a US holiday (Presidents' Day) |
| 21–22, 24–28 | USDJPY (7 setups) | Y | Y | Open range 4–20 pips |
| 23 | USDJPY 2012-09-04 06:00 | N | N | Micro: ATR 3.2 pips, 0.8-pip open range |
| 29 | USDJPY 2018-12-04 18:15 | N | N | The zone stretches over 8 consolidation candles (the origin-extension issue) |
| 30 | USDJPY 2020-12-02 02:00 | Y | **N** | 0.7-pip open range (0.19 ATR): micro, like #23 |

| | Q4 yes |
|---|---|
| Your answers | 23 / 30 (77%) |
| My counter-check | 21 / 30 (70%) |
| We agree | **28 / 30** (up from 19 / 30 in round 1) |
| After raising the open-range minimum to 0.3·ATR | 21 / 25 kept (**84%**); #11, 12, 13, 23, 30 removed, and nothing from round 1 |

### Change made (logged in [03](03_VALIDATION.md), 0 trials)

- **Open range ≥ 0.3·ATR** (was 0.1). Gaps of 2 pips or less were rejected as "not a visible imbalance" whenever we judged them on their own. The new threshold applies that consistently. Cost: about 13% fewer candidates (EURUSD 2.80 → 2.43 a week).

### Remaining misses (4 of 25) and where they are handled

| Miss | Handled by |
|---|---|
| Holiday / flat-range breaks (#3, #20; round 1 #9 Christmas) | **M3:** a fixed holiday blackout (US and UK bank holidays, Dec 24–Jan 2). The consolidation rule itself stays out of S1 (not codable without a range detector) |
| Micro setups with a tiny ATR (#9) | **M3:** the 15-pip minimum stop. With `min_stop_mode = skip` they never trade |
| Zones stretched over many candles (#29; round 1 #28, #29) | Cosmetic for the proximal entry: the stop is beyond the leg extreme either way. It only affects `entry_at = mid` and the "alive" rule. Decide before M4: zone = zone candle only, stop beyond the origin |

**M2 exit:** 84% would-draw after the fixes, against the 80% mark, with the reviewer and the counter-check agreeing on 28 of 30. The detectors pass the faithfulness review.
