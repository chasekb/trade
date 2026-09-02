# Bounded Adaptive Throughput Architecture for Normalized Signal Generation

Date: 2026-08-22
Task: `t_a9dfebf6`
Status: design only; no runtime or order-submission behavior is changed by this document.

## 1. Decision summary

The live worker must retain the semantic target of the simulated worker: one latest evaluation per symbol in the selected, ordered universe for each logical sweep. It must not achieve that target by issuing one unbounded request per symbol or by using `hardware_concurrency` as a fan-out setting.

The design is a bounded scheduler with:

- a fixed-capacity symbol queue and per-symbol freshness state;
- a provider-scoped token bucket for request budget;
- bounded request concurrency and bounded CPU workers;
- adaptive concurrency driven only by observed latency, rate-limit responses, timeout/error rate, tick duration, queue lag, stale age, and configured exchange budget;
- an independent account-snapshot cadence with a hard execution-authority freshness gate;
- durable per-sweep metrics and normalized API diagnostics;
- generation-scoped cancellation and deterministic stale-result suppression.

A quote failure can prevent evaluation for that symbol, but it can never be converted into a tradable signal. Missing, stale, warming, rejected, and execution-blocked states remain distinguishable.

## 2. Interfaces and ownership

The implementation should introduce these interfaces behind the existing live/simulated service boundary. Names are normative; concrete language/container choices are implementation work.

```text
QuoteScheduler
  start(SchedulerConfig, OrderedUniverse, GenerationId) -> RunningScheduler
  enqueue(SweepId, Symbol, FreshnessDeadline, Reason)
  next_batch(now) -> QuoteWorkItem[]
  complete(QuoteWorkItem, QuoteResult)
  cancel(GenerationId) -> CancellationReceipt
  snapshot() -> SchedulerDiagnostics

ExchangeBudget
  try_acquire(RequestClass, cost, now) -> Permit | BudgetDenied
  refund(Permit, unused_cost)
  snapshot() -> BudgetDiagnostics

QuoteProvider
  fetch_quotes(symbols, request_context, cancellation) -> QuoteResult[]

SignalWorkerPool
  evaluate(QuoteSnapshot, StrategyConfig, cancellation) -> SignalEvaluation

AccountSnapshotProvider
  refresh(cancellation) -> AccountSnapshot

IntentLedger
  reserve_once(IntentKey, evaluation_version) -> Reservation | Duplicate
  mark_dispatched(IntentKey, exchange_order_id)
  reconcile(IntentKey, terminal_outcome)

MetricsJournal
  append(SweepMetrics, AccountMetrics, IntentMetrics)
  latest() -> DurableDiagnostics
```

Ownership rules:

1. `QuoteScheduler` owns queue order, retries, freshness, and cancellation; it never decides whether an order is executable.
2. `SignalWorkerPool` owns CPU-bound feature/strategy evaluation; it emits immutable evaluations tagged with generation, sweep, symbol, and quote version.
3. `IntentLedger` is the only component allowed to turn an executable evaluation into a dispatchable intent. It serializes the check-and-reserve operation by `IntentKey = (session_id, symbol, strategy_revision, signal_epoch)`.
4. `AccountSnapshotProvider` is authoritative for available cash/holds in live mode. Signal generation may continue with an old snapshot for diagnostics, but order dispatch is prohibited when the authority gate fails.
5. `MetricsJournal` is append-only and bounded by retention policy; metrics are not inferred from paginated rows.

## 3. Capacity defaults and invariants

Defaults are deliberately conservative and must be explicit configuration, not provider or hardware discovery:

| Setting | Default | Invariant |
|---|---:|---|
| `max_selected_symbols` | existing configured universe limit (currently 500) | never silently truncate a user-selected universe; reject over-limit input |
| `max_inflight_quote_requests` | 4 | `1 <= value <= configured_exchange_concurrency_cap` |
| `max_symbols_per_quote_request` | 3 | provider API limit and budget cost are explicit |
| `quote_queue_capacity` | `max_selected_symbols` | no symbol is silently evicted |
| `max_inflight_cpu_evaluations` | 2 | independent from network concurrency; bounded by configured CPU cap |
| `sweep_target_interval` | 1 second | scheduling target, not permission to exceed budget |
| `max_quote_age_for_evaluation` | 5 seconds | older data is diagnostic-only and cannot produce an executable intent |
| `max_account_snapshot_age_for_dispatch` | 5 seconds | stale or missing account authority blocks dispatch |
| `max_attempts_per_symbol_per_sweep` | 2 | one initial attempt plus one bounded retry |
| retry backoff | 250 ms, then 1 s ceiling | no retry after cancellation, deadline, or hard 4xx |
| durable metrics retention | 24 h or 10,000 sweeps, whichever comes first | journal writes are bounded and failure is observable |

Hard invariants:

- Queue depth, request concurrency, CPU concurrency, retries, and durable writes are bounded.
- At most one current evaluation per `(generation, sweep, symbol, quote_version)` is accepted.
- No symbol is dropped without `drop_reason` and a metric event.
- A result from a cancelled or superseded generation is discarded before signal state or intent state mutation.
- A HOLD or insufficient-data result is not an order intent.
- No intent is dispatched unless the account snapshot, quote freshness, risk gates, and duplicate ledger checks all pass.
- The page size is presentation-only and cannot alter sweep coverage or summary counts.
- `Stop Trading` prevents new work and dispatch but does not claim cancellation of already accepted exchange orders.

## 4. Sweep lifecycle and full-universe approximation

The scheduler keeps the exact ordered selected universe in an immutable `UniverseSnapshot {generation_id, revision, symbols[]}`. A sweep creates one `SymbolWorkState` for every selected symbol, initially `pending`. The queue priority is:

1. symbols whose freshness deadline has expired, oldest age first;
2. symbols never successfully evaluated in the current sweep;
3. symbols with a prior transient failure and an unexpired retry deadline;
4. stable universe order as the deterministic tie-breaker.

A logical sweep is complete only when each symbol is `succeeded`, `held`, `insufficient`, `failed`, `stale`, or `cancelled`. Therefore a slow or rate-limited symbol is visible rather than silently omitted. The next sweep may reuse a successful quote only for diagnostics; it must not relabel an old quote as this sweep’s fresh evaluation.

State transitions:

```text
NEW -> RUNNING -> DRAINING -> STOPPED
              \-> DEGRADED (budget/backpressure/staleness) -> RUNNING

symbol: PENDING -> IN_FLIGHT -> EVALUATED
symbol: IN_FLIGHT -> RETRY_WAIT -> IN_FLIGHT (transient only)
symbol: IN_FLIGHT -> FAILED | STALE | CANCELLED
symbol: EVALUATED -> INTENT_CANDIDATE -> RESERVED -> DISPATCHED -> SETTLED
                                      \-> DUPLICATE | BLOCKED
```

`DEGRADED` is an observable operating condition, not a reason to increase fan-out. It causes the scheduler to preserve ordering and continue bounded work while reporting missed freshness. If the configured budget cannot cover the selected universe, the service remains safe but reports `coverage_state=budget_limited`; it does not invent signals for unvisited symbols.

Batching is adaptive only within the configured limits. Start at batch size 1 and increase to the configured maximum after two healthy observations (latency below target, no 429, and queue lag improving). Decrease to 1 on any 429, timeout, or worsening queue lag. Batch size changes are generation-local and recorded in metrics.

## 5. Exchange budgeting and adaptive concurrency

Each provider and request class has a token bucket:

```text
capacity = configured_burst_tokens
refill_rate = configured_requests_per_second
cost = endpoint-specific request cost
```

A request requires both a token permit and an available in-flight slot. A denied permit remains queued until its deadline; it is not bypassed by spawning more tasks. Account requests use a separate bucket reservation so quote traffic cannot starve account authority.

The controller samples rolling windows of only these permitted signals: request latency (p50/p95), 429/rate-limit responses, timeout/error rate, tick duration, queue lag, stale age, and configured exchange budget. It applies additive increase/multiplicative decrease:

- decrease concurrency by one and apply provider backoff after any 429;
- decrease by one when timeout/error rate or p95 latency breaches its configured threshold for two windows;
- hold when queue lag or stale age is rising;
- increase by one only after three healthy windows with no 429, bounded p95 latency, falling queue lag, and available token budget;
- never exceed the explicit cap or the token-bucket grant;
- after consecutive failures, stop retrying the affected symbol for the sweep and mark it `failed`/`stale`.

The controller must not use CPU count, memory size, event-loop task count, or observed instantaneous free capacity to raise the exchange fan-out. Hardware-derived values may only be used to validate a separately configured CPU worker cap.

## 6. Retry, drop, stale-data, and backpressure policy

Retryable: timeout, connection reset, 5xx, and provider-declared transient failure. Retry once with deterministic backoff and the same symbol work ID. Non-retryable: malformed symbol, authentication failure, unsupported endpoint, and other hard 4xx. A 429 is retryable only after the provider’s `Retry-After` (bounded by the sweep deadline); it also reduces concurrency.

At the sweep deadline, queued work becomes `stale` with `drop_reason=deadline`; in-flight work may finish but its result is discarded if its deadline or generation is no longer valid. No queue eviction is allowed: capacity pressure is represented by backpressure and missed freshness metrics.

Backpressure order:

1. stop admitting optional diagnostic refreshes;
2. preserve account-snapshot reservations and currently in-flight work;
3. stop retries before first attempts;
4. mark overdue symbols stale/failed;
5. enter `DEGRADED`; never exceed configured exchange budget.

A stale quote can be displayed with `data_status=stale` and its age, but cannot create or refresh an executable intent. A previously reserved intent must be revalidated against a fresh quote before dispatch; otherwise it is released with `stale_quote`.

## 7. Account cadence and execution authority

Account snapshots run on their own cadence (default 5 seconds, configurable) and are not fetched once per quote symbol. The latest snapshot includes `snapshot_id`, captured time, age, source status, cash/hold quantities, and error class. A refresh failure does not erase the last snapshot for diagnostics, but it sets `dispatch_authority=blocked` once the maximum age is exceeded.

Before every dispatch batch, the service atomically checks snapshot freshness, session state, reserved cash, current holdings, symbol-side constraints, quote freshness, and `IntentLedger`. If any check fails, the intent is recorded as `blocked` with a stable reason and no exchange call. Account refresh and quote scheduling may proceed while dispatch is blocked.

## 8. Cancellation and duplicate prevention

Every start creates a monotonically increasing `generation_id`; every sweep and work item carries it. `Stop Trading` atomically changes the session to `DRAINING`, increments the generation, cancels queue waiters, prevents retries and new CPU evaluations, clears undispatched reservations, and waits for workers to acknowledge cancellation. A quote request already in flight may return, but its generation check discards it before mutation.

Accepted exchange orders are not retroactively cancellable by this state transition. They continue reconciliation until terminal, and the API returns `stop_state=settling` while any accepted order remains unresolved. A subsequent start receives a new generation and cannot reuse old intents.

The duplicate key is persisted in the intent ledger before dispatch. An idempotency key is sent to the exchange when supported. A worker retry, duplicate websocket event, or repeated status poll can therefore produce at most one accepted intent for the same signal epoch. Recovery after restart reloads non-terminal ledger rows before admitting new intents.

## 9. Durable metrics and normalized API contract

Persist one `SweepMetrics` row/event per completed or cancelled sweep and one `SymbolOutcome` event per terminal symbol state. Required fields include generation/session/sweep IDs, ordered selected count, attempted/succeeded/held/insufficient/failed/stale/cancelled counts, queue depth and lag, batch size, in-flight quote/CPU counts, p50/p95 latency when sample count is sufficient, tick/sweep duration, quote age min/max/p95, 429/timeout/error counts, budget grants/denials, backpressure state, account snapshot age/status, blocked intents by reason, duplicate suppressions, and execution outcomes. Missing observations are `null`/`unobserved`, never zero.

The existing `/api/orderbook/live-signals` response should converge on:

```json
{
  "signals": [],
  "pagination": {
    "page": 1, "per_page": 50, "total_signals": 0,
    "total_scope": "latest_by_symbol_selected_universe",
    "total_pages": 0, "has_next": false, "has_prev": false
  },
  "summary": {
    "selected_symbol_count": 0, "evaluated_symbol_count": 0,
    "latest_signal_count": 0, "active_signal_count": 0,
    "average_strength": null, "last_updated": null
  },
  "diagnostics": {
    "coverage_contract": "full_selected_universe_latest_by_symbol",
    "coverage_state": "running",
    "universe_revision": null, "generation_id": null, "sweep_id": null,
    "attempted_symbols_this_tick": [], "quote_success_count": 0,
    "missing_latest_symbols": [], "stale_symbols": [],
    "oldest_signal_age_seconds": null, "stale_symbol_age_seconds": null,
    "tick_duration_ms": null, "sweep_duration_ms": null,
    "queue_depth": 0, "queue_lag_ms": null,
    "inflight_quote_requests": 0, "quote_concurrency_cap": 4,
    "batch_size": 1, "api_error_count": 0, "timeout_count": 0,
    "rate_limit_count": 0, "backpressure_state": "none",
    "account_snapshot": {"loaded": false, "age_seconds": null, "status": "unobserved"},
    "dispatch_authority": "blocked", "blocked_intents": {},
    "duplicate_intents_suppressed": 0, "expected_edge": null,
    "realized_edge": null, "execution_outcomes": {}, "stop_state": "stopped"
  }
}
```

Signals remain latest-by-symbol rows and preserve the existing signal, criteria, ML, strength, execution, and timestamp fields. `total_signals` is never cumulative history and never page length. Summary counts and average strength are computed before pagination across the filtered latest population. The frontend must render diagnostics as transport/coverage state, not as evidence that a signal is executable.

## 10. Intentional live/simulated deviations

- Live quotes are exchange-derived and simulated quotes are synthetic or explicitly live-parity paper data; identical schema does not imply identical prices or signals.
- Live work is budget- and freshness-limited; simulation can deterministically evaluate every symbol on a one-second clock. Live reports incomplete/stale coverage instead of fabricating a completed tick.
- Live account snapshots and exchange acceptance/fill reconciliation are authoritative; simulation uses paper balances and immediate/local fills.
- Live Stop Trading preserves accepted-order settlement; simulated stop can close paper positions according to its own contract.
- The selected universe, ordering, pagination semantics, signal gates, and normalized diagnostic meanings remain shared.

## 11. Test matrix and acceptance gates

| Scenario | Required assertion |
|---|---|
| Full universe, larger than page size | every selected symbol gets one terminal sweep outcome; page size does not change totals or active count |
| Queue capacity/backpressure | no unbounded tasks; no silent eviction; overdue symbols carry stale/drop reason |
| Healthy adaptive increase | concurrency/batch rises only within configured caps after required healthy windows |
| 429 and Retry-After | token permits/backoff honored; concurrency decreases; no request storm; rate-limit metric durable |
| timeout/5xx | exactly bounded retry; then failed/stale outcome; no executable intent |
| hard 4xx/auth error | no retry; dispatch remains blocked where authority is affected |
| stale quote | visible diagnostic row; execution blocked with `stale_quote` |
| account snapshot failure/age | signals may be diagnosed, but dispatch authority becomes blocked at threshold |
| concurrent workers | deterministic symbol ordering; immutable version checks reject late results |
| duplicate worker/replay | persisted intent key suppresses duplicate reservation and dispatch |
| Stop during quote fetch | generation increments; in-flight result discarded; no post-stop intent; cancellation receipt complete |
| Stop with accepted order | status is `settling`; reconciliation continues; no false cancellation claim |
| restart recovery | non-terminal intents reload before new dispatch; no duplicate exchange order |
| normalized pagination | `total_scope`, `has_next`, summary population, placeholders, and null/unobserved values are stable across pages |
| metrics durability failure | trading fails closed for dispatch, error is surfaced, and no fabricated zero metrics appear |

Implementation is not authorized by this task. The next implementation task must add the shared diagnostic schema and scheduler behind feature flags, then verify these cases in paper/read-only mode and exact-SHA remote CI before any live activation.
