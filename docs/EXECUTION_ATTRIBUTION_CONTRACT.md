# Generated-signal outcome and diagnostic attribution contract

Status: canonical design for live and live-parity simulated trading. This document is a
producer/consumer contract; it does not change runtime behavior by itself.

## 1. Scope and invariants

Every evaluated symbol/tick produces one attributable evaluation record, including a
hold, insufficient-data decision, blocked intent, or executable intent. Live and
`live_parity` use the same vocabulary and field meanings. Synthetic `simulated` may
have different exchange gates, but it must not claim that a paper decision was an
exchange acceptance.

An intent is not an execution. A signal can be executable locally, submitted, accepted
by an exchange, pending, rejected, partially filled, fully filled, or terminal with no
fill. Only authoritative fills create executed-trade rows and realized PnL. A stop or
take-profit decision is an exit intent and must remain distinguishable from an entry
signal.

All enum values below are stable snake_case identifiers. Human-readable reason text is
optional and never used for aggregation or compatibility decisions.

## 2. Canonical evaluation record

The canonical record is `generated_signal_outcome` (currently serialized inside
`order_book_signals.signal_data.execution_analysis`). Producers should emit these
fields:

```json
{
  "contract_version": 1,
  "outcome_state": "blocked_intent",
  "session_id": "live_...",
  "trade_type": "live",
  "signal_id": "signal-...",
  "intent_id": "intent-...",
  "client_order_id": "trade-...",
  "external_order_id": null,
  "trade_id": null,
  "strategy": "orderbook",
  "symbol": "BTC-USD",
  "side": "buy",
  "intended_action": "open",
  "signal_generated": true,
  "strength": 0.73,
  "strength_bucket": "medium",
  "expected_return": 0.021,
  "expected_return_bucket": "positive",
  "fee_adjusted_expected_return": 0.003,
  "required_edge": 0.018,
  "diagnostic_factor": "none",
  "blocker_reason": "pending_order",
  "blocked": true,
  "executable_intent": false,
  "timestamp": "2026-08-22T00:00:00Z"
}
```

Required identity/context fields are `contract_version`, `outcome_state`,
`session_id`, `trade_type`, `signal_id`, `strategy`, `symbol`, `side`,
`intended_action`, and `timestamp`. Numeric diagnostics are nullable when unavailable;
producers must not convert unavailable, malformed, or non-finite values to a
meaningful zero. `side` is `buy`, `sell`, or `none`; `intended_action` is `open`,
`close`, `add`, or `none`.

`blocked` and `executable_intent` are compatibility projections. Consumers must use
`outcome_state` as the authority: `blocked` is true only for `blocked_intent`, and
`executable_intent` is true only for `executable_intent` or a later accepted/executed
lifecycle that originated from it.

## 3. Outcome states

Use exactly one state for each evaluation or lifecycle snapshot:

| State | Meaning | Creates executed trade? |
|---|---|---:|
| `explicit_skip` | No order intent was proposed (hold, warm-up, stale/missing data, or strategy deliberately chose no action). | No |
| `blocked_intent` | A buy/sell/exit intent was proposed but a local policy, account, or exchange gate prevented admission. | No |
| `executable_intent` | All local gates passed; the intent is eligible for dispatch. | No |
| `submitted_pending` | Dispatch was attempted and accepted/identified, but terminal authority data is not available. | No |
| `rejected` | Submission or local dispatch was refused before any fill. | No |
| `terminal_unfilled` | Authority reported terminal completion with zero fill. | No |
| `partially_executed` | Authority reported a positive partial fill; persist actual quantity, price, value, and fees. | Yes, for the filled portion |
| `fully_executed` | Authority reported a positive full fill. | Yes |
| `reconciliation_error` | Accepted work or a fill cannot yet be reconciled safely (malformed/inconclusive authority response, persistence failure, or missing required identity). | Do not infer |

A `blocked_intent` is counted once at the decision point. A later exchange rejection
or no-fill is a lifecycle outcome, not another blocker. `explicit_skip` is counted in
evaluated coverage but not in generated signals or blocked intents.

## 4. Blocker taxonomy

`blocker_reason` is required for `blocked_intent`, and must be `null` for
`explicit_skip` unless the record also carries `skip_reason`. Only the first blocking
gate in the documented evaluation order is emitted; diagnostic fields may explain
why a signal was weak even when an account gate wins admission precedence.

Canonical reasons:

| Identifier | Use |
|---|---|
| `max_positions` | Managed positions plus reserved/pending entries reached the configured limit. |
| `pending_order` | An order for the symbol/action is already pending; do not treat a duplicate request as cancellation. |
| `spot_cannot_open_short` | Spot venue cannot open a new sell/short position. |
| `below_minimum_notional` | Estimated quote notional is below the exchange minimum or is non-finite/non-positive. |
| `insufficient_cash` | Spendable cash after pending reservations cannot cover notional plus estimated fee. |
| `live_execution_disabled` | Live execution is not explicitly enabled; this is never an implicit paper fill. |
| `existing_holding` | An account/inherited holding is not eligible for a fresh strategy entry under the selected management mode. Use `existing_position` as a legacy alias only. |
| `existing_position` | Legacy/current alias for a session-managed position already occupying the symbol. New producers should emit `existing_holding` when provenance matters and `existing_position` otherwise. |
| `ml_profitability_gate` | ML confidence/profitability policy rejected the generated intent. `ml_confidence_gate` and `profitability_gate` are legacy aliases. |
| `stop_take_profit_close` | A close was selected by a stop-loss or take-profit rule. This is an exit decision reason, not a failed entry; carry it in `decision_reason` (and `exit_rule`: `stop_loss` or `take_profit`) rather than pretending the authorized close was blocked. |
| `stale_or_missing_data` | Required quote, history, account snapshot, or model input is stale, missing, malformed, or non-finite. Carry `data_status` and `data_age_seconds` where available. |

Additional operational reasons may be added only with a new contract entry and a
compatibility mapping. `unknown` is a fail-closed ingestion bucket, not a producer
choice.

Recommended admission order is: data validity; ML/profitability policy; account
management/holding; pending order; max positions; sizing/notional; venue side rules;
cash/reservations; live execution opt-in. A close/exit path records its exit rule and
must not be relabeled as an entry blocker.

## 5. Diagnostic-factor taxonomy

`diagnostic_factor` explains the strategy/data reason for a generated or skipped
signal. It is independent of `blocker_reason`; both may be present. Use exactly one
of:

- `missing_expected_return`: expected return is unavailable or invalid.
- `negative_fee_adjusted_edge`: expected edge is zero or below the fee/spread/slippage hurdle.
- `below_required_edge`: expected edge is positive but does not exceed a separately configured required edge. If the implementation cannot distinguish this from the fee hurdle, use the former and set `diagnostic_detail` to `fee_hurdle` or `required_edge`.
- `weak_strength`: signal strength is below the configured minimum.
- `account_exchange_blocker`: the decision was prevented by account/venue constraints; the specific `blocker_reason` remains authoritative.
- `exit_risk_rule`: stop-loss/take-profit or another explicit exit-risk policy selected the close.
- `none`: no diagnostic factor blocked the strategy decision.
- `unavailable`: legacy/insufficient record; only accepted on reads or migration output, never as a new producer value.

`hold`, `no_signal`, `profitability_gate_reason`, and free-form prose are legacy
values and must be mapped at the API boundary, not aggregated as new factor buckets.

## 6. Required dimensions and bucket semantics

Every reportable signal, blocked intent, and executed outcome carries these dimensions:

- `strategy`: configured strategy identifier; empty values normalize to `unknown`.
- `symbol`: canonical venue product symbol, e.g. `BTC-USD`.
- `side`: `buy`, `sell`, or `none`.
- `strength_bucket`: `none` for no signal; otherwise `weak`, `medium`, or `strong` using the session's configured strength thresholds. Emit the numeric `strength` and threshold version alongside it; do not hard-code thresholds in the frontend.
- `expected_return_bucket`: `missing` when unavailable; otherwise `negative`, `near_zero`, or `positive` based on configured/report metadata boundaries. Emit the numeric value and bucket policy/version.

Bucket boundaries are part of the session configuration and must be returned as
metadata (`bucket_policy_version`, thresholds, and units). This prevents a later
report from silently comparing labels generated under different thresholds.

## 7. Persistence and reconciliation

Until dedicated columns are introduced, persist the complete record in
`order_book_signals.signal_data.execution_analysis`, keyed by `signal_id` and
`session_id`; do this for live and live-parity sessions. Persist executed lifecycle
records in `individual_trades` with `trade_id`, `session_id`, `trade_type`,
`strategy_type`, `symbol`, `side`, timestamp, actual fill fields, fees, and explicit
`is_closing_leg`. Do not create an `individual_trades` row for blocked, skipped,
rejected, or terminal-unfilled outcomes.

Identity rules:

1. `signal_id` identifies one evaluated signal record and is immutable.
2. `intent_id` identifies one admission/dispatch attempt and is stable across retries.
3. `client_order_id` is the locally generated idempotency key sent to the venue.
4. `external_order_id` is the venue's authoritative order id; acceptance without it remains pending/reconciliation-risk.
5. `trade_id` identifies one persisted fill/trade record and is derived deterministically from `(external_order_id, fill_id)` when the venue supplies both; otherwise use a durable local idempotency key, never a timestamp-only guess.

A reconciliation report must scope `session_id`, `trade_type`, and time window over
both signals and outcomes. It must expose row counts, truncation/coverage status,
by-strategy rows, blocker counts/shares, diagnostic-factor counts, dimension buckets,
and outcome coverage. Outcomes without a matching executable intent are
`outcomes_unexplained=true`; they must not be silently dropped.

## 8. API/report shape

`GET /api/execution/reconciliation` retains the existing envelope and adds:

```json
{
  "contract_version": 1,
  "session_id": "...",
  "trade_type": "live_parity",
  "coverage_complete": true,
  "signal_rows": 120,
  "outcome_rows": 8,
  "signal_rows_truncated": false,
  "by_strategy": [{
    "strategy": "orderbook",
    "signals_evaluated": 100,
    "signals_generated": 40,
    "explicit_skips": 60,
    "executable_intents": 4,
    "blocked_intents": 36,
    "outcomes": {"submitted_pending": 0, "rejected": 0, "terminal_unfilled": 0, "partially_executed": 0, "fully_executed": 4},
    "blocker_counts": {"pending_order": 6},
    "diagnostic_factor_counts": {"weak_strength": 12},
    "dimensions": {"by_symbol": {}, "by_side": {}, "by_strength_bucket": {}, "by_expected_return_bucket": {}},
    "outcome_coverage": 1.0,
    "outcomes_unexplained": false
  }],
  "overall": {}
}
```

The existing `blockers: [{reason,count,share,blocked_expected_return_sum}]` field,
`dominant_blocker`, and legacy metric names remain supported. `win_rate` remains a
0-100 percentage, `average_loss` remains a positive magnitude, and realized PnL is
net of actual fees. `total_fees` is not added a second time to PnL.

The frontend normalizer must preserve zeros with nullish fallback, retain unknown
future enum values as `unknown`, expose coverage/truncation warnings, and never infer
an execution from `executable_intent=true`. UI labels may be friendly; filtering and
aggregation use the canonical identifiers.

## 9. Redaction and privacy

Do not persist or return API credentials, secrets, raw authorization headers, account
IDs, full venue responses, or free-form provider error bodies containing sensitive
fields. Symbol, side, strategy, bucket labels, timestamps, notional estimates, and
actual fill/PnL/fee values are reportable to authorized trading operators. Treat
available cash and account holdings as scoped operational data: return only the
minimum needed for diagnostics and never expose them in public/unauthenticated
responses. Redact provider order payloads before logging. Human reason text must not
contain credentials, tokens, or full account snapshots.

## 10. Compatibility and migration

Readers accept the current `execution_analysis` fields and map:

- absent `outcome_state` + `signal_generated=false` -> `explicit_skip`;
- absent `outcome_state` + `blocked=true` -> `blocked_intent`;
- absent `outcome_state` + `executable_intent=true` -> `executable_intent`;
- `spot_cannot_open_short`, `existing_position`, `ml_confidence_gate`, and
  `profitability_gate` -> their canonical blocker aliases above;
- textual diagnostic reasons -> the closest canonical factor, otherwise `unavailable`.

Legacy rows with null `is_closing_leg` retain the historical fallback
(`pnl != 0`) only for compatibility. New writes must explicitly set the field,
including exact-flat closes. Unknown or malformed records remain visible in an
`unknown`/`reconciliation_error` bucket and must set a coverage warning; they must
never be counted as successful executions.

## 11. Acceptance examples

1. A generated buy with valid data, positive fee-adjusted edge, no position, enough
   cash, and live execution enabled: `executable_intent`, `diagnostic_factor=none`,
   `blocker_reason=null`; after venue acceptance, `submitted_pending`; after a full
   authoritative fill, `fully_executed` and one `individual_trades` row.
2. A generated sell in live-parity spot mode with no existing position:
   `blocked_intent`, `blocker_reason=spot_cannot_open_short`,
   `diagnostic_factor=account_exchange_blocker`; no trade row.
3. A hold during indicator warm-up: `explicit_skip`, `skip_reason=stale_or_missing_data`,
   `diagnostic_factor=missing_expected_return` only if the expected-return diagnostic
   was actually unavailable; otherwise `diagnostic_factor=none`.
4. A strong signal whose expected edge is below fees/spread/slippage:
   `explicit_skip` or `blocked_intent` according to whether an order intent was
   proposed, `diagnostic_factor=negative_fee_adjusted_edge`; it is not an
   `account_exchange_blocker`.
5. A managed position crossing take-profit: `blocked_intent` is not used for the
   already-authorized exit; emit an exit evaluation with `intended_action=close`,
   `diagnostic_factor=exit_risk_rule`, `exit_rule=take_profit`, followed by the
   appropriate submission/fill lifecycle state.
6. An accepted order whose provider lookup is timed out or malformed:
   `reconciliation_error`/`submitted_pending` with the stable client and external
   ids retained; no zero-fill or zero-fee trade is invented, and the reservation
   remains visible until authoritative resolution.
7. A report filtered to `session_id=sim_1&trade_type=live_parity` contains only that
   session's signals and outcomes; `coverage_complete=false` or
   `signal_rows_truncated=true` is surfaced rather than presenting partial totals as
   complete.
