# Order-book signal paths and current behavior inventory

Status: observed implementation inventory; no production behavior changed.

Scope: the checked-in C++ backend paths for `live`, `live_parity`, and synthetic `simulated` execution, with emphasis on order-book signal generation, model branches, execution blockers, accounting, and frequency. Source references are line anchors from this checkout; line numbers should be refreshed if the implementation moves.

## 1. Path map

### Live execution (`LiveTradingService`)

1. `LiveTradingService::workerLoop` (`src/trading/LiveTradingService.cpp:2309-2437`) selects the configured live universe, fetches Coinbase public order books, refreshes the Coinbase account snapshot, generates a tick, dispatches queued exchange orders, and flushes signal/trade writes. Network and database work occur outside the service mutex.
2. `selectLiveQuoteBatchLocked` (`src/trading/LiveTradingService.cpp:1244`, declaration `include/trading/LiveTradingService.hpp:182`) selects the user-configured universe. The current diagnostics explicitly report `live_quote_symbols_per_tick_cap=0` and `quote_fanout_limit_enforced=false` (`src/trading/LiveTradingService.cpp:2561-2581`). A warning threshold is logging/observability only; it is not a cap.
3. `fetchLiveQuotes` (`src/trading/LiveTradingService.cpp:1208`) obtains one `OrderBookSummary` per selected symbol with bounded retry behavior. A symbol with no valid quote is skipped by `generateTickLocked`; it does not create a signal or execution count (`src/trading/LiveTradingService.cpp:2234-2245`).
4. `buildSignalRecordLocked` (`src/trading/LiveTradingService.cpp:1516-1803`) converts the quote into the shared signal payload. `generateTickLocked` (`src/trading/LiveTradingService.cpp:2226-2307`) attaches `execution_analysis`, stores the latest signal history, and opens/adds/closes only session-managed positions.
5. `buildEntryExecutionAnalysisLocked` (`src/trading/LiveTradingService.cpp:1835-1931`) is the live pre-submit blocker chain. It attributes no signal, ML confidence, account-position-management policy, existing position, pending order, max positions, nonpositive size/price, Coinbase minimum notional, spot short prohibition, insufficient cash, and disabled live execution. Only `would_submit_order` is executable.
6. `openPositionLocked`/`addToPositionLocked` (`src/trading/LiveTradingService.cpp:1991-2101`) queue quote-sized buy intents only after live execution is explicitly enabled and safety gates pass. `dispatchOrders` and pending-order recovery (`src/trading/LiveTradingService.cpp:1035-1207`) submit to Coinbase and wait for a terminal fill rather than inventing a fill.
7. `applyLiveFillLocked` (`src/trading/LiveTradingService.cpp:654-1034`) creates the durable trade row, applies cash/position changes, stores exchange fees, and carries entry-time ML values onto closing rows. `closePositionLocked` (`src/trading/LiveTradingService.cpp:2104-2152`) is restricted to session-managed positions; pre-existing Coinbase holdings are handled by the distinct liquidation path (`src/trading/LiveTradingService.cpp:2154-2224`).

### Live-parity paper (`SimulatedTradingService` with `mode_ == "live_parity"`)

1. `SimulatedTradingService::startSession` accepts `mode` and uses Coinbase public market data for both `live` and `live_parity` (`src/trading/SimulatedTradingService.cpp:2175-2189`; `usesLiveMarketData` at lines 144-146). It retains the selected symbols and strategy parameters, but never enables exchange dispatch for `live_parity`.
2. The worker fetches live quotes, skips symbols without a quote, then calls the same `generateTickLocked` and payload-producing code as synthetic simulation (`src/trading/SimulatedTradingService.cpp:1832-1935`).
3. In the no-position branch, `live_parity` uses `buildExecutionAnalysisLocked` as the live-equivalent paper gate. An executable analysis increments `executable_order_intents_` and calls local `openPositionLocked`; a generated but blocked candidate increments `execution_blocker_counts_` (`src/trading/SimulatedTradingService.cpp:1732-1795`). The analysis applies minimum notional, spot-only buy, and cash checks for parity (`src/trading/SimulatedTradingService.cpp:575-601`).
4. `openPositionLocked` settles a local paper fill when live order execution is disabled; it records `trade_type=live_paper` for `mode_ == "live"` without exchange dispatch, while `live_parity` uses `trade_type=live_parity` through the general mode expression (`src/trading/SimulatedTradingService.cpp:1470-1560`). The same method can still represent synthetic short-capable behavior outside live-parity; the live-parity analysis prevents new sell-side spot entries.
5. `closePositionLocked` settles local paper exits (or queues Coinbase orders only if the explicit live execution flag is enabled, which is not the live-parity contract) and records gross PnL plus a separate fee (`src/trading/SimulatedTradingService.cpp:1639-1730`).

Observed boundary: live-parity shares quote acquisition, signal/model fields, profitability gating, minimum-notional/spot/cash entry checks, and diagnostics with live, but its fill is local and does not prove exchange acceptance, fill price, partial-fill behavior, exchange fees, or account-state reconciliation.

### Synthetic simulated execution (`SimulatedTradingService` with `mode_ == "simulated"`)

1. `startSession` initializes default capital to `$10,000`, default symbols to `BTC-USD`, `ETH-USD`, and `SOL-USD`, accepts `parameters` or the legacy `strategy_params`, and overlays selected top-level settings (`src/trading/SimulatedTradingService.cpp:2142-2285`; defaults at lines 112-115 and 217-231).
2. The worker ticks once per loop with a one-second sleep (`src/trading/SimulatedTradingService.cpp:1832-1935`). Synthetic ticks update an AR(1) imbalance and price process; live/live-parity ticks consume Coinbase snapshots instead (`buildSignalRecordLocked`, `src/trading/SimulatedTradingService.cpp:1045-1387`).
3. The no-position branch applies the live-parity analysis only for `live_parity`. Synthetic mode uses direct ML, max-position, position-size, and spot-side checks before calling local `openPositionLocked` (`src/trading/SimulatedTradingService.cpp:1759-1795`).
4. Existing positions are updated mark-to-market, held by `buyandhold`, accumulated by DCA, or closed on an opposite signal/holding age (`src/trading/SimulatedTradingService.cpp:1798-1829`). Stop-loss/take-profit parameters are interpreted as entry-notional percentages (`src/trading/SimulatedTradingService.cpp:1430-1468`).
5. Synthetic opens/adds/closures are local fills. `applyLiveFillLocked` and `dispatchOrders` are reachable only when the explicit live-order execution flag is enabled in `mode_ == "live"` (`src/trading/SimulatedTradingService.cpp:657-877`); the normal `simulated` and `live_parity` paths do not submit exchange orders.

## 2. Signal dimensions and model branches

### Symbol dimension

- The selected universe is stored in `symbols_` in both service headers (`include/trading/LiveTradingService.hpp:248-259`, `include/trading/SimulatedTradingService.hpp:217-227`). An empty request falls back to the service defaults; a supplied array is preserved as the selected universe (`SimulatedTradingService.cpp:2189-2200`; live start has the corresponding initialization in `LiveTradingService.cpp`).
- Each signal carries `symbol`, `session_id`, epoch `timestamp`, ISO UTC timestamp, price/mid, spread, imbalance, best bid/ask, depth, volume, and `total_signals` (`SignalRecord` definitions in both headers; payload construction in `LiveTradingService.cpp:1571-1606` and `SimulatedTradingService.cpp:1132-1174).
- `total_signals` is a tick/index-derived value, not a count of durable rows. Live diagnostics call current latest-by-symbol coverage out separately (`LiveTradingService.cpp:2569-2581`); simulated diagnostics describe latest-by-symbol coverage and separate display pagination (`SimulatedTradingService.cpp:2012-2064`, `2375-2429`).

### Strategy dimension

- Order-book strategies are exactly `orderbook` and `ml_enhanced_orderbook` (`SimulatedTradingService.cpp:140-142`; the live service has the same predicate). They derive candidate strength as `min(1, abs(imbalance)*1.15)`, generate at `strength >= 0.22`, and choose buy for nonnegative imbalance or sell for negative imbalance (`LiveTradingService.cpp:1547-1556`).
- Non-order-book strategies use `evaluateStrategySignal` (`src/trading/StrategySignal.cpp:113-303`) over rolling price history: SMA, EMA, RSI, Bollinger, MACD, stochastic, Fibonacci, DCA, and buy-and-hold are implemented; insufficient history and unknown strategies return hold.
- DCA and buy-and-hold use fixed-amount behavior in sizing (`SimulatedTradingService.cpp:396-403` and the corresponding live implementation). Other strategies use position-sizing inputs including signal strength, win probability, expected return, model confidence, spread, recent performance, and cohort metrics (`src/trading/PositionSizingPolicy.cpp:20-84`; service sizing around `SimulatedTradingService.cpp:396-486`).

### Model and fallback dimension

- `ml_enhanced_orderbook` attempts feature engineering/model inference using imbalance, spread percent, mid, bid/ask volume, depth, momentum, and volatility (`LiveTradingService.cpp:1637-1680`; simulated equivalent `SimulatedTradingService.cpp:1201-1268`). Classifier output becomes `win_probability`; regressor output or transformer output becomes `expected_return`; confidence is derived from classifier distance from 0.5.
- Live marks a ready model with the active model id and does not expose the simulated transformer warm-up branch (`LiveTradingService.cpp:1672-1679`). Simulated checks transformer sequence readiness, increments `transformer_warming_symbols_`, emits `model_version=transformer-warming-up` and `inference_status=warming_up` when needed, and fails the ML gate for that branch (`SimulatedTradingService.cpp:1226-1267`, `1390-1421`). This is a parity gap to define, not an assumed bug.
- If no model is used, order-book strategies use `model_version=heuristic-fallback`, expected return `imbalance * orderbook_expected_return_scale_percent`, default scale 2.4%, clamped to 0-5% (`LiveTradingService.cpp:1686-1702`; simulated `1271-1287`). Non-order-book strategies mark expected return unavailable and expose a diagnostic rather than inventing actionability (`LiveTradingService.cpp:1703-1729`; simulated `1288-1315`).
- Both order-book producers call `evaluateOrderBookProfitabilityGate` (`StrategySignal.cpp:305-341`) with directional expected return, round-trip fee, spread fraction, and slippage buffer. The gate records `fee_adjusted_expected_return`, `required_edge`, pass/fail, and reason; a failed generated candidate is rewritten to `hold` with `signal_generated=false` (`LiveTradingService.cpp:1733-1769`; simulated `1318-1354`).
- `ml_enhanced_orderbook` additionally applies a directional classifier confidence gate: buys require `win_probability >= confidence_threshold`; sells require `<= 1-confidence_threshold` (`LiveTradingService.cpp:1805-1832`; simulated `1390-1421`). The heuristic fallback honors `fallback_to_baseline`.

## 3. Execution, cost, and accounting representation

| Concept | Current representation / computation | References |
| --- | --- | --- |
| Signal strength | `SignalRecord::strength`, payload `strength`/`signal_strength`; order-book strength is normalized absolute imbalance; non-order-book strength is strategy-specific in [0,1]. | service headers; `LiveTradingService.cpp:1547-1581`; `StrategySignal.cpp:84-102,162-299` |
| Expected return | `ml_analysis.expected_return`; model regressor or transformer output, otherwise heuristic fallback; non-order-book missing expected return is explicit. | `LiveTradingService.cpp:1637-1729`; simulated `1201-1315` |
| Fee/spread/slippage | Profitability hurdle is round-trip fee + spread fraction + slippage buffer; defaults include 1.5% fee and 0.2% slippage in the order-book fallback path, with configurable `round_trip_fee_percent`, `slippage_buffer_percent`, and `min_orderbook_signal_strength`. | `StrategySignal.cpp:305-341`; service gate inputs `LiveTradingService.cpp:1733-1755` |
| Position sizing | Base notional is percent/dollar configured, then confidence/performance/spread multipliers and minimum net PnL policy can reduce it; `allow_unprofitable_trades` can override the sizing decision. | `PositionSizingPolicy.cpp:20-134`; `SimulatedTradingService.cpp:396-486` |
| Realized PnL | Opening legs carry `pnl=0`; close rows store gross realized PnL. Simulated local close returns `net_pnl=gross-fee`, but the persisted trade row retains gross `pnl` and separate `fees`. Live fills similarly set close-row gross PnL and separate exchange fees. | `SimulatedTradingService.cpp:1639-1729`; `LiveTradingService.cpp:654-1034` |
| Fees | `TradeRecord::fees`, `total_fees_`, durable `individual_trades.fees`, and portfolio `total_fees`. The stats layer computes `net_pnl = total_pnl - total_fees`. | headers; `TradingStatsCalculator.cpp:97-104,133-146`; schema in `SimulatedTradingService.cpp:314-366` |
| Wins/losses | `TradingStatsCalculator` counts positive/negative PnL rows; `ExecutionReconciliation` counts only closing legs as decided outcomes, excluding zero-PnL opens. | `TradingStatsCalculator.cpp:97-147`; `ExecutionReconciliation.cpp:45-89` |
| Expectancy/profit factor | Stats layer computes trade-level PnL metrics; reconciliation computes closing-leg expectancy as total realized PnL / winners+losers and profit factor from gross winning/losing closing PnL. | `TradingStatsCalculator.cpp:32-51`; `ExecutionReconciliation.cpp:62-80` |
| Drawdown | Stats layer tracks peak-to-current cumulative PnL drawdown, based on its input rows; portfolio also exposes unrealized PnL separately. | `TradingStatsCalculator.cpp:92-126`; service portfolio JSON (`LiveTradingService.cpp:2481-2500`, simulated `1976-1994`) |
| Blocked intents | Live stores per-signal execution analysis and blocker counts in order-book diagnostics; simulated stores `signals_evaluated`, `signals_generated`, executable intents, model warm-up/rejected-input counts, and blocker counts. | `LiveTradingService.cpp:2526-2582`; `SimulatedTradingService.cpp:2012-2064` |
| Rejected exchange orders | Live `dispatchOrders` records acceptance/error in logs and pending-order state; an exchange rejection does not become a fill. | `LiveTradingService.cpp:1035-1207`; analogous simulated live-order path `SimulatedTradingService.cpp:781-877` |
| Trade frequency | Worker iterations are roughly one per second in simulated mode; live has no cadence sleep after the live tick and logs quote fan-out duration/request rate. Signal frequency is represented by tick counters and evaluated/generated counts, not an immutable event-rate metric. | `SimulatedTradingService.cpp:1907`; `LiveTradingService.cpp:2352-2373`, `2404-2410` |

Important accounting distinction: portfolio/status stats and execution reconciliation are not identical contracts. The former consumes trade inputs and can include opening rows with zero PnL; the latter attributes realized outcomes to closing legs and separates blocked/generated/executable signal counts. Any optimization protocol must specify which contract is authoritative for each metric.

## 4. Timestamps, fixtures, and configuration knobs

### Timestamps and persistence

- Signal/trade rows use epoch seconds plus ISO UTC strings generated by `nowEpochSeconds`/`nowIsoUtc`; signal timestamps are prediction-time, while close fills use fill/close time (`LiveTradingService.cpp:694-708`; simulated `1692-1711`).
- `order_book_signals` persists signal id, session, symbol, type, strength, price, timestamp, JSON payload, spread, imbalance, mid, best bid/ask, depth, volume, and `total_signals`; `individual_trades` persists session, symbol, side, size, price, timestamp, strategy, reason, PnL, fees, prediction fields, trade type, and `is_closing_leg` (`SimulatedTradingService.cpp:314-366`; live has the same write shape at `LiveTradingService.cpp:1409-1514`).
- Both services queue writes under the mutex and retry/flush outside it. Simulated recent trades are capped at 100; live recent signal retention is bounded by `max(kMaxRecentSignals, symbols_.size())` (`SimulatedTradingService.cpp:1423-1428`; `LiveTradingService.cpp:1934-1942`). Full per-session trade inputs are retained in memory for status statistics.

### Relevant knobs

- Universe: `symbols`; default simulated universe is BTC/ETH/SOL.
- Strategy: `strategy`; aliases/parameters are accepted through `parameters` or legacy `strategy_params`.
- Sizing: `position_size_percent`, `position_size_mode`, `position_size_value`, `amount`, `initial_portfolio_size`, `minimum_net_pnl_usd`, `allow_unprofitable_trades`.
- Entry/model gates: `min_orderbook_signal_strength` (default 0.22), `orderbook_expected_return_scale_percent` (default 2.4% fallback), `round_trip_fee_percent` (default order-book fallback 1.5%), `slippage_buffer_percent` (default 0.2% order-book fallback), `confidence_threshold` (default 0.6), `fallback_to_baseline`.
- Capacity and exits: `max_positions` / `max_positions_per_session`, `position_update_interval`, `stop_loss_percent`/`stop_loss`, `take_profit_percent`/`take_profit`, DCA `interval_hours`.
- Live safety: `live_order_execution` is an explicit opt-in; Coinbase credentials/account snapshot, spot-only side rules, minimum quote notional, available cash/quantity, account-position-management state, and pending orders remain independent blockers.
- Cost/sizing interaction: `PositionSizingPolicy` also consumes cached live stats and execution cohort metrics (`SimulatedTradingService.cpp:435-468`), so a future protocol must identify whether these are baseline inputs or post-signal adaptation.

### Existing fixtures and tests

- `src/tests/test_strategy_signal.cpp:128-243` covers all indicator strategy signal types, warm-up/unknown fail-safe behavior, directional expected-return diagnostics, shared order-book fee/spread/slippage gate, fee-neutral blocking, weak-strength blocking, fallback-scale behavior, and strong buy/sell directionality.
- `src/tests/test_execution_reconciliation.cpp:97-184` is the primary deterministic attribution fixture. It covers holds, blocked reasons, executable intents, opening/closing outcomes, winners/losers, win rate, average win/loss, expectancy, profit factor, fees, outcome coverage, unexplained outcomes, exact-flat fee-negative closes, and unknown strategy bucketing.
- `src/tests/test_strategy_expectancy_harness.cpp:35-90` verifies per-strategy expectancy aggregation and flags high-count negative-expectancy fixtures.
- `src/tests/test_position_sizing_policy.cpp` covers sizing-policy calculations; `src/tests/test_portfolio_accounting.cpp` covers account/position accounting; `src/tests/test_trading_stats_calculator.cpp` covers serialized stats conventions; `src/tests/test_coinbase_order.cpp`, `test_coinbase_auth.cpp`, and `test_coinbase_portfolio.cpp` cover exchange request/auth/account primitives.
- `CMakeLists.txt:138-210` registers the relevant test targets, including `position_sizing_policy`, `portfolio_accounting`, `strategy_signal`, `strategy_expectancy_harness`, `execution_reconciliation`, Coinbase tests, and `trading_stats_calculator`. There are no service-level deterministic fixtures that instantiate a full `LiveTradingService` or `SimulatedTradingService` tick with captured order-book snapshots; that is a material coverage gap.

## 5. Observed gaps the optimization protocol must define

These are inventory findings, not proposed behavior changes:

1. **Metric grain and cost semantics:** specify whether a trade means an opening leg, a closing leg, a round trip, or an exchange fill; specify whether expectancy/average loss are gross PnL or net of fees, spread, and slippage. Current rows store gross PnL plus separate fees, while reconciliation closes on closing legs.
2. **Signal-to-outcome join:** define the durable join key/window from prediction signal to order intent, accepted order, partial/terminal fill, and closing outcome. Current signal and trade rows share session/symbol/time fields but do not expose a single protocol-level attribution id for every lifecycle stage.
3. **Live versus live-parity evidence:** define which exchange facts must be present before parity is considered proven: quote timestamp, fee, slippage/fill price, acceptance/rejection, partial fill, and account snapshot state. Live-parity currently proves only local paper settlement against live public quotes.
4. **Model branch comparability:** define treatment of model-ready, heuristic-fallback, transformer-warming-up, inference exception, and expected-return-unavailable rows. Live and simulated transformer readiness behavior is not identical.
5. **Blocked versus rejected:** distinguish a pre-submit blocker (signal never becomes an intent), an exchange rejection, a pending order, a non-fill/expired order, and a session/account safety skip. Current blocker counters cover pre-submit analysis; dispatch rejection is primarily logged/pending-state behavior.
6. **Frequency denominator:** define whether frequency is per worker tick, per selected symbol, per valid quote, per generated signal, per executable intent, or per accepted/final fill. Live quote fan-out and failures can make these denominators diverge.
7. **Universe coverage:** define how missing/failed quote symbols enter coverage and rate calculations. Current live diagnostics exclude failed symbols from signal/execution counts but expose failure status and retries.
8. **Sizing versus gating:** define when expected return is a gate, a size input, an exit input, or report-only. Current implementation uses the shared profitability gate and then feeds expected return into sizing; the diagnostics factoring contract in `docs/STRATEGY_OBJECTIVE.md:41-58` requires this to be explicit.
9. **Exit and drawdown basis:** define whether drawdown uses realized closing PnL only, mark-to-market PnL, net PnL after fees, or portfolio equity. Current stats drawdown is cumulative input-row PnL, while portfolio exposes realized and unrealized values separately.
10. **Fixture/time-window protocol:** define fixed quote snapshots or deterministic seeds, model artifact/version, selected universe, parameters, timezone, and minimum observation window required to compare before/after expectancy. Existing unit fixtures cover pure functions but not end-to-end service ticks.
11. **Closeout evidence:** require exact-SHA remote CI plus a runtime/evidence artifact for live-parity or live claims; green compilation alone cannot establish signal quality, fill parity, expectancy, or safe live execution.

## 6. Reconciliation checklist for the next worker

- [ ] Preserve the user-selected universe and record quote coverage/failure separately from signal quality.
- [ ] Reconcile every generated candidate to a blocker, executable intent, exchange result, fill, and closing outcome.
- [ ] Report signal strength, expected return, required edge, fee-adjusted return, and model branch with symbol/strategy/session/timestamp dimensions.
- [ ] Compare average realized win, average realized loss, net expectancy, profit factor, drawdown, fees, and blocked/rejected counts after costs.
- [ ] Keep `live`, `live_parity`, and synthetic `simulated` labels distinct; do not treat local paper fills as Coinbase fills.
- [ ] Keep missing expected-return/model data fail-closed and explicitly classified.
- [ ] Use fixed fixtures or captured evidence with exact configuration and timestamps; do not infer improvement from raw signal/trade count.
- [ ] Run independent review for live-affecting behavior and verify exact pushed-SHA CI before closeout.
