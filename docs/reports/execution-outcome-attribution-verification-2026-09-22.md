# Execution outcome attribution contract verification — 2026-09-22

## Verdict

The contract artifact exists, but the repository is only contract-plus-unit-test complete. It is not end-to-end complete: `SignalOutcomeAttribution` is not used by either trading service, no canonical terminal-outcome relation is persisted, and the API still reconciles legacy `execution_analysis` JSON against `individual_trades` without a signal-to-outcome join.

This is a bounded architecture handoff, not a claim that the parent backlog item is complete. Verification was read-only; no local build/test, live account access, order submission, database mutation, or runtime restart was performed.

## Evidence inspected

- Contract: `docs/EXECUTION_OUTCOME_ATTRIBUTION.md:1-31`.
- Canonical C++ type and validator: `include/trading/ExecutionReconciliation.hpp:11-100`, `src/trading/ExecutionReconciliation.cpp:11-193`.
- Validator/reconciliation unit fixture: `src/tests/test_execution_reconciliation.cpp:98-140` and `:142-234`.
- Legacy aggregation remains the active API contract: `include/trading/ExecutionReconciliation.hpp:112-177` and `src/api/PredictController.cpp:94-128`.
- API reads `order_book_signals.signal_data` and `individual_trades` independently: `src/api/PredictController.cpp:1783-1884`; it does not join `signal_id` to a terminal outcome or report duplicate/missing canonical rows.
- Both services create only `order_book_signals` and `individual_trades`: `src/trading/SimulatedTradingService.cpp:341-396` and `src/trading/LiveTradingService.cpp:350-424`.
- Both services persist legacy signal JSON/trade rows without canonical attribution fields: `src/trading/SimulatedTradingService.cpp:1159-1252` and `src/trading/LiveTradingService.cpp:1464-1557`.
- Execution analysis is diagnostic JSON built at the gate boundary, not a validated terminal record: `src/trading/SimulatedTradingService.cpp:576-649` and `src/trading/LiveTradingService.cpp:2039-2129`.
- Existing mode/provenance design is documented but not implemented by the canonical attribution path: `docs/design/trading-mode-data-contract.md:145-216` and `:218-260`.

## What is complete

1. The vocabulary and required shape are explicit: status, runtime mode, side, blocker, diagnostic factor, strength/return buckets, objective values, bounded metadata, and legacy adapter.
2. The pure validator is fail-closed for required identifiers, enum validity, bucket consistency, finite numbers, non-negative fees, status/side/blocker combinations, and forbidden sensitive labels.
3. The legacy aggregate report preserves existing backend units: win rate is 0–100, average loss is a positive magnitude, realized PnL is closing-leg based, and non-finite profit factor is represented by an explicit flag at the API boundary.
4. `signal_id` already exists as the primary key of `order_book_signals`, so it can remain the idempotency key for the canonical outcome relation.

## Exact gaps to close

### 1. Canonical persistence is absent

Missing additive relation, migration, or equivalent idempotent storage keyed by `signal_id`. Required persisted fields are at least:

- identity/scope: `signal_id`, `session_id`, `strategy`, `symbol`, `mode`, `runtime_window`, `timestamp_epoch_seconds`;
- terminal classification: `status`, `side`, `blocker`, `diagnostic`;
- derived inputs: `strength`, `strength_bucket`, `expected_return`, `expected_return_bucket`;
- objective: `fee_adjusted_expected_return`, `realized_pnl`, `fees`, `net_objective_impact`;
- bounded `safe_metadata` JSON/text plus a schema version and producer/version marker;
- lifecycle linkage needed for audit: `intent_id`, `trade_id`, and `exchange_order_id` where available. These linkage fields are nullable for skipped/blocked and legacy rows.

Invariant: at most one terminal outcome per `signal_id`; insert/upsert must be idempotent and must not silently replace a conflicting terminal outcome. Preserve unknown raw enum input for audit while normalizing report output to `unknown`.

### 2. Trading services do not construct or validate terminal outcomes

`SimulatedTradingService` and `LiveTradingService` currently emit `execution_analysis` JSON and trade rows, but never call `validateSignalOutcome`, `legacySkippedOutcome`, or a shared outcome builder. Integration must classify every generated, blocked, skipped, executed, and terminal-close path. The analysis snapshot must not be treated as proof of execution because live preflight gates are repeated later (`docs/reports/live-executable-intent-blocker-trace-2026-08-23.md:74`).

Required boundaries:

- construct blocked/skipped outcome immediately after the authoritative gate decision;
- construct executed only after local paper settlement or authoritative exchange fill state;
- construct terminal realized outcome only after the closing leg is authoritative;
- on validator failure, fail closed for persistence and order submission, with a bounded diagnostic log and no secret/account payload;
- paper/live-parity must never call exchange order submission and must retain explicit paper authority/mode;
- live outcomes must retain exchange order linkage when available.

### 3. Lifecycle identifiers are not propagated through trades/intents

`order_book_signals` has `signal_id`, but `individual_trades` inserts at `src/trading/SimulatedTradingService.cpp:1216-1250` and `src/trading/LiveTradingService.cpp:1521-1555` do not persist `signal_id`, `intent_id`, `exchange_order_id`, canonical mode/authority, fill kind, gross/net PnL, or blocker reason. Without these fields, a closing trade cannot be deterministically attributed to the originating signal and the report cannot distinguish paper from Coinbase execution.

### 4. API/reporting is still the legacy aggregate path

`GET /api/trading/execution-reconciliation` must gain a canonical path that:

- joins generated signals/intents to exactly one terminal outcome by `signal_id`;
- scopes by canonical mode and session, with deprecated `trade_type` compatibility mapping;
- reports missing outcomes, duplicate outcomes, unknown enum values, malformed legacy JSON, and result truncation separately;
- bounds both signal and outcome result sets;
- excludes account-management rows from strategy metrics by default;
- retains current aggregate fields and frontend names for compatibility, using additive fields rather than renaming/removing them.

Current `signal_rows_truncated` only bounds signal paging (`src/api/PredictController.cpp:1790-1842`); there is no outcome truncation or join-integrity diagnostic.

### 5. Frontend has no canonical terminal-outcome model

`frontend/lib/executionReconciliation.ts:12-168` normalizes the old aggregate response only. Add optional additive canonical diagnostics/row types, preserving current `StrategyReconciliation` fields and zero semantics. Do not expose `safe_metadata` values unless the backend has already redacted and bounded them; never display credentials, balances, tokens, order secrets, or full account snapshots.

## Compatibility and migration rules

- Preserve `SignalAttribution`, `OutcomeAttribution`, current endpoint names, legacy `trade_type` filters, and current frontend aggregate fields until canonical reporting is proven.
- Adapt legacy signal rows with no terminal record through `legacySkippedOutcome`; show them as skipped/unknown and never count them as executed.
- Keep legacy `is_closing_leg = NULL` meaningful. Do not backfill a boolean or provenance value without evidence.
- Map existing `trade_type` values according to `docs/design/trading-mode-data-contract.md:208-216`; `trade_type='live'` is Coinbase provenance only when exchange-order evidence exists.
- Malformed legacy JSON becomes skipped/unknown with a diagnostic count, not a query-fatal cast.
- Unknown producer enum values remain retained as raw values and are normalized to `unknown` in reports.
- Rollback boundary: additive schema/columns and feature-gated canonical reads only. Legacy aggregate reads remain the fallback until canonical persistence and reconciliation pass remote CI and bounded runtime evidence.

## Sensitive-field exclusions

The canonical type must remain independent of account models and exchange clients. Reject or omit credentials, API keys, passwords, tokens, private keys, balances, complete account snapshots, reserved cash, and raw authenticated exchange responses from `safe_metadata` and API serialization. Only bounded redacted labels are allowed. The existing validator checks forbidden words (`src/trading/ExecutionReconciliation.cpp:157-168`), but no production persistence/API path currently invokes that validator; this is an integration gap, not evidence of end-to-end redaction.

## Recommended implementation slices

1. Backend contract/persistence slice: shared builder plus additive/idempotent outcome relation and lifecycle columns; wire both services; preserve legacy writes and add validator/compatibility handling.
2. API/reporting slice: canonical joined query, integrity/truncation diagnostics, mode/session/account-management filters, additive JSON response fields, and frontend normalizer additions.
3. Verification slice: deterministic unit tests for every status and gate, duplicate/missing outcomes, malformed legacy JSON, unknown enums, mode mappings, paper no-submit invariant, sensitive-field rejection, exact-flat fee-negative close, and legacy aggregate compatibility. Runtime evidence must remain read-only and separate from live-account evidence.

Acceptance evidence must include exact changed paths, remote CI for the exact SHA, API contract fixtures, and a bounded read-only reconciliation response showing canonical counts plus explicit missing/duplicate/truncated diagnostics. No local build was run for this verification task, per task constraints.
