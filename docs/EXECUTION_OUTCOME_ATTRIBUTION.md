# Signal outcome attribution contract

`trade::trading::SignalOutcomeAttribution` is the shared, storage-facing contract for one terminal result per generated signal or paper/live intent. It is intentionally independent of JsonCpp, PostgreSQL, exchange clients, and account models so the same validation and vocabulary can be used by live trading, live-parity simulation, persistence, and reporting.

## Required shape

- `signal_id` is the idempotency key; `session_id` is an opaque session scope. Neither may contain credentials, balances, or complete account details.
- `strategy`, `symbol`, `status`, `mode`, `timestamp_epoch_seconds`, and `runtime_window` are required.
- `status` is exactly one of `executed`, `blocked`, or `skipped`. A blocked or skipped safety decision is never represented as executed.
- `side` is `buy` or `sell` for executed outcomes and `none` for skipped outcomes.
- `blocker` uses the stable categories `max_positions`, `pending_order`, `spot_cannot_short`, `minimum_notional`, `insufficient_cash`, `live_execution_disabled`, `existing_holding`, `ml_or_profitability_gate`, `stop_or_take_profit_close`, `stale_or_missing_data`, `none`, or `unknown`.
- `diagnostic` uses `missing_expected_return`, `negative_fee_adjusted_edge`, `below_required_edge`, `weak_strength`, `account_or_exchange_blocker`, `exit_risk_rule`, `none`, or `unknown`.
- `strength_bucket` is derived from strength in `[0,1]`: `weak` `< .30`, `medium` `[.30,.70)`, `strong` `[.70,1]`.
- `expected_return_bucket` is derived from the return fraction: `negative` `< 0`, `neutral` `[0,.001)`, `positive` `[.001,.01)`, `high` `>= .01`.
- `objective` carries prediction-time expected return, fee-adjusted expected return, realized net PnL, fees, and net objective impact. Fees are non-negative and all numeric values must be finite.
- `safe_metadata` is bounded redacted labels only. Validation rejects sensitive labels such as `secret`, `password`, `token`, `credential`, `private_key`, and `balance`.

`validateSignalOutcome` returns an error for missing identifiers, invalid buckets, incomplete status/blocker combinations, non-finite values, unsafe metadata, or invalid objective values. Callers must fail closed: do not submit an order and do not persist the record when validation fails.

## Compatibility and reconciliation

Existing `SignalAttribution` and `OutcomeAttribution` structures remain unchanged for current aggregate/report callers. Legacy signal rows with no terminal attribution must be adapted with `legacySkippedOutcome`; they are visible as explicit skipped/unknown records and must not be counted as executed. New persistence should enforce one row per `signal_id` (idempotent insert/upsert) and retain the raw enum value if a future producer sends an unknown value, while normalizing reports to `unknown`.

A report is reconciled by joining the generated signal/intent `signal_id` to exactly one terminal outcome. Missing outcomes remain unexplained gaps; duplicate outcomes are a data-integrity error and must not be silently counted twice. Aggregate dimensions are strategy, symbol, side, strength bucket, expected-return bucket, diagnostic factor, runtime mode, and bounded runtime window. Win/loss metrics use realized net PnL on closing legs only; exact-flat gross exits with fees remain fee-negative outcomes.

## Integration points

- `LiveTradingService`: construct the record at the signal/gate boundary, classify every safety or exchange gate before dispatch, and persist an executed outcome only after the order/fill state is authoritative. Attribution must never enable an order.
- `SimulatedTradingService`: use the same builder and gate classifications. `live_parity` uses public market data and live-like gates but settles paper fills locally; it never dispatches exchange orders.
- Persistence: add the versioned outcome relation keyed by `signal_id`, with bounded text/JSON fields and an additive migration from existing signal/trade rows. Malformed legacy JSON is a skipped/unknown attribution, not a query-fatal cast.
- API/reporting: serialize enum strings and derived buckets, bound result sets, expose missing/duplicate/truncated reconciliation diagnostics, and never serialize account secrets or full account snapshots.
