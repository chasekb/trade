# Shared Strategy-Diagnostics Factoring Contract

Date: 2026-08-22
Status: design contract for implementation and experiments
Scope: live trading, simulated trading, live-parity paper execution, persisted signal/outcome reconciliation, and dashboard consumers.

## 1. Purpose and non-negotiable safety rules

This document is the shared contract for turning a strategy observation into an expected-return and profitability diagnostic. It is intentionally separate from a strategy-tuning recommendation: no strategy may be called optimized from signal count, throughput, or a green build alone.

The objective is risk-adjusted expectancy after costs: improve average realized win, reduce average realized loss, and improve net expectancy/profit factor without unacceptable drawdown. Live execution remains fail-closed. A missing, malformed, stale, or unit-ambiguous expected-return value must not become an executable live intent.

The contract applies identically to the live service and the simulated service wherever they claim parity. Synthetic simulation may retain short-capable behavior, but its results must be labeled synthetic and must not be used as live Coinbase evidence.

## 2. Canonical diagnostic vocabulary

Every generated signal row should carry these fields under `ml_analysis` (and the same values needed for execution under `execution_analysis`):

| Field | Canonical unit and semantics | Missing/non-finite behavior |
| --- | --- | --- |
| `signal_type` / `intended_side` | `buy`, `sell`, or `hold`; direction is the position-opening or intended action direction | Unknown values are unsupported; do not infer a side. |
| `signal_strength` | dimensionless [0, 1]; magnitude only, never directional | Clamp only values proven to be numeric; otherwise hold/report unavailable. |
| `expected_return` | **fraction of the proposed notional for one complete trade**, before fees, spread, and slippage. Buy-positive and sell-negative convention is required at the public boundary. | `expected_return_available=false`; never treat numeric zero as proof of no risk or as available alpha. |
| `directional_expected_edge` | dimensionless fraction after applying side: buy = `expected_return`; sell = `-expected_return` | Must be finite and side-known before a gate. |
| `required_edge` | dimensionless fraction: round-trip fee + spread + slippage buffer | Each component is clamped at zero; a missing cost configuration uses the documented conservative default, not a negative value. |
| `fee_adjusted_expected_return` | dimensionless fraction: `directional_expected_edge - required_edge` | Unavailable if the expected return is unavailable. A zero or negative value fails a profitability gate. |
| `expected_net_pnl_usd` | USD for the proposed notional: `notional_usd * fee_adjusted_expected_return` | Not an entry substitute for the fractional edge; zero/negative fails a minimum-net-PnL rule unless the explicit unprofitable-trade override is enabled. |
| `win_probability` | dimensionless [0, 1], probability of a favorable directional outcome; for sells a low upward probability is favorable | Missing model output defaults to 0.5 for reporting only and cannot pass a required model gate. |
| `confidence` | dimensionless [0, 1], model confidence, not a probability or expected return | Missing defaults to 0 for sizing/reporting; never promotes a signal. |
| `spread` / `spread_fraction` | `spread` is quote currency; `spread_fraction = spread / mid_price` | Nonpositive/invalid price makes spread-derived diagnostics unavailable and blocks live action. |
| `round_trip_fee_fraction` | dimensionless fraction covering entry and exit fees | Must be explicit in the diagnostic payload. |
| `slippage_buffer_fraction` | dimensionless conservative fraction for both sides of the modeled round trip | Must not be silently omitted in a live gate. |
| `profitability_gate_passed` | boolean result of the edge hurdle, not a model confidence result | Missing is false for live execution. |
| `diagnostic_factor` | stable machine-readable reason/category, e.g. `fee_adjusted_edge_passed`, `negative_fee_adjusted_edge`, `expected_return_unavailable`, `weak_strength`, `hold`, `ml_confidence_gate` | Empty becomes `unknown`; it must not be replaced with an optimistic default. |
| `factoring_semantics` | one of `gate`, `size`, `exit`, `report`, `unavailable`; multiple execution uses are represented by an array in the proposed schema | Missing means `unavailable` for safety-sensitive consumers. |

### Direction and sign rules

- A buy is profitable only when the expected return is positive and exceeds the hurdle.
- A sell is profitable only when the expected return is negative and its negation exceeds the hurdle.
- The canonical formula is:

  `required_edge = max(0, round_trip_fee) + max(0, spread_fraction) + max(0, slippage_buffer)`

  `directional_expected_edge = signal_type == sell ? -expected_return : expected_return`

  `fee_adjusted_expected_return = directional_expected_edge - required_edge`

- `hold` is not a negative trade. It is a non-actionable observation and is `report` only.
- A negative fee-adjusted edge is a valid diagnostic result and a blocking result for an edge-required path; it is not missing data.
- Missing, non-finite, unsupported-side, or unit-ambiguous values are `unavailable`, not zero and not positive edge.
- Expected return is prediction-time data. It must be captured at entry and copied to closing rows; it must never be recomputed from realized PnL (no hindsight leakage).

### Current unit hazard to resolve before implementation

The model paths currently call `predict_pnl`/`predict_transformer` while serializing the result as `expected_return`, whereas gates and `PositionSizingPolicy` consume that field as a fraction. The implementation must choose one canonical boundary (this contract chooses a fraction), explicitly convert model output if it is USD PnL, and expose the source unit/conversion in the payload. No model output may enter a fraction gate until this is resolved and tested.

## 3. Decision-point contract

| Decision point | Required diagnostic use | Current implementation status and rule |
| --- | --- | --- |
| Signal generation | Produce signal type, strength, reason, data sufficiency, and diagnostic availability. Indicator history warm-up is `data_status=insufficient`; a valid-data no-trade is `sufficient`. | Shared `evaluateStrategySignal` covers indicator families. Order-book generation uses signed imbalance and strength threshold. Do not conflate data insufficiency with profitability blocking. |
| Signal strength | Report [0,1] magnitude; may reduce size through the sizing policy, but cannot prove profitability. | Active sizing input for ordinary strategies; order-book strength also participates in the order-book gate. Keep strength and expected edge separate. |
| Profitability gate | Apply directional edge and cost hurdle before a live or live-parity entry intent. | Active for `orderbook` and `ml_enhanced_orderbook`. Missing expected return fails closed. Indicator strategies remain unavailable until a real estimator is added. |
| ML/confidence gate | Apply side-aware confidence: buy requires `win_probability >= threshold`; sell requires `win_probability <= 1-threshold`. A warming or unavailable model fails closed where required. | Active for `ml_enhanced_orderbook`; report blocker separately as `ml_confidence_gate`. Fallback behavior must remain explicitly configured and labeled. |
| Position sizing | Start with configured USD/percent ceiling; diagnostic and risk inputs may reduce it, never increase the user ceiling. Record allocation and all inputs. | `PositionSizingPolicy` uses strength, probability, expected return, confidence, spread, volatility, performance, drawdown, and fees. This is `size` use, but unavailable expected return must not be encoded as a favorable zero. DCA/buy-and-hold fixed amounts intentionally bypass this multiplier. |
| Add-to-position | Apply strategy-specific accumulation rule, pending-order/cash/minimum-notional checks, and any edge/confidence rule applicable to the strategy. | DCA scheduled buys are allocation decisions, not alpha gates; live adds remain buy-only and fail closed. An ordinary strategy must not add solely because a prior position exists. |
| Close/exit | Exits may be caused by opposite signal, age-out, stop loss, take profit, explicit close, or exchange/account reconciliation. Attribute the exact cause. | Stop-loss/take-profit and opposite/age rules are active exits; current profitability diagnostics do not independently choose exits. Never let an unavailable expected return suppress a safety exit. |
| Execution-blocker reporting | Persist `executable_intent`, `blocked`, stable blocker reason, intended side, diagnostic factor, edge fields, allocation, and cost fields. | `execution_analysis` is report-only attribution unless it is the same fail-closed result consumed by the live decision. Separate strategy-quality blockers (`profitability_gate`, `ml_confidence_gate`) from exchange/runtime blockers (`spot_cannot_open_short`, `below_minimum_notional`, `insufficient_cash`, `pending_order`, `live_execution_disabled`, account-management blockers). |
| Outcome reconciliation | Join generated signals to closing outcomes; use net realized PnL after fees, preserve exact-flat closing legs, and expose coverage/unexplained outcomes. | `ExecutionReconciliation` is report-only. `win_rate` is 0-100; average loss in the reconciliation report is a positive magnitude; net expectancy and profit factor use after-fee realized PnL. |

## 4. Live, simulated, and frontend behavior

### Live service

`LiveTradingService` must never submit an order unless all of the following hold: valid market quote; explicit live execution enablement and configured exchange client; known side; required profitability/ML gates; account-management authority; no duplicate pending order; maximum-position limit; positive allocation; Coinbase minimum notional; spot buy-only entry; sufficient available cash after pending reserves and estimated fee. A diagnostic payload is evidence of the same decision, not an alternate authorization path.

Live positions use entry-time prediction fields. Account-inherited holdings remain distinguishable from session-managed quantity. Closing an inherited holding is not strategy PnL, and liquidation is an explicit account action, not a strategy exit. Exact-flat gross closes still count as closing legs and carry fees.

### Simulated service

Synthetic mode may open simulated long or short positions and may retain its existing simulation rules. It must label `trade_type`/mode as synthetic and must not claim live exchange blocker evidence. `live_parity` uses Coinbase public market data and live spot/minimum/cash/position/ML/profitability checks but settles locally; it must never submit Coinbase orders. Its blocker and diagnostic schema must match live.

The local frontend fallback is a separate compatibility producer. It must use the same directional edge convention, fee/spread/slippage units, unavailable semantics, and prediction-time capture. It must not silently invent a positive expected return when backend diagnostics are unavailable.

### API and persisted schema changes required

1. Standardize `expected_return` at the API boundary as a fractional notional return. Add `expected_return_unit: "fraction_of_notional"` and, where model output differs, `source_expected_return_unit` plus an explicit conversion marker.
2. Add `directional_expected_edge` and `expected_net_pnl_usd` to `ml_analysis` and `execution_analysis`; retain existing fields for compatibility during migration.
3. Replace the singular/ambiguous `factoring_semantics` string with `factoring_semantics: string[]` (values from `gate`, `size`, `exit`, `report`, `unavailable`) while accepting the legacy string on read.
4. Add `diagnostics_status` (`active`, `report_only`, `unavailable`) and `diagnostics_version` to signal rows. `expected_return_available=false` is mandatory when unavailable.
5. Persist the diagnostic snapshot with each signal and prediction-time fields with each trade leg. Do not derive entry diagnostics from a closing outcome.
6. Keep `is_closing_leg` nullable for legacy rows; new rows must set it explicitly. Reconciliation must subtract fees from closing gross PnL exactly once.
7. Extend frontend types and table/export labels so users can distinguish unavailable from numeric zero and see units. Numeric fallback code must use nullish coalescing, not truthiness.
8. Preserve `session_id`, `trade_type`, selected universe, and mode filters on both signals and outcomes. A report with clipped signals must state truncation and must not be presented as complete coverage.

## 5. Explicit strategy matrix

Status meanings: `actively-factored` means a diagnostic affects an execution decision (gate, size, or exit) and is also reported; `report-only` means it is emitted/aggregated but does not affect execution; `unavailable` means no trustworthy expected-return diagnostic exists and any path requiring expected edge fails closed.

| Strategy | Live status | Simulated status | Current factoring | Required rationale/acceptance |
| --- | --- | --- | --- | --- |
| `orderbook` | actively-factored | actively-factored; same in `live_parity` | Signed imbalance generates side/strength; heuristic expected return uses the shared directional fee/spread/slippage gate; sizing consumes diagnostic/risk inputs; blockers report separately. | Demonstrate unit conversion, positive buy/negative sell fixtures, hurdle failures, and parity blocker equivalence. |
| `ml_enhanced_orderbook` | actively-factored | actively-factored; same in `live_parity` | Order-book signal plus model probability/expected return; side-aware ML gate, shared profitability gate, and bounded sizing. Transformer warming/model failure is fail-closed where required and visible. | Prove classifier/regressor/transformer output units, fallback policy, warming behavior, and OOS expectancy after costs. |
| `sma` | unavailable (strength may size; signal/exit rules still report) | unavailable (strength may size; synthetic execution is not evidence) | Shared crossover produces [0,1] strength and opposite/age exits, but no trustworthy expected-return estimator. | Do not mark profitability active until an estimator is calibrated and its fee-adjusted edge gates or sizes entries with fixtures and OOS evidence. |
| `ema` | unavailable (strength may size; signal/exit rules still report) | unavailable (strength may size; synthetic execution is not evidence) | Same as SMA. | Same acceptance as SMA. |
| `rsi` | unavailable (threshold signal/strength report; no edge gate) | unavailable (threshold signal/strength report; no edge gate) | Oversold/overbought distance is not expected return. | Add estimator or retain unavailable; never interpret threshold strength as profitability. |
| `bollinger` | unavailable (z-score strength report; no edge gate) | unavailable (z-score strength report; no edge gate) | Band distance is a signal-strength observation only. | Require realized/OOS calibration after costs before active factoring. |
| `macd` | unavailable (crossover strength report; no edge gate) | unavailable (crossover strength report; no edge gate) | MACD crossover distance is not expected return. | Same estimator/calibration requirement. |
| `stochastic` | unavailable (threshold strength report; no edge gate) | unavailable (threshold strength report; no edge gate) | Percent-D threshold distance is not expected return. | Same estimator/calibration requirement. |
| `fibonacci` | unavailable (level proximity strength report; no edge gate) | unavailable (level proximity strength report; no edge gate) | Level selection/proximity is not expected return. | Same estimator/calibration requirement. |
| `dca` | report-only for profitability; allocation schedule actively controls adds | report-only for profitability; allocation schedule actively controls adds | Scheduled buy interval and configured amount are intentional accumulation policy. No alpha claim, confidence multiplier, or expected-edge gate. Live remains buy-only and fail-closed on exchange/account constraints. | Evaluate contribution, fees, drawdown, and opportunity cost against a benchmark; do not optimize raw DCA signal count. |
| `buyandhold` | report-only baseline; allocation actively controls initial buy | report-only baseline; allocation actively controls initial buy | One initial buy then hold. It is a benchmark, not a predictive signal. | Report benchmark total/net return, fees, drawdown, and exposure; do not compare its signal count with active strategies. |

For every `unavailable` strategy, a generated signal may still be persisted for observability and may follow the existing strategy behavior in synthetic mode, but any implementation that requires a positive expected edge must fail closed. This distinction must be visible in `diagnostics_status` and not hidden behind `expected_return: 0`.

## 6. Acceptance rules for implementers and experiments

### Contract and unit tests

- Buy with +3% expected return and a 1.7% hurdle yields +1.3% fee-adjusted edge and can pass strength/cash/exchange gates.
- Sell with -3% expected return and a 1.7% hurdle yields +1.3% directional edge and can pass; sell with +3% fails.
- Either side with edge equal to or below the hurdle fails profitability.
- Missing, NaN, infinity, unsupported side, or unknown unit yields `unavailable`, `profitability_gate_passed=false`, and no live intent.
- Zero expected return is distinguishable from unavailable; it is an available but non-profitable estimate only when the producer explicitly sets availability true.
- Fees, spread, and slippage are subtracted once in the diagnostic; realized closing PnL subtracts persisted closing fees once in reconciliation.
- Exact-flat gross closing legs remain in closing-leg coverage and can be net losers when fees are nonzero.
- Entry prediction fields on exits equal the captured entry snapshot, not outcome-derived values.
- Synthetic short fixtures are labeled synthetic and excluded from live-parity conclusions.

### Runtime/evidence rules

Every strategy change must report, by strategy and selected symbol universe: evaluated/generated signals, strength distribution, expected-return availability and buckets, fee-adjusted edge, gate pass rate, executable intents, blocker counts, fills, average win, average loss, net expectancy, profit factor, fees, drawdown, and unexplained/outcome coverage. Compare against a fixed pre-change window or fixture and state whether evidence is synthetic, live-parity, backtest, or live-account derived.

No implementation may close its work item on green CI alone when runtime/calibration evidence is required. Live claims require explicit approval, no unapproved orders, and preserved fail-closed behavior. Remote CI must verify the exact pushed SHA; prohibited local Docker/CMake/backend builds are not substituted with plausible output.

## 7. Source map

- Shared signal and diagnostic helpers: `include/trading/StrategySignal.hpp`, `src/trading/StrategySignal.cpp`
- Live signal, sizing, gates, exits, and blocker analysis: `include/trading/LiveTradingService.hpp`, `src/trading/LiveTradingService.cpp`
- Simulated/synthetic/live-parity equivalents: `include/trading/SimulatedTradingService.hpp`, `src/trading/SimulatedTradingService.cpp`
- Sizing and minimum-net-PnL policy: `include/trading/PositionSizingPolicy.hpp`, `src/trading/PositionSizingPolicy.cpp`
- Signal/outcome attribution and metrics: `include/trading/ExecutionReconciliation.hpp`, `src/trading/ExecutionReconciliation.cpp`, `src/api/PredictController.cpp`
- Backend stats conventions: `src/trading/TradingStatsCalculator.cpp`
- Frontend signal contract and local fallback: `frontend/types/trading.ts`, `frontend/lib/api.ts`
- Objective and existing diagnostic history: `docs/STRATEGY_OBJECTIVE.md`, `docs/reports/non-orderbook-diagnostics-closeout-2026-08-05.md`, `docs/reports/trade-strategy-objective-review-2026-08-01.md`
