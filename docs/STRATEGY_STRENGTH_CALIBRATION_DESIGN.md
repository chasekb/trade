# Outcome-Calibrated Strategy Strength Integration Design

Status: design only; no calibration values are approved.
Related backlog: TRADE-BL-0013.

## Purpose and current boundary

The current indicator evaluator returns `buy`, `sell`, or `hold`, a technical-distance strength in `[0, 1]`, and a reason. `sma`, `ema`, `rsi`, `bollinger`, `macd`, `stochastic`, and `fibonacci` are handled in `src/trading/StrategySignal.cpp:148-299`. `dca` and `buyandhold` are accumulation/baseline strategies and should not be silently converted into calibrated signal strategies.

The existing strategy-neutral profitability diagnostic is declared in `include/trading/StrategySignal.hpp:63-103` and implemented in `src/trading/StrategySignal.cpp:344-399`. It already applies directional expected-return semantics and subtracts round-trip fees, spread, and slippage. It is currently exercised by `StrategyExpectancyHarness`, but the normal non-order-book live and simulated signal paths do not use it as an entry/exit decision.

Live and simulated non-order-book generation both call the shared evaluator (`src/trading/LiveTradingService.cpp:1557-1568` and `src/trading/SimulatedTradingService.cpp:1118-1129`). The design must therefore keep the signal calculation shared and must not create separate live/sim calibration behavior.

## Recommended smallest API change

Keep the existing public function source-compatible:

```cpp
StrategySignalOutcome evaluateStrategySignal(
    const std::string&, const std::deque<double>&,
    const StrategyParams&, bool, long long);
```

Add optional calibration data and a post-signal decision layer rather than adding required arguments to existing callers:

```cpp
struct StrengthCalibrationBin {
  double raw_strength_min = 0.0;       // inclusive
  double raw_strength_max = 1.0;       // exclusive except final bin
  double calibrated_strength = 0.0;    // fitted value, not a guessed default
  std::size_t evidence_count = 0;
};

struct StrengthCalibrationRule {
  std::string strategy;
  std::string regime = "unknown";
  double holding_period_min = 0.0;
  double holding_period_max = 0.0;
  double fee_fraction_min = 0.0;
  double fee_fraction_max = 0.0;
  std::size_t minimum_evidence = 0;
  bool validated_out_of_sample = false;
  std::vector<StrengthCalibrationBin> bins;
};

struct StrengthCalibrationContext {
  std::string regime = "unknown";
  double expected_holding_period = 0.0;
  double round_trip_fee_fraction = 0.0;
};

struct StrategyStrengthCalibration {
  bool enabled = false;
  std::vector<StrengthCalibrationRule> rules;
};

struct StrategySignalEvaluation {
  StrategySignalOutcome raw_signal;
  StrategySignalOutcome effective_signal;
  StrategyProfitabilityDiagnostic profitability;
  bool calibration_applied = false;
  std::string calibration_status = "disabled";
};

StrategySignalOutcome applyStrategyStrengthCalibration(
    const StrategySignalOutcome&, const StrategyStrengthCalibration&,
    const StrengthCalibrationContext&);

StrategySignalEvaluation evaluateStrategySignalWithDiagnostics(
    const std::string&, const std::deque<double>&,
    const StrategyParams&, const StrategyStrengthCalibration&,
    const StrengthCalibrationContext&, const StrategyProfitabilityInput&,
    bool, long long);
```

The exact field names can be adjusted to local style, but the separation is important:

1. `evaluateStrategySignal` remains the raw technical signal and preserves every existing caller and default.
2. `applyStrategyStrengthCalibration` is a pure, deterministic mapping from raw strength plus a fully specified context. It does not infer regime, fees, holding period, or evidence.
3. `evaluateStrategySignalWithDiagnostics` is the integration seam for new live/sim paths. It computes raw signal, maps strength only when an eligible rule exists, then evaluates profitability using the effective strength and the same directional/fee-adjusted diagnostic contract.
4. Existing order-book generation remains on `evaluateOrderBookProfitabilityGate`; this design must not replace or weaken that gate.

`StrategyParams` may carry a default-disabled `StrategyStrengthCalibration` only if configuration plumbing requires it. Prefer a separate calibration object at the service/session boundary so indicator tuning parameters and fitted outcome artifacts cannot be confused. A missing object must mean disabled/identity behavior.

## Mapping and evidence contract

A calibration rule is eligible only when all of these match:

- strategy name matches exactly;
- regime matches exactly; `unknown` is a real fallback key, not a wildcard;
- expected holding period is inside the rule's interval;
- round-trip fee fraction is inside the rule's fee interval;
- every selected bin has `evidence_count >= minimum_evidence`;
- the rule is marked `validated_out_of_sample`.

The rule should be selected deterministically. Prefer the most-specific exact rule (regime, holding-period interval, and fee interval), then the explicit `unknown` regime rule. If multiple rules remain equally specific, reject the mapping as ambiguous and use the raw strength. Do not average rules at runtime.

The fitted mapping is a monotonicity claim to be proven by the calibration report, not an assumption of the implementation. Each bucket must retain the outcome-analysis provenance needed to show realized expectancy, average win, average loss, drawdown, symbol/regime coverage, holding period, and fee treatment. Calibration values must come from the outcome analysis; this design deliberately provides no values.

A mapping must not turn a fee-negative signal into an actionable one. After effective strength is computed, pass it into `evaluateStrategyProfitabilityDiagnostic`. A diagnostic that is unavailable, weak, unsupported, or `negative_fee_adjusted_edge` remains non-actionable. If evidence shows a high-strength bucket has negative fee-adjusted expectancy or worse average loss, that rule is rejected/held out rather than capped with an invented value.

`dca`, `buyandhold`, and order-book strategies remain outside this mapping table unless a separate evidence-backed design explicitly extends them. In particular, order-book strength and its minimum threshold remain governed by the existing order-book branch and `evaluateOrderBookProfitabilityGate`.

## Fallback and fail-closed behavior

Backward-default behavior is identity mapping:

- `enabled == false`, no matching rule, insufficient evidence, invalid OOS flag, or ambiguous matching rules leaves `effective_signal` equal to the raw signal;
- status must identify why (`disabled`, `no_match`, `insufficient_evidence`, `not_validated`, `ambiguous`, or `invalid_rule`);
- missing expected-return diagnostics remain unavailable and are never treated as positive, zero-risk, or high confidence;
- a hold or warming-up signal remains hold with strength `0.0`, regardless of any calibration table;
- a calibration failure must not promote hold to buy/sell and must not bypass existing live-account, minimum-notional, pending-order, or explicit-live-order gates.

For normal indicator execution, the rollout should initially use the new evaluation result only to expose calibrated strength and diagnostics. Changing entry, sizing, or exit behavior requires separate evidence and an explicit caller decision (`gate`, `size`, `exit`, or `report`) under `docs/STRATEGY_OBJECTIVE.md:41-58`. If the caller requires expected edge and it is unavailable, it must fail closed; if the diagnostic is report-only, it must remain visible without changing execution.

## Numerical boundaries and validation

All runtime inputs and fitted values must be validated before use:

- reject non-finite raw strength, calibrated strength, context fee, or holding period; retain the raw signal and mark `invalid_rule`/`invalid_context`;
- clamp valid raw and calibrated strength to `[0, 1]` only at the API boundary, while recording malformed fitted values rather than silently hiding them;
- use half-open bins `[min, max)` except the final bin, whose upper boundary is inclusive;
- require `min <= max`, finite bounds, and non-overlapping bins;
- use `>=` for `minimum_evidence` and `validated_out_of_sample == true`;
- preserve existing technical threshold semantics (`<=` oversold/lower boundaries and `>=` overbought/upper boundaries);
- treat an exactly zero fee-adjusted expected return as non-actionable, matching `StrategySignal.cpp:384-393`;
- preserve signed directional expected return: buys require positive edge and sells require negative model return before costs.

A calibrated strength must never be NaN, infinity, negative, or above one in serialized payloads. The effective signal reason should retain the raw reason and append a stable calibration status; diagnostic factor and reason remain separately machine-readable.

## Data flow and implementation locations

1. `include/trading/StrategySignal.hpp`: add the calibration structs, result type, and pure mapping/evaluation declarations. Keep the old evaluator declaration unchanged.
2. `src/trading/StrategySignal.cpp`: add finite/boundary validation, deterministic rule selection, identity fallback, and the diagnostic composition. Reuse `clamp01`; do not duplicate fee arithmetic from `evaluateStrategyProfitabilityDiagnostic`.
3. `src/trading/LiveTradingService.cpp` and `src/trading/SimulatedTradingService.cpp`: replace only the non-order-book integration seam after calibration evidence exists. Both services must consume the same `effective_signal` and diagnostic result. Preserve the existing order-book branch and all live-only safety checks.
4. `src/trading/StrategyExpectancyHarness.cpp` / `include/trading/StrategyExpectancyHarness.hpp`: add context/rule fields to fixtures and report raw versus effective strength, calibration status, regime, holding period, fee bucket, and diagnostic factor. Keep realized PnL net of fees/spread/slippage and keep blocked intents distinct from holds.
5. `src/tests/test_strategy_signal.cpp`: unit-test pure mapping and diagnostic composition. Cover disabled identity, exact lower/upper boundaries, final-bin inclusion, non-overlap/invalid rules, regime/holding-period/fee matching, insufficient evidence, not-validated rules, hold/warm-up preservation, buy/sell direction, and zero-net-edge blocking.
6. `src/tests/test_strategy_expectancy_harness.cpp`: add deterministic known-good versus known-bad strength ranking fixtures, one rejected/held rule, and a fee-negative high-strength fixture. Assert that blocked intents do not contribute to fills or expectancy and that raw behavior remains unchanged when calibration is absent.
7. `CMakeLists.txt:151-164`: no new target is required if the implementation stays in `StrategySignal.cpp`; retain both `test_strategy_signal` and `test_strategy_expectancy_harness` coverage. If calibration data parsing becomes a separate source, add it to the backend source list and the focused test target together.

## Frontend and documentation contract

No frontend threshold/default should change in this design because no calibration evidence exists and `frontend/hooks/useTrading.ts:798-830` currently exposes technical indicator parameters, while the `min_orderbook_signal_strength` controls at `:845-866` are order-book-specific. The existing frontend signal types already carry `signal_strength`, diagnostic fields, and `strength_composition` (`frontend/types/trading.ts:51, 97-132`), so a first implementation can remain additive.

If a later evidence-backed rollout makes calibration or an indicator minimum user-configurable, update all of the following together:

- `frontend/hooks/useTrading.ts` parameter metadata and presets;
- `frontend/components/dashboard/StrategyConfigForm.tsx` labels/help text if the control is user-facing;
- `frontend/types/trading.ts` for calibration status/context fields;
- `frontend/lib/api.ts` normalization and payload forwarding;
- `docs/API_REFERENCE.md` and `docs/FRONTEND_ARCHITECTURE.md` for the request/response contract;
- adjacent frontend tests for default preservation, explicit zero values, and backward payloads.

Do not relabel `min_orderbook_signal_strength` as an indicator calibration threshold. A calibrated indicator strength and an order-book profitability threshold are different contracts.

## Required evidence before implementation values or behavior are approved

The calibration report must provide, per strategy and candidate rule:

- bucket definition and sample count;
- symbol and regime coverage;
- holding-period definition;
- fee/spread/slippage treatment;
- realized expectancy, average win, average loss, profit factor, and drawdown;
- out-of-sample/walk-forward result and monotonicity assessment;
- comparison against raw strength and against raw strength plus profitability diagnostic;
- rejection/hold rationale where evidence is insufficient or fee-adjusted high-strength outcomes are negative;
- objective-impact expectations and rollback condition from `docs/STRATEGY_OBJECTIVE.md`.

Until that report exists, the only safe implementation is the disabled/identity path and diagnostic reporting/fallback behavior. No calibration constants, thresholds, regime filters, holding periods, or frontend defaults should be invented in code or documentation.
