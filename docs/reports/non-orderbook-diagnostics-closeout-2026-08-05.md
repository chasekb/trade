# TRADE-BL-0012 — Non-order-book expected-return diagnostics

Timestamp: 2026-08-05T03:59:34Z

## Scope

This slice adds explicit strategy-neutral expected-return diagnostics for non-order-book strategies without changing live order submission authority.

Touched strategies:
- SMA
- EMA
- RSI
- Bollinger
- MACD
- Stochastic
- Fibonacci
- DCA
- Buy-and-hold

## Root cause

Order-book strategies already exposed fee/spread/slippage profitability fields (`expected_return`, `fee_adjusted_expected_return`, `required_edge`, and gate reason). Indicator-family strategies could generate buy/sell/hold rows with `signal_type`, `strength`, and `reason`, but their expected-return diagnostics were absent from the table contract. The frontend therefore could not distinguish “no alpha estimate exists for this strategy” from a real zero expected return.

## Implementation

Backend live and simulated signal rows now emit an explicit diagnostic object through `ml_analysis` for non-order-book strategies when no model-derived expected-return estimate exists:

- `ml_enabled: true`
- `expected_return: 0.0`
- `expected_return_available: false`
- `diagnostics_available: false`
- `fee_adjusted_expected_return: 0.0`
- `required_edge: fee + spread + slippage buffer`
- `profitability_gate_passed: false`
- `profitability_gate_reason: Expected-return diagnostic is unavailable`
- `diagnostic_factor: expected_return_unavailable`
- `factoring_semantics: unavailable`
- `model_version: strategy-diagnostic-unavailable`

Order-book strategies continue to use their existing directional expected-return gate. This slice adds `expected_return_available: true` for the heuristic order-book fallback contract.

The local simulated frontend fallback mirrors the same distinction so frontend tests and local-only development do not accidentally treat DCA, buy-and-hold, or indicator strategies as high-confidence alpha signals.

## Safety / live trading

This is diagnostic/reporting work. It does not:

- enable live order execution;
- bypass Coinbase client configuration checks;
- bypass duplicate pending-order prevention;
- bypass max-position or pending-entry caps;
- bypass minimum-notional checks;
- bypass cash checks;
- bypass existing ML/profitability/account-position-management gates;
- submit any live order solely because diagnostics were added.

Missing/unavailable expected-return diagnostics are now fail-safe and visible. They are not represented as high confidence, positive edge, or actionable profitability.

## Factoring semantics

- Order-book and ML-enhanced order-book expected-return diagnostics: gate live order-book executable intent through the existing fee/spread/slippage profitability gate.
- Indicator strategies listed above: `unavailable` until a real pre-trade expected-return estimator is added.
- DCA and buy-and-hold: `unavailable`, so scheduled accumulation is not misrepresented as alpha or high-confidence expected-return forecasting.
- Hold signals: report-only.

## Verification plan

Allowed local checks, no local Docker/backend build:

- `npx jest lib/localSimulatedFallbackSignals.test.ts components/dashboard/__tests__/dashboard-tables.test.tsx --runInBand`
- `npx eslint lib/localSimulatedFallbackSignals.test.ts components/dashboard/OrderBookSignalsTable.tsx components/dashboard/__tests__/dashboard-tables.test.tsx types/trading.ts`
- `npx tsc --noEmit`
- `git diff --check`

Remote verification required after push:

- GitHub Actions Docker Build Validation for the exact pushed SHA.
- The remote backend image build runs `strategy_signal` through the Dockerfile.cpp `ctest -R` filter.

## Notes

A broader targeted ESLint command including `frontend/lib/api.ts` still fails on pre-existing `@typescript-eslint/no-explicit-any` debt in that file. This slice does not add new `any` or eslint-disable lines to `api.ts`; the file remains covered by TypeScript and the local fallback Jest tests above.
