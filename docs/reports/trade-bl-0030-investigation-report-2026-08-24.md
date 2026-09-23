# TRADE-BL-0030 investigation report

Date: 2026-08-24
Evidence timestamps: UTC
Status: evidence-backed investigation; no causal fix claimed

## Executive summary

A controlled `live_parity` simulated-trading paper session processed all seven selected symbols, performed 140 evaluations (20 per symbol), generated zero signals, created zero paper intents, and produced zero fills. Every symbol reached refreshed/sufficient quote state. The last observed per-symbol decisions were `profitability_gate` for BTC-USD, ETH-USD, ADA-USD, and LTC-USD, and `no_signal` for SOL-USD, DOT-USD, and XRP-USD. All seven observed Transformer status rows were `warming_up`.

The observed roughly one-minute behavior remains unresolved and evidence-limited. It is not explained by the nominal three-second frontend polling or one-second synthetic worker sleep alone, but the retained evidence does not include the frontend request/render timestamps, live quote request timings, WebSocket frames, or a per-widget trace needed to identify the responsible path. Sequential live-data quote acquisition, a stale/absent WebSocket event path, a different widget query, and backend/database recovery conditions remain plausible but unproven.

The `expected input dimension: 0` log is ruled out as a Transformer feature-width failure: the Transformer metadata was 60x353 and scalar input dimension is derived from separate 2-D regressor/classifier sessions. Exact 60x353 per-symbol readiness was not reached in the observed rows and is a confirmed window-specific blocker. The `is_closing_leg` mismatch is a confirmed reconciliation-completeness/schema blocker when a legacy table is queried before service schema repair, not a worker or order-dispatch blocker. A separate `pg_input_is_valid(text, unknown)` compatibility error affected signal pagination and predates the paper session; it did not suppress the 140 evaluations.

No real Coinbase order execution occurred. Fail-closed semantics and the selected universe remained intact. This report does not claim that any code change fixes the observed behavior.

## Scope, provenance, and safety boundary

The investigation used read-only source inspection and a safe paper-session reproduction. No real Coinbase order, replay, account mutation, configuration mutation, schema mutation, retraining, or deployment was performed. No secret-bearing files, credentials, cookies, or tokens are included.

The runtime evidence was preserved in the terminal capture:

- `/home/kahlil/.hermes/cache/terminal-output/out-1787468841-3649500-8390.log`

The source inventory was prepared against the trade repository around commit `8af7838c9112e4f88c0f358504877d054ce9eb0c`; the report incorporates the later reconciliation and validation handoffs without treating later source/history as proof that the paper session was rerun on that code. The exact raw HTTP payload, response bodies, browser network trace, WebSocket frames, per-request timestamps, and model identifier were not retained.

### Source-baseline traceability note

All `src/...`, `frontend/...`, and `CMakeLists.txt` line/function references in this report are references to the investigated source baseline `8af7838c9112e4f88c0f358504877d054ce9eb0c`. The trade report checkout at this branch does contain the cited C++ and frontend paths; the earlier “documentation-only checkout” limitation referred only to the separate Hermes reviewer checkout used during review, not to this trade repository. Reviewers should still resolve source references against the pinned baseline (or its corresponding repository history) because this report does not assert that the retained paper session was rerun on a later source revision.

## Reproduction context and exact steps

### Observed identifiers and timestamps

| Field | Value | Evidence status |
|---|---|---|
| Frontend surface | Simulated Trading tab / `SimulatedTradingPanel` | Source-verified |
| Strategy | `ml_enhanced_orderbook` | Source/task context |
| Execution mode | `live_parity` paper mode: Coinbase public market data with local paper settlement | Source and runtime context |
| Session id | `sim_1787459668` | Runtime evidence |
| Session start | `2026-08-23T04:34:28Z` | Runtime evidence |
| Evidence sample | `2026-08-23T04:34:41Z`–`2026-08-23T04:35:24Z` | Runtime evidence |
| Stop requested/settled | `2026-08-23T04:35:38Z` | Runtime evidence |
| Zero-trade interval | `2026-08-23T04:34:28Z`–`2026-08-23T04:35:38Z` | Runtime evidence; sampled interval also had zero intents/fills |
| Request/correlation ids | No request id or trace id retained; session id is the only stable runtime identifier | Missing evidence |
| Model id/name/version | Not available in retained session evidence | Missing evidence |
| Transformer reload | `2026-08-23T04:10:23.381Z`–`.382Z`; lookback 60, features 353; scalar expected input dimension log reported 0 | Runtime evidence |
| Separate database warning | `2026-08-23T04:31:54.527Z` and later repeats; `pg_input_is_valid(text, unknown)` unavailable | Runtime evidence, separate from session blocker |

### Reproduction procedure

1. Recreate the supported stack with `podman-compose ... up -d --no-build`, removing only a stale Created container that holds the conflicting host PostgreSQL port if present; wait for PostgreSQL health and start the backend/frontend dependents.
2. Verify `GET http://127.0.0.1:8081/health` and database-backed `GET http://127.0.0.1:8081/api/trading/live/status`.
3. Open the Simulated Trading tab, preserve the selected symbol array below, select `ML-Enhanced Order Book`, and select Coinbase live-data paper mode (`parameters.execution_mode=live_parity`). Do not use Live Trading.
4. Start the session. The frontend builds the payload in `frontend/components/dashboard/SimulatedTradingPanel.tsx:585-606`; `frontend/lib/api.ts:618-672` serializes it and tries `/api/trading/simulated/start`, using the legacy alias only after endpoint failure (`:786-879`).
5. The backend receives and forwards the request at `src/api/PredictController.cpp:1179-1201`; `SimulatedTradingService::startSession` copies the symbols and starts the worker (`src/trading/SimulatedTradingService.cpp:2142-2284`).
6. During the run, retain status, signal, stats, reconciliation, browser-network, and WebSocket timestamps. Stop once and record final status, counts, model metadata, gate reason, intents, and fills. The retained run produced the identifiers and counts in this report.

The exact serialized request JSON, HTTP headers excluding secrets, response body, browser click time, request/response times, and model id/version were not retained and must not be reconstructed from source.

## Frontend context and update-rate evidence

The simulated panel is mounted by `frontend/app/page.tsx:56-81`. The selected symbol array is constructed and submitted by `frontend/components/dashboard/SimulatedTradingPanel.tsx:585-606`. The API client forwards it through the canonical and legacy start payload paths in `frontend/lib/api.ts:618-672,786-879`.

| Surface | Configured rate/behavior | What was measured | Interpretation |
|---|---|---|---|
| Simulated status widget | `frontend/hooks/useTrading.ts:66-99`, 5-second refetch | No browser/network timestamps retained | Cannot explain a measured one-minute interval by itself |
| Simulated order-book signals | `frontend/hooks/useTrading.ts:375-445`, 3-second refetch | No browser/network timestamps retained | Nominal polling is not one minute |
| Simulated stats | `frontend/hooks/useTrading.ts:483-497`, 3-second refetch | No browser/network timestamps retained | Nominal polling is not one minute |
| Execution reconciliation widget | `frontend/hooks/useExecutionReconciliation.ts:29-33`, 60-second poll | Widget-specific timestamps unavailable | Separate reconciliation surface; not proof of producer/signal cadence |
| WebSocket cache updates | `/ws`; local heartbeat every 30 seconds | Frame timestamps unavailable; producer not retained | Delivery/cache behavior remains open |

Requests for more than 50 symbols are chunked in groups of 50 and merged before display pagination. No frontend universe cap was found, and display sorting/pagination cannot account for missing worker evaluations in this seven-symbol run.

## Selected universe and data-flow trace

The selected universe, in order, was:

`BTC-USD, ETH-USD, SOL-USD, ADA-USD, DOT-USD, XRP-USD, LTC-USD`

The panel stores the array; `apiClient.startTrading` forwards it through the start payload; `PredictController` forwards it unchanged; and `SimulatedTradingService::startSession` copies every symbol without dedupe, cap, or sort. Only an empty input receives the service fallback list. `workerLoop` snapshots the selected array and attempts every selected symbol in live-parity quote acquisition. A failed or empty quote is intentionally excluded from that tick, but all seven symbols in this window were reported refreshed/sufficient.

Symbol-keyed maps may serialize lexicographically, and signal endpoints/display pagination may reorder or hide rows. Those presentation behaviors do not cap or drop worker coverage. Runtime evidence confirms all seven selected symbols reached evaluation in this window.

## Complete per-symbol reconciliation

“Unavailable” means the evidence does not establish a value; it is not a zero or a pass. A terminal gate is the last observed decision for this window, not proof that later fee, sizing, position, or fill gates would have passed or failed.

The seven rows below are transcribed from the immutable per-symbol reconciliation artifact at commit [`784bb9d8bc1edf18fe92e155b860042767f0aceb`](https://github.com/chasekb/trade/blob/784bb9d8bc1edf18fe92e155b860042767f0aceb/docs/reports/trade-bl-0030-per-symbol-reconciliation-2026-08-23.md). The underlying runtime counts and selected-symbol list are also recorded in the immutable evidence inventory at commit [`bdae98e93fe4a7e7a92a2128b2f3265ba6dcaf30`](https://github.com/chasekb/trade/blob/bdae98e93fe4a7e7a92a2128b2f3265ba6dcaf30/docs/investigations/trade-bl-0030-evidence-inventory-2026-08-23.md). Row-specific provenance is: BTC-USD, ETH-USD, ADA-USD, and LTC-USD map to the reconciliation artifact’s `profitability_gate` rows; SOL-USD, DOT-USD, and XRP-USD map to its `no_signal` rows. The same artifact supplies the 20-evaluation count and `warming_up` Transformer state for every row. The runtime terminal capture named above is not durably available to downstream reviewers; its reported worker start/stop lines (2658/2666) are retained only in the upstream handoff, so those lines are not presented as independently retrievable evidence.

| Symbol | Freshness/fetch | Evaluations | Transformer state | Signal / terminal gate | Paper intents | Fills | Classification |
|---|---|---:|---|---|---:|---:|---|
| BTC-USD | Refreshed/sufficient | 20 | `warming_up`; exact 60x353 readiness not observed | No generated signal recorded; `profitability_gate` | 0 | 0 | Confirmed blocker for this window |
| ETH-USD | Refreshed/sufficient | 20 | `warming_up`; exact 60x353 readiness not observed | No generated signal recorded; `profitability_gate` | 0 | 0 | Confirmed blocker for this window |
| SOL-USD | Refreshed/sufficient | 20 | `warming_up`; exact 60x353 readiness not observed | No signal; `no_signal` | 0 | 0 | Confirmed no-trade state; not infrastructure proof |
| ADA-USD | Refreshed/sufficient | 20 | `warming_up`; exact 60x353 readiness not observed | No generated signal recorded; `profitability_gate` | 0 | 0 | Confirmed blocker for this window |
| DOT-USD | Refreshed/sufficient | 20 | `warming_up`; exact 60x353 readiness not observed | No signal; `no_signal` | 0 | 0 | Confirmed no-trade state; not infrastructure proof |
| XRP-USD | Refreshed/sufficient | 20 | `warming_up`; exact 60x353 readiness not observed | No signal; `no_signal` | 0 | 0 | Confirmed no-trade state; not infrastructure proof |
| LTC-USD | Refreshed/sufficient | 20 | `warming_up`; exact 60x353 readiness not observed | No generated signal recorded; `profitability_gate` | 0 | 0 | Confirmed blocker for this window |

Aggregate: 7/7 symbols evaluated, 140 total evaluations, 0 generated signals, 0 paper intents, and 0 fills. Per-symbol quote prices, freshness ages, model scores, fee/spread/slippage values, minimum-notional outcomes, cash/position outcomes, pending-order outcomes, and successful Transformer `Run()` results are unavailable.

## Producer cadence and one-minute classification

`src/trading/SimulatedTradingService.cpp:1832-1935` runs the worker loop and sleeps one second after each iteration (approximately `:1907`). This is nominal synthetic cadence, not a live-data upper bound. Live/live-parity mode fetches selected symbols sequentially (`:1851-1879`); `fetchLiveQuotes` retries each symbol up to twice (`:879-937`). Coinbase requests use a 10-second Drogon timeout and 15-second future wait (`src/exchange/CoinbaseAdvancedClient.cpp:27,168-192`), so live quote latency/failure can extend a loop.

The preserved sample spans 43 seconds and contains 140 evaluations, but it does not provide enough producer/request/event timestamps to derive a wall-clock widget, quote, or WebSocket rate. Classification: **unresolved / evidence-limited**. The behavior is not explained by nominal three-second frontend polling or one-second synthetic sleep alone. It must not be labeled a confirmed quote cap, symbol drop, Transformer dimensional failure, or single root cause.

## Proven causes/findings for this window

- The worker started and processed all seven selected symbols: `src/trading/SimulatedTradingService.cpp:1832-1942,2175-2284`.
- All seven had refreshed/sufficient market data and 20 evaluations each.
- Zero signals, intents, and fills were observed; four symbols stopped at `profitability_gate` and three at `no_signal`.
- The observed rows were Transformer-warming-up; exact 60x353 readiness was not reached in the retained rows.
- `live_parity` is paper-only; ordinary simulated mode has no exchange order client and paper settlement is local.
- Fail-closed behavior was preserved: missing/failed live quotes are not evaluated/executed for that tick, and no executable path was reached.
- The selected universe survived frontend payload, controller, session, and worker boundaries without a cap, dedupe, or sort.

These findings establish what happened in the retained window. They do not prove why a roughly one-minute display behavior was observed.

## Ruled-out or separated leads

- `expected input dimension: 0` is not the Transformer feature width. `src/ml/ONNXModelManager.cpp:47-74,127-196,222-252` derives scalar input dimension from 2-D regressor/classifier sessions while Transformer metadata is separate 60x353. This is misleading telemetry, not a proven Transformer dimensional blocker.
- A missing `is_closing_leg` column is not supported as the cause of worker suppression; it affects reconciliation outcome loading.
- The separate `pg_input_is_valid(text, unknown)` failure at approximately 04:31:54Z affects signal pagination (`src/trading/SimulatedTradingService.cpp:2520`, `src/trading/LiveTradingService.cpp:3407`) and can return HTTP 200 with advertised rows/pages but empty signal rows. It predates the session and did not suppress 140 evaluations.
- The separate YB-USD Coinbase TLS/network event is not tied to this seven-symbol session; all seven session symbols were refreshed/sufficient.
- No frontend symbol cap or display pagination behavior explains missing worker evaluations.

## Open blockers and evidence gaps

- No raw per-line worker log, per-symbol quote start/end/retry/freshness timestamps, or successful Transformer per-symbol inference trace.
- No frontend request/render timestamps, cache-hit data, WebSocket frame timestamps, or retained identification of the widget that appeared to update at roughly one minute.
- No exact wire request/response payload, request id, trace id, model id/version, or browser click timestamp.
- No exact timestamped missing-`is_closing_leg` runtime error or schema snapshot at reconciliation time.
- No independent reached-gate evidence for fee/spread/slippage, minimum-notional, cash/position, pending-order, paper-intent, or fill decisions after the terminal observations.

## Individual issue status

### Coinbase TLS/network

- Owner: exchange/runtime transport.
- Status: **OPEN as a separate issue; not proven causal for `sim_1787459668`.**
- Evidence: `CoinbaseAdvancedClient::request` (`src/exchange/CoinbaseAdvancedClient.cpp:168-200`) reports HTTPS/response failures; `getOrderBook` is `:514-560`; `fetchLiveQuotes` (`src/trading/SimulatedTradingService.cpp:879-937`) retries and omits a failed symbol from that tick. A separate preserved pane summary describes one YB-USD failure after retry, but its raw error, request timestamps, and session correlation are unavailable. All seven symbols in the paper window were refreshed/sufficient.
- Required evidence: fresh capture with raw TLS/DNS error, selected symbol, request start/end, retry count, recovery, and synchronized session/status timestamps.

### Transformer input/readiness

- Owner: ML/trading.
- Status: **`input_dim=0` dimensional-blocker lead RULED OUT; exact per-symbol warm-up blocker CONFIRMED for the observed window; successful `Run()` reachability OPEN.**
- Evidence: reload logged lookback 60/features 353 at `2026-08-23T04:10:23.381Z`–`.382Z`; `ONNXModelManager` scalar input dimension comes from 2-D regressor/classifier sessions (`src/ml/ONNXModelManager.cpp:170-196`), while Transformer metadata is handled at `:47-74,127-148`. Simulation requires an exact 60x353 sequence and labels insufficient rows `warming_up` (`src/trading/SimulatedTradingService.cpp:1201-1263,1390-1420`). All seven observed rows were warming up.
- Required evidence: per-symbol sequence shape/readiness transition, Transformer `Run()` success/failure, output dimensions, and timestamps in a fresh controlled session.

### `is_closing_leg` schema mismatch

- Owner: database/API reconciliation.
- Status: **CONFIRMED reconciliation-completeness blocker before schema repair; NOT a worker/order blocker.**
- Evidence: `src/ml/DataCollector.cpp:41-60` can create `individual_trades` without the column. Service repair exists in `src/trading/SimulatedTradingService.cpp:338-365` and `src/trading/LiveTradingService.cpp:356-383`. Reconciliation selects it in `src/api/PredictController.cpp:1762-1785`, catches the exception at `:1789-1792`, and may return partial signals with empty outcomes and an error. The exact missing-column runtime timestamp was not retained. The separate `pg_input_is_valid` compatibility failure remains a diagnostic/pagination issue; a later history fix is not treated as applied to this report's baseline.
- Required evidence/action: verify migration or endpoint preflight against a legacy-created table, retain the exact database error and schema snapshot, and then validate reconciliation completeness. Do not infer worker suppression from this issue.

## Tests, checks, queries, and artifacts

Checks and evidence used:

- Read-only source inspection of the frontend payload/polling paths, `PredictController`, `SimulatedTradingService`, `LiveTradingService`, `ONNXModelManager`, `DataCollector`, `CoinbaseAdvancedClient`, and `test_execution_reconciliation.cpp`.
- Static CMake inventory: `CMakeLists.txt:166-171` (`test_execution_reconciliation`), `:173-200` (Coinbase tests), and `:212-234` (`test_transformer_onnx_export`).
- Runtime no-build stack health checks: `GET http://127.0.0.1:8081/health`, `GET http://127.0.0.1:8081/api/trading/live/status`, and the supported frontend/backend smoke path. The backend health endpoint returned HTTP 200 in the preserved runtime handoff.
- Runtime/session reconciliation for `sim_1787459668`, including seven-symbol coverage, 140 evaluations, zero intents/fills, terminal gates, and Transformer state.
- Preserved terminal artifact: `/home/kahlil/.hermes/cache/terminal-output/out-1787468841-3649500-8390.log`.
- Supporting immutable evidence artifacts: [evidence inventory at commit `bdae98e93fe4a7e7a92a2128b2f3265ba6dcaf30`](https://github.com/chasekb/trade/blob/bdae98e93fe4a7e7a92a2128b2f3265ba6dcaf30/docs/investigations/trade-bl-0030-evidence-inventory-2026-08-23.md) and [per-symbol reconciliation at commit `784bb9d8bc1edf18fe92e155b860042767f0aceb`](https://github.com/chasekb/trade/blob/784bb9d8bc1edf18fe92e155b860042767f0aceb/docs/reports/trade-bl-0030-per-symbol-reconciliation-2026-08-23.md). These artifacts are the sources for the runtime aggregate and seven table rows; this report is the consolidated checked-in handoff for reviewers.

No local Docker/Podman image build, CMake build, C++ unit test, frontend build, replay, order submission, account mutation, or schema mutation was performed under the remote-only verification policy. Remote CI is the required compile/build gate for this documentation change.

## Safe code changes identified, not claimed as completed

1. Promote and verify the later removal of unsupported `pg_input_is_valid` calls in both read-only signal/order-book paths, with a regression test against the supported PostgreSQL version.
2. Add an explicit migration or reconciliation endpoint preflight that guarantees `is_closing_leg` before outcome selection, while preserving partial-result/error semantics until schema readiness is proven.
3. Add timestamped per-symbol quote/failure/retry evidence and Transformer sequence/readiness/`Run()` telemetry.
4. Capture frontend request/render/cache/WebSocket timestamps for the exact widget before classifying the one-minute behavior.

These are follow-up actions, not fixes demonstrated by this report. Correlation alone is insufficient to claim resolution.

## Final safety conclusion

The selected seven-symbol universe remained intact from frontend payload through backend session and worker evaluation. Fail-closed behavior remained intact, and no real Coinbase order execution occurred: the observed run created zero intents and zero fills, and `live_parity` uses public market data with local paper settlement rather than the live order-dispatch path. The investigation should remain open for the missing runtime traces and should not be closed as a single-cause fix based on the current evidence.
