# Cross-Strategy Diagnostics Contract

Status: proposed contract documenting current behavior and the next implementation boundary.

This document is self-contained. It is the normative reference for strategy diagnostics, profitability factoring, and the evidence required before a diagnostic may influence live execution. Current behavior is explicitly labeled; proposed behavior does not imply that an unimplemented factor is already active.

## 1. Objective and scope

The project objective is risk-adjusted expectancy in live trading: increase average realized win and minimize average realized loss after fees, spread, slippage, and live execution blockers. Signal count and trade count are supporting measures only. A change is not an optimization if it increases activity while worsening net expectancy, profit factor, or drawdown.

The contract covers every selectable strategy in `frontend/components/dashboard/StrategySelector.tsx` and every shared live/simulated decision path:

- `ml_enhanced_orderbook`
- `orderbook`
- `sma`
- `ema`
- `rsi`
- `bollinger`
- `macd`
- `stochastic`
- `fibonacci`
- `dca`
- `buyandhold`
- `unknown` (invalid or unsupported input; never actionable)

The shared indicator evaluator is `evaluateStrategySignal` in `include/trading/StrategySignal.hpp` / `src/trading/StrategySignal.cpp`. Live and simulated services call it for non-order-book strategies. Order-book strategies have service-specific construction but share `evaluateOrderBookProfitabilityGate`. The strategy-neutral diagnostic helper is `evaluateStrategyProfitabilityDiagnostic`.

## 2. Classification vocabulary

Every strategy/diagnostic combination has one primary classification:

- **actively factored** — the diagnostic currently participates in a decision path. The exact operation is identified as `gate`, `size`, or `exit`.
- **report-only** — currently emitted or computed for observability, harness output, UI, or post-trade analysis, but it cannot authorize, size, or close an order.
- **unavailable** — no supported value exists for this strategy/path. It must not be treated as zero risk, positive edge, high confidence, or permission to trade. A path requiring expected edge fails closed.

The existing `factoring_semantics` field uses the narrower values `gate`, `size`, `exit`, `report`, and `unavailable`; retain those wire values. The three classifications above are the review-level grouping of those values.

## 3. Diagnostic semantics

### 3.1 Units and signs

| Diagnostic | Unit and valid bounds | Buy/sell direction | Current default/unavailable behavior |
|---|---|---|---|
| `signal_type` | enum `buy`, `sell`, `hold` | `buy` opens/adds long exposure; `sell` closes spot exposure in live execution; simulated sell entries may be synthetic and are not live-parity evidence; `hold` has no intent | Any other value is unsupported and non-actionable. `unknown` returns `hold` with an explanatory reason. |
| `signal_strength` | dimensionless fraction, `[0,1]` | higher means stronger technical/order-book signal, not higher profitability | Shared evaluator returns `[0,1]`; invalid/non-finite values must be rejected at API boundaries. Order-book gate compares it with `min_signal_strength`. |
| `expected_return` / `expected_return_fraction` | decimal return fraction, not percent (for example `0.02` = 2%); finite and bounded by the configured estimator risk limit, with a hard safety bound `[-1,1]` | raw model estimate is positive for a favorable buy and negative for a favorable sell; normalized directional edge is `expected_return_fraction` for buy and `-expected_return_fraction` for sell | `expected_return_available=false` means unavailable, not zero. Current non-order-book rows serialize `expected_return=0.0` together with the availability flag and a fail-safe reason. |
| `fee_adjusted_expected_return` | decimal return fraction after costs | positive means favorable in the signal direction for either side | `directional_expected_edge - required_edge`; non-positive is blocked by the profitability gate. |
| `required_edge` | decimal return fraction hurdle | direction-neutral cost hurdle | `max(0, round_trip_fee) + max(0, spread) + max(0, slippage_buffer)`; invalid or negative cost inputs must not reduce the hurdle. |
| `spread` / `spread_fraction` | decimal bid/ask spread fraction; `ask - bid` divided by the positive reference/mid price | always a cost, never a directional alpha | Missing spread is unavailable for a path requiring live profitability. The current helper clamps negative values to zero; the proposed API must reject malformed negative/non-finite values before helper invocation. |
| `round_trip_fee_fraction` | decimal fraction for entry plus exit fees | always a cost | Defaults are path-specific today (`0.015` in `StrategySignal`, `0.0016` in minimum trade sizing). This conflict must be removed by a shared cost policy; no caller may silently rely on a different default. |
| `slippage_buffer_fraction` | decimal fraction buffer for expected execution slippage | always a cost | Current order-book and diagnostic helpers add it to the hurdle. Missing required live slippage is fail-closed. |
| `win_probability` / `confidence` | dimensionless probability/confidence, `[0,1]` | not directional by itself | Reported by ML/order-book paths and used by the existing size multiplier when supplied; unavailable values must not be substituted with a favorable value. |
| `forecast_horizon` | nullable integer seconds; when present, inclusive `[1,31,536,000]` (one second to 365 days) | no direction | Null means no forecast horizon was supplied and is report-only; zero, negative, fractional, non-integer, or out-of-range values are invalid and unavailable. |
| `prediction_timestamp` | RFC 3339/ISO-8601 UTC timestamp with an explicit timezone and parseable seconds | no direction | Missing or unparsable timestamps make a live estimate stale/unavailable; historical reports may retain the row with an attribution-incomplete marker. |
| `model_version` | non-empty UTF-8 identifier, maximum 128 bytes; no control characters | no direction | Missing version is reportable for legacy rows but invalid for a live model-derived gate. |
| realized PnL | USD, net of fees/spread/slippage for the measured fill | positive win, negative loss, zero excluded from average-win/loss denominators | Harness records `realized_pnl`; `max_drawdown` is USD. |
| expectancy / average win / average loss | USD per filled trade; average loss is reported as a positive magnitude | no signal-side sign; net expectancy is signed USD | Harness computes these from filled rows only. |
| profit factor | dimensionless gross wins / absolute gross losses | no direction | Zero-loss result is positive infinity when there are wins; no fills yields the neutral default `0`. |

All fractions must be finite. Percentages in API/UI adapters must be explicitly converted at the boundary; the backend contract above is decimal fraction for cost and return fields. The existing `OrderBookSignal` frontend type receives these numeric values as `number` and must preserve availability flags.

Machine-readable reasons must use a fixed lowercase `gate_reason` enum, with optional human detail in `gate_reason_detail`. The initial enum is `hold`, `weak_strength`, `expected_return_unavailable`, `negative_fee_adjusted_edge`, `unsupported_signal`, `invalid_input`, `stale_estimate`, `execution_blocked`, and `passed`. Existing `profitability_gate_reason` remains the compatibility string; new code must populate the enum without parsing prose. Unknown enum values are treated as `invalid_input` and fail closed. `forecast_horizon` is optional only for reporting; a live gate requires a present, integer, in-range horizon and rejects an estimate whose timestamp is older than that horizon or the configured quote/model freshness window.

### 3.2 Decision meanings

- **Gate:** allows or blocks an intent. A positive directional edge must strictly exceed the fee/spread/slippage hurdle; equality fails.
- **Size:** scales a permitted order but never raises the configured dollar ceiling. `calculate_position_size_usd` caps output at `base_usd`; `derive_position_size_multiplier` currently uses signal strength, probability, confidence, expected return, spread, volatility, live performance, and cohort performance.
- **Exit:** participates in close/add/hold behavior. Current live management closes an existing position on an opposite signal or age-out; no generic expected-return diagnostic is currently wired into indicator exits.
- **Report:** emitted for UI, execution attribution, or harness analysis only.
- **Unavailable:** blocks any entry path whose policy requires a verified expected edge; it may remain visible as a diagnostic row.

## 4. Strategy × diagnostic matrix

The matrix describes current behavior. “Active” means the indicated factor is actually in the live/simulated path today; “proposed” is deliberately not counted as active.

| Strategy | Signal generation | Expected return / directional edge | Fee-adjusted edge and profitability gate | Position sizing | Exit/add decisions | Realized expectancy diagnostics |
|---|---|---|---|---|---|---|
| `ml_enhanced_orderbook` | **actively factored** for executable order-book intent; strength and direction are inputs | **actively factored** when ML estimate is available; heuristic fallback is available and explicitly marked | **actively factored** (`gate`) in live and simulated order-book branches via `evaluateOrderBookProfitabilityGate` | **actively factored** only where the service supplies sizing inputs; ceiling remains authoritative | **report-only** for the generic diagnostic; live opposite-signal/age-out management remains the exit authority | **report-only**, including blocked intents, fills, PnL, and model metadata |
| `orderbook` | **actively factored** for executable order-book intent | **actively factored** through heuristic expected return; calibration evidence remains required | **actively factored** (`gate`) with directional sign and cost hurdle | **actively factored** when sizing inputs are available; never increases configured maximum | **report-only** for profitability; existing position-management exits remain authoritative | **report-only** |
| `sma` | **actively factored** technically by shared evaluator; strength is normalized MA gap | **unavailable** in the current service signal path unless a caller supplies an external estimate | **unavailable** for a required profitability gate; the neutral helper can classify a supplied estimate, but it is not wired to authorize these entries | **actively factored** by generic size policy only when callers provide inputs; not proven to be a strategy-specific profitability factor | **report-only** for expected-return diagnostics; technical/opposite signal and service rules remain current authority | **report-only** via harness/backtest/reporting |
| `ema` | Same as `sma`: **actively factored** technical signal | **unavailable** currently | **unavailable** currently; supplied estimates are diagnostic only until wired and calibrated | **actively factored** generic policy when inputs exist; no proven EMA-specific edge factor | **report-only** for profitability | **report-only** |
| `rsi` | **actively factored** by threshold distance | **unavailable** currently | **unavailable** currently | **actively factored** generic policy when inputs exist, not RSI profitability | **report-only** for profitability | **report-only** |
| `bollinger` | **actively factored** by band z-score | **unavailable** currently | **unavailable** currently | **actively factored** generic policy when inputs exist, not Bollinger profitability | **report-only** for profitability | **report-only** |
| `macd` | **actively factored** by line/signal crossover | **unavailable** currently | **unavailable** currently | **actively factored** generic policy when inputs exist, not MACD profitability | **report-only** for profitability | **report-only** |
| `stochastic` | **actively factored** by `%D` threshold distance | **unavailable** currently | **unavailable** currently | **actively factored** generic policy when inputs exist, not stochastic profitability | **report-only** for profitability | **report-only** |
| `fibonacci` | **actively factored** by proximity to configured levels | **unavailable** currently | **unavailable** currently | **actively factored** generic policy when inputs exist, not Fibonacci profitability | **report-only** for profitability | **report-only** |
| `dca` | **actively factored** as scheduled buy cadence; no sell signal intent | **unavailable by design** for alpha forecasting | **unavailable** for alpha gate; accumulation cadence is intentionally not represented as profitability approval | **actively factored** by risk/cash/notional limits; generic expected-edge sizing must not claim alpha | **actively factored** for scheduled adds only; live spot path is buy-only | **report-only** as allocation-strategy performance versus benchmarks |
| `buyandhold` | **actively factored** as one initial buy then hold | **unavailable by design** for alpha forecasting | **unavailable** by design; baseline must not be mislabeled a profitable signal | **actively factored** by allocation/risk limits | **report-only** for expected-return exits; hold is the strategy behavior | **report-only** as a baseline benchmark |
| `unknown` | **unavailable**; returns hold and reason | **unavailable** | **unavailable** and must never pass | **unavailable**; zero allocation | **unavailable** | **report-only** error/coverage attribution |

Important distinction: the technical signal itself is an active decision input for indicator strategies, but the profitability diagnostic is unavailable. Until an estimator is added and calibrated, no indicator strategy may claim that its technical strength is fee-adjusted expected edge.

### 4.1 Explicit per-diagnostic classification matrix

The preceding table describes the decision path in prose. This matrix is the exhaustive classification of each diagnostic combination. `A(role)` means actively factored in that role; `R` means report-only; `U` means unavailable. A generic input accepted by the sizing policy is not evidence that a strategy-specific estimator exists: those cells are marked `R` unless the strategy's current service path actually uses the value for that decision.

| Strategy | signal_strength | win_probability | model_confidence | expected_return | directional_expected_edge | fee/spread/slippage | profitability_gate | position_sizing | exit/add | reporting/attribution |
|---|---|---|---|---|---|---|---|---|---|---|
| `ml_enhanced_orderbook` | A(gate) | A(size) | A(size) | A(gate) | A(gate) | A(gate) | A(gate) | A(size) | R | R |
| `orderbook` | A(gate) | R | R | A(gate) | A(gate) | A(gate) | A(gate) | A(size) | R | R |
| `sma` | A(signal) | U | U | U | U | U | U | R | R | R |
| `ema` | A(signal) | U | U | U | U | U | U | R | R | R |
| `rsi` | A(signal) | U | U | U | U | U | U | R | R | R |
| `bollinger` | A(signal) | U | U | U | U | U | U | R | R | R |
| `macd` | A(signal) | U | U | U | U | U | U | R | R | R |
| `stochastic` | A(signal) | U | U | U | U | U | U | R | R | R |
| `fibonacci` | A(signal) | U | U | U | U | U | U | R | R | R |
| `dca` | A(schedule) | U | U | U(by design) | U(by design) | U(alpha gate) | U(alpha gate) | A(risk/cash) | A(schedule add) | R |
| `buyandhold` | A(schedule) | U | U | U(by design) | U(by design) | U(alpha gate) | U(alpha gate) | A(risk/cash) | R(hold) | R |
| `unknown` | U | U | U | U | U | U | U | U | U | R(error) |

For `sma`, `ema`, `rsi`, `bollinger`, `macd`, `stochastic`, and `fibonacci`, `A(signal)` only means the technical signal generator can produce `buy`/`sell`/`hold`; it does not authorize a live entry. Their unavailable expected-return and cost cells cause a required profitability gate to fail closed. `R` in their sizing column means the generic `PositionSizingPolicy` can consume caller-supplied values, but the strategy service has not established that those values are strategy-specific or objective-factored. For `dca` and `buyandhold`, allocation/risk limits are active but deliberately separate from alpha diagnostics. For `unknown`, `evaluateStrategySignal` returns `hold` with an unknown-strategy reason and no action is allowed.

## 5. Current live and simulated behavior

### Live

`LiveTradingService` uses shared non-order-book signal generation and a separate order-book loop. Live entries are Coinbase spot-only: non-buy entries are rejected, and account readiness, minimum quote size, cash, explicit live-order enablement, pending-symbol protection, and maximum-position limits remain mandatory blockers. Existing positions may close on opposite signal or age-out. DCA adds are scheduled buys.

A live sell signal therefore means a close/management intent, not permission to open a short. Any future live-parity paper mode must apply these spot constraints without being confused with synthetic simulated shorts.

### Simulated

`SimulatedTradingService` uses the shared evaluator and diagnostic helper. Non-live-parity simulation can fill sell-side entries, which is useful for synthetic backtests but cannot be presented as Coinbase spot live evidence. The expectancy harness (`evaluateStrategyExpectancy`) records generated signal, diagnostic availability/factor, cost hurdle, blocked intent, fill, and realized net PnL without calling Coinbase.

Current non-order-book diagnostic rows intentionally expose `expected_return_available=false`, `diagnostics_available=false`, `profitability_gate_passed=false`, `diagnostic_factor=expected_return_unavailable` (or `hold`), and `factoring_semantics=unavailable` (or `report` for hold). These values are visibility and fail-safe behavior, not an entry gate implementation for every service path.

## 6. Required API and data-model changes

### 6.1 Canonical backend contract

Extend the strategy diagnostic payload, preserving existing fields for compatibility:

```text
StrategyDiagnostic {
  strategy: string
  signal_type: "buy" | "sell" | "hold"
  signal_strength: double             // [0,1]
  expected_return: double             // decimal fraction
  expected_return_available: bool
  directional_expected_edge: double   // signed for signal direction
  diagnostics_available: bool
  fee_adjusted_expected_return: double
  required_edge: double
  profitability_gate_passed: bool
  profitability_gate_reason: string
  diagnostic_factor: string           // stable machine value
  factoring_semantics: "gate" | "size" | "exit" | "report" | "unavailable"
  unavailable_reason: string
  gate_reason: "hold" | "weak_strength" | "expected_return_unavailable"
    | "negative_fee_adjusted_edge" | "unsupported_signal" | "invalid_input"
    | "stale_estimate" | "execution_blocked" | "passed"
  gate_reason_detail: string
  forecast_horizon: integer | null  // seconds, [1,31536000] when present
  prediction_timestamp: string       // RFC3339 UTC when estimate is present
  schema_version: integer             // positive integer; current version starts at 1
  cost_basis: {
    round_trip_fee_fraction: double
    spread_fraction: double
    slippage_buffer_fraction: double
  }
  bounds_valid: bool
}
```

The C++ ownership should remain in `StrategySignal.hpp/.cpp` for calculation and validation. `LiveTradingService` and `SimulatedTradingService` own source-specific availability and execution policy. `PredictController` owns JSON/API serialization, not duplicated calculations. The frontend `OrderBookSignal.ml_analysis` and `execution_analysis` types own optional compatibility fields and must use `??` for numeric fallback behavior.

The existing C++ structs should evolve compatibly: add fields rather than renaming `expected_return_available`, `diagnostics_available`, `fee_adjusted_expected_return_fraction`, `required_edge_fraction`, `factor`, or `reason`. Expose a stable `unavailable_reason` separately from human-readable `profitability_gate_reason`; do not overload `diagnostic_factor` with prose.

### 6.2 Shared cost policy

Introduce one explicitly configured cost-policy value object used by the order-book gate, strategy diagnostic, minimum trade sizing, and realized attribution:

```text
TradingCostPolicy {
  round_trip_fee_fraction: double
  spread_fraction: double
  slippage_buffer_fraction: double
  source: "configured" | "observed" | "default"
  valid: bool
}
```

Remove the current implicit default conflict (`0.015` in `StrategySignal` versus `0.0016` in `PositionSizingPolicy`). Defaults must be named, observable, and never silently differ between gate and sizing. A policy with missing required live inputs or invalid bounds has `valid=false` and cannot authorize live execution.

### 6.3 Estimator ownership and decision wiring

Add a strategy-neutral expected-return provider interface owned by the strategy/ML boundary, for example:

```text
ExpectedReturnEstimate estimateExpectedReturn(
  strategy, symbol, signal_type, signal_strength,
  market_snapshot, model_context)
```

It must return availability, signed raw return, model/version metadata, timestamp, and validity status. The service then calls the single diagnostic evaluator and passes the result to an explicit execution policy. Do not let UI code, the harness, or a second helper infer actionability.

Until this is implemented and calibrated for `sma`, `ema`, `rsi`, `bollinger`, `macd`, `stochastic`, and `fibonacci`, their expected-return diagnostics remain unavailable. DCA and buy-and-hold remain intentionally unavailable for alpha diagnostics and use their allocation policies instead.

## 7. Fail-closed rules

For live execution, a required input that is unavailable, non-finite, negative where prohibited, outside bounds, stale, or directionally inconsistent must produce a blocked intent with a stable machine-readable reason. At minimum:

- unknown strategy or signal type: block;
- `signal_strength` outside `[0,1]`: block;
- non-finite or unavailable required expected return: block;
- non-finite, negative, or missing required fee/spread/slippage policy: block;
- price, bid, ask, or mid not strictly positive: block;
- `ask < bid`, impossible spread, stale quote, or invalid timestamp: block;
- directional edge not strictly greater than the cost hurdle: block;
- insufficient live cash, minimum notional, pending-order, max-position, or spot-only checks: block;
- invalid sizing result or result above the configured maximum: clamp/block, never leverage upward.

A blocked signal must remain observable separately from a live-account blocker. `profitability_gate_reason` explains diagnostic quality; `execution_analysis.blocker_reason` explains execution authority. No unavailable diagnostic may be converted into an automatic buy, sell, size increase, or liquidation.

## 8. Testing and evidence requirements

Every new estimator or wiring change requires:

1. Unit tests for buy and sell sign normalization, hold behavior, unsupported signals, unavailable/non-finite estimates, equality at the cost hurdle, and bounds rejection.
2. Cost-policy tests proving fees, observed/configured spread, and slippage are added once and use the same values in gate, sizing, and attribution.
3. Strategy fixtures for all twelve strategy names, including unknown, warm-up, positive-edge, fee-negative, and missing-input cases.
4. Live/simulated parity tests proving the same diagnostic object is produced for the same input while preserving live spot-only blockers and clearly labeling synthetic simulated sells.
5. Expectancy harness assertions for average win, average loss, expectancy, profit factor, max drawdown, blocked intents, and the negative-expectancy flag. Zero-PnL open legs remain excluded from win/loss denominators.
6. API serialization and frontend type tests proving availability flags and zero values are not conflated.
7. Exact-SHA remote GitHub Actions Docker Build Validation, including the C++ test target and frontend checks, before closeout. Local Docker/backend builds are not required for this repository workflow.

Evidence for a strategy becoming actively factored must include a fixed fixture or replay/backtest window plus before/after signal count, fill count, blocked intents, average win/loss, net expectancy, profit factor, drawdown, and cost drag. A higher signal count alone is not acceptance evidence.

## 9. Migration and compatibility

Existing clients may omit new optional fields. During migration:

- retain existing JSON names and decimal-fraction units;
- treat `schema_version` as a positive integer (missing legacy rows read as version 1); unknown future versions are report-only and cannot authorize live orders;
- serialize `forecast_horizon` as JSON `null` when absent, never as zero or an empty string;
- serialize `prediction_timestamp` as RFC 3339 UTC and reject malformed timestamps on live paths;
- keep `gate_reason` within the fixed enum and place free-form explanation in `gate_reason_detail`;
- emit `expected_return_available` and `diagnostics_available` whenever an estimate is absent;
- keep `profitability_gate_passed=false` for unavailable or invalid diagnostics;
- map legacy human-readable gate text to the new stable `diagnostic_factor` without parsing prose in the frontend;
- version model and estimator changes through `model_version` / estimator metadata;
- keep `factor=hold` and `factoring_semantics=report` for hold rows;
- do not reinterpret historical rows whose cost basis is unknown; mark them as attribution-incomplete;
- preserve the distinction between simulated synthetic fills and live spot fills in reports and dashboards.

Migration is complete only when every live entry path that claims objective-aligned profitability uses the canonical diagnostic and cost policy, while intentional baselines (`dca`, `buyandhold`) remain explicit reportable exceptions.

## 10. Evidence references

- Strategy inventory and live/simulated path audit: `docs/reports/trade-strategy-objective-review-2026-08-01.md`.
- Non-order-book availability and fail-safe payload: `docs/reports/non-orderbook-diagnostics-closeout-2026-08-05.md`.
- Deterministic fixture and expectancy metrics: `docs/reports/strategy-expectancy-harness-closeout-2026-08-03.md`, `include/trading/StrategyExpectancyHarness.hpp`, `src/trading/StrategyExpectancyHarness.cpp`.
- Objective and factoring vocabulary: `docs/STRATEGY_OBJECTIVE.md`.
- Signal and diagnostic interfaces: `include/trading/StrategySignal.hpp`, `src/trading/StrategySignal.cpp`.
- Generic sizing and minimum-trade policy: `include/trading/PositionSizingPolicy.hpp`, `src/trading/PositionSizingPolicy.cpp`.
- Live execution ownership and spot blockers: `src/trading/LiveTradingService.cpp`.
- Simulated execution ownership and synthetic-fill behavior: `src/trading/SimulatedTradingService.cpp`.
- API serialization and frontend compatibility: `src/api/PredictController.cpp`, `frontend/types/trading.ts`.
