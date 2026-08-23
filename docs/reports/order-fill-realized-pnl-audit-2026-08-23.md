# Order, Fill, and Realized-PnL Reporting Audit

Date: 2026-08-23
Scope: `src/trading/LiveTradingService.cpp`, `src/trading/SimulatedTradingService.cpp`, `src/trading/TradingStatsService.cpp`, `src/trading/TradingStatsCalculator.cpp`, `src/api/PredictController.cpp`, and the Live Trading/ML dashboard consumers.

This is a source-level audit. No live session, exchange order, database replay, local build, or local test command was run. The repository was clean before this report; `git diff --check` passed after authoring it.

## Evidence chain

1. Selected symbols are stored in `LiveTradingService::startSession` (`src/trading/LiveTradingService.cpp:2191-2199`), serialized in status (`2589-2596`), and used by the worker quote loop. The live worker requests the full selected vector serially; the warning threshold is diagnostic only (`47-53`, `1208-1263`, and the worker loop around `2328-2373`).
2. Signals are persisted to `order_book_signals`; they are not fills. `signalToJson` exposes signal/prediction/diagnostic fields (`517-542`), while order intents are queued only after execution gates pass (`1991-2049`, `2051-2101`).
3. Submitted live orders are separately persisted in `live_coinbase_orders` (`332-402`, `859-918`). Coinbase acceptance is marked `pending` (`921-932`); terminal resolution and fill application happen later. A successful order-create response is therefore not a realized trade.
4. A positive/negative realized result is produced only by a closing fill. In live fills, `applyLiveFillLocked` calculates gross PnL for `close` (`689-745`) and queues a trade record (`852-855`). Opening fills intentionally write `pnl = 0` (`777-850`). Simulated trading follows the same opening/closing-leg split (`678-779`, `1683-1729`).
5. Persisted status statistics read `individual_trades` by session and calculate `TradingStats` (`LiveTradingService.cpp:2585-2655`; `SimulatedTradingService.cpp:2069-2139`). The generic `/api/trades/stats` route instead calls `TradingStatsService` (`PredictController.cpp:614-649`), whose query can be scoped by `trade_type` and `session_id` but has no closing-leg predicate (`TradingStatsService.cpp:94-150`).
6. The ML PnL widget uses a different endpoint, `/api/ml/pnl-trades`, which returns only nonzero PnL rows and no session/trade-type filters (`PredictController.cpp:1497-1545`). The frontend polls it independently (`frontend/hooks/useMLAnalytics.ts:27-42`) and renders top/bottom rows (`frontend/components/dashboard/PnlTradesTable.tsx:49-86`).
7. The Live Trading panel reads the live producer status, normalizes its `stats`, and displays the result alongside Coinbase portfolio tiles (`frontend/components/dashboard/LiveTradingPanel.tsx:285-365`, `394-499`). This is not the same data source as the global ML PnL widget.

## Confirmed findings

### High: mixed inherited/session-managed closes can suppress valid realized PnL

`LiveTradingService::applyLiveFillLocked` sets `inherited_close = position.inherited_quantity > 1e-12` and then sets `gross_pnl = 0.0` whenever that flag is true (`src/trading/LiveTradingService.cpp:711-725`). It does not calculate PnL separately for the session-managed quantity in a mixed position. The code separately computes `managed_closed_quantity` at lines 715-720, so a positive strategy-managed slice can exist but be assigned zero PnL whenever any inherited quantity remains.

The resulting trade is persisted with `pnl = 0`, and `realized_pnl_` is incremented by zero (`730`). `TradingStatsCalculator` counts winners/losers strictly from the stored `pnl` sign (`src/trading/TradingStatsCalculator.cpp:97-119`). Therefore a functioning strategy that adds to an inherited Coinbase holding and later closes while inherited quantity remains can appear to have no positive-PnL trades. This is a real accounting/reporting defect in the mixed-position path.

### Medium: generic stats include opening legs in trade and volume denominators

`TradingStatsService` selects every `individual_trades` row matching optional `trade_type`/`session_id` filters (`src/trading/TradingStatsService.cpp:112-130`) and passes all rows to `calculateTradingStats`. The calculator increments `total_trades`, volume, and fees for every row, including opening rows with `pnl = 0` (`src/trading/TradingStatsCalculator.cpp:97-110`). Winners and losers exclude zero PnL, but `avg_trade_size`, total volume, Sharpe inputs, drawdown sequence, and total-trade count include opens.

This does not erase a positive closing PnL, but it can make the dashboard report a lower-looking win rate, a diluted average trade, and a different risk series than a closing-trade report. The existing test explicitly codifies this behavior (`src/tests/test_trading_stats_calculator.cpp:69-86`), so it is confirmed as a contract/reporting artifact rather than an accidental untested branch.

### Medium: PnL-trades widget and session statistics are divergent views

`/api/ml/pnl-trades` filters to `pnl IS NOT NULL AND pnl <> 0` and returns global top/bottom rows without `session_id` or `trade_type` scoping (`src/api/PredictController.cpp:1531-1539`). The Live Trading panel instead consumes the session-scoped `stats` block from `/api/live-trading/status` via the live producer (`frontend/components/dashboard/LiveTradingPanel.tsx:291-353`). A positive fill can therefore be present in session stats but absent from the widget if it is outside the global top/bottom ten, while unrelated historical rows can appear in the widget. Conversely, a session with only open fills or only zero-PnL/inherited-management rows will have no PnL widget rows by design.

This is a confirmed coverage/interpretation gap, not proof that the exchange fill was missing.

### Medium: a close fill can be dropped if both internal and persisted position context are absent

For a `close` fill, `applyLiveFillLocked` first tries `positions_`, then reconstructs from `intent.position`; if neither is available it logs an error and returns before queuing the trade (`src/trading/LiveTradingService.cpp:689-700`). The pending-order persistence path normally stores `position_json` (`859-907`) and recovery reconstructs it (`963-1019`), which reduces the likelihood. However, malformed/missing state at this boundary causes the exchange fill to disappear from `individual_trades` and from realized-PnL stats. No compensating fill ledger or reconciliation row is written in this failure branch. This remains a confirmed loss-of-reporting path, with runtime frequency unknown.

## Ruled out by source and existing tests

- **Order acceptance being treated as a fill:** Coinbase create handling distinguishes acceptance from execution; the client comments and pending-order state retain the order until a terminal lookup (`src/exchange/CoinbaseAdvancedClient.cpp:349-370`, `src/trading/LiveTradingService.cpp:921-1040`).
- **Opening fills being counted as positive trades:** opening fills explicitly set `pnl = 0`; only closing actions calculate realized PnL (`LiveTradingService.cpp:710-772`, `SimulatedTradingService.cpp:678-772`).
- **Missing quote rows creating orders:** live entry code requires a positive price, minimum notional, spot-compatible buy side, sufficient cash, and explicit live execution (`LiveTradingService.cpp:2012-2048`).
- **Execution reconciliation dropping exact-flat closes:** `ExecutionReconciliation::applyOutcome` counts closing legs independently of PnL sign, and the test covers a zero-gross/fee-negative close (`src/trading/ExecutionReconciliation.cpp:45-58`; `src/tests/test_execution_reconciliation.cpp:170-178`).
- **Portfolio cash sign/quantity identity as the primary cause:** the pure accounting helpers and long/short open-mark-close identity tests cover both directions (`include/trading/PortfolioAccounting.hpp:17-28`; `src/tests/test_portfolio_accounting.cpp:22-77`). This does not validate the mixed inherited/session provenance defect above.
- **Frontend `DataTable` silently truncating the selected universe:** the order-book table receives an already paginated array; the separate coverage audit found pagination is display-only. This audit found no evidence that table pagination itself deletes fills or realized PnL.

## Unknown / requires runtime evidence

- Whether the deployed database contains mixed inherited/session-managed positions at close time, and how often the `inherited_close` branch is reached.
- Whether any production close fill has hit the missing-position early return.
- Whether provider rate limits, quote age, or the unbounded live worker cadence are causing the observed low fill count; source inspection identifies the path but cannot establish runtime frequency.
- Whether the database write retry queues eventually drain after transient PostgreSQL failures; both services requeue writes, but no replay or database inspection was performed.
- Whether the browser currently shows stale or partial order-book rows; the frontend/backend cadence mismatch is source-confirmed, but browser evidence was not collected.
- Actual positive-PnL trade counts, fees, and session/global divergence in the deployed database.

## Focused follow-up recommendations

1. Add a regression fixture for a mixed inherited/session-managed position: close a quantity spanning both components and assert the session-managed portion receives its signed gross PnL while inherited quantity remains excluded.
2. Make the closing-fill record or reconciliation path fail closed: do not silently drop a terminal exchange fill when position context is missing; persist an explicit unexplained outcome containing order ID, symbol, quantity, fees, and reason.
3. Define whether dashboard “trades” means fills or completed closing legs. If it means completed trades, add an explicit closing-leg filter/field to stats and expose session/trade-type filters on `/api/ml/pnl-trades`; otherwise label opening-leg-inclusive metrics clearly.
4. Run a read-only production/replay reconciliation keyed by `client_order_id`/exchange `order_id`, comparing submitted, terminal, filled, persisted-trade, and closing-PnL counts. Do not close runtime/evidence-gated backlog work from green CI alone.

## Verification record

- Read-only source inspection completed across the files listed in the scope.
- `git diff --check`: passed.
- No local build/test/container command run, in accordance with the task's remote-only verification policy.
- No live trading session, exchange request, database write, or external side effect performed.
