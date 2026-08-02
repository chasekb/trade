# Live vs Simulated Order-Book Signal Parity Closeout - 2026-08-02

Backlog item: `TRADE-BL-0005 | Reconcile live and simulated order-book signal execution deltas`

## Scope

This closeout audits the current checked-in live and simulated order-book signal contract after the earlier reconciliation work in `docs/reports/live-simulated-signal-execution-delta-2026-07-27.md`.

The goal is to keep live and simulated order-book diagnostics comparable before live-only execution blockers apply. It does not remove live-account safety controls, submit orders, change account authority, or claim synthetic market data equals Coinbase market data.

## Current source-of-truth contract

For order-book strategies, both producers now share the same pre-execution signal contract:

1. Raw imbalance creates a candidate `buy` or `sell` only when candidate strength reaches the activity threshold.
2. Candidate expected return is populated from ONNX inference when available; transformer-only packs use transformer expected PnL when no regressor is present.
3. Heuristic fallback expected return uses `orderbook_expected_return_scale_percent`, defaulting to the shared live/simulated fallback scale and clamped to `0.0` through `5.0` percent.
4. Generated order-book candidates pass through `evaluateOrderBookProfitabilityGate` before remaining actionable.
5. The gate writes the same diagnostic fields in both paths:
   - `ml_analysis.fee_adjusted_expected_return`
   - `ml_analysis.required_edge`
   - `ml_analysis.profitability_gate_passed`
   - `ml_analysis.profitability_gate_reason`
6. A profitability-gated candidate is downgraded to `hold`, sets `signal_generated=false`, keeps `data_status=sufficient`, and renders as `HOLD` rather than insufficient-data `WAITING`.

## Audited code paths

- Shared gate:
  - `src/trading/StrategySignal.cpp`: `evaluateOrderBookProfitabilityGate`
- Simulated order-book producer:
  - `src/trading/SimulatedTradingService.cpp`: generated candidate ML/heuristic expected return, shared gate invocation, gated-HOLD payload mutation, and diagnostic field serialization
- Live order-book producer:
  - `src/trading/LiveTradingService.cpp`: generated candidate ML/heuristic expected return, shared gate invocation, gated-HOLD payload mutation, and diagnostic field serialization
- Shared frontend widget:
  - `frontend/components/dashboard/OrderBookSignalsTable.tsx`: sufficient rows render actual `HOLD` / `BUY` / `SELL`; insufficient rows render `WAITING`; ML diagnostics render fee-adjusted and required-edge values
- Frontend regression coverage:
  - `frontend/components/dashboard/__tests__/dashboard-tables.test.tsx`: profitability-gated sufficient HOLD rows render as `HOLD`, not `WAITING`, and show fee-adjusted/required-edge diagnostics
- Backend regression coverage:
  - `src/tests/test_strategy_signal.cpp`: shared order-book gate blocks weak or fee-negative edges, blocks fee-neutral edges, treats directional sell edge correctly, and verifies the shared heuristic fallback scale can clear the default fee/spread/slippage hurdle only for strong favorable candidates

## Delta classification

| Delta area | Current classification | Current handling |
| --- | --- | --- |
| Coinbase live data versus synthetic simulated data | Intended data-source delta | Contract remains comparable by surfacing data source-specific rows with shared diagnostic field names and units. |
| Live account readiness, explicit live execution opt-in, cash/holding availability, pending orders, min notional, max positions, and exchange submission | Intended live-only execution blockers | These remain after pre-execution signal generation and are not bypassed by this item. |
| Missing ONNX artifacts/model unavailable | Intended fallback mode | Both paths label fallback with `model_version=heuristic-fallback` and use the same default/clamped expected-return scale. |
| Transformer-only model pack without regressor | Prior contract mismatch, now reconciled | Both paths use transformer expected PnL as expected return when no regressor is present. |
| Simulated candidates bypassing live profitability gate | Prior bug, now reconciled | Simulated candidates now apply the shared fee/spread/slippage gate and carry the same diagnostics as live candidates. |
| Profitability-gated HOLD versus insufficient-data WAITING | Prior UI ambiguity, now tested | Sufficient gated HOLD rows render as `HOLD`; only `data_status=insufficient` renders `WAITING`. |

## Verification performed locally

No local Docker/backend/production build was run.

Allowed local verification for this closeout:

- `git diff --check`
- report/source contract scan for the shared gate and live/simulated diagnostic field assignments
- frontend targeted Jest coverage for `dashboard-tables.test.tsx`
- frontend `npx tsc --noEmit`
- targeted ESLint for `dashboard-tables.test.tsx`
- backlog JSON validation

The backend C++ compile/test gate is intentionally deferred to GitHub Actions Docker Build Validation for the exact pushed SHA.

## Closeout criteria mapping

1. Checked-in report naming observed deltas and classifying intended versus bug:
   - This file plus `docs/reports/live-simulated-signal-execution-delta-2026-07-27.md` provide the delta matrix and current classification.
2. Same input fixture emits the same signal contract before live-only blockers:
   - Shared gate coverage in `src/tests/test_strategy_signal.cpp` exercises the common candidate gate contract used by both producers.
   - Live and simulated producer code writes the same diagnostic fields and performs the same gated-HOLD mutation before live-only execution blockers.
3. Frontend renders sufficient HOLD/gated HOLD versus insufficient-data WAITING consistently:
   - `dashboard-tables.test.tsx` covers a sufficient profitability-gated HOLD and asserts no `WAITING` label appears.
4. Exact pushed SHA verified by remote CI:
   - Pending. This item must remain open until Docker Build Validation completes successfully for the commit that adds this closeout report.

## Remaining boundaries

- This closeout does not replay live Coinbase orders or submit live orders.
- This closeout does not claim synthetic simulated fills have live-account parity; `TRADE-BL-0006` remains the dedicated live-parity simulated trading mode item.
- This closeout does not optimize strategy parameters; `TRADE-BL-0008`, `TRADE-BL-0011`, and `TRADE-BL-0016` remain the expectancy optimization/factoring work.
- This closeout does not remove widget or quote cadence caps; `TRADE-BL-0024` and `TRADE-BL-0025` remain the order-book widget limitation work.
