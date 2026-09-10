# Cross-Strategy Diagnostic Decision-Path Inventory

Date: 2026-08-22
Scope: `StrategySignal`, `PositionSizingPolicy`, `LiveTradingService`, `SimulatedTradingService`, and `StrategyExpectancyHarness`.

This is a source-level inventory, not runtime evidence. “Actively factored” means the value can change whether an intent is generated, gated, sized, opened, added, or closed. “Report-only” means the value is serialized or counted but does not change the action. “Unavailable” means the path explicitly cannot produce a diagnostic and fails closed where an action would otherwise depend on it.

## Contract vocabulary observed in source

- Signal type is `buy`, `sell`, or `hold`; strength is intended to be in `[0, 1]` (`include/trading/StrategySignal.hpp:40-44`).
- `evaluateStrategyProfitabilityDiagnostic` computes the hurdle as round-trip fees + spread + slippage, but only makes an action actionable when an expected return is available and the directional edge exceeds that hurdle (`src/trading/StrategySignal.cpp:344-399`).
- Order-book profitability uses the same cost hurdle and additionally enforces minimum strength (`src/trading/StrategySignal.cpp:305-341`). For a sell, the directional edge is `-expected_return`; expected-return sign convention must therefore be explicit in the cross-strategy contract.
- `PositionSizingPolicy` combines signal strength, win probability, model confidence, expected return, spread, volatility, live performance, and cohort performance to reduce or increase a multiplier (`src/trading/PositionSizingPolicy.cpp:36-75`). The final position-size helper caps the result at the configured base amount (`:78-84`).
- Minimum-trade sizing can fail closed on non-positive edge or insufficient expected net PnL unless `allow_unprofitable_trades` is true (`src/trading/PositionSizingPolicy.cpp:94-133`). The service paths do not use this helper uniformly: simulated sizing does, while the live service uses the multiplier path.

## Strategy signal generation matrix

| Strategy | Signal producer and decision | Strength / diagnostic inputs | Current profitability and ML behavior | Fail-open / fail-closed notes |
|---|---|---|---|---|
| `orderbook` | `buildSignalRecordLocked` in both services derives strength from `abs(imbalance) * 1.15`, generates at `>= 0.22`, and maps imbalance sign to buy/sell (`SimulatedTradingService.cpp:1108-1129`; `LiveTradingService.cpp:1547-1569`). | Imbalance, spread, volume, depth, momentum; heuristic expected return is `imbalance * configured scale` (`SimulatedTradingService.cpp:1271-1287`; live equivalent `:1686-1702`). | **Actively factored.** `evaluateOrderBookProfitabilityGate` is applied to generated signals; fee/spread/slippage hurdle and minimum strength can turn the signal into HOLD (`SimulatedTradingService.cpp:1318-1354`; `LiveTradingService.cpp:1733-1770`). Position sizing then also consumes expected return/confidence/spread. | Missing/failed model falls back to a labeled heuristic and remains eligible for the order-book profitability gate. Non-positive fee-adjusted edge fails closed by converting to HOLD. |
| `ml_enhanced_orderbook` | Same order-book signal producer as `orderbook`; model inference is added after signal generation. | Classifier win probability, regressor/transformer expected PnL, confidence derived from `abs(win_probability - 0.5) * 2`, spread and order-book features (`SimulatedTradingService.cpp:1205-1267`; live `:1637-1684`). | **Actively factored in two gates.** The order-book profitability gate runs before the ML gate. `signalPassesMlGateLocked` requires buy probability >= threshold or sell probability <= `1-threshold` (`SimulatedTradingService.cpp:1390-1420`; live `:1805-1832`). | Simulated transformer warming-up fails closed. Heuristic fallback honors `fallback_to_baseline` (default true), so it can fail open to baseline. Inference exceptions fall back to heuristic. This is an intentional but unresolved policy difference from unavailable expected-return diagnostics in indicator strategies. |
| `sma` | `evaluateStrategySignal` compares short and long moving averages; generates crossover signal after `long_window + 1` history (`StrategySignal.cpp:148-160`). | Crossover strength is `0.3 + abs(gap)/price*200`, clamped; no model expected return is produced by this strategy. | **Unavailable for action.** Service emits `expected_return_available=false`, invokes the diagnostic only to serialize factor/reason/hurdle, and labels `factoring_semantics` as `report` for HOLD or `unavailable` otherwise (`SimulatedTradingService.cpp:1288-1315`; live `:1703-1730`). | Warm-up holds fail closed for signal generation. Once a crossover exists, lack of expected return is not a profitability gate in the service tick; sizing receives default expected return 0 and may still produce a positive size. This is a major contract gap. |
| `ema` | Same shape as SMA using EMA windows (`StrategySignal.cpp:148-160`). | Same crossover strength; no expected-return producer. | **Unavailable/report-only** as for SMA. | Same gap: a generated signal can proceed through the normal simulated path despite unavailable profitability evidence; live path additionally requires execution/order gates. |
| `rsi` | RSI oversold generates buy; overbought generates sell; neutral otherwise (`StrategySignal.cpp:162-180`). Requires `window + 1` prices. | Strength reflects distance beyond threshold; no expected-return producer. | **Unavailable/report-only** in both service producers. ML gate is bypassed because it only applies to `ml_enhanced_orderbook`; position sizing sees default ML values. | Warm-up is fail-closed. Threshold crossings are action signals without fee-adjusted expectancy gating. |
| `bollinger` | Z-score against rolling mean/stddev; outside configured bands generates buy/sell (`StrategySignal.cpp:183-206`). Zero volatility is HOLD. | Strength is `abs(z)/3`, clamped; no expected-return producer. | **Unavailable/report-only.** | Insufficient history and zero volatility fail closed to HOLD. A valid band signal is not blocked when expected-return diagnostic is unavailable. |
| `macd` | MACD line/signal-line crossover after slow + signal history (`StrategySignal.cpp:209-225`). | Crossover strength; no expected-return producer. | **Unavailable/report-only.** | Warm-up fail-closed; generated crossover can reach normal entry path without actionable profitability evidence. |
| `stochastic` | Smoothed %D oversold/overbought thresholds generate buy/sell (`StrategySignal.cpp:228-264`). | Threshold-distance strength; no expected-return producer. | **Unavailable/report-only.** | Warm-up fail-closed; no profitability gate for valid signals. |
| `fibonacci` | Recent high/low retracement proximity generates buy in uptrend or sell in downtrend (`StrategySignal.cpp:267-299`). | Strength from retracement level; no expected-return producer. | **Unavailable/report-only.** | Warm-up/no-range/between-levels hold. Valid level signal has no actionable expectancy diagnostic. |
| `dca` | Emits buy on first entry or after configured interval; otherwise hold (`StrategySignal.cpp:131-141`). | Strength always 1.0 on scheduled buy; no expected-return producer. | **Unavailable/report-only** for profitability; fixed amount bypasses confidence/performance multiplier in both services (`SimulatedTradingService.cpp:396-403`; live corresponding method `:409-479`). | Schedule is deterministic and intentionally ignores expectancy. Whether DCA is exempt from profitability gating is unresolved. Simulated DCA can add; live DCA is restricted to buy and enabled execution. |
| `buyandhold` | Emits one buy when no position and holds thereafter (`StrategySignal.cpp:120-129`). | Strength always 1.0 on initial buy; no expected-return producer. | **Unavailable/report-only** for profitability; fixed configured amount bypasses confidence/performance multiplier (`SimulatedTradingService.cpp:396-403`; live `:409-479`). | Initial entry is not expectancy-gated. No automatic exit in tick path. Contract must decide whether investment-style entry is exempt or requires a horizon/return diagnostic. |
| Unknown strategy | Falls through to `Unknown strategy: <name>` HOLD (`StrategySignal.cpp:301-302`). | No diagnostic. | **Unavailable and fail-closed at signal generation.** | There is no explicit configuration validation contract; unknown names can start a session that silently produces holds. |

## Shared position-sizing path

Both services extract `signal.strength`, `ml_analysis.win_probability`, `expected_return`, and `confidence`, plus spread, and load scoped live/cohort performance (`SimulatedTradingService.cpp:420-478`; live `:424-479`). The multiplier uses all of these in `PositionSizingPolicy` (`src/trading/PositionSizingPolicy.cpp:36-75`).

Important differences:

- Simulated `dca` and `buyandhold` return their configured amount before extracting or applying diagnostics (`SimulatedTradingService.cpp:396-403`).
- Live `dca` and `buyandhold` have the same fixed-amount bypass (`LiveTradingService.cpp:409-479`, beginning at the strategy bypass).
- Simulated non-fixed strategies call `minimum_trade_size_decision` with expected return, fees, slippage, spread, a minimum net-PnL requirement, and a max notional; it can return zero (`SimulatedTradingService.cpp:435-486`).
- Live entry uses the multiplier-derived allocation, then checks Coinbase minimum quote notional, spot-side direction, cash, and execution enablement (`LiveTradingService.cpp:1991-2048`). It does not call `minimum_trade_size_decision`.
- A negative/absent expected return is therefore a hard trade-size blocker in the simulated path only when the minimum-trade inputs make the decision fail; in live, the multiplier generally reduces size but does not itself guarantee positive fee-adjusted expectancy. The live profitability gate currently protects order-book signals, not indicator/DCA/buy-and-hold signals.

## Entry, add, exit, and close decision paths

### Simulated and live-parity

`SimulatedTradingService::generateTickLocked` evaluates every available symbol, serializes `execution_analysis`, records blocker counts, and:

- For `live_parity`, trusts `execution_analysis.executable_intent`; otherwise it increments the named blocker (`SimulatedTradingService.cpp:1732-1775`).
- For ordinary simulated mode, checks ML gate, max positions, `positionSizeUsdForSignal`, and spot short restrictions before opening (`:1777-1795`). The fallback blocker `profitability_or_position_size` conflates size and profitability.
- `buyandhold` never auto-closes; `dca` adds only on a buy signal (`:1801-1811`). Other strategies close on opposite signal or after `hold_ticks`, then may reopen if the ML gate passes (`:1813-1822`). The reopen condition does not independently require a profitability diagnostic.
- `updateMarkToMarketLocked` applies stop-loss/take-profit to every simulated position and calls close (`:1430-1459`). Explicit close persists entry-time prediction values, computes gross PnL and fees, and returns net PnL in the API response (`:1639-1729`).

### Live

`LiveTradingService::generateTickLocked` requires a real quote, builds and persists a signal plus `buildEntryExecutionAnalysisLocked`, and opens only when `executable_intent` is true (`LiveTradingService.cpp:2226-2260`). For existing positions it skips unmanaged Coinbase holdings; buy-and-hold holds; DCA adds only when account-entry management permits; other strategies close on opposite signal/age and may reopen only under account-entry permission and ML gate (`:2263-2299`).

`buildEntryExecutionAnalysisLocked` is the most complete live blocker inventory (`LiveTradingService.cpp:1835-1931`): no signal, profitability gate, ML confidence, account management, existing position, pending order, max positions, non-positive size/price, below-minimum notional, spot short, insufficient cash, and live execution disabled. It reports `would_submit_order` only after all these checks.

Live `openPositionLocked` repeats the safety gates and queues a Coinbase order only when execution is enabled (`LiveTradingService.cpp:1991-2048`). `addToPositionLocked` repeats minimum notional/cash/side/execution checks, but has no separate expected-return/profitability gate (`:2051-2101`). `closePositionLocked` is exits-only for session-managed positions and queues a sell; it does not re-evaluate entry profitability (`:2104-2151`). Explicit account liquidation is separate, fail-closed on active session, execution enablement, available quantity, finite quantity, and exchange minimum notional (`:2154-2224`).

Both services preserve prediction-time win probability/expected return/confidence on entry and closing rows, avoiding hindsight-derived diagnostics (`SimulatedTradingService.cpp:1524-1548`, `:1707-1714`; live equivalent in `applyLiveFillLocked` and close path).

## Diagnostic production/consumption/reporting matrix

| Diagnostic | Producer | Consumer | Status |
|---|---|---|---|
| Indicator signal strength | `evaluateStrategySignal` | Entry eligibility and position-size multiplier; serialized signal/execution analysis | Actively factored for sizing; not consistently used as a profitability gate. |
| Order-book expected return | ML regressor/transformer or labeled heuristic fallback | Shared order-book profitability gate, position sizing, serialized analysis | Actively factored; fallback policy differs by model readiness. |
| ML win probability/confidence | Classifier or heuristic | `ml_enhanced_orderbook` directional gate; sizing; entry/exit attribution | Actively factored for ML strategy; report/sizing-only for non-ML strategies. |
| Fees/spread/slippage hurdle | Service parameters + quote spread | Order-book gate; simulated minimum-trade sizing; diagnostic report | Actively factored for order-book and some simulated sizing; not a universal cross-strategy gate. |
| Live/cohort profit factor, Sharpe, drawdown, fees, net PnL | Trading stats/cohort query in service | Position-size multiplier | Actively factored into size, but not a direct no-trade gate; sample sufficiency is only explicit for cohort metrics. |
| Stop-loss/take-profit | Position mark-to-market | Close action | Actively factored into exits; no expected-return diagnostic is recomputed at exit. |
| Execution blockers | `buildEntryExecutionAnalysisLocked` (live), `buildExecutionAnalysisLocked`/tick checks (simulated) | Persisted signal JSON, API portfolio/status blocker counts, reconciliation | Reported and sometimes action-enforcing. Simulated ordinary mode has partial/conflated blocker attribution; live analysis is more complete. |
| Realized PnL, fees, expectancy, drawdown | Trade rows / `StrategyExpectancyHarness` / stats services | Reports and subsequent sizing | Report-only for the current decision; harness is a synthetic evaluation tool, not wired into live/sim ticks. |

## StrategyExpectancyHarness boundary

`evaluateStrategyExpectancy` applies the strategy-neutral diagnostic to fixtures and marks non-hold, non-actionable rows blocked (`src/trading/StrategyExpectancyHarness.cpp:113-166`). It aggregates signals, fills, blocked intents, average win/loss, expectancy, profit factor, drawdown, and negative-expectancy flags. Default fixtures cover SMA, EMA, RSI, Bollinger, MACD, stochastic, Fibonacci, DCA, buy-and-hold, plus fee-negative SMA/EMA regressions (`:169-200`).

This harness is **not** a production decision path. It currently models a stronger universal contract than the services implement: indicator/DCA/buy-and-hold fixtures are gated by expected return, while service code marks those diagnostics unavailable and can still enter. The synthesis task must decide whether the harness is the target contract or only a research comparator.

## Omissions and ambiguities for the cross-strategy contract

1. **Universal gate vs strategy exemptions:** Decide whether every generated entry must have fee-adjusted expected return, or whether DCA and buy-and-hold are explicit exemptions with a different horizon/return definition.
2. **Unavailable expected return:** Define one fail-closed behavior. Current indicator paths report “unavailable” but ordinary simulated entries can continue; live entries can also proceed for non-order-book strategies if other gates pass.
3. **Expected-return units/sign:** Order-book code treats expected return as a directional value and negates it for sells. Regressor/transformer outputs and indicator expected returns have no explicit unit/sign contract.
4. **Strength semantics:** Order-book uses a 0.22 activity threshold and the gate repeats a minimum-strength check. Other strategies use indicator-specific strength; the global minimum is only supplied by the harness, not services.
5. **Sizing vs gating:** Position sizing can reduce allocation without preventing a trade. The contract must state whether a size of zero, negative edge, or below-minimum expected net PnL is a blocker and must use the same policy in live, simulated, and parity modes.
6. **ML fallback:** Simulated transformer warm-up fails closed, while model absence/inference failure can fail open to a heuristic when `fallback_to_baseline` permits it. Live has no explicit transformer warm-up branch in `signalPassesMlGateLocked`; model readiness/fallback behavior needs parity definition.
7. **Reopen after exit:** Opposite-signal/age exits can be followed by reopen decisions. The required profitability/ML/size checks for the new entry should be explicit rather than relying on a subset of gates.
8. **Add-to-position:** DCA adds use fixed sizing and no independent profitability gate. Decide whether each add is an independent intent requiring a fresh edge, or whether the initial entry diagnostic covers the whole accumulation plan.
9. **Exit diagnostics:** Stop-loss, take-profit, opposite-signal, age-out, explicit close, and liquidation do not use expected return. Define whether expectancy is entry-only, exit-only, or both, and how close decisions are attributed.
10. **Execution-blocker taxonomy:** Live has detailed blockers; ordinary simulated mode combines profitability and position sizing and does not consistently count failures from `openPositionLocked` (minimum notional/cash). Define a shared ordered blocker taxonomy and precedence.
11. **Account-managed holdings:** Live correctly separates inherited/session-managed quantities and blocks fresh entries unless account-entry management is enabled, but the contract should state how inherited positions participate in strategy diagnostics and expectancy denominators.
12. **Diagnostic persistence:** Entry values are persisted for trade attribution, but signal-level ML/diagnostic payloads are stored as JSON text. Define schema/versioning and null/unknown semantics for unavailable values.
13. **Harness authority:** Decide whether `StrategyExpectancyHarness` is normative acceptance evidence. If so, production services need parity tests for every strategy and mode; if not, document the deliberate differences.
14. **Unknown strategy validation:** Unknown strategy names silently produce HOLD. Start-session validation should either reject unknown strategies or expose an explicit unavailable/invalid configuration state.

## Recommended synthesis acceptance contract

Before implementing a universal diagnostic contract, require a per-strategy decision table containing: signal type/strength definition; expected-return producer and units; cost inputs; minimum-strength rule; ML readiness/fallback; entry gate; size policy; add policy; exit policy; blocker precedence; persisted fields; and fail-open/closed behavior. Acceptance should compare live, simulated, and live-parity outcomes for the same fixture and verify that blocked-intent counts explain every generated-but-unfilled signal without conflating unavailable diagnostics with negative expectancy.
