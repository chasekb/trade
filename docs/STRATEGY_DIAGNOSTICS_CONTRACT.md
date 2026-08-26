# Cross-Strategy Profitability and Diagnostic Contract

Status: implementation design contract

This document defines the contract for profitability, expected-return, confidence, cost, execution, and expectancy diagnostics across the live and simulated trading paths. It is intentionally stricter than the current compatibility fields: implementation work must preserve the fail-closed live path and must not infer availability from a numeric zero.

## 1. Scope and decision vocabulary

The supported strategy identifiers are `sma`, `ema`, `rsi`, `bollinger`, `macd`, `stochastic`, `fibonacci`, `dca`, `buyandhold`, `orderbook`, and `ml_enhanced_orderbook`. The same contract applies to every producer, including the indicator signal evaluator, order-book fallback, ML prediction path, simulated trading service, live trading service, execution reconciliation, API serialization, and dashboard normalizers.

A diagnostic has one or more explicit roles:

- **Gate:** may prevent a generated intent from becoming an executable intent. A live gate must fail closed when a required input is missing, malformed, stale, or outside its validity bounds.
- **Sizing input:** may reduce (never increase above the configured risk ceiling) notional or quantity. It is not a substitute for a gate.
- **Exit input:** may request or prioritize a close/reduce action. Profitability diagnostics do not authorize an exit by themselves; position ownership, exchange capability, and close authority remain mandatory.
- **Report-only:** emitted for attribution, analysis, and reconciliation, but cannot change execution.
- **Unavailable:** the producer cannot provide a valid value for the current decision. Unavailable is a state, not a value of zero.

Signal generation and profitability are separate stages. Indicator rules may generate `buy`, `sell`, or `hold`; the profitability stage decides whether a generated non-hold signal is actionable. A `hold` is never converted to an order by diagnostic factoring.

## 2. Canonical units and validity bounds

All canonical API fields below use JSON numbers unless explicitly marked nullable. Fractions are decimal fractions, not percentages: `0.015` means 1.5%. Dollar amounts are USD-equivalent quote currency. Prices are positive quote currency per base unit; quantities are positive base units. Timestamps are UTC ISO-8601 strings.

| Field | Canonical unit | Valid range | Invalid or missing behavior |
|---|---|---:|---|
| `signal_type` / `intended_side` | enum | `buy`, `sell`, `hold` | reject the diagnostic; live intent is blocked |
| `signal_strength` | fraction | `[0, 1]` | block; do not clamp malformed input silently |
| `win_probability` | probability fraction | `[0, 1]` | unavailable; if required by policy, block |
| `model_confidence` / `confidence` | probability-like fraction | `[0, 1]` | unavailable; if required by policy, block |
| `expected_return_fraction` | signed return fraction for the forecast horizon | finite and inclusive `[-1, 1]` | `null` with `status=invalid` for non-finite or out-of-range input; live gate blocks |
| `directional_expected_edge_fraction` | non-negative return fraction in intended direction | finite and inclusive `[0, 1]` | `null` with `status=invalid` for non-finite, negative, or greater-than-one input; live gate blocks |
| `fee_fraction` | fraction of notional | finite and inclusive `[0, 1]` | `null` with `status=invalid` for non-finite, negative, or greater-than-one input; live gate blocks |
| `spread_fraction` | fraction of mid-price/notional | finite and inclusive `[0, 1]` | `null` with `status=invalid` for non-finite, negative, or greater-than-one input; live gate blocks |
| `slippage_buffer_fraction` | non-negative fraction of notional | finite and inclusive `[0, 1]` | `null` with `status=invalid` for non-finite, negative, or greater-than-one input; live gate blocks |
| `required_edge_fraction` | sum of cost fractions | finite and inclusive `[0, 3]` | `null` with `status=invalid` if any cost is invalid or the sum is non-finite/out of range; live gate blocks |
| `fee_adjusted_expected_return_fraction` | directional net return fraction | finite and inclusive `[-3, 1]` | `null` with `status=invalid` if derived from invalid inputs; live gate blocks |
| `forecast_horizon` | integer seconds for the forecast | `null` (not applicable/unavailable) or integer `[1, 31,536,000]` inclusive | reject fractional, non-integer, zero, negative, non-finite, or over-year values; required forecast with invalid horizon is unavailable and live-blocking |
| `price`, `mid_price` | USD/base unit | finite and `> 0` for an order | block |
| `quantity`, `notional_usd` | base units / USD | finite and `>= 0`; order quantity must be `> 0` | block |
| `realized_pnl`, `net_pnl`, fees | USD | finite; PnL may be negative, fees must be `>= 0` | reject persisted outcome or mark reconciliation incomplete |
| `win_rate`, `intent_conversion_rate`, `outcome_coverage` | fraction internally; percentage only where documented | `[0, 1]` internally | reject; the serialized `win_rate` compatibility field is `[0, 100]` |
| `status` | enum | `available`, `unavailable`, `invalid`, `not_applicable` | reject unknown values; live execution treats every value except `available` as blocked |
| `role` | enum | `gate`, `sizing`, `exit`, `report_only` | reject unknown values; role cannot grant authority not defined by the decision path |
| `gate_reason` | fixed enum | `none`, `hold_signal`, `insufficient_history`, `missing_diagnostic`, `invalid_diagnostic`, `negative_directional_edge`, `non_positive_net_edge`, `invalid_cost`, `stale_market_data`, `model_unavailable`, `exchange_not_ready`, `position_authority`, `minimum_notional`, `live_not_authorized`, `unsupported_strategy`, `unsupported_side` | reject unknown values; human text belongs in optional `gate_reason_detail` |
| `generated_at` | UTC RFC 3339 timestamp | parseable UTC timestamp with `Z` offset and second precision | reject missing, malformed, or non-UTC timestamps |
| `source` | enum | `strategy`, `ml`, `orderbook`, `exchange_fill`, `reconciliation` | reject unknown values |

Do not use `NaN`, infinity, sentinel negatives, or a fabricated zero to represent unavailable data in JSON. Canonical API fields use `null` plus an explicit availability/status field. Legacy fields that cannot be nullable retain their old numeric shape only for compatibility and must be accompanied by the canonical field and status.

## 3. Direction and sign semantics

`expected_return_fraction` is a signed forecast for the underlying price move over a named forecast horizon, independent of the action. Positive means the price is expected to rise; negative means it is expected to fall. This is the convention used by existing ML fields such as `prev_expected_return` and the strategy fixture input.

For an intended action, normalize to a non-negative directional edge:

```text
buy:  directional_edge =  expected_return_fraction
sell: directional_edge = -expected_return_fraction
hold: directional_edge = unavailable / not applicable
```

A buy with a negative forecast and a sell with a positive forecast therefore has a negative directional edge and cannot pass a profitability gate. A sell with a negative forecast can pass if its magnitude clears costs. Never compare a raw signed forecast to a cost hurdle without applying this normalization.

The canonical formulas are:

```text
required_edge = fee_fraction + spread_fraction + slippage_buffer_fraction
net_edge = directional_edge - required_edge
profitability_passed = signal_type != hold
                      && signal_strength >= min_signal_strength
                      && expected_return_available
                      && all cost inputs valid
                      && net_edge > 0
```

The strict `> 0` comparison is intentional: exactly fee-neutral trades are not actionable. A policy may add a positive minimum net PnL requirement, exchange minimum notional, or safety margin, but may not make a negative or unavailable edge executable in live mode.

## 4. Cost basis and fee semantics

All cost fractions used before execution are charged against the intended order's quote notional. The required edge uses a round-trip basis:

- `fee_fraction` is the estimated total entry plus exit fee fraction for the complete trade. The existing compatibility name `round_trip_fee_fraction` maps to this field.
- `spread_fraction` is the estimated round-trip bid/ask crossing cost as a fraction of mid-price. If the producer has only one-way spread, it must explicitly convert it to the configured round-trip basis rather than silently mixing bases.
- `slippage_buffer_fraction` is a conservative round-trip adverse-move allowance, not observed slippage. It must not be added again after actual fill reconciliation.

Do not mix `spread_percent` (currently present in order-book features) with canonical `spread_fraction` without an explicit percent-to-fraction conversion. A value of `0.15` in a field named percent means 0.15%; a canonical fraction is `0.0015`.

For live execution, provisional costs are gates/sizing estimates only. After a fill, the authoritative exchange fee replaces any estimate. Actual charged fees must flow through the in-memory fill, cash/equity accounting, persisted trade row, aggregate session statistics, reconciliation, API response, and frontend. Never add an exchange-confirmed fee to a provisional fee that was already booked; apply only the accounting delta.

For simulated execution, the configured fee/spread/slippage assumptions are the accounting basis and must be recorded with the simulated fill. A simulation must not claim exchange-confirmed fees.

## 5. Diagnostic record and API contract

Implementers should introduce a shared diagnostic record (name may vary, but fields and semantics must match):

```text
ProfitabilityDiagnostic {
  status: "available" | "unavailable" | "invalid" | "not_applicable"
  signal_type: "buy" | "sell" | "hold"
  signal_strength: number | null
  win_probability: number | null
  model_confidence: number | null
  expected_return_fraction: number | null
  forecast_horizon: integer_seconds | null
  directional_expected_edge_fraction: number | null
  fee_fraction: number | null
  spread_fraction: number | null
  slippage_buffer_fraction: number | null
  required_edge_fraction: number | null
  fee_adjusted_expected_return_fraction: number | null
  min_signal_strength: number | null
  profitability_gate_passed: boolean
  gate_reason: "none" | "hold_signal" | "insufficient_history" | "missing_diagnostic" | "invalid_diagnostic" | "negative_directional_edge" | "non_positive_net_edge" | "invalid_cost" | "stale_market_data" | "model_unavailable" | "exchange_not_ready" | "position_authority" | "minimum_notional" | "live_not_authorized" | "unsupported_strategy" | "unsupported_side"
  gate_reason_detail: string | null
  role: "gate" | "sizing" | "exit" | "report_only"
  generated_at: string
  source: "strategy" | "ml" | "orderbook" | "exchange_fill" | "reconciliation"
}
```

Required serialization changes:

1. Add the canonical nullable fields and `status`, `gate_reason`, `source`, and `forecast_horizon` to signal/analysis JSON.
2. Keep `expected_return` and `fee_adjusted_expected_return` temporarily as compatibility aliases, documented as fractions. Mark them deprecated and make their direction semantics explicit in API documentation.
3. Serialize unavailable canonical numerics as JSON `null`; do not serialize `0.0` as if it were a forecast.
4. Serialize `profitability_gate_passed=false` whenever status is not `available`, regardless of the legacy numeric fields.
5. Add `diagnostic_contract_version` to signal and reconciliation payloads so frontend and backend contract migrations are observable.
6. Add units metadata or stable field names; do not expose a field whose name alternates between percent and fraction.
7. For reconciliation, preserve `win_rate` as a 0–100 percentage for the existing backend contract, while `share`, `intent_conversion_rate`, and `outcome_coverage` remain fractions in `[0,1]`. `average_loss` remains a positive loss magnitude. `profit_factor` remains explicitly undefined when there are no losses; use the existing `profit_factor_undefined` flag rather than a fabricated infinity.

Frontend types and normalizers must use `??`, preserve legitimate zeroes, distinguish `null` from zero, and display unavailable status rather than silently showing a zero edge. The dashboard must not enable a live start or order control based only on a legacy field.

## 6. Strategy and decision-path classification

The classification below describes the current intended behavior and the required target contract. “Active” means the value can affect the named decision after implementation; “report-only” means it is diagnostic output and cannot affect the decision; “unavailable” means no valid producer exists at that point.

| Strategy | Signal generation | Entry profitability gate | Entry sizing | Add-to-position | Exit/close | Execution/reporting |
|---|---|---|---|---|---|---|
| `sma` | Active: crossover emits buy/sell/hold; strength `[0,1]` | Required for live; simulated policy may explicitly configure bypass, default fail-closed | Active sizing input may reduce configured ceiling | Same entry contract; no implicit averaging | Report-only unless a separate exit rule requests close | Active blocker and expectancy attribution |
| `ema` | Active: crossover emits buy/sell/hold | Required for live | Active sizing input | Same as `sma` | Report-only unless separate exit rule | Active attribution |
| `rsi` | Active: oversold buy / overbought sell | Required for live; missing expected return blocks | Active sizing input | Same entry contract; ownership/position limits still gate | Report-only unless explicit exit policy | Active attribution |
| `bollinger` | Active: band excursion emits buy/sell | Required for live | Active sizing input | Same entry contract | Report-only unless explicit exit policy | Active attribution |
| `macd` | Active: MACD/signal crossover | Required for live | Active sizing input | Same entry contract | Report-only unless explicit exit policy | Active attribution |
| `stochastic` | Active: oversold/overbought | Required for live | Active sizing input | Same entry contract | Report-only unless explicit exit policy | Active attribution |
| `fibonacci` | Active: retracement/support/resistance | Required for live | Active sizing input | Same entry contract | Report-only unless explicit exit policy | Active attribution |
| `dca` | Active: schedule emits buy | Required for live unless an explicit, audited DCA policy says otherwise; schedule is not profitability evidence | Active sizing input, capped by configured risk | Active by definition, but every purchase still passes cash, minimum, and live safety gates | Report-only | Active attribution; record scheduled reason |
| `buyandhold` | Active: one initial buy | Required for live; no position is not evidence of profitability | Active sizing input | No re-entry after held position unless policy explicitly changes | Report-only; hold does not imply close | Active attribution |
| `orderbook` | Active: imbalance/order-book signal | Active shared profitability gate; missing ML expected return remains unavailable and blocks | Active sizing input; spread/volatility reduce size but cannot override gate | Same shared gate and ownership checks | Report-only unless explicit close policy | Active blocker, fill, and expectancy attribution |
| `ml_enhanced_orderbook` | Active: order-book signal followed by classifier/regressor/transformer enrichment | Active shared profitability gate, then active directional ML gate; missing required model output blocks unless the explicitly configured baseline fallback produces a valid diagnostic | Active sizing input from directional edge, confidence, and spread/volatility; never overrides either gate | Same fresh diagnostic, ML, ownership, and execution checks | Report-only unless explicit close policy | Active model-readiness, profitability, ML-blocker, fill, and expectancy attribution |

The decision-path table above is supplemented by the following exhaustive diagnostic matrix. It is normative for both the live service and the ordinary simulated/backtest service; the final column identifies mode-specific behavior. Each cell is an explicit classification, not an assertion that a numeric producer already exists.

Legend: `Active (producer)` is factored into the named path when its producer is valid; `Active (fail-closed)` is an active blocker that rejects an unavailable or invalid required diagnostic; `Active (cost)` is an active configured cost or ceiling input; `Report-only` cannot alter an action; `Unavailable (reason)` has no valid producer at that path. A simulation bypass is `Report-only (explicit bypass)` and is never inherited by live mode.

| Strategy / path | `signal_strength` | `win_probability` | `model_confidence` | signed `expected_return_fraction` | directional edge | fee / spread / slippage | profitability gate | sizing | exit | blocker / reporting | Mode-specific rationale |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `sma` | Active (producer) | Unavailable (no model producer) | Unavailable (no model producer) | Unavailable (no forecast producer) | Unavailable (depends on forecast) | Active (cost) | Active (fail-closed) | Active (cost/ceiling only) | Report-only | Active (report/block) | Live blocks entries; Sim may use explicit bypass for signal-only studies. |
| `ema` | Active (producer) | Unavailable (no model producer) | Unavailable (no model producer) | Unavailable (no forecast producer) | Unavailable (depends on forecast) | Active (cost) | Active (fail-closed) | Active (cost/ceiling only) | Report-only | Active (report/block) | Live blocks entries; Sim may use explicit bypass for signal-only studies. |
| `rsi` | Active (producer) | Unavailable (no model producer) | Unavailable (no model producer) | Unavailable (no forecast producer) | Unavailable (depends on forecast) | Active (cost) | Active (fail-closed) | Active (cost/ceiling only) | Report-only | Active (report/block) | Live blocks entries; Sim may use explicit bypass for signal-only studies. |
| `bollinger` | Active (producer) | Unavailable (no model producer) | Unavailable (no model producer) | Unavailable (no forecast producer) | Unavailable (depends on forecast) | Active (cost) | Active (fail-closed) | Active (cost/ceiling only) | Report-only | Active (report/block) | Live blocks entries; Sim may use explicit bypass for signal-only studies. |
| `macd` | Active (producer) | Unavailable (no model producer) | Unavailable (no model producer) | Unavailable (no forecast producer) | Unavailable (depends on forecast) | Active (cost) | Active (fail-closed) | Active (cost/ceiling only) | Report-only | Active (report/block) | Live blocks entries; Sim may use explicit bypass for signal-only studies. |
| `stochastic` | Active (producer) | Unavailable (no model producer) | Unavailable (no model producer) | Unavailable (no forecast producer) | Unavailable (depends on forecast) | Active (cost) | Active (fail-closed) | Active (cost/ceiling only) | Report-only | Active (report/block) | Live blocks entries; Sim may use explicit bypass for signal-only studies. |
| `fibonacci` | Active (producer) | Unavailable (no model producer) | Unavailable (no model producer) | Unavailable (no forecast producer) | Unavailable (depends on forecast) | Active (cost) | Active (fail-closed) | Active (cost/ceiling only) | Report-only | Active (report/block) | Live blocks entries; Sim may use explicit bypass for signal-only studies. |
| `dca` | Active (schedule producer) | Unavailable (no model producer) | Unavailable (no model producer) | Unavailable (no forecast producer) | Unavailable (depends on forecast) | Active (cost) | Active (fail-closed) | Active (cost/ceiling) | Report-only | Active (schedule/block) | Live requires the shared gate unless an audited policy is explicitly approved; Sim bypass remains report-labeled. |
| `buyandhold` | Active (initial-buy producer) | Unavailable (no model producer) | Unavailable (no model producer) | Unavailable (no forecast producer) | Unavailable (depends on forecast) | Active (cost) | Active (fail-closed) | Active (cost/ceiling) | Report-only | Active (report/block) | Live requires the shared gate; Sim bypass is explicit and cannot authorize re-entry or close. |
| `orderbook` | Active (producer) | Unavailable (plain orderbook has no probability) | Unavailable (plain orderbook has no model) | Unavailable (no forecast producer) | Unavailable (depends on forecast) | Active (producer/config) | Active (fail-closed) | Active (cost/ceiling) | Report-only | Active (report/block/fill) | Live and Sim use identical arithmetic; missing expected return blocks live and is report-labeled by an explicit Sim bypass only. |
| `ml_enhanced_orderbook` | Active (orderbook producer) | Active (classifier producer) | Active (model producer) | Active (model/fallback producer) | Active (producer) | Active (producer/config) | Active (fail-closed) | Active (edge/confidence/cost) | Report-only | Active (model/block/fill) | Live and Sim require valid model output unless the configured labeled fallback supplies the same valid diagnostic. |
| unknown strategy identifier | Unavailable (evaluator returns `hold`) | Unavailable (no strategy producer) | Unavailable (no strategy producer) | Unavailable (unsupported strategy) | Unavailable (depends on forecast) | Unavailable (no intent) | Active (fail-closed: unsupported_strategy) | Unavailable (no executable intent) | Report-only (no close authority) | Active (block/report) | Live always blocks; Sim records `hold` and unsupported-strategy status and cannot bypass into an order. |

For every indicator, DCA, buy-and-hold, and plain-orderbook row, “Unavailable” is intentional current-state behavior: it does not mean zero, and it does not turn the corresponding gate into report-only. For live mode the active fail-closed gate blocks the generated buy/sell intent. For simulation/backtest mode, only an explicit caller policy may change that gate to `Report-only (explicit bypass)`; the bypass must be serialized with its reason and is rejected by live configuration. `ml_enhanced_orderbook` is the only listed strategy whose current contract has producers for all forecast/confidence diagnostics, subject to model readiness and bounds.

The unknown identifier is the `evaluateStrategySignal` fallback: it returns `hold`, has no signal-strength or profitability producer, and receives `gate_reason=unsupported_strategy`; it is not equivalent to a valid zero-strength strategy. This row applies to live, simulation, and harness paths.

The indicator strategies currently generate signals without expected-return data. Until a valid model/forecast producer is wired to each strategy, their profitability diagnostic is `unavailable`, not fee-neutral. The live service must therefore block generated entries under the shared gate. Simulated/backtest callers may use an explicit opt-in policy to evaluate signal behavior without a profitability gate, but that bypass must be visible in the report and never leak into live configuration.

`ml_enhanced_orderbook` is a distinct live and simulated strategy identifier even though it shares order-book signal generation with `orderbook`. Its classifier probability/confidence gate is an additional active decision path after profitability factoring. Transformer warm-up or unavailable required inference is fail-closed; a configured baseline fallback is acceptable only when it emits a valid, labeled expected-return diagnostic and remains prohibited from weakening the live safety invariant.

At raw order-book signal generation, ML `win_probability`, `expected_return`, and `confidence` are report-only. In the `ml_enhanced_orderbook` post-enrichment path they are explicitly promoted to active gate/sizing inputs, as shown in the matrix; the role must be present in the diagnostic record and the required validity bounds apply. Confidence must not be treated as expected return: it is a `[0,1]` certainty-like score, while expected return is signed and horizon-specific.

## 7. Decision-path requirements

### Signal generation

`evaluateStrategySignal` owns indicator logic and returns only signal type, strength, and reason. It must not fabricate profitability. Each service must attach one diagnostic record after signal generation and before intent creation. Warm-up (`insufficient price history`) remains a data-sufficiency hold; it must not be mislabeled as a profitability blocker.

### Profitability and ML gates

Apply signal-strength bounds, availability, direction normalization, and cost hurdle in one shared function. Reject unsupported side values and non-finite values. Record the first blocking reason and all applicable diagnostic fields. A missing model output, malformed legacy signal JSON, missing mid-price, or invalid cost estimate is fail-closed for live execution.

### Position sizing

`PositionSizingInputs::expected_return` must adopt the signed forecast convention, while sizing should consume `directional_expected_edge_fraction` or an explicitly named signed value after side normalization. Cost-adjusted edge must not be counted twice: either the sizing function receives gross expected return and subtracts required costs once, or it receives net edge and does not subtract them again. The configured dollar/percentage allocation is a hard upper bound; all confidence/performance multipliers can only reduce it.

`MinimumTradeSizeInputs` must use the same canonical cost basis and must reject non-finite/negative cost inputs rather than clamping them into a plausible trade. `allow_unprofitable_trades` is not permitted for live mode and must be carried as an explicit simulation/backtest-only flag.

### Add-to-position and DCA

An add is a new entry intent for cost and accounting purposes. It must have its own diagnostic snapshot, side, expected-return horizon, cost assumptions, notional, and gate result. Do not reuse the original entry diagnostic after market conditions change. DCA schedule eligibility does not bypass profitability, cash, minimum-notional, or ownership gates.

### Exits and closes

Profitability diagnostics are not close authority. Close decisions must continue to enforce managed/inherited position authority, quantity floors, exchange minimum notional, and live opt-in. If an exit model is added, it must use an explicit `exit_expected_return_fraction` and exit horizon rather than overloading entry `expected_return_fraction`; direction is defined by the reduction action and must be normalized separately. A flat gross close with nonzero fees remains a closing leg and a fee-negative outcome where appropriate.

### Execution blockers and reconciliation

Every generated signal, executable intent, blocker, fill, and closing outcome must preserve strategy, symbol, side, diagnostic status/factor, gross forecast, directional edge, required edge, and actual fees. `blocked_expected_return_sum` must use the canonical signed forecast only when aggregating by forecast; a directional-edge sum requires a separate field and cannot be inferred later. Reconciliation must count all closing legs, including exact-flat gross PnL exits, and must report unexplained outcomes and incomplete coverage.

## 8. Required versus optional implementation changes

### Required before adopting this contract

1. Add a shared typed diagnostic record/status and central direction-normalization/factoring function.
2. Replace implicit zero defaults for expected return, edge, and costs with nullable/status-aware representations at API boundaries.
3. Validate finite values and bounds at service boundaries; fail closed for live gates.
4. Unify live and simulated order-book gate arithmetic with the canonical fee/spread/slippage basis.
5. Separate signed gross forecast from directional net edge in `StrategySignal`, `PositionSizingPolicy`, `StrategyExpectancyHarness`, `ExecutionReconciliation`, and JSON serialization.
6. Add explicit side, horizon, availability/status, and diagnostic factor to persisted signal/intent records and API payloads; provide a migration/backward-compatible reader for legacy rows.
7. Ensure live exchange fees replace estimates exactly once and are propagated to persistence, accounting, reconciliation, and frontend output.
8. Update frontend TypeScript types, normalizers, tables, and API tests for `null` unavailable fields, units, side semantics, and contract version.
9. Add tests for buy/sell normalization, hold/unsupported side, missing/non-finite/out-of-range inputs, exact fee-neutral boundaries, negative directional edge, cost-basis conversion, live fail-closed behavior, and legacy payloads.
10. Add per-strategy fixtures for all eleven strategies, including generated signal, unavailable diagnostic, blocked intent, allowed simulated bypass, fill, and exact-flat close accounting; include separate model-ready, model-unavailable, and configured-fallback cases for `ml_enhanced_orderbook`.

### Optional improvements after the required migration

- Add a strongly typed C++ enum for side/status/diagnostic role instead of strings.
- Add a forecast-provider interface with model version, calibration window, and horizon metadata.
- Persist separate one-way and round-trip spread/slippage estimates when execution analysis needs both.
- Add schema-level database constraints for finite/range checks where PostgreSQL types permit them.
- Add dashboard tooltips and unit labels sourced from the contract version.
- Add calibration and drift reports for confidence and expected-return forecasts.
- Add property-based tests over valid/invalid numeric ranges and a cross-language JSON contract fixture.

## 9. Test and acceptance matrix

The implementation is complete only when tests demonstrate:

1. For the same forecast and costs, buy uses `+forecast`, sell uses `-forecast`; opposite-direction forecasts are blocked.
2. Fees, spread, and slippage are each applied once on the declared round-trip basis.
3. `net_edge == 0` is blocked; positive edge passes only when strength and all required inputs are valid.
4. Missing, `null`, malformed, non-finite, negative-cost, or out-of-range inputs never become executable live intents.
5. `hold`, warm-up, unsupported strategy, and unsupported side have distinct factors/statuses.
6. Sizing never exceeds the configured maximum and never turns an unavailable gate into a trade.
7. Live and simulated order-book paths produce the same diagnostic arithmetic; simulation bypass is explicit and live bypass is rejected.
8. Adds/DCA receive fresh diagnostics; exits preserve authority and minimum-notional guards.
9. Actual exchange fees replace provisional fees without double counting; simulated assumptions remain labeled simulated.
10. API JSON round-trips canonical `null` availability and frontend preserves zero values with nullish fallbacks.
11. Reconciliation attributes blockers and outcomes by strategy and side, counts exact-flat closing legs, and exposes coverage/undefined profit-factor flags.
12. CI exercises the C++ unit targets and frontend contract tests; no completion claim should rely on local build output when the repository's remote-only policy applies.

## 10. Live safety invariant

No live order may be submitted solely because a strategy emitted `buy` or `sell`, because a confidence value is nonzero, or because a legacy expected-return field defaulted to zero. A live intent requires a valid, available, directionally favorable diagnostic, a positive net edge over the complete cost hurdle, valid sizing, current market data, position/account authority, exchange minimum compliance, and explicit live execution authorization. Any uncertainty in those prerequisites blocks the intent and records a durable reason for reconciliation.
