# Live-order safety observability contract

Status: normative design contract
Date: 2026-08-27
Scope: live order safety and the bounded order-book market-data pipeline

This document defines the durable telemetry, diagnostic, and operator-evidence contract for live trading. It complements `docs/reports/live-order-safety-specification.md`; where this document names a metric, event, threshold, or state, implementations and tests MUST use the same vocabulary. Telemetry is diagnostic only: it MUST NOT authorize an order, bypass a safety gate, or turn an unknown state into a success.

## 1. Safety and state vocabulary

The live lifecycle states are `STOPPED`, `STARTING`, `READY`, `DEGRADED`, `DRAINING`, and `RECONCILING`. A missing, malformed, expired, or contradictory safety input is an execution blocker. Unknown is not healthy.

The normative stop endpoint registered by the backend is `POST /api/trading/live/stop`; `POST /api/trading/live/start` starts a session and `GET /api/trading/live/status` reports lifecycle/readiness. There is no alternate stop route in this contract.

Stop handling is two-phase:

1. Atomically set the stop request, prevent new intent admission, and stop dispatch of not-yet-submitted intents.
2. Allow already submitted exchange work to resolve or be reconciled. The bounded drain deadline is 30 seconds. At the deadline, unresolved work remains `UNKNOWN`/`RECONCILING` and the service reports `MANUAL_REQUIRED`; it is never marked cancelled merely because the timer expired.

Recovery requires three consecutive healthy scheduler ticks and a continuous 15-second stable window. A healthy tick requires valid selected-universe coverage, quote freshness, account freshness, queue bounds, and no unresolved order/reconciliation blocker. These are conjunctive requirements; the 15-second window is the sole recovery-window value.

## 2. Bounded scheduler and freshness contract

The following defaults and hard bounds are normative. A missing, zero, negative, non-finite, or out-of-range value fails closed to `STOPPED`/`DEGRADED` before live execution is enabled; deployments may tighten values without exceeding the bounds.

| Setting | Default | Hard bound / meaning |
|---|---:|---|
| intent queue capacity | 256 | fixed maximum 256; overflow rejects the intent and records `queue_full` |
| worker count | 2 | 1..4 |
| dispatch limit | 2 | 1..worker_count and never above 4 |
| quote batch size | 8 | 1..32 |
| exchange token rate | 5 requests/s | 0.5..20 requests/s |
| exchange token burst | 10 | 1..20 and no more than two seconds of configured rate |
| scheduler tick deadline | 2 s | positive and bounded; missed deadline is a degraded tick |
| exchange transport timeout | implementation setting | positive; order/account calls MUST have an explicit timeout |
| account transport timeout | 10 s | 1..10 s |
| account absolute attempt deadline | 15 s | 1..15 s, including retry time |
| retry count | 1 | at most one bounded retry, including parse/invalid responses |
| quote normal freshness | 5 s | age <=5 s is normal |
| quote hard stale/expired | >15 s | age >15 s is expired and execution-ineligible |
| account active freshness | 45 s | age <=45 s is active; older is degraded/blocked |
| selected-universe allowlist refresh | 15 min | cached allowlist max age 30 min |
| stop drain deadline | 30 s | unresolved work requires reconciliation/manual action |
| recovery window | 15 s | plus three healthy ticks |

A quote age is measured from the exchange quote timestamp to the observation time, not from log ingestion time. `fresh` means age <=5 seconds; `stale` means >5 and <=15 seconds; `expired` means >15 seconds, missing, malformed, or timestamp-inconsistent. A stale quote may remain visible for diagnostics but is not eligible for a new live intent. Expired quotes cannot be used for entries, exits, liquidation, or sizing.

An account snapshot is `active` only when loaded successfully, internally valid, and no older than 45 seconds. Transport failure, timeout, malformed/invalid response, absent baseline, or age >45 seconds is an account blocker. The one retry applies to transport and parse/invalid failures, but the 15-second absolute attempt deadline still wins.

## 3. Selected-universe and queue semantics

Live mode requires an explicit selected product list. Canonicalization trims ASCII surrounding whitespace and uppercases product IDs. Each product MUST match `^[A-Z0-9]+-[A-Z0-9]+$`; duplicates after canonicalization are rejected, as are empty selections, invalid IDs, and unsupported products. Live mode MUST NOT substitute `defaultSymbols()` for an empty or invalid explicit list.

The authoritative supported-product source is the backend Coinbase product allowlist fetched by the market-data/control-plane path. Its refresh interval is 15 minutes and its maximum usable cache age is 30 minutes. If the allowlist cannot be loaded or is older than 30 minutes, live execution fails closed. A syntactically valid but absent product is unsupported and rejected.

Coverage is per selected symbol and has one explicit terminal classification: `quote_ok`, `missing`, `malformed`, `timeout`, `transport_error`, or `unsupported`. `coverage_complete=true` means every requested symbol has a terminal classification, including failure classifications; it does *not* mean the universe is execution-ready. Any `missing`, `malformed`, `timeout`, `transport_error`, or `unsupported` result keeps `execution_eligible=false`, records the blocker, and is surfaced in the widget. A partial request, unclassified symbol, or unavailable allowlist sets `coverage_complete=false`.

Queue depth is the number of admitted, not-yet-terminal intents. Queue lag is observation time minus intent enqueue time. An intent is durably queued only after a transactional database/outbox row is committed. The current in-memory retry deque is not durable. If the outbox write fails, the intent is not dispatched and is reported as `persistence_failed`; if the process restarts, only committed `submitting`/`pending` rows are recovered. Restart after persistence failure MUST produce no exchange submission and a visible fail-closed diagnostic.

## 4. Durable metric catalog

Metric names use the `trade_live_` namespace. Every metric has the bounded labels shown below and a unit. High-cardinality values MUST NOT be metric labels: session IDs, correlation IDs, trace IDs, strategy/run IDs, universe versions, instruments, client order IDs, idempotency keys, exchange order IDs, queue sequences, and raw error strings belong in logs/audit records or exemplars only.

Metrics are emitted at scrape intervals and on terminal transitions where applicable. Counters and histograms are retained for 30 days; gauges for 7 days; durable order/reconciliation audit rows for at least 400 days or the platform's trading-record retention requirement, whichever is longer. Rollups MUST preserve hourly data for 400 days. The bounded labels are `mode` (`live|paper|simulated`), `venue` (`coinbase|unknown`), `result`/`reason` from finite enumerations, and `state` from the lifecycle vocabulary.

| Metric | Type | Labels | Unit / meaning |
|---|---|---|---|
| `trade_live_scheduler_ticks_total` | counter | mode, state, result | ticks; result `healthy|degraded|deadline_missed` |
| `trade_live_scheduler_tick_duration_seconds` | histogram | mode | seconds |
| `trade_live_intent_queue_depth` | gauge | mode, state | intents; never above 256 |
| `trade_live_intent_queue_lag_seconds` | histogram | mode | seconds from enqueue to dispatch/terminal |
| `trade_live_intent_rejected_total` | counter | mode, reason | intents; reason `stopped|draining|queue_full|invalid_universe|stale_quote|account_lag|reconciliation|persistence_failed|duplicate` |
| `trade_live_quote_requests_total` | counter | mode, venue, result | requests; result `success|timeout|transport_error|parse_error|rate_limited|unsupported` |
| `trade_live_quote_request_duration_seconds` | histogram | mode, venue | seconds |
| `trade_live_quote_age_seconds` | histogram | mode, result | seconds at decision time; result `fresh|stale|expired|missing` |
| `trade_live_selected_symbols` | gauge | mode | symbols in explicit selection |
| `trade_live_selected_universe_coverage_ratio` | gauge | mode, result | ratio 0..1; result `complete|partial` |
| `trade_live_selected_universe_age_seconds` | histogram | mode | seconds since selection/allowlist validation |
| `trade_live_selected_symbol_results_total` | counter | mode, result | symbols; finite result classifications |
| `trade_live_account_snapshot_age_seconds` | histogram | mode, result | seconds; result `active|degraded|expired|unknown` |
| `trade_live_account_snapshot_attempts_total` | counter | mode, result | attempts; result `success|timeout|transport_error|parse_error|invalid` |
| `trade_live_account_snapshot_failures_total` | counter | mode, reason | failures; bounded reasons |
| `trade_live_order_submission_total` | counter | mode, venue, result | attempts; `accepted|definitive_rejection|ambiguous|blocked` |
| `trade_live_order_submission_duration_seconds` | histogram | mode, venue | seconds |
| `trade_live_order_retry_total` | counter | mode, reason | retries; `transport|timeout|parse|invalid` |
| `trade_live_idempotency_conflicts_total` | counter | mode, result | conflicts; `duplicate_same_intent|key_reuse_mismatch|database_conflict` |
| `trade_live_order_outbox_total` | counter | mode, result | rows; `committed|write_failed|recovered` |
| `trade_live_order_terminal_total` | counter | mode, result | `filled|rejected|cancelled|not_found|unknown` |
| `trade_live_cancel_requests_total` | counter | mode, result | `requested|accepted|rejected|timeout|unknown` |
| `trade_live_drain_duration_seconds` | histogram | mode, result | seconds; `completed|deadline|manual_required` |
| `trade_live_reconciliation_total` | counter | mode, result | `matched|mismatch|unknown|manual_required` |
| `trade_live_reconciliation_discrepancy` | gauge | mode, kind | count of unresolved discrepancies; kind `order|fill|position|cash|symbol` |
| `trade_live_execution_blockers` | gauge | mode, reason | currently active blockers by finite reason |

Counters MUST be monotonic across process lifetime and reset safely on restart. A restart counter and deployment identifier belong in logs, not in metric labels. Expose exemplars containing trace/correlation IDs only when the metrics backend supports bounded exemplar storage.

## 5. Structured logs and audit events

Logs MUST be JSON records with an event name, UTC RFC3339 timestamp, severity, and schema version. Each order, decision, queue, account, cancellation, and reconciliation record MUST carry these correlation fields when applicable:

- `correlation_id` and `trace_id` (required for request/operation records; nullable for startup)
- `strategy_id` and `run_id` (nullable for manual/liquidation operations)
- `universe_version` (nullable when no universe is involved)
- `instrument` (nullable for account-wide or lifecycle events)
- `client_order_id`, `idempotency_key`, and `exchange_order_id` (nullable until assigned)
- `account_snapshot_version` and `quote_timestamp` (nullable when not observed)
- `queue_sequence` (nullable when not queued)
- `mode` and `failure_classification` (required; use `unknown` rather than omission for an observed-but-unclassified failure)

The `failure_classification` enum is `none`, `validation`, `stale_data`, `coverage`, `account_lag`, `exchange_throttle`, `transport`, `parse_invalid`, `timeout`, `duplicate`, `persistence`, `cancel_drain`, `reconciliation`, `configuration`, or `unknown`.

Mandatory events are `live.lifecycle_transition`, `universe.validation`, `market_data.quote_batch`, `decision.evaluated`, `intent.enqueued`, `intent.rejected`, `outbox.persisted`, `order.submission_attempt`, `order.retry`, `order.accepted`, `order.ambiguous`, `order.terminal`, `idempotency.conflict`, `account_snapshot.attempt`, `account_snapshot.updated`, `stop.requested`, `drain.progress`, `reconciliation.completed`, and `configuration.invalid`.

Example decision event:

```json
{
  "schema_version": 1,
  "event": "decision.evaluated",
  "timestamp": "2026-08-27T12:00:02.123Z",
  "severity": "INFO",
  "correlation_id": "cid-redacted-example",
  "trace_id": "trace-redacted-example",
  "strategy_id": "orderbook_v1",
  "run_id": "run-example",
  "universe_version": "uv-42",
  "instrument": "BTC-USD",
  "client_order_id": null,
  "idempotency_key": null,
  "exchange_order_id": null,
  "account_snapshot_version": "acct-901",
  "quote_timestamp": "2026-08-27T12:00:01.900Z",
  "queue_sequence": null,
  "mode": "live",
  "failure_classification": "stale_data",
  "decision": "blocked",
  "blocker_reason": "quote_stale",
  "quote_age_seconds": 5.4,
  "execution_eligible": false
}
```

Example submission event:

```json
{
  "schema_version": 1,
  "event": "order.submission_attempt",
  "timestamp": "2026-08-27T12:00:03Z",
  "severity": "INFO",
  "correlation_id": "cid-redacted-example",
  "trace_id": "trace-redacted-example",
  "strategy_id": "orderbook_v1",
  "run_id": "run-example",
  "universe_version": "uv-42",
  "instrument": "BTC-USD",
  "client_order_id": "trade-example",
  "idempotency_key": "idem-example",
  "exchange_order_id": null,
  "account_snapshot_version": "acct-901",
  "quote_timestamp": "2026-08-27T12:00:01.900Z",
  "queue_sequence": 187,
  "mode": "live",
  "failure_classification": "none",
  "attempt": 1,
  "outbox_state": "committed",
  "result": "accepted"
}
```

Credentials, JWTs, API keys, HMAC material, authorization headers, request signatures, raw account payloads, full exchange responses, and unrestricted strategy payloads MUST never be logged. Amounts and balances should be redacted or bucketed in ordinary logs; exact financial values belong only in access-controlled audit storage. Error strings must be normalized to bounded reason codes, with a separately access-controlled diagnostic reference if needed. Null fields may be omitted only where the schema marks them nullable; required correlation fields must not be silently invented.

## 6. Trace spans and propagation

Use W3C Trace Context (`traceparent`, optional `tracestate`) across HTTP and internal boundaries. Preserve one trace through the following spans:

- `live.http.start|stop|execute|status`
- `market_data.universe_validate`
- `market_data.quote_batch` and child `market_data.quote_request`
- `decision.tick` and `decision.signal`
- `queue.intent_enqueue` / `queue.intent_dequeue`
- `persistence.outbox_commit`
- `exchange.order_submit` and child `exchange.http_request`
- `exchange.order_lookup` / `exchange.fill_lookup`
- `account.snapshot_fetch` and `account.snapshot_apply`
- `cancellation.request`, `cancellation.exchange`, and `drain.wait`
- `reconciliation.load`, `reconciliation.compare`, and `reconciliation.complete`

The HTTP request creates the root span. The worker carries trace context with the intent; the outbox row stores the correlation/trace reference needed for restart recovery. Exchange boundaries propagate a sanitized trace header only when the provider permits it; never place credentials or order payloads in trace attributes. Span attributes are bounded enums, durations, counts, and redacted references. IDs may be span attributes but MUST NOT become metric labels. Span status is `OK` only after the operation's durable outcome is known; an accepted exchange request with unknown local persistence is `ERROR`/`UNSET` and creates reconciliation work, not a success.

## 7. Actionable alerts

Alerts are deduplicated by `alert_rule`, `mode`, `venue`, and bounded `failure_classification`; never by instrument or order ID. Include the first/last occurrence, affected counts, and a link to logs/traces. Resolve only after the stated recovery condition, not after a single good sample.

| Rule / severity | Trigger | Action, escalation, recovery |
|---|---|---|
| `live_config_invalid` / P1 | any invalid safety setting or unavailable allowlist | keep live `STOPPED`; page immediately; resolve after valid config and 3 healthy ticks + 15s |
| `live_exchange_throttled` / P2 | rate-limited responses >=3 in 5m or throttle ratio >=10% over 5m | freeze new submissions, preserve queue, inspect token bucket/provider limits; resolve with 10m below 1% and no queue growth |
| `live_queue_lag` / P1 | p95 lag >2s for 3 ticks or depth >=80% capacity | stop new admissions, page; resolve with p95 <1s for 3 ticks and depth <50% |
| `live_quote_stale` / P1 | any execution-eligible symbol expired, or >=10% selected symbols stale for 2 ticks | block affected/all execution according to coverage; resolve with complete fresh coverage for 3 ticks +15s |
| `live_universe_incomplete` / P1 | coverage incomplete or failed/unsupported symbol result | block all live entries; resolve when every symbol classified and all are valid/fresh for 3 ticks +15s |
| `live_account_lag` / P1 | snapshot age >45s, two failed attempts, or no baseline | block entries/exits; page; resolve after valid active snapshot and 3 ticks +15s |
| `live_order_ambiguous` / P1 | submission timeout/transport failure without definitive rejection | prevent same-intent resubmission; reconcile by client key; resolve only terminal exchange/local match |
| `live_idempotency_conflict` / P1 | key reuse mismatch or duplicate conflict | reject candidate, freeze affected symbol, page; resolve after operator review and durable audit |
| `live_retry_exhausted` / P2 | one bounded retry exhausted on any safety-critical operation | block affected operation; resolve after successful fresh operation and healthy window |
| `live_drain_overdue` / P1 | drain reaches 30s with pending work | set `MANUAL_REQUIRED`, no auto-cancel claim; page; resolve after explicit reconciliation |
| `live_reconciliation_mismatch` / P1 | nonzero order/fill/position/cash discrepancy | block impacted symbol/session; page; resolve only after authoritative match and audit record |
| `live_telemetry_missing` / P2 | expected tick/event metrics absent for 2 intervals | treat health as unknown; stop live execution if not restored; resolve after two complete intervals |

P1 pages the on-call immediately and escalates to the trading owner after 10 minutes. P2 notifies on-call and escalates after 30 minutes. Repeated resolution/re-fire cycles within one hour are one incident until the recovery condition has held for 15 minutes.

## 8. Operator widgets and diagnostics

The live dashboard MUST show lifecycle state, execution eligibility, last healthy tick, queue depth/lag, selected count, coverage ratio, quote age percentiles, account age, outbox/reconciliation status, and stop/drain progress. Each blocker is a separate diagnostic card with `state`, `observed_at`, `threshold`, `affected_count`, `failure_classification`, and `next_action`.

The widgets distinguish:

- **Throttling:** provider rate-limit count/ratio, token availability, request duration, retry count, and last rate-limit time; do not label this as quote staleness unless freshness also failed.
- **Queue lag:** depth, oldest intent age, p50/p95 lag, admission rejects, and worker/dispatch utilization; do not call provider throttling without a rate-limit result.
- **Stale quotes:** selected symbols by freshness class, oldest quote timestamp, missing/expired count, and whether the blocker is normal stale or hard expired.
- **Account lag:** snapshot age, last successful version/time, attempt/failure counts, and whether entries, exits, or both are blocked.
- **Reconciliation:** pending/ambiguous order count, drain age, discrepancy kind and count, authoritative source, and explicit `MANUAL_REQUIRED` state.

Response-only missing-symbol rows are allowed for visibility and MUST be marked `data_status=missing`, `execution_eligible=false`; they never create signals that submit orders. A widget showing zeros, an empty table, or an unavailable telemetry source MUST display `UNKNOWN`/`data unavailable`, not green.

## 9. Dashboard views and retention

1. **Safety overview:** lifecycle/readiness, active blockers, alert state, last healthy tick, and current execution eligibility.
2. **Market-data coverage:** selected-universe count/version, allowlist age, per-result counts, quote age distribution, batch duration, and throttling diagnostics.
3. **Order pipeline:** queue depth/lag, outbox committed/write failures, submission outcomes, retries, idempotency conflicts, and terminal states.
4. **Stop and recovery:** stop request time, drain progress/deadline, unresolved work, recovery tick count, and stable-window timer.
5. **Account and reconciliation:** snapshot age/version/failures, pending orders, fills, positions/cash discrepancies, and operator-required actions.

Raw structured events and trace exemplars are searchable for 30 days; hourly metric rollups and order/reconciliation audit records follow the retention values in section 4. Dashboard aggregation MUST preserve bounded labels and link to sampled traces/log records rather than copying high-cardinality IDs into time-series dimensions.

## 10. Acceptance criteria and failure fixtures

A tester may declare the contract satisfied only when each criterion has captured metric, log, trace, alert, and widget evidence with timestamps and correlation links:

- **Exchange throttling:** inject HTTP 429/rate-limit responses; token usage and bounded retry are visible, submission is blocked or delayed, `exchange_throttle` is logged, alert fires/deduplicates, and recovery requires the stated quiet window.
- **Queue lag/full:** hold the dispatcher; fill 80% and then 100% of the queue; lag/depth metrics rise, new intents reject at capacity, outbox state remains truthful, and the queue widget identifies lag rather than throttling.
- **Incomplete universe:** return one timeout, one malformed response, and one unsupported product; all symbols have terminal classifications, coverage semantics match section 3, no live order is admitted, and failed symbols are visible.
- **Stale quotes:** advance the clock beyond 5s and 15s; stale and expired classifications differ, expired data cannot create any order, and the stale-quote alert/widget identifies timestamps and affected count.
- **Account outage/lag:** fail both account attempts or advance age beyond 45s; execution becomes ineligible, failure metrics/logs/traces correlate to the tick, and a valid snapshot plus healthy window is required for recovery.
- **Duplicate/idempotency:** replay an identical key and then reuse it with a changed intent; the first is deduplicated as the same intent, the second is a conflict, no duplicate exchange submission occurs, and both outcomes are audited.
- **Retry exhaustion:** fail the initial and one retry; no third attempt occurs, the operation remains blocked/unknown as appropriate, and the retry-exhausted alert fires.
- **Late acknowledgement:** make submission ambiguous, then return a late exchange acknowledgement; lookup by client order ID resolves the existing order without resubmission, and the terminal transition updates durable state.
- **Stop/drain:** request `POST /api/trading/live/stop` with queued and in-flight work; queued work is not submitted, in-flight work receives cancellation/drain handling, the 30-second deadline is enforced, and unresolved work is `MANUAL_REQUIRED` rather than falsely cancelled.
- **Restart recovery:** persist a `submitting`/`pending` row, restart the worker, and recover it; separately fail the outbox write before restart and prove no order is submitted after recovery. Evidence must distinguish durable rows from the in-memory queue.
- **Reconciliation mismatch:** inject order, fill, position, cash, and symbol mismatches; discrepancy gauges/logs/traces/alerts and the reconciliation widget agree, and live execution remains blocked until authoritative resolution.
- **Combined failures:** combine throttling with stale quotes, queue lag with account lag, and stop/drain with an ambiguous order. The resulting state is the strictest fail-closed state, alerts deduplicate without losing classifications, and recovery requires all applicable conditions.

Production verification is limited to read-only status, metrics, logs, traces, and dry-run/sandbox exchange calls. Do not inject failures into live Coinbase accounts, cancel real orders for testing, alter production balances, or force restart of an active live session. Use deterministic clock injection, mock Coinbase responses, an isolated database, a fake outbox, and a trace/metrics test sink for the fixtures above.

## Source anchors

The current repository anchors used for this contract are:

- `include/api/PredictController.hpp:38-50` — registered live routes, including `POST /api/trading/live/stop` and reconciliation status.
- `include/trading/LiveTradingService.hpp:128-209` — pending writes, market quotes, order intents, persisted pending orders, account and quote seams.
- `src/trading/LiveTradingService.cpp:335-411` — order-book, trade, and live-order persistence tables.
- `src/trading/LiveTradingService.cpp:895-1032` — transactional-before-dispatch intent persistence and restart recovery query.
- `src/trading/LiveTradingService.cpp:1035-1225` — exchange submission, ambiguous outcomes, client-order lookup, and pending resolution.
- `src/trading/LiveTradingService.cpp:2309-2437` — worker lifecycle, account/quote fetch, stop and write-flush behavior.
- `src/trading/LiveTradingService.cpp:2526-2584` and `:3258-3363` — backend diagnostics and full selected-universe widget coverage.
- `src/api/PredictController.cpp:1673-1804` — execution reconciliation endpoint and persisted signal/trade attribution.

This is an implementation contract, not a claim that all telemetry exists today. Any missing item is a release blocker for enabling the corresponding live safety behavior.
