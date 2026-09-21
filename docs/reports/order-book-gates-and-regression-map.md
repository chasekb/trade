# Order-book gates and regression map

Status: read-only design note; no behavior change.

## Scope

The live and simulated order-book paths are implemented separately, but both call the same pure profitability gate in `StrategySignal.cpp`. The safe evaluation seam is therefore the existing pure structs/functions, not a new gate embedded in either service.

## Signal flow

1. `LiveTradingService::workerLoop()` fetches Coinbase quotes, applies account snapshots, then calls `generateTickLocked()` (`src/trading/LiveTradingService.cpp:2309-2403`). Missing quotes are fail-closed: `generateTickLocked()` skips the symbol (`2241-2244`).
2. `SimulatedTradingService::workerLoop()` fetches quotes only for `live`/`live_parity`; synthetic mode passes an empty quote map into `generateTickLocked()` (`src/trading/SimulatedTradingService.cpp:1732-1830`, `1832-1907`). Live-data modes also skip symbols with no valid quote (`1748-1751`).
3. `buildSignalRecordLocked()` in both services consumes `MarketQuote` fields (`mid`, `spread`, `imbalance`, volume/depth). Order-book strategies (`orderbook`, `ml_enhanced_orderbook`) compute `strength = min(1, abs(imbalance) * 1.15)` and initially generate when `strength >= 0.22` (Live `1553-1556`; simulated `1114-1117`). Direction is the sign of imbalance: positive is buy, negative is sell.
4. The payload records raw market data, criteria analysis, model/fallback metadata, and `ml_analysis`. The pure gate is called only when an order-book signal was initially generated (Live `1733-1752`; simulated `1318-1337`). A failed gate rewrites the signal to `hold`, strength `0`, prediction `HOLD`, and preserves the gate reason (Live `1757-1769`; simulated `1342-1354`).
5. Live attaches `buildEntryExecutionAnalysisLocked()` before persistence and only opens when `executable_intent` is true (`Live 1835-1930`, `2226-2306`). Simulated attaches `buildExecutionAnalysisLocked()` and, in `live_parity`, applies the same spot/minimum/cash checks while retaining paper settlement (`Simulated 518-601`, `1753-1795`). Synthetic simulation intentionally remains short-capable; live and live-parity reject opening sells as `spot_cannot_open_short` (Live `1911-1913`; simulated `575-587`).

## Tunable inputs and ownership

| Input | Current key/default | Enforcement and notes |
|---|---|---|
| Minimum order-book strength | `min_orderbook_signal_strength`, default `0.22` (`StrategySignal.hpp:46-54`, service constants at Live `39-41`, simulated `35-37`) | The initial activity threshold is hard-coded `0.22` in each service (`Live 1554-1556`; simulated `1114-1117`). The configurable minimum is applied later by `evaluateOrderBookProfitabilityGate()` (`StrategySignal.cpp:323-328`). These can diverge: changing the parameter does not change initial signal generation, only the profitability gate. |
| Expected-return scale | `orderbook_expected_return_scale_percent`, default `2.4%`, clamped to `0..5%` | Heuristic fallback computes `expected_return = imbalance * scale` (Live `1686-1702`; simulated `1271-1287`). Model paths use regressor output, or transformer output when no regressor exists (Live `1659-1679`; simulated `1233-1263`). |
| Round-trip fees | `round_trip_fee_percent`, default `1.5%` for order-book gate | Converted to a fraction at gate construction (Live `1740-1743`; simulated `1325-1328`). Separately, position sizing uses a different default of `0.16%` (`Live 409-479`; simulated `471-480`) and fill accounting uses `kFeeRate = 0.05%` per leg (`Live 38`; simulated `34`). These are distinct contracts and should not be silently unified. |
| Slippage buffer | `slippage_buffer_percent`, default `0.2%` for order-book gate | Converted at Live `1744-1747` and simulated `1329-1332`; summed as a non-negative hurdle by `StrategySignal.cpp:308-310`. Minimum-trade sizing reads the same key but defaults to `0` (`Live 474-477`; simulated `476-478`). |
| Spread | Observed `signal.spread / mid_price` | Live comes from Coinbase `MarketQuote` (`buildSignalRecordLocked`); simulated synthetic spread is `mid * (0.0004..0.0007)` (`Simulated 1098-1100`). The gate always adds non-negative spread fraction (`StrategySignal.cpp:308-310`). |
| Imbalance weighting | `abs(imbalance) * 1.15` for strength; payload composition reports imbalance at 60% importance, spread 25%, volume 15% | The 1.15 multiplier and the payload importance labels are service-local heuristics, not learned weights (`Live 1553-1556`, `1782-1794`; simulated `1114-1117`, `1367-1379`). No separate imbalance-weight parameter exists. |
| Position sizing | `position_size_percent` (default 1%), `position_size_mode` (`percent`/`dollar`), `position_size_value`; plus `max_positions`, minimum net PnL, and sizing policy inputs | Both services assemble `PositionSizingInputs` and call `calculate_position_size_usd()` (Live `409-479`; simulated `396-486`). The policy reduces size using strength, win probability, expected return, confidence, spread, volatility, live/cohort performance and fees, while never exceeding the configured base (`PositionSizingPolicy.cpp:36-83`). Simulated additionally calls `minimum_trade_size_decision()` with expected-return, fee, slippage, spread, `minimum_net_pnl_usd`, and `allow_unprofitable_trades` (`Simulated 470-486`); Live currently returns the sizing-policy result directly (`Live 479`). |
| ML confidence/fallback | `confidence_threshold` default `0.6`; `fallback_to_baseline` default true | Applies only to `ml_enhanced_orderbook` after profitability gating. Buy requires `win_probability >= threshold`; sell requires `<= 1-threshold` (Live `1805-1832`; simulated `1390-1420`). Live and simulated differ when transformer inference is warming: simulated explicitly blocks `transformer-warming-up` (`1397-1400`), while Live has no corresponding branch. |
| Capacity/execution gates | `max_positions` / `max_positions_per_session`, exchange minimum, cash, pending orders, account-management mode, live execution flag | Applied in execution-analysis/open paths, after the signal gate. Live adds account-managed holding and Coinbase spot checks (`Live 1871-1929`); simulated adds `live_parity` equivalents and otherwise paper/synthetic behavior (`Simulated 544-601`). |

## Directional fee/spread/slippage semantics

`evaluateOrderBookProfitabilityGate()` computes:

- `required_edge = max(0, round_trip_fee) + max(0, spread) + max(0, slippage)` (`StrategySignal.cpp:305-310`).
- Buy expected edge is `expected_return`; sell expected edge is `-expected_return` (`312-317`). Thus a negative expected return is favorable only for a sell.
- Hold returns blocked without evaluating strength (`319-321`).
- Strength below minimum blocks (`323-328`).
- Net edge must be strictly positive; zero is blocked (`330-337`).

`evaluateStrategyProfitabilityDiagnostic()` has the same directional conversion and strict-positive hurdle, but first fails closed when expected return is unavailable/non-finite (`StrategySignal.cpp:344-399`). It is currently used for non-order-book strategy diagnostics, not as the order-book gate.

The separate `PositionSizingPolicy` repeats the fee/spread/slippage sum in `expected_net_pnl_usd()` and `minimum_trade_size_decision()` (`PositionSizingPolicy.cpp:86-133`). This duplication is a risk for parameter drift, especially because Live does not call the minimum-trade decision while simulated does.

## Existing regression coverage

`src/tests/test_strategy_signal.cpp` is a pure-function test target (`CMakeLists.txt:151-156`) and proves:

- favorable buy edge passes and positive net edge is reported (`185-199`);
- fee-negative, exactly fee-neutral, and negative buy edge are blocked (`200-213`);
- favorable sell uses negative expected return (`215-217`);
- old 1.2% fallback scale remains below the default hurdle, while 2.4% clears it for a strong signal (`219-233`);
- weak strength blocks and strong negative sell edge passes (`235-243`);
- strategy-neutral diagnostics fail closed when expected return is unavailable, identify weak strength/negative edge, and preserve directional sell semantics (`138-183`).

`src/tests/test_position_sizing_policy.cpp` is a separate CMake target (`CMakeLists.txt:138-143`) and proves weak setups reduce size, strong setups remain within the configured cap, fee/spread/slippage can block a minimum-net-PnL decision, and the explicit `allow_unprofitable_trades` override is honored (`90-126`).

`src/tests/test_strategy_expectancy_harness.cpp` and `src/tests/test_execution_reconciliation.cpp` cover attribution/reconciliation of blocked intents and realized outcomes, but do not exercise either service's private `buildSignalRecordLocked()` or execution-analysis methods. There is therefore no direct regression test for parameter parsing, live-vs-simulated service parity, or the initial hard-coded `0.22` threshold.

## Smallest safe extension points

1. Keep `evaluateOrderBookProfitabilityGate()` as the single pure gate seam. Add a pure, non-mutating “gate snapshot”/diagnostic helper only if parameter sweeps need structured inputs and outputs; do not duplicate directional arithmetic in either service.
2. Extract a shared order-book configuration builder for defaults, finite/clamped values, and fraction conversion. This is the smallest way to prevent Live/simulated drift while preserving current defaults. Treat the initial activity threshold as a separate explicit field if it is intended to become tunable; otherwise document that `min_orderbook_signal_strength` is a post-generation gate.
3. For instrumentation, extend the existing `ml_analysis`/`execution_analysis` payloads with raw inputs and derived values: signal strength, configured minimum, expected edge, directional edge, required fee/spread/slippage components, net edge, and the first blocking factor. Preserve existing keys and reasons for compatibility.
4. Add a pure parameter-evaluation matrix test around `StrategySignal` for buy/sell, strength boundary, zero edge, negative costs, non-finite expected return, and independent fee/spread/slippage perturbations. Add a sizing-policy test that explicitly records the Live-vs-simulated minimum-trade-size difference before changing it.
5. If service-level coverage becomes necessary, extract signal construction/gating from the private services into a small shared producer object with injected market quote and model outputs. Avoid tests that require Coinbase, Postgres, or a worker thread merely to prove pure gate semantics.

## Explicit risks

- The gate's `round_trip_fee_fraction` default (1.5%) differs from fill accounting (0.05% per leg), sizing's default (0.16%), and the slippage default in sizing (0%). Changing one can change trade eligibility without changing realized accounting.
- The service initial threshold is hard-coded while the gate threshold is configurable; parameter sweeps can appear ineffective near the initial threshold.
- The same order-book construction and gate logic is duplicated in Live and Simulated services. A one-sided fix can break live/parity equivalence.
- Simulated synthetic imbalance is deliberately predictive (`AR(1)` persistence and impact), whereas live imbalance is an instantaneous Coinbase snapshot; positive simulated expectancy is not evidence of live edge.
- Live spot cannot open shorts, so a gate-passing sell may still be blocked by execution policy. Do not classify that as a profitability failure.
- Model fallback/warm-up behavior differs between services, and model expected PnL is not guaranteed to be in the same units as the fractional fee/spread hurdle. Any calibration or parameter evaluation must validate units before changing behavior.
- Position sizing reads cached live/cohort performance and may vary with runtime history. Parameter evaluation should isolate sizing policy inputs and report the source snapshot rather than treating size as a deterministic function of signal alone.
