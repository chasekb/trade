# TRADE-BL-0022: Phantom ETH-USD position diagnostic

Date of capture: 2026-08-23
Capture time (UTC): 2026-08-23T04:12:06Z
Scope: read-only runtime/API/database inspection. No live order was placed, canceled, replayed, closed, or liquidated.

## Executive conclusion

The currently displayed ETH-USD row is Coinbase-only account inventory, not a session-managed position. It is a dust-sized holding (`8.4078200000000004e-09` ETH) confirmed by the Coinbase account snapshot. It is not pending settlement, stale internal state, or frontend-only: the same row is present in all three backend-facing API paths and the persisted live-order table contains only rejected ETH-USD sell attempts, with no filled ETH-USD live order in the inspected records.

The row is eligible for strategy management only in the current live-tab producer response (`eligible_for_strategy_management=true`, `management_state=eligible_account_holding`), while it remains `session_managed=false` and `managed_quantity=0`. The live session is stopped and no live order execution is enabled, so it is not presently actionable. A previous read during this capture window returned `coinbase_unmanaged`/`eligible=false` before the refresh settled; a repeat at 04:12:06Z returned the stable eligible-account-holding state on both backend and frontend proxy. That transient difference is recorded as an observed producer-state transition, not treated as proof of a separate frontend bug.

## Runtime/API evidence

All values below are redacted of credentials, account identifiers, order IDs, and client IDs.

### `GET http://127.0.0.1:8081/api/live-portfolio/status`

- HTTP 200; `status=success`; producer `live_tab_coinbase_portfolio`; source `coinbase`.
- `account_snapshot_at=2026-08-23T04:12:06Z`; `account_snapshot_loaded=true`.
- `session_id=""`; `is_active=false`; `is_trading=false`; status `stopped`.
- `credentials_configured=true`; `live_order_execution_enabled=false`; `can_trade=false`.
- Readiness blockers: start live trading before manual orders; explicitly confirm live order execution.
- `pending_order_count=0`; `pending_orders=[]`; `pending_reserved_cash=0`.
- `session_managed_positions_count=0`; `account_managed_positions_count=0`; `coinbase_unmanaged_positions_count=1`.
- Portfolio cash: `cash_balance=99.80458336183851`; `cash_hold=0`; `total_value=99.804603640575493`.
- Portfolio positions value/exposure: `0.0000202787369798`.
- `recent_trades=[]`; `recent_signals=[]`; stats `total_trades=0`, `total_fees=0`, `net_pnl=0`.

ETH-USD row in `positions`, `portfolio.positions`, and `positions_by_symbol.ETH-USD`:

```text
symbol=ETH-USD
quantity=8.4078200000000004e-09
side=buy
status=coinbase
current_price=2411.8899999999999
entry_price=2411.8899999999999
unrealized_pnl=0
pnl_percentage=0
session_managed=false
managed_quantity=0
managed_entry_price=0
inherited_quantity=8.4078200000000004e-09
eligible_for_strategy_management=true
management_state=eligible_account_holding
pending_order_present=false
managed_quantity_floor_remaining=0
reconciliation_status=coinbase_confirmed
account_snapshot_present=true
account_snapshot_loaded=true
account_snapshot_at=2026-08-23T04:12:06Z
```

Coinbase holding exposed in the same response:

```text
asset=ETH
available=8.4078200000000004e-09
hold=0
price_usd=2411.8899999999999
value_usd=0.0000202787369798
```

### `GET http://127.0.0.1:8081/api/trading/live/positions`

- HTTP 200; exactly one row.
- The sole row is the ETH-USD row above, including `session_managed=false`, `management_state=eligible_account_holding`, `pending_order_present=false`, and `reconciliation_status=coinbase_confirmed`.

### `GET http://127.0.0.1:8081/api/trading/live/status`

- HTTP 200; `status=stopped`; `is_active=false`; `session_id=""`; `open_positions_count=1`.
- `positions` is an object with exactly one key, `ETH-USD`, matching the row above.
- `pending_order_count=0`; `recent_trades=[]`; `recent_signals=[]`; `session_managed_positions_count=0`.
- Portfolio totals match the live-portfolio response: cash `99.80458336183851`, position value/exposure `0.0000202787369798`, total value `99.804603640575493`.

### Frontend proxy / Live Trading producer

The same three paths were also queried through `http://127.0.0.1:3000` and returned HTTP 200 with the same ETH-USD account row and totals. The frontend Live Trading panel consumes `useLiveTabProducer()` from `/api/live-portfolio/status`, normalizes `positions`, and renders the row through `OpenPositionsSection`; the producer name is `live_tab_coinbase_portfolio`.

A first backend read at `2026-08-23T04:04:13Z` showed the same holding with `session_managed=false`, but `eligible_for_strategy_management=false` and `management_state=coinbase_unmanaged`. A subsequent frontend-proxy read at the same snapshot timestamp showed `eligible=true`/`eligible_account_holding`; a repeat at `2026-08-23T04:12:06Z` showed `eligible=true` from both ports. This is a state/refresh timing difference in the producer output, not a second ETH position. In all samples, the holding remained Coinbase-confirmed and session-unmanaged.

## Persistence evidence

Read-only queries were run against the running `trade_db_1` PostgreSQL container using its configured non-secret database role; no credential values were printed.

- `individual_trades` contains 6,009 ETH-USD rows, all with a non-empty `sim_...` session ID when classified by the inspected count query. The latest inspected ETH rows are `trade_type=live_parity` under simulated session `sim_1786217836`; there were no `live_...` ETH-USD trade rows in the inspected live-session query.
- `live_coinbase_orders` contains 33 ETH-USD records, all `status=rejected`; the status query returned no `FILLED` ETH-USD records. The rejected records are dust sell/close attempts from historical sessions and do not establish a filled live ETH position.
- Current API `recent_trades` and `recent_signals` are empty because there is no active session (`session_id=""`).

## Internal-state mapping

The API does not serialize the C++ containers directly, so the following maps are based on their explicit serializers and the observed response:

| Internal state | Observed diagnostic | Interpretation |
| --- | --- | --- |
| `positions_` | One `ETH-USD` object/row | Account snapshot reconciliation created/retained the row. |
| `pending_orders_` | `pending_order_count=0`, `pending_orders=[]` | No queued local intent. |
| `pending_live_orders_` | No pending order rows; `pending_order_present=false` | No accepted exchange order awaiting fill. |
| `pending_order_symbols_` | Count zero and ETH flag false | ETH is not blocked by a pending symbol. |
| `managed_quantity_floors_` | `managed_quantity_floor_remaining=0` | No active quantity floor is reported for ETH. |
| `recent_trades_` | `recent_trades=[]` | No in-memory current-session trade history. |
| `last_account_snapshot_.holdings` | ETH available dust, hold zero, valued at current price | Coinbase is the authoritative source of the row. |
| `portfolio.positions` | One ETH-USD row | Live portfolio widget includes Coinbase inventory. |
| `positions_by_symbol` | One `ETH-USD` key | Live status endpoint includes the same account holding. |
| persisted `individual_trades` | Simulated ETH history; no inspected live ETH rows | Does not explain the current live row. |
| persisted `live_coinbase_orders` | 33 rejected ETH sell attempts; zero filled ETH orders | Historical rejected attempts, not a successful fill. |

The source confirms this mapping: `applyLiveAccountSnapshotLocked()` creates a position from each Coinbase holding, sets `inherited_quantity`, `status=coinbase`, and (when account exits are not enabled) `management_state=coinbase_unmanaged`; the serializer marks `reconciliation_status=coinbase_confirmed` when the holding remains in the latest snapshot. `refreshLivePortfolioStatus()` calls the account refresh before building the Live Trading producer response.

## Classification

- Session-managed: **No** (`session_id` empty, `session_managed=false`, `managed_quantity=0`, managed count zero).
- Coinbase-only: **Yes** (holding appears in `last_account_snapshot_.holdings`, `status=coinbase`, inherited quantity equals total quantity, Coinbase-confirmed reconciliation).
- Pending-settlement: **No** (`pending_order_count=0`, no pending order present, no reserved cash, no pending live order row).
- Stale/internal: **No evidence**; the row is refreshed from and confirmed by the current Coinbase account snapshot.
- Frontend-only: **No**; the same row is returned by backend `/api/trading/live/positions` and `/api/trading/live/status`.

## Safety and limits of this capture

No order-mutating endpoint was called. No start, stop, close, liquidate, replay, or manual-order operation was invoked. The diagnostic cannot prove the historical origin of the dust holding because the exchange-side fill history was not mutated or independently replayed; it proves only the current account snapshot, current producer classification, local state exposed by the APIs, and persisted local records inspected above.

The current recommended follow-up is to keep this row visibly labeled as a Coinbase-only/inherited dust holding and distinguish it from session-managed positions. Any decision to liquidate it remains a separate explicit live-order operation and was intentionally not performed here.
