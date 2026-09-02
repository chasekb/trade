# Simulated-execution data-flow investigation

Date: 2026-09-02
Scope: end-to-end selected-universe propagation, frontend cadence, simulated/live-parity worker execution, fills, and reporting. This is an investigation report only: no source or runtime behavior was changed, no local build/test was run, and no live order or account mutation was performed.

## Executive verdict

The selected symbol universe is preserved through the frontend start request, backend session creation, payload serialization, and worker iteration. There is no source evidence of a frontend cap, deduplication, sort, or pagination truncating the worker universe. All selected symbols reach the worker loop when the session payload is non-empty; the important exception is per-symbol quote acquisition: symbols whose quote request fails after the bounded retry path are excluded from that tick's signal and execution path.

The approximately one-minute observation is not explained by the simulated signal/stat polling path. Those hooks poll at 3 seconds and can receive native WebSocket cache events. The direct source-level one-minute cadence is the price-history widget (`usePriceData`, 60-second refetch and generated point spacing). Backend synthetic simulation sleeps one second after each cycle; live-parity quote acquisition is sequential and bounded by network/exchange work rather than a minute scheduler. Current runtime evidence cannot prove successful-cycle latency or fill cadence because the frontend/backend were not running and PostgreSQL was unhealthy/recovering during capture.

## End-to-end dependency-aware sequence

1. `SimulatedTradingPanel` owns the selected `symbols` state. Its start action calls `apiClient.startTrading` with the symbols array unchanged. The panel then propagates active status and renders the session-backed queries.
2. The simulated start endpoint aliases route to `PredictController` (`src/api/PredictController.cpp`, controller start handlers). `PredictController` validates `execution_mode` and forwards the request payload without rewriting the symbols array.
3. `SimulatedTradingService::startSession` copies every symbol string from `payload.symbols` into session state (`src/trading/SimulatedTradingService.cpp`, start-session implementation). Only an empty input takes the documented default (`BTC-USD`, `ETH-USD`, `SOL-USD`). No cap, dedupe, or sort occurs here.
4. The worker loop (`SimulatedTradingService::workerLoop`, `src/trading/SimulatedTradingService.cpp:1832-1908`) iterates the selected symbols once per tick and sleeps one second after the cycle. In live-parity mode, quote acquisition requests each selected symbol sequentially; the fetch path (`:879-937`) allows at most two attempts per symbol. DNS/TLS/exchange-response failures terminate that symbol's attempt path; other failures may retry once. A failed quote is omitted from that tick's signal/execution inputs.
5. `generateTickLocked` evaluates each available symbol, runs signal/model logic, attaches `execution_analysis`, and either records a blocker or routes an eligible intent to paper execution (`src/trading/SimulatedTradingService.cpp:1201-1355`, `:1732-1810`). ML inference is synchronous within the tick and only attempted for `ml_enhanced_orderbook`; model failure falls back to heuristic diagnostics.
6. The simulated paper/live-parity path creates synthetic fills locally (`src/trading/SimulatedTradingService.cpp:1470-1559`, `:1562-1637`, `:1639-1729`). Synthetic simulation uses the signal/current price and fixed fee rate; live-parity uses Coinbase public quotes but never submits an exchange order. A gate/blocker therefore prevents an intent or fill; it does not imply that the symbol was absent from the worker universe.
7. Signal and portfolio data are serialized by `buildPortfolioJson` and `signalToJson`; `std::map` containers make emitted signal/quote order lexicographic. This reorders presentation but does not remove selected symbols. The backend exposes `symbols` and `selected_symbol_count` for coverage.
8. Frontend queries in `frontend/hooks/useTrading.ts` poll simulated signals and stats every 3 seconds (`:433-444`, `:483-497`), and status every 5 seconds while active (`:76-89`). Native WebSocket events (`:598-615`, `:661-697`) can update caches immediately; the 30-second heartbeat is liveness only. If more than 50 symbols are requested for signal display, the frontend chunks requests into groups of 50 and merges responses before display pagination. This is a request/display transport detail, not a worker-universe cap.
9. The price widget is a separate path: `frontend/hooks/usePriceData.ts:36-51` refetches every 60 seconds, and `:13-15` constructs mock history at 60-second spacing; its development “real-time” cache updates occur every 5 seconds (`:54-103`). This is the strongest source explanation for an approximately one-minute chart update, but not proof of exchange freshness.
10. For actual live Coinbase execution (not simulated/live-parity), `LiveTradingService::workerLoop` and `generateTickLocked` build signals and apply gates; `dispatchOrders` persists `live_coinbase_orders` before submission, and `resolvePendingLiveOrders` later obtains terminal fill details. `CoinbaseAdvancedClient::placeMarketOrder` distinguishes acceptance from fill. `applyLiveFillLocked` then creates `individual_trades`, updates positions/PnL, and refreshes the account snapshot. This separate path must not be conflated with simulated paper fills.

## Timing and latency comparison

| Stage | Configured/observed timing | Evidence and meaning |
|---|---:|---|
| Simulated signal query | 3 s | `frontend/hooks/useTrading.ts:433-444`; UI refresh cadence, not backend production cadence. |
| Simulated stats query | 3 s | `frontend/hooks/useTrading.ts:483-497`. |
| Active status query | 5 s | `frontend/hooks/useTrading.ts:76-89`. |
| WebSocket heartbeat | 30 s | `frontend/hooks/useTrading.ts:598-615`; liveness, not publication. |
| Generic query defaults | stale 300 s / refetch 30 s | `QueryProvider`; applies only where those defaults are selected. |
| Price-history refetch | 60 s | `usePriceData.ts:36-51`; direct one-minute frontend cadence. |
| Mock history spacing | 60 s | `usePriceData.ts:13-15`. |
| Mock chart cache update | 5 s | `usePriceData.ts:54-103`; local mutation, not provider latency. |
| Simulated worker sleep | 1 s after each cycle | `SimulatedTradingService.cpp:1832-1908`; actual tick duration additionally includes fetch, DB, model, and gate work. |
| Per-symbol live-parity fetch | up to 2 attempts | `SimulatedTradingService.cpp:879-937`; sequential fan-out means total cycle time grows with selected symbols and response/retry latency. |
| Order-book aggregation | up to 20 bid/ask levels; 10 s HTTP timeout / 15 s future wait | `getOrderBook` path; timeout bounds a request but does not establish observed latency. |
| Live quote fan-out | no fixed post-cycle sleep; logs `fetch_ms` and request rate | `LiveTradingService.cpp:2309-2408`; runtime sample unavailable. |
| Model/gate path | synchronous within tick | `SimulatedTradingService.cpp:1201-1355`; no measured inference sample. |
| Simulated paper fill | same tick after gates | `SimulatedTradingService.cpp:1498-1558`; synthetic/local, not exchange acknowledgement. |

These are configured/source timings, not measured end-to-end timestamps. The runtime capture at approximately `2026-08-23T07:02:44Z` found `trade_cpp-backend_1` and `trade_frontend_1` in `created` state, `trade_db_1` running but unhealthy/starting, and Redis healthy. Backend/frontend logs were empty in the inspected recent window. PostgreSQL showed initialization/shutdown/recovery activity between approximately `07:01:15` and `07:03:35 UTC`; `pg_isready` rejected connections while starting. Historical tmux output showed frontend DNS failures (`getaddrinfo ENOTFOUND cpp-backend`) and connection refusals to `10.89.1.7:8080`, plus PostgreSQL `pg_input_is_valid(text, unknown)` undefined-function errors. These prove transport/database failures, not slow successful response intervals.

## Causality classification

Confirmed causal findings:

- The one-minute chart behavior is directly supported by `usePriceData`'s 60-second refetch and point spacing.
- Signal/stat simulated widgets are configured for 3-second polling and may be event-driven via WebSocket; a one-minute interval is not configured in those paths.
- The simulated worker is nominally one-second paced, while live-parity duration depends on sequential per-symbol fetch and bounded retries.
- Selected symbols are preserved into the worker unless the input is empty (default substitution); quote failure removes a symbol only from the affected tick's downstream signal/execution inputs.
- Historical DNS/connection/database errors can prevent frontend data refresh and persistence; they do not establish a fill or worker-cadence failure.

Correlated but not proven causal:

- The unavailable backend and unhealthy database correlate with missing/stale widgets, but no successful multi-cycle browser/backend trace distinguishes producer outage, cache staleness, or a consumer defect.
- Sequential fan-out and retries could correlate with low observed fill frequency as the universe grows, but no live `fetch_ms`, request-rate, quote-age, model, or gate samples were captured.
- PostgreSQL compatibility errors correlate with missing signal reads, but the affected query and current deployment frequency were not retested.

Not causal by the available evidence: frontend table pagination (display-only after chunk/merge), lexicographic `std::map` ordering, WebSocket heartbeat interval, and order acceptance itself being treated as a fill. Source and deterministic tests distinguish acceptance from terminal fill and preserve opening-versus-closing accounting semantics. A separate confirmed reporting defect remains: mixed inherited/session-managed closes can suppress managed PnL in `LiveTradingService::applyLiveFillLocked` (`:711-725`), but runtime occurrence is unknown and it does not explain selected symbols failing to reach the worker.

## Blockers and follow-up checks

Confirmed blockers/evidence gaps:

- No running frontend/backend during capture; no fresh browser, WebSocket, worker, model, gate, or fill timestamps.
- PostgreSQL unhealthy/recovering; current persistence and read-side comparisons are unavailable.
- Historical backend DNS/connection failures and PostgreSQL function-compatibility errors.

Unconfirmed:

- Actual end-to-end latency from frontend request through worker signal, paper intent, fill, persistence, and cache update.
- Whether any selected symbol is systematically omitted beyond per-tick quote failures.
- Runtime frequency of retries, quote age, model fallback, gate blockers, pending writes, and mixed inherited closes.
- Whether the approximately one-minute symptom was observed in the price widget or incorrectly attributed to signal/stat widgets.

Recommended read-only checks before any fix:

1. Start/restore only the simulated or live-parity stack (never live order execution), wait for healthy frontend/backend/database, and capture at least three cycles across at least three selected symbols.
2. Correlate browser request/event timestamps, backend worker/fan-out logs (`requested`, `attempted`, `succeeded`, `skipped`, `fetch_ms`, rate), quote timestamps, model/fallback/gate lines, paper intents, fills, DB rows, and WebSocket cache updates.
3. Assert `selected_symbol_count`, worker attempted/succeeded/skipped counts, and per-symbol identifiers at each boundary; preserve the exact input order and use a deliberately >50-symbol display probe to distinguish chunking from worker coverage.
4. Reconcile persisted signal, order/intent, fill, and closing-leg counts. For live-only verification, require explicit approval and an independent review; do not infer live fills from simulated/live-parity results.
5. Add a mixed inherited/session-managed partial-close fixture and separately define the authoritative gross/net PnL contract before implementing changes.

## Evidence inventory

Primary evidence: completed frontend trace, backend simulated-trading trace, runtime cadence evidence report, fill/realized-PnL trace, and order/fill reporting audit supplied by parent tasks. Their exact-SHA evidence includes runtime report commit `4f62004da9ff30f79452aff03b074a94f692778b` and successful Docker Build Validation run `32624634891`; those remote build results validate the evidence artifact only and do not replace missing runtime measurements. No application files were modified by this investigation.
