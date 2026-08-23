# Fill, realized-PnL, and attribution trace — 2026-08-23

## Scope and verdict

This is a source-level trace of the live, live-parity, synthetic-simulated, persistence, API, and frontend reporting paths. No production behavior, account state, order, or database row was changed. No live or replay data was available in the repository or `~/.hermes`; therefore runtime fill-to-ledger reconciliation remains unverified.

The core simulated accounting identity is covered and internally coherent. The live path has explicit order recovery and fail-closed settlement behavior, but its accounting/reporting contract has material gaps: live fills are not linked to the persisted order record, actual execution slippage is not recorded, and mixed inherited/session-managed closes can suppress realized PnL for the managed slice. These are classified below rather than treated as legitimate market outcomes.

## End-to-end event ordering

### Live Coinbase execution

1. `LiveTradingService::workerLoop()` fetches public order books, then `generateTickLocked()` builds a signal and `buildEntryExecutionAnalysisLocked()` classifies blockers before any order intent (`src/trading/LiveTradingService.cpp:2226-2303`, `:1840-1928`).
2. `openPositionLocked()`, `addToPositionLocked()`, `closePositionLocked()`, or `liquidateCoinbaseHoldingLocked()` creates an `OrderIntent`, reserves cash, and inserts the symbol into `pending_order_symbols_` (`src/trading/LiveTradingService.cpp:1991-2049`, `:2051-2102`, `:2104-2151`, `:2154-2223`). Live entry/close requires `live_order_execution=true`; spot entries are buy-only.
3. `dispatchOrders()` first inserts a durable `live_coinbase_orders` row with status `submitting`, then calls `CoinbaseAdvancedClient::placeMarketOrder()` with a random client order id (`src/trading/LiveTradingService.cpp:1035-1103`; schema at `:386-402`). A definitive rejection marks the row `rejected` and releases reservations. An inconclusive response retains a pending order.
4. Coinbase acceptance is not treated as a fill. `placeMarketOrder()` polls historical order details five times, then returns acceptance with fill details pending (`src/exchange/CoinbaseAdvancedClient.cpp:339-372`).
5. `resolvePendingLiveOrders()` resolves missing order ids by client id, polls `getOrderFill()`, applies the aggregate terminal fill once, flushes the trade row, marks the durable order terminal, and refreshes the Coinbase account snapshot (`src/trading/LiveTradingService.cpp:1106-1205`). Complete-not-found is retried 30 times before marking `not_found` and releasing reservations; inconclusive lookups remain pending.
6. `parseOrderFill()` accepts terminal `FILLED`, `CANCELLED`, `EXPIRED`, or `FAILED` orders, validates non-negative numeric fields, and requires positive filled value, average price, and actual fees whenever `filled_size > 0` (`src/exchange/CoinbaseOrder.cpp:53-108`). Thus a terminal cancellation with a positive partial aggregate is eligible for settlement; a terminal zero-fill outcome emits no `individual_trades` row (`src/trading/LiveTradingService.cpp:654-663`).
7. `applyLiveFillLocked()` uses `filled_size`, `average_filled_price` (or `filled_value / filled_size`), `filled_value`, and `total_fees`; creates one trade record; updates position state; increments `realized_pnl_` by gross close PnL and `total_fees_` by actual fees; then queues the trade for persistence (`src/trading/LiveTradingService.cpp:654-857`).

### Simulated and live-parity execution

`SimulatedTradingService::generateTickLocked()` evaluates each signal, attaches `execution_analysis`, and either paper-fills or records a blocker (`src/trading/SimulatedTradingService.cpp:1732-1810`). Synthetic simulation uses the generated signal price and supports synthetic long/short accounting. `live_parity` uses Coinbase public quotes but settles locally and applies spot-only, minimum-notional, cash, pending, and ML/profitability gates (`src/trading/SimulatedTradingService.cpp:518-601`, `:1470-1559`). It never submits an exchange order.

For non-live execution, opening and adding a position apply `openCashDelta()` and an estimated `kFeeRate` fee; closing applies `closeCashDelta()`, computes gross PnL and net PnL, and writes a closing leg (`src/trading/SimulatedTradingService.cpp:1470-1559`, `:1562-1637`, `:1639-1729`). The shared accounting helpers are in `include/trading/PortfolioAccounting.hpp:10-70`.

## Schemas and reporting surfaces

- `order_book_signals`: signal metadata plus `signal_data` JSON containing `execution_analysis`, spread, bid/ask, mid, imbalance, depth, and volume (`src/trading/LiveTradingService.cpp:334-353`; simulated schema `src/trading/SimulatedTradingService.cpp:316-335`).
- `individual_trades`: `trade_id`, session, symbol, side, size, execution price, epoch timestamp, strategy, signal reason, gross `pnl`, per-leg `fees`, prediction-time ML values, `trade_type`, and nullable `is_closing_leg` (`src/trading/LiveTradingService.cpp:355-381`, `:1459-1502`). Existing rows with `FALSE` and nonzero PnL are migrated to NULL; NULL falls back to the legacy nonzero-PnL closing-leg convention in reconciliation.
- `live_coinbase_orders`: client/order ids, intent amount and unit, action, reserved cash, serialized signal/position snapshots, status, and update time. It does not contain filled size, filled value, average fill price, actual fees, terminal fill status details beyond the status string, or a foreign key/order link to `individual_trades` (`src/trading/LiveTradingService.cpp:386-402`).
- `TradingStatsService::getTradingStats()` reads all matching `individual_trades`, without selecting `is_closing_leg`, and `calculateTradingStats()` sums stored gross PnL and fees, then derives `net_pnl = total_pnl - total_fees` (`src/trading/TradingStatsService.cpp:94-150`; `src/trading/TradingStatsCalculator.cpp:81-153`). Live session status excludes `live_account_managed_add`, `live_account_managed_close`, and `live_liquidation` (`src/trading/LiveTradingService.cpp:2598-2622`).
- `PredictController::executionReconciliation()` reads signal JSON and trade rows over a time window, applies session/trade-type filters, infers legacy closing legs, and computes `realized_pnl = gross_pnl - fees` for closing legs (`src/api/PredictController.cpp:1673-1803`). `ExecutionReconciliation.cpp` excludes open legs from win/loss denominators but accumulates their fees (`src/trading/ExecutionReconciliation.cpp:26-113`).
- Live portfolio JSON exposes account cash, pending reservations, signed and absolute position values, gross `realized_pnl_`, `net_pnl = total_value - initial_capital_`, `total_fees_`, positions, and recent trades (`src/trading/LiveTradingService.cpp:2446-2523`). The frontend normalizer preserves backend fee totals and derives `net_pnl` only when the backend omits it (`frontend/lib/simulatedTradingStats.ts:253-325`).

## Economics and sizing

- Live order-book inputs record best bid, best ask, mid, and absolute spread; gating uses spread/mid, configured round-trip fee fraction, and configured slippage buffer (`src/trading/LiveTradingService.cpp:1540-1579`, `:1733-1768`). Defaults include `kFeeRate=0.0005`, round-trip gate fraction `0.015`, and slippage buffer `0.002` (`src/trading/LiveTradingService.cpp:38-53`). The execution fee is not assumed at settlement: `fill.total_fees` is used.
- Simulated fills use the signal/current price, not bid/ask execution, and use the fixed `kFeeRate` path. Spread and slippage are used for gating/sizing, not realized fill economics (`src/trading/SimulatedTradingService.cpp:1470-1559`, `:1639-1729`; `src/trading/PositionSizingPolicy.cpp:48-99`).
- Percent sizing compounds from current cash plus signed positions value, with a fallback to initial capital if equity is non-positive (`include/trading/PortfolioAccounting.hpp:34-41`; live `src/trading/LiveTradingService.cpp:409-479`; simulated `src/trading/SimulatedTradingService.cpp:396-486`). Cash gates subtract pending reservations and include buy fees (`PortfolioAccounting.hpp:43-49`).
- Coinbase market buys are quote-sized; closes/liquidations are base-sized. Generated quote orders and inherited-holding liquidation are guarded by the $1 minimum (`src/exchange/CoinbaseOrder.cpp:15-50`; live `:2012-2047`, `:2187-2223`).

## Findings by classification

### Accounting/attribution — high: mixed inherited/session close suppresses managed PnL

`applyLiveFillLocked()` sets `inherited_close = position.inherited_quantity > 1e-12` and then sets `gross_pnl = 0.0` for the entire close, not only the inherited quantity (`src/trading/LiveTradingService.cpp:711-725`). A position that contains both inherited quantity and session-added quantity can therefore close the session-managed slice while any inherited quantity remains and have all closing PnL labeled `live_account_managed_close` and excluded from session stats (`:723-730`, `:614-621`, `:2614-2621`).

Impact: realized PnL, average win/loss, expectancy, and outcome coverage can be understated or discarded for mixed positions. This is not a market outcome. Required evidence/fix scope: reproduce a mixed holding with `inherited_quantity > 0`, a managed add, and a partial close; assert separate basis/quantity/PnL attribution for inherited versus session-managed slices.

### Accounting/attribution — medium: live in-memory cash is snapshot-dependent after settlement

For fresh live fills, `applyLiveFillLocked(..., account_snapshot_reflects_fill=false)` updates positions and PnL but does not apply an open/close cash delta; it relies on the subsequent Coinbase snapshot refresh (`src/trading/LiveTradingService.cpp:654-857`, `:1195-1204`). If that snapshot fails, status can expose updated positions and fees while `cash_`, total value, and available cash remain stale. Recovery explicitly marks the snapshot as reflecting the fill (`:1022-1027`), so restart and fresh-settlement paths have different transient accounting semantics.

Impact: displayed cash/available balance and total value can disagree with persisted fills until a later successful snapshot. Classification is accounting/attribution; missing evidence is a runtime trace with snapshot failure after a known fill.

### Accounting/attribution — medium: portfolio realized PnL is gross while reconciliation is net

Live `realized_pnl_` is incremented by gross price-difference PnL (`src/trading/LiveTradingService.cpp:717-730`), while `total_fees_` is separate. The live portfolio reports that gross value as `realized_pnl` (`:2497-2500`); the reconciliation endpoint instead reports closing-leg `gross_pnl - fees` (`src/api/PredictController.cpp:1776-1786`), and stats exposes gross `total_pnl` plus net `net_pnl` (`src/trading/TradingStatsCalculator.cpp:102-133`). The labels are not explicit enough to prevent an operator comparing portfolio `realized_pnl` to reconciliation `total_pnl` from assuming the same basis.

Impact: frontend tiles can show a gross realized number while expectancy/reconciliation is after-fee. This is a reporting contract mismatch, not a fee double-count in the canonical stats calculation. Evidence needed: representative API payload captured from the same session and compared field-by-field.

### Fill slippage — unknown/evidence gap: no execution-vs-quote attribution

Live fills correctly use Coinbase `average_filled_price`, `filled_value`, and actual `total_fees` (`src/exchange/CoinbaseOrder.cpp:10-17`, `src/trading/LiveTradingService.cpp:665-685`). However, `individual_trades` stores no order id, quote bid/ask/mid snapshot id, or slippage fields. Signal rows contain the pre-submit quote, but there is no durable join from a fill to the exact signal/order row (`src/trading/LiveTradingService.cpp:335-353`, `:1465-1500`).

Consequently, realized price is authoritative for PnL, but realized spread capture, adverse selection, and slippage cannot be calculated from stored records. Missing evidence: a live/replay sample containing order-book snapshot, client/order id, terminal fill response, and resulting trade row.

### Trading economics — legitimate model limitation: paper fills do not model bid/ask or realized slippage

Synthetic and live-parity paper fills use the modeled signal price and fixed fee rate; spread/slippage only affect the pre-trade hurdle and sizing. This is a legitimate simulation-model limitation, not a live fill bug, but paper expectancy is not execution-realistic (`src/trading/SimulatedTradingService.cpp:1470-1559`, `:1639-1729`). A parity closeout must not claim live fill economics from synthetic results.

### Sizing — covered, with test evidence

Sizing is current-equity based and cash-gated; pending reservations are subtracted before a new intent, and buy fees are included. The shared helper and deterministic tests cover long/short cash deltas, signed position value, exposure, cash sufficiency, sizing fallback, and managed sell quantity (`include/trading/PortfolioAccounting.hpp:17-56`; `src/tests/test_portfolio_accounting.cpp:22-158`). No source mismatch was found in this slice.

### Frontend artifact — medium: recent trade display omits explicit closing-leg marker

Both C++ `tradeToJson()` serializers emit id, side, quantity, price, gross `pnl`, fees, and trade type but omit `is_closing_leg` (`src/trading/LiveTradingService.cpp:545-564`; `src/trading/SimulatedTradingService.cpp:604-623`). The database and reconciliation layer retain the flag, but dashboard recent-trade consumers cannot distinguish opening zero-PnL legs from exact-flat closing legs based on the API row alone. This can mislead manual attribution even though backend reconciliation has the correct flag.

### Legitimate/covered behavior — terminal/recovery and exact-flat handling

The order state machine distinguishes acceptance from fill, persists intent before submission, retains inconclusive orders, releases reservations on definitive rejection/not-found, and uses actual terminal fill fees. Exact-flat closes remain closing legs when `is_closing_leg=true`, and the reconciliation test verifies that fees make them fee-negative losers (`src/tests/test_execution_reconciliation.cpp:170-178`).

## Tests, fixtures, replay, and logs

Relevant deterministic tests are `src/tests/test_coinbase_order.cpp` (fill parsing, partial positive fill, terminal rejection, malformed numeric fields, minimum quote size), `src/tests/test_portfolio_accounting.cpp` (cash/position identity and sizing), `src/tests/test_trading_stats_calculator.cpp` (gross/net stats), `src/tests/test_execution_reconciliation.cpp` (blockers, coverage, exact-flat closes), and `src/tests/test_strategy_signal.cpp` (fee/spread/slippage gates). No fill replay harness or persisted exchange-fill fixture was found under `src/tests`, `data`, or the repository file inventory. `~/.hermes/kanban/boards/trade/logs/t_763420b0.log` contains prior agent tool traces only; it contains no live order/fill payloads. No runtime claim is made from these unit fixtures.

## Closeout requirements

1. Capture a representative paper/live-parity window and, separately with explicit approval, a live terminal fill sample; include signal quote, client/order id, terminal status, filled size/value/average price/fees, position before/after, account snapshot before/after, and persisted rows.
2. Add a mixed inherited/session-managed partial-close fixture and decide the authoritative basis/PnL split before changing production behavior.
3. Add a durable order-to-fill linkage or an explicit reconciliation query/report if slippage attribution is required.
4. Define and document whether portfolio `realized_pnl` is gross or net; keep the API/frontend labels consistent with reconciliation and stats.
5. Preserve the current fail-closed behavior for inconclusive order lookup, missing actual fees/price, minimum notional, and insufficient cash.

## Verification performed

- Source inspection and targeted file searches only.
- `git status --short` was clean before the report was added.
- No local C++/Docker/package build or test command was run, per remote-only Kanban policy.
- No external order, account mutation, or production deployment was performed.
