# 06 — Strategy S2: Liquidity-Sweep Reversal (draft for review)

**Status:** frozen 2026-10-29 with the §11 amendment (approved by the user before any S2 run): S2 is §1–3 and §6–9
as written plus §11, which replaces §4–5 (entry on M1) and the §7 grid (4 configs). Same protocol (03): research
2010–2019 only; validation and hold-out stay untouched until a candidate is frozen.

**Source method.** JeaFx's second most-repeated model (research report §5, rank 2; notes b1 #1, b4 #5, b5 C):
*equal highs/lows are where stops sit → price sweeps them with a wick → a body-close break of structure the other way
→ limit order at the zone that caused the break → stop beyond the sweep → target the opposite liquidity.*
In his words: *"wait for price to push above the equal highs … sweep high, break and close beneath the prior low,
sell supply, stop above the high, target next demand."*

**Why it differs from S1.** S1 joins an existing trend at a pullback. S2 fades a stop-run: the trigger is a failed
push through obvious liquidity. It trades against the M15 move by design and is closer to a reversal.

Everything not stated here is the same as S1 (01): data, costs, fills, session, holiday blackout, Friday flatten,
position limits, 0.5% risk, the 15-pip minimum stop, the 3·ATR_H4 stop cap, M1 resolution of fills and exits.

## 1. Timeframes

H4 for the optional context filter, M15 for everything else (same as S1, so the engine and data are reused).

## 2. Liquidity pool

**Equal highs** = two confirmed M15 swing highs (pivot N = 3) within `0.1·ATR_M15` of each other, with no price
above the pool between them. Pool level = the higher of the two. Equal lows mirror this. This is the existing,
tested detector (`equal_levels`, S1's liquidity veto). JeaFx: *"they don't have to be to the pip … very very close"*.

## 3. Sweep (the trigger condition)

At the first M15 bar `s` that trades above an equal-highs pool:

- **Sweep** if that bar **closes back at or below the level** (a wick through). JeaFx: *"a wick beyond is a sweep,
  a body close beyond is a break"*.
- **Break** if it closes above → no S2 setup from this pool (it is S1's territory: continuation).

`sweep_high` = the highest high from bar `s` until the BOS below (it keeps updating while price stays up there).

## 4. Break of structure the other way

Within `W` M15 bars after the sweep *(param W ∈ {8, 24})*: a bar **closes below the most recent confirmed swing
low** that existed at the sweep bar. That is the reversal BOS at bar `t_b`. If the price instead closes above
`sweep_high + 0.1·ATR`, or `W` bars pass, the setup is dropped.

## 5. Zone, entry, stop, target (bearish case; bullish mirrors)

1. **Impulse and zone:** S1's rules (01 §4) applied to the leg from `sweep_high` down to `t_b`: the first bearish
   candle with `body ≥ 1.0·ATR`, the zone candle before it (stepping past rally candles), zone = zone candle +
   next candle's wick, at least one FVG and the 0.1·ATR open range. No zone → no trade.
2. **Entry:** sell **limit** at the zone's near edge *(param entry_at ∈ {proximal, mid})*.
3. **Stop:** above `sweep_high + 0.1·ATR_M15`. JeaFx: *"stop above the high … always clear the highs"*.
4. **Target** *(param target ∈ {T1, T2})*: T1 = 3R fixed. T2 = the opposite liquidity: the lowest low of the
   swing leg that ran up into the sweep, taken only if it is ≥ 3R away.
5. **Life of the order:** placed at the close of `t_b`; cancelled if not filled within 48 M15 bars, if any M15 close
   goes above the zone, or if price trades above `sweep_high` before the fill. First touch only.

## 6. Context filter *(param htf ∈ {none, against_h4})*

- `none`: every sweep counts. This is the pure stop-run fade (b5 C).
- `against_h4`: only sweeps that run *against* the H4 trend (e.g. equal highs swept inside an H4 downtrend), so the
  reversal is back with the bigger trend. This is his "liquidity + structure" version (b1 #1, notes Jh).

## 7. Declared grid: 16 configs

| Param | Values |
|---|---|
| `W` (bars from sweep to BOS) | 8, 24 |
| `entry_at` | proximal, mid |
| `target` | T1, T2 |
| `htf` | none, against_h4 |

Fixed: pivot N = 3, equal-level tolerance 0.1·ATR, impulse m = 1.0, stop buffer 0.1·ATR, expiry 48 bars,
session London+NY, `min_stop_mode` = the Stage B outcome of S1 (`skip` unless widen is adopted there).
These fixed values are chosen before any S2 run; they are not tuned on S2.

**Selection and pass rules:** 03 §4 and §5 unchanged, with "neighbours" = ±1 step in W (the only numeric
grid param) at the same entry_at, target and htf. Walk-forward as 03 §2. A NO-GO at M4 ends S2 without validation.

## 8. Trial budget

**Decided 2026-10-29 (option A):** 250 configs per strategy; the Deflated Sharpe test uses the running total across all strategies (223 from S1 + S2's own).

## 9. What is left out (not codable or hindsight)

His "fuel" judgement for sweep vs break, "inducement vs true zone" picks, trendline liquidity, and the Asia range
(that is S3). These stay out, as in S1.

## 10. Feasibility check after coding (counts only, 2026-10-29)

Code: `src/ta/s2.py`, tests `tests/test_s2.py`. A dry run on 2010–2019 counted setups only: no wins, losses or R
were computed and nothing was written to the registry, so the trial count is still 223.

| Step (7 pairs, 2010–2019) | W = 8 | W = 24 |
|---|---|---|
| Equal-level sweeps followed by a reversal BOS | 2,819 | 4,629 |
| … that also have a valid zone (impulse, FVG, open range) | 1,090 | 1,737 |
| Orders that get touched: proximal, no H4 filter (best case) | 135 | 217 |
| … mid entry, `against_h4` (worst case) | 22 | 48 |

**Every S2 config is below the 300-trade minimum (03 §4) before portfolio limits.** 2020–2026 would give about
100–150 trades, so P3 (≥ 500 out-of-sample trades) cannot be met. Run as drafted, S2 cannot pass. Where setups are lost:
57% of zones need a stop under 15 pips (skipped), and most of the rest are never revisited before expiry.

JeaFx does not take this setup on the BOS timeframe. In his worked sweep trades (notes b6) the sweep is on the higher
timeframe, then he drops to the 1–2 minute chart, waits for a structure shift, and places a limit at the new
small zone (his "standard confirmation", research report §4).

Clarifications made while coding (not grid params): reference low = latest swing low confirmed by the sweep bar;
the invalidation buffer uses ATR at the sweep bar, the stop buffer ATR at zone creation; the order is placed at zone
creation (BOS close, or the next close if the FVG completes there) and expires 48 bars later; T2 = the lowest low
from the pool's first swing to the sweep bar; the `htf` filter reads the H4 state at the sweep bar; pools swept on
the same bar give one setup.

## 11. Amendment: entry on M1 (approved 2026-10-29, before any S2 run)

**Rule change (bearish; bullish mirrors).** §3 (the M15 sweep) is unchanged. §4–5 move to M1, as in his worked
sweep trades:

1. From the first minute after the sweep bar closes, for up to `W`×15 minutes: the first **M1 bearish BOS**
   (pivots N = 3 on M1 mid prices, the same structure rules as 01 §3) whose leg gives a valid **M1 zone**
   (01 §4 rules with ATR_M1, impulse m = 1.0, FVG, open range). The setup is dropped if an M1 close goes above the
   sweep extreme + 0.1·ATR_M15 before that BOS.
2. Sell limit at the M1 zone (`entry_at` proximal | mid). Stop = sweep extreme (highest high from the sweep bar to
   the zone) + 0.1·ATR_M15. The 15-pip minimum stop (skip), the 3·ATR_H4 cap, the session and the blackout are unchanged.
3. Expiry 48 M15 bars (720 minutes) after the zone forms. Cancelled on an M1 close above the zone, or on a trade above
   the sweep extreme. Fills and exits are on M1 bid/ask, exactly as now.

**Counts (7 pairs, 2010–2019, orders that get touched, before portfolio limits):**

| Config | W = 8 | W = 24 |
|---|---|---|
| proximal, no H4 filter | 905 | 968 |
| mid, no H4 filter | 773 | 828 |
| proximal, `against_h4` | 396 | 428 |
| mid, `against_h4` | 338 | 366 |
| proximal, T2 target ≥ 3R | 390 | 403 |

That is about 4× the drafted version. Pro rata, 2020–2026 gives about 550–650 trades for the no-filter configs
(P3 needs ≥ 500: possible, but tight once portfolio limits apply) and about 250–300 for `against_h4` or T2 (cannot meet P3).

**Proposed grid, 4 configs:** W ∈ {8, 24} × `entry_at` ∈ {proximal, mid}, with T1 = 3R and no H4 filter. `htf` and
T2 are dropped because they cannot reach the out-of-sample trade count, not because of any result. The neighbour
rule (03 §4) becomes ±1 step in W. Trial count after the run: 223 + 4 = 227.

Count script: kept outside the repo (scratchpad), same detectors (`ta.features`). It computed no R.
