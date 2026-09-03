# Trade Strategy Objective Alignment Review — 2026-08-01

## Scope

This report closes the review-only implementation slice for `TRADE-BL-0010`: code review every live and simulated trading strategy for alignment with the project objective in `docs/STRATEGY_OBJECTIVE.md`.

No live orders were placed. No local Docker, CMake, backend, or production build was run. The closeout gate for this report remains exact-SHA GitHub Actions Docker Build Validation after push.

## Objective used for review

The project objective is to maximize risk-adjusted expectancy in the live trading environment: increase average realized win and minimize average realized loss after fees, spread, slippage, and live execution blockers. Raw signal count or trade count is not a goal unless added executions improve net expectancy without unacceptable drawdown.

## Strategy inventory and code paths

Frontend strategy selection is exposed by `frontend/components/dashboard/StrategySelector.tsx:11-22`:

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

Shared indicator strategy parameters are defined in `include/trading/StrategySignal.hpp:12-37`. The shared indicator evaluator is declared in `include/trading/StrategySignal.hpp:84-93` and implemented in `src/trading/StrategySignal.cpp:113-303`.

Simulated strategy signal generation calls the shared evaluator for non-order-book strategies at `src/trading/SimulatedTradingService.cpp:968-990`. Live strategy signal generation calls the same evaluator for non-order-book strategies at `src/trading/LiveTradingService.cpp:1496-1518`.

Order-book strategies are handled separately in both services:

- simulated order-book signal construction and profitability gate: `src/trading/SimulatedTradingService.cpp:974-977`, `src/trading/SimulatedTradingService.cpp:1130-1167`
- live order-book signal construction and live execution loop: `src/trading/LiveTradingService.cpp:1502-1505`, `src/trading/LiveTradingService.cpp:2040-2113`

The shared profitability diagnostic contract is declared in `include/trading/StrategySignal.hpp:63-103` and implemented in `src/trading/StrategySignal.cpp:344-399`.

## Per-strategy classification

| Strategy | Signal/strength source | Live/sim execution alignment | Objective alignment classification | Finding |
| --- | --- | --- | --- | --- |
| `ml_enhanced_orderbook` | Order-book imbalance plus ML/heuristic expected-return diagnostics | Live and simulated both use order-book branches and the shared directional fee/spread/slippage profitability gate | Optimized but still needs runtime parity evidence | This is the strongest objective-aligned path: expected edge is directional, fee-adjusted, gated, and visible. Existing backlog items `TRADE-BL-0005`, `TRADE-BL-0021`, and `TRADE-BL-0008` remain the right follow-up tracks for parity and tuning evidence. |
| `orderbook` | Order-book imbalance with heuristic expected return | Live and simulated both use order-book branches and the same gate helper | Optimized enough for gate semantics; needs calibration evidence | The strategy has fee-adjusted gate semantics, but the default heuristic edge scale still requires outcome-backed calibration against average win/loss and blocker rates. Covered by `TRADE-BL-0008` and `TRADE-BL-0013`. |
| `sma` | Fast/slow moving-average gap, strength from normalized gap | Live and simulated share the same evaluator | Needs calibration | Strength can be high when moving averages diverge, but no expected-return diagnostic is produced or factored into entry/exit decisions. Covered by `TRADE-BL-0013`, `TRADE-BL-0016`, and `TRADE-BL-0011`. |
| `ema` | Fast/slow EMA gap, strength from normalized gap | Live and simulated share the same evaluator | Needs calibration | Same issue as SMA; crossover strength is not proven to correlate with net expectancy after fees/spread/slippage. |
| `rsi` | Oversold/overbought threshold distance | Live and simulated share the same evaluator | Needs calibration | RSI can produce buy/sell signals, but expected-return and fee-adjusted diagnostics are unavailable in the signal path. |
| `bollinger` | Z-score outside bands | Live and simulated share the same evaluator | Needs calibration | Band distance is treated as strength without realized expectancy evidence or spread/fee gating. |
| `macd` | MACD line versus signal line crossover | Live and simulated share the same evaluator | Needs calibration | Crossover strength is technical-distance based, not profitability based. |
| `stochastic` | Percent-D overbought/oversold threshold distance | Live and simulated share the same evaluator | Needs calibration | Like RSI, threshold distance is not enough evidence that average win improves or average loss shrinks after costs. |
| `fibonacci` | Price proximity to retracement/resistance levels | Live and simulated share the same evaluator | Diagnostics-unavailable / needs calibration | Strength follows the Fibonacci level selected, not measured expectancy. |
| `dca` | Scheduled buy interval | Live and simulated share the same evaluator; live spot entries are buy-only and fail closed on account/order checks | Intentionally ungated accumulation | DCA intentionally optimizes accumulation cadence rather than per-signal expectancy. It should be reviewed separately as an allocation/risk-budget strategy, not as a signal-strength strategy. |
| `buyandhold` | One initial buy, then hold | Live and simulated share the same evaluator; live spot entries are buy-only and fail closed on account/order checks | Intentionally ungated baseline | Buy-and-hold is a baseline/allocation strategy. Objective evidence should be reported as benchmark performance versus active strategies, not as a signal-count optimization. |

## Execution-path observations

### Shared indicator evaluator

`src/trading/StrategySignal.cpp:120-141` handles `buyandhold` and `dca` as accumulation strategies. `src/trading/StrategySignal.cpp:148-299` handles indicator/crossover strategies. These strategies return `buy`, `sell`, or `hold` plus a 0..1 strength and reason, but they do not currently attach expected-return, fee-adjusted expected-return, required edge, or diagnostic-factor classifications to the generated signal.

### Live execution safety

Live entries remain spot-only. `src/trading/LiveTradingService.cpp:1837-1841` rejects non-buy entries, so indicator sell signals cannot open synthetic shorts in live Coinbase spot accounts. Live execution also checks Coinbase minimum quote size, cash, pending symbols, explicit live-order enablement, and max positions in `src/trading/LiveTradingService.cpp:1805-1862`.

For existing live positions, live strategy management can close on opposite signal or age-out in `src/trading/LiveTradingService.cpp:2099-2111`. For DCA, live adds are isolated to scheduled buy signals in `src/trading/LiveTradingService.cpp:2090-2096`.

### Simulated execution semantics

Simulated entries can use the sanitized signal side in `src/trading/SimulatedTradingService.cpp:1292-1314`, including sell-side simulated entries when live order execution is not the active Coinbase path. That is acceptable for synthetic simulation only if dashboards and reports clearly avoid treating synthetic shorts as live-parity evidence. `TRADE-BL-0006` remains the required follow-up for a live-parity paper mode that applies live spot constraints without submitting Coinbase orders.

### Order-book profitability gate

The order-book gate is directionally correct: buys use positive expected return and sells use negative expected return as favorable edge (`src/trading/StrategySignal.cpp:311-317`). The gate subtracts fees, spread, and slippage (`src/trading/StrategySignal.cpp:308-310`) and fails closed when net edge is non-positive (`src/trading/StrategySignal.cpp:330-337`).

### General strategy diagnostic helper

`evaluateStrategyProfitabilityDiagnostic` in `src/trading/StrategySignal.cpp:344-399` can classify generic strategy diagnostics as hold, weak strength, expected-return unavailable, negative fee-adjusted edge, or fee-adjusted edge passed. The review found this helper is not yet wired into the indicator-family entry/exit decisions, so non-order-book strategies remain diagnostic-unavailable rather than fully objective-factored.

## Actionable findings mapped to backlog

1. Indicator/crossover strategy strength is not calibrated to realized expectancy.
   - Affected strategies: `sma`, `ema`, `rsi`, `bollinger`, `macd`, `stochastic`, `fibonacci`.
   - Existing backlog coverage: `TRADE-BL-0013` and `TRADE-BL-0011`.
   - Expected objective impact: reduce average loss and avoid high-strength/negative-expectancy entries.

2. Non-order-book strategies do not factor expected-return/profitability diagnostics into gates, sizing, or exits.
   - Affected strategies: all indicator strategies plus accumulation baselines where diagnostics are intentionally absent.
   - Existing backlog coverage: `TRADE-BL-0012`, `TRADE-BL-0016`, and `TRADE-BL-0011`.
   - Expected objective impact: make missing diagnostics visible and fail safe where expected edge is required.

3. Synthetic simulated sell entries are not live-parity evidence for Coinbase spot behavior.
   - Affected path: simulated non-live-parity execution in `src/trading/SimulatedTradingService.cpp:1275-1314`.
   - Existing backlog coverage: `TRADE-BL-0006`.
   - Expected objective impact: prevent synthetic short behavior from being mistaken for live-account expectancy.

4. DCA and buy-and-hold should be reported as accumulation/baseline strategies, not signal-strength-optimized strategies.
   - Existing backlog coverage: `TRADE-BL-0011` for evaluation harness output and `TRADE-BL-0002` for training/optimization planning.
   - Expected objective impact: compare active strategies against baseline allocation performance without inflating signal-count objectives.

5. Order-book strategies are currently the only strategies with directional fee-adjusted expected-return gate semantics.
   - Existing backlog coverage: `TRADE-BL-0005`, `TRADE-BL-0008`, `TRADE-BL-0021`.
   - Expected objective impact: preserve order-book expectancy gates while improving parity and measured throughput.

No new backlog IDs are required by this review because each actionable finding maps to existing open trade backlog items with execution and closeout criteria. Future implementation should not close those items without fixture/runtime evidence and exact-SHA CI.

## Classification summary

- Optimized / objective-factored now: `ml_enhanced_orderbook`, `orderbook` gate semantics.
- Needs calibration: `sma`, `ema`, `rsi`, `bollinger`, `macd`, `stochastic`, `fibonacci`.
- Diagnostics unavailable / intentionally ungated: `buyandhold`, `dca`.
- Requires live-parity separation before live claims: synthetic simulated sell/short behavior.

## Closeout notes for TRADE-BL-0010

This report satisfies the review portion of `TRADE-BL-0010` by inventorying every strategy, tracing live and simulated signal/execution paths, classifying objective alignment, and mapping actionable findings to existing backlog items. It does not implement calibration, harnesses, or live-parity paper execution; those remain intentionally open under their respective backlog IDs.
