# Live order-book execution attribution closeout — 2026-08-04

## Backlog scope

Implements the first code-backed slice for `TRADE-BL-0014 — Attribute execution blockers and outcomes by strategy` and directly supports `TRADE-BL-0027 — Investigate why live order-book universe strategy has no positive-PnL trades`.

The change makes the Live Trading tab explain why a live order-book signal did or did not become an executable Coinbase order intent before any order submission. It is instrumentation and reporting only; it does not loosen live execution gates or submit additional orders.

## Objective alignment

The project objective is risk-adjusted live expectancy, not raw signal count. This change exposes the evidence needed to distinguish:

- weak/no generated signals;
- negative or insufficient fee-adjusted expected edge;
- ML confidence gates;
- Coinbase spot-only sell/short blockers;
- existing-position and pending-order suppression;
- max-position caps;
- position sizing or minimum-notional blockers;
- insufficient cash;
- explicit `live_order_execution` disabled state;
- genuinely executable order intents.

That makes the no-positive-PnL investigation measurable by average win, average loss, expectancy, profit factor, drawdown, fees/spread/slippage drag, generated signals, blocked intents, submitted orders, and fills rather than by widget throughput alone.

## Implementation

Backend:

- `include/trading/LiveTradingService.hpp`
  - Adds `buildEntryExecutionAnalysisLocked(...)` as a private helper.
- `src/trading/LiveTradingService.cpp`
  - Adds stable bucket/counter helpers for signal strength, expected return, and blocker counts.
  - Annotates each latest no-position live signal with `payload.execution_analysis` before persistence.
  - Classifies entry blockers without changing safety gates:
    - `no_signal`
    - `profitability_gate`
    - `ml_confidence_gate`
    - `account_position_management_disabled`
    - `existing_position`
    - `pending_order`
    - `max_positions`
    - `nonpositive_position_size_or_price`
    - `below_minimum_notional`
    - `spot_cannot_open_short`
    - `insufficient_cash`
    - `live_execution_disabled`
    - `would_submit_order`
  - Adds aggregate diagnostics to `order_book_signal_diagnostics`:
    - `executable_order_intent_count`
    - `execution_blocker_counts`
    - `execution_strength_bucket_counts`
    - `execution_expected_return_bucket_counts`

Frontend:

- `frontend/types/trading.ts`
  - Adds typed `execution_analysis` on order-book signals.
  - Adds typed execution-attribution diagnostic count maps.
- `frontend/components/dashboard/OrderBookSignalsTable.tsx`
  - Displays blocker, strength-bucket, and expected-return-bucket summaries in the live order-book coverage panel.
  - Includes per-row execution analysis in the Details dialog.
- `frontend/components/dashboard/__tests__/dashboard-tables.test.tsx`
  - Covers visible execution blocker summaries and per-row details.

## Live-trading safety

Preserved:

- No live orders unless `live_order_execution` is explicitly enabled.
- Coinbase client must be configured and ready.
- Duplicate pending-order prevention remains in force.
- Existing-position suppression remains in force.
- Max managed-position and pending-entry caps remain in force.
- Coinbase minimum-notional checks remain in force.
- Cash checks remain in force.
- Coinbase spot accounts still cannot open synthetic shorts.
- Account-position-management authority remains unchanged.

The new analysis is computed before order submission and recorded as response/persistence metadata. It does not create extra `OrderIntent`s and does not bypass `openPositionLocked(...)`.

## Verification plan

Local full backend builds were intentionally skipped per user instruction. Allowed local checks before commit:

- `git diff --check`
- frontend targeted Jest for the dashboard table test
- `npx tsc --noEmit`
- independent high-risk trading review

Required closeout gate after push:

- exact pushed SHA must pass GitHub Actions Docker Build Validation.
- Close `TRADE-BL-0014` only after the exact-SHA run succeeds and evidence is recorded in the backlog.

## Expected follow-up

`TRADE-BL-0027` remains open after this slice. It should use the new execution-attribution fields to capture a runtime window and determine whether the no-positive-PnL observation is caused by blocker mix, spot-only sell pressure, expected-return calibration, live fills/slippage, accounting, or a legitimate market outcome.
