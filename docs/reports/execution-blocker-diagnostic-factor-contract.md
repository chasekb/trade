# Execution blocker and diagnostic-factor contract

Status: implementation proposal only; this document does not change runtime behavior.

## 1. Scope and design decisions

The contract attributes one evaluation of one symbol to one durable signal identity and one terminal outcome. It applies to live execution, simulated execution, and live-parity paper execution. The producer must persist the same decision facts before attempting an external order or paper fill; execution results may arrive later.

The contract is additive and versioned. Existing `order_book_signals.signal_data.execution_analysis` and `individual_trades` remain readable during migration, but new reports must use the normalized tables below. A report is not complete merely because an aggregate PnL row exists: it must prove generated-signal coverage and expose unresolved rows.

The objective semantics follow `docs/STRATEGY_OBJECTIVE.md`: realized PnL is net of fees, spread, and slippage where available; signal count is not an objective; and exchange/account safety blockers are measured separately from signal-quality gates.

## 2. Durable entities

### 2.1 `execution_signals` (one row per evaluated signal)

This is the canonical decision record. Persist every evaluated tick, including a HOLD/non-generated evaluation, so that skips are observable. `signal_id` is immutable and globally unique within the deployment; retries upsert the same record rather than creating a second evaluation.

```sql
execution_signals (
  signal_id                 TEXT PRIMARY KEY,
  schema_version             INTEGER NOT NULL DEFAULT 1,
  session_id                 TEXT NULL,
  correlation_id             TEXT NOT NULL,
  idempotency_key            TEXT NOT NULL UNIQUE,
  strategy                   TEXT NOT NULL,
  symbol                     TEXT NOT NULL,
  side                       TEXT NOT NULL,       -- buy|sell|hold|close|unknown
  action                     TEXT NOT NULL,       -- entry|add|exit|hold|unknown
  strength_bucket            TEXT NOT NULL,       -- weak|medium|strong|unknown
  expected_return_bucket     TEXT NOT NULL,       -- unavailable|negative|near_zero|positive|unknown
  expected_return            DOUBLE PRECISION NULL,
  fee_adjusted_expected_return DOUBLE PRECISION NULL,
  required_edge              DOUBLE PRECISION NULL,
  generated                  BOOLEAN NOT NULL,
  paper_live_mode            TEXT NOT NULL,       -- simulated|live_paper|live
  runtime_window_id          TEXT NOT NULL,
  generated_at_epoch         BIGINT NOT NULL,
  generated_at               TIMESTAMPTZ NOT NULL,
  terminal_at_epoch          BIGINT NULL,
  terminal_at                TIMESTAMPTZ NULL,
  terminal_outcome           TEXT NULL,           -- executed|blocked|skipped|unknown
  terminal_reason_code       TEXT NULL,
  objective_impact_class     TEXT NOT NULL,       -- realized|blocked_edge|skipped|unknown
  objective_impact_json      TEXT NOT NULL DEFAULT '{}',
  metadata_redacted_json     TEXT NOT NULL DEFAULT '{}',
  created_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CHECK (terminal_outcome IS NULL OR terminal_outcome IN
         ('executed','blocked','skipped','unknown')),
  CHECK ((terminal_outcome IS NULL) = (terminal_at IS NULL)),
  CHECK (terminal_outcome IS NULL OR terminal_reason_code IS NOT NULL)
)
```

`generated=true` means an actionable signal was produced; `generated=false` is a deliberate skip/hold evaluation. A generated row must eventually have `terminal_outcome`; a non-generated row must also be terminalized as `skipped` when the evaluation is persisted. `unknown` is a terminal reporting value only for an exhausted/reconciled failure path and must carry a reason such as `persistence_failure`, `malformed_legacy_payload`, or `external_result_unavailable`; it never authorizes an order.

`generated_at` and `terminal_at` are the authoritative instants. Epoch seconds preserve existing conventions; `TIMESTAMPTZ` is used for indexed bounded queries and audit. `runtime_window_id` identifies the run/session window and must have an explicit start and end in the API/report, not an implicit lower-bound-only query.

`idempotency_key` is deterministic from producer, runtime window, symbol, decision sequence, and signal version. It must not include mutable JSON. `correlation_id` joins retries, order attempts, and fills for the same decision but does not replace the unique signal key.

`metadata_redacted_json` may contain bounded, allow-listed diagnostic context only: model version, quote age bucket, spread bucket, feature names (not values), exchange venue, and configuration version. Never store API keys, auth headers, account identifiers, raw request payloads, full order-book snapshots, wallet balances, credentials, or unredacted exchange errors. Enforce a byte limit (recommended 8 KiB), reject or truncate with `metadata_truncated=true`, and record the truncation as a diagnostic factor.

`objective_impact_json` is numeric, nullable-safe evidence, not a command: expected return, fee-adjusted edge, estimated fees, estimated spread/slippage, allocated notional, and (for executed rows) realized gross/net PnL and fees. Unknown values remain null; zero is a real value. `objective_impact_class` distinguishes `realized`, `blocked_edge`, `skipped`, and `unknown` so blocked expected edge is never counted as realized PnL.

### 2.2 `execution_diagnostic_factors` (zero or more per signal)

```sql
execution_diagnostic_factors (
  signal_id                 TEXT NOT NULL REFERENCES execution_signals(signal_id),
  factor_sequence            INTEGER NOT NULL,
  schema_version             INTEGER NOT NULL DEFAULT 1,
  factor_code                TEXT NOT NULL,
  factor_value_raw           TEXT NOT NULL,
  factor_value_normalized    TEXT NOT NULL,
  factoring_semantics        TEXT NOT NULL, -- gate|size|exit|report|unavailable|unknown
  blocking                   BOOLEAN NOT NULL,
  observed_at                TIMESTAMPTZ NOT NULL,
  metadata_redacted_json     TEXT NOT NULL DEFAULT '{}',
  PRIMARY KEY (signal_id, factor_sequence)
)
```

Required normalized factor codes are:

- `missing_expected_return`
- `negative_fee_adjusted_edge`
- `below_required_edge`
- `weak_strength`
- `account_exchange_blocker`
- `exit_risk_rule`

The factor row preserves `factor_value_raw` for forward compatibility while reports bucket an unrecognized value as `unknown`. Unknown factor codes are reportable and non-blocking by themselves; if the producer cannot determine whether an unknown condition is safe, it must set `blocking=true`, `factoring_semantics=unknown`, and fail closed. Multiple factors are allowed and ordered; the terminal reason is the selected governing blocker, not a lossy concatenation of all factors.

### 2.3 `execution_outcome_links` (stable execution linkage)

```sql
execution_outcome_links (
  signal_id                 TEXT NOT NULL REFERENCES execution_signals(signal_id),
  link_sequence              INTEGER NOT NULL,
  link_type                  TEXT NOT NULL, -- order|trade|fill|position_leg
  trade_id                  TEXT NULL,
  order_id                  TEXT NULL,
  client_order_id           TEXT NULL,
  external_execution_id     TEXT NULL,
  linked_at                 TIMESTAMPTZ NOT NULL,
  metadata_redacted_json    TEXT NOT NULL DEFAULT '{}',
  PRIMARY KEY (signal_id, link_sequence),
  UNIQUE (link_type, external_execution_id)
)
```

A signal may link to several fills/legs, but every link is immutable and idempotent. The producer must link `trade_id`, `order_id`, and `client_order_id` when available; legacy rows may remain null. A closing leg must retain the existing nullable `is_closing_leg` compatibility behavior. `execution_signals` remains the source of terminal classification; links do not independently create an outcome.

### 2.4 `runtime_windows`

```sql
runtime_windows (
  runtime_window_id TEXT PRIMARY KEY,
  schema_version INTEGER NOT NULL DEFAULT 1,
  mode TEXT NOT NULL,                  -- simulated|live_paper|live
  started_at TIMESTAMPTZ NOT NULL,
  ended_at TIMESTAMPTZ NULL,
  session_id TEXT NULL,
  selected_universe_hash TEXT NULL,
  producer_version TEXT NULL,
  closed BOOLEAN NOT NULL DEFAULT FALSE
)
```

A window cannot be reported as complete until `ended_at` is set and the producer has either terminalized all signals or explicitly recorded an unresolved count. The selected universe is represented by a hash plus counts, not by secrets or an implicit global universe.

## 3. Enumerations and terminal state machine

### 3.1 Required blocker taxonomy

Use stable snake-case codes, retaining the existing spelling as aliases during migration:

- `max_positions`
- `pending_order`
- `spot_cannot_short` (legacy alias `spot_cannot_open_short`)
- `minimum_notional` (legacy alias `below_minimum_notional`)
- `insufficient_cash`
- `live_execution_disabled`
- `existing_holding` (legacy alias `existing_position`)
- `ml_profitability_gate` (legacy aliases `profitability_gate`, `ml_confidence_gate`)
- `stop_take_profit_close`
- `stale_or_missing_data`

`nonpositive_position_size_or_price`, `account_position_management_disabled`, `no_signal`, `paper_fill`, `would_submit_order`, `rejected`, and `not_found` are retained as raw legacy values or mapped to a more specific normalized code only when the mapping is provable. Otherwise use `unknown` plus the raw value.

### 3.2 Terminal outcomes

- `executed`: an order/fill or simulated paper fill is durably linked. `objective_impact_class=realized`; realized PnL is populated only when the leg is closing, and fees are separately retained.
- `blocked`: an actionable intent was prevented before submission/fill. `terminal_reason_code` is a required blocker and at least one blocking diagnostic factor is required for quality/account gates. No realized PnL may be inferred.
- `skipped`: no actionable intent was produced, including HOLD, stale/missing quote, unavailable expected return, or a deliberate exit-risk/no-signal decision. The reason and factors must explain why.
- `unknown`: the producer cannot safely establish the outcome after retry/reconciliation exhaustion. It is visible in every aggregate, marks the report incomplete, and never counts as executed.

Nonterminal internal states (`created`, `evaluated`, `submitting`, `pending`) may exist in an append-only event log, but they are not report outcomes. The current row changes to exactly one terminal value:

`created -> evaluated -> {executed, blocked, skipped, unknown}`

`evaluated -> submitting -> pending -> {executed, blocked, unknown}`

No terminal row may transition to another terminal value. A duplicate callback is accepted only if its idempotency key and payload hash match; conflicting callbacks create an integrity error and fail closed.

## 4. API contract

The existing `GET /api/trading/execution-reconciliation` remains compatible for old consumers. Add a versioned endpoint:

`GET /api/v2/trading/execution-reconciliation?runtime_window_id=&session_id=&mode=&strategy=&symbol=&side=&from=&to=&include_signals=&limit=&cursor=`

The response is:

```json
{
  "schema_version": 2,
  "runtime_window": {
    "id": "rw_...", "mode": "live_paper", "started_at": "...Z",
    "ended_at": "...Z", "closed": true
  },
  "filters": {"strategy": null, "symbol": null, "side": null},
  "coverage": {
    "evaluated": 1200, "generated": 240, "terminal": 240,
    "executed": 31, "blocked": 180, "skipped": 29,
    "unknown": 0, "missing_outcome": 0,
    "duplicate_signal_ids": 0, "truncated": false,
    "complete": true
  },
  "aggregates": {
    "dimensions": ["mode", "strategy", "symbol", "side", "strength_bucket", "expected_return_bucket", "terminal_outcome", "terminal_reason_code", "diagnostic_factor"],
    "rows": [
      {"mode":"live_paper", "strategy":"...", "symbol":"BTC-USD", "side":"buy",
       "strength_bucket":"strong", "expected_return_bucket":"positive",
       "terminal_outcome":"blocked", "terminal_reason_code":"pending_order",
       "diagnostic_factor":"account_exchange_blocker", "count":1,
       "blocked_expected_return_sum":0.004, "realized_pnl":null, "fees":null}
    ]
  },
  "signals": [],
  "warnings": []
}
```

`include_signals=true` returns bounded, paginated signal rows with redacted metadata and links; it never returns raw credentials or unbounded payloads. Pagination is timestamp plus `signal_id` cursor, not OFFSET-only, and a `limit+1` read sets `truncated`. A truncated response has `complete=false` and must not be described as full-window reconciliation.

Add a producer-side idempotent write API internally (or equivalent service method):

```json
{
  "schema_version": 2,
  "runtime_window_id": "rw_...",
  "signal_id": "sig_...",
  "idempotency_key": "...",
  "decision": {"generated": true, "strategy":"...", "symbol":"...", "side":"sell", "action":"entry",
               "strength_bucket":"medium", "expected_return_bucket":"negative",
               "expected_return":-0.01, "fee_adjusted_expected_return":-0.012,
               "required_edge":0.004, "mode":"live_paper"},
  "outcome": {"terminal_outcome":"blocked", "terminal_reason_code":"spot_cannot_short"},
  "diagnostic_factors": [{"factor_code":"account_exchange_blocker", "factor_value_raw":"spot_cannot_open_short",
                          "factoring_semantics":"gate", "blocking":true}],
  "metadata": {"exchange":"coinbase", "quote_age_bucket":"fresh"}
}
```

The response returns `{schema_version, signal_id, accepted, terminal_outcome, duplicate, warning}`. Validation failures reject the write and do not permit an order. Malformed legacy JSON is represented as `unknown`/`malformed_legacy_payload`, never treated as an executable intent.

## 5. Persistence, uniqueness, and migration

- `ensureSchema()` in `SimulatedTradingService.cpp:314-369` is the current de facto migration mechanism; the same additive DDL must be applied by both simulated and live services, preferably through a shared schema helper before splitting ownership.
- Use parameterized queries or the repository's safe escaping helper; never cast arbitrary legacy TEXT directly to JSON. `PredictController.cpp:1714-1756` currently parses `signal_data` and must retain parse-failure-safe behavior.
- Add indexes on `(runtime_window_id, generated_at, signal_id)`, `(strategy, symbol, generated_at)`, `(terminal_outcome, terminal_reason_code)`, and `(correlation_id)`. Unique constraints are `signal_id`, `idempotency_key`, `(signal_id,factor_sequence)`, and external execution identifiers.
- Backfill `execution_signals` from `order_book_signals` using existing `signal_id`, `session_id`, symbol, timestamps, and `execution_analysis`. Backfill executed links from `individual_trades`; because the current table lacks `signal_id`, mark linkage `legacy_unlinked` and coverage unresolved rather than guessing by timestamp/symbol.
- Map known legacy blocker strings to the normalized taxonomy while preserving raw values. Legacy rows with no reliable terminal decision remain `unknown`; they cannot silently become `skipped`.
- Dual-write normalized rows and legacy JSON during rollout. Compare counts and blocker totals by window. Read v2 only after parity is established; retain the old endpoint until all consumers migrate.
- `resetMlDatabases()` currently truncates `individual_trades` and `order_book_signals` (`PredictController.cpp:1651-1658`); reset must also clear normalized child/link tables in foreign-key order and close or delete the associated runtime window explicitly.

## 6. Reconciliation and aggregation rules

For a closed window, the invariant is:

`evaluated = generated + non_generated_evaluations`

`generated = executed + blocked + skipped + unknown`

`missing_outcome = generated - terminalized_generated`

A report is `complete=true` only when `missing_outcome=0`, duplicate counts are zero, the window is closed, and the query is not truncated. Any violation sets `complete=false`, emits a warning, and exposes the offending signal IDs/counts to authorized operators. Never fill a missing row with `unknown` merely to make counts balance; `unknown` is written only by an explicit reconciliation attempt.

Aggregate across these independent dimensions: runtime window, mode, session, strategy, symbol, side, action, strength bucket, expected-return bucket, terminal outcome, blocker/reason, diagnostic factor, and time bucket. Also report `generated`, `executed`, `blocked`, `skipped`, `unknown`, `missing`, duplicate, and unresolved-link counts.

Executed metrics use only linked closing legs and preserve current conventions: `win_rate` is 0–100, `average_loss` is a positive magnitude, `total_fees` is not added twice, and expectancy is per decided closing leg. Blocked metrics report count, share of generated intents, sum of fee-adjusted expected return, and estimated cost drag separately; these are opportunity-cost diagnostics, not realized PnL. Skipped metrics report reason/factor counts but do not enter win/loss denominators. Unknown/unresolved rows are excluded from performance numerators and shown as a data-quality risk.

`PredictController.cpp:1673-1801` and `ExecutionReconciliation.cpp:26-143` currently aggregate by strategy and infer coverage from executable intents/closing legs. They must evolve to join by `signal_id`, use the explicit window end, count every terminal outcome, and return coverage fields rather than inferring one outcome from aggregate ratios.

## 7. Fail-closed and acceptance criteria

- Missing expected return is `unavailable`/`missing_expected_return`; it cannot be interpreted as zero risk or permission to trade, consistent with `docs/STRATEGY_OBJECTIVE.md:41-58`.
- Unknown side, mode, strategy, blocker, factor, malformed payload, duplicate conflict, failed persistence, stale/missing quote, or missing account state is visible as unknown and blocks live submission. Unknown values are preserved raw for later mapping.
- A write failure queues a retry, but the producer must not claim `executed` until the durable signal/outcome and any order/fill linkage are accepted. On retry exhaustion, persist or surface `unknown` and halt the affected live path.
- Live and live-parity must emit identical decision taxonomy and fields. Simulation may use `paper_fill`; it must still terminalize as `executed` only after a durable simulated fill link.
- Stop/take-profit closes are `action=exit`, `terminal_outcome=executed` when filled, or `blocked`/`skipped` with `stop_take_profit_close` when not submitted; they must not be confused with entry blockers.
- Every generated signal has exactly one terminal outcome, proven by a unique row and coverage query. Multiple fills are links under that one outcome, not multiple outcomes.
- No runtime code is part of this proposal. Implementation should add schema/serialization/API tests for uniqueness, state transitions, legacy backfill, redaction limits, unknown handling, exact count reconciliation, and parity between live and live-parity modes before enabling v2 reports.

## 8. Existing code and convention references

- `src/trading/SimulatedTradingService.cpp:314-369` — current runtime schema and nullable `is_closing_leg` migration.
- `src/trading/SimulatedTradingService.cpp:940-1042` — batched signal/trade upserts and retry queue.
- `src/trading/SimulatedTradingService.cpp:1045-1055` — current signal identity construction.
- `src/trading/SimulatedTradingService.cpp:537-599` — simulated execution analysis and blocker decisions.
- `src/trading/LiveTradingService.cpp:1860-1929` — live blocker precedence and existing blocker names.
- `src/trading/LiveTradingService.cpp:2240-2260` — live execution-analysis persistence boundary.
- `include/trading/ExecutionReconciliation.hpp:20-85` — current aggregate attribution structures and strategy-only API.
- `src/trading/ExecutionReconciliation.cpp:26-143` — current blocker/PnL aggregation and unexplained-outcome limitation.
- `src/api/PredictController.cpp:1673-1801` — current bounded legacy endpoint, parsing, filters, and serialization.
- `frontend/lib/executionReconciliation.ts:12-187` — frontend normalization and existing 0–100/after-fee conventions.
- `frontend/types/trading.ts:120-139` — existing `execution_analysis` compatibility shape.
- `docs/STRATEGY_OBJECTIVE.md:3-69` — objective impact, directional edge, diagnostics factoring, and fail-closed requirements.
