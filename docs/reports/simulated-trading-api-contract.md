# Simulated-trading API contract

This document records the backend contract consumed by the React simulated-trading dashboard.

## Session lifecycle

- `POST /api/trading/simulated/start` and `/api/simulated-trading/start` accept the same payload. The canonical fields are `strategy`, `symbols`, and `parameters`; `strategy_params` remains a legacy alias.
- A successful start returns `status: "started"`, `is_active: true`, `isActive: true`, `is_trading: true`, `session_id`, `mode`, `execution_mode`, `strategy_type`, and the normalized `symbols` list.
- Session identifiers are unique even when multiple starts occur during the same epoch second. A start while another mode is active is rejected rather than silently taking over the active session.
- `GET /api/simulated-trading/status` returns the active session identity in `session_id` and the activity aliases above. When `session_id` is supplied as a query parameter, `requested_session_id` is echoed and `session_id_matches` states whether it is the active session.
- Stop responses may use `success` or `settling`. A stopped session is inactive; callers must clear cached statistics and signals before a later start.
- Strategy updates preserve the same activity, session, mode, strategy, and symbol fields as status responses.

## Symbols and signals

- Symbol input is normalized at start and signal-query boundaries: empty entries are removed and duplicates are removed while preserving first-seen order. An omitted symbol filter means the current selected universe.
- The worker produces at most one current signal per selected symbol. `total_signals` is the number of latest-by-symbol rows, not cumulative worker history.
- `GET /api/orderbook/simulated-signals` accepts `symbols`, `page`, `per_page`, and optional `session_id`. The session filter is applied to both in-memory and persisted fallback reads.
- Responses include both canonical and compatibility pagination keys:
  `current_page`, `page`, `per_page`, `limit`, `total_signals`, `total`, `total_pages`, `has_next`, and `has_prev`.
- `page` and `per_page` are clamped to at least `1`; offset arithmetic is performed with an unsigned size type so hostile integer inputs cannot wrap. Empty results use `total_pages: 0` and both navigation flags false.
- Signal rows provide the widget fields `signal_id`, `session_id`, `symbol`, `signal_type`, `signal`, `signal_generated`, `signal_strength`, `strength`, `price`, `timestamp`, `spread`, `imbalance`, `imbalance_ratio`, `mid_price`, `best_bid`, `best_ask`, `order_book_depth`, `volume`, `data_status`, `signal_reason`, `criteria_analysis`, `ml_analysis`, `strength_composition`, and `execution_analysis`. Persisted legacy JSON receives safe defaults for optional analysis objects.

## Statistics and portfolio

- Status and portfolio payloads expose `stats`, `recent_trades`, and `trades`. Statistics are scoped to the current simulated session when persisted rows are available; in-memory trade inputs are used while the session is running or when persistence is unavailable.
- `win_rate` is a percentage from `0` to `100`; `max_drawdown` is denominated in dollars. `total_value` equals cash plus signed position value, while `total_positions_exposure` is the absolute gross exposure.
- `total_fees` is the portfolio-level fee total and must not be added again to a per-trade fee sum when deriving net P&L.

## Compatibility assumptions

The frontend tolerates the historical `isActive` and `page` names, while new code should prefer `is_active`, `current_page`, and the explicit session identity fields. Backend changes should retain both aliases until all deployed dashboard clients have migrated.
