# Generated-signal outcome and diagnostic attribution contract

Status: canonical producer/consumer design for live and live-parity simulated trading. This
is documentation only; it does not change runtime behavior. All enum values are stable
snake_case identifiers. Human-readable text is never an aggregation key.

## 1. Scope and invariants

Every evaluated symbol/tick emits exactly one evaluation record: an explicit skip, a
blocked intent, or an executable intent. Subsequent dispatch/fill observations are
immutable lifecycle events for that intent. `live` and `live_parity` use the same fields
and meanings; simulated execution must not claim exchange acceptance. An intent is not
an execution: only an authoritative positive fill creates an executed-trade record and
realized PnL. A stop/take-profit decision is an exit evaluation, not a failed entry.

## 2. Canonical evaluation record

The logical record is `generated_signal_outcome`:

```json
{
  "contract_version": 2, "session_id": "live_...", "trade_type": "live",
  "signal_id": "signal-...", "intent_id": "intent-...", "strategy": "orderbook",
  "symbol": "BTC-USD", "side": "buy", "intended_action": "open",
  "outcome_state": "blocked_intent", "signal_generated": true,
  "strength": 0.73, "strength_bucket": "medium", "expected_return": 0.021,
  "expected_return_bucket": "positive", "fee_adjusted_expected_return": 0.003,
  "required_edge": 0.018, "diagnostic_factor": "none",
  "blocker_reason": "pending_order", "skip_reason": null,
  "client_order_id": null, "external_order_id": null, "trade_id": null,
  "event_id": "uuid", "event_sequence": 1, "event_version": 1,
  "observed_at": "2026-08-22T00:00:00Z"
}
```

Required on every evaluation: `contract_version`, `session_id`, `trade_type`,
`signal_id`, `strategy`, `symbol`, `side`, `intended_action`, `outcome_state`,
`event_id`, `event_sequence`, `event_version`, and `observed_at`. `intent_id` is
required for a proposed intent (`blocked_intent` or `executable_intent`) and may be
null for an explicit skip. Numeric diagnostics are nullable when unavailable; never
coerce malformed or non-finite values to zero. `side` is `buy`, `sell`, or `none`;
action is `open`, `close`, `add`, or `none`.

`signal_generated`, `blocked`, and `executable_intent` are compatibility projections,
not authorities. `blocked` is true only for `blocked_intent`; `executable_intent` is
true for `executable_intent` and its later lifecycle. Consumers use `outcome_state`.

## 3. Outcome states

| State | Meaning | Executed-trade row? |
|---|---|---:|
| `explicit_skip` | No order intent was proposed: hold, warm-up, deliberate no-action, or unavailable data. | No |
| `blocked_intent` | An order/exit intent was proposed but a local policy, account, or venue gate prevented admission. | No |
| `executable_intent` | All local gates passed; eligible for dispatch. | No |
| `submitted_pending` | Dispatch was accepted/identified, but terminal authority data is unavailable. | No |
| `rejected` | Dispatch/submission was refused before any fill. | No |
| `terminal_unfilled` | Authority reports terminal completion with zero fill. | No |
| `partially_executed` | Authority reports a positive partial fill; persist actual filled quantity/value/fees. | Yes, filled portion |
| `fully_executed` | Authority reports a positive full fill. | Yes |
| `reconciliation_error` | Accepted work or a possible fill cannot safely be reconciled. | Never infer |

An evaluation is counted once. Lifecycle events do not create additional evaluations.
Blocked, skipped, rejected, and terminal-unfilled records are never fabricated losses.
A stop/take-profit exit must carry `intended_action=close`, `exit_rule`, and
`diagnostic_factor=exit_risk_rule`; it is not a `blocked_intent` when authorized.

## 4. Blocker taxonomy and precedence

`blocker_reason` is required only for `blocked_intent` and null otherwise. Emit the
first failing gate in this order: stale/missing data; ML/profitability policy; holding
policy; pending order; max positions; notional; venue side rule; cash/reservations;
explicit live opt-in. A close path records its exit rule instead of relabeling the
close as an entry blocker.

| Identifier | Meaning |
|---|---|
| `max_positions` | Positions plus reserved/pending entries reached the configured limit. |
| `pending_order` | A duplicate order for the symbol/action is already pending. |
| `spot_cannot_open_short` | Spot venue cannot open a new sell/short position. |
| `below_minimum_notional` | Estimated quote notional is below venue minimum or invalid/non-positive. |
| `insufficient_cash` | Spendable cash after reservations cannot cover notional plus estimated fee. |
| `live_execution_disabled` | Live execution was not explicitly enabled; never imply a paper fill. |
| `existing_holding` | An inherited/account holding is not eligible for a fresh strategy entry. |
| `existing_position` | Legacy alias for a session-managed position occupying the symbol. |
| `ml_profitability_gate` | ML confidence/profitability policy rejected the intent. |
| `stop_take_profit_close` | Legacy decision reason only; new authorized exits use `exit_rule` and `exit_risk_rule`. |
| `stale_or_missing_data` | Required quote, history, account snapshot, or model input is stale, missing, malformed, or non-finite. |

Legacy reads map `spot_cannot_open_short`, `existing_position`, `ml_confidence_gate`,
and `profitability_gate` to the canonical names. `unknown` is a fail-closed ingestion
bucket, never a producer choice. Additional reasons require a new contract version.

## 5. Diagnostic factors

`diagnostic_factor` is independent of `blocker_reason` and has exactly one value:

- `missing_expected_return`: expected return unavailable or invalid.
- `negative_fee_adjusted_edge`: edge is at or below fee/spread/slippage hurdle.
- `below_required_edge`: positive edge does not exceed configured required edge.
- `weak_strength`: strength is below configured minimum.
- `account_exchange_blocker`: account/venue constraint blocked admission; the specific blocker remains authoritative.
- `exit_risk_rule`: stop-loss, take-profit, or explicit exit-risk policy selected a close.
- `none`: no diagnostic factor applies.
- `unavailable`: legacy/migrated read only, never a new write.

Legacy prose values map at the API boundary. They are not aggregation buckets.

## 6. Dimensions and bucket policies

Every reportable evaluation and lifecycle outcome includes `strategy` (empty values
normalize to `unknown`), canonical `symbol`, `side`, `strength_bucket`, and
`expected_return_bucket`. Strength is numeric plus `strength_bucket` (`none`, `weak`,
`medium`, `strong`). Expected return is numeric plus `expected_return_bucket` (`missing`,
`negative`, `near_zero`, `positive`). Thresholds are session configuration, not frontend
constants; return `bucket_policy_version`, thresholds, and units in report metadata.

## 7. Persistence schema and lifecycle history

Do not serialize these records into `order_book_signals`: that table is order-book
specific, has globally unique `signal_id`, and requires non-null `symbol`, `signal_type`,
`strength`, `price`, and `timestamp`. The canonical persistence location is a dedicated
append-only table (or an equivalent sidecar collection) named `generated_signal_outcomes`.
A conforming relational implementation has this shape:

```sql
CREATE TABLE generated_signal_outcomes (
  id BIGSERIAL PRIMARY KEY,
  event_id VARCHAR(255) NOT NULL,
  contract_version INTEGER NOT NULL,
  session_id VARCHAR(255) NOT NULL,
  trade_type VARCHAR(32) NOT NULL,
  signal_id VARCHAR(255) NOT NULL,
  intent_id VARCHAR(255),
  event_sequence INTEGER NOT NULL,
  event_version INTEGER NOT NULL,
  outcome_state VARCHAR(32) NOT NULL,
  strategy VARCHAR(255) NOT NULL,
  symbol VARCHAR(255) NOT NULL,
  side VARCHAR(16) NOT NULL,
  intended_action VARCHAR(16) NOT NULL,
  signal_generated BOOLEAN NOT NULL,
  strength REAL, strength_bucket VARCHAR(32) NOT NULL,
  expected_return REAL, expected_return_bucket VARCHAR(32) NOT NULL,
  fee_adjusted_expected_return REAL, required_edge REAL,
  diagnostic_factor VARCHAR(64) NOT NULL,
  blocker_reason VARCHAR(64), skip_reason VARCHAR(64),
  client_order_id VARCHAR(255), external_order_id VARCHAR(255), trade_id VARCHAR(255),
  exit_rule VARCHAR(32), diagnostic_detail VARCHAR(255),
  observed_at TIMESTAMP NOT NULL, payload JSONB,
  UNIQUE (session_id, event_id),
  UNIQUE (session_id, signal_id, event_sequence, event_version),
  UNIQUE (session_id, intent_id, event_sequence, event_version)
);
CREATE INDEX generated_signal_outcomes_scope_idx
  ON generated_signal_outcomes (session_id, trade_type, observed_at);
CREATE INDEX generated_signal_outcomes_dimensions_idx
  ON generated_signal_outcomes (strategy, symbol, side, outcome_state);
CREATE INDEX generated_signal_outcomes_intent_idx
  ON generated_signal_outcomes (session_id, intent_id, event_sequence);
```

The table is append-only: never update or delete an earlier lifecycle row. For each
`signal_id`, `event_sequence=1` is the evaluation and each later observation increments
the sequence. `event_version` starts at 1 for that observation; a correction to an
already emitted observation appends the same sequence with the next version. Therefore
the relational uniqueness key is `(session_id, signal_id, event_sequence, event_version)`;
the shorter `(session_id, signal_id, event_sequence)` key must not be used because it
would prohibit corrections. A producer retry of the same event uses the same
`(session_id,event_id)` and is a no-op; it must not create a new sequence or version.
A new authoritative observation appends the next sequence for the same `intent_id`.
`executable_intent -> submitted_pending -> rejected|terminal_unfilled|
partially_executed|fully_executed` are legal transitions. `blocked_intent` and
`explicit_skip` are terminal evaluations. `reconciliation_error` may be followed by a
new authoritative terminal event, but never by an invented fill. A terminal state may
not transition to another terminal state except through a correction version that
preserves the original event sequence and explains the correction in `diagnostic_detail`.
Restart recovery queries open `submitted_pending`/`reconciliation_error` intents by stable
`client_order_id` and `external_order_id` before dispatching again. If both IDs are absent,
the intent is not safely retryable and remains `reconciliation_error`.

`individual_trades` remains the executed-fill projection, with `trade_id`, session,
trade type, strategy, symbol, side, actual fill fields, fees, and explicit
`is_closing_leg`. It receives no row unless authoritative quantity is positive.
`trade_id` is deterministic from `(external_order_id, fill_id)` where available;
otherwise use a durable local idempotency key, never timestamp-only identity.

For a sidecar/document store, preserve the same fields and uniqueness keys in the
partition `(session_id, signal_id)` and event key `(intent_id,event_sequence,event_version)`;
nullable diagnostics must remain absent/null, not zero. This is the compatibility
fallback, not permission to use `order_book_signals` for non-orderbook records.

## 8. API and objective-impact report

`GET /api/execution/reconciliation` retains its envelope and returns scope, coverage,
canonical buckets, and per-strategy rows:

```json
{
  "contract_version": 2, "session_id": "sim_1", "trade_type": "live_parity",
  "coverage_complete": true, "signal_rows": 120, "outcome_rows": 8,
  "signal_rows_truncated": false, "bucket_policy_version": "session-3",
  "by_strategy": [{
    "strategy": "orderbook", "evaluated": 100, "signals_generated": 40,
    "explicit_skips": 60, "executable_intents": 4, "blocked_intents": 36,
    "outcomes": {"submitted_pending": 0, "rejected": 0, "terminal_unfilled": 0,
      "partially_executed": 0, "fully_executed": 4},
    "blocker_counts": {"pending_order": 6},
    "diagnostic_factor_counts": {"weak_strength": 12},
    "dimensions": {"by_symbol": {}, "by_side": {}, "by_strength_bucket": {},
      "by_expected_return_bucket": {}},
    "outcome_coverage": 1.0, "outcomes_unexplained": false,
    "objective_impact": {
      "executed_count": 4, "pnl_population": 4, "win_count": 3,
      "loss_count": 1, "win_rate_pct": 75.0, "average_realized_pnl": 0.012,
      "average_win_pnl": 0.018, "average_loss_magnitude": 0.006,
      "insufficient_data": false
    }
  }],
  "overall": {}
}
```

For any strategy/factor/dimension row, `executed_count` is the denominator for realized
PnL metrics; `pnl_population` counts only positive-fill trades with authoritative net
PnL. `win_rate_pct = 100 * win_count / pnl_population` when the denominator is greater
than zero, otherwise null with `insufficient_data=true`. `average_realized_pnl` is the
sum of net realized PnL divided by `pnl_population`; `average_win_pnl` divides by
`win_count`; `average_loss_magnitude` divides by `loss_count` and is positive. Blocked,
skipped, rejected, terminal-unfilled, pending, and reconciliation-error rows are
excluded from all PnL/win/loss denominators and never treated as losses. A factor's
`impact_population` is the subset of executed fills carrying that factor; zero means
all impact fields are null and `insufficient_data=true`. Legacy `win_rate` (0-100) and
positive `average_loss` remain supported as aliases; `total_fees` is not added twice to
net PnL.

`by_diagnostic_factor` is an array with one row per canonical factor (including zero
counts when the caller requests a complete taxonomy). Each row has `factor`, `evaluated`,
`blocked_intents`, `impact_population`, `executed_count`, `pnl_population`, `win_count`,
`loss_count`, `average_realized_pnl`, `average_win_pnl`, `average_loss_magnitude`,
`win_rate_pct`, and `insufficient_data`. Factor rows use the same formulas and null rules
as strategy rows; `impact_population` describes factor reach and is not a substitute for
`pnl_population`. `dimensions` uses the same row shape keyed by `symbol`, `side`,
`strength_bucket`, or `expected_return_bucket`. Blocked/skipped records can increase
counts in those rows but cannot enter any realized-PnL population.

The frontend preserves null versus zero, unknown future enum values as `unknown`, and
coverage/truncation warnings. It never infers execution from `executable_intent=true`.

## 9. Redaction, compatibility, and skip semantics

Never persist or return credentials, authorization headers, account IDs, full provider
responses, or sensitive provider error bodies. Report only authorized operator fields:
symbol, side, strategy, buckets, timestamps, estimates, actual fill/PnL/fee values.
Cash and holdings are scoped diagnostics, not public API fields. Redact order payloads
before logging. Human reason text must contain no secrets or full account snapshots.

`skip_reason` is canonical for `explicit_skip` and null for intents. Allowed values are
`stale_or_missing_data`, `warmup`, `no_signal`, `deliberate_hold`, and `unsupported_input`.
`stale_or_missing_data` is a skip reason only when no intent exists; when an intent was
proposed, use `blocked_intent` with `blocker_reason=stale_or_missing_data`. A missing
expected-return diagnostic may accompany either record only when that value was actually
unavailable. Readers map absent state plus `signal_generated=false` to `explicit_skip`,
`blocked=true` to `blocked_intent`, and `executable_intent=true` to `executable_intent`.
Malformed legacy rows remain visible as `unknown`/`reconciliation_error`, set a coverage
warning, and are never successful executions. Legacy null `is_closing_leg` retains its
historical read fallback only; all new writes set it explicitly, including flat closes.

## 10. Acceptance examples

1. Valid positive-edge buy with no holding, sufficient cash, and live opt-in: emit
   `executable_intent`, then immutable `submitted_pending`, then `fully_executed` and
   one `individual_trades` row after authoritative full fill.
2. Live-parity spot sell with no position: `blocked_intent`,
   `spot_cannot_open_short`, `account_exchange_blocker`; no trade row.
3. Indicator warm-up with no intent: `explicit_skip`, `skip_reason=warmup`; use
   `stale_or_missing_data` instead when the actual cause is stale/missing input.
4. Positive signal below fees: explicit skip or blocked intent according to whether
   an intent was proposed, with `negative_fee_adjusted_edge`; never account blocker.
5. Position crossing take-profit: exit evaluation with `intended_action=close`,
   `diagnostic_factor=exit_risk_rule`, `exit_rule=take_profit`, then normal dispatch/fill
   lifecycle; never classify the authorized close as an entry blocker.
6. Accepted order lookup timeout: append `reconciliation_error` (or retain
   `submitted_pending`) with stable IDs; invent no zero-fill/zero-fee trade and keep
   reservation visible until authority resolves it.
7. A report filtered by `session_id=sim_1&trade_type=live_parity` contains only that
   scope and surfaces `coverage_complete=false` or `signal_rows_truncated=true` rather
   than presenting partial totals as complete.
