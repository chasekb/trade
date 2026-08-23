# TRADE-BL-0030 — Per-symbol reconciliation and update-rate evidence

Date: 2026-08-23 (evidence timestamps are UTC unless noted)
Status: investigation evidence; no causal fix claimed

## Executive conclusion

The available timestamped paper-session evidence proves that the worker started, preserved and evaluated all seven selected symbols, and produced no paper intents or fills during the observed window. The per-symbol terminal observations were `profitability_gate` for BTC-USD, ETH-USD, ADA-USD, and LTC-USD, and `no_signal` for SOL-USD, DOT-USD, and XRP-USD. All seven rows were reported as quote `refreshed/sufficient` and Transformer `warming_up`.

The frontend status/signal widgets poll at approximately three-second intervals, while the synthetic worker loop sleeps one second between ticks. The observed session evidence spans 43 seconds of sampled evaluations (04:34:41–04:35:24Z) and records 20 evaluations per symbol. This validates worker activity but does not prove a one-minute widget cadence. In live-data modes, sequential Coinbase requests and per-request timeouts can make producer progress substantially slower; no timestamped live quote/WebSocket trace is available here. Therefore the one-minute behavior remains unclassified beyond “not explained by the nominal frontend polling or synthetic one-second sleep alone.”

No real Coinbase order execution occurred. No order, replay, account mutation, configuration change, schema change, build, or local test was performed for this report.

## Reproduction and evidence inventory

The relevant paper session was started with the selected universe:

`BTC-USD, ETH-USD, SOL-USD, ADA-USD, DOT-USD, XRP-USD, LTC-USD`

Runtime identifiers and timestamps:

| Item | Evidence |
|---|---|
| Paper session | `sim_1787459668` |
| Session start | `2026-08-23T04:34:28Z` |
| Sample window | `2026-08-23T04:34:41Z` through `2026-08-23T04:35:24Z` |
| Session stop | `2026-08-23T04:35:38Z` |
| Evaluations | 140 total; 20 per selected symbol |
| Generated signals | 0 |
| Paper intents | 0 |
| Fills | 0 |
| Model reload | `2026-08-23T04:10:23.381Z`–`.382Z`; Transformer lookback 60, features 353, logged expected input dimension 0 |
| Separate PostgreSQL warning | `2026-08-23T04:31:54Z`; `pg_input_is_valid(text, unknown)` unavailable |

Supporting runtime artifact: `/home/kahlil/.hermes/cache/terminal-output/out-1787468841-3649500-8390.log` (captured by the Transformer-readiness investigation). Supporting durable evidence is recorded in the Kanban handoffs for `t_d892d89f`, `t_bd743ad8`, `t_4c2df7ea`, `t_995c2152`, and `t_bee966e2`.

Reproduction procedure represented by the evidence:

1. Recreate the supported stack with `podman-compose ... up -d --no-build`; remove the stale Created container that held host port 5432 if present.
2. Wait for PostgreSQL health, then start backend/frontend dependents.
3. Verify `GET http://127.0.0.1:8081/health` and database-backed `GET http://127.0.0.1:8081/api/trading/live/status`.
4. Start simulated paper mode with the seven-symbol array above and observe the session status/diagnostic outputs.
5. Reconcile the resulting per-symbol status, model metadata, gate reason, paper intent, and fill counters against the service code and persisted diagnostic paths.

The fresh no-build recreation completed with all services healthy at the smoke-test closeout. The backend health endpoint returned HTTP 200 and the database-backed live-status endpoint returned HTTP 200. No PostgreSQL 5432 bind error occurred; trade PostgreSQL used host port 5433 while an unrelated PostgreSQL container retained 5432.

## Per-symbol reconciliation

“Unavailable” means the evidence does not establish the value; it is not a zero or a pass. A terminal blocker is the last observed decision for the window, not proof that later gates would have passed or failed.

| Symbol | Freshness / fetch result | Signal | Model / readiness | Gate or blocker observed | Paper intent | Fill | Evidence / confidence |
|---|---|---|---|---|---:|---:|---|
| BTC-USD | Refreshed; sufficient | No generated signal recorded | `transformer-warming-up`; exact 60x353 sequence not ready in observed rows | `profitability_gate` | 0 | 0 | 20 evaluations; high confidence for window |
| ETH-USD | Refreshed; sufficient | No generated signal recorded | `transformer-warming-up`; exact 60x353 sequence not ready in observed rows | `profitability_gate` | 0 | 0 | 20 evaluations; high confidence for window |
| SOL-USD | Refreshed; sufficient | No signal | `transformer-warming-up`; exact 60x353 sequence not ready in observed rows | `no_signal` | 0 | 0 | 20 evaluations; high confidence for window |
| ADA-USD | Refreshed; sufficient | No generated signal recorded | `transformer-warming-up`; exact 60x353 sequence not ready in observed rows | `profitability_gate` | 0 | 0 | 20 evaluations; high confidence for window |
| DOT-USD | Refreshed; sufficient | No signal | `transformer-warming-up`; exact 60x353 sequence not ready in observed rows | `no_signal` | 0 | 0 | 20 evaluations; high confidence for window |
| XRP-USD | Refreshed; sufficient | No signal | `transformer-warming-up`; exact 60x353 sequence not ready in observed rows | `no_signal` | 0 | 0 | 20 evaluations; high confidence for window |
| LTC-USD | Refreshed; sufficient | No generated signal recorded | `transformer-warming-up`; exact 60x353 sequence not ready in observed rows | `profitability_gate` | 0 | 0 | 20 evaluations; high confidence for window |

Aggregate reconciliation: 7/7 selected symbols were evaluated, 140/140 expected per-symbol evaluations were observed, and 0/140 generated signals, intents, or fills were observed. The available evidence does not provide per-symbol quote prices, raw freshness ages, model output scores, fee/spread/slippage values, minimum-notional decisions, cash/position decisions, pending-order decisions, or successful per-symbol Transformer `Run()` results; those fields remain unavailable rather than inferred.

## Update-rate validation and one-minute classification

### Widget / consumer rate

`frontend/hooks/useTrading.ts:483-497` polls simulated status with a three-second interval and two-second stale time. `frontend/hooks/useTrading.ts:375-444` polls order-book signals at three seconds. For more than 50 symbols, the hook chunks requests in groups of 50 and merges successful results; failed chunks are surfaced through failure diagnostics rather than silently treated as complete. WebSocket messages can update the cache immediately, but the producer for those messages is not present in this repository and no timestamped WebSocket capture is available.

### Producer rate

`src/trading/SimulatedTradingService.cpp:1832-1935` runs the worker loop and sleeps one second after each iteration at approximately `:1907`. Synthetic mode does not perform Coinbase quote acquisition, so this is the nominal synthetic producer cadence. Live/live-parity mode fetches selected symbols sequentially before each tick (`:1851-1879`); `fetchLiveQuotes` attempts each symbol up to twice (`:879-937`). Coinbase requests have a 10-second Drogon timeout and 15-second future wait (`src/exchange/CoinbaseAdvancedClient.cpp:27,168-192`). Thus one-second sleep is not an upper bound for live-data tick completion.

Observed runtime calculation method: use the timestamped sample duration and count evaluations, then report the raw numerator/denominator rather than claiming a wall-clock producer rate not directly logged. The sample contains 140 evaluations across 43 seconds and 20 evaluations per symbol. This demonstrates active processing and approximately one per-symbol evaluation sequence over the sample, but it is not a direct measurement of widget refresh delivery, quote-fetch latency, or WebSocket event cadence.

Classification: the one-minute symptom is **unresolved / evidence-limited**. It is not explained by the nominal three-second frontend polling or one-second synthetic worker sleep alone. Plausible contributors include sequential live quote latency/failures, stale or absent WebSocket events, a different widget/query path, or backend/database recovery conditions, but none is proven by the available timestamped evidence. Do not treat the one-minute observation as a confirmed quote cap, symbol drop, or model-dimension failure.

## Causal findings and limits

### Proven for the paper window

- The worker started and processed all seven selected symbols: `src/trading/SimulatedTradingService.cpp:1832-1942,2175-2284`.
- The selected symbol array is preserved through the frontend payload, both simulated start route aliases, `PredictController`, and `startSession`: `frontend/components/dashboard/SimulatedTradingPanel.tsx:585-606`; `frontend/lib/api.ts:618-672,786-879`; `src/api/PredictController.cpp:1179-1201`; `src/trading/SimulatedTradingService.cpp:2189-2200`.
- Live quote failure can omit a symbol for that tick, but all seven paper-window rows were reported refreshed/sufficient. No symbol-drop explanation is supported for that window.
- The observed paper rows were stopped before executable intent/fill processing. Fee, spread, slippage, minimum-notional, cash/position, pending-order, and paper-fill outcomes are unavailable as reached-gate values; no causal result is inferred for them.
- Fail-closed behavior and the selected universe remain intact in the inspected paths. Ordinary simulated mode does not submit exchange orders; live-parity paper mode settles locally and does not call Coinbase order submission.

### Ruled out or separated

- `expected input dimension: 0` is not the Transformer feature width. `src/ml/ONNXModelManager.cpp:47-74,127-196` derives the scalar from 2-D regressor/classifier sessions, while Transformer metadata is 60x353. The transformer-only session loaded and the model manager was ready (`include/ml/ONNXModelManager.hpp:28-36`). This is misleading telemetry, not a proven dimensional blocker.
- The `pg_input_is_valid(text, unknown)` failure at 04:31:54Z affects signal pagination (`src/trading/SimulatedTradingService.cpp:2520`, `src/trading/LiveTradingService.cpp:3407`) and can return HTTP 200 with `total_signals=468`, `total_pages=94`, and `signals=[]`; it predates the paper session and did not suppress the 140 worker evaluations.
- The missing `is_closing_leg` column affects execution-reconciliation outcome loading, not worker signal generation or order dispatch.

### Open evidence gaps

- No raw per-line paper worker log is checked into this worktree, so exact per-symbol quote ages, signal scores, and successful Transformer invocation results are unavailable.
- No timestamped live quote latency/failure trace, frontend render trace, or WebSocket producer trace is available to classify the one-minute symptom.
- The exact timestamp of a missing-`is_closing_leg` runtime error is unavailable; source/history establish the failure path, while the 04:31:54Z artifact is a separate pagination warning.

## Individual issue status

| Issue | Owner / status | Evidence and impact |
|---|---|---|
| Coinbase TLS/network | Exchange/runtime owner; open, not tied causally to this paper window | `src/trading/SimulatedTradingService.cpp:879-937` fails fast for TLS/DNS/exchange-response classes and omits failed quotes for that tick. The seven paper rows were refreshed/sufficient. No timestamped raw YB-USD/TLS event ties this lead to `sim_1787459668`. |
| Transformer input/readiness | ML/trading owner; dimension-zero lead ruled out, paper-window warm-up confirmed | Reload logged 60x353 and expected input dimension 0 at 04:10:23Z. The scalar is regressor/classifier telemetry; Transformer readiness requires exact 60x353 rows in `src/trading/SimulatedTradingService.cpp:1201-1263`. All seven observed rows were warming up, so warm-up blocked readiness during this window. Successful per-symbol inference remains unobserved. |
| `is_closing_leg` schema mismatch | Database/API owner; confirmed reconciliation-completeness blocker, not worker suppression | `src/ml/DataCollector.cpp:41-60` can create `individual_trades` without the column; service schema repair is in `src/trading/SimulatedTradingService.cpp:338-365` and `src/trading/LiveTradingService.cpp:356-383`. `src/api/PredictController.cpp:1762-1792` catches the missing-column failure and can return partial signals with empty outcomes and an error. |

## Tests, checks, and limitations

Read-only source inspection covered the files and line ranges cited above. Runtime checks covered no-build stack recreation, service health, `GET /health`, `GET /api/trading/live/status`, and status evidence for `sim_1787459668`. No local Docker/Podman image build, CMake build, C++ test, frontend build, order submission, event replay, schema mutation, or account mutation was run as part of this report.

The report is evidence-backed but not a fix or deployment validation. A stronger one-minute classification requires a fresh controlled capture containing frontend request/render timestamps, backend tick timestamps, per-symbol quote fetch start/end and failure categories, Transformer readiness transitions, WebSocket event timestamps, and the exact widget query path. Until that capture exists, retain this investigation as open and preserve the selected universe and fail-closed execution semantics.
