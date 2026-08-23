# TRADE-BL-0030 evidence inventory

Date: 2026-08-23
Scope: evidence inventory for the Simulated Trading live-data paper-session observation. This is an investigation handoff, not a root-cause or fix claim.

## Evidence boundary and provenance

The strongest runtime evidence is the preserved read-only paper-session reconciliation recorded in the Kanban investigation handoffs. The repository was inspected at commit `8af7838c9112e4f88c0f358504877d054ce9eb0c` (`feat(trade): remove live quote cadence enforcement`). No application files were changed by the investigation tasks; no local build, CMake build, C++ test, replay, account mutation, or exchange order was performed.

The runtime evidence is not a raw per-line application log checked into this worktree. Counts and decisions below are transcribed from the preserved runtime capture/handoffs. Exact raw request/response bodies, WebSocket frames, browser network traces, and per-request timestamps were not retained. Where evidence is absent, this inventory says so explicitly.

## Reproduction context

| Field | Directly observed or verified value | Evidence status |
|---|---|---|
| Frontend route | Simulated Trading tab, mounted by `frontend/app/page.tsx:56-81` and `SimulatedTradingPanel` | Source-verified |
| Execution mode | `live_parity` paper mode (Coinbase public market data; local paper settlement) | Source/code plus runtime session context |
| Strategy | `ml_enhanced_orderbook` | Source-verified and runtime task specification |
| Session id | `sim_1787459668` | Directly observed in preserved runtime evidence |
| Session start | `2026-08-23T04:34:28Z` | Directly observed |
| Evidence sample | `2026-08-23T04:34:41Z` through `2026-08-23T04:35:24Z` | Directly observed |
| Stop requested/settled | `2026-08-23T04:35:38Z` | Directly observed |
| Zero-trade interval | `[2026-08-23T04:34:28Z, 2026-08-23T04:35:38Z]`; the sampled interval also had zero intents/fills | Directly observed; do not replace with an inferred UI duration |
| Selected symbols (ordered) | `BTC-USD`, `ETH-USD`, `SOL-USD`, `ADA-USD`, `DOT-USD`, `XRP-USD`, `LTC-USD` | Directly observed in session evidence |
| Model id/name/version | Not available in the preserved session evidence | Missing evidence |
| Transformer reload | `2026-08-23T04:10:23.381Z`-`.382Z`: lookback 60, features 353; log also reported expected input dimension 0 | Directly observed in preserved runtime log |
| Exact start endpoint/payload | Endpoint contract is verified, but exact wire capture is unavailable | Missing evidence |
| Request/correlation ids | No request id or trace id retained; session id above is the only stable runtime identifier | Missing evidence |
| Real execution | No live Coinbase order execution; `live_parity` cannot enter the live dispatch path | Source-verified and investigation safety record |

### Reproduction path

1. In the Simulated Trading panel, preserve the selected symbol array and choose `ML-Enhanced Order Book`.
2. Select Coinbase live-data paper mode (`parameters.execution_mode=live_parity`), not synthetic simulation and not Live Trading.
3. Start the session. The frontend constructs the payload in `frontend/components/dashboard/SimulatedTradingPanel.tsx:585-606`; `frontend/lib/api.ts:618-672` serializes it and tries `/api/trading/simulated/start`, then the legacy alias only on endpoint failure (`:786-879`).
4. The backend accepts `simulated`/`live_parity` and forwards the payload at `src/api/PredictController.cpp:1179-1201`. `SimulatedTradingService::startSession` copies the supplied symbols and starts the worker (`src/trading/SimulatedTradingService.cpp:2142-2284`).
5. Observe status/signals/stats during the session, then stop once and retain final status. The preserved run returned the session and counts above.

The exact serialized JSON, HTTP headers (excluding secrets), HTTP response body, browser click timestamp, and request/response timestamps were not retained, so this inventory does not reconstruct them from source.

## Producer and frontend cadence evidence

| Producer/consumer | Configured behavior | Runtime measurement | Interpretation |
|---|---|---|---|
| Simulated worker | One loop iteration, then one-second sleep (`workerLoop`, `src/trading/SimulatedTradingService.cpp:1832-1935`) | Per-tick runtime timestamps unavailable | Code cadence only; sequential quote latency can extend a loop |
| Live quote acquisition | Sequential per selected symbol; up to two attempts, with TLS/DNS/exchange-response failures breaking retry (`fetchLiveQuotes`, `:879-937`) | Per-symbol request timings unavailable | A failed quote is excluded from that tick's signal/execution path |
| Simulated status query | 5-second refetch (`frontend/hooks/useTrading.ts:66-99`) | Browser/network capture unavailable | Cannot explain a measured one-minute display interval by itself |
| Simulated stats query | 3-second refetch (`frontend/hooks/useTrading.ts:483-497`) | Browser/network capture unavailable | Explicit configuration is not one minute |
| Simulated order-book signals | 3-second refetch (`frontend/hooks/useTrading.ts:375-445`) | Browser/network capture unavailable | Explicit configuration is not one minute |
| Execution reconciliation | 60-second poll (`frontend/hooks/useExecutionReconciliation.ts:29-33`) | Widget-specific runtime timestamps unavailable | This is a separate reconciliation surface, not proof of signal/producer cadence |
| WebSocket | `/ws`, local heartbeat every 30 seconds; event cache updates are consumed by `useTrading.ts` | Frame timestamps unavailable | Event delivery/cache behavior remains an evidence gap |

The observed zero-trade interval is bounded by the session start and stop timestamps above. A roughly one-minute UI behavior cannot be classified as frontend polling, worker cadence, quote latency, or WebSocket behavior from the available data: runtime producer/request/event timestamps were not retained.

## Per-symbol reconciliation

All seven symbols were refreshed/sufficient and evaluated 20 times each in the preserved sample. There were 140 evaluations, 0 generated signals, 0 executable paper intents, and 0 fills.

| Symbol | Freshness/fetch | Evaluations | Transformer state | Signal/terminal gate observation | Paper intent | Fill | Classification |
|---|---|---:|---|---|---:|---:|---|
| BTC-USD | refreshed/sufficient | 20 | warming_up on observed rows | profitability gate | 0 | 0 | Confirmed blocker for this window |
| ETH-USD | refreshed/sufficient | 20 | warming_up on observed rows | profitability gate | 0 | 0 | Confirmed blocker for this window |
| SOL-USD | refreshed/sufficient | 20 | warming_up on observed rows | no signal | 0 | 0 | Confirmed no-trade state; not infrastructure proof |
| ADA-USD | refreshed/sufficient | 20 | warming_up on observed rows | profitability gate | 0 | 0 | Confirmed blocker for this window |
| DOT-USD | refreshed/sufficient | 20 | warming_up on observed rows | no signal | 0 | 0 | Confirmed no-trade state; not infrastructure proof |
| XRP-USD | refreshed/sufficient | 20 | warming_up on observed rows | no signal | 0 | 0 | Confirmed no-trade state; not infrastructure proof |
| LTC-USD | refreshed/sufficient | 20 | warming_up on observed rows | profitability gate | 0 | 0 | Confirmed blocker for this window |

The evidence does not show independent terminal decisions for fee/spread/slippage, minimum-notional, cash/position, pending-order, or paper-fill gates. They were not reached after the observed terminal decisions and must not be described as passing or failing.

## Selected-universe and data-flow trace

- `SimulatedTradingPanel` stores the selected symbols as a string array. Custom/universe selection updates the whole array; no frontend cap was found.
- `apiClient.startTrading` passes the array through the canonical and legacy start payload fields. `PredictController` forwards it unchanged.
- `SimulatedTradingService::startSession` copies every string without dedupe, cap, or sort; only an empty input receives the source fallback list.
- `workerLoop` snapshots the selected array. Every selected symbol is attempted in live-parity quote acquisition; a failed/empty quote is intentionally omitted from that tick.
- Quotes and recent signals use symbol-keyed maps, so serialized output can become lexicographic. Signal endpoint sorting and display pagination can reorder or hide rows but do not cap worker coverage. Frontend requests over 50 symbols are chunked by 50 and merged before display pagination; failed chunks are diagnosed.
- The session evidence confirms all seven selected symbols reached refreshed/sufficient evaluation in this window. It does not establish a complete per-request quote trace or independent WebSocket event count.

## Lead-by-lead status

### Transformer input/readiness

- Direct observation: reload logged `Lookback: 60, Features: 353` and `expected input dimension: 0` at `2026-08-23T04:10:23.381Z`-`.382Z`.
- Source explanation: `ONNXModelManager::load_models` derives scalar `input_dim_` from 2-D regressor/classifier sessions (`src/ml/ONNXModelManager.cpp:170-196`); Transformer metadata is separately 60x353 (`:47-74`, `:127-148`). A transformer-only package can therefore report scalar zero without a Transformer width mismatch.
- Readiness: model manager readiness is true when a session exists (`include/ml/ONNXModelManager.hpp:28-36`). Simulation requires an exact 60x353 sequence before Transformer inference and labels insufficient rows `warming_up` (`src/trading/SimulatedTradingService.cpp:1201-1263`).
- Status: `expected input dimension: 0` is ruled out as the Transformer dimensional blocker (misleading telemetry). Per-symbol warm-up is a confirmed blocker for this observed paper window. Successful per-symbol `Run()` output is not present in the retained log and remains open evidence.
- Owner/status: ML/model-readiness owner; telemetry clarification and a runtime per-symbol inference trace remain open. Confidence: high for code behavior, medium for timestamped runtime causation, low for successful per-symbol inference reachability.

### Coinbase TLS/network

- Direct observation: a separate preserved pane summary at `2026-08-22T16:14:19Z` names one failed YB-USD order-book fetch after one retry with a TLS/network error. The raw transport error, selected universe, session id, and request timestamps are unavailable.
- Source: `CoinbaseAdvancedClient::request` (`src/exchange/CoinbaseAdvancedClient.cpp:168-200`) uses HTTPS and reports failed/non-OK responses; `getOrderBook` is `:514-560`. `fetchLiveQuotes` records failure and excludes the symbol from signal evaluation (`src/trading/SimulatedTradingService.cpp:879-937`, `:1732-1751`).
- Status: confirmed blocker for that one observed YB-USD fetch event; separate open issue for recurrence/root cause. It is not implicated by the seven-symbol paper window, where all seven were refreshed/sufficient. It does not establish the roughly one-minute widget cadence or overall zero-trade cause. Confidence: medium for the single event, low for window-wide recurrence.
- Owner/status: exchange/network/runtime owner; capture raw TLS error, per-symbol request timestamps, retries, recovery, and status snapshots in a fresh window.

### `is_closing_leg` schema mismatch

- Source: `src/ml/DataCollector.cpp:41-60` creates `individual_trades` without the column. Trading service `ensureSchema` adds nullable `is_closing_leg` (`src/trading/SimulatedTradingService.cpp:338-365`, `src/trading/LiveTradingService.cpp:356-383`).
- Consumer: `PredictController` execution reconciliation selects the column (`src/api/PredictController.cpp:1762-1785`) and catches the exception (`:1789-1792`), preserving prior signal rows but returning an error with empty/partial outcomes. `TradingStatsService.cpp:94-155` does not select the column and uses an independent fallback/error path.
- Direct runtime evidence for the exact missing-column error timestamp is not retained. A separate `pg_input_is_valid(text, unknown)` warning at `2026-08-23T04:31:54Z` affected signal pagination: HTTP 200 advertised 468 signals/94 pages while the page returned `signals=[]`. That warning predates the paper session and did not suppress its 140 evaluations.
- Status: confirmed reconciliation-completeness blocker when the legacy schema is queried before service schema repair; not a worker/gate/fill blocker. The pagination compatibility error is a separate diagnostic issue in this inspected snapshot, with a later fix noted outside this branch. Confidence: high for code behavior, medium for historical runtime occurrence.
- Owner/status: database/API owner; verify migration/endpoint schema behavior before claiming reconciliation completeness.

## Proven facts, ruled-out leads, and open evidence

### Proven for the observed window

- Worker started and processed all seven selected symbols.
- All seven had refreshed/sufficient market data and 20 evaluations each.
- 140 evaluations produced 0 generated signals, 0 paper intents, and 0 fills.
- Four symbols ended at profitability-gate decisions; three ended at no-signal decisions.
- Transformer rows were warming up in the observed window.
- `live_parity` is paper-only and no real Coinbase order execution occurred.
- The selected universe survived the payload/session/worker boundaries in source and runtime evidence.

### Ruled out or not supported by this evidence

- `expected input dimension: 0` as a Transformer feature-width mismatch.
- A missing `is_closing_leg` column as the cause of worker suppression.
- The separate `pg_input_is_valid` pagination error as the cause of the 140-evaluation result.
- A frontend symbol cap or display pagination as the cause of missing worker evaluations.
- Coinbase YB-USD TLS failure as the cause of this seven-symbol window.

### Open evidence gaps

- Exact wire payload, endpoint response, request/session/model correlation ids, model id/version, and browser/WebSocket frames.
- Raw per-line worker and quote logs, including per-symbol fetch start/end, retry, freshness, and recovery timestamps.
- Direct per-symbol Transformer inference success/failure/output evidence.
- Measured frontend request intervals, cache hits, WebSocket event timestamps, and the widget whose display was observed at roughly one minute.
- Exact missing-column runtime log timestamp and schema snapshot at reconciliation time.
- Independent fee/spread/slippage, minimum-notional, cash/position, pending-order, intent, and fill decisions after the observed terminal gates.

## Safety and conclusion

This inventory supports an evidence-bounded classification: the paper session was a confirmed zero-intent/zero-fill observation with explicit per-symbol early decisions, not proof of a single root cause. The strongest window-specific blocker evidence is Transformer sequence warm-up combined with profitability/no-signal outcomes; the `input_dim=0` log value is misleading telemetry rather than a proven dimensional failure. The Coinbase TLS event and database failures are separate diagnostic/blocker concerns with incomplete correlation to this session. No fix should be claimed from timing correlation alone. Fail-closed behavior and the selected universe were preserved, and no real Coinbase order was submitted.

## Supporting artifacts and queries

- `docs/investigations/trade-bl-0030-read-only-paper-session-plan.md` (available in sibling investigation workspace; records safe reproduction contract and evidence checklist).
- `docs/reports/coinbase-orderbook-failure-evidence-2026-08-23.json` (available in sibling investigation workspace; records the separate YB-USD event and evidence limits).
- Preserved runtime capture referenced by the Transformer handoff: `/home/kahlil/.hermes/cache/terminal-output/out-1787468841-3649500-8390.log`.
- Relevant source paths and line ranges are listed inline above. No secret-bearing files, credentials, cookies, or tokens are included.

No code tests were needed for this read-only documentation/evidence task. Repository hygiene should be checked by the parent report task before commit/push; remote CI remains the required build gate for any repository change.
