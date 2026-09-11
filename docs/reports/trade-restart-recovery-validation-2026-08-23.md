# Trade restart and recovery validation — 2026-08-23

Task: `t_bf42c79d` — Validate restart and recovery behavior.

Scope: controlled read-only API checks plus paper-only simulated sessions against the running Compose stack (`trade_cpp-backend_1`, `trade_db_1`, `trade_redis_1`). No live order was submitted, no live session was started, and no local build or test command was run.

## Environment and safety preconditions

- Backend was healthy on `127.0.0.1:8081`; frontend health was healthy on `127.0.0.1:3000`.
- Before the controlled active-session scenario, live status reported `status=stopped`, `is_active=false`, `pending_order_count=0`, and `live_order_execution_enabled=false` after the account refresh.
- The live account refresh reported `can_trade=false` with blockers `Start live trading before placing manual orders` and `Live order execution must be explicitly confirmed`.
- PostgreSQL catalog estimates after restart: `individual_trades=1`, `live_coinbase_orders=0`, `order_book_signals=284513` rows. The live-order table had no pending or accepted rows to recover.
- Redis key names remained present after restart (`ml_active_model_id`, `ml_active_model_name`, `ml_active_model_version`, `ml_last_metrics`, training status/progress keys); values were not copied into this report.

## Scenario results

### 1. Idle restart

Precondition: simulated session was stopped and live session was stopped. A paper-only stop request returned success and zero open positions/pending orders. The backend container was restarted with `podman restart --time 30 trade_cpp-backend_1`; health returned on the first poll after restart and the container remained healthy.

Postcondition:

- Simulated status: stopped, no session ID, no symbols, tick 0, no positions, no pending orders, default paper capital `$10,000`.
- Live status initially: stopped, no session ID, no symbols, no positions, no pending orders, live balances `0.0` until an explicit account refresh.
- Backend logs showed successful PostgreSQL and Redis reconnection and `Server listening on port 8080`.

Result: process restart is available and fail-closed for live trading, but in-memory session state is not restored.

### 2. Active work restart (paper-only)

Started a controlled simulated session with session ID `restart-active-20260823`, strategy `orderbook`, symbol `BTC-USD`, execution mode `simulated`, initial paper capital `$100`, and confidence threshold `1.0` to prevent an unintended paper fill. After five seconds, status was active with tick `4`, one selected symbol, one latest signal, zero positions, zero pending orders, and zero reserved cash.

Restarted the backend while this worker was active. The restart took approximately `30,503 ms`; health returned on the first health poll after the container came back. Post-restart status was stopped with an empty session ID, zero symbols, tick 0, zero positions, zero pending orders, zero reserved cash, and default paper capital `$10,000`.

Result: active paper work is terminated rather than resumed or replayed. No duplicate paper order occurred in this run. The active session, tick, generated signal, and its configured `$100` capital were lost because they were in memory only.

### 3. Stop Trading behavior

The simulated stop endpoint returned `status=success`, `is_active=false`, `is_trading=false`, and zero pending orders after the pre-restart benchmark session. Live status remained stopped and live execution remained disabled. The active paper session was not resumed after restart.

Result: the observed stop path prevents continued simulated work and the live path remained fail-closed. A queued-live-order stop/settlement scenario was not run because `live_coinbase_orders` was empty and creating an exchange order would violate the safety boundary.

### 4. API polling and pagination after restart

Ten sequential live-status requests were issued after restart. Nine completed in approximately `0.00065–0.00107 s`; one timed out at `5.002981 s`; one later request took `1.281907 s`. Frontend health returned HTTP 200 in `0.001828 s`.

Both `/api/orderbook/live-signals?page=1&per_page=5` and page 2 returned HTTP 200 with pagination metadata reporting `total_signals=468` and `total_pages=94`, but returned an empty `signals` array after restart. Simulated signals likewise reported `total_signals=468` but returned no rows because the in-memory worker had reset.

Backend logs repeatedly reported:

```text
Database parameterized query failed: ERROR: function pg_input_is_valid(text, unknown) does not exist
```

The failure occurred during signal pagination queries. This is a reproducible post-restart/API-polling gap: the response advertises retained rows while returning no rows, and the database query error is not surfaced as an HTTP error.

### 5. Account snapshot consistency

Immediately after restart, live status had zero balances and no positions despite the pre-restart process having held an account snapshot with approximately `$99.8046` total value and one tiny inherited `ETH-USD` holding. Calling the explicit read-only `/api/live-portfolio/status` refresh restored the Coinbase snapshot: approximately `$99.8046` total value, one inherited `ETH-USD` holding, `account_snapshot_loaded=true`, `can_trade=false`, and explicit readiness blockers. A subsequent live-status request reflected that snapshot.

Result: account state can be reconstructed from Coinbase only after an explicit refresh; the ordinary post-restart status initially exposes zero-valued live account state without a freshness/error marker. This is a stale/empty-state risk for operators polling status immediately after restart.

### 6. Persistence and queue reconstruction

Source inspection confirms `LiveTradingService::recoverPendingOrders()` queries `live_coinbase_orders` rows with `status IN ('submitting','pending')` and reconstructs intent/reserved-cash state. The runtime database contained zero rows in that table, so the recovery branch was not exercised. No duplicate or unauthorized live execution was observed, but pending-order recovery remains unverified in a real persisted pending-row scenario.

Simulated signals/trades are written to PostgreSQL, but active simulated session state (`positions_`, `recent_signals_`, `recent_trades_`, counters, and pending vectors) is reset by process restart and is not reconstructed from those tables. The controlled restart showed this directly: pre-restart tick 4/one signal became post-restart tick 0/no signals.

## Recovery matrix

| Interruption point | Evidence | Result | Gap/status |
|---|---|---|---|
| Idle process restart | Backend restart with both modes stopped | Healthy reconnect; both modes stopped | Live snapshot initially zero until explicit refresh |
| Active simulated work | Paper session active at tick 4, then backend restart | Worker terminated; no resumed session or duplicate paper order | In-memory session/counters/signals lost |
| Queued simulated work | No pending simulated orders at test boundary | Not exercised | Requires deterministic queue/failure injection |
| Queued live work | `live_coinbase_orders` estimate 0; live execution disabled | Not exercised | Must use a persisted fixture or exchange sandbox, not a real order |
| API polling during recovery | Ten status polls; one 5 s timeout and one 1.28 s response | Mostly fast, but intermittent latency | Investigate backend/DB contention and expose readiness during recovery |
| Pagination/retention | 468 historical rows advertised; empty row arrays; repeated PostgreSQL function error | Contract inconsistency | Blocking data-integrity/observability defect |
| Partial failure | Signal pagination query errors; live refresh succeeds separately | Errors logged, HTTP remains 200 for signal endpoint | Surface query failure and distinguish retained count from returned rows |
| Stop Trading | Simulated stop and live stopped state | Fail-closed observed | Queued-live settlement not runtime-tested |

## Minimal reproductions and findings

1. **Signal pagination mismatch (high operational severity, no live-funds exposure):** with the healthy backend running, request `GET /api/orderbook/live-signals?page=1&per_page=5`. The response reports `total_signals=468` and `total_pages=94` but `signals=[]`; backend logs show the unsupported PostgreSQL `pg_input_is_valid(text, unknown)` call. The same symptom repeats on page 2 and after backend restart.
2. **Live snapshot reset after restart (medium operational severity, safety currently fail-closed):** restart `trade_cpp-backend_1`, then request `GET /api/trading/live/status` before any refresh. The response is stopped with zero balances/positions; request `GET /api/live-portfolio/status` to refresh, then live status returns the Coinbase snapshot and explicit `can_trade=false` blockers.
3. **Active simulated state loss (medium data-retention severity):** start a paper-only session, observe tick/signals, restart the backend, then request simulated status. The session becomes stopped/default with tick 0 and no signals/positions. No duplicate execution occurred, but restart recovery is not stateful for simulated sessions.
4. **Startup runtime skew warning:** after each restart, logs reported missing `/app/data/cpp_assets/feature_params.json` and no usable ONNX models, causing neutral/heuristic fallbacks. This did not enable live execution, but it changes post-restart inference behavior and should be reconciled with the image/volume contract.

## Acceptance assessment

- Recovery behavior documented for idle, active paper work, API polling, pagination, account snapshot, Stop Trading, persistence, and partial failure.
- No duplicate or unauthorized live execution observed; live order execution was explicitly disabled and no live order was submitted.
- Recovery gaps found and minimally reproduced: live snapshot initially empty, simulated in-memory state loss, pagination empty-row/count inconsistency, unsupported PostgreSQL function errors, intermittent polling timeout, and post-restart model-asset fallback.
- Queued-live-order reconstruction and partial external-order failure were not proven because the safe runtime had no persisted pending orders and no exchange sandbox fixture was available. These remain open verification work, not passing acceptance criteria.

## Verification constraints

- No local Docker/Podman image build, CMake build, or unit/frontend test was run.
- This was runtime evidence collection against the already-running published `dev` images. No repository code was changed by the scenarios themselves.
