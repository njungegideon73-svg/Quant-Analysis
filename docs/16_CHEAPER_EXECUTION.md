# 16 — Cheaper execution for the NASDAQ 100 opening-range rules (exploratory, 2026-10-29)

**Question.** docs/15 found an opening-range effect on the NASDAQ 100 of about +0.1R before costs. Does a cheaper venue
than the Dukascopy CFD turn it into a tradeable edge? Same status as 15: exploration on opened data, not registered.

## Venues (costs as published or reported, October 2026; not checked on an account)

| Venue | Serves Kenya? | Spread | Commission | Round trip used (points) |
|---|---|---|---|---|
| **Dukascopy CFD** (as tested) | yes | 1–2 pt (data) | 3.5 per 100k notional per side (assumed) | ≈ 3.0 |
| **Pepperstone NAS100 CFD** | yes: Pepperstone Markets Kenya, CMA-licensed | 1.0 pt average (Pepperstone's site) | none on index CFDs | 1.0 + 2 × 0.5 slip = **2.0** |
| **MNQ micro futures, IBKR** | reportedly yes (third-party sources only) | 1 tick = 0.25 pt | ≈ $0.60 per side all-in (CME fee $0.35 + broker + NFA) at $2/pt = 0.30 pt | 0.25 + 2 × 0.25 slip + 0.6 = **1.35**; with 2-tick slip **1.85** |

**Method.** The zero-cost trades of 15 (mid fills, every day trading) minus `cost / stop distance`, with the 10% cost
rule re-applied at each venue's cost. Check: a flat 3-point cost reproduces the frozen engine's 2021–2026 result to
within 0.01R (N 30, 3R: +0.072R against +0.069R). Run twice on both copies of the data, identical. Script:
scratchpad `s5_recost.py`.

## Results, bias off (the bias-on configs are lower at every venue)

| Config | Venue | Cost per trade 2021–26 | EV 2014–20 | EV 2021–26 | Trades, t 2021–26 |
|---|---|---|---|---|---|
| N 30, 3R | Dukascopy (engine) | 0.03R | −0.065R | +0.069R | 1,379, t 2.2 |
| N 30, 3R | Pepperstone | 0.02R | −0.041R | +0.086R | 1,393, t 2.8 |
| N 30, 3R | **MNQ, 1 tick slip** | **0.013R** | −0.048R | **+0.093R** | 1,393, t 3.0 |
| N 15, 3R | MNQ, 1 tick slip | 0.017R | −0.002R | +0.094R | 1,430, t 2.5 |
| N 15, close | MNQ, 1 tick slip | 0.017R | −0.006R | +0.095R | 1,430, t 2.4 |
| N 5, close | MNQ, 1 tick slip | 0.025R | +0.048R | +0.112R | 1,428, t 2.1 |

## What this says

1. **Cheaper execution adds only about +0.02R.** Since 2021 the Dukascopy cost was already only 0.03–0.05R per trade,
   because the opening ranges are wide (median stop 81 points at N 15, 105 at N 30). Futures cut that to 0.01–0.02R.
2. **The limit now is the edge itself, not costs.** Even at futures cost the best is +0.09 to +0.11R in 2021–2026:
   just under P2 (+0.10R) and half the +0.20R target. In 2014–2020 it is about zero even at futures cost.
3. **Futures also trade more days.** At N 15/30 the 10% rule passes about 1,300–1,480 days in 2014–2020 instead of
   700–900, but the extra days add nothing: 2014–2020 stays at about zero.
4. **Still selected after looking** (15 §"Why this is still not a GO"). Nothing here changes the S5 verdict.

## Account size (MNQ, $2 per point)

| Stop at N 15, 2021–26 | Points | Risk per contract | Account for 1% risk | For 2% risk |
|---|---|---|---|---|
| Median | 81 | ≈ $165 | ≈ $16,500 | ≈ $8,300 |
| 90th percentile | 156 | ≈ $315 | ≈ $31,500 | ≈ $15,800 |

One MNQ contract is the smallest size, so a smaller account must skip the wide-range days (the better ones by cost)
or risk more than planned. A CFD (Pepperstone) can be sized finer, at about 0.007R more cost per trade than futures.

## Gold at micro-futures costs (MGC), added 2026-10-29

**Costs.** MGC: tick $0.10/oz = $1, so $10 per $1 move. The round trip used is 0.10 spread + 2 × 0.10 slip + 2 × 0.08
commission (assumed $0.80 per side all-in; the CME fee was not found) = **$0.46/oz**, against about $0.70 on Dukascopy.
Same method and checks as above (both runs identical; script `s5_recost.py RUNDIR XAUUSD`, `gold_buckets.py`).

| Config, bias off | EV 2014–20 (10% rule) | EV 2021–26 (10% rule) | Trades 2021–26, t | No cost rule: 2021–26 net |
|---|---|---|---|---|
| N 15, 3R | +0.064R | −0.024R | 987, t −0.6 | −0.020R |
| N 15, close | +0.029R | −0.028R | 987, t −0.6 | −0.003R |
| N 30, 3R | −0.015R | +0.004R | 1,197, t 0.1 | +0.009R |
| N 30, close | −0.007R | −0.001R | 1,197, t 0.0 | +0.009R |

The H4-bias and N 5 configs are no better (−0.10 to +0.03R in 2021–26). **Gold fails even at micro-futures costs.**

**Why the zero-cost effect does not survive:**
- **It sits on the small-range days.** Before costs, 2014–2020 days where the round trip is over 20% of the stop show
  +0.17 to +0.31R, but those costs take more than that. On the cheap days (cost under 5% of the stop) the effect is
  about zero since 2021 (−0.04 to +0.04R gross).
- **It shrank.** The gross edge fell from +0.12…+0.29R (2014–20) to +0.02…+0.08R (2021–26), when gold's moves and
  ranges grew.
- **Part of it may be the mid-price fills** of the zero-cost run: on 2–5 dollar ranges, the bid/ask bounce alone is a
  large share of R.

So the NASDAQ 100 is the only market left with a candidate edge (about +0.09R at futures cost), and a two-market
portfolio of ORB edges is not available from gold.

## Next, if pursued

- A **forward test from 2027** (data nobody has seen) of one pre-registered config, on the Pepperstone demo or the
  IBKR paper account, to confirm both the edge and the real fills. With ~230 trades a year it takes about two years to
  reach the 500 trades of P3.
- Before that: confirm IBKR accepts Kenyan residents for futures, and the real MNQ commission, on IBKR's own pages.

Sources: [Pepperstone indices](https://pepperstone.com/en/markets/indices/); CMA licences
([The Star, 2021](https://www.the-star.co.ke/business/kenya/2021-11-08-cma-licenses-two-new-forex-trading-brokers));
MNQ fees ([NinjaTrader MNQ](https://ninjatrader.com/margin-details/?symbol=MNQ)); IBKR and Kenya
([QuantWheel](https://quantwheel.com/marketplace/brokers/in/kenya-with-non-us-residents), third party).
