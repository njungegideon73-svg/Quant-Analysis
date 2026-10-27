# 04 — Execution, Risk & Infrastructure

## 1. Live runner (M6+)

A single Python process that wraps the **same strategy object** the backtester uses.

```
Connection (demo, M6): the **JForex SDK** (`DDS2-jClient-JForex`, Dukascopy's public Maven repo, v3.6.51 on 2026-10-27) in a headless Java process that logs in with the `.env` credentials, streams bars/ticks to the Python strategy and executes its intents over a local socket. The strategy stays pure Python, shared with the backtest. The cTrader notes below apply if live moves to Pepperstone (M7).

every M15 close (+5 s grace):
  1. fetch last closed M15/H4 bars per pair          ── ProtoOAGetTrendbarsReq
  2. update incremental features → strategy.on_bar() → intents
  3. risk guard (§3) approves / rejects each intent
  4. reconcile with broker state                     ── ProtoOAReconcileReq (open positions + pending orders)
  5. place / cancel / amend orders                   ── ProtoOANewOrderReq / ProtoOACancelOrderReq / ProtoOAAmendOrderReq
background:
  - execution events  (ProtoOAExecutionEvent) → fills, SL/TP exits → SQLite + alerts
  - spot subscription (ProtoOASubscribeSpotsReq) → spread guard, stale-data guard (no tick > 2 min in session → alert)
  - token refresh before expiry; heartbeat every 10 s
```

| Item | Design |
|---|---|
| Order type | `LIMIT` with `expirationTimestamp` (= zone expiry) and absolute `stopLoss` / `takeProfit` set on the order. **SL/TP live at the broker**, so a crash or disconnect never leaves an unprotected position. Exact field behaviour is verified on demo at M6. |
| Idempotency | `label`/`clientOrderId` = hash(pair, zone id, side). Reconciliation never duplicates an order. |
| Session window | cTrader has no "active hours" orders, so the runner cancels at the window close and re-places at the open if the zone is still valid (exactly what the backtest simulates). |
| Weekend | Cancel pending orders Fri 15:00 NY and flatten positions Fri 16:30 NY. |
| Restart | On start: load SQLite state, rebuild features from history, reconcile, then resume. The state is rebuilt from data, never trusted blindly. |
| Environments | `CTRADER_ENV=demo` is the default (`demo.ctraderapi.com`). Live requires `CTRADER_ENV=live` **and** the CLI flag `--i-understand-live`. |

## 2. Position sizing

- `units = floor(risk_pct · NAV / (|entry − stop| · pip_value_usd))`, with `risk_pct = 0.005` (0.001 during M7 micro).
- The pip value is converted with live quotes (for example USDJPY → USD/JPY rate).
- NAV is read from the broker account summary before each order.

## 3. Risk guard (pre-trade + continuous)

| Guard | Rule | Action |
|---|---|---|
| Per-trade risk | ≤ risk_pct of NAV after rounding | Reject |
| Concurrency | ≤ 1 per pair, ≤ 4 total, ≤ 2 same-currency direction | Reject |
| Spread guard | Current spread > 3× the pair's 30-day median for that hour | Don't place the order now; retry next bar |
| Daily loss | Realised + open P&L ≤ −2% NAV for the day | Cancel pending orders, no new orders until next day |
| **Drawdown halt** | Drawdown from peak > the **Monte Carlo 95th-percentile DD** from 03 §5 (~20% at 0.5% risk if the edge matches the spec) | Flatten, stop the runner, alert. Restart is manual after review: the live edge is statistically likely broken. |
| Losing streak | Streak > the Monte Carlo 99th percentile (~25) | Alert + review (not an auto-halt) |
| Kill switch | `ta kill` (CLI), a Telegram `/kill`, or a `KILL` file in the run dir | Cancel all, flatten all, stop |
| Stale data / clock | No candle for an expected bar, or system clock drift > 2 s (chrony/NTP) | Pause trading, alert |

## 4. Monitoring & alerts

- **Telegram bot** (optional, recommended): fills, exits (with R), errors, guard triggers, a daily summary (trades, R, NAV, drawdown) and a weekly comparison against the backtest expectation band.
- **Logs:** structured JSON lines with daily rotation, kept for 90 days.
- **SQLite** `live/state.db` holds orders, fills, positions, guard events and a heartbeat. A weekly job replays the backtester over the live period and writes a parity report (03 §6).

## 5. Infrastructure

| Stage | Where | Notes |
|---|---|---|
| Research (M0–M5) | This machine (4 cores, 15 GB RAM) | Everything local; no cloud cost |
| Forward test (M6) | This machine as a `systemd --user` service with auto-restart | Fine if it is on 24/5; otherwise move to a VPS early |
| Live (M7) | A small Linux VPS (1–2 vCPU, 2 GB, ~$5–10/mo) | The 15-minute strategy isn't latency-sensitive, so any reliable region works |

- **Secrets:** a `.env` file (`CTRADER_CLIENT_ID`, `CTRADER_CLIENT_SECRET`, `CTRADER_ACCESS_TOKEN`, `CTRADER_REFRESH_TOKEN`, `CTRADER_ACCOUNT_ID`, `CTRADER_ENV`, optional `TELEGRAM_TOKEN`/`TELEGRAM_CHAT_ID`). It is git-ignored, has `chmod 600`, and is never logged.
- **Backups:** `live/state.db` and `runs/registry.duckdb` copied nightly. Raw data can be re-downloaded, so it isn't backed up.
- **Version control:** git. Each live deployment is pinned to a tagged commit plus the config hash that passed validation. The runner refuses to start if the config hash isn't in the "approved" list.

## 6. Repository layout (built in M0)

```
Quant Analysis/
├─ docs/                    # this documentation
├─ research/                # phase-1 transcripts, notes, report
├─ src/ta/
│  ├─ data/                 # dukascopy download, resample, quality
│  ├─ features/             # pivots, structure, zones, fvg, liquidity (incremental)
│  ├─ strategy/s1.py        # S1 rules → intents (pure)
│  ├─ engine/               # backtest driver, broker sim, costs, portfolio
│  ├─ validate/             # grid, walk-forward, bootstrap, DSR, monte carlo
│  ├─ live/                 # ctrader adapter, runner, risk guard, alerts
│  └─ cli.py                # `ta download|backtest|grid|report|live|kill`
├─ configs/                 # s1_base.yaml, grids, approved.yaml
├─ tests/                   # fixtures, prefix-invariance, fills, sizing
├─ data/  runs/  live/      # git-ignored
└─ pyproject.toml  uv.lock  .env.example
```

## 7. Promotion gates

`backtest GO (03 §5)` → `forward test pass (03 §6)` → `live micro 0.1% × 2 months inside MC band` → `0.5% risk`

A gate can be failed but never skipped.
