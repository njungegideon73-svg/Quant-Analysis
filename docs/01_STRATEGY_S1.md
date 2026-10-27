# 01 — Strategy S1: Trend-Continuation Zone Limit

**Source method:** JeaFx core model (30+ videos). It runs: higher-timeframe trend → break of structure → fresh, imbalanced supply/demand zone in discount/premium → limit order → stop beyond the zone → target.

**Status:** specification for M2–M4. Every number marked *(param)* is in the declared grid ([03 §3](03_VALIDATION.md)). Everything else is fixed.

Notation: rules are written for **longs**, and shorts mirror them (high↔low, bid↔ask, above↔below). `ATR` = Wilder ATR(14) on the timeframe named. All signal logic uses **mid** prices (`(bid+ask)/2`). Fills and stops use bid/ask ([02 §5](02_DATA_AND_BACKTEST.md)).

---

## 1. Bars

- M1 bid/ask is resampled to **M15** and **H4** mid OHLC. H4 bars are aligned to the FX-standard 17:00 America/New_York day, so boundaries fall at 17, 21, 01, 05, 09, 13 NY time.
- A bar becomes available **only at its close**. At M15 time *t*, the H4 information used is from the **last fully closed** H4 bar.

## 2. Swing pivots (both timeframes)

A **swing high** at bar *i*:
`high[i] > max(high[i-N .. i-1])` **and** `high[i] >= max(high[i+1 .. i+N])`

- It is **confirmed at the close of bar i+N**, and it does not exist before then.
- Optional size filter: `high[i] − min(low[i-N .. i+N]) ≥ k·ATR` *(param k)*.
- Swing lows mirror this.
- `N` *(param)*: M15 ∈ {2, 3, 5}; H4 fixed at 3.

## 3. Market structure state machine (both timeframes)

State ∈ {`NONE`, `BULL`, `BEAR`}. It is close-based, matching JeaFx: *a wick beyond is a sweep, a body close beyond is a break*.

```
ref_high  = most recent confirmed swing high not yet broken
ref_low   = most recent confirmed swing low  not yet broken
protected = the structural low/high that invalidates the current trend

on bar close c at bar t:
  if close[t] > ref_high.price:                       # bullish BOS
      leg_origin = argmin(low[ref_high.bar .. t])      # the pullback low that launched the break
      protected  = low[leg_origin]
      emit BOS(dir=+1, bar=t, broken=ref_high, origin=leg_origin)
      state = BULL; ref_high = None (next confirmed swing high becomes ref_high)
  elif state == BULL and close[t] < protected:         # trend flip (JeaFx "first opposite BOS")
      emit BOS(dir=-1, ...) with mirrored origin; state = BEAR
  (mirror for bearish)
```

- A BOS in the **same** direction as the state is a *continuation BOS*. A BOS against it is a *reversal BOS*.
- S1 trades only **continuation BOS** on M15, in the direction of the H4 state (§7).

## 4. Impulse and zone (M15)

At each bullish BOS at bar `t_b`, with `o = leg_origin`:

1. **Impulse start.** `j` = the first bar in `(o, t_b]` that is bullish with `body ≥ m·ATR_M15` *(param m ∈ {1.0, 1.5})*. If none exists, there is no zone.
2. **Zone candle** `z`: start at `j − 1` and step back while `z > o` and candle `z` is itself bullish with `body ≥ 0.5·ATR_M15` (fixed). JeaFx's *"last candle before the impulse"* is the *"small candle before a large rally away"*, often an indecision candle, so a candle that is already part of the rally is not the zone. `z ≥ o` always.
3. **Zone** = `[zone_low, zone_high]` with `zone_low = min(low[o .. j−1])` and `zone_high = high[z]`. This is wick-to-wick, extended over the origin wick.
   - Variant *(param zone_body)*: `zone_high = max(open, close)[z]`.
4. **Imbalance required.** At least one bullish 3-candle FVG in `[j−1, t_b+1]`, i.e. `low[k+1] > high[k−1]` for some k. If there is none, there is no zone.
   - **Open range (no retest).** Every bar after the impulse up to creation must stay clear of the zone: `min(low[j+1 .. created]) − zone_high ≥ 0.3·ATR_M15` (fixed; set by review rounds 1–2, see 05). This is JeaFx's own test of imbalance: *"the open price range is left open and the demand zone hasn't been retested"*. A zone that was wicked back into before price left has no imbalance.
   - The window reaches one bar past the BOS because, when the impulse candle *is* the BOS candle, the gap can only complete on the next bar (34% of BOS on EURUSD 2010–12).
5. The zone is **created at the close of `t_b`**, or at the close of `t_b+1` when only that bar completes the FVG. No order may exist before that.

## 5. Zone life cycle

A zone is **valid** while all of these hold:

| Rule | Definition |
|---|---|
| Fresh | No M15 bar after `t_b` has had `low ≤ zone_high` before our order exists. The first touch is the trade; zones already touched are discarded. |
| Alive | No M15 close `< zone_low` |
| Discount | `entry_price ≤ EQ`, where `EQ = (leg_high + zone_low)/2` and `leg_high = max(high[o .. now])`. `leg_high` only rises, so this condition only becomes easier. |
| Bias | The H4 state is `BULL` (§7) |
| Not expired | `now − t_b ≤ K` M15 bars *(param K ∈ {48, 96, 192})* |

**One setup per pair.** When a new continuation BOS creates a new valid zone, it **replaces** the pending order of the older zone. That's the default *(param zone_pick = newest)*. The variant *(param zone_pick = extreme)* keeps the oldest still-valid zone of the current leg instead, which is JeaFx's "extreme zone".

## 6. Order

| Item | Rule |
|---|---|
| Entry | Buy **limit** at `entry = zone_high` *(param entry_at ∈ {proximal, mid})*, where `mid = (zone_high+zone_low)/2` |
| Stop | `stop = zone_low − b·ATR_M15` *(param b ∈ {0.05, 0.10, 0.20})*. Executed on **bid**. |
| Stop distance floor | `entry − stop ≥ 15 pips` (JPY: 0.15). If smaller, `min_stop_mode` *(param)* decides: `skip` the trade, or `widen` the stop to 15 pips. |
| Stop distance cap | `entry − stop ≤ 3·ATR_H4`, otherwise skip (prevents giant-risk trades) |
| Target T1 (fixed) | `entry + 3·(entry − stop)` |
| Target T2 (structural) | `leg_high` at fill time (the swing JeaFx targets). **Skip if < 3R** (his rule). Not capped. |
| Size | `units = floor(0.005·equity / (stop distance × pip value in USD))` |
| Placement | At the close of the bar where all §5 conditions first hold. Re-checked every M15 close; cancelled as soon as any condition fails. |
| Fill window | Fills are allowed only within the session window (§8). Outside it the order is inactive. |

There is **no trade management** in the baseline: set-and-forget, target or stop. Variants for later phases (not in the M4 grid): breakeven after the next continuation BOS, and a 50% partial at 2R.

## 7. Higher-timeframe bias (H4)

- Longs only if the H4 state = `BULL`, shorts only if `BEAR`, and no trades while `NONE`.
- Variant *(param htf_location)*: also require the M15 entry price to be in H4 discount: `entry ≤ (H4 leg_high + H4 protected)/2`.

## 8. Time filters

| Rule | Default | Param |
|---|---|---|
| Session window for fills | 07:00–17:00 Europe/London (London + NY overlap) | `session ∈ {london_ny, all}` |
| Rollover blackout | No fills 16:45–17:30 America/New_York | fixed |
| Weekend | No fills after Fri 15:00 NY; flatten open positions Fri 16:30 NY at market | fixed |
| News | **Not in the baseline** (no point-in-time calendar yet). Added later as an A/B filter once a historical high-impact calendar is sourced (see 02 §2). | — |

## 9. Liquidity veto (A/B filter)

- **Equal lows** = two confirmed M15 swing lows within `t·ATR` of each other *(t ∈ {0.1})* that no later bar has traded below.
- **Veto:** skip a long if unswept equal lows lie in `(zone_low − 2·ATR_M15, zone_low)`. JeaFx: *never buy above equal lows*, because the zone is likely bait and price will run the lows first.
- Tested as `liq_veto ∈ {off, on}`.

## 10. Portfolio rules

- Max **1 position or pending order per pair**.
- Max **4 open positions** (2% total risk).
- Max **2 positions with the same directional currency exposure**. Example: long EURUSD + long GBPUSD = 2× short USD, so a third short-USD position is blocked.
- When signals compete in the same bar, the earliest-created zone wins. Ties are broken by fixed pair order, for determinism.

## 11. What is deliberately NOT in S1

These come from the videos but cannot be coded or would need hindsight: narrative, "true zone vs inducement" selection, "fuel"-based sweep calls, momentum read by eye, the DXY/Fed bias, multi-scenario planning, and 1–5m refinement entries (killed by costs, see the research report §4.1).

## 12. Required logging per setup

Each setup records zone id, `t_b`, origin, zone bounds, filter values, order times, fill/cancel reason, MAE/MFE in R, and exit reason. This feeds the faithfulness review (M2) and later diagnostics such as win rate by hour, by pair, and by zone age.
