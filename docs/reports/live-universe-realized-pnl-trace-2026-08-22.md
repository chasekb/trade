# Live selected-universe order-book to realized-PnL trace

Date: 2026-08-22
Backlog scope: `TRADE-BL-0027`
Task: `t_3d1b2b91`

## Scope and evidence boundary

This is a read-only source trace of the checked-out backend/frontend contract. No live session was started, no Coinbase order was submitted, and no account or database state was changed. No reproducible live time window or runtime metrics were available in this workspace; therefore runtime claims below are classified as confirmed from source, ruled out by source, or unknown pending persisted/runtime evidence.

Relevant prior implementation evidence is in:

- `docs/reports/live-orderbook-execution-attribution-closeout-2026-08-04.md`
- `docs/reports/live-parity-paper-and-blocker-attribution-progress-2026-08-08.md`
- `docs/reports/execution-reconciliation-closeout-2026-08-08.md`

## End-to-end path

1. **Selected universe ingestion**
   - `frontend/lib/symbolUniverse.ts` parses/deduplicates custom symbols and the dashboard passes the selected array through `buildStartTradingPayload` in `frontend/lib/api.ts`.
   - `src/api/PredictController.cpp:1348-1357` forwards the JSON body unchanged to `LiveTradingService::startSession`.
   - `src/trading/LiveTradingService.cpp:2810-2821` copies every string in `payload.symbols`; only an empty list falls back to `BTC-USD`, `ETH-USD`, `SOL-USD` (`:111-113`). There is no source-level selected-universe truncation here.
   - `parameters` is canonical; `strategy_params` is accepted as a legacy alias (`:2823-2831`). Selected symbols are also returned in portfolio/status JSON (`:2446-2459`, `:2585-2595`).

2. **Live-session preflight and account baseline**
   - `startSession` creates a Coinbase client from `COINBASE_API_KEY`/`COINBASE_API_SECRET` (`:2790-2798`), fetches accounts and ticker-valuations through `fetchLiveAccountSnapshot` (`:1266-1297`), and fails closed if the snapshot cannot load (`:2800-2809`).
   - Synthetic capital keys `initial_portfolio_size`, `initial_balance`, and `capital` are rejected (`:2832-2841`). `live_order_execution` must be explicitly true; otherwise startup fails (`:2851-2864`).
   - `max_positions` is taken from top-level payload first, then `max_positions_per_session`, default 100; it is clamped to at least 1. `position_update_interval` defaults to 5 and is clamped to at least 1 (`:2866-2877`). The latter controls hold/age-out evaluation, not quote cadence.
   - Account holdings are reconciled into `PositionState` by `applyLiveAccountSnapshotLocked` (`:1300-1407`). Account management modes are `disabled`, `monitor`, `manage_exits`, and `manage_entries_and_exits` (`:488-504`). Inherited holdings are not treated as session PnL; their management state and quantity provenance are retained.
   - Startup recovers persisted `submitting`/`pending` rows via `recoverPendingOrders` (`:963-1032`) before starting the worker (`:2913-2927`).

3. **Quote fan-out and cadence**
   - `workerLoop` (`:2309-2437`) first resolves pending fills, flushes queued writes, snapshots the selected symbols, fetches all live quotes, refreshes account state, generates one tick, dispatches orders, and flushes writes.
   - `selectLiveQuoteBatchLocked` (`:1244-1263`) sets the batch to the complete `symbols_` vector. Diagnostics explicitly report `live_quote_symbols_per_tick_cap=0` and `quote_fanout_limit_enforced=false` (`:2526-2582`).
   - `fetchLiveQuotes` (`:1208-1242`) performs one Coinbase order-book request per selected symbol, records valid `mid`, spread, best bid/ask, imbalance, volume, and depth, and skips failed requests. Missing quotes never become synthetic ticks (`:2226-2245`).
   - Current behavior has no normal quote sleep/cadence throttle: the loop immediately iterates after persistence/dispatch. The only sleeps are one-second stop settling (`:2347-2349`) and bounded final persistence retries (`:2427-2430`). A fan-out warning threshold of 10 is logging-only (`:2363-2373`, `:50-53`).
   - Logged evidence: requested/attempted/succeeded/skipped symbols, fetch milliseconds, and estimated requests/second (`:2352-2367`). `quote_success_symbol_count` is the current tick's successful quote count, while `current_latest_signal_count` and `coverage_complete` are derived from recent latest-by-symbol signals (`:2561-2579`). No historical runtime values were available for this trace.

4. **Signal construction**
   - `generateTickLocked` calls `buildSignalRecordLocked` once for each valid quote (`:2234-2253`). For `orderbook`/`ml_enhanced_orderbook`, strength is `min(1, abs(imbalance)*1.15)` and a BUY/SELL signal is initially generated at strength >= 0.22 (`:1547-1557`). Sell signals are directionally represented even though Coinbase spot cannot open synthetic shorts.
   - The payload contains signal type, generated flag, strength, price, timestamp, data status, spread, volume, imbalance, criteria analysis, and ML analysis (`:1583-1606`, `:1796-1802`). For order-book strategy, data is normally `sufficient`; only indicator reasons containing `insufficient price history` or `warming up` are marked insufficient (`:143-146`, `:1593-1600`). A failed quote produces no signal row for that symbol in that tick.
   - ML-enhanced mode uses the loaded ONNX/transformer model when ready (`:1633-1684`), with expected return sourced from regressor or transformer. Without a model, the heuristic fallback uses `orderbook_expected_return_scale_percent`, default 2.4%, clamped to 0-5% (`:1686-1702`). The historical code comment records that the former 1.2% fallback could never clear the default fee/spread/slippage hurdle; the current checked-out fallback was raised to 2.4%.
   - Signal rows are persisted to `order_book_signals` with signal and market fields plus JSON payload (`:1409-1457`). Recent in-memory signals are capped at 250, but the cap is raised to at least the selected-universe size (`:1934-1942`); the persisted table is not capped by this deque.

5. **Expected-return/profitability gate**
   - For generated order-book signals, `buildSignalRecordLocked` evaluates `evaluateOrderBookProfitabilityGate` (`:1733-1756`) with expected return, spread/mid, `round_trip_fee_percent` (default 1.5%), `slippage_buffer_percent` (default 0.2%), and `min_orderbook_signal_strength` (default 0.22).
   - The gate emits `fee_adjusted_expected_return`, `required_edge`, `profitability_gate_passed`, and a reason. A failure rewrites the signal to HOLD, strength 0, `signal_generated=false`, `data_status=sufficient`, and the reason becomes the gate reason (`:1757-1769`). This is a valid-market-data strategy hold, not an insufficient-coverage condition.
   - `buildEntryExecutionAnalysisLocked` (`:1835-1931`) records `expected_return`, fee-adjusted expected return, required edge, strength/return buckets, intended action/side, and the first blocker. For a post-gate HOLD it reports `no_signal` unless the payload explicitly says the profitability gate failed, in which case it reports `profitability_gate` (`:1863-1868`).
   - `ml_enhanced_orderbook` applies an additional directional confidence gate: buys require `win_probability >= confidence_threshold` and sells require `win_probability <= 1-confidence_threshold`; default threshold is 0.6 (`:1805-1833`). Heuristic fallback obeys `fallback_to_baseline` (`:1813-1816`).

6. **Executable-intent preflight blockers**

   `buildEntryExecutionAnalysisLocked` evaluates blockers in this order, returning the first match:

   - `no_signal` or `profitability_gate` (`:1863-1868`)
   - `ml_confidence_gate` (`:1871-1873`)
   - `account_position_management_disabled` for inherited/account-managed symbols when entries are not permitted (`:1875-1878`)
   - `existing_position` (`:1880-1882`)
   - `pending_order` (`:1884-1886`)
   - `max_positions`, counting managed positions plus pending entry symbols (`:1888-1897`)
   - `nonpositive_position_size_or_price` (`:1900-1904`)
   - `below_minimum_notional`; Coinbase minimum is $1.00 (`src/exchange/CoinbaseOrder.cpp:15-41`; live analysis `:1906-1910`)
   - `spot_cannot_open_short` for SELL entry signals (`:1911-1913`)
   - `insufficient_cash`; available cash is `max(0, cash_ - pending_reserved_cash_)`, and estimated fee is 0.05% (`:1915-1921`, `kFeeRate` at `:38`)
   - `live_execution_disabled` (`:1923-1926`)
   - otherwise `would_submit_order`, `blocked=false`, `executable_intent=true` (`:1928-1931`).

   The same gates are enforced again by `openPositionLocked` (`:1991-2049`), so diagnostic metadata cannot bypass execution safety. `generateTickLocked` only calls `openPositionLocked` when the diagnostic says executable (`:2248-2259`). The per-signal analysis is persisted inside `signal_data`; aggregate blocker counts and strength/expected-return buckets are emitted in `order_book_signal_diagnostics` (`:2526-2582`).

7. **Position sizing and reservation**
   - `positionSizeUsdForSignal` (`:409-479`) derives base size from either `position_size_mode=dollar`/`position_size_value` or `position_size_percent` (default 1%) of `percentSizingCapital(cash_, total_positions_value_, initial_capital_)`. DCA/buy-and-hold additionally cap the result by `amount`.
   - `calculate_position_size_usd` applies a multiplier that can reduce, but never increase, the configured base ceiling (`src/trading/PositionSizingPolicy.cpp:36-84`). Inputs include signal strength, win probability, expected return, confidence, spread, live stats, and optional cohort metrics. Live profit factor, Sharpe, drawdown, fees, and net PnL are read through the 5-second `TradingStatsService` cache (`LiveTradingService.cpp:444-479`; `TradingStatsService.cpp:94-150`).
   - A queued order reserves `allocated_usd + estimated_fee` and marks the symbol pending (`:638-645`). Available cash subtracts all pending reservations. This is distinct from the $1 Coinbase minimum and can independently block an intent.

8. **Order submission and accepted-but-pending state**
   - `dispatchOrders` (`:1035-1104`) checks stop/shutdown, persists an intent in `live_coinbase_orders` with signal/position JSON and `submitting` status (`:859-918`), then calls `CoinbaseAdvancedClient::placeMarketOrder` with quote size for buys and base size for sells (`:1071-1074`).
   - Definitive rejection marks the row rejected and releases the reservation; non-definitive failure remains a pending client-id lookup (`:1075-1089`). Accepted orders are marked `pending` and stored in `pending_live_orders_`; acceptance is explicitly not treated as a fill (`:1091-1102`).
   - `resolvePendingLiveOrders` (`:1106-1206`) resolves missing order IDs by client ID, retries lookup, abandons a complete-not-found order only after 30 attempts while releasing reservation, and otherwise retains pending state. It requires a terminal historical order response with actual fill data before applying accounting.

9. **Fill handling, fees, and position lifecycle**
   - `CoinbaseOrder::parseOrderFill` accepts terminal FILLED/CANCELLED/EXPIRED/FAILED responses, parses numeric strings or numbers, rejects malformed/non-finite/negative values, and for positive fills requires filled value, average price, and actual `total_fees` (`src/exchange/CoinbaseOrder.cpp:53-109`).
   - `applyLiveFillLocked` releases pending reservation and ignores zero-size terminal outcomes (`LiveTradingService.cpp:654-663`). Positive fills use actual average price/value/`total_fees` (`:665-687`).
   - Open/add fills create or average a `PositionState`, capture entry-time ML values, and have `pnl=0`; close fills compute gross realized PnL from managed quantity and entry price, record the closing leg, add gross PnL to `realized_pnl_`, and remove/resize the position (`:689-745`, `:777-850`). Inherited holding exits are classified `live_account_managed_close` and explicitly excluded from strategy PnL. Liquidation fills are `live_liquidation` with zero PnL (`:746-776`).
   - Actual fees are accumulated in `total_fees_`, and the trade is queued for persistence and in-memory statistics (`:852-856`). The persisted row includes `pnl`, `fees`, `trade_type`, `is_closing_leg`, and entry prediction fields (`:1459-1502`).
   - A fresh Coinbase account snapshot is applied after any settlement (`:1195-1205`) and every worker iteration (`:2374-2393`), reconciling available/held quantity, cash, positions, inherited quantities, managed floors, and unrealized PnL (`:1300-1407`).

10. **Realized-PnL attribution and displayed fields**
    - `buildStatusJson` reloads persisted `individual_trades` for the current session, excludes `live_account_managed_add`, `live_account_managed_close`, and `live_liquidation`, and falls back to in-memory inputs only when the query is empty (`:2598-2633`). It serializes total gross PnL, total fees, net PnL, win rate, average win/loss, profit factor, Sharpe, drawdown, trade counts, and volume (`:2633-2655`).
    - `TradingStatsCalculator` defines `net_pnl = total_pnl - total_fees`; win rate is winners/(winners+losers)*100, zero-PnL rows excluded from that denominator; max drawdown is the peak-to-trough cumulative `pnl` series; profit factor uses gross positive PnL/gross absolute negative PnL (`src/trading/TradingStatsCalculator.cpp:81-153`). The calculator consumes stored gross `pnl` and separate `fees`, so after-fee expectancy must use `net_pnl`, not `total_pnl`.
    - `portfolio` exposes `cash_balance`, `available_balance_usd`, `pending_reserved_cash`, signed positions value, unrealized/realized/net PnL, total fees, positions, recent trades/signals, and diagnostics (`:2446-2523`). `tradeToJson` emits `pnl` and `fees` plus prediction fields (`:545-564`); `signalToJson` emits ML, profitability, and execution analysis (`:517-542`).
    - `buildLiveTabProducerJson` separately exposes Coinbase-authoritative account portfolio, positions, pending orders, readiness, and blockers (`:2658-2764`). `can_trade` requires active session, configured credentials, loaded account snapshot, enabled execution, and no account snapshot error (`:2664-2667`). This producer is not the same shape as the session stats payload, and frontend consumers must distinguish `portfolio.total_fees` from per-trade `fees`.

## Widget/display versus executable intent

- The order-book widget/API `getOrderBookSignals` selects the latest signal per symbol from `recent_signals_`, filters requested symbols, and adds response-only HOLD placeholders for selected symbols without a latest signal (`:3242-3300`). Placeholders are never persisted and never create intents.
- The widget therefore can show full selected-universe coverage even when a symbol had no successful quote in the current tick or no generated signal. `execution_analysis.executable_intent` is the authoritative source-level distinction between a generated/diagnostic row and a live order intent.
- The latest signal history is bounded in memory, while `order_book_signals` and `individual_trades` are persisted. A dashboard row count, `total_analyzed`, `total_signals`, or current latest-by-symbol count must not be interpreted as cumulative generated-signal count without querying persisted rows.
- Confirmed no hidden live quote cap: current code requests `symbols_` in full and explicitly reports no cap. Any runtime coverage gap must be attributed to quote failures, Coinbase/API limits, transport errors, or unavailable runtime evidence—not an enforced application symbol cap.

## Failure-mode classification

| Suspected cause | Classification from source | Evidence / missing evidence |
|---|---|---|
| Selected-universe truncation | Ruled out in current source | Full `symbols_` batch, explicit cap=0 and enforcement=false. Runtime request/success logs still needed to prove a particular session's coverage. |
| Normal cadence sleep suppressing quotes | Ruled out in current source | No normal worker sleep; only stop-settling/final-write sleeps. Runtime rate-limit/transport behavior remains unknown. |
| Missing/stale quote coverage | Unknown for the target live window | Failed quote requests are skipped and logged, but no target-window logs were supplied. |
| Insufficient history/warm-up | Mostly ruled out for order-book strategy | Order-book uses current imbalance; indicator strategies have warm-up logic. Need target strategy/window data to quantify. |
| Signal strength below activity threshold | Confirmed possible blocker | Initial threshold is 0.22 strength, derived from imbalance. Need persisted signal distribution. |
| Fee/spread/slippage/required-edge hurdle | Confirmed possible blocker | Default required inputs are 1.5% round-trip fee + 0.2% slippage + live spread; failed gate rewrites to HOLD. Need expected-return/spread distributions. |
| Heuristic expected-return calibration | Confirmed historical risk, current fallback changed | Current fallback scale defaults to 2.4%; no live model/runtime evidence proves it clears gate often enough or predicts realized returns. |
| ML confidence gate | Confirmed possible blocker for ML-enhanced mode | Directional 0.6 default threshold; model availability and output distribution unknown. |
| Spot-only SELL entries | Confirmed blocker | SELL signals can be generated, but executable entry requires BUY. Need signal direction distribution. |
| Min notional | Confirmed possible blocker | $1.00 quote minimum before live entry; target sizing/runtime values unknown. |
| Cash / pending reservation | Confirmed possible blocker | Available cash subtracts pending reservations and estimated 0.05% fee; target account state unknown. |
| Existing position / pending order / max positions | Confirmed possible blockers | Explicit ordered gates; target counts unknown. |
| Live execution confirmation/readiness | Confirmed startup gate | Session cannot start unless account snapshot and explicit execution confirmation succeed. |
| Live-fill slippage and actual fees | Unknown for target window | Parser and settlement use Coinbase terminal fill, average price, and actual `total_fees`; no target fills supplied. |
| Missed exits / stop-loss / take-profit | Confirmed code path, unknown outcome | `updateMarkToMarketLocked` evaluates stop/take-profit and opposite/age exits; exchange acceptance/fills/runtime sequence unknown. |
| Accounting/attribution error | Not established by static trace | Gross PnL and fees are stored separately; managed/inherited/liquidation rows are classified. Requires reconciliation against Coinbase fills and persisted rows for a real window. |
| Legitimate market outcome | Unknown | No live realized-PnL dataset was available. |

## Required runtime evidence to close the investigation

Capture one reproducible window with session ID and UTC bounds, then correlate by symbol/signal ID/order ID:

- selected `symbols`, `requested_symbol_count`, `quote_attempted_symbol_count`, `quote_success_symbol_count`, `quote_skipped_symbol_count`, current batch, fetch milliseconds, request rate, and warning logs;
- persisted `order_book_signals.signal_data` including signal strength, imbalance, spread, expected return, fee-adjusted expected return, required edge, data status, execution blocker, and executable-intent flag;
- blocker counts by symbol and bucket, submitted `live_coinbase_orders` status transitions, Coinbase terminal status/fill size/value/average price/total fees;
- `individual_trades` rows including `trade_type`, `is_closing_leg`, gross `pnl`, and `fees`, plus account snapshots before/after settlement;
- positive/negative/zero-PnL counts, after-fee average win/loss/expectancy, profit factor, drawdown, and comparison against paper/live-parity mode over the same quote inputs where possible.

Until this data exists, the no-positive-realized-PnL observation is not confirmed or disproved by source inspection alone.

## Safe follow-up recommendations

1. Capture and persist the runtime window above before changing gates or sizing. This has the highest diagnostic value and preserves safety behavior.
2. Reconcile every accepted order to a terminal Coinbase fill and `individual_trades` row; separately report blocked intents and widget-only placeholders.
3. Bucket outcomes by signal direction/strength/expected-return/required-edge/spread and distinguish gross PnL from fee-adjusted PnL before considering calibration changes.
4. If an implementation change is later justified, create a separate high-risk implementation item. Preserve fail-closed startup, spot-only sell restrictions, min-notional, cash, pending-order, and max-position gates; require independent review and exact-SHA GitHub Actions Docker Build Validation before closure.

## Verification performed

- Source searches and line-numbered reads across live service, exchange fill parser, sizing policy, stats calculator/service, API controller, and frontend universe/payload paths.
- No local build, Docker build, CMake build, or live-account test was run, consistent with the remote-CI/read-only investigation constraints.
- The only repository change is this documentation report; it does not alter live-account behavior.
