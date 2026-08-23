# Evidence-backed strategy-strength implementation contract

Status: approved handoff for the next implementation worker. No new calibration constants are approved.
Date: 2026-08-22
Scope: `sma`, `ema`, `rsi`, `bollinger`, `macd`, `stochastic`, and `fibonacci`, plus regime and profitability/expected-return composition.

## Decision

The checkout contains indicator signal code, deterministic expectancy fixtures, and fee-aware diagnostic plumbing, but no persisted historical replay, live-parity outcome set, repeated strength buckets, symbol/regime-labelled outcomes, holding-period labels, or fee-bearing trade ledger that can support a fitted mapping. The checked-in fixtures are regression inputs, not market evidence. Therefore:

- preserve the existing signal formulas and source-compatible API;
- keep emitted strength finite and in `[0, 1]`, treating it as technical-distance ranking only, never as calibrated probability or expected return;
- do not add numeric calibration values, threshold changes, regime filters, or joint indicator mappings;
- preserve the existing live/simulated shared evaluator and legacy behavior until outcome evidence is produced;
- keep missing expected-return diagnostics explicit and fail-safe;
- retain the existing fee/spread/slippage gate semantics; a green fixture or green CI is not calibration evidence.

The only evidence-backed behavior available for extension is the existing generic profitability diagnostic and order-book gate. It is a cost-safety boundary, not evidence that any indicator strength predicts returns.

## Current formulas to preserve

`evaluateStrategySignal` in `src/trading/StrategySignal.cpp` currently uses:

| Strategy | Existing raw mapping | Bounds/order requirement |
| --- | --- | --- |
| SMA | `gap = SMA(short) - SMA(long)`; `strength = clamp01(0.3 + abs(gap)/price * 200)` | Positive gap = buy, negative = sell; greater normalized gap must not produce lower strength. |
| EMA | Same crossover mapping using EMA values | Same as SMA; do not assume faster EMA is more predictive. |
| RSI | Buy at/below oversold; sell at/above overbought; threshold distance plus `0.3`, clamped | Preserve inclusive `<=`/`>=` thresholds. Larger directional distance must not lower strength. |
| Bollinger | `z = (price - mean) / stddev`; signal outside configured `±bb_std_dev`; `abs(z)/3`, clamped | Preserve band boundary semantics. Zero volatility remains hold. |
| MACD | EMA fast minus EMA slow versus signal-line EMA; crossover strength from normalized gap | Preserve crossover direction and deterministic tie => hold/zero strength. |
| Stochastic | Average `%D` over `stoch_d`; oversold/overbought threshold-distance plus `0.3`, clamped | Preserve inclusive thresholds and deterministic neutral/flat behavior. |
| Fibonacci | Lookback high/low; configured retracement proximity within `3%` of range; strength `0.3 + level * 0.7`, clamped | Preserve configured level ordering and first matching level behavior. Level ordinal is not proven expectancy. |

`windowSize` rounds inputs, enforces a minimum window, and the evaluator returns hold with a `warming up: insufficient price history` reason when required history is absent. Do not turn insufficient data into a weak or calibrated signal. Non-finite or invalid future calibration inputs must preserve the raw/legacy signal or fail closed; they must never promote hold.

## Profitability and expected-return composition

For a known non-hold side, the existing diagnostic contract is:

```text
required_edge = max(0, round_trip_fee_fraction)
              + max(0, spread_fraction)
              + max(0, slippage_buffer_fraction)

directional_edge = buy  ? expected_return_fraction
                   : sell ? -expected_return_fraction
                   : 0
fee_adjusted_edge = directional_edge - required_edge
```

A diagnostic is actionable only when:

- side is exactly `buy` or `sell`;
- strength is at least the caller's minimum;
- expected return is explicitly available and finite;
- `fee_adjusted_edge > 0` (exactly zero fails).

`hold` is non-actionable, not a negative trade. Missing/unavailable, non-finite, unsupported-side, or unit-ambiguous expected return is `expected_return_unavailable`, not numeric zero, confidence, or positive edge. A negative fee-adjusted edge is a valid, explicit blocker (`negative_fee_adjusted_edge`), not missing data. A future calibrated strength may not override this result or promote a fee-negative signal.

The existing `evaluateOrderBookProfitabilityGate` remains the order-book execution contract. Do not replace it with an indicator mapping. Non-order-book indicator paths currently lack a trustworthy expected-return estimator; they must remain diagnostics-unavailable for any path that requires positive expected edge.

## Regime and joint mappings

No approved regime filter or joint profitability/expected-return mapping exists in the available evidence. Do not infer regimes from the indicator itself, introduce trend/volatility/range defaults, combine indicators, or fit coefficients from the deterministic fixtures. `dca` and `buyandhold` remain accumulation/baseline strategies, not candidates for indicator calibration; order-book strategies remain on their dedicated branch.

A later rule may be considered only with a persisted, look-ahead-free outcome dataset containing at least strategy, symbol, side, timestamp, raw feature/distance, emitted strength, expected-return availability and edge fields, fill/blocker status, holding period, gross PnL, fees, spread, slippage, net PnL, and regime label. It must be evaluated chronologically with train/validation/test or walk-forward splits, minimum support per bucket, and confidence intervals. Required comparisons are raw strength, raw strength plus diagnostics, and the combined candidate after costs. Reject or defer a rule when high-strength fee-adjusted expectancy is negative, absolute average loss is worse than incumbent, drawdown is materially worse, monotonic ordering is unstable, or evidence is insufficient in any required fold.

## Safe fallback and implementation boundary

Until that evidence exists, implementation changes are limited to additive reporting or testable identity behavior:

- disabled/no rule/no match/insufficient evidence/not validated/ambiguous/invalid rule => preserve raw signal and identify the status;
- hold and warm-up always remain hold with strength `0.0`;
- valid strength values serialize in `[0, 1]`; malformed fitted values are rejected rather than silently treated as evidence;
- bins, if introduced only as an evidence-driven future interface, use `[min,max)` except the final inclusive upper bound, require finite non-overlapping bounds, and require `evidence_count >= minimum_evidence` plus explicit out-of-sample validation;
- deterministic exact matching must include strategy, regime, holding-period interval, and fee interval; ambiguous matches fall back to raw behavior rather than averaging rules;
- both live and simulated services must consume the same result; preserve live account, spot-only, minimum-notional, pending-order, cash, and explicit-live-order gates;
- no frontend defaults or user-facing thresholds change in this evidence-deferred slice.

## Acceptance evidence for a future mapping

Before changing `StrategySignal.cpp/.hpp`, defaults, or execution behavior, the next worker must provide per strategy/candidate: formula version and parameters, bucket definitions/counts, symbol/regime/holding-period/cost coverage, fee-adjusted expectancy, average win, absolute average loss, profit factor, drawdown, blocked intents, walk-forward/OOS monotonicity, comparison to incumbent, and rejection rationale for held-out candidates. The evidence must be reproducible and must distinguish synthetic fixtures from live-parity or historical outcomes.

Relevant current source and baseline references: `include/trading/StrategySignal.hpp`, `src/trading/StrategySignal.cpp`, `src/tests/test_strategy_signal.cpp`, `include/trading/StrategyExpectancyHarness.hpp`, `src/trading/StrategyExpectancyHarness.cpp`, `docs/STRATEGY_OBJECTIVE.md`, `docs/reports/trade-strategy-objective-review-2026-08-01.md`, and `docs/reports/trade-backlog-current-closeout-2026-08-08.md`.
