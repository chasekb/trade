# Live-Order Safety and Operational Observability

Status: implementation specification

This specification defines the fail-closed contract for live order-book trading as the bounded quote-fetch architecture evolves. It is intentionally stricter than simulated trading: a signal can be displayed when market data is incomplete, but it must never become a live order intent unless all safety predicates are true.

## 1. Existing authority and safety baseline

The live service is the authority for live execution. The frontend may select a universe, display diagnostics, and request start/stop/manual actions, but it must not decide readiness, available cash, account holdings, retryability, or order identity.

The current source-backed baseline is:

- `LiveTradingService::startSession` requires a successful Coinbase account snapshot, rejects synthetic capital fields, and requires explicit `live_order_execution=true` (`src/trading/LiveTradingService.cpp:2767-2927`).
- `buildEntryExecutionAnalysisLocked` blocks existing positions, pending symbols, position limits, insufficient cash, minimum notional, spot short entries, disabled execution, and failed ML gates (`src/trading/LiveTradingService.cpp:1835-1931`).
- `pending_order_symbols_` and `pending_reserved_cash_` reserve one live action per symbol and subtract reserved cash from available cash (`src/trading/LiveTradingService.cpp:638-645`, `2466-2489`).
- Every submission is persisted under a database-primary `client_order_id` with `ON CONFLICT DO NOTHING`; ambiguous submissions remain recoverable and are looked up by client id (`src/trading/LiveTradingService.cpp:859-918`, `963-1032`).
- Coinbase fills are applied once, persisted, and reconciled with a fresh account snapshot where possible (`src/trading/LiveTradingService.cpp:1106-1205`).
- Stop Trading marks the session inactive, clears unsent intents and their reservations, and leaves accepted exchange orders in `settling` until reconciliation completes (`src/trading/LiveTradingService.cpp:2930-2954`).
- The selected universe is preserved. The current implementation requests the full selected list, reports attempted/succeeded/skipped counts, and deliberately has no symbol cap (`src/trading/LiveTradingService.cpp:1244-1264`, `2526-2582`). Any future bounded queue must bound work in flight, not silently truncate the requested universe.

The following sections are the normative contract for the bounded implementation and for tests that guard this baseline.

## 2. State machine and Stop Trading drain

Use explicit session states:

`stopped -> starting -> active -> stop_requested -> draining -> stopped`

`degraded` is an execution/readiness condition orthogonal to `active`; it may be entered from `active` or `draining` when market/account/reconciliation evidence is unsafe.

A `POST /api/trading/live/stop` request (the registered route; there is no
normative `/api/live-trading/stop` alias) must:

1. Atomically set `stop_requested=true`, `active=false`, and reject new strategy or manual intents.
2. Cancel quote-fetch work that has not started and prevent new queue admission. In-flight public GETs may finish only if the client cancellation hook permits; they may not create signals or orders after the stop epoch.
3. Move every unsent intent to `cancelled_before_submit`, release its symbol lock and cash reservation exactly once, and emit a terminal event for each intent.
4. Never cancel an already accepted market IOC as if it were cancellable. Keep it in `pending_reconciliation`; resolve by exchange order id or client-order-id lookup, then retrieve the fill/status and refresh the account snapshot.
5. Continue the drain worker until: quote work is empty, unsent intents are empty, database writes are flushed or durably queued, and every accepted order is terminal or explicitly `reconciliation_unknown`. A write is "durably queued" only when it is in a committed transactional outbox/retry row in the database (including its operation key, payload, attempt, next-attempt time, and session/stop generation); an in-memory queue does not satisfy this condition.
6. Return `status=settling` while accepted orders, ambiguous submissions, or persistence retries remain. Return `status=success` only when the drain contract is complete. A repeated stop is idempotent and returns the current drain status.
7. Keep manual liquidation behind the same stop gate unless it is an explicitly separate, operator-approved emergency action with its own audit event. Stop must not trigger unapproved liquidation.

The stop epoch is a monotonic session value (`stop_generation`). Every quote batch, signal, intent, submission, and persistence event carries it. Workers discard results whose generation is no longer current.

## 3. Freshness, coverage, and degraded mode

All timestamps are UTC ISO-8601 plus epoch milliseconds where latency arithmetic is needed. For each selected symbol, store `requested_at`, `received_at`, `quote_timestamp`, `age_ms`, `fetch_latency_ms`, `source`, and `quality` (`fresh`, `stale`, `invalid`, `missing`). The exchange response has no trusted client-side timestamp; `received_at` is the observation time and age is measured from it unless an exchange timestamp is available.

Default policy (configurable only by backend deployment configuration, not the browser):

- `fresh`: quote age <= 5,000 ms and valid bid/ask, mid, finite spread, and positive depth.
- `stale`: age > 5,000 ms and < 15,000 ms; display with an explicit stale badge, never create a new live entry.
- `expired`: quote age >= 15,000 ms, timeout, malformed/empty book, or failed request; no signal is executable. An expired quote is also a hard-degraded condition.
- Account snapshot `fresh`: age <= 45,000 ms. `account_degraded`: >45,000 ms, failed, or valuation incomplete. No new live entry, add, or manual buy is allowed while degraded. Exits may be allowed only under a separately configured emergency policy using a still-authoritative holding quantity; otherwise block and show the reason.
- A selected-universe tick is `collection_complete` when every selected symbol has either a fresh result or an explicitly classified terminal result for that tick. Failed, malformed, empty, timed-out, or otherwise expired results are terminal for collection accounting but are never execution-eligible; therefore they make `coverage_complete=false`. Missing symbols are not treated as HOLD and are not hidden by pagination.
- A partial tick, or any tick containing an expired/invalid terminal result, may publish signals for observability, but all signals from it carry `coverage_complete=false` and `execution_eligible=false`. Only a tick in which every selected symbol is fresh can be coverage-complete and provide an execution-eligible basis for an order intent.
- Failed market data is not retried indefinitely. Retry at most once for a transient timeout/429 or parse/invalid response within the same tick, with bounded backoff; do not retry unauthorized responses. Drop the tick result after the deadline and wait for the next scheduled observation.
- On 2 consecutive stale/partial ticks, enter `degraded` and keep live execution disabled until three consecutive healthy complete fresh ticks and a 15-second stable recovery window have been observed, with a fresh account snapshot. The 15-second window is the sole readiness-recovery window; it is distinct from the 30-second order-reconciliation recovery timeout below. Recovery is explicit in diagnostics (`degraded_reason`, `recovered_at`), not inferred from a green HTTP response.

Selected universe invariants:

- Canonicalization trims ASCII surrounding whitespace, uppercases the product code, and accepts only the exchange product-id grammar `[A-Z0-9]+-[A-Z0-9]+`; empty, malformed, unsupported, or otherwise invalid symbols reject the live-start request. Supported products are taken from the backend-owned Coinbase `all_usd` allowlist (currently exposed by `PredictController::products`); its refresh cadence is 15 minutes and its maximum age is 30 minutes. Allowlist load or refresh failure, or an unavailable/expired allowlist, fails closed and rejects live activation. Canonical duplicates are rejected (rather than silently deduplicated), while the original user-visible order is retained only for diagnostics. An explicitly empty selection is invalid in live mode and must not fall back to `defaultSymbols()`.
- The exact canonical user-selected symbols are retained in `selected_symbols`; preserve the user-visible order separately as `selected_symbols_order`.
- A queue capacity or worker count limits concurrent requests, never selected symbols per tick. If the deadline cannot cover the universe, report `coverage_complete=false`, `missing_symbols`, and `queue_capacity_exceeded`; do not truncate or substitute a default universe.
- Backend-only adaptive inputs are request latency, 429 count/rate, timeout/error rate, queue age, tick duration, stale age, and configured exchange budget. Browser timing, CPU count, widget page size, and displayed signal count are not concurrency inputs.

## 4. Intent identity, duplicate prevention, and retry boundaries

Each intent has a deterministic `intent_id` derived from `session_id`, `stop_generation`, signal id, symbol, side, action, and a monotonic intent sequence. `client_order_id` is generated once before the first exchange submission and is persisted before submission. It must never be regenerated during retry or recovery.

Database constraints are authoritative:

- unique `client_order_id` (one application intent to one exchange order);
- unique non-null exchange `order_id`;
- intent status transition guarded by the current status and version/generation;
- one live pending action per symbol unless a future explicit policy allows safe close-before-open sequencing.

Submission rules:

- Persist `submitting` before the exchange call. If persistence fails, do not call Coinbase.
- A definitive validation/auth/minimum-notional/insufficient-funds rejection is terminal and releases reservations exactly once.
- A timeout, connection reset, 5xx, or cancellation after request transmission is ambiguous, not a safe rejection. Do not retry placement. Look up the persisted client id and reconcile order status/fill.
- A 429 is a throttle signal: record it, stop admission for the configured cooldown, and retry only read-only quote/account work within its bounded retry budget. Never duplicate an order because a placement response was delayed.
- Fill/status polling is bounded by attempts and wall-clock age. After the 30-second order-reconciliation recovery timeout, mark `reconciliation_unknown`, retain the reservation, disable new live entries, and alert an operator. Do not mark an unknown order rejected or fabricate a fill.
- Apply a fill at most once using `fill_applied` plus a unique trade id. Persistence retries are idempotent upserts; a persistence failure after local application leaves the order pending reconciliation rather than applying the fill again.
- Account snapshots can confirm quantity but cannot replace the exchange order/fill record for realized PnL or fees.

## 5. Bounded scheduler and queue contract

The scheduler has separate bounded lanes:

1. quote fetch lane for selected-universe market data;
2. account snapshot lane with its own cadence and single-flight lock;
3. order submission/reconciliation lane, serialized by intent and symbol safety rules;
4. persistence lane with bounded retry storage.

- The queue is FIFO within freshness priority: expired/degraded recovery and account reconciliation first, then symbols with oldest observation age, then stable selected-universe order. The initial safe configuration is normative: queue capacity 256; worker count 2, bounded 1..4; dispatch limit 2 and never greater than worker count; quote batch size 8, bounded 1..32; exchange token bucket 5 requests/second with rate bounded 0.5..20 requests/second and burst bounded 1..20 and no greater than two seconds of rate; request deadline 2,000 ms; account attempt deadline 15,000 ms with a 10,000 ms transport timeout; one same-tick read-only retry with bounded backoff; throttle cooldown 1,000 ms, bounded 1,000..60,000 ms; order-reconciliation recovery timeout 30,000 ms; stop-drain deadline 30,000 ms; and degraded entry after 2 consecutive stale/partial ticks. Deployments may tighten these values only within the stated bounds. Missing, zero, negative, non-finite, or out-of-range safety settings fail closed at startup and disable live execution; they must never become unbounded defaults. Adaptive concurrency may move only within these limits and only after a completed control interval. Reduce concurrency immediately on 429s, timeout/error spikes, queue lag, or stale-age growth; increase slowly after a sustained healthy interval. Never use unbounded `hardware_concurrency()` fan-out.

A queue-full result is a classified drop (`queue_capacity_exceeded`), not a successful HOLD. No retry loop may outlive the tick deadline. Stop generation invalidates queued work.

## 6. Durable observability contract

Metrics use only bounded labels: `service`, `environment`, `result`, `reason_code`, `queue_lane`, `side`, `action`, and coarse `symbol_group`/strategy names from an allowlist. Never use session, tick, signal, intent, client-order, exchange-order, trace, or raw symbol identifiers as metric labels; attach those IDs as exemplars where supported. Structured logs and audit events carry the correlation fields `service`, `environment`, `session_id`, `stop_generation`, `tick_id`, `intent_id` (when applicable), `signal_id` (when applicable), `client_order_id` (when applicable), `exchange_order_id` (when known), `symbol` (when known), `side`/`action` (when applicable), `strategy` (when known), `selected_universe_hash`, `queue_lane`, `attempt`, `source`, `status`, `reason_code`, timestamps, and `trace_id`. Fields with no applicable value are omitted or JSON `null`, never fabricated. Do not log API keys, JWTs, Coinbase secrets, raw signed requests, or complete account payloads.

Durable counters/gauges/histograms:

- `live_quote_requests_total{result}` and `live_quote_latency_ms{symbol_group}`;
- `live_quote_429_total`, `live_quote_timeout_total`, `live_quote_errors_total{reason_code}`;
- `live_quote_queue_depth`, `live_quote_queue_age_ms`, `live_tick_duration_ms`;
- `live_selected_symbols`, `live_covered_symbols`, `live_missing_symbols`, `live_stale_symbols`, `live_expired_symbols`, `live_coverage_complete`;
- `live_account_snapshot_total{result}`, `live_account_snapshot_age_ms`, `live_account_lag_ms`, `live_account_valuation_failures_total`;
- `live_intents_total{action,result,reason_code}`, `live_intent_queue_depth`, `live_intent_age_ms`;
- `live_orders_submitted_total{side,action}`, `live_orders_accepted_total`, `live_orders_rejected_total`, `live_orders_ambiguous_total`;
- `live_order_duplicate_prevented_total`, `live_order_retry_suppressed_total`, `live_order_reconciliation_total{result}`;
- `live_order_reservation_usd`, `live_pending_order_count`, `live_stop_requests_total`, `live_stop_drain_duration_ms`, `live_stop_drain_incomplete_total`;
- `live_persistence_failures_total`, `live_persistence_retry_depth`, `live_reconciliation_unknown_total`.

Structured event names include `live_session_start`, `live_session_stop_requested`, `live_stop_drain_complete`, `live_quote_batch_started`, `live_quote_result`, `live_tick_partial`, `live_degraded_entered`, `live_degraded_recovered`, `live_account_snapshot_failed`, `live_intent_blocked`, `live_order_persisted`, `live_order_submit_ambiguous`, `live_order_duplicate_prevented`, `live_order_reconciled`, `live_fill_applied`, and `live_reconciliation_unknown`.

Alert conditions:

- any accepted/ambiguous order remains unreconciled beyond the 30-second order-reconciliation recovery timeout;
- `coverage_complete=false` or expired-symbol count persists for two ticks while execution is enabled;
- account snapshot is degraded beyond 30 seconds or valuation is incomplete;
- 429/throttle rate reaches 5 responses per minute, queue age exceeds 2,000 ms, or timeout rate exceeds 20% for two consecutive ticks (these are the initial thresholds; tightening is allowed);
- reservation total disagrees with persisted pending orders;
- duplicate prevention, fill idempotency, or persistence invariants fail;
- Stop drain remains incomplete beyond its deadline.

Persistence retry rows are the crash-recovery source of truth: the transaction
that records an order/intent also records any required outbox operation, and a
worker claims rows with a lease, retries idempotently by operation key, and
marks them complete only after the external result is persisted. Rows survive
process restart and are retained for at least 30 days (or until terminal plus
the configured audit-retention period, whichever is longer); expired rows are
archived, never deleted while non-terminal. An in-memory retry queue may be a
performance cache only. If the database/outbox transaction cannot commit, live
execution fails closed and no exchange placement is attempted. A restart after
persistence failure must reload pending rows, preserve the original
`client_order_id`, and reconcile before admitting new entries.

## 7. API and widget diagnostics

`GET /api/live-portfolio/status` and live signal responses must expose the same authoritative diagnostic vocabulary. Additive fields are preferred:

```json
{
  "readiness": {
    "can_trade": false,
    "mode": "degraded",
    "reasons": ["account_snapshot_stale", "partial_selected_universe"],
    "account_snapshot_age_ms": 18700,
    "selected_symbol_count": 12,
    "covered_symbol_count": 10,
    "missing_symbols": ["ABC-USD", "XYZ-USD"],
    "coverage_complete": false
  },
  "scheduler": {
    "queue_depth": 2,
    "queue_age_ms": 850,
    "in_flight": 2,
    "configured_concurrency": 3,
    "effective_concurrency": 2,
    "last_tick_duration_ms": 1240,
    "last_429_at": null
  },
  "orders": {
    "pending_count": 1,
    "ambiguous_count": 0,
    "reconciliation_unknown_count": 0,
    "reserved_cash_usd": 125.25,
    "stop_state": "active"
  }
}
```

The widget must distinguish: `exchange_throttled`, `queue_lag`, `quote_stale`, `account_lag`, `partial_universe`, `order_pending`, `order_ambiguous`, `order_reconciliation_unknown`, `persistence_failed`, and strategy blockers. It must show selected, covered, missing, stale, and expired counts; latest update age; account snapshot age; pending/ambiguous orders and reserved cash; stop/drain state; and an explicit `can_trade` result from the backend. Pagination is display-only and must never change coverage diagnostics.

## 8. Acceptance criteria and failure scenarios

A tester can validate all of the following without placing a real order by using a fake Coinbase client and database fixtures:

- Stop during quote fetch: no post-stop signal or intent is admitted; unsent reservations are released; accepted orders remain reconcilable; response stays `settling` until terminal or the 30-second stop-drain deadline, after which it remains visibly incomplete and execution stays disabled.
- Repeated stop and restart race: stop is idempotent, no old worker can submit into a new session, and restart waits for worker/drain completion.
- Timeout after order transmission: exactly one persisted client id is looked up; no duplicate placement; eventual fill is applied once, including fees.
- Database failure before placement: no exchange call occurs. Database failure after local fill application does not apply a second fill.
- Restart after persistence failure: a committed outbox row is replayed exactly once by operation key; an uncommitted in-memory retry is not treated as durable, and live execution remains disabled until the order/account state is reconciled.
- Duplicate intent for one symbol: second intent is blocked and `live_order_duplicate_prevented_total` increments.
- 429/5xx: quote work is bounded and classified; order placement is not blindly retried; concurrency backs off within configured limits.
- Invalid scheduler configuration: startup reports the invalid field and remains execution-disabled rather than accepting zero/unbounded capacity, workers, deadlines, or retry limits.
- Invalid or empty explicit universe: live start rejects the request and never substitutes the default symbol list; canonical duplicates and malformed product IDs are named in diagnostics.
- Missing, malformed, stale, or partial selected-universe quotes: diagnostics enumerate missing/expired symbols, distinguish `collection_complete` from `coverage_complete`, set `coverage_complete=false`, and no live order is eligible from that tick.
- Account snapshot timeout, valuation failure, or stale age: `can_trade=false`, account data is not silently replaced with zero, and the widget names `account_lag`/valuation failure.
- Queue capacity/deadline exhaustion: no selected symbols disappear; dropped work is classified and visible.
- Reconciliation timeout: order becomes `reconciliation_unknown`, reservations remain held, new entries are blocked, and an alert is emitted.
- Inherited Coinbase holdings and emergency liquidation retain their distinct trade types and never fabricate strategy PnL.
- Every metric uses only the bounded labels defined in section 6; high-cardinality identifiers are prohibited as metric labels and may be attached only as exemplars where supported. Every structured log and audit event carries the applicable correlation fields, using JSON `null` or omission when a field has no meaning for that event, and contains no credential or signed-request material.

Closeout requires deterministic unit/integration fixtures for these scenarios, a remote CI run for the exact pushed commit, and an independent high-risk review before enabling live rollout. No runtime readiness or throughput claim is closed by green CI alone; live-parity/paper evidence remains a separate gate.

## 9. Rollout and rollback

Roll out behind `bounded_live_quotes` and `live_safety_observability_v2` flags:

1. shadow mode: collect queue/freshness/coverage metrics while the existing producer remains execution authority;
2. live-paper mode: produce intents but suppress exchange placement, validating blockers, idempotency, and drain behavior;
3. restricted live: one approved account and a small explicit universe, with the kill switch defaulting to execution disabled;
4. expand only after zero unknown reconciliations, complete coverage within budget, no duplicate intents, and acceptable throttle/lag metrics over the evidence window.

Rollback immediately to execution-disabled/paper mode on any duplicate-order, unknown-reconciliation, account-authority, selected-universe truncation, or stop-drain invariant breach. Preserve diagnostic rows and audit events during rollback. Do not delete pending order records or reset reservations as a rollback shortcut; reconcile them first.
