# TRADE-BL-0022: ETH-USD lifecycle and position authority

Static source trace of `LiveTradingService`. No orders, production writes, live endpoints, or runtime side effects were performed for this report.

## State model and authority

The live service's runtime position read model is `positions_` (`std::map<std::string, PositionState>`) in `include/trading/LiveTradingService.hpp:51-75,271`. `PositionState::quantity` is the total visible base quantity; `managed_quantity` is the session/account-managed portion; `inherited_quantity` is the quantity attributed to the Coinbase account before or outside this session. `session_managed` and `management_state` control strategy/close authority. `getOpenPositions()` and all status/Live Tab producers serialize this in-memory map, not a fresh Coinbase response (`src/trading/LiveTradingService.cpp:3018-3024`, `2658-2764`).

Coinbase is the authoritative source only when a successful account snapshot is fetched and applied. The latest successful snapshot is retained in `last_account_snapshot_`; `account_snapshot_present` is computed by matching `holding.asset + "-USD"` to the map key (`567-605`). A failed fetch records `last_account_snapshot_error_` but does not clear `positions_` (`3036-3059`).

There is no general symbol canonicalizer. Portfolio conversion groups accounts by exact currency (`src/trading/CoinbasePortfolio.cpp:13-33`), and `applyLiveAccountSnapshotLocked` forms the key by exact `holding.asset + "-USD"` (`1300-1318`). Requested symbols and order product IDs are also passed/compared exactly (`2811-2821`, `2040-2045`, `3076-3096`). Thus `ETH` becomes `ETH-USD`; case, whitespace, quote currency, and aliases are not normalized. `ETH-USD`, `eth-usd`, and `ETH/USD` are distinct keys.

## Lifecycle trace for ETH-USD

### Startup and initial snapshot

`startSession` first rejects an already-active or still-settling worker, creates the Coinbase client, and fetches an account snapshot before activating the session (`2767-2809`). It then accepts the requested symbol list verbatim (default `BTC-USD`, `ETH-USD`, `SOL-USD`), validates live execution confirmation, clears all transient position/order/history state, and calls `applyLiveAccountSnapshotLocked(snapshot, true)` (`2810-2905`). The initial snapshot sets cash, cash hold, position value, and initial capital (`1302-1311`).

For each nonzero Coinbase holding, including ETH, the snapshot sets `quantity = available + hold`, `inherited_quantity = quantity`, and the current/entry price from the snapshot. With account management disabled/monitor-only, the new position is `session_managed=false`, `management_state="coinbase_unmanaged"`, and is visible but not strategy-closeable. With `manage_exits` or `manage_entries_and_exits`, the holding is added to the selected symbol universe if absent and becomes account-managed (`managed_quantity=quantity`, `session_managed=true`, `management_state="account_managed"`) (`1313-1361`).

Because startup clears `positions_` immediately before applying this successful snapshot, an old ETH position cannot survive a successful restart snapshot merely because it was old. It can survive later failed/absent refreshes, as described below.

### Worker snapshots and mark-to-market

Each active worker iteration fetches live quotes and then a fresh Coinbase account snapshot (`2309-2395`). If the account request succeeds, it applies the snapshot before generating signals; if it fails, the old in-memory map remains and the worker still proceeds with quote/signal work (`2374-2393`). `applyLiveAccountSnapshotLocked` overwrites each present symbol's `quantity` with `available + hold`, updates available sell quantity, prices, inherited/managed attribution, and removes absent symbols unless they are pending or inside a managed floor grace window (`1317-1406`).

`generateTickLocked` uses real quotes only. For ETH, it reads `positions_.find("ETH-USD")`, updates the current price, and leaves Coinbase-unmanaged holdings visible without auto-liquidating them (`2226-2269`). Session-managed positions can be closed on an opposite signal/age-out or stop-loss/take-profit; DCA can add (`2272-2299`). `updateMarkToMarketLocked` reads/writes `current_price`, `unrealized_pnl`, `pnl_percentage`, age, aggregate unrealized PnL and total position value, and may enqueue a close (`1944-1989`).

### Opening and adding

`openPositionLocked` refuses an existing or pending ETH key, enforces position count, Coinbase minimum notional, cash, spot-long-only, and explicit live execution, then queues an `OrderIntent` with `action="open"`; it does not mutate `positions_` at queue time (`1991-2049`). `addToPositionLocked` follows the same pending/cash/minimum/spot gates, copies the existing position into the intent, and queues `action="add"` (`2051-2102`).

Dispatch persists the order intent, reserves cash, and leaves `pending_order_symbols_` set (`638-645`, `859-918`, `1035-1104`). Accepted orders are held in `pending_live_orders_`; no position is created until a fill is resolved. A definitive rejection clears the pending symbol and cash reservation. A client-order lookup that is complete-not-found for 30 attempts marks the order `not_found` and clears the reservation/symbol (`1132-1150`). Other unresolved accepted orders remain pending.

### Fill application

`resolvePendingLiveOrders` queries the exchange fill, then under the mutex calls `applyLiveFillLocked` once and persists the resulting trade. It subsequently tries a fresh Coinbase account snapshot (`1106-1205`).

For an ETH open/add fill, `applyLiveFillLocked` clears `pending_order_symbols_` and the reserved cash, creates a new `PositionState` keyed by `intent.product_id` or grows the existing one, updates total/managed quantity, managed weighted entry price, current price, and managed floor state (`654-857`). With `account_snapshot_reflects_fill=false` (the normal pending-fill path), open adds to `position.quantity`; with `true`, the snapshot is treated as already containing the fill and quantity is not blindly doubled (`806-824`).

For `action="close"`, the fill computes managed/inherited quantities and PnL, subtracts quantity only when the account snapshot does not already reflect the fill, clamps managed quantity, and erases the map entry at a near-zero quantity (`689-745`). For `action="liquidate_holding"`, it similarly clears managed/inherited quantities and erases at zero (`746-777`). A close of an inherited-only holding is rejected by `closePositionLocked` (`2104-2151`); an explicit liquidation path is separate and minimum-notional guarded (`2154-2224`).

### Stop and shutdown

`stopSession` sets `stop_requested_=true`, sets `active_=false`, releases queued-but-not-dispatched intents and their cash reservations, but deliberately leaves accepted `pending_live_orders_` for settlement (`2930-2954`). The worker continues until pending accepted orders, pending symbols, and pending writes are gone; it does not clear `positions_` on normal stop (`2310-2437`). Therefore an ETH entry that was already in `positions_` remains readable after stop until another successful snapshot or fill-driven deletion changes it. The destructor only sets inactive/stop/shutdown flags and joins the worker; it also does not clear the map (`283-293`).

### Refresh and reads

`refreshLiveTabProducerStatus` creates a Coinbase client if needed, fetches a snapshot outside the mutex, and applies it with `establish_baseline = !active_` on success. On failure it preserves the prior map and returns producer JSON with the error (`3036-3059`). The producer JSON serializes `positions_`, `positions_by_symbol`, pending local/accepted orders, and a Coinbase snapshot copy (`2658-2764`). `getOpenPositions` simply serializes the current map under the mutex (`3018-3024`).

## Floor, pending, and absence conditions

`managed_quantity_floors_` is created after a filled managed open/add with `{managed_quantity, 30}` (`843-848`). On each successful account snapshot where ETH is absent, the floor keeps the visible quantity at least at the stored managed amount and decrements the grace counter; when the counter reaches zero it is retained for that snapshot, and the next absent snapshot erases it (`1326-1336`, `1392-1405`). In practical terms, a floor can preserve the prior ETH position for 30 absent successful snapshots and remove it on the 31st, unless a later snapshot reports enough quantity and clears the floor.

A Coinbase-absent ETH position can remain visible under these precise conditions:

1. **No successful snapshot is applied:** startup/refresh/worker fetch fails, so the old `positions_` map is retained; `refreshLiveTabProducerStatus` explicitly returns stale in-memory positions with an error.
2. **Accepted order is still pending:** `pending_order_symbols_` contains `ETH-USD`, so the absent-symbol cleanup condition is false. This includes accepted orders that never become queryable/terminal; only the client-lookup not-found path has a finite 30-attempt cleanup.
3. **Managed floor grace is active:** a successful snapshot omits ETH but `managed_quantity_floors_["ETH-USD"]` still has remaining grace; the old quantity is retained for the grace window.
4. **A stopped session is only read, not reconciled:** `stopSession` does not clear positions and no worker snapshot runs after the accepted orders settle. `getOpenPositions` and status continue exposing the last in-memory ETH position.

A successful snapshot with absent ETH, no pending symbol, and no active floor erases the position immediately. A successful snapshot with ETH present, including a dust quantity, recreates/updates it; no minimum-notional filter applies to visibility. `account_snapshot_present=false` alone is therefore evidence of a stale/pending/grace state, not proof that the position has already been removed.

## Authoritative source by stage

- Startup baseline: successful Coinbase account snapshot, applied into in-memory `positions_`.
- Active worker/account reconciliation: latest successful Coinbase snapshot is authoritative for total quantity and cash; `positions_` is the serving read model between snapshots.
- Accepted-but-unfilled order: persisted `live_coinbase_orders` plus in-memory `pending_live_orders_`, pending symbol, and cash reservation; no position mutation yet.
- Fill settlement: Coinbase fill is authoritative for the filled quantity/fees; `applyLiveFillLocked` mutates `positions_`, then a snapshot is attempted.
- Failed snapshot: no new authority is available; prior in-memory state remains visible and is explicitly marked through error/reconciliation fields.
- Stop/read endpoints: in-memory `positions_` and pending state; stop is not a final portfolio reconciliation.
- Persistence: fills/trades and order intents are written to Postgres, but `getOpenPositions` does not reconstruct positions from Postgres.

## Existing evidence/tests used

The source includes focused Coinbase portfolio tests in `src/tests/test_coinbase_portfolio.cpp` covering account aggregation, cash/hold handling, and malformed/nonpositive values. No focused `LiveTradingService` unit tests were found under `src/tests`; this report is therefore a static trace, not a claim of runtime or build verification.
