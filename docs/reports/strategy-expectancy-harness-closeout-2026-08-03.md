# Strategy Expectancy Harness Closeout

Date: 2026-08-03

## Backlog scope

Implements the first code-backed slice for TRADE-BL-0011 — Add shared strategy expectancy evaluation harness.

## What changed

- Added `include/trading/StrategyExpectancyHarness.hpp`.
- Added `src/trading/StrategyExpectancyHarness.cpp`.
- Added `src/tests/test_strategy_expectancy_harness.cpp`.
- Registered the harness source and test target in `CMakeLists.txt`.

## Harness contract

The harness evaluates fixed strategy fixtures through the existing shared strategy signal and profitability diagnostic contracts:

- `evaluateStrategySignal(...)`
- `evaluateStrategyProfitabilityDiagnostic(...)`

For each fixture it records:

- strategy name
- generated signal type and strength
- whether expected-return diagnostics were available
- directional expected edge
- fee/spread/slippage-adjusted expected return
- required edge hurdle
- diagnostic factor
- whether the intent was blocked
- whether the paper/backtest trade was filled
- realized net PnL

It then aggregates objective-aligned metrics overall and by strategy:

- fixture count
- signals generated
- trades filled
- blocked intents
- average realized win
- average realized loss
- net expectancy
- profit factor
- max drawdown
- total PnL
- negative-expectancy flag

## Strategy coverage

The default fixture set covers every indicator-family strategy handled by `evaluateStrategySignal`:

- sma
- ema
- rsi
- bollinger
- macd
- stochastic
- fibonacci
- dca
- buyandhold

The harness intentionally uses fixed deterministic price paths rather than live exchange data so future code changes can compare strategy behavior without depending on Coinbase availability.

## Regression coverage

`test_strategy_expectancy_harness` verifies:

- one output row is emitted per fixture
- all default strategies are represented
- fee-positive fixtures become fills
- fee-negative expected-return regression fixtures still generate signals but are blocked before fill
- default baseline expectancy is positive
- average win exceeds average loss in the default baseline
- profit factor is above one in the default baseline
- a high-signal-count losing configuration is flagged as negative expectancy
- the negative-expectancy flag is available overall and per strategy

This directly protects the project objective by ensuring a strategy can be flagged when it increases signal/trade count while worsening net expectancy.

## Safety notes

- The harness is pure evaluation code; it does not call Coinbase, submit orders, mutate live sessions, or change live execution gates.
- It reuses existing diagnostic factoring logic instead of introducing a separate interpretation of fees/spread/slippage.
- The new test is registered in CMake for remote container verification.

## Verification plan

Local Docker/backend build was intentionally not run per user instruction.

Allowed pre-push checks for this slice:

- `git diff --check`
- repository status inspection
- exact pushed SHA verification after commit
- GitHub Actions Docker Build Validation for the exact pushed SHA

## Remaining TRADE-BL-0011 follow-up

This closes the initial shared harness implementation, but future expansion should add historical/live-parity replay inputs once TRADE-BL-0006 live-parity paper mode exists. Until then, the checked-in deterministic fixtures provide the common strategy expectancy contract and regression guard.
