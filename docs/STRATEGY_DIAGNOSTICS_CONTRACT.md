# Cross-Strategy Diagnostics Contract

Status: proposed design contract for review; current implementation is explicitly distinguished below
Scope: live trading, ordinary simulation, live-parity simulation, and expectancy reporting
Normative safety rule: live execution fails closed whenever a required diagnostic is unavailable, invalid, or contradictory. This document distinguishes the current implementation from the proposed contract; it does not claim that proposed behavior is already implemented.

## 1. Purpose and objective

This contract defines how strategy signals, model diagnostics, trading costs, execution blockers, sizing, exits, and attribution are represented and interpreted across the trade system. It supports the project objective in `docs/STRATEGY_OBJECTIVE.md`: improve risk-adjusted expectancy after fees, spread, and slippage rather than maximizing signal or trade count.

Every implementation or review using this contract must be able to attribute:

- generated signals and signal strength;
- expected return and fee-adjusted expected return;
- required edge and profitability-gate outcome;
- executed trades and blocked intents, with blocker precedence;
- average win, average loss, expectancy, profit factor, and maximum drawdown;
- live-only exchange/account blockers.

A missing diagnostic is not a zero estimate, a high-confidence estimate, or permission to trade.

## 2. Strategy and decision-path inventory

The selectable strategy identifiers are defined in `frontend/components/dashboard/StrategySelector.tsx:11-22`:

- `ml_enhanced_orderbook` — order-book signal plus classifier/regressor/transformer diagnostics;
- `orderbook` — order-book imbalance signal and heuristic/model expected-return path;
- `sma` and `ema` — short/long moving-average comparison;
- `rsi` — overbought/oversold threshold signal;
- `bollinger` — band/z-score signal;
- `macd` — MACD/signal crossover;
- `stochastic` — stochastic threshold signal;
- `fibonacci` — retracement support/resistance proximity;
- `dca` — scheduled accumulation buy;
- `buyandhold` — initial allocation buy, then hold;
- `unknown` — any unrecognized identifier. Current code returns a hold with `Unknown strategy: <name>` at `src/trading/StrategySignal.cpp:301-302`; the proposed contract treats this as invalid non-trading configuration.

The following paths are distinct and must not be collapsed into “the strategy”: signal generation and warm-up; order-book profitability gate; ML directional/confidence gate; live entry authority; ordinary simulated entry; simulated live-parity entry; live and simulated DCA adds; opposite-signal exit; age-out exit; stop-loss/take-profit; explicit close; account liquidation; position sizing and minimum trade size; pending-order, account, cash, max-position, minimum-notional, spot-side, and execution-enable blockers; persisted signal/trade attribution; and expectancy-harness aggregation. Live-parity paper mode is not implemented in the repository today, so every live-parity row below is a future/unsupported policy row rather than evidence of a current execution path.

## 3. Classification vocabulary

A diagnostic has both a factual availability state and a decision role. The matrix uses the following compact labels:

- **A** — actively factored into the named action decision today.
- **R** — report, attribution, or sizing input only; it does not universally authorize or block the action.
- **U** — unavailable or unsupported for that strategy/path. It must not be interpreted as zero or positive edge.


The normative roles are `gate`, `size`, `exit`, `report`, and `unavailable`, matching `docs/STRATEGY_OBJECTIVE.md:41-58`. A field may be `R` in one path and `A` in another. “Active” in the matrix is current behavior, not approval of every current behavior as safe.

## 4. Strategy/diagnostic matrix

Columns: `S` signal/strength, `W` win probability, `C` model confidence, `E` signed expected return, `D` directional edge, `K` fee+spread+slippage hurdle, `G` profitability gate, `Z` position sizing, `X` exits, and `B` blocker/reporting attribution.

| Strategy and path | S | W | C | E | D | K | G | Z | X | B | Current rationale and contract disposition |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `orderbook`, live | A | R | R | A | A | A | A | A | R | A | Imbalance generates buy/sell; directional edge is cost-adjusted by the shared gate (`StrategySignal.cpp:305-341`). Account and execution blockers remain authoritative. |
| `orderbook`, ordinary simulated | A | R | R | A | A | A | A | A | R | A | Same profitability contract; simulation additionally applies simulated fill and minimum-size rules. |
| `orderbook`, live-parity simulated (future/unsupported today) | U | U | U | U | U | U | U | U | U | R | The repository has no live-parity paper mode today. These are future policy requirements, not current active classifications; until implemented they are unavailable and excluded from performance aggregates. |
| `ml_enhanced_orderbook`, live | A | A | A | A | A | A | A | A | R | A | Order-book profitability gate and ML directional/confidence gate both constrain entry; inference readiness is fail-closed when required. |
| `ml_enhanced_orderbook`, ordinary simulated | A | A | A | A | A | A | A | A | R | A | Current fallback and transformer warm-up differ from live; the proposed contract requires an explicit configured parity policy. |
| `ml_enhanced_orderbook`, live-parity simulated (future/unsupported today) | U | U | U | U | U | U | U | U | U | R | The repository has no live-parity paper mode today. A future implementation must replay live authority with exchange submission disabled; until then these diagnostics are unavailable and excluded from performance aggregates. |
| `sma`/`ema`, live | A | U | U | U | U | R | U | R | R | A | Signal is active, but current diagnostic payload says expected return unavailable. Existing service paths may still reach ordinary entry; proposed live authority blocks where edge is required. |
| `sma`/`ema`, ordinary simulated | A | U | U | U | U | R | U | R | R | A | Current ordinary simulation and the stricter harness disagree on unavailable-edge behavior; this is an explicit reconciliation item. |
| `sma`/`ema`, live-parity simulated (future/unsupported today) | U | U | U | U | U | U | U | U | U | R | No live-parity paper mode exists today; unavailable and excluded from performance aggregates until implemented. |
| `rsi`, live | A | U | U | U | U | R | U | R | R | A | Threshold signal is active; warm-up holds. No supported expected-return estimator currently exists. |
| `rsi`, ordinary simulated | A | U | U | U | U | R | U | R | R | A | Report unavailable diagnostics; do not convert the zero placeholder into alpha. |
| `rsi`, live-parity simulated (future/unsupported today) | U | U | U | U | U | U | U | U | U | R | No live-parity paper mode exists today; unavailable and excluded from performance aggregates until implemented. |
| `bollinger`, live | A | U | U | U | U | R | U | R | R | A | Band signal is active; insufficient history and zero volatility hold. Expected return is unavailable. |
| `bollinger`, ordinary simulated | A | U | U | U | U | R | U | R | R | A | Same semantics; harness must record unavailable rather than negative expectancy. |
| `bollinger`, live-parity simulated (future/unsupported today) | U | U | U | U | U | U | U | U | U | R | No live-parity paper mode exists today; unavailable and excluded from performance aggregates until implemented. |
| `macd`, live | A | U | U | U | U | R | U | R | R | A | Crossover signal is active; expected return unavailable and live entry must fail closed if required by policy. |
| `macd`, ordinary simulated | A | U | U | U | U | R | U | R | R | A | Crossover/warm-up is reportable; ordinary simulation behavior must be aligned with harness policy. |
| `macd`, live-parity simulated (future/unsupported today) | U | U | U | U | U | U | U | U | U | R | No live-parity paper mode exists today; unavailable and excluded from performance aggregates until implemented. |
| `stochastic`, live | A | U | U | U | U | R | U | R | R | A | Threshold signal is active; no supported return/confidence diagnostic. |
| `stochastic`, ordinary simulated | A | U | U | U | U | R | U | R | R | A | Same unavailable semantics and explicit blocker attribution. |
| `stochastic`, live-parity simulated (future/unsupported today) | U | U | U | U | U | U | U | U | U | R | No live-parity paper mode exists today; unavailable and excluded from performance aggregates until implemented. |
| `fibonacci`, live | A | U | U | U | U | R | U | R | R | A | Retracement signal is active; no-range, warm-up, and between-levels paths hold. |
| `fibonacci`, ordinary simulated | A | U | U | U | U | R | U | R | R | A | Report signal quality separately from unavailable profitability diagnostics. |
| `fibonacci`, live-parity simulated (future/unsupported today) | U | U | U | U | U | U | U | U | U | R | No live-parity paper mode exists today; unavailable and excluded from performance aggregates until implemented. |
| `dca`, live initial/add | A | U | U | U | U | R | U | A | R | A | Scheduled buy and fixed-size behavior are active; live add permissions and account blockers remain active. Exemption from an expectancy gate is unresolved. |
| `dca`, simulated initial/add | A | U | U | U | U | R | U | A | R | A | Fixed allocation currently bypasses some multiplier logic (`SimulatedTradingService.cpp:396-403`); define whether this is a deliberate benchmark exemption. |
| `dca`, live-parity initial/add (future/unsupported today) | U | U | U | U | U | U | U | U | U | R | No live-parity paper mode exists today; future benchmark-allocation policy is unavailable and excluded from performance aggregates until implemented. |
| `buyandhold`, live | A | U | U | U | U | R | U | A | R | A | Initial allocation is a fixed-size baseline and then holds. Horizon and cost-gate exemption are unresolved. |
| `buyandhold`, simulated | A | U | U | U | U | R | U | A | R | A | Must remain a benchmark, not be mislabeled as predictive alpha. |
| `buyandhold`, live-parity (future/unsupported today) | U | U | U | U | U | U | U | U | U | R | No live-parity paper mode exists today; future benchmark-allocation policy is unavailable and excluded from performance aggregates until implemented. |
| `unknown`, any path | U | U | U | U | U | U | U | U | U | R | Current fallback is hold-only, not an active signal producer. Proposed configuration validation rejects it before a trading session; unknown rows are excluded from performance aggregates and cannot count as valid strategy performance. |

## 5. Diagnostic value semantics

### 5.1 Signal and strength

`StrategySignalOutcome` in `include/trading/StrategySignal.hpp:40-44` uses `signal_type = buy|sell|hold`, `strength` intended in `[0,1]`, and a human-readable reason. `hold` includes warm-up, insufficient data, zero volatility, no range, and unknown strategy fallback. Hold is non-actionable and report-only.

Current producers: order-book imbalance uses an activity threshold of 0.22 and strength based on absolute imbalance; SMA/EMA compare fast and slow averages; RSI, Bollinger, MACD, stochastic, and Fibonacci use their respective threshold/crossover/level rules; DCA emits a scheduled buy; buy-and-hold emits one initial buy. Exact tuning knobs are in `StrategyParams` (`StrategySignal.hpp:12-38`).

Proposed bounds: reject non-finite strength and clamp only at the producer boundary; consumers accept exactly `[0,1]`. A hold or invalid strength cannot pass an action gate.

### 5.2 Expected return, direction, and confidence

Current fields use fractional values, not percentages: `expected_return_fraction` and `directional_expected_edge_fraction` (`StrategySignal.hpp:46-82`). For a buy, directional edge is `expected_return_fraction`; for a sell it is `-expected_return_fraction` (`StrategySignal.cpp:311-317`, `374-377`). Therefore profitable buys require positive model return and profitable sells require negative model return before costs. The serialized UI fields currently include `expected_return`, `fee_adjusted_expected_return`, and `required_edge`; the UI must preserve fraction-vs-percent labeling.

Current code validates availability with an explicit boolean and `std::isfinite`, but does not establish a universal finite range, model horizon, or whether model output is gross or net. The following are proposed bounds for the new schema, pending approval of the canonical basis in Section 10; they are not claims about current production validation:

- `expected_return` and `directional_expected_edge` are fractions in the inclusive range `[-1.0, 1.0]`. A finite value exactly at either boundary is valid; a non-finite or out-of-range value is invalid, sets availability false, records `expected_return_invalid`, and cannot pass a gate. No silent clamping is permitted.
- `forecast_horizon` is either null (unavailable) or an integer number of seconds in the inclusive range `[1, 31_536_000]` (one second through 365 days). Non-integer, zero, negative, non-finite, or out-of-range values are schema errors and fail closed for required diagnostics.
- `profitability_gate_reason` is a lowercase ASCII enum, not free text: `hold`, `weak_strength`, `expected_return_unavailable`, `expected_return_invalid`, `unsupported_signal`, `negative_fee_adjusted_edge`, `fee_adjusted_edge_passed`, or `policy_exempt`. Human detail belongs in a separate bounded `reason` string.
- Cost components are finite fractions in `[0, 1]`; negative values are invalid in the new schema (the current helper clamps them to zero). The required edge is their non-negative sum, and an overflow or non-finite sum fails closed.

The proposed API must add or document:

- `unit: fraction` and a separate display conversion, never implicit percent conversion;
- `forecast_horizon` with an explicit unit and nullable value until defined;
- `return_basis: gross|net` and `source`/`model_version`;
- the canonical bounds and exact boundary behavior above;
- `expected_return_available`, where false is distinct from numeric zero.

`win_probability` and `confidence` are active action inputs only for ML order-book paths. For non-ML strategies their absence/default is not evidence of confidence.

### 5.3 Cost hurdle

The current hurdle is:

```text
required_edge_fraction = max(0, round_trip_fee_fraction)
                       + max(0, spread_fraction)
                       + max(0, slippage_buffer_fraction)
fee_adjusted_edge_fraction = directional_edge_fraction - required_edge_fraction
```

`evaluateOrderBookProfitabilityGate` and `evaluateStrategyProfitabilityDiagnostic` implement this at `StrategySignal.cpp:305-400`. The gate is strict: `net > 0` passes; equality fails. Fees are explicitly round-trip in the input name. The source does not fully define whether spread and slippage are one-way or round-trip, observed or buffered, so implementation must specify those bases before changing the contract. Negative cost inputs are clamped to zero today; non-finite cost inputs must fail closed in the proposed implementation rather than silently becoming zero. Pending the Section 10 decision, the interim live rule is fail-closed for unavailable, invalid, or contradictory required diagnostics; ordinary simulation may report the discrepancy but must not treat unavailable as zero edge.

### 5.4 Availability and factors

Current unavailable serialization is documented in `docs/reports/non-orderbook-diagnostics-closeout-2026-08-05.md:24-42`: numeric placeholders may be `0.0`, but `expected_return_available:false`, `diagnostics_available:false`, `profitability_gate_passed:false`, `diagnostic_factor:expected_return_unavailable`, and `factoring_semantics:unavailable` carry the meaning. Frontend normalization must render “Unavailable,” never “0%” or “profitable.”

Current machine-readable factors are `hold`, `weak_strength`, `expected_return_unavailable`, `unsupported_signal`, `negative_fee_adjusted_edge`, and `fee_adjusted_edge_passed` (`StrategySignal.cpp:351-399`). Preserve the factor and a human reason; add a stable `gate_reason` enum rather than requiring consumers to parse prose.

## 6. Decision roles and fail-closed behavior

### Entry and adds

- Order-book and ML order-book entry: signal, required strength, diagnostic availability, directional/cost gate, ML gate, account readiness, pending-order and position limits, price/size/minimum-notional, cash, spot-side, and explicit execution enablement all apply. Any required unknown or invalid value blocks.
- Indicator entry: current signal can be generated, but proposed live authority blocks if the configured policy requires expected edge and it is unavailable. The current service/harness disagreement must be resolved before treating either as normative.
- DCA and buy-and-hold: fixed-size baseline behavior is a deliberate policy decision, not an accidental bypass. If exempted from expectancy gating, label the path `benchmark_allocation`, report costs and realized outcomes, and retain all account, size, cash, and execution blockers. Exemption must not authorize arbitrary indicator signals.
- Adds require a declared policy: reuse entry diagnostics, require fresh diagnostics, or permit only DCA's scheduled allocation. Never infer an add decision from a stale initial-entry prediction.

### Exits

Stop-loss/take-profit, opposite-signal, age-out, explicit close, and account liquidation are active exit paths but do not currently recompute expected return. An exit must not be blocked merely because an entry-time diagnostic is unavailable when risk protection requires closing. Persist entry-time diagnostics for attribution and attach the close reason. Whether exit diagnostics are entry-only, exit-only, or both is unresolved and must be selected in the API version.

### Blocker precedence

Live blocker attribution must preserve separate categories and deterministic precedence: no signal/hold; unavailable or failed profitability diagnostic; ML confidence/model readiness; account readiness; existing position/add policy; pending order; max positions; invalid size/price; minimum notional; spot-side restriction; insufficient cash; execution disabled. Ordinary simulation currently conflates some failures as `profitability_or_position_size`; it should adopt the same taxonomy while retaining a `mode` field. A generated but unfilled intent must have exactly one primary blocker and optional secondary diagnostics.

## 7. Proposed API and data model

Additive, versioned fields are preferred for compatibility. The diagnostic object should be namespaceable under the existing `ml_analysis`/execution attribution payload while supporting non-ML strategies:

```json
{
  "schema_version": 1,
  "strategy": "sma",
  "signal": "buy",
  "signal_strength": 0.63,
  "expected_return": null,
  "expected_return_available": false,
  "diagnostics_available": false,
  "unit": "fraction",
  "return_basis": null,
  "forecast_horizon": null,
  "directional_expected_edge": null,
  "round_trip_fee_fraction": 0.015,
  "spread_fraction": 0.001,
  "slippage_buffer_fraction": 0.002,
  "required_edge": 0.018,
  "fee_adjusted_expected_return": null,
  "factoring_semantics": "unavailable",
  "diagnostic_factor": "expected_return_unavailable",
  "profitability_gate_passed": false,
  "profitability_gate_reason": "expected_return_unavailable",
  "source": "strategy_signal",
  "model_version": "strategy-diagnostic-unavailable"
}
```

Schema version 0/current compatibility retains numeric zero placeholders for unavailable serialized fields and the existing `profitability_gate_passed` and `profitability_gate_reason` fields. Schema version 1 may serialize unavailable numeric diagnostics as `null`, but it must retain `expected_return_available:false`, `diagnostics_available:false`, `profitability_gate_passed:false`, and `profitability_gate_reason:"expected_return_unavailable"`. There is no `gate_passed` or unversioned `gate_reason` alias: consumers must use `profitability_gate_passed` and `profitability_gate_reason`; any future rename requires an explicitly versioned migration. API serializers in `src/api/PredictController.cpp` and frontend types in `frontend/types/trading.ts:94-108` must preserve these flags and type numeric fields as nullable in schema version 1. The frontend must use nullish handling (`??`) and never use zero as a missing-value fallback.

Required model additions include a stable strategy enum/validation result, mode (`live|simulated|live_parity`), primary blocker code, blocker precedence, diagnostic source/model version, cost bases, and entry/exit/add attribution timestamps. Do not silently rename existing fields; add aliases or versioned fields and document migration.

## 8. Implementation guidance and terminology mapping

| Contract term | Current code/data | Required interpretation |
|---|---|---|
| signal | `StrategySignalOutcome.signal_type`; frontend `OrderBookSignal.signal` | `buy`, `sell`, or non-actionable `hold` |
| strength | `StrategySignalOutcome.strength`; `signal_strength` | finite fraction in `[0,1]` |
| expected return | `expected_return_fraction`; serialized `expected_return` | fractional forecast with explicit availability and horizon |
| directional edge | `directional_expected_edge_fraction` | buy keeps return sign; sell negates it |
| required edge | `required_edge_fraction` / `required_edge` | non-negative fee + spread + slippage hurdle |
| fee-adjusted return | `fee_adjusted_expected_return_fraction` | directional edge minus hurdle; strict positive gate |
| factor | `StrategyProfitabilityDiagnostic.factor`; `diagnostic_factor` | stable enum, not prose parsing |
| factoring semantics | `factoring_semantics` | `gate`, `size`, `exit`, `report`, or `unavailable` |
| blocker | `blocker_reason`, execution analysis | primary reason an intent did not fill |
| realized PnL | `StrategyExpectancyRow.realized_pnl` and trade stats | net after costs; zero-PnL open legs excluded from win/loss denominators |

The expectancy harness (`include/trading/StrategyExpectancyHarness.hpp:13-76`, `src/trading/StrategyExpectancyHarness.cpp`) is pure evaluation and should be the deterministic regression oracle for the shared diagnostic contract, but its stricter unavailable-edge behavior must be reconciled with production services before being called normative for live authority.

## 9. Testing and verification expectations

Unit and fixture tests must cover all eleven selectable strategies plus unknown configuration, both buy and sell signs, hold/warm-up, zero volatility, no range, insufficient history, non-finite and absent values, negative costs, strict zero-net boundary, and unavailable serialization. Test every matrix row in live, ordinary simulated, and live-parity policy fixtures where applicable.

Cross-mode tests must use identical signals and prove that live and simulation differ only in declared exchange-submission/account effects. Every generated-but-unfilled intent must expose a specific blocker; unavailable must never become negative expectancy or actionability. Test ML classifier/regressor/transformer warm-up, model absence, fallback configuration, and live/sim fallback parity.

Test sizing and minimum-notional decisions, fixed DCA/buy-and-hold allocation, adds, reopen-after-exit, stop-loss/take-profit, age/opposite exits, explicit close, liquidation, and persistence of entry-time diagnostics. Test API/frontend normalization, null handling, strategy/blocker aggregation, and expectancy denominators.

Allowed repository verification for this documentation change is `git diff --check` plus status inspection. Backend/Docker validation is remote-only per repository guidance; implementation changes require the exact pushed SHA to pass GitHub Actions Docker Build Validation, including backend CTest and frontend build checks.

## 10. Unresolved questions requiring explicit approval

1. Should the interim DCA and buy-and-hold `benchmark_allocation` exemption from expected-return gating remain normative, and what horizon/benchmark reports prove that exemption is intentional? Until decided, the exemption applies only to their scheduled/initial allocation; all account, size, cash, and execution blockers remain mandatory, and those rows are excluded from predictive-alpha aggregates.
2. Should all indicator live entries fail closed now, or is a real pre-trade estimator required before enabling them?
3. Is the expectancy harness the normative production oracle or a research comparator?
4. What are the canonical forecast horizon, gross/net basis, finite bounds, and spread/slippage bases? Until decided, the bounds above are proposals and the interim live behavior is fail-closed.
5. Must live and ordinary simulated ML fallback behavior be identical, or are differences part of the declared mode contract?
6. Do adds require fresh diagnostics, and which diagnostics may authorize a DCA add?
7. Is attribution entry-only, exit-only, or both, and how are close reasons represented?
8. Should unknown strategies be rejected at configuration/session start, and how are historical unknown rows migrated?

Until these questions are answered, implementations must preserve explicit unavailable state, avoid silently broadening execution authority, and fail closed for live paths that require the unresolved diagnostic.

## References

- `docs/STRATEGY_OBJECTIVE.md`
- `docs/reports/non-orderbook-diagnostics-closeout-2026-08-05.md`
- `docs/reports/strategy-expectancy-harness-closeout-2026-08-03.md`
- `docs/reports/execution-reconciliation-closeout-2026-08-08.md`
- `include/trading/StrategySignal.hpp`
- `src/trading/StrategySignal.cpp`
- `include/trading/StrategyExpectancyHarness.hpp`
- `src/trading/StrategyExpectancyHarness.cpp`
- `frontend/components/dashboard/StrategySelector.tsx`
- `frontend/types/trading.ts`
- `src/api/PredictController.cpp`
