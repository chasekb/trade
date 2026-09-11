# Bounded live-quote scheduling and adaptive exchange budgets

Status: design specification; no runtime behavior changes
Scope: backend-only live Coinbase market-data and account-refresh scheduling

## 1. Goals and non-goals

The scheduler must make live order-book retrieval deterministic, bounded, observable, and safe for account-backed execution. It must preserve the operator-selected symbol universe: the backend must accept the complete selected list, must not alphabetically truncate it, and must not introduce a Coinbase symbol blacklist. A bounded scheduler may defer or coalesce refresh work, but it must report that fact and retain every selected symbol in the coverage state.

The scheduler is not an order executor and does not relax existing live gates. A quote can inform a signal only when it is valid and within its freshness policy. A live order still requires explicit execution opt-in, an authoritative sufficiently fresh account snapshot, pending-order/idempotency checks, position authority, available cash/quantity, exchange constraints, and the profitability gate. Stop Trading cancels market-data work and prevents new order intents; it does not cancel an already accepted Coinbase order.

The scheduler is backend-only. The frontend supplies the selected universe and reads normalized diagnostics; it does not choose worker counts, retry timing, token-bucket rates, queue capacity, or exchange concurrency.

## 2. Components and ownership

`LiveQuoteScheduler` is owned by the singleton `LiveTradingService` and has these components:

- `UniverseState`: a deduplicated, order-preserving vector of selected product IDs plus a monotonically increasing `universe_generation`.
- `QuoteQueue`: a fixed-capacity priority queue of quote jobs. Capacity is 256 queued jobs. There is at most one queued or in-flight job per `(universe_generation, symbol)`; a newer job coalesces/replaces an older queued job for that symbol.
- `QuoteWorkers`: a fixed CPU worker pool. Safe defaults are `worker_count=2`, hard minimum 1, hard maximum 4. `dispatch_limit` is the coupled maximum number of active network calls and is never greater than `worker_count`. The maximum is a constant safety limit, not `hardware_concurrency()`; hardware concurrency is never used for fan-out.
- `ExchangeBudget`: one token bucket for all Coinbase requests made by this live service, including quote order books and account valuation tickers. The account lane reserves a bounded, all-or-nothing cost so quote fan-out cannot starve account safety refreshes.
- `AdaptiveController`: updates batch admission and worker concurrency only at tick boundaries from bounded rolling metrics. It cannot exceed fixed queue, worker, request-rate, or timeout limits.
- `AccountSnapshotScheduler`: a separate single-flight cadence, default 15 seconds, for `listAccounts` plus required valuation tickers. It never runs once per quote symbol or once per quote tick.
- `CancellationState`: a generation/cancellation token checked before enqueue, before budget wait, before network dispatch, after network completion, and before publishing a result.

The service remains responsible for applying completed quotes under its existing mutex and for persisting signals outside that mutex. Network calls never hold the state mutex.

## 3. Fixed safe defaults

These values are defaults and hard-bounded configuration fields:

| Setting | Default | Hard range / rule |
| --- | ---: | --- |
| queue capacity | 256 jobs | fixed; never grows dynamically |
| worker count | 2 | 1 through 4; no unbounded fan-out |
| dispatch/in-flight quote limit | 2 | 1 through worker count; updated atomically with worker count |
| quote batch size target | 8 symbols | 1 through 32; batch size is admission grouping, not a universe cap |
| public request rate | 5 requests/second | 0.5 through 20; configured exchange budget wins over adaptive increase |
| public burst | 10 tokens | 1 through 20 and no greater than two seconds of configured rate |
| account reservation | 10 request costs | exactly 6 account pages plus 4 valuation tickers; all-or-nothing |
| quote deadline | 2 seconds absolute | includes queue wait, token wait, network, and retry |
| account attempt deadline | 15 seconds absolute | includes pagination, valuation, token waits, and retry |
| client transport timeout | 10 seconds | never overrides either absolute deadline |
| maximum attempts | 2 total | one initial attempt plus one retry |
| retry backoff | 100 ms base | retry only once; bounded by the absolute deadline |
| normal quote freshness | 5 seconds | quote older than this cannot create an entry intent |
| hard quote age | 15 seconds | older data is stale and excluded from signal execution |
| account snapshot active freshness | 45 seconds | older data blocks live order admission |
| account snapshot hard stale | 90 seconds | diagnostic severity only; remains fail-closed |
| queue lag warning / fail-closed | 2 s / 10 s | fail-closed means no new live order intent, not process termination |
| account refresh cadence | 15 seconds | single-flight; settlement may trigger an immediate coalesced refresh |
| controller interval | 10 seconds | decisions only at completed intervals |

A configured exchange rate is an operator budget, not a target to exhaust. The controller can reduce rate and concurrency but never raise either above the configured rate or the hard range.

## 4. Job model, priority, and admission

Each `QuoteJob` contains:

```
job_id, session_id, universe_generation, symbol, requested_at,
not_before, deadline, attempt, priority, cancellation_generation
```

Priority is deterministic and safety-first:

1. symbols needed by an open managed position or pending exit;
2. unseen or hard-stale symbols;
3. soft-stale symbols, ordered by oldest successful quote;
4. ordinary refreshes in configured selected-universe order;
5. `job_id` as the final tie-breaker.

An open managed position or a pending exit receives an exit-protection priority, but it still cannot bypass the exchange token bucket, request timeout, or cancellation. Account refreshes have their own reserved budget and are never queued behind quote work.

On each scheduler tick, the producer walks the complete selected universe in selected order and attempts to admit one refresh per symbol whose quote is missing, stale, or due by cadence. It does not silently replace the selected universe with a smaller batch. Admission is:

```
if stop_requested or generation != current_generation: drop(cancelled)
else if an equivalent queued/inflight job exists: coalesce(duplicate)
else if queue has room: enqueue(priority)
else if a queued lower-priority job exists: replace that job and record(queue_eviction)
else: defer this symbol and record(queue_full)
```

`queue_full` is a temporary scheduling result, never a blacklist. The symbol remains in `UniverseState`, receives `deferred_until`, and is retried on the next admission pass. If a symbol is deferred for more than 10 seconds, the scheduler emits a `coverage_lag` diagnostic and raises its priority. A queue cannot grow to accommodate a burst.

A batch is formed by taking up to the current adaptive `batch_size` highest-priority jobs that share the same cancellation generation and are eligible under the budget. Batch formation never changes the selected universe; it only controls work issued in this dispatch window. The current Coinbase client performs one order-book request per product, so a batch is a bounded scheduling group rather than a claim that Coinbase supports a multi-product request.

## 5. Token bucket and account reservation

The exchange budget is a monotonic-clock token bucket:

```
tokens = min(capacity, tokens + elapsed_seconds * configured_rate)
allow(cost=1) iff tokens >= 1; then tokens -= 1
```

A request waits only until its absolute deadline and cancellation token. Waiting for a token is counted as queue/budget lag, not network latency. Each account refresh atomically reserves exactly 10 request costs: at most 6 paginated `listAccounts` calls and at most 4 valuation tickers. The reservation must be available before the attempt starts; quote work may consume only unreserved tokens. The account lane is single-flight and has a 15-second completion-to-completion cadence. If reservation is unavailable by the 15-second attempt deadline, pagination exceeds 6 pages, valuation requires more than 4 tickers, or any required call fails, the entire refresh fails closed, retains the last complete snapshot, and blocks account-dependent orders once the retained snapshot is older than 45 seconds. No partial snapshot is published.

HTTP 429, explicit rate-limit response, or a provider response containing a retry-after value causes an immediate controller decrease and sets `not_before` to `min(retry_after, 5 seconds)` for the one permitted retry. If retry-after is absent, use 1 second. A second 429 drops the job for this cycle and records `rate_limited`; it does not create a retry storm.

## 6. Adaptive batch size and concurrency

The controller uses exponentially weighted moving averages over completed requests and completed 10-second intervals:

- `p95_latency_ms`: request network latency, excluding token wait;
- `rate_limit_ratio`: 429 responses / attempted requests;
- `timeout_error_ratio`: timeouts plus transport/parse errors / attempted requests;
- `tick_duration_ms`: time from admission through signal publication;
- `queue_lag_ms`: now minus job enqueue time at dispatch;
- `max_stale_age_ms`: oldest selected symbol's current quote age;
- `budget_utilization`: consumed tokens / available configured tokens;
- `coverage_ratio`: selected symbols with a valid quote not older than 5 seconds / selected symbols.

Controller state is one atomically updated tuple `(workers, dispatch_limit, batch_size, cooldown_until)`, clamped to `batch_size [1,32]`, `dispatch_limit [1,4]`, and `workers [1,4]`. It starts at `(2, 2, 8, now)`. Every 10 seconds:

```
pressure = max(
  p95_latency_ms / 5000,
  queue_lag_ms / 2000,
  tick_duration_ms / 5000,
  max_stale_age_ms / 10000,
  1 + 4 * rate_limit_ratio,
  1 + timeout_error_ratio
)
```

- If `rate_limit_ratio >= 0.05`, `timeout_error_ratio >= 0.10`, p95 latency > 5 seconds, or queue lag > 10 seconds: atomically set `dispatch_limit = max(1, ceil(dispatch_limit / 2))`, `workers = max(dispatch_limit, workers - 1)`, and `batch_size = max(1, floor(batch_size / 2))`.
- If queue lag > 2 seconds or stale age > 5 seconds: reduce neither below one, but reduce batch size by 25% and do not increase concurrency.
- Increase only after three consecutive healthy intervals, at least 20 completed requests, and no overdue account reservation: no 429s, error/timeout ratio < 2%, p95 latency < 1.5 seconds, queue lag < 500 ms, tick duration < 2 seconds, stale age < 5 seconds, and budget utilization < 80%. Atomically increase `dispatch_limit` by one only when allowed, set `workers = max(previous_workers, dispatch_limit)`, and increase batch size by one. If the limit cannot increase, batch size may still increase.
- The budget-derived limit is `floor(configured_rate * max(p95_latency_seconds, 0.25))`, clamped to `[1,4]`; the new tuple is always clamped to `dispatch_limit <= workers <= 4`. No transition can produce more active requests than worker slots.
- If `coverage_ratio` falls while the controller is healthy, improve fairness by admitting the oldest symbol first; do not increase beyond the budget or hard limits solely to chase coverage.

A single bad response cannot cause oscillation: decreases are immediate, increases require three healthy intervals. Configuration changes reset the controller to safe defaults.

## 7. Completion, freshness, retries, and drops

A successful response is published only if it is valid, finite, has a positive mid/bid/ask as applicable, and its cancellation generation still matches. The result stores `received_at`, `request_started_at`, `request_finished_at`, `age_ms`, `attempt`, and `source="coinbase_order_book"`.

Failure classes are deterministic:

- `cancelled`: stop/session generation changed; no retry.
- `invalid_response` or parse error: one retry only if the deadline remains; otherwise drop for this cycle.
- timeout or transport error: one retry after 100 ms plus bounded jitter; otherwise drop.
- 429/rate limited: one retry after bounded provider delay; second rate limit drops.
- HTTP 4xx other than 429: definitive drop; no retry.
- HTTP 5xx: one retry, then drop.

A failed refresh never overwrites the last valid quote. It marks the symbol `last_error`, increments its failure counters, and exposes the age of the retained quote. Retained data older than 5 seconds is not eligible for a new entry; data older than 15 seconds is marked stale and cannot be used for any live signal action. Existing positions may still be marked to market from the last known value with an explicit stale-data status; no new order intent is created from stale data.

At the end of each scheduler interval, the signal-generation phase consumes a coherent snapshot: the latest valid quote per symbol whose generation matches the current universe. Missing or stale symbols produce explicit `hold`/`missing` rows for the widget and never produce order intents. `latest-by-symbol` counts cover the complete selected universe state before display pagination.

## 8. Account snapshot cadence and safety

The account lane runs at most once per 15 seconds and is single-flight. Before an attempt it atomically reserves exactly 10 request costs, then calls at most 6 paginated `listAccounts` pages and at most 4 valuation tickers required to value non-zero holdings. It does not call one account snapshot per quote worker or per selected symbol. A settlement event may request an immediate refresh, but an existing in-flight refresh is coalesced and a second refresh is not started. If the reservation is unavailable, a cap would be exceeded, the 15-second absolute deadline expires, or any required call fails, the attempt fails closed and publishes no partial snapshot.

Account snapshot state includes `snapshot_id`, `requested_at`, `received_at`, `age_ms`, `success`, `error_class`, `pages_used`, `tickers_used`, and `holdings_valued`. On failure, the prior snapshot may remain visible for diagnostics, but its age and error are surfaced. When age exceeds 45 seconds, live order admission fails closed with `account_snapshot_stale`; it does not fall back to synthetic/session capital. A successful snapshot atomically replaces the prior authoritative snapshot under the service mutex.

## 9. Stop Trading and cancellation

`stopSession` increments the cancellation generation and sets `stop_requested` under the state mutex. Admission rejects new work. Queued jobs are removed and counted as `cancelled`; workers observe cancellation before budget waits and before publishing. In-flight HTTP calls use the existing bounded timeout and are not assumed interruptible; their results are discarded if the generation changed. The worker drains persistence and resolves already accepted live orders according to the existing pending-order recovery path.

Stop does not submit a compensating order, does not mark an accepted order as cancelled without Coinbase evidence, and does not erase pending-order reservations until the existing order-resolution path establishes a terminal outcome. No quote completion after Stop may call `generateTickLocked`, queue a new order, or mutate the current session as though trading remained active.

## 10. Idempotent order boundary

Quote scheduling must not weaken order idempotency. Every generated intent carries `session_id`, `signal_id`, `symbol`, `side`, and a deterministic intent key. Before queueing an intent, under the service mutex, reject if the symbol already has a pending intent/order or if the session/generation is no longer active. The existing unique `client_order_id` is persisted before/with dispatch and is used for recovery lookup after ambiguous network outcomes. A timeout after submission is `unknown`, not rejected; the resolver searches by client order ID before any retry. No scheduler retry may resubmit an order intent.

## 11. API and diagnostics contract

Existing portfolio/status payloads retain their fields. Add an additive `quote_scheduler` object with:

```
{
  "enabled": true,
  "universe_generation": 7,
  "selected_symbol_count": 42,
  "queue_capacity": 256,
  "queue_depth": 19,
  "inflight": 2,
  "worker_count": 2,
  "batch_size": 8,
  "configured_rate_per_second": 5.0,
  "tokens_available": 6.0,
  "queue_lag_ms": 410,
  "coverage_ratio": 0.83,
  "empty_universe": false,
  "oldest_quote_age_ms": 3200,
  "last_tick_duration_ms": 920,
  "account_snapshot_age_ms": 7400,
  "account_snapshot_ready": true,
  "admitted": 40,
  "coalesced": 12,
  "deferred_queue_full": 0,
  "cancelled": 0,
  "succeeded": 35,
  "missing": 7,
  "dropped_by_reason": {"rate_limited": 0, "timeout": 1},
  "p95_latency_ms": 840,
  "rate_limit_ratio": 0.0,
  "timeout_error_ratio": 0.02,
  "adaptive_state": "healthy"
}
```

Per-symbol coverage, if returned, includes `symbol`, `last_success_at`, `age_ms`, `queued`, `inflight`, `last_result`, `last_error_class`, `deferred_until`, and `quote_eligible_for_execution`. Secrets, API keys, request signatures, and raw authenticated account data are never included in diagnostics or logs.

Required counters/histograms include request attempts, success, invalid, 429, timeout, transport error, definitive 4xx, retry, cancellation, coalescing, queue-full deferral, queue lag, token wait, network latency, tick duration, stale-age buckets, selected-universe coverage, account refresh success/failure/stale, and order-intent blockers. Every metric is tagged only by bounded dimensions such as session mode, endpoint class, result class, and strategy; do not tag by unbounded raw error text or symbol in aggregate metrics.

## 12. Testable acceptance criteria

1. A selected universe of 0, 1, 42, and more than 256 symbols is accepted without silent truncation or blacklist behavior. For an empty universe, `coverage_ratio=1.0`, `oldest_quote_age_ms=0`, `missing=0`, and `empty_universe=true`; the controller performs no quote admission and account safety remains independent.
2. Queue depth never exceeds 256; in-flight requests never exceed `dispatch_limit`, and `dispatch_limit <= worker_count <= 4` even when hardware concurrency is large. Every adaptive transition updates the tuple atomically.
3. Duplicate refreshes for one symbol coalesce, and a full queue reports explicit deferral while retaining the symbol in coverage state.
4. Priority ordering is deterministic and favors managed exits, then unseen/hard-stale symbols, then soft-stale symbols, then ordinary refreshes; equal keys use selected order and job ID.
5. Token accounting never spends below zero, public quote work cannot consume the account reservation, and 429 causes immediate bounded backoff without a retry storm.
6. One timeout/5xx/parse failure retries at most once; a second failure drops only that cycle and retains any prior quote with age/error diagnostics.
7. No quote older than 5 seconds can create an entry intent; no quote older than 15 seconds can create any live order intent.
8. Account refreshes are single-flight and cadence-bound; an account snapshot older than 45 seconds blocks live orders and never falls back to simulated capital. A refresh requiring more than 6 pages or 4 valuation tickers fails closed without partial publication.
9. Stop Trading cancels queued work, discards late quote completions, prevents new intents, and leaves accepted Coinbase orders in the existing resolver path.
10. An ambiguous order submission is resolved by client-order-id lookup and is never blindly resubmitted.
11. Diagnostics expose complete selected-universe counts before UI pagination and include queue, budget, freshness, account, retry, and adaptive-controller state.
12. Tests use a fake clock, fake token bucket, fake Coinbase client, deterministic queue, and cancellation token to cover every state transition without contacting Coinbase.

## 13. Rollout and rollback

Phase 0: implement the scheduler behind `LIVE_QUOTE_SCHEDULER_ENABLED=false`; keep the existing synchronous path as the disabled fallback. Add fake-client/controller tests and metrics in shadow mode without changing signal or order behavior.

Phase 1: enable scheduling with `LIVE_QUOTE_SCHEDULER_SHADOW=true`. The scheduler records admission, queue, latency, freshness, and coverage decisions while the legacy fetch path remains authoritative. Compare selected-universe coverage, quote success, stale age, tick duration, and account age.

Phase 2: enable scheduler quote publication with live order execution still disabled. Require no increase in 429/error rates, no missing managed-exit coverage attributable to scheduler admission, and stable account cadence before proceeding.

Phase 3: enable for a small operator-approved live universe with the existing explicit live-order opt-in. Keep a kill switch that immediately disables scheduler publication and prevents new live order intents; do not kill pending-order resolution.

Rollback to the synchronous/disabled path when any hard condition occurs: any duplicate order intent, account snapshot stale while an order is admitted, queue or worker bound violation, unexplained selected-universe loss, sustained 429 ratio >= 5%, timeout/error ratio >= 10%, or p95 quote latency > 5 seconds for three controller intervals. Rollback must preserve the last authoritative account snapshot, pending-order records, and diagnostics. No database migration is required for the initial rollout; additive JSON fields and in-memory scheduler state are sufficient.
