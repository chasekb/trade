# Runtime cadence, latency, and data-age evidence

Collected 2026-08-23 from the checked-out trade worktree and the live read-only host state. No source, runtime, database, exchange, or trading configuration was changed. No order was submitted.

## Scope and limitations

- The trade containers were not operating when this investigation ran: `trade_cpp-backend_1` and `trade_frontend_1` were in `created` state; `trade_db_1` was `running` but `unhealthy`/`starting`; Redis was healthy.
- Consequently, this run could not collect a fresh multi-cycle browser trace, WebSocket trace, backend worker trace, exchange response trace, model latency sample, or fill sample.
- The live tmux pane contained historical runtime output. Those observations are reported separately from source-derived inferences.
- PostgreSQL was still replaying/syncing after an interrupted shutdown. Read-only `pg_isready` attempts at approximately 07:02:44 UTC rejected connections and the bounded retry command timed out at 35 seconds.
- No credentials, `.env` values, cookies, or full upstream response bodies were read or included.

## Commands and exact live-state observations

Commands used (read-only):

- `git status --short --branch; git log -5 --oneline`
- `tmux ls; tmux list-panes -a -F ...`
- `tmux capture-pane -t 0:7.0 -p -S -120`
- `podman ps --all --format ...`
- `podman inspect trade_cpp-backend_1 trade_frontend_1 trade_db_1 ...`
- `podman logs --since 12h --timestamps trade_db_1`
- `podman logs --since 2h --timestamps trade_cpp-backend_1`
- `podman logs --since 2h --timestamps trade_frontend_1`
- `podman exec trade_db_1 pg_isready -U postgres -d postgres`
- `podman network inspect trade_trading-network ...`

At the capture time, UTC was `2026-08-23T07:02:44Z`.

Observed container state:

| Container | State | Evidence |
|---|---|---|
| `trade_cpp-backend_1` | `created`, no start time | `podman ps --all`; inspect reported `status=created`, image `ghcr.io/chasekb/trade/cpp-backend:dev` |
| `trade_frontend_1` | `created`, no start time | `podman ps --all`; inspect reported `status=created`, image `ghcr.io/chasekb/trade/frontend:dev` |
| `trade_db_1` | `running`, `health=starting` | inspect health entries at `2026-08-23T02:02:43.533-05:00` and `02:03:24.569-05:00` both rejected connections |
| `trade_redis_1` | `Up`, healthy | `podman ps --all` |

The backend/frontend log command returned no output in the last two hours because those containers had not started. The database log showed:

- `2026-08-23 07:01:15.587 UTC`: PostgreSQL became ready during initialization.
- `2026-08-23 07:01:19.916 UTC`: received fast shutdown request.
- `2026-08-23 07:01:20.778 UTC`: shutdown checkpoint started.
- `2026-08-23 07:02:41.516 UTC`: PostgreSQL restarted.
- `2026-08-23 07:02:45.870 UTC`: database shutdown was interrupted; last known up at `07:01:20 UTC`.
- `2026-08-23 07:02:55.948 UTC` through `07:03:35.899 UTC`: data-directory fsync was still running, while connection attempts reported `the database system is starting up`.

The tmux pane `0:7.0` was confirmed as the trade shell (`pid=728510`, current command `bash`, path ending `/etl/trade`). Its historical output contained:

- Frontend proxy errors at `2026-08-23T05:09:03`-ish UTC and later: `getaddrinfo ENOTFOUND cpp-backend`, then `connect ECONNREFUSED 10.89.1.7:8080` for `/api/products`, `/api/ml/models`, and `/api/ml/config`.
- PostgreSQL errors at `2026-08-23 05:09:03.973 UTC`, `05:11:52.871 UTC`, `05:12:06.458 UTC`, and `05:12:19.302 UTC`: the query used `pg_input_is_valid(text, unknown)`, which the running PostgreSQL image reported as an undefined function.
- Historical shutdown boundary: PostgreSQL logged a fast shutdown at `2026-08-23 05:37:55.323 UTC`; Redis logged SIGTERM at `2026-08-23 05:41:39.040 UTC`; the foreground compose process returned to the shell prompt afterward.

These historical lines establish failures and lifecycle boundaries, not successful trading cycles.

## Source-derived cadence map

| Boundary | Source location | Configured/implemented interval | Interpretation |
|---|---|---:|---|
| Trading status query | `frontend/hooks/useTrading.ts:76-89` | 5 s while active; 10 s live when inactive | Status display polling is not inherently one minute. |
| Order-book signals query | `frontend/hooks/useTrading.ts:433-444` | 3 s while enabled | The simulated signal widget is configured for near-real-time polling. |
| Simulated stats query | `frontend/hooks/useTrading.ts:483-497` | 3 s while enabled | Stats widget polling is also not one minute. |
| Native simulated WebSocket heartbeat | `frontend/hooks/useTrading.ts:598-615` | Ping every 30 s | Heartbeat prevents timeout; it is not a data publication cadence. |
| Simulated WebSocket cache updates | `frontend/hooks/useTrading.ts:661-697` | Event-driven | `trading_statistics_update` and `orderbook_signals_update` update React Query immediately when a producer exists. |
| Price-history query | `frontend/hooks/usePriceData.ts:36-51` | `staleTime=30 s`, refetch every 60 s | This is the direct source-level explanation for an approximately one-minute price widget cadence. |
| Mock chart history spacing | `frontend/hooks/usePriceData.ts:13-15` | 60 s between generated points | The development price series itself is constructed at one-minute resolution. |
| Mock “real-time” chart updates | `frontend/hooks/usePriceData.ts:54-103` | Every 5 s | These mutate the cached price series locally; they do not prove exchange freshness. |
| Simulated worker loop | `src/trading/SimulatedTradingService.cpp:1832-1908` | 1 s sleep after each cycle | Synthetic ticks are nominally one second apart, except network/database work and settling. |
| Simulated live-data fetch | `src/trading/SimulatedTradingService.cpp:879-937` | One request per selected symbol; max 2 attempts | DNS/TLS/exchange-response categories stop retrying immediately; other failures may retry once. |
| Live worker quote acquisition | `src/trading/LiveTradingService.cpp:2309-2408` | No post-cycle sleep in the inspected source | Each cycle is bounded by quote/account/database/exchange work rather than a fixed minute cadence. |
| Live quote fan-out timing | `src/trading/LiveTradingService.cpp:2352-2372` | Measured per batch in `fetch_ms`; request-rate logged | The implementation logs requested/attempted/succeeded/skipped/fetch_ms/rate, but no live sample was available. |
| Signal/model/gate path | `src/trading/SimulatedTradingService.cpp:1201-1355` | Synchronous within tick | Model inference is attempted only for `ml_enhanced_orderbook`; failures fall back to heuristic diagnostics. |
| Paper intent/fill path | `src/trading/SimulatedTradingService.cpp:1766-1793`, `1498-1558` | Same tick; synthetic fill immediately in non-live-execution mode | Live-parity increments executable intents and routes to paper position creation; actual live fills are a separate pending path. |
| Live fill reconciliation | `src/trading/SimulatedTradingService.cpp:838-876` and corresponding live service path | Next worker iterations; no timestamp sample | Accepted-but-not-filled orders remain pending until exchange lookup succeeds. |

## Evidence-based assessment

1. **The approximately one-minute cadence is most directly attributable to the price-data widget's frontend implementation.** `usePriceData` explicitly refetches every 60 seconds and generates historical points at 60-second spacing. This is a source-level finding, not a fresh runtime measurement.
2. **The order-book signal and simulated-stat widgets are configured much faster (3 seconds) and can be event-driven through the native WebSocket.** A one-minute visual update for those widgets would therefore require a missing/unavailable producer, stale runtime, failed backend proxy, cache behavior outside these hooks, or a UI component not consuming these hooks. The current runtime state supports the unavailable-backend explanation, but does not distinguish it from all other possibilities.
3. **Backend worker cadence is not a one-minute scheduler.** Synthetic simulation has a one-second loop sleep. The live worker has no fixed sleep after the cycle in the inspected source, so quote/account/network latency and symbol fan-out determine cycle duration. The live code logs the required fan-out timing fields, but no live backend container was running to produce samples.
4. **Historical runtime evidence shows frontend/backend transport failure rather than slow successful responses.** The observed failures are DNS resolution errors and connection refusals. They prevent request completion and prevent any valid response/data-age or end-to-end latency measurement.
5. **The database was also unavailable during the current inspection window.** Interrupted shutdown recovery and fsync activity prevent reliable correlation against current signal/trade rows. No fill or paper-intent evidence was observed.
6. **The PostgreSQL `pg_input_is_valid` errors are a distinct backend/database compatibility failure.** They occurred while the frontend was attempting signal-related reads in the historical pane and can explain missing/failed signal data, but this run did not modify or retest that query.

## Required follow-up to close the runtime evidence gap

Run a fresh read-only capture after `trade_cpp-backend_1`, `trade_frontend_1`, and `trade_db_1` are healthy:

- Record browser Network/console timestamps for at least 5 status, signal, stats, price, and WebSocket events across at least 3 symbols.
- Capture backend logs containing at least 3 quote fan-out lines, fetch failures/retries, model inference/fallback lines, signal-gate decisions, paper intents, and fill/pending-fill transitions.
- Compare request start/end, backend log timestamps, signal timestamps, and `updated_at`/data timestamps to calculate response latency and age rather than inferring from polling intervals.
- Preserve whether the run is simulated, live-parity paper, or live; do not enable live order execution.
- Recheck the exact feature endpoints and `/health`; keep the investigation open if the backend remains unavailable or if no multiple-cycle evidence is produced.
