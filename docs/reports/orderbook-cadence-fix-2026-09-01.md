# Order-book cadence fix and diagnostics

Date: 2026-09-01

## Root cause

The live-data simulated worker performed one blocking Coinbase public order-book request for every selected symbol before it could generate any signals or sleep for the next simulated tick. With 401 symbols, retries and provider/network latency made the producer interval tens of seconds even though the loop slept for only one second. The delay was upstream of API polling and display pagination; pagination only projected the latest-by-symbol result.

## Fix

Live-data simulated sessions now admit a bounded batch of eight symbols per worker iteration and select the next batch with a deterministic round-robin cursor. Requests inside a batch remain sequential and use the existing timeout/retry behavior. The change therefore reduces the time before the first visible signal without increasing request concurrency or bypassing provider pacing. Synthetic sessions retain their existing all-symbol simulated tick behavior.

Symbols outside the current live batch remain pending and are not recorded as provider failures. A failed or invalid request only affects its admitted symbol; valid symbols in the same and later batches continue through signal generation. A failed refresh does not replace a previously valid signal with synthetic data.

## Observable fields

When `diagnostics_enabled` is true, simulated status/order-book responses include:

- `cadence.schema_version`: `order_book_cadence.v1`.
- `cadence.session_id` and `cadence.universe_generation`: correlation/reset boundaries.
- `cadence.last_tick.tick_id`, `started_at`, `finished_at`, `elapsed_ms`, `outcome`, `selected_symbols`, `quote_requested`, `quote_success`, `quote_missing`, and signal counts.
- `cadence.counters`: tick, quote request/success/failure/timeout/rate-limit/retry/drop, signal, serialization, API-poll, and WebSocket-delivery counters.
- `cadence.histograms`: fixed-bucket monotonic durations for worker ticks, quote requests, quote batches, signal generation, and serialization.
- `cadence.recent_errors`: bounded, symbol-free stage/class/attempt records for transport, TLS, DNS, timeout, exchange, and invalid-response failures.
- `cadence.coverage`: selected-universe versus current-batch quote/signal coverage and retry/drop counts.
- Per-signal or per-symbol `cadence`: `trace_id`, `tick_id`, `batch_id`, `event_id`, state, attempt count, producer wall-clock anchors, and monotonic-derived duration fields.
- `diagnostics.quote_scheduler`: whether live-data scheduling is active, configured batch size, round-robin cursor, and most recent batch symbols.

Wall-clock ISO-8601 UTC values are used for cross-component correlation. Durations and latency histograms use `steady_clock`/`performance.now()` so wall-clock adjustments cannot create negative or misleading latency. Browser API responses also carry a request ID, wall-clock receive time, monotonic receive time, total API duration, parse duration, and error class.

The frontend canonical view model merges by `(session_id, symbol)`, rejects older/repeated sequence or event versions, retains diagnosis-only pending rows, and applies display pagination after merging. Thus UI timestamp/refresh delay can be distinguished from producer cadence using `cadence.last_tick`, `last_updated`, and the browser API observation fields.

## Verification

- `npx tsc --noEmit` — passed.
- `npx eslint components/dashboard/OrderBookSignalsTable.tsx hooks/useTrading.ts lib/orderBookSignalsViewModel.ts types/trading.ts` — passed.
- `npx jest lib/orderBookSignalsViewModel.test.ts lib/orderBookSignalsReconciliation.test.ts --runInBand` — 10 tests passed.
- `c++ -std=c++20 -Iinclude src/tests/test_quote_batch_scheduler.cpp src/trading/QuoteBatchScheduler.cpp -o /tmp/test_quote_batch_scheduler && /tmp/test_quote_batch_scheduler` — passed.
- `docker compose -f docker-compose.test.yml run --rm cpp-test` could not run because the local Docker daemon socket was unavailable.
- The pre-existing full frontend run remains red in legacy dashboard/panel assertions that expect the prior table/diagnosis markup; the cadence-focused frontend tests and type/lint checks pass.
