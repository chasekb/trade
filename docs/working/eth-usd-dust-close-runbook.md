# ETH-USD dust close: one-time exception runbook

Status: design only. This document is not approval to place an order. No production credentials or exchange orders may be used while implementing or reviewing this design.

Backlog: TRADE-BL-0007

## 1. Scope and non-negotiable separation

This is a single-use, ETH-USD-only exception for an already-held Coinbase dust balance. It is not a strategy trade, a general minimum-size workaround, or a change to normal liquidation policy.

The normal dust-liquidation path must remain fail-closed:

- It may sell only the validated available base quantity already held by Coinbase.
- It must reject a base quantity below the applicable product minimum/notional rather than increasing the amount.
- It must never infer a quote buy, add synthetic quantity, or call the exception path implicitly.
- It must not accept an exception approval field as a general liquidation override.
- Any symbol other than the exact string `ETH-USD`, any missing approval, or any stale/reused approval is rejected.

The implementation should use a distinct operation/action discriminator (for example `eth_usd_one_time_dust_close`) and a one-time durable consumption marker. The ordinary `liquidate-holdings` endpoint and strategy-generated orders must not acquire this behavior through shared sizing defaults.

Relevant existing surfaces inspected:

- `src/trade_bot/trading/live_components/trade_executor.py`: the current live executor dispatches Coinbase market buys with `quote_size` and sells with `base_size`; it currently lacks the approval, idempotency, terminal-fill, and reconciliation gates required by this exception.
- `src/trade_bot/core/trading_bot.py`: a second live execution surface also dispatches market buy/sell requests and records trade data; it must not inherit this exception through shared signal sizing.
- `src/trade_bot/data/coinbase_portfolio_handler.py`: authenticated account/portfolio reads expose available balances and holdings; preflight must use authoritative Coinbase values and fail closed on unavailable credentials or read errors.
- `src/trade_bot/data/data_provider.py` and `src/trade_bot/data/data_components/orderbook_handler.py`: quote/order-book data surfaces; freshness, crossed-book, and numeric validation are not an execution approval.
- Repository inspection found no existing `/api/trading/live/liquidate-holdings` route or dedicated dust-close implementation in the current Python tree. The implementation must add a separate operation rather than assume that endpoint exists.

## 2. Required preflight snapshot

Preflight is read-only and must return a machine-readable report plus a redacted evidence artifact. It must be captured immediately before approval and repeated immediately before each order. A snapshot is stale if its timestamp exceeds the configured approval freshness window or if any relevant value changes.

Required fields:

- `operation_id`, `run_id`, UTC `snapshot_at`, and code/config version.
- Exact `symbol` (`ETH-USD`) and Coinbase product metadata version/source.
- Coinbase available ETH quantity (`dust_quantity`), total ETH quantity, and any held/reserved ETH.
- Product base increment, quote increment, minimum base size, minimum quote/notional, and any product status/trading-disabled flag. Do not rely solely on the current code constant; revalidate exchange metadata.
- Best bid, best ask, computed mid, quote timestamp/age, and the source of the quote. Reject missing, zero, non-finite, crossed, or stale prices.
- Available USD, total USD, and USD held/reserved. Available USD must be authoritative Coinbase account data, not simulated/session cash.
- Account readiness/authenticated-account health, product/account permissions, and whether the account is restricted or in an error state.
- Live-order enablement as resolved by the backend runtime (currently live sessions are started through `src/trade_bot/web/web_routes/trading_routes.py` → `TradingHandlers.start_live_trading`); this must be false for dry-run and true only for the separately controlled execution phase. Do not treat construction of `LiveTradeExecutor` or presence of credentials as approval to execute.
- Existing pending/open ETH-USD orders, plus any pending order symbols that could reserve ETH or USD. Require none for ETH-USD; abort on an inconclusive order-history lookup.
- Existing one-time operation state: absent/unconsumed approval, no prior buy/sell intent in an executable state, and no active operation with the same idempotency key.
- Fee schedule or configured fee assumption, spread estimate, slippage tolerance, timeout, and maximum total cost used for this run.

A preflight is `PASS` only if every field is present, finite where numeric, internally consistent, fresh, and independently captured. Otherwise it is `ABORT_PREFLIGHT` and no order request is constructed.

## 3. Dry-run calculations (no order placement)

All calculations use decimal-safe/fixed-precision money and exchange increments. Reject overflow, negative values, NaN, infinity, and rounding that would exceed an approved cap.

Let:

- `q_dust` = authoritative available ETH quantity, rounded down to the sell base increment.
- `bid`, `ask`, `mid = (bid + ask) / 2`.
- `m_quote` = current Coinbase minimum quote/notional for an ETH-USD market order.
- `m_base` = current minimum base size, if supplied by product metadata.
- `sell_buffer` = explicit safety buffer for fees, spread, and adverse movement; it is part of the approval, never an implicit default.
- `q_target` = minimum ETH quantity that makes the final sell valid, including the selected buffer: `max(m_base, (m_quote / bid) * (1 + sell_buffer))`, then rounded up only for this explicitly approved exception.
- `q_buy = max(0, q_target - q_dust)`.
- `quote_buy` = `q_buy * ask` plus the explicitly approved buy-side slippage reserve, rounded up to the quote increment and then checked against the minimum buy quote.
- `expected_sell_value = (q_dust + expected_filled_buy_base) * bid` using the conservative sell price, not mid.
- `buy_fee_reserve` and `sell_fee_reserve` = conservative fee estimates, each included separately in the total-cost calculation.
- `spread_cost` = conservative crossing cost for buy and sell relative to mid.
- `slippage_reserve` = the approved adverse-price reserve for both legs.
- `max_total_cost` = the user-approved USD ceiling for quote funds plus fees and explicitly budgeted execution costs. It is not merely the quote amount.

The report must show: dust quantity and notional, current minimum, target quantity, proposed quote-buy amount, expected buy fill quantity, expected final sell notional, each fee reserve, spread/slippage reserve, expected net residual, and `estimated_total_cost <= max_total_cost`.

A dry-run can recommend execution only when the quote buy is positive, meets the current buy minimum, available USD covers `max_total_cost` with a separate safety margin, the projected sell meets both product minimums, and every preflight gate passes. A dry-run never changes live enablement and never submits an order.

## 4. Exact approval record

Approval is a durable, immutable record tied to the exact dry-run snapshot. Free-form text such as “close the ETH dust” is not sufficient. The approval payload must contain:

```json
{
  "approval_id": "human-generated-or-server-generated-opaque-id",
  "operation": "eth_usd_one_time_dust_close",
  "symbol": "ETH-USD",
  "quote_buy_amount_usd": "<exact fixed-precision amount>",
  "maximum_total_cost_usd": "<exact fixed-precision ceiling>",
  "slippage_tolerance_bps": "<integer>",
  "timeout_seconds": "<positive integer>",
  "abort_criteria": [
    "<exact enumerated criteria from the approved runbook/report>"
  ],
  "preflight_snapshot_id": "<id>",
  "preflight_snapshot_hash": "<hash>",
  "approved_at": "<UTC timestamp>",
  "approver_id": "<auditable user identity, not a secret>",
  "approval_expires_at": "<UTC timestamp>",
  "one_time_nonce": "<unique nonce>",
  "status": "approved"
}
```

The server must compare the approval to the execution-time preflight and reject missing, expired, stale, modified, mismatched, or already-consumed approvals. Exact comparisons are required for symbol, quote amount, maximum cost, slippage tolerance, timeout, and the complete abort-criteria set. Approval cannot increase a value computed by dry-run unless the user approves a newly generated dry-run. Persist a hash/redacted representation; do not persist credentials, API keys, signatures, or raw authorization headers.

## 5. Execution state machine

States are terminally auditable and monotonic:

`PREFLIGHT_PASS -> APPROVAL_REQUIRED -> APPROVED -> BUY_INTENT_RECORDED -> BUY_SUBMITTED -> BUY_TERMINAL_SUCCESS -> SELL_PREFLIGHT_PASS -> SELL_INTENT_RECORDED -> SELL_SUBMITTED -> SELL_TERMINAL_SUCCESS -> POST_RECONCILED`

Any violation enters one of the explicit terminal abort states: `ABORT_PREFLIGHT`, `ABORT_APPROVAL`, `ABORT_DUPLICATE`, `ABORT_BUY_REJECTED`, `ABORT_BUY_NONTERMINAL`, `ABORT_BUY_TIMEOUT`, `ABORT_SELL_PREFLIGHT`, `ABORT_SELL_REJECTED`, `ABORT_SELL_NONTERMINAL`, `ABORT_SELL_TIMEOUT`, `ABORT_COST_CAP`, `ABORT_BALANCE`, `ABORT_PRICE`, `ABORT_RECONCILIATION`, or `ABORT_UNKNOWN_STATE`.

### Buy leg

1. Re-read all preflight fields; require live enablement, no pending ETH-USD order, and sufficient authoritative USD.
2. Claim the one-time operation atomically and write a redacted buy intent before dispatch. The intent contains exact quote amount, maximum cost, limits, snapshot/approval hashes, and an idempotency key.
3. Submit a Coinbase market IOC buy using `quote_size`; use a deterministic client order ID derived from operation ID, approval ID, and leg (`buy`), with no secret material.
4. If submission outcome is ambiguous, recover by querying the client order ID. Never submit a second buy merely because the first response timed out.
5. Treat only a validated terminal `FILLED` result as success. `CANCELLED`, `EXPIRED`, `FAILED`, nonterminal, malformed, or partial/unknown outcomes abort the sell phase. A nonterminal result must not be treated as a fill.
6. Verify actual filled base, quote value, fees, and total cost. Abort if actual cost plus fees exceeds the approved maximum or the actual fill is inconsistent.

### Sell leg

1. Refresh the Coinbase account and quote after terminal buy success. Do not use the pre-buy balance as the sell quantity.
2. Calculate the sell quantity as the lower of the refreshed available ETH and the explicitly computed/capped target; round down to base increment. Never sell more than the authoritative available balance.
3. Re-check bid/ask, minimums, slippage, remaining timeout, cost/risk limits, and pending orders. If the refreshed quantity cannot meet the product minimum, abort and report the residual; do not top up again.
4. Write a separate redacted sell intent and use a separate deterministic client order ID (`sell`).
5. Submit only the capped base-size market IOC sell. Recover ambiguous responses by client order ID, never by blind resubmission.
6. Require a validated terminal `FILLED` result before declaring closeout. Any nonterminal, rejected, cancelled, expired, malformed, timed-out, price, or balance result is an abort with residual reconciliation.
7. Refresh the account again and reconcile actual ETH, USD, fees, both client IDs, and the final order statuses against the operation ledger.

Timeout applies to the whole operation and to each exchange wait. When it expires, stop issuing requests, resolve order status by client ID, and leave the operation in an abort/reconciliation state until the exchange state is known. Never cancel or resubmit an order based only on a local timeout.

## 6. Residual and rollback handling

There is no financial rollback that reverses a filled market order. “Rollback” means safe containment and reconciliation:

- Buy not accepted: no sell; mark the operation aborted and verify no order exists by client ID.
- Buy accepted but not terminal: no sell; poll only within timeout, then reconcile asynchronously by client ID.
- Buy filled but sell rejected/nonterminal: do not buy again and do not silently retry sell. Freeze this one-time operation, report the actual ETH residual and order ID, and require a new explicit operator decision for any later action.
- Sell filled with residual below minimum: mark `RESIDUAL_BELOW_MINIMUM`, report exact available quantity and valuation, and leave it for normal fail-closed handling. Never auto-raise it.
- Account/API snapshot disagreement: `ABORT_RECONCILIATION`; preserve all evidence and require an operator review.
- Any unexpected symbol, order, fill, or approval reuse: `ABORT_UNKNOWN_STATE` and disable this operation key permanently.

Closeout requires post-run evidence showing zero ETH-USD dust or a documented residual with reason, quantity, notional, account snapshot timestamp, and next safe action. The dashboard/accounting state must not claim closure from internal state alone.

## 7. Audit and evidence contract

Persist distinct redacted records for each leg and for the operation:

- `eth_usd_dust_close_preflight` (inputs, freshness, gates, report hash).
- `eth_usd_dust_close_approval` (approval fields, approver identity, expiry, hashes; no secret).
- `eth_usd_dust_close_buy_intent` and `eth_usd_dust_close_buy_result`.
- `eth_usd_dust_close_sell_intent` and `eth_usd_dust_close_sell_result`.
- `eth_usd_dust_close_abort` for every abort state.
- `eth_usd_dust_close_reconciliation` and final residual/closeout record.

Each record includes operation ID, leg, symbol, client order ID, timestamps, state transition, price/quantity/fees/cost fields, snapshot and approval hashes, and redacted error classification. Never include API keys, passphrases, JWTs, authorization headers, request signatures, or full credential-bearing payloads. Retain raw Coinbase order IDs only as identifiers, not credentials.

Evidence package for operator review: dry-run JSON, preflight snapshots before buy and sell, approval record, redacted intent/result records, exchange status/fill responses with secrets removed, final account snapshot, and a reconciliation report. Code changes require targeted tests, independent high-risk review, and exact-SHA Docker Build Validation CI before any live use; this design task itself places no orders.

## 8. Abort checklist (operator-facing)

Abort without submitting or progressing the next leg if any item is true:

- Symbol is not exactly ETH-USD, approval is absent/expired/reused, or approval values do not match.
- Preflight is stale, malformed, incomplete, or cannot be reconciled to Coinbase.
- Account is not ready, live execution is disabled, or production credentials are unavailable/invalid.
- Pending ETH-USD orders exist or order history is inconclusive.
- Bid/ask/mid is stale, crossed, non-finite, outside approved slippage, or moved beyond the approved price guard.
- Available USD/ETH is insufficient or differs from the snapshot.
- Buy quote is below current Coinbase minimum, target sell is below product minimum, or any amount rounds to zero.
- Estimated or actual total cost exceeds the exact approval ceiling.
- Buy is not terminally FILLED before the sell phase.
- Any timeout, exchange rejection, ambiguous status, malformed fill, duplicate client ID, or unexpected residual occurs.

The safe default for every unlisted condition is abort and reconcile, not retry or increase size.
