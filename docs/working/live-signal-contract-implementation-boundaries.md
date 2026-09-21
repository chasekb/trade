# Live Signal Contract and Implementation Boundaries

Status: implementation handoff
Date: 2026-08-22
Scope: Live Trading order-book signal production and its comparison with Simulated Trading

This note is the source-backed contract map for the bounded/live-signal work. It is deliberately limited to signal production, signal reads, lifecycle/resource handling, and the diagnostics needed to explain live-only outcomes. It does not authorize a strategy redesign, removal of live-account safety gates, or a claim that synthetic fills are equivalent to Coinbase fills.

## 1. Contract summary

The shared pre-execution contract is:

- The selected universe is the user-provided, deduplicated symbol list. It must not be silently capped or replaced by a frontend page size. A default universe is used only when no symbols are supplied.
- Each symbol produces a normalized signal row with `signal_id`, `session_id`, `symbol`, `signal_type`, `signal`, `signal_generated`, `signal_strength`, `price`, ISO `timestamp`, `signal_reason`, `data_status`, order-book fields, prediction/criteria fields, and `ml_analysis`/execution diagnostics where applicable.
- `buy`/`sell` is actionable only after the shared fee/spread/slippage profitability gate. A failed profitability gate becomes a sufficient-data `hold`, not an insufficient-data `WAITING` row. Missing/warming data remains `data_status=insufficient` (or the explicit live read placeholder state `missing`).
- Reads are latest-by-symbol views, not cumulative signal history. Totals and active counts are calculated across the complete filtered latest-by-symbol population before display pagination. Display pagination is stable and must not alter coverage or summary counts.
- Live uses Coinbase quotes/account state and retains live-only execution blockers. Simulated may use synthetic state (or live quotes in the parity mode), starts with synthetic capital, and does not submit Coinbase orders. These are intentional deviations.
- Live execution remains fail-closed: explicit `live_order_execution` opt-in, account/client readiness, pending-order and duplicate-symbol guards, max-position limits, cash/holding checks, minimum notional, spot-only constraints, and account-position-management authority remain downstream of signal generation.
- The recent checked-in live contract intentionally has no hard quote fan-out cap or normal cadence sleep. The full selected universe is requested; fan-out, elapsed fetch time, estimated request rate, and warning-threshold crossings are observable. Any new scheduler must budget exchange requests without silently dropping the selected universe and must preserve this intentional distinction from an unapproved hard cap.

## 2. Code and data-flow map

### Backend entry points and API routes

- `include/api/PredictController.hpp:25-33,74-84` declares the start/stop/update handlers and `/api/orderbook/live-signals` and `/api/orderbook/simulated-signals` routes.
- `src/api/PredictController.cpp:1240-1268` parses `symbols`, `page`, and `per_page`, then delegates to the corresponding service. Query parsing is shared, but service state and mode are separate.
- `include/trading/LiveTradingService.hpp:26-42` is the live service façade. `include/trading/SimulatedTradingService.hpp:25-38` is the simulated façade.
- `src/trading/LiveTradingService.cpp:3242-3467` and `src/trading/SimulatedTradingService.cpp:2375-2620` implement signal reads, aggregation, pagination, JSON normalization, and persisted fallback behavior.

### Signal models and producers

- `LiveTradingService::SignalRecord` is declared at `include/trading/LiveTradingService.hpp:108-126`. It stores identity, symbol, signal type, strength, market values, timestamp, payload, and cumulative producer count.
- The simulated equivalent is in `include/trading/SimulatedTradingService.hpp` (the same fields plus the simulated service's state). The live service uses a `std::deque` (`LiveTradingService.hpp:273`); simulated uses a per-symbol `std::map` (`SimulatedTradingService.hpp:243`).
- `src/trading/LiveTradingService.cpp:1516-1780` (`buildSignalRecordLocked`) builds live rows from Coinbase market quotes, rolling indicator state, ML/transformer/regressor output, shared profitability diagnostics, and execution analysis.
- The simulated producer is `src/trading/SimulatedTradingService.cpp:1046-1400` (`buildSignalRecordLocked`) and `:1732-1830` (`generateTickLocked`). It evaluates the same strategy/gate contract but can synthesize market state.
- `src/trading/StrategySignal.cpp` and `include/trading/StrategySignal.hpp` own shared strategy parameter interpretation and `evaluateOrderBookProfitabilityGate`. Do not fork the gate in the services.
- `src/trading/PositionSizingPolicy.cpp`/`include/trading/PositionSizingPolicy.hpp` own fee/slippage/spread-aware sizing. Live uses it at `LiveTradingService.cpp:409-464`; simulated has its corresponding sizing path. Parameter tuning is outside this task.
- `src/trading/TradingStatsService.cpp`, `TradingStatsCalculator.cpp`, `include/trading/TradingStats*` own trade/statistics summaries, not signal-widget aggregation. Do not move signal counts into the stats layer.

### Frontend consumers

- `frontend/lib/api.ts:1011-1071` selects the live/simulated route, preserves pagination parameters, and supplies the local synthetic simulated fallback when configured. Its network fallback currently returns an empty success-shaped response; future changes must not turn an exchange/API error into falsely complete coverage.
- `frontend/hooks/useTrading.ts:375-445` owns React Query keys, selected-universe chunking, merge, display pagination, stale time, and polling. For a universe larger than `ORDERBOOK_SYMBOL_CHUNK_SIZE`, it requests every symbol in each chunk with `page=1, per_page=chunk.length`, merges responses, then paginates for display. Failed chunks are marked in diagnostics and set `coverage_complete=false`.
- `frontend/types/trading.ts:94-170` defines `OrderBookSignal` and `OrderBookSignalDiagnostics`; `:193-208` defines the generic pagination shape. Keep backend field names and units aligned with these types.
- `frontend/components/dashboard/OrderBookSignalsTable.tsx:53-58,188-235,293-411` renders display pagination, active summaries, `HOLD` versus `WAITING`, and diagnostics. `frontend/components/dashboard/LiveTradingPanel.tsx` and `SimulatedTradingPanel.tsx` pass the selected universe and mode.
- `frontend/components/ui/DataTable.tsx:53-60,130-154` renders pagination controls but does not slice data. The caller must provide the page slice.

### Persistence and schema

- Both services create `order_book_signals` in `LiveTradingService.cpp:332-353` and `SimulatedTradingService.cpp:314-335`. The table has `signal_id` primary key, session/symbol/type, strength/price/timestamp, `signal_data` text JSON, order-book columns, and `total_signals`.
- Live also creates `individual_trades` and `live_coinbase_orders` (`LiveTradingService.cpp:355-402`). `live_coinbase_orders.client_order_id` is the durable idempotency key for accepted live orders.
- `queueSignalWriteLocked`, `takePendingWritesLocked`, and `flushWrites` are at the live service around `:1400-1514` and have simulated equivalents. Writes happen outside the service mutex; failed batches are requeued in memory for retry.
- Signal persistence is upserted by `signal_id`; there is no explicit retention/delete policy for `order_book_signals`. In-memory signal history is bounded (`kMaxRecentSignals=250`, raised to at least selected-universe size) while trades are capped at 100. Database history therefore grows unless an external policy exists.
- Reads use parameterized symbol filters. The stopped-session fallback uses `DISTINCT ON (symbol)` ordered by `timestamp DESC`, then strength/win probability/timestamp ordering. It does not currently filter by session ID, and malformed legacy JSON is guarded with `pg_input_is_valid` in the SQL ordering path before casts.

### Scheduler/lifecycle entry points

- Live quote fetch: `LiveTradingService::fetchLiveQuotes` at `:1208-1242`; selection at `:1244-1264`; account snapshot at `:1266-1298`.
- Tick generation: `generateTickLocked` at `:2226-2307`; it updates market state, produces rows, evaluates execution intents, marks positions, and trims in-memory history.
- Worker: `workerLoop` at `:2309-2437`; `startWorkerLocked` at `:2439-2444`; start/stop handlers at `:2767-2955`.
- Simulated equivalents are `generateTickLocked` `SimulatedTradingService.cpp:1732-1830`, `workerLoop` `:1832-1930`, and start/stop `:2142-2305`.
- Live currently fetches all selected symbols sequentially, refreshes the account snapshot in the same worker loop, generates one tick, dispatches orders and flushes writes outside the mutex, and repeats without a normal cadence sleep. Stop sets `stop_requested_`, marks inactive immediately, clears not-yet-dispatched intents/reservations, and lets already accepted Coinbase orders settle.

## 3. Simulated versus live behavior matrix

| Area | Simulated Trading | Live Trading | Required implementation boundary |
|---|---|---|---|
| Selected-universe coverage | `startSession` keeps requested symbols (`SimulatedTradingService.cpp:2190-2200`), defaults only when empty. In-memory generation evaluates every selected symbol each tick. | `startSession` keeps requested symbols; current `selectLiveQuoteBatchLocked` returns all of them (`LiveTradingService.cpp:1244-1263`). A read adds response-only `hold`/`data_status=missing` rows for selected symbols without a latest quote (`:3280-3307`). | Preserve literal selected universe, deduplicate deterministically, and make any budget/queue outcome visible per symbol. Never let `page/per_page` or a chunk size silently reduce the universe. Missing/stale symbols are not executable intents. |
| Signal payload/diagnostics | Producer emits the normalized core fields, criteria, ML fields, profitability fields, and execution analysis. | Same core fields and shared gate; live adds Coinbase/account/execution blockers and producer fan-out/coverage diagnostics. | Normalize names/units in service serializers, not endpoint-specific frontend patches. Preserve `data_status` distinction and explicit live-only diagnostic fields. |
| Strategy parameters | `parameters` canonical; legacy `strategy_params` alias accepted; top-level settings backfill parameters. Synthetic capital is required/allowed. | Same canonical/legacy parameter interpretation, but `initial_portfolio_size`, `initial_balance`, and `capital` are rejected by live parameter updates and must not create synthetic live capital. | Keep shared strategy/gate interpretation. Explicitly test live capital rejection and live sizing/account authority separately from pre-execution signal equivalence. |
| Latest-by-symbol aggregation | Active read maps recent rows by symbol, sorts strength desc/timestamp desc/symbol asc, then paginates (`SimulatedTradingService.cpp:2395-2455`). Persisted read uses `DISTINCT ON (symbol)` (`:2513-2521`). | Same active read plus selected-symbol placeholders (`LiveTradingService.cpp:3261-3349`). Persisted read uses the same SQL shape (`:3400-3408`). | Totals must count latest rows, not history. Define tie-breaking for equal timestamps before changing the scheduler; current in-memory latest selection only uses `timestamp`. |
| Active counts | Active reads count non-`hold` latest rows over the full filtered set before slicing; persisted fallback currently counts only returned page rows. | Same active behavior; live diagnostics also report executable intents/blockers. Persisted fallback also counts only returned page rows. | Correct the persisted fallback to aggregate counts/average over all latest rows, while keeping page rows bounded. Do not report page-scoped counts as population totals. |
| Retention | In-memory recent trades are capped at 100; signals are per-symbol map/trim behavior. Persisted `order_book_signals` is not deleted. | In-memory trades cap at 100; signals cap at `max(250, symbols.size())` (`:1934-1942`). Persisted signals are not deleted. | Preserve enough rows for the selected universe, but make the durable retention window and cleanup owner explicit before implementation. No silent loss of selected-universe latest rows. |
| Pagination | Backend clamps page/per-page to at least 1, sorts deterministically, and slices display rows. Frontend merges large-universe chunks before display pagination. | Same, with response-only missing rows in active selected reads. | Page controls are display-only after full selected-universe merge. Stable sort needs a final symbol/signal-id tie-break in every path. |
| Market data | Default simulated mode synthesizes quotes; `live_parity` can use public live quotes while still disabling Coinbase orders. | Coinbase order-book snapshots and account snapshots are authoritative. | Never call synthetic cash/positions live state. Keep the parity mode distinct from live execution. |
| Execution | Simulated order intents are paper/local and may use synthetic capital. | Order intents are blocked unless live opt-in and all account/exchange guards pass; accepted orders settle via `live_coinbase_orders`. | Signal normalization must not bypass or reimplement live execution guards. |

## 4. Approved resource and lifecycle semantics

These are the semantics implementation workers must preserve. Values not present in approved code are called out as ambiguities below rather than invented here.

### Exchange limits and selected-universe work

1. The selected universe is authoritative. There is no approved hard quote-symbol cap and no approved normal `sleep(1)` cadence in the current live contract; the recent implementation intentionally requests the full universe and exposes warning/throughput diagnostics.
2. A bounded scheduler may enforce provider request budgets, connection/in-flight limits, and adaptive backoff, but it must queue or defer work with per-symbol diagnostics rather than silently drop symbols. A budget decision is not a strategy decision.
3. Exchange order placement remains governed by `CoinbaseAdvancedClient`, minimum-notional checks, account readiness, pending-order reservations, and live opt-in. Signal-worker throughput must not increase order submission concurrency beyond the exchange-safe policy.
4. CPU signal processing and database flushes must be bounded/off the API handler path. Existing code already avoids holding `mutex_` during network, exchange dispatch, and persistence; preserve that property.

### Queue bounds, freshness, retries, and stale work

1. Queues and in-flight work must be finite. Overflow must be deterministic and observable per symbol; it must not grow unbounded or overwrite a live intent silently.
2. Freshness is evaluated against quote acquisition/processing time, not only the signal timestamp. Stale quotes/signals must not create executable intents; they remain visible with an explicit stale outcome/diagnostic.
3. Retry only transient exchange/network/persistence failures. Do not retry invalid symbols, malformed payloads, rejected orders, stopped work, or stale data as if they were fresh. Retry/drop classification must be deterministic and counted.
4. Backoff must respond to provider rate-limit responses and respect the request budget. The exact token-bucket/window and backoff constants are not currently encoded in the repository and must be resolved before implementation from the approved exchange/provider limits.
5. Stale queued work is dropped or replaced by a newer per-symbol item according to an explicit policy; it must not execute after Stop Trading or after a newer symbol snapshot has superseded it.

### Cancellation, stop, and idempotency

1. Stop is an immediate admission barrier: no new quote, signal, or order intent may be admitted after `stop_requested_` is observed.
2. Cancellation propagates through queued work, quote fetch loops, CPU signal processing, order dispatch, and persistence. Already accepted Coinbase orders are not cancelled by pretending they did not happen; they settle/reconcile through `live_coinbase_orders`.
3. Existing per-symbol guards (`pending_order_symbols_`, positions, and durable `client_order_id`) remain authoritative. Concurrent workers must not generate duplicate live orders for one symbol; an idempotency claim must be acquired before dispatch and released only on terminal/drop paths.
4. Stop response may be `settling` while accepted exchange orders or persistence writes remain. The worker must perform bounded cleanup and expose final state; no orphaned pending intent or reservation is acceptable.
5. Retry must reuse or reconcile the durable client-order identity where an exchange request may have been accepted. Never submit a new order solely because the response was lost.

### Retention and pagination

1. In-memory retention must retain at least one latest row per selected symbol while the session is active, plus the existing bounded diagnostic window. Durable retention must be bounded by an explicit policy, but the repository currently has no approved duration/count or cleanup job.
2. Latest-by-symbol totals, active counts, average strength, coverage, and last-updated are population metrics calculated before pagination. Returned `signals` is only the requested display page.
3. Stable ordering must include strength, relevant confidence/expected-return tie-breaks where approved, timestamp, and a final symbol/signal-id tie-break. The current in-memory and SQL paths are not fully identical on equal values; implementation must resolve this without changing the intended ranking.

## 5. Tests and acceptance coverage

Existing focused tests:

- `src/tests/test_strategy_signal.cpp`: shared strategy signal and profitability-gate semantics.
- `src/tests/test_position_sizing_policy.cpp`: sizing, fee/slippage/spread hurdles and caps.
- `src/tests/test_execution_reconciliation.cpp`: signal/outcome attribution, blockers, flat close handling.
- `src/tests/test_execution_cohorts.cpp`, `test_trading_stats_calculator.cpp`, `test_portfolio_accounting.cpp`: accounting/stat summaries.
- `frontend/lib/localSimulatedFallbackSignals.test.ts`: simulated payload/diagnostic fallback shape.
- `frontend/lib/startTradingPayload.test.ts`: live/simulated start payload parameter handling.
- `frontend/components/dashboard/__tests__/dashboard-tables.test.tsx`: sufficient HOLD versus WAITING and live missing-row diagnostics.
- `frontend/lib/simulatedTradingStats.test.ts` and `frontend/lib/executionReconciliation.test.ts`: frontend normalization and summary contracts.

Tests that must be added or extended by implementation workers:

1. Backend service contract fixtures for identical pre-execution input: normalized fields, `data_status`, profitability-gated HOLD, ML fallback labeling, strategy parameter aliases, and live-only diagnostics.
2. Selected-universe/read fixtures: full-universe coverage, missing/stale placeholders, latest-by-symbol dedupe, equal-timestamp deterministic ordering, population active counts/average strength, and persisted fallback counts independent of display page.
3. Persistence fixtures: malformed legacy `signal_data` cannot abort a read; upsert/idempotency behavior; explicit retention/cleanup semantics once approved.
4. Scheduler fixtures: finite queue/in-flight bounds, deterministic overflow, freshness ordering, exchange request budget, rate-limit backoff, transient retry versus permanent drop, stale suppression, CPU bounds, and durable throughput counters.
5. Lifecycle fixtures: account snapshot cadence independent of quote generation, immediate stop admission barrier, cancellation through each stage, bounded cleanup, no orphaned reservations, and concurrent per-symbol duplicate prevention.
6. Frontend hook/merge fixtures: chunk-wide selected-universe fetch, failed-chunk diagnostics, display-only page size, stable merged ordering, and no false `coverage_complete` on network fallback.

Remote verification is required for C++/container changes. No local CMake/Docker/backend build is authorized for this handoff; use `git diff --check` and source/document checks locally, then exact pushed-SHA GitHub Actions verification for implementation tasks.

## 6. Explicit ambiguities to resolve before implementation

1. What exact Coinbase/provider request budget, connection limit, and rate-limit window are approved? The repository only contains a warning threshold of 10 symbols, not an enforceable provider budget.
2. What finite queue length, in-flight quote limit, CPU-worker limit, and persistence retry queue size are approved? Do not infer these from `kMaxRecentSignals`; that is read-history retention, not work capacity.
3. What freshness SLA and stale threshold apply to quote, signal, queued work, and accepted-order reconciliation? The current code has no named freshness duration.
4. What retry count/backoff schedule is approved for quote, persistence, and exchange failures? The final write flush currently makes three bounded attempts with 250/500 ms sleeps, but that is not a general signal scheduler contract.
5. Should stale queued work be dropped, coalesced to one newest item per symbol, or retained as a visible non-executable diagnostic? The contract requires bounded/deterministic behavior but does not choose among these policies.
6. What durable signal retention duration/count and cleanup owner are approved? Current `order_book_signals` writes are append/upsert only and can grow indefinitely.
7. Should reads be scoped to the active/session ID when symbols overlap across sessions? Current persisted queries filter symbols but not `session_id`; changing this affects historical/stopped-session semantics.
8. What exact stable ranking is approved for equal strength/timestamp: win probability, expected return, signal ID, or symbol as the final tie-break? SQL currently includes win probability while active in-memory reads do not.
9. What should happen to an individual symbol after a rate-limit or provider error: immediate retry, deferred retry, stale placeholder, or explicit dropped row? The selected universe must remain observable, but the response shape is not yet specified.
10. Are throughput counters required to survive process restart in a new durable table, or only be reconstructed from persisted signal/order rows? No durable throughput schema currently exists.

Until these are resolved from approved exchange/provider limits or existing backlog decisions, implementation workers must not invent numeric limits or silently convert intentional live deviations into caps.

## 7. Non-goals and safety boundaries

- Do not redesign SMA/EMA/RSI/MACD/DCA/buy-and-hold strategy rules.
- Do not remove live execution opt-in, account authority, minimum notional, pending-order, cash/holding, spot-only, or profitability gates.
- Do not treat simulated synthetic capital/fills as live account state.
- Do not blacklist or cap user-selected symbols.
- Do not make frontend pagination a backend coverage limit.
- Do not claim runtime/live-trading readiness from source parity or green CI alone; live/runtime/data evidence remains a separate closeout gate.
