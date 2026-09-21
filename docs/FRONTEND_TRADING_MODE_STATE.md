# Frontend trading-mode state and API integration contract

Status: implementation design note for the mode/state integration work

Scope: the Next.js dashboard currently exposes two tabs (`Live Trading` and
`Simulated Trading`). Simulated Trading has a second execution selector:
`simulated` (synthetic) and `live_parity` (Coinbase public market-data paper
mode). Live Trading is the only surface that can submit exchange orders.

## 1. Current repository findings

Primary files:

- `frontend/types/trading.ts`: `TradingMode` is currently only `'live' | 'simulated'`; `OrderBookSignal.execution_analysis` already carries executable/blocked fields; `TradingStats` is the shared summary contract.
- `frontend/lib/api.ts`: request/payload construction, endpoint compatibility fallbacks, local synthetic session, and local synthetic records.
- `frontend/hooks/useTrading.ts`: status polling, start/stop mutations, order-book polling and simulated WebSocket cache updates.
- `frontend/components/dashboard/SimulatedTradingPanel.tsx`: simulated mode selector, configuration, controls, synthetic/live-parity signals, stats, and reconciliation.
- `frontend/components/dashboard/LiveTradingPanel.tsx`: Coinbase readiness gate, explicit live-order confirmation, account-management opt-in, manual execution, live stats and signals.
- `frontend/components/dashboard/TradingControls.tsx`: shared start/stop controls and disabled-start messaging.
- `frontend/components/dashboard/OrderBookSignalsTable.tsx`: signal/diagnostic display.
- `frontend/components/dashboard/RecentTradesTable.tsx`: trade/fill display; fees are optional.
- `frontend/components/dashboard/OpenPositionsSection.tsx`: session/account-managed position display and close/liquidate actions.
- `frontend/components/dashboard/ManualTradeSection.tsx`: direct `POST /api/trading/live/execute`; this is an explicit live side effect and must remain live-only.
- `frontend/lib/simulatedTradingStats.ts`: canonical normalization and derivation boundary for synthetic and backend snapshots.
- `frontend/lib/liveTabProducer.ts`: Coinbase readiness, blockers, errors, positions, pending orders and account snapshot normalization.
- `frontend/lib/executionReconciliation.ts` and `frontend/hooks/useExecutionReconciliation.ts`: blocker-to-outcome diagnostic contract.
- `include/api/PredictController.hpp`: authoritative C++ route list and duplicate simulated start/stop/status compatibility routes.

The backend route list confirms these mode-relevant routes:

- `POST /api/trading/simulated/start` (canonical) and `POST /api/simulated-trading/start` (legacy alias)
- `POST /api/trading/simulated/stop` and `POST /api/simulated-trading/stop`
- `GET /api/simulated-trading/status` and `GET /api/trading/simulated/status`
- `POST /api/trading/simulated/update-strategy-params`
- `GET /api/orderbook/simulated-signals`
- `POST /api/trading/live/start`, `POST /api/trading/live/stop`, `GET /api/trading/live/status`
- `POST /api/trading/live/update-strategy-params`
- `GET /api/orderbook/live-signals`
- `GET /api/live-portfolio/status`
- `GET /api/trading/live/positions`
- `POST /api/trading/live/close-position`
- `POST /api/trading/live/liquidate-holdings`
- `POST /api/trading/live/execute`
- `GET /api/trading/execution-reconciliation`

## 2. Canonical UI mode model

Use an explicit UI mode independent of the backend's two-value trading mode:

```text
TradingTabMode = 'simulated' | 'live'
SimulatedExecutionMode = 'synthetic' | 'live_parity'

SessionMode =
  | { tab: 'simulated'; execution: 'synthetic' }
  | { tab: 'simulated'; execution: 'live_parity' }
  | { tab: 'live'; execution: 'live' }
```

Do not send `live_parity` as the backend `mode`. It remains a simulated
session (`mode: 'simulated'`) with `parameters.execution_mode: 'live_parity'`.
The existing selector calls this value `live_parity`; retain that wire value for
backward compatibility while exposing a typed UI alias if desired.

The backend status response must be normalized to a single frontend snapshot
with these fields (all optional at the wire boundary):

```text
isActive, mode, executionMode, strategy, symbols, sessionId,
source, readiness, blockers, errors, pendingOrders, openPositions,
recentTrades, stats, portfolio
```

Compatibility rules:

1. `mode` accepts `live` or `simulated`; missing mode falls back to the request/tab mode.
2. `executionMode` reads `execution_mode` from the response or nested `parameters`; missing simulated value means `synthetic`.
3. Legacy `is_active`, `is_trading`, and camel-case `isActive` are equivalent.
4. A legacy response with no `execution_mode` is never inferred to be live parity.
5. Synthetic/local records are identified by `source: 'local_synthetic'` or existing local IDs, but continue to satisfy the existing `TradeLike`/`OrderBookSignal` shapes.
6. `status: 'error'` is an error state, not an inactive/empty successful snapshot.

## 3. State machine

The UI should represent these states separately from the session mode:

```text
unavailable
  -> loading (requesting status/readiness)
  -> ready (not active and can start)
  -> blocked (not active; required gate or data unavailable)
  -> starting (POST start pending)
  -> active (backend confirms active)
  -> stopping (POST stop pending)
  -> stopped/ready

starting -> error (start rejected, timeout, malformed response)
active   -> error (polling/WebSocket/API error; retain last known data)
active   -> blocked (backend reports a new execution blocker)
active   -> unavailable (authoritative source cannot be reached and no cached snapshot exists)
```

State rendering requirements:

- `loading`: disable start/stop and show a non-actionable loading label; do not show zero balances as authoritative.
- `unavailable`: show source/endpoint unavailable and retry; do not silently fabricate an inactive live account or zero portfolio.
- `blocked`: show the first actionable blocker and all relevant blocker categories; start must remain disabled. For live, this includes missing credentials, missing account snapshot, producer errors, and the explicit real-order confirmation. For live-parity, explain that no exchange orders are submitted, but public market data and live execution gates still apply.
- `starting`/`stopping`: disable all conflicting controls and show progress; do not optimistically show a fill or position.
- `active`: show the authoritative session mode, source, symbols, session ID where available, last update time, and a stop control.
- `error`: show the server error/message, preserve the last known snapshot if safe, and provide retry. An error response must not be converted into success by a local fallback for live or live-parity.
- `stopped/ready`: show no active positions/trades unless retained historical records are explicitly labeled historical.

## 4. Mode-specific behavior and safety messaging

### Synthetic simulation

- Start: `POST /api/trading/simulated/start` with `parameters.execution_mode` absent or `simulated` and simulated capital fields.
- If `NEXT_PUBLIC_FORCE_LOCAL_SIM_TRADING` is enabled, or the backend start/status path is unavailable, local synthetic simulation is allowed by the existing compatibility contract.
- The fallback must label the source as synthetic/local and must never call a Coinbase execution endpoint.
- Synthetic signals come from `buildSyntheticOrderBookSignals`; synthetic records must remain consumable by `normalizeSimulatedTradingSnapshot`, `RecentTradesTable`, and `OrderBookSignalsTable`.
- The UI should distinguish synthetic fills from real/live-parity fills in labels and summaries, not by changing the legacy `Trade` required fields.

Recommended label: `Synthetic simulation — locally generated prices/fills; no exchange orders`.

### Live-parity / paper-live simulation

- Start: same simulated start endpoint and `mode: 'simulated'`; set `parameters.execution_mode: 'live_parity'`.
- Do not activate the local synthetic fallback when the live-parity endpoint fails.
- Poll `GET /api/simulated-trading/status` and `GET /api/orderbook/simulated-signals`; the backend should report the paper/live-data source and execution diagnostics.
- Display live-data paper status and explicitly state: `Coinbase public market data; paper fills only; no Coinbase orders submitted`.
- Show blocked intents and blocker reasons even when no fills occur. A generated signal with zero executable intents is diagnostic data, not a loading state.
- If live data or readiness cannot be obtained, use `unavailable`/`blocked`; do not show synthetic records as a substitute.

Recommended label: `Live-data paper mode — live market data, simulated fills, no exchange orders`.

### Live execution

- Start: `POST /api/trading/live/start`; send live-only strategy parameters and the explicit `live_order_execution: true` confirmation.
- Before start, require credentials, loaded account snapshot, no producer errors, symbols, and the explicit confirmation. Existing `useLiveTabProducer` fields are the readiness source.
- The account-management selection is a separate safety scope: `disabled`, `monitor`, `manage_exits`, or `manage_entries_and_exits`. It must be displayed in the active-session summary.
- Manual execution remains `POST /api/trading/live/execute`; it must stay disabled until readiness permits trading and must validate amount/side/symbol before submitting.
- A successful order acceptance is not necessarily a fill. The UI must support pending order/accepted, terminal filled, rejected, cancelled/expired, and fill-details-pending records. Do not report an accepted order as a realized fill.
- Live close and liquidation are distinct actions and require confirmation for liquidation. Account-managed/inherited holdings must remain visibly distinct from session-managed positions.

Recommended label: `Live execution — real Coinbase orders; review account scope and confirmation`.

## 5. API request/response field map

### Start and stop

`apiClient.startTrading` builds a compatibility payload containing:

- common: `symbols`, `strategy`, `strategy_type`, `parameters`, `strategy_params`, `max_positions`, `position_size_percent`, `position_size`, `position_update_interval`, `immediate_start`, `batch_size`, strategy/ML aliases
- simulated: `initial_balance`, `capital`, `initial_portfolio_size`
- mode-specific: `parameters.execution_mode` (`live_parity` only for paper/live-data simulation); live parameters omit simulated capital fields

The response may be direct or wrapped and currently accepts `status: started/success`, `is_active`, camel-case `isActive`, or `session_id`. Future normalization should preserve all of these and additionally capture `session_id`, `execution_mode`, `source`, `blockers`, and pending/order acknowledgements.

Stop uses `POST /api/trading/{live|simulated}/stop`. It currently recognizes `success` and `settling`; `settling` should be represented as `stopping`, not immediately as fully stopped if the response contains pending work.

### Status and readiness

- Simulated status: `/api/simulated-trading/status` (legacy `/api/trading/simulated/status` exists server-side but is not currently used by `apiClient`). Read `portfolio`, `stats`, `recent_trades`, `trades`, `positions`, `total_fees`, `net_pnl`, `execution_mode`, `source`, and diagnostics when present.
- Live status: `/api/trading/live/status` for session status.
- Live producer/account: `/api/live-portfolio/status`; read `portfolio`, `readiness`, `credentials_configured`, `account_snapshot_loaded`, `live_order_execution_enabled`, `can_trade`, `blockers`, `errors`, `pending_orders`, `positions`, `holdings`, `account_snapshot_at`, and stats.

The current `getLivePortfolioStatus` catches all errors and returns a successful zero snapshot. This is unsafe for state rendering: retain the raw error/unavailable condition separately or remove this fallback for the mode-aware path. Zero values are valid account data only after a successful authoritative response.

### Signals and diagnostics

- Live signals: `/api/orderbook/live-signals`
- Simulated signals: `/api/orderbook/simulated-signals`
- Query fields: `symbols` comma-separated, `page`, `per_page`
- Signal fields: `symbol`, `timestamp`, `price`, `signal`, `signal_generated`, `signal_strength`, `data_status`, `spread`, `volume`, `prediction`, optional ML fields, and `execution_analysis`
- `execution_analysis`: `intended_action`, `intended_side`, `executable_intent`, `blocked`, `blocker_reason`, `diagnostic_factor`, expected-return/fee fields, allocation/cash, estimated fee, and minimum notional
- Response summary/diagnostics: pagination, `total_analyzed`, `active_signals`, `average_strength`, `last_updated`, coverage counts, `executable_order_intent_count`, blocker count maps, warming/rejected-input counts

`OrderBookSignalsTable` should render `data_status: insufficient/none` as unavailable/warming/empty-data messaging and render `blocked` as an intentional blocked-intent result, not as an absent signal.

### Stats, trades, positions, fills

- Stats source: `/api/simulated-trading/status` for simulation and `/api/live-portfolio/status` for live dashboard stats.
- Canonical stats fields: `total_pnl`, `total_fees`, `net_pnl`, `win_rate` (0–100, not fraction), trade counts, average/best/worst values, profit factor, per-trade Sharpe, max drawdown in dollars, volume, average trade size, and timestamps.
- `normalizeSimulatedTradingSnapshot` handles nested/direct portfolio forms and merges backend stats over derived values. Portfolio-level `total_fees` replaces, never adds to, per-trade fees.
- Recent trade compatibility: retain `id`/`trade_id`, `symbol`, `side`, `quantity`, `price`, `pnl`, `timestamp`, optional `fees`, and add optional `source`, `execution_mode`, `order_id`, `client_order_id`, `fill_status`, `filled_quantity`, `average_filled_price`, and `blocker_reason` at the new normalization boundary.
- Position compatibility: retain symbol/quantity/entry/current/unrealized fields and optional `session_managed`, `management_state`, `eligible_for_strategy_management`, and inherited quantity. Do not treat account holdings as session alpha.
- For live order/fill display, accepted/pending/rejected/filled are separate states; missing fill details must show `pending fill details`, not a zero-price fill.

### Reconciliation

`GET /api/trading/execution-reconciliation?hours=&session_id=&trade_type=` returns signal rows, outcome rows, `by_strategy`, `overall`, blockers, win rate, expectancy, PnL, fees, coverage and truncation/error indicators. It is diagnostic/read-only. The UI should pass the active session ID and execution mode/trade type when available so synthetic, paper, and live outcomes are not mixed in a trailing-window summary.

## 6. Known integration gaps to address in implementation

1. `TradingMode` cannot express `live_parity`; use a separate execution-mode type rather than widening backend mode to an unsafe third start route.
2. `SimulatedTradingPanel` checks `status.mode === 'live_parity'`, but the backend contract is simulated mode plus `parameters.execution_mode`; status normalization must expose `executionMode` and the panel must use it.
3. `getLivePortfolioStatus` converts request failure into a successful zero account. This erases `unavailable`; mode-aware callers need raw failure state.
4. `getOrderBookSignals` converts all request failures into a successful empty dataset. Preserve the error/unavailable state for live-parity and live; only synthetic mode may use its explicit local fallback.
5. `startTrading` uses a local synthetic fallback after all simulated endpoint attempts fail. Gate this fallback strictly on synthetic execution, never live-parity.
6. `ManualTradeSection` bypasses `apiClient`, directly posts to `/api/trading/live/execute`, and only checks HTTP success. It needs typed response handling for accepted/pending/rejected/fill states and must not be reusable by simulation tabs.
7. `getPositions` computes a query endpoint but calls the unparameterized hard-coded endpoint; the mode-aware implementation should either use the computed endpoint or document that pagination is client-side compatibility behavior.
8. `RecentTradesTable` uses array index keys and has no fill/source/status columns; add stable order/trade key and optional status/source columns without breaking synthetic records.
9. `useLiveTrading` exposes one boolean `loading` and merged error, which cannot distinguish start, stop, update, close, liquidation, or readiness. The new state adapter should retain operation-specific pending/error state.
10. `TradingControlsProps` declares promise-returning callbacks in shared types while the component declares void callbacks; align the type at the integration seam.
11. The reconciliation widget currently uses a trailing 24-hour aggregate without active session mode filtering; pass session/mode filters once the status adapter exposes them.
12. Existing local synthetic persistence is sessionStorage-backed and uses deterministic local IDs/timestamps. Keep those records readable and label their source rather than migrating them destructively.

## 7. Implementation acceptance criteria

- [ ] A typed mode/session normalization boundary represents synthetic simulation, live-parity paper simulation, and live execution without sending `live_parity` as backend mode.
- [ ] Status/readiness loading, blocked, unavailable, starting, active, stopping, stopped, and error states are distinct and testable.
- [ ] Live-parity endpoint/data failures cannot silently become synthetic records or an inactive/zero successful snapshot.
- [ ] Synthetic fallback remains available only for synthetic mode and preserves existing local record shapes/IDs.
- [ ] Start/stop response aliases remain backward compatible with current and legacy backend routes.
- [ ] Live start and manual order controls remain fail-closed on missing credentials, stale/missing account snapshot, producer errors, missing symbols, and absent explicit order confirmation.
- [ ] Live accepted/pending/rejected/filled/cancelled states are represented separately from realized fills; no accepted order is displayed as a fill without fill details.
- [ ] Signal tables distinguish insufficient/unavailable data from intentional blocked intents and show blocker reasons/diagnostics.
- [ ] Stats preserve existing conventions: win rate 0–100, max drawdown dollars, no fee double count, and zero-PnL legs excluded from win/loss rate.
- [ ] Positions/trades/fills remain backward compatible with existing synthetic and legacy response shapes, with optional source/execution/status fields.
- [ ] Endpoint and response normalization tests cover each mode, legacy aliases, fallback gating, blocked intents, unavailable responses, and fill lifecycle states.
- [ ] `git diff --check`, focused frontend tests/type checks permitted by the task, and required remote CI for the exact pushed SHA pass before implementation closeout.

## 8. Suggested implementation slices

1. Add typed `SimulatedExecutionMode`, `SessionMode`, operation-state and normalized status/fill contracts; add pure normalization tests.
2. Refactor `apiClient` mode-aware error/fallback behavior and preserve raw unavailable states; test synthetic fallback versus live-parity/live failure.
3. Update `useLiveTrading` and both panels to consume the adapter and render the state machine/safety copy.
4. Extend signal/trade/position tables with source, blocker, and fill lifecycle fields while retaining optional legacy fields.
5. Add session/mode filtering to reconciliation and verify the complete endpoint map against `include/api/PredictController.hpp`.
6. Run independent high-risk review focused on fail-closed live execution, synthetic fallback gating, and fee/PnL display semantics.
