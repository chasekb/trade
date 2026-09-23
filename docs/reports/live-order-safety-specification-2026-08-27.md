# Bounded Live-Order Safety Specification

**Status:** implementation-ready design contract; no runtime implementation or live-account testing is included.
**Date:** 2026-08-27

## 1. Scope and assumptions

This specification consolidates the live-order safety, observability, and acceptance contracts for bounded order-book trading. It applies to `LiveTradingService`, its persistence/exchange boundaries, and the existing API surface:

- `POST /api/trading/live/start`
- `POST /api/trading/live/stop` (the normative Stop Trading command)
- `GET /api/trading/live/status`
- `GET /api/trading/execution-reconciliation`

Current source seams are `include/api/PredictController.hpp:38-50`, `include/trading/LiveTradingService.hpp:128-211,239-291`, and the persistence, dispatch, worker, and startup paths in `src/trading/LiveTradingService.cpp:385-405,859-1200,2309-2437,2767-2864`.

Coinbase Advanced is the exchange authority. Existing explicit live-execution confirmation, cash/position/pending-symbol checks, minimum-notional checks, and strategy/risk gates remain mandatory; these controls add lifecycle, data-integrity, durability, and reconciliation gates. No automatic liquidation, mutation replay, restart auto-resume, or default-symbol substitution is permitted.

Validation uses an isolated database, deterministic monotonic clock, fake exchange/providers, fake telemetry sinks, and a hard zero-network assertion. No test uses live credentials, submits a real order, or mutates a real account.

### Safety invariants

1. No new entry is submitted unless lifecycle is `READY`, Stop Trading is not requested, the explicitly selected universe is validated and fully covered by fresh valid quotes, account authority is fresh, capacity/rate budget is available, all existing risk gates pass, and the intent is durably recorded before dispatch.
2. `collection_complete` is not execution eligibility. Only `coverage_complete` permits execution.
3. Every logical intent has one deterministic identity and at most one placement attempt. Unknown exchange outcomes are reconciled, never blind-retried.
4. Durable outbox rows and reservations are the restart authority; in-memory queues are performance buffers only.
5. Stop Trading blocks new entries immediately. It may continue explicitly permitted cancellation, lookup, fill settlement, and reconciliation work, but cannot claim clean stop while exchange exposure or persistence state is unresolved.
6. Unknown, missing, malformed, stale, or failed safety inputs fail closed. Telemetry failure cannot enable trading and must be visible as `UNKNOWN` or blocked.

### Invariant-to-evidence map

| Invariant | Enforcement/evidence | Validation scenarios |
|---|---|---|
| 1. Admission requires READY, complete fresh inputs, capacity, risk gates, and durable intent | `trade_live_blocked_intents_total`, coverage/account/queue gauges, `order_intent_blocked`, `order_outbox_committed`, status `can_trade` | S08-S11, S14-S15, S22 |
| 2. Collection is distinct from execution coverage | `trade_live_collection_coverage_ratio`, `selected_universe_evaluated`, status collection/coverage fields | S08-S09 |
| 3. One identity and no blind retry | idempotency-conflict/submission metrics, `order_intent_deduplicated`, `order_lookup_result`, client-ID trace chain | S07, S12-S13, S16 |
| 4. Durable outbox is restart authority | persistence/outbox-age metrics, `order_outbox_committed`, durable rows and restart recovery event | S13, S16, S20 |
| 5. Stop blocks entries and truthful drain/reconciliation | lifecycle transitions, drain/cancellation/reconciliation metrics and events, status deadline/pending counts | S01-S05, S17-S18, S21 |
| 6. Unknown inputs and telemetry fail closed | reason metrics, `live_session_blocked`, `persistence_failure`, `telemetry_delivery_failure`, diagnostic `UNKNOWN` | S10-S11, S19-S20, S22 |

## 2. Canonical vocabulary and configuration

### Lifecycle states

`STOPPED`, `STARTING`, `READY`, `DEGRADED`, `DRAINING`, `RECONCILING`.

`READY` means new execution may be admitted only after the per-tick gate passes. `DEGRADED` permits collection, diagnostics, cancellation, settlement, and reconciliation only when policy permits; it never authorizes a reduced-universe entry.

### Operator diagnostic states

`HEALTHY`, `DEGRADED`, `BLOCKED`, `DRAINING`, `RECONCILIATION_REQUIRED`, `UNKNOWN`.

Diagnostic state is derived from lifecycle plus evidence freshness; absent or stale diagnostic payloads are `UNKNOWN`, not healthy.

### Closed reason registry

`EXCHANGE_THROTTLED`, `EXCHANGE_UNAVAILABLE`, `INTERNAL_QUEUE_LAG`, `QUEUE_OVERFLOW`, `QUOTE_STALE`, `QUOTE_INVALID`, `UNIVERSE_INCOMPLETE`, `ACCOUNT_LAG`, `ACCOUNT_UNAVAILABLE`, `PERSISTENCE_FAILURE`, `IDEMPOTENCY_CONFLICT`, `CANCELLATION_TIMEOUT`, `RECONCILIATION_MISMATCH`, `CONFIG_INVALID`, `ALLOWLIST_UNAVAILABLE`, `MANUAL_REQUIRED`, `STOP_REQUESTED`, `DRAIN_DEADLINE_EXCEEDED`.

### Normative defaults and bounds

Deployments may tighten values only within the stated bounds. Missing, zero, negative, non-finite, or out-of-bound values reject startup/reload; no unsafe default is substituted.

| Control | Default | Allowed bound / behavior |
|---|---:|---|
| Quote normal freshness | 5 s | `age <= 5s` is normal; `>5s` is execution-ineligible; hard expiry is `>15s` |
| Account active freshness | 45 s | Older/absent blocks new orders |
| Account transport timeout | 10 s | Per request |
| Account absolute attempt deadline | 15 s | Includes one bounded retry |
| Provider retry | 1 | Only for known-not-submitted quote/account requests |
| Recovery | 3 healthy ticks and 15 continuous seconds | Both conditions required; any failed tick resets both |
| Queue capacity | 256 intents | Overflow rejects/block intents; no silent drop |
| Workers / dispatch concurrency | 2 / 2 | `dispatch <= workers <= 4` |
| Quote batch | 8 | Integer `1..32` |
| Scheduler tick deadline | 2 s | Deadline is a safety fault, not permission to submit partial data |
| Exchange token bucket | 5 requests/s, burst 10 | Rate `0.5..20/s`, burst `1..20`, burst no greater than two seconds of rate |
| Stop drain deadline | 30 s hard deadline | Expiry escalates to `RECONCILING` and `MANUAL_REQUIRED` |
| Allowlist refresh | 15 min | Cached allowlist max age 30 min; unavailable/expired blocks |
| Ambiguous lookup attempts | 30 complete-not-found attempts | Lookup cadence and total wall-clock bound are product decisions; no placement retry |
| Outbox/database retry | 1 | Only transient failure within a fixed operation deadline; exhaustion blocks |

Product decisions required before production sign-off are listed in Section 11; until decided, the safer behavior stated here is normative.

## 3. Order and Stop Trading state machine

```text
STOPPED --validated start--> STARTING --baseline + fresh full coverage--> READY
   ^                              | failure
   |                              v
   +-------------------------- STOPPED

READY <------ healthy inputs ------> DEGRADED
  |  stop, shutdown, kill switch, fatal fault, invalid reload
  v
DRAINING --all work terminal + durable status--> STOPPED
    |
    | deadline, unresolved cancel/lookup, ambiguous result, persistence failure
    v
RECONCILING --fresh account + exchange/durable agreement + operator approval--> STOPPED
```

`RECONCILING` never transitions directly to active trading. A separate explicit start is required after reconciliation.

### Start and readiness

`STOPPED -> STARTING` is accepted only when safety configuration is valid, selected products are non-empty and allowlisted, credentials exist, the initial account snapshot succeeds, and no unresolved durable order exists. `STARTING -> READY` requires a valid account baseline, one complete selected-universe collection, fresh valid quotes for every selected product, and no pending/ambiguous blocker. Any failure returns to `STOPPED` without starting a worker or placing an order.

### Per-tick admission gate

All conditions are conjunctive: lifecycle `READY`; atomic stop flag false; selected-universe collection complete; every selected product has a valid quote age `<=5s`; execution coverage is complete; allowlist is available/fresh; account age `<=45s`; queue and rate budget are available; no unresolved durable order exists for that product; and existing strategy/risk/account gates pass. A failed condition emits a blocked-intent reason and sends no entry.

### Stop contract

1. Under the lifecycle mutex, set `stop_requested=true` before the HTTP response. `generateTickLocked` must not create new intents and `dispatchOrders` must reject any dequeued entry after the flag is set.
2. Queued, not-submitted intents become `cancelled_before_submit`; release reservations only after the durable transition commits.
3. Persisted/submitted orders receive cancellation requests only when exchange evidence says they are cancellable. Cancellation is best effort and never converts unknown exposure to cancelled.
4. Poll status, fills, and cancellation for at most 30 seconds. Apply late acknowledgements/fills exactly once and persist each result.
5. Drain durable writes before clean stop. If any order or write is unresolved at the deadline, enter `RECONCILING`, retain rows/reservations, and return `reconciliation_required`.
6. Stop is idempotent. The response may be `accepted/draining`, `stopped`, or `reconciliation_required`; it must not claim all orders cancelled without exchange evidence.

### Restart contract

On startup, load all durable `submitting`, `pending`, `cancel_requested`, and `ambiguous` rows before enabling execution. Reconcile by `client_order_id` first, then exchange order ID; apply status/fill evidence idempotently. Missing rows, unavailable persistence, stale account authority, invalid payloads, or unresolved ambiguity leave the service `RECONCILING`/`STOPPED`. Restart never regenerates an intent, reuses an idempotency key, or auto-resumes.

## 4. Stale and degraded-mode policy

Quotes are normal through 5 seconds, stale/degraded and execution-ineligible above 5 through 15 seconds, and expired/invalid above 15 seconds. Missing, malformed, non-finite, crossed, or otherwise invalid quotes are execution-ineligible at every age. The exact hard-expiry comparison is `age > 15s`; this is a deliberate boundary decision.

`collection_complete` means every selected product has a terminal classification: valid, expired, malformed, timeout, or unavailable. `coverage_complete` means every selected product has a fresh valid quote. Failed terminal classifications count toward collection but never coverage. A selection change creates a new universe version and invalidates the prior execution snapshot.

The backend-owned Coinbase allowlist refreshes every 15 minutes and is rejected after 30 minutes. Product IDs are trimmed ASCII whitespace, upper-cased, validated as one `BASE-QUOTE` grammar, deduplicated after canonicalization, and checked against the allowlist. Explicit empty or invalid selection is rejected; it never falls back to `defaultSymbols()`.

Account authority is Coinbase data, not local estimation. Initial failure rejects start. A refresh timeout, transport, parse, or invalid-response failure gets one retry inside the 15-second attempt deadline, then preserves the last snapshot for diagnostics only, marks account health stale, and blocks entries. Unknown cash/positions block balance-dependent actions; no synthetic zero baseline is invented.

Recovery requires three consecutive healthy ticks and 15 continuous seconds of healthy inputs. Exits during `DEGRADED` require a fresh quote, active account authority, and explicit risk-policy approval; default policy blocks them too. Whether emergency market exits may bypass stale-quote gating is an unresolved operator decision.

## 5. Account and selected-universe safeguards

The selected universe is preserved in full in durable/audit state and status responses. Status must distinguish requested, collected, valid, expired, invalid, and execution-eligible counts, plus universe version and per-symbol diagnostic detail. Partial data never becomes a smaller implicit universe.

Account safeguards include: active snapshot age, source, success timestamp, error class, and whether the action depends on balances or positions. Account mismatch or unavailable authority blocks the affected action; account-authority mismatch defaults to session-wide stop, while an isolated order mismatch may be product-scoped only after product policy is approved.

## 6. Duplicate prevention, persistence, retries, and reconciliation

### Identity and outbox

`intent_id` is the SHA-256 digest of canonical UTF-8 `live:v1` intent content: schema/version, session ID, universe version, product, side, action, amount, amount unit, signal ID/timestamp, and strategy/risk decision version. Numeric formatting is finite and deterministic with sorted keys. `client_order_id = "live:v1:" + hex(SHA-256(canonical_intent))`, subject to confirmed exchange length limits; identity version changes when canonicalization changes.

The durable row is keyed by `client_order_id` and contains exchange ID (nullable/unique), session/universe identity, product/side/action/amount/unit, reservation, canonical payload/hash, lifecycle status, attempt count, error class, timestamps, trace context, and terminal evidence. Insert and reservation commit atomically. A duplicate key with identical payload returns the existing intent and never calls placement; a different payload is `IDEMPOTENCY_CONFLICT` and blocks the session.

### Submission and retry boundary

The outbox commit must complete before exchange submission. If it fails, there is no exchange call. Acknowledgement and exchange order ID must be persisted before applying fills or releasing reservations. If exchange acceptance is possible but acknowledgement persistence fails, retain `AMBIGUOUS` and reconcile; never submit again.

Definitive reject persists `rejected`, releases reservation after commit, and is not placement-retried. A throttle is retried only when known not to have reached the exchange and only within the token bucket/one-retry boundary. Timeout, connection reset, malformed response, and post-dispatch cancellation timeout are ambiguous: lookup by client ID/order ID only. Status/fill updates are idempotent by exchange ID and fill ID; partial fills remain pending until terminal evidence and account reconciliation.

### Reconciliation outcomes

Reconciliation compares durable order state, exchange order/status/fills, and a fresh account snapshot. Each row is classified `terminal_confirmed`, `pending`, `ambiguous`, `missing_from_exchange`, or `account_mismatch`, with evidence timestamp/error. Any nonterminal or mismatch blocks active trading for its configured scope. No local estimate overwrites exchange authority, no unknown exposure is released, and no automatic liquidation or guessed correction occurs.

## 7. Observability schema, dashboards, and alerts

### Metrics

Namespace: `trade_live_*`. Labels are closed enums/bounded buckets only: lifecycle state, operation, outcome, result, action, exchange, retry class, lane, freshness, coverage, and reason. Never label metrics with symbol, account, order ID, client ID, session ID, signal ID, trace ID, URL, or free-form error text.

Required families: quote requests and duration/freshness; selected symbols; collection/execution coverage ratio; account age and requests; scheduler duration/outcome; queue depth/capacity/wait; exchange requests/duration/throttles; orders submitted by action/result; idempotency conflicts; persistence operations/failures; outbox age; cancellation requests; drain duration; reconciliation discrepancies/age; lifecycle transitions; blocked intents; and telemetry delivery drops. Suggested exact names include `trade_live_collection_coverage_ratio`, `trade_live_order_queue_depth`, `trade_live_orders_submitted_total`, `trade_live_outbox_age_seconds`, `trade_live_reconciliation_discrepancies_total`, and `trade_live_blocked_intents_total`.

Use logs/audit/exemplars for correlation identifiers. Retain metrics 30 days hot and 13 months downsampled, order/audit events at least 13 months, and traces 7 days hot with 100% sampling for blocked, ambiguous, cancellation-timeout, persistence-failure, and discrepancy events. These retention values may be extended, not shortened, without decision.

### Structured events and traces

Events use JSON schema `trade.live.v1` and include event name/time, service/environment/severity, nullable session/intent/client/exchange/product/action identifiers, lifecycle state, reason code, attempt, duration/queue age, outcome, redacted error class, and W3C trace IDs. Required events cover session start/block/stop, universe evaluation, quote/account completion, intent create/block/deduplicate, outbox commit, submission start/result, acknowledgement, fill, lookup, cancel request/result, drain start/complete/escalation, persistence/telemetry failure, reconciliation completion/discrepancy.

Trace root is selection; child spans are `quote.collect`, `account.snapshot`, `intent.admit`, `outbox.commit`, `exchange.submit`, `exchange.lookup`, `exchange.cancel`, `fill.apply`, and `reconciliation.compare`. Retry retains the same intent/trace and increments attempt. Secrets, authorization headers, credential-bearing URLs, raw account numbers, and sensitive payloads are forbidden; balances/quantities are restricted to authorized audit sinks and redacted in ordinary logs. Events cap at 32 KiB with `payload_truncated=true` on overflow.

### Status API and dashboards

`GET /api/trading/live/status` should expose additive fields: lifecycle and operator state; `can_trade`; primary reason; requested/selected/valid/expired counts; collection and execution coverage; oldest quote age; account age/state; queue depth/capacity/oldest wait; throttle rate; pending/ambiguous/cancel-pending counts; outbox age; reconciliation state/age/discrepancies; drain deadline/remaining time; recovery ticks/window; `updated_at`; and `data_quality=FRESH|STALE|UNKNOWN`.

Dashboard panels must separately show readiness, market-data coverage, account health, execution pipeline, Stop/drain, and reconciliation. The UI must distinguish exchange throttling, internal queue lag, stale market data, account lag, and reconciliation. Missing/stale diagnostic data or telemetry delivery failure renders `UNKNOWN` and cannot infer health from zero/absent fields.

Alerts are deduplicated by `(alert_code, environment, bounded reason)` for 15 minutes and carry first/last seen and count. Recommended triggers: throttled share `>=20%` for 5 minutes; quote-fetch p95 `>2s` warn/`>5s` page; expired quote while READY; account age `>45s` warn/`>60s` page or missing; queue depth `>=192` warn/`>=256` page; queue wait p95 `>2s` warn/`>10s` page; any ambiguous submission, persistence failure while active, discrepancy, drain deadline, required reconciliation, or telemetry drops. Queue-age, outbox-age, and exact severity thresholds remain product decisions where not numerically stated.

No alert may claim safe stop while nonterminal orders or undurable writes remain. Alerts auto-resolve only after their stated recovery condition and emit a recovery notification.

## 8. Implementation slices and dependencies

```text
1 config/enums/reason registry
├── 2 schema + outbox + identity
├── 4 quote/universe freshness gate
├── 5 account authority refresh
└── 6 exchange classifier + token bucket + lookup/cancel
2 + 6 -> 3 lifecycle/stop-drain coordinator
2 + 3 + 4 + 5 + 6 -> 7 worker integration
2 + 6 + 7 -> 8 restart/reconciliation
1 + 3..8 -> 9 metrics/events/traces/status/UI/alerts
3..9 -> 10 deterministic fake acceptance fixtures and release gate
```

Implementation boundary is rollback-safe: disable live execution and leave `STOPPED`/`RECONCILING`; preserve outbox, reservations, audit, and account evidence. Never delete order rows, reuse IDs, or retry ambiguous requests. Rollout order is shadow telemetry, dry-run gate, sandbox exchange, then narrowly enabled production cohort.

## 9. Testable acceptance criteria

Every scenario uses `FrozenClock`, a scripted `FakeExchange`, transactional failure-injecting `FakeDatabase`, bounded queue, fake telemetry, restart harness, and zero-network assertion. Every pass includes exchange call ledger, durable rows before/after, transitions/events, metrics with bounded labels, trace assertions, status/dashboard/alert evidence, and exact timestamps.

| ID | Scenario | Required proof |
|---|---|---|
| S01 | Stop while queued | zero placements; queued intents terminal cancelled-before-submit; stop idempotent |
| S02 | Stop during submit | no second placement; cancellation/ambiguity handled; lookup before stop |
| S03 | Stop after accepted order | pending/fills settle or reconcile; no false clean stop |
| S04 | Stop after fill | one fill, fee, position/cash effect; repeated stop same result |
| S05 | Partial fill | known quantity once; remainder remains pending; no synthesized full fill |
| S06 | Definitive reject | one placement; rejected row; reservation released; no fill |
| S07 | Submit timeout/unknown | one placement; lookup by client ID; 30 not-found attempts max; no blind retry |
| S08 | Quote 5s/15s boundaries | `<=5s` normal, `>5s` blocked, `>15s` expired; no entry |
| S09 | Incomplete universe | collection and coverage differ; all selected products retained; zero entries |
| S10 | Account failure | one bounded retry; last snapshot preserved diagnostically; entries blocked |
| S11 | Account at >45s | stale state and blocked entry; no fabricated freshness |
| S12 | Concurrent duplicate | one durable key, one placement, one reservation/effect |
| S13 | Lost response/replay | existing intent lookup/continue; no insert or placement duplicate |
| S14 | Exchange throttling | token bucket <=5/s with burst <=10; no silent drop; stop preempts queue |
| S15 | Queue 255/256/257 | capacity bounded; 257th rejected with reason; order preserved |
| S16 | Restart pending rows | startup reconciles; no new entries/auto-resume; settle once |
| S17 | Cancellation success | cancellation and terminal state durable; remaining reservation released |
| S18 | Cancellation timeout | reconcile/manual required at 30s; no clean stop or new order |
| S19 | Reconciliation mismatch | preserve both observations; block scope; no guessed overwrite/liquidation |
| S20 | Telemetry/database failure | no false terminal state; one placement; outbox remains visible/retryable |
| S21 | Stop/start race | linearizable stop-wins result; stale command conflict; zero post-stop placement |
| S22 | Malformed unsafe intent | reject/quarantine before exchange; reservations unchanged; no sensitive payload logging |

Acceptance is not satisfied by `NOT TESTED` or `BLOCKED`. Critical scenarios require zero prohibited calls and zero duplicate placements. Implementation release additionally requires green remote CI for the implementation commit.

## 10. Failure and recovery outcomes

| Failure | Immediate outcome | Recovery authority |
|---|---|---|
| Invalid config/allowlist/selection | `STOPPED`, no worker/order | Correct config, refresh allowlist, explicit start |
| Stale/incomplete quote coverage | `DEGRADED`, entries blocked | Fresh complete new universe version; recovery window |
| Account stale/unavailable | `DEGRADED`, balance-dependent actions blocked | Fresh authoritative snapshot; recovery window |
| Queue/rate saturation | admission blocked/deferred, no silent drop | Bounded drain and operator-visible capacity health |
| Persistence failure before submit | no exchange call; blocked | DB repair and durable retry once |
| Persistence failure after possible acceptance | `AMBIGUOUS`/`RECONCILING`; no retry | Lookup and durable evidence |
| Exchange reject | terminal `rejected`; no placement retry | Policy/investigation, not automatic replay |
| Exchange timeout/reset/malformed response | `AMBIGUOUS`; lookup only | Exchange/client-ID reconciliation |
| Stop deadline/cancel unknown | `RECONCILING`, `MANUAL_REQUIRED` | Operator confirms exchange/account state |
| Restart with nonterminal rows | `RECONCILING`/`STOPPED` | Reconcile, then explicit operator start |
| Account/order mismatch | blocked configured scope | Fresh evidence and operator resolution |
| Telemetry outage | diagnostic `UNKNOWN`; safe stop remains possible; active health cannot be claimed | Restore sink and verify continuity |

Fail-closed recovery is distinct from operator-approved recovery: code may stop, preserve evidence, poll, and reconcile automatically; it may not resume live entries, release unknown reservations, overwrite authority, liquidate, or reuse identity without explicit operator approval.

## 11. Unresolved decisions and risks

1. Stop HTTP acknowledgement SLA and whether `accepted/draining` or fully drained is the normal response contract (S01).
2. Whether emergency exits may use stale quotes in `DEGRADED` (safe default: no).
3. Maximum tolerated missing selected products (safe default: zero for live entries).
4. Ambiguous lookup cadence and total wall-clock bound; the default cap is 30 complete-not-found attempts, but cadence must be chosen before implementation.
5. Cancellation policy for open/partial orders and permitted work after 30 seconds.
6. Queue-age, saturation, throttle, outbox-age, and unresolved-order alert thresholds/severities not explicitly fixed above.
7. Account/position mismatch tolerance and whether any automatic remediation is allowed (safe default: zero tolerance/no remediation).
8. Coinbase allowlist endpoint/cache implementation, credentials rotation, exchange client-order length limit, and rate-limit header semantics.
9. Terminal outbox/audit retention and archival policy; retain nonterminal rows indefinitely until decided.
10. Clock skew monitoring: negative ages are `UNKNOWN`, never fresh; deployment must report skew.

These are deliberate gates, not implementation freedoms. Until resolved, the safe defaults in this document apply and the affected feature remains blocked from live enablement.

## 12. Closeout evidence

A completed implementation must link each invariant to: (a) an enforcement seam and state transition, (b) named metric/event/status evidence, and (c) at least one S01-S22 deterministic validation scenario. Closeout requires the machine-readable evidence bundle, zero-network proof, remote CI results, and operator sign-off for the decisions in Section 11. Documentation completion alone confirms the contract, not runtime safety.
