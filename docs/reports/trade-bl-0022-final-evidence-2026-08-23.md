# TRADE-BL-0022 — Final ETH-USD phantom-position evidence

Capture window: 2026-08-23 UTC. This report consolidates the persisted-state, endpoint, and frontend investigations. All credentials, authorization headers, account identifiers, order identifiers, client identifiers, signatures, and secrets are intentionally omitted.

## Determination

**Primary classification: Coinbase-only / Coinbase-confirmed inherited dust holding. Confidence: high.**

The Live Trading ETH-USD row is not frontend-only: the same row is emitted by the backend endpoints and by the frontend proxy. It is not session-managed: the active session is empty/stopped, `managed_quantity` is zero, and the service reports `session_managed=false`. It is not pending-settlement: pending collections and counts are empty/zero, with no reserved cash. It is not stale/internal: the fresh Coinbase account snapshot contains the ETH holding and the response marks it `reconciliation_status=coinbase_confirmed`.

The apparent phantom is a real Coinbase account holding surfaced by the Live Trading producer while live trading is stopped. The historical origin of the dust cannot be reconstructed from the inspected records. `eligible_account_holding`/`eligible_for_strategy_management=true` is an account-management eligibility label, not evidence of session ownership; one earlier refresh transiently used `coinbase_unmanaged` and `eligible_for_strategy_management=false`.

## Reconciled identity and values

The stable identity across all captures is:

- symbol: `ETH-USD`
- side: `buy`
- status: `coinbase`
- quantity: `8.4078200000000004e-09`
- inherited_quantity: `8.4078200000000004e-09`
- managed_quantity: `0`
- managed_entry_price: `0`
- managed_quantity_floor_remaining: `0`
- session_managed: `false`
- pending_order_present: `false`
- unrealized_pnl: `0`
- pnl_percentage: `0`
- reconciliation_status: `coinbase_confirmed`
- account_snapshot_present/loaded: `true`

Prices and value changed between safe read-only refreshes because the market quote changed; this is not a second position:

| Capture | account_snapshot_at / observation | ETH price and row entry | Coinbase holding value | Classification fields |
|---|---|---:|---:|---|
| Persisted-state capture | `2026-08-23T04:12:06Z` | `2411.8899999999999` | `0.0000202787369798` | `management_state=eligible_account_holding`, eligible=true |
| Endpoint capture | `2026-08-23T05:12:23Z` | `2375.4000000000001` | `0.000019971935628` | `management_state=coinbase_unmanaged`, eligible=false |
| Live-row/frontend-proxy capture | `2026-08-23T05:15:05Z`; proxy observed `05:15:20Z` | `2368.4400000000001` | `0.0000199134172008` | `management_state=eligible_account_holding`, eligible=true |

At the latest capture, the Live Trading row renders quantity `0.0000` (the UI formats eight-decimal dust to four decimals), entry/current `$2368.4400`, unrealized `$0.00`, management `Eligible account holding`, and an account-holding liquidation affordance disabled because `can_trade=false`. The latest portfolio totals were `cash_balance=99.80458336183851`, `total_positions_value=0.0000199134172008`, and `total_value=99.804603275255715` (UI rounds these to `$99.80`, `$0.00`, and `$99.80`).

## Session, pending, account, and activity state

Across the latest endpoint/frontend captures:

- `session_id=""`
- `status=stopped`
- `is_active=false`
- `is_trading=false`
- active/settling session: none observed
- `pending_order_count=0`
- `pending_orders=[]`
- `pending_reserved_cash=0`
- `pending_live_orders_`: no pending row
- `pending_order_symbols_`: ETH flag false
- `account_snapshot_at=2026-08-23T05:15:05Z` in the latest producer response
- `account_snapshot_loaded=true`
- Coinbase holdings: one ETH holding with `available=8.4078200000000004e-09`, `hold=0`, `price_usd=2368.4400000000001`, `value_usd=0.0000199134172008`
- `account_managed_positions_count=0`
- `coinbase_unmanaged_positions_count=1`
- `recent_trades=[]`, `recent_signals=[]`
- `total_trades=0`, `total_fees=0`, realized/unrealized/net P&L all zero
- `credentials_configured=true`, but `live_order_execution_enabled=false` and `can_trade=false`; blockers include `Start live trading before placing manual orders` and `Live order execution must be explicitly confirmed`

## Four endpoint/source responses

All requests below were safe GET/read-only observations and returned HTTP 200.

1. **`GET /api/live-portfolio/status`** — the distinct Live Trading tab producer. At `2026-08-23T05:12:23Z` it returned `source=coinbase`, `producer=live_tab_coinbase_portfolio`, one ETH-USD row, the Coinbase holdings snapshot, empty session/pending state, and `reconciliation_status=coinbase_confirmed`. The later capture at `05:15:05Z` returned the same identity with the updated quote/value above.
   - Backend route: `src/api/PredictController.cpp:1269-1285`.
   - Producer construction: `src/trading/LiveTradingService.cpp:2658-2764`.

2. **`GET /api/trading/live/positions`** — `LiveTradingService::getOpenPositions`, one-element response containing the same ETH-USD quantity, provenance, and Coinbase-confirmed fields. It has no independent session/pending envelope.
   - Backend route: `src/api/PredictController.cpp:1306-1312`.

3. **`GET /api/trading/live/status`** — in-memory live-service status, captured without a `session_id` query parameter. It returned `status=stopped`, empty `session_id`, `is_active=false`, `is_trading=false`, `open_positions_count=1`, the same ETH-USD row, empty recent activity, and `pending_order_count=0`/`pending_reserved_cash=0`.
   - Backend route: `src/api/PredictController.cpp:1368-1373` (optional `session_id` is read but no session was supplied).

4. **Frontend proxy `GET http://127.0.0.1:3000/api/live-portfolio/status`** — HTTP 200 at `2026-08-23T05:15:20Z`; returned the same Coinbase producer response and row, with only the normal quote/value update. The frontend uses this producer response for the Live Trading panel, not `/api/trading/live/positions`.
   - Fetch path: `frontend/components/dashboard/LiveTradingPanel.tsx:288-292`, `frontend/hooks/useTrading.ts:464-478`, `frontend/lib/api.ts:1007-1009`.
   - Normalization: `frontend/lib/liveTabProducer.ts:48-77`.
   - Row rendering/formatting and account-holding action: `frontend/components/dashboard/OpenPositionsSection.tsx:117-180`.

The backend producer explicitly copies `positions_` into both `positions` and `positions_by_symbol` (`LiveTradingService.cpp:2669-2675`), and builds `pending_orders` from both pending collections (`:2677-2706`). This explains why the row and zero pending state agree across envelope forms.

## Persisted collections and records

The persisted-state investigation inspected the requested live-service state and redacted diagnostic artifact:

- `last_account_snapshot_.holdings`: ETH available `8.4078200000000004e-09`, hold `0`, with the account snapshot timestamp above.
- `portfolio.positions`: one ETH-USD row with the stable identity and quantity above.
- `positions_by_symbol.ETH-USD`: same row, not a separate record.
- `pending_orders_`: empty; `pending_live_orders_`: no pending ETH row; `pending_order_symbols_`: ETH false.
- `managed_quantity_floors_`: remaining floor `0`.
- `recent_trades_`: empty.
- Persisted `individual_trades`: 6,009 ETH-USD rows were inspected; they belonged to simulated `sim_*` sessions, with no inspected `live_*` ETH rows. These do not explain the current live row.
- Persisted live Coinbase orders: 33 ETH-USD records were found; all were `rejected`, with no `FILLED` ETH-USD record observed. They show historical rejected attempts, not a completed fill or pending settlement.

Source artifact from the persisted investigation (credentials and identifiers redacted):
`/run/media/unordered_map/priority_queue/log(perplexity)/-sum/log/Pr(context_for_token)/chasecapitalmanagement/etl/trade/.worktrees/t_7c680bc2/docs/reports/trade-bl-0022-phantom-eth-usd-diagnostic-2026-08-23.md`

## Contradictions and alternatives

- **Quote/value differences:** `2411.89` at 04:12, `2375.40` at 05:12, and `2368.44` at 05:15 are time-separated market refreshes. Quantity and provenance remained unchanged; this is expected price movement.
- **Eligibility label difference:** the 04:04:13Z/05:12 capture history included `coinbase_unmanaged`/eligible=false, while the later 04:12:06Z and 05:15:05Z captures used `eligible_account_holding`/eligible=true. This is a refresh/state-timing difference, not a second position and not session ownership. `session_managed` stayed false and managed quantity stayed zero.
- **Frontend-only:** rejected. The backend producer and both live service endpoints returned the row.
- **Stale/internal:** rejected at current capture because a fresh Coinbase snapshot includes the exact available quantity and marks the row Coinbase-confirmed. Historical origin remains unknown.
- **Pending-settlement:** rejected. Pending arrays/collections, pending count, reserved cash, and pending symbol flag are all empty/zero/false; persisted ETH orders were rejected, not filled/pending.
- **Session-managed:** rejected. No session ID, stopped service, zero managed quantity, zero managed floor, zero session-managed count, and no live individual-trade rows.

Alternative explanations retained with low confidence: (1) the dust was created by an older Coinbase action whose historical provenance is no longer represented in the inspected live/session records; or (2) the eligibility label changed during account-refresh timing. Neither alternative changes the primary classification.

## Safety confirmation

No live trading state was mutated. The investigations used read-only GET requests and persisted/log inspection only. No order was placed, replayed, canceled, closed, liquidated, or otherwise submitted; no session was started or stopped.

## Source paths

- `src/api/PredictController.cpp:1269-1285,1306-1312,1368-1373`
- `src/trading/LiveTradingService.cpp:2658-2764` (producer, positions, pending collections, readiness)
- `frontend/components/dashboard/LiveTradingPanel.tsx:288-292,355-365,412-428,503-507`
- `frontend/hooks/useTrading.ts:75-89,464-478`
- `frontend/lib/api.ts:1007-1009`
- `frontend/lib/liveTabProducer.ts:48-77`
- `frontend/components/dashboard/OpenPositionsSection.tsx:117-180`
- Redacted persisted diagnostic artifact listed above
