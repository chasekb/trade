# Live-Parity Paper Simulation Contract

> Implementation contract for a distinct paper mode that reuses Coinbase public market data and live execution gates without placing Coinbase orders.

**Status:** implementation-ready specification
**Scope:** backend simulation service, persistence/reporting, API payloads, simulated-trading frontend, and regression tests

## 1. Goal and non-negotiable safety rules

Add a paper-live execution mode while preserving the existing synthetic simulator. The mode must make signal quality, live-market-data availability, execution blockers, paper fills, and accounting distinguishable in storage and API responses.

The paper-live mode:

- uses the same Coinbase public order-book/quote path as live trading;
- uses the selected symbol universe exactly as supplied by the user;
- applies live-compatible spot, minimum-notional, cash, position-count, pending-intent, ML/profitability, and other preflight gates;
- creates local paper fills and local paper positions only;
- never calls Coinbase order submission, never creates an exchange order, and never enables the live execution flag;
- fails closed when a quote/order-book fetch is unavailable; it must not call synthetic-price generation as a fallback;
- keeps synthetic simulation behavior unchanged, including its synthetic price/imbalance generator and legacy short-capable behavior;
- exposes enough provenance for an operator to prove which mode, data source, gates, and accounting path produced every row.

This is a paper execution mode, not a third live-account mode. It must not read or write Coinbase account holdings, balances, or live-order recovery state.

## 2. Canonical mode names and compatibility

Use these canonical values:

| Field | Synthetic paper | Live-data paper | Real Coinbase execution |
|---|---|---|---|
| `execution_mode` / session `mode` | `simulated` | `live_parity` | `live` |
| `market_data_source` | `synthetic` | `coinbase_public` | `coinbase_public` |
| persisted `trade_type` for fills | `simulated` | `live_parity_paper` | `live` |
| `execution_is_paper` | `true` | `true` | `false` only after explicit confirmation |
| order submission allowed | no | no | yes, after all live gates |

`live_paper` is not a second spelling to add. Existing rows with `trade_type = live_paper` are legacy compatibility rows and must remain readable; new live-parity rows use `live_parity_paper`. Existing request aliases remain accepted:

- `parameters` is canonical; `strategy_params` remains an input alias;
- `execution_mode` may be top-level or under `parameters`, with top-level taking precedence;
- `/api/trading/simulated/start` remains canonical for both simulated modes, with the legacy `/api/simulated-trading/start` route retained;
- `mode=simulated` on status and signal endpoints remains the simulated-service selector. The response `mode` identifies `simulated` or `live_parity`.

Reject unknown execution modes with HTTP 400. Do not reinterpret an omitted mode as `live_parity`; omitted mode remains `simulated`.

## 3. Start request contract

The canonical start payload is:

```json
{
  "mode": "simulated",
  "execution_mode": "live_parity",
  "strategy": "ml_enhanced_orderbook",
  "strategy_type": "ml_enhanced_orderbook",
  "symbols": ["BTC-USD", "ETH-USD"],
  "parameters": {
    "execution_mode": "live_parity",
    "position_size_mode": "dollar",
    "position_size_value": 100,
    "max_positions_per_session": 4,
    "confidence_threshold": 0.6,
    "fallback_to_baseline": false,
    "round_trip_fee_percent": 1.5,
    "slippage_buffer_percent": 0.2,
    "min_orderbook_signal_strength": 0.35,
    "minimum_net_pnl_usd": 0.5,
    "stop_loss_percent": 0,
    "take_profit_percent": 0
  },
  "max_positions": 4,
  "position_update_interval": 5,
  "immediate_start": true
}
```

For `live_parity`, synthetic capital fields (`initial_portfolio_size`, `initial_balance`, `capital`) are invalid and must be rejected or stripped before the service can start. The paper ledger requires an explicit virtual starting capital field, with the existing default of USD 10,000 retained for backward-compatible UI behavior. The implementation must name this as virtual/paper capital in the response; it must never be presented as Coinbase cash.

For `simulated`, preserve current payload behavior, including default virtual capital and all existing aliases.

## 4. Signal and execution-analysis fields

Every persisted signal and API signal response must retain the existing fields and add/standardize these fields in `execution_analysis`:

```json
{
  "strategy": "ml_enhanced_orderbook",
  "symbol": "BTC-USD",
  "signal_generated": true,
  "intended_action": "open",
  "intended_side": "buy",
  "strength_bucket": "strong",
  "expected_return_bucket": "positive_low",
  "expected_return": 0.012,
  "fee_adjusted_expected_return": 0.006,
  "required_edge": 0.004,
  "diagnostic_factor": "fee_adjusted_expected_return",
  "allocated_usd": 100,
  "minimum_notional": 1,
  "available_cash": 10000,
  "estimated_fee": 0.05,
  "data_status": "sufficient",
  "executable_intent": true,
  "blocked": false,
  "blocker_reason": "paper_fill"
}
```

`signal_generated=false` is a hold/no-signal observation, not a blocked trade intent. It may use `blocker_reason=no_signal` for display, but it must not increment blocked-intent totals. A generated signal that fails any preflight gate is a blocked intent and must include exactly one stable reason from the controlled set:

- `market_data_unavailable` (only when an explicit signal observation is emitted for an unavailable quote);
- `profitability_gate`;
- `ml_confidence_gate`;
- `account_position_management_disabled` (live only; not paper-live);
- `existing_position`;
- `pending_order`;
- `max_positions`;
- `nonpositive_position_size_or_price`;
- `below_minimum_notional`;
- `spot_cannot_open_short`;
- `insufficient_cash`;
- `live_execution_disabled` (real-live only; never paper-live);
- `paper_fill` for an accepted paper intent;
- `would_submit_order` for a real-live intent that passed preflight.

For `live_parity`, `paper_fill` is the only successful intent reason. `executable_intent=true` means “would be accepted as a local paper fill,” never “an exchange order was sent.”

If no quote is available, the preferred behavior is no signal row and no execution count for that symbol on that tick, while `market_data[symbol]` records the failure. If an explicit unavailable-data signal row is required for UI coverage, it must have `data_status=unavailable`, `signal_generated=false`, `executable_intent=false`, and must not use synthetic price, imbalance, spread, or volume values.

## 5. Market-data boundary and worker behavior

`SimulatedTradingService::workerLoop`, `fetchLiveQuotes`, `generateTickLocked`, and `buildSignalRecordLocked` are the primary boundary. `usesLiveMarketData("live_parity")` must remain true. The live-parity path must:

1. snapshot the selected symbols;
2. fetch Coinbase public order books using the same retry/error classification as live trading;
3. update per-symbol `market_data_status` with `refreshed`/`failed`, category, error, retry count, and last successful timestamp;
4. pass only valid live quotes into signal construction;
5. skip a symbol entirely when its quote is invalid or missing;
6. never enter the synthetic `else` branch in `buildSignalRecordLocked` for `live_parity`;
7. continue processing other selected symbols when one quote fails;
8. keep the full selected universe and existing no-hard-cap fan-out policy.

Tests must inject/fake quote results at the exchange-client boundary rather than relying on live Coinbase network access. Fixtures must cover valid bid/ask/depth/imbalance, one-symbol failure, all-symbol failure, retryable failure, and non-retryable TLS/DNS/HTTP failure. Assertions must prove synthetic price generation was not called and no fill is created from a missing quote.

## 6. Execution preflight and paper-fill contract

Refactor or factor shared preflight logic so live and live-parity evaluate the same safety inputs without sharing side effects. The result should carry:

- `allowed`: whether the intent passes;
- `blocker_reason` and human-readable `blocker_detail`;
- `side`, `quantity`, `notional`, `estimated_fee`, and `available_cash`;
- `minimum_notional`, `position_count`, and `pending_intent` facts;
- `execution_mode`, `market_data_source`, and `fill_mode`.

For `live_parity`:

- entry and add intents passing preflight immediately create a local paper position/fill;
- close intents create a local paper closing fill using the live quote path and paper ledger;
- fee and slippage assumptions are explicit and identical to the configured paper policy, not Coinbase-confirmed fees;
- no `CoinbaseAdvancedClient::placeMarketOrder`, `dispatchOrders`, `pending_live_orders`, client order IDs, account snapshot fetch, or order persistence path is invoked;
- pending paper intents are optional only if asynchronous paper-fill behavior is introduced; if introduced, they must be separately identified as `paper_pending` and never share live order IDs.

For `simulated`, preserve current synthetic execution and accounting. For `live`, retain explicit confirmation and all existing exchange-fill reconciliation behavior.

## 7. Persistence model and migration

Current shared tables are `order_book_signals` and `individual_trades`, created/altered in both `SimulatedTradingService::ensureSchema` and `LiveTradingService::ensureSchema`. The current implementation stores execution analysis inside `signal_data` and uses `trade_type` for fill provenance, but does not persist blocked intents as first-class rows. Implement the following minimal migration:

### Signals

Keep existing columns and JSON payload compatibility. Add nullable columns only if query/reporting needs them:

- `execution_mode TEXT`;
- `market_data_source TEXT`;
- `data_status TEXT`;
- `execution_blocked BOOLEAN`;
- `blocker_reason TEXT`;
- `executable_intent BOOLEAN`.

For legacy rows, these columns must remain nullable. Do not use `NOT NULL DEFAULT FALSE` where NULL is needed to distinguish old rows from explicit new values. Backfill only new rows; do not invent blocker semantics for historical JSON.

### Paper fills

Keep `individual_trades` as the fill/outcome table. New live-parity fills use:

- `trade_type = live_parity_paper`;
- `is_closing_leg` set correctly for exits;
- `fees` equal to the configured paper estimate;
- `signal_reason` retaining the source reason;
- prediction-time ML values copied from entry, never derived from outcome.

### Blocked intents

Do not insert blocked intents into `individual_trades`; doing so would corrupt trade counts, PnL, fees, win rate, and expectancy. Add a separate `execution_intents` table (or an equivalent migration-owned table) with:

- `intent_id` primary key;
- `session_id`, `symbol`, `timestamp`, `execution_mode`, `market_data_source`;
- `strategy_type`, `signal_id`, `signal_type`, `side`;
- `strength`, `expected_return`, `fee_adjusted_expected_return`, `required_edge`;
- `requested_notional`, `estimated_fee`, `available_cash`;
- `status` (`blocked`, `paper_filled`, `submitted`, `pending`, `rejected`, `cancelled`);
- `blocker_reason`, `blocker_detail`;
- `fill_trade_id` nullable;
- `created_at`.

A generated signal creates one intent row only when it reaches execution preflight. A hold does not. A paper fill updates the intent status to `paper_filled` and links the resulting trade. A blocked row remains blocked forever. A real-live accepted order is `submitted`/`pending` until exchange reconciliation updates it.

If a separate table is deferred, the implementation must at minimum persist blocked-intent counters and complete blocker payloads in a session diagnostics table without adding blocked rows to `individual_trades`; the separate table is preferred because it supports reconciliation and deduplication.

## 8. Accounting and summary contract

The paper ledger must expose distinct virtual accounting fields:

- `initial_capital` / `virtual_initial_capital`;
- `cash_balance` / `virtual_cash_balance`;
- `available_balance_usd`;
- `pending_reserved_cash`;
- `total_positions_value` (signed);
- `total_positions_exposure` (absolute);
- `realized_pnl`, `unrealized_pnl`, `net_pnl`, `total_fees`;
- `open_positions_count`, `pending_order_count`;
- `execution_mode`, `execution_is_paper`, `market_data_source`;
- `paper_fill_count`, `blocked_intent_count`, `signals_evaluated`, `signals_generated`, `executable_order_intent_count`;
- `execution_blocker_counts`;
- `market_data` per-symbol status and failure list.

`stats` retains the canonical fields already emitted by `calculateTradingStats`: `total_pnl`, `total_fees`, `net_pnl`, `win_rate` (0–100), trade counts, average win/loss, profit factor, per-trade Sharpe, dollar max drawdown, volume, average size, today count, and last trade time. `total_fees` is the aggregate fee field; do not add per-trade fees to it a second time.

Stats filters must treat `live_parity_paper` independently from `simulated` and `live`. The existing `TradingStatsFilter.trade_type` and `session_id` query path must accept the new value. Execution reconciliation must join/aggregate intents and fills by `fill_trade_id`/`signal_id`, so blocked intents affect conversion and blocker metrics but never PnL or trade denominators.

## 9. API response shape

`GET /api/simulated-trading/status` and its `/api/trading/simulated/status` alias should return the existing envelope plus:

```json
{
  "mode": "live_parity",
  "execution_mode": "live_parity",
  "execution_is_paper": true,
  "market_data_source": "coinbase_public",
  "fill_mode": "paper",
  "coinbase_order_submission_enabled": false,
  "virtual_capital": true,
  "portfolio": { "...": "existing portfolio fields" },
  "stats": { "...": "canonical stats fields" },
  "order_book_signal_diagnostics": {
    "...": "existing diagnostics",
    "data_source": "coinbase_public",
    "blocked_intents": 3,
    "paper_fills": 2,
    "execution_blocker_counts": { "spot_cannot_open_short": 3 }
  },
  "recent_trades": [
    {
      "trade_type": "live_parity_paper",
      "execution_mode": "live_parity",
      "fill_mode": "paper",
      "is_closing_leg": false
    }
  ],
  "blocked_intents": [
    {
      "intent_id": "...",
      "status": "blocked",
      "blocker_reason": "below_minimum_notional",
      "execution_mode": "live_parity",
      "market_data_source": "coinbase_public"
    }
  ]
}
```

Keep `trades` and `recent_trades` aliases. Keep `mode=simulated` as the request selector used by existing hooks; use response `mode=live_parity` so the frontend can label the active session correctly. Do not expose Coinbase account balances or pending exchange orders in a paper response.

## 10. Frontend contract and touchpoints

The simulated panel already has an execution selector in `frontend/components/dashboard/SimulatedTradingPanel.tsx` and sends `parameters.execution_mode`. Preserve that control, but make the state and types explicit:

- `TradingExecutionMode = 'simulated' | 'live_parity'`;
- `TradingStatusPayload.mode` accepts both values;
- `buildStartTradingPayload` preserves `execution_mode` and only strips synthetic capital for real `live`, not for `live_parity` virtual capital;
- `apiClient.startTrading('simulated', ...)` remains the only start call for both simulated modes;
- synthetic local fallback is permitted only for `execution_mode=simulated`; live-parity must return the backend/network error and never silently fallback to local synthetic data;
- stop/status/query keys must continue using the simulated service selector while display labels use the response execution mode;
- WebSocket status types must allow `live_parity` and carry `execution_mode`, `market_data_source`, `execution_is_paper`, and blocker counts when supplied;
- normalize optional fields with `??`, preserving legitimate zeros.

Update `frontend/types/trading.ts`, `frontend/lib/api.ts`, `frontend/hooks/useTrading.ts`, `frontend/hooks/useWebSocket.ts`, and the simulated panel as needed. Add visible labels for “Synthetic simulation” and “Coinbase live-data paper mode,” plus a persistent warning that no Coinbase orders are submitted. Display quote failures as unavailable/data errors, not as zero prices or generated synthetic signals. Show paper fills and blocked intents separately in tables or summary cards; do not label blocked intents as trades.

## 11. Concrete implementation workstreams

### Backend worker

Touchpoints:

- `include/trading/SimulatedTradingService.hpp`: mode/fill provenance, intent/preflight records, paper diagnostics, and response helpers.
- `src/trading/SimulatedTradingService.cpp`: mode validation, live-parity quote boundary, shared preflight, paper fill provenance, blocked-intent persistence, schema migration, status/diagnostics.
- `include/trading/LiveTradingService.hpp` and `src/trading/LiveTradingService.cpp`: extract or mirror only pure preflight contracts; preserve real order dispatch and account reconciliation unchanged.
- `include/trading/TradingStatsService.hpp`, `src/trading/TradingStatsService.cpp`, and `src/api/PredictController.cpp`: new trade type/filter and response fields.
- `include/trading/ExecutionReconciliation.hpp`, `src/trading/ExecutionReconciliation.cpp`: intent/fill conversion and blocker metrics.
- `src/exchange/CoinbaseAdvancedClient.cpp` / header: test seam or injectable public quote client; do not add order calls to paper mode.
- `CMakeLists.txt`: include any new source/test target.

### Frontend worker

Touchpoints:

- `frontend/components/dashboard/SimulatedTradingPanel.tsx`;
- `frontend/lib/api.ts`;
- `frontend/hooks/useTrading.ts` and `frontend/hooks/useWebSocket.ts`;
- `frontend/types/trading.ts`;
- `frontend/components/dashboard/OrderBookSignalsTable.tsx`, `RecentTradesTable.tsx`, and `ExecutionReconciliationTable.tsx` for provenance and blocked-intent display;
- `frontend/lib/startTradingPayload.test.ts`, relevant panel/hook tests, and normalization tests.

### Test/QA worker

Add focused tests under `src/tests/` and `frontend/` for the acceptance cases below. Backend tests must use quote fixtures/test doubles; frontend tests must mock API responses and prove no local synthetic fallback for live-parity.

## 12. Acceptance cases

### Backend safety and mode separation

- [ ] Omitted execution mode starts `simulated` and produces synthetic quotes as before.
- [ ] Explicit `simulated` starts only the synthetic generator and persists `trade_type=simulated`.
- [ ] Explicit `live_parity` fetches Coinbase public order-book fixtures and persists `trade_type=live_parity_paper` for fills.
- [ ] `live_parity` never invokes Coinbase order submission, never creates a client order ID, and leaves `pending_live_orders` empty.
- [ ] `live` still requires credentials, account snapshot, and explicit `live_order_execution=true`; its existing order/fill reconciliation remains intact.
- [ ] Unknown mode returns HTTP 400; a live session cannot be taken over by a simulated/live-parity session.

### Live-data fail-closed behavior

- [ ] A valid quote drives price, spread, bid/ask, depth, volume, and imbalance in the signal.
- [ ] A failed quote produces a visible per-symbol failure with category/retries/error and no signal/fill based on synthetic values.
- [ ] All quote failures produce zero generated signals, zero paper fills, and no fabricated portfolio movement.
- [ ] A partial universe continues valid symbols without dropping the selected universe or silently capping it.
- [ ] Retryable and non-retryable fetch errors retain the specified retry/category semantics.

### Gates, intent persistence, and accounting

- [ ] Below minimum notional, spot short, insufficient cash, max positions, pending intent, ML gate, and profitability gate each create a blocked intent with the stable reason.
- [ ] Hold/no-signal observations do not create blocked-intent rows or inflate blocker totals.
- [ ] An allowed live-parity entry creates one paper fill, one linked intent, one paper position, and the expected estimated fee; it does not change Coinbase state.
- [ ] A live-parity close creates a closing paper fill with entry prediction values and removes only the local paper position.
- [ ] Blocked intents are absent from `individual_trades`, stats trade counts, PnL, fees, win rate, and expectancy denominators.
- [ ] `live_parity_paper` stats are filterable independently from synthetic and real-live rows.
- [ ] Restart/status recovery never treats paper fills as exchange pending orders and preserves legacy nullable classifications.

### API and frontend

- [ ] Start payload preserves selected symbols and `execution_mode=live_parity`.
- [ ] Status response labels mode/data source/fill mode and exposes paper-vs-blocked counts.
- [ ] Frontend displays the live-data paper warning and active mode from backend response.
- [ ] Frontend displays quote failures as unavailable and never substitutes local synthetic signals for live-parity.
- [ ] Frontend distinguishes paper fills from blocked intents and preserves zero-valued accounting fields.
- [ ] Existing synthetic local fallback tests still pass and do not run for live-parity.
- [ ] Existing live payload tests still prove synthetic capital is not sent to the real-live endpoint.

## 13. Verification and closeout

Backend workers must run the focused C++ tests in remote CI only; no local CMake/Docker build is authorized by the project workflow. Frontend workers must use the repository's remote CI path rather than local package builds unless a task explicitly authorizes local execution. Before closeout, verify:

- exact pushed SHA and every required GitHub Actions job;
- focused backend quote/mode/persistence tests and frontend payload/status/fallback tests;
- `git diff --check` and clean intended working tree;
- an evidence payload showing at least one synthetic session, one live-parity quote failure, one blocked intent, and one paper fill with no Coinbase order side effect.

The implementation is not complete if only the selector or payload exists, if blocked intents are inferred only from in-memory counters, if a live-parity quote failure falls through to synthetic generation, or if green CI is reported from an older SHA.
