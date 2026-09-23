# Execution blocker and diagnostic-factor contract

Status: implementation proposal only. This document changes no runtime behavior.

## 1. Purpose and non-negotiable invariants

The contract attributes every requested symbol evaluation and every generated actionable decision in live, live-parity paper, and simulated trading to exactly one durable terminal outcome. It is an additive, versioned replacement for inferring coverage from `execution_analysis` JSON plus aggregate `individual_trades` rows.

The producer records the decision before an external order or paper fill is attempted. A fill, rejection, cancellation, manual action, liquidation, or retry later attaches evidence to the same decision; it does not create another decision outcome. A report is complete only when it can prove the following for a closed runtime window:

```
evaluated = generated + non_generated_evaluations
generated = executed + blocked + skipped + unknown
missing_outcome = generated - terminalized_generated
```

`unknown` is an explicit reconciliation failure, never a convenient value used to make totals balance. Missing or conflicting evidence remains incomplete and visible. No unknown or malformed value authorizes live submission.

The objective follows `docs/STRATEGY_OBJECTIVE.md`: realized PnL is after fees and, where available, spread/slippage; blocked expected edge is opportunity-cost evidence, not realized PnL; and exchange/account blockers are reported separately from signal-quality gates.

## 2. Durable schema

The current `ensureSchema()` DDL in both trading services is the de facto migration mechanism. The implementation should move shared DDL/mapping logic into one schema helper, then dual-write these relations while legacy consumers remain active. JSON columns below are existing TEXT-compatible payloads: they must be bounded and parse-failure-safe, not PostgreSQL JSON casts.

### 2.1 `runtime_windows`

One row represents one producer run and its bounded reporting interval.

```sql
runtime_windows (
  runtime_window_id       TEXT PRIMARY KEY,
  schema_version          INTEGER NOT NULL DEFAULT 2,
  mode                    TEXT NOT NULL, -- simulated|live_paper|live
  session_id              TEXT NULL,
  started_at              TIMESTAMPTZ NOT NULL,
  ended_at                TIMESTAMPTZ NULL,
  closed                  BOOLEAN NOT NULL DEFAULT FALSE,
  selected_universe_hash  TEXT NULL,
  selected_symbol_count   INTEGER NULL,
  producer_version        TEXT NULL,
  close_reason            TEXT NULL,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CHECK (mode IN ('simulated','live_paper','live')),
  CHECK (closed = FALSE OR ended_at IS NOT NULL)
)
```

A window is report-complete only after `closed=true`, `ended_at` is set, all requested evaluations have been terminalized or an explicit unresolved count is stored, and the query is neither truncated nor filtered into a false whole-window claim. The universe hash is a non-secret identity for the selected universe; the report also returns selected/evaluated/quote-attempted counts.

### 2.2 `execution_signals`

One row is the canonical decision record for one symbol evaluation. Persist HOLD/non-generated evaluations and requested symbols with missing quotes/data, not only successful signal JSON.

```sql
execution_signals (
  signal_id                    TEXT PRIMARY KEY,
  schema_version               INTEGER NOT NULL DEFAULT 2,
  runtime_window_id            TEXT NOT NULL REFERENCES runtime_windows(runtime_window_id),
  session_id                   TEXT NULL,
  correlation_id               TEXT NOT NULL,
  idempotency_key              TEXT NOT NULL UNIQUE,
  producer_instance_id         TEXT NOT NULL,
  decision_sequence            BIGINT NOT NULL,
  strategy                     TEXT NOT NULL,
  symbol                       TEXT NOT NULL,
  side                         TEXT NOT NULL, -- buy|sell|hold|close|unknown
  action                       TEXT NOT NULL, -- entry|add|exit|hold|none|unknown
  strength_bucket              TEXT NOT NULL, -- weak|medium|strong|unknown
  expected_return_bucket       TEXT NOT NULL, -- unavailable|negative|near_zero|positive|unknown
  expected_return               DOUBLE PRECISION NULL,
  fee_adjusted_expected_return  DOUBLE PRECISION NULL,
  required_edge                 DOUBLE PRECISION NULL,
  generated                    BOOLEAN NOT NULL,
  data_status                  TEXT NOT NULL, -- sufficient|stale|missing|malformed|unknown
  paper_live_mode              TEXT NOT NULL,
  evaluated_at_epoch           BIGINT NOT NULL,
  evaluated_at                 TIMESTAMPTZ NOT NULL,
  terminal_at_epoch            BIGINT NULL,
  terminal_at                  TIMESTAMPTZ NULL,
  terminal_outcome             TEXT NULL, -- executed|blocked|skipped|unknown
  terminal_reason_code         TEXT NULL,
  objective_impact_class       TEXT NOT NULL, -- realized|blocked_edge|skipped|unknown
  objective_impact_json        TEXT NOT NULL DEFAULT '{}',
  metadata_redacted_json       TEXT NOT NULL DEFAULT '{}',
  metadata_truncated           BOOLEAN NOT NULL DEFAULT FALSE,
  created_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CHECK (paper_live_mode IN ('simulated','live_paper','live')),
  CHECK (terminal_outcome IS NULL OR terminal_outcome IN ('executed','blocked','skipped','unknown')),
  CHECK ((terminal_outcome IS NULL) = (terminal_at IS NULL)),
  CHECK (terminal_outcome IS NULL OR terminal_reason_code IS NOT NULL),
  CHECK (terminal_outcome IS NULL OR objective_impact_class IS NOT NULL)
)
```

`signal_id` is immutable and globally unique within the deployment. `idempotency_key` is deterministic from deployment/producer instance, runtime window, symbol, decision sequence, and schema version; it must not include mutable JSON. `correlation_id` joins retries, order attempts, and fills for one decision but does not replace uniqueness. Persisting the producer instance and sequence makes identity restart-safe: after restart, the producer resumes from a durable sequence/lease or creates a new instance namespace, and cannot reuse an existing key for different decision facts.

A generated row must end in a terminal outcome. A non-generated evaluation ends as `skipped`, including HOLD, stale/missing quote, missing expected return, and exit-risk/no-action decisions. A generated decision prevented before submission is `blocked`; a durable fill-producing action is `executed`; a failed persistence/external reconciliation path is `unknown`. Internal states (`created`, `evaluated`, `submitting`, `pending`) belong in an optional event log and are not report outcomes.

`objective_impact_json` is numeric, nullable-safe evidence: estimated/realized gross and net PnL, fees, spread/slippage estimate, expected edge, allocated notional, and settlement quantities. Null means unavailable; zero is a real value. It must never be interpreted as a command.

### 2.3 `execution_diagnostic_factors`

A signal may have zero or more ordered factors. This preserves all relevant explanations while the terminal reason identifies the governing outcome.

```sql
execution_diagnostic_factors (
  signal_id                 TEXT NOT NULL REFERENCES execution_signals(signal_id),
  factor_sequence            INTEGER NOT NULL,
  schema_version             INTEGER NOT NULL DEFAULT 2,
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

Required normalized factor codes are `missing_expected_return`, `negative_fee_adjusted_edge`, `below_required_edge`, `weak_strength`, `account_exchange_blocker`, and `exit_risk_rule`. Preserve unknown raw values for forward compatibility; normalize them to `unknown` for aggregation. An unknown condition whose safety cannot be established is `blocking=true` with `factoring_semantics=unknown` and fail-closed behavior. A bounded redaction/truncation failure is itself a factor, not silent data loss.

### 2.4 `execution_outcome_links` and settlement

Links attach all order/fill/leg evidence to one signal. They are immutable and idempotent.

```sql
execution_outcome_links (
  signal_id                 TEXT NOT NULL REFERENCES execution_signals(signal_id),
  link_sequence             INTEGER NOT NULL,
  link_type                 TEXT NOT NULL, -- order|trade|fill|position_leg|manual|liquidation
  trade_id                  TEXT NULL,
  order_id                  TEXT NULL,
  client_order_id           TEXT NULL,
  external_execution_id     TEXT NULL,
  parent_link_sequence      INTEGER NULL,
  quantity                  DOUBLE PRECISION NULL,
  price                     DOUBLE PRECISION NULL,
  fees                      DOUBLE PRECISION NULL,
  gross_pnl                 DOUBLE PRECISION NULL,
  net_pnl                   DOUBLE PRECISION NULL,
  settlement_status         TEXT NOT NULL, -- pending|partial|filled|zero_fill|rejected|cancelled|unknown
  is_closing_leg            BOOLEAN NULL,
  linked_at                 TIMESTAMPTZ NOT NULL,
  metadata_redacted_json    TEXT NOT NULL DEFAULT '{}',
  PRIMARY KEY (signal_id, link_sequence),
  UNIQUE (link_type, external_execution_id)
)
```

Partial fills are multiple links under one signal; `executed` requires at least one accepted fill/paper-fill link and reports requested, filled, remaining, fees, and settlement status. A zero-fill rejected/cancelled order is not executed and must terminalize as `blocked` or `unknown` according to whether the pre-submit blocker or external uncertainty is authoritative. Pending/partial rows cannot be reported as complete until settled or explicitly unresolved.

Manual intervention, exchange liquidation, and stop/take-profit actions retain `correlation_id` and signal linkage where they originated from a generated decision. An unprompted/manual/liquidation event gets a synthetic `action=exit` signal with `generated=false` and an explicit reason, so it is visible without being misattributed to an entry signal. Closing legs retain nullable `is_closing_leg` compatibility semantics; exact-flat exits remain representable.

A dual-write transaction must atomically persist the decision and its local order/link intent. If the external order call cannot be included in the database transaction, use an outbox with a durable idempotency key and do not claim `executed` until the accepted order/fill evidence is linked. Retry exhaustion writes `unknown` and halts the affected live path rather than silently dropping the post-analysis decision.

### 2.5 Indexes and constraints

Add indexes on `(runtime_window_id, evaluated_at, signal_id)`, `(strategy, symbol, evaluated_at)`, `(terminal_outcome, terminal_reason_code)`, `(paper_live_mode, runtime_window_id)`, and `(correlation_id)`. Enforce unique signal/idempotency identities, factor sequence uniqueness, and external execution identifiers transactionally. A terminal row is immutable as to classification: duplicate callbacks are accepted only when idempotency key and payload hash match; conflicting callbacks create an integrity error and fail closed.

## 3. Taxonomy and state machine

### 3.1 Blocker codes

Use stable snake-case values while accepting legacy aliases during migration:

- `max_positions`
- `pending_order`
- `spot_cannot_short` (legacy `spot_cannot_open_short`)
- `minimum_notional` (legacy `below_minimum_notional`)
- `insufficient_cash`
- `live_execution_disabled`
- `existing_holding` (legacy `existing_position`)
- `ml_profitability_gate` (legacy `profitability_gate`, `ml_confidence_gate`)
- `stop_take_profit_close`
- `stale_or_missing_data`

`nonpositive_position_size_or_price`, `account_position_management_disabled`, `no_signal`, `paper_fill`, `would_submit_order`, `rejected`, `not_found`, `submitting`, `pending`, and `terminal` remain raw legacy values unless a specific mapping is proven. Otherwise use normalized `unknown` and preserve the raw value. Exit, manual, and liquidation reasons must not be collapsed into entry blockers.

### 3.2 Terminal transitions

```text
created -> evaluated -> skipped
created -> evaluated -> blocked
created -> evaluated -> submitting -> pending -> executed
created -> evaluated -> submitting -> pending -> blocked
created -> evaluated -> submitting -> pending -> unknown
```

No terminal state transitions to another terminal state. `blocked` means an actionable intent was prevented before any fill. `executed` means at least one durable accepted fill/paper-fill link exists; it does not imply a complete fill. `skipped` means no actionable intent was produced. `unknown` means outcome evidence is unresolved after bounded retries. An unknown or malformed side/mode/strategy, missing account state, failed durable write, conflicting callback, or missing quote required for a live decision fails closed.

## 4. API contract

Keep `GET /api/trading/execution-reconciliation` compatible for current consumers. Add:

`GET /api/v2/trading/execution-reconciliation?runtime_window_id=&session_id=&mode=&strategy=&symbol=&side=&action=&from=&to=&terminal_outcome=&terminal_reason_code=&factor_code=&include_signals=&limit=&cursor=`

Filters are echoed in the response and apply identically to coverage and aggregates. `from`/`to` are explicit UTC bounds; a runtime-window request cannot claim a closed whole window if it omits the window end. Pagination uses `(evaluated_at, signal_id)` seek cursors bound to the complete filter set, not OFFSET. Read `limit+1` to set `truncated`; when truncated, `complete=false`.

Example response:

```json
{
  "schema_version": 2,
  "runtime_window": {
    "id": "rw_...", "mode": "live_paper", "started_at": "...Z",
    "ended_at": "...Z", "closed": true,
    "selected_symbol_count": 20, "quote_attempted_count": 20,
    "quote_success_count": 19
  },
  "filters": {"session_id": null, "mode": "live_paper", "strategy": null,
              "symbol": null, "side": null, "action": null,
              "from": "...Z", "to": "...Z"},
  "coverage": {
    "evaluated": 1200, "generated": 240, "non_generated": 960,
    "terminal": 240, "executed": 31, "blocked": 180,
    "skipped": 29, "unknown": 0, "missing_outcome": 0,
    "duplicate_signal_ids": 0, "unresolved_links": 0,
    "truncated": false, "complete": true,
    "warnings": []
  },
  "aggregates": {
    "dimensions": ["runtime_window_id", "mode", "session_id", "strategy",
      "symbol", "side", "action", "strength_bucket", "expected_return_bucket",
      "terminal_outcome", "terminal_reason_code", "diagnostic_factor", "time_bucket"],
    "rows": [{
      "mode": "live_paper", "strategy": "...", "symbol": "BTC-USD", "side": "buy",
      "strength_bucket": "strong", "expected_return_bucket": "positive",
      "terminal_outcome": "blocked", "terminal_reason_code": "pending_order",
      "diagnostic_factor": "account_exchange_blocker", "count": 1,
      "blocked_expected_return_sum": 0.004, "realized_pnl": null, "fees": null
    }]
  },
  "signals": [],
  "next_cursor": null
}
```

`include_signals=true` returns bounded signal rows, links, factors, and redacted metadata only. Authorization must be applied before serialization; operators may see diagnostic identifiers and bounded raw reason values, while normal consumers receive normalized values and no account/order secrets. Never return API keys, auth headers, account identifiers, wallet balances, raw order-book snapshots, credentials, or unredacted exchange errors. Enforce an 8 KiB metadata limit, set `metadata_truncated=true`, and emit a factor when truncating.

The internal producer write contract is idempotent and validates before any live submission:

```json
{
  "schema_version": 2,
  "runtime_window_id": "rw_...",
  "signal_id": "sig_...",
  "idempotency_key": "...",
  "decision": {"generated": true, "strategy": "...", "symbol": "...", "side": "sell",
    "action": "entry", "strength_bucket": "medium", "expected_return_bucket": "negative",
    "expected_return": -0.01, "fee_adjusted_expected_return": -0.012,
    "required_edge": 0.004, "mode": "live_paper"},
  "outcome": {"terminal_outcome": "blocked", "terminal_reason_code": "spot_cannot_short"},
  "diagnostic_factors": [{"factor_code": "account_exchange_blocker",
    "factor_value_raw": "spot_cannot_open_short", "factoring_semantics": "gate", "blocking": true}],
  "metadata": {"exchange": "coinbase", "quote_age_bucket": "fresh"}
}
```

Return `{schema_version, signal_id, accepted, terminal_outcome, duplicate, warning}`. A duplicate with matching payload is a successful no-op; a conflict is rejected and fail-closed. Malformed legacy JSON becomes `unknown`/`malformed_legacy_payload`, never an executable intent.

## 5. Aggregation and accounting

Aggregate by runtime window, mode, session, strategy, symbol, side, action, strength bucket, expected-return bucket, terminal outcome, blocker/reason, diagnostic factor, and UTC time bucket. Return evaluated, generated, non-generated, executed, blocked, skipped, unknown, missing, duplicate, unresolved-link, selected-universe, quote-attempted, and quote-missing counts. Reports must separately expose `blocked_expected_return_sum` and estimated cost drag; neither enters realized PnL.

Executed metrics use linked closing legs only. Preserve repository conventions: `win_rate` is 0–100, `average_loss` is a positive magnitude, Sharpe remains per-trade, and portfolio `total_fees` replaces rather than adds to a per-trade fee sum. Opening legs and zero-PnL open legs are excluded from win/loss denominators. For partial fills, realized quantity and net PnL are summed once across links; the parent signal is counted once. Manual/liquidation outcomes are separate exit/action cohorts and cannot inflate entry conversion.

`complete=true` requires: closed window with explicit end; all requested evaluations represented, including missing quotes; `generated = executed + blocked + skipped + unknown`; zero duplicate/conflicting identities; no unresolved settlement/linkage; no truncation; and no persistence/parse warnings. Never fill a missing row with `unknown` solely to balance arithmetic. Unknown/unresolved rows are visible, excluded from performance numerators, and mark the report incomplete.

## 6. Compatibility, migration, and fail-closed rollout

- Backfill `execution_signals` from `order_book_signals` using existing `signal_id`, session, symbol, timestamp, and `execution_analysis`; persist requested-symbol evaluations and missing-quote evaluations only from authoritative runtime counters, otherwise record an unresolved coverage warning.
- Backfill executed links from `individual_trades`; because the current table lacks `signal_id`, use `legacy_unlinked` and unresolved coverage rather than guessing by timestamp/symbol.
- Map known blocker aliases while preserving raw values. Legacy rows without reliable terminal decisions remain `unknown`; they do not silently become skipped.
- Dual-write normalized relations and legacy JSON. Compare counts, terminal outcomes, factor totals, settlement quantities, and blocker totals by closed window. Read v2 only after live and live-parity parity checks pass.
- `resetMlDatabases()` currently truncates `individual_trades` and `order_book_signals`; reset must clear normalized tables in foreign-key order and explicitly close/delete associated runtime windows.
- Shared schema and serializers must be used by live and simulated services so taxonomy, field presence, redaction, state transitions, and idempotency behavior are identical. Simulation may use a paper-fill link, but it still terminalizes `executed` only after durable fill evidence.
- A persistence or outbox failure queues bounded retries. Until the decision and linkage are durable, no live order is authorized. After exhaustion, write/surface `unknown`, stop the affected live path, and expose the error without secrets.

## 7. Implementation acceptance tests

Before enabling v2 reports, add tests for:

- requested-symbol and missing-quote coverage, including failed/stale data and post-analysis persistence drops;
- one terminal outcome per generated signal, duplicate callbacks, conflicting callbacks, and restart-safe idempotency;
- transition rejection after terminalization and fail-closed unknown handling;
- partial, zero-fill, rejected, cancelled, manual, liquidation, and stop/take-profit settlement/linkage;
- exact count reconciliation, explicit runtime end, filter/cursor binding, truncation, and unresolved warnings;
- factor cardinality, unknown raw preservation, redaction byte limit, authorization, and metadata truncation;
- fee/spread/slippage accounting without double-counting and correct closing-leg win/loss conventions;
- identical taxonomy/serialization for live, live-parity, and simulated modes;
- legacy backfill and dual-write parity before switching reads.

## 8. Existing source references

- `src/trading/SimulatedTradingService.cpp:314-369` — current schema and nullable `is_closing_leg` migration; `:940-1042` — signal/trade upserts; `:1045-1055` — signal identity; `:537-599` — blocker analysis.
- `src/trading/LiveTradingService.cpp:332-406` — live schema; `:1860-1929` — blocker precedence; `:2240-2260` — execution-analysis persistence boundary.
- `include/trading/ExecutionReconciliation.hpp:20-85` and `src/trading/ExecutionReconciliation.cpp:26-143` — current strategy-only aggregate API and unexplained-outcome limitation.
- `src/api/PredictController.cpp:1673-1801` — bounded legacy reconciliation, filters, parsing, and serialization; `:1651-1658` — reset truncation.
- `frontend/types/trading.ts:120-139` and `frontend/lib/executionReconciliation.ts` — existing compatibility shape and normalization.
- `docs/STRATEGY_OBJECTIVE.md:3-69` — objective, directional edge, diagnostics factoring, and fail-closed requirements.
