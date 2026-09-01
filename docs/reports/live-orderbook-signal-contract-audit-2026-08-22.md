# Live order-book signal contract audit

Date: 2026-08-22
Scope: C++ live producer, Coinbase/network client, persistence/readback, API route, and Live Trading frontend assumptions. This is a source audit; no live Coinbase session or runtime baseline was executed.

## Executive summary

- The live worker currently requests the entire selected universe on every worker iteration. There is no enforced per-tick symbol cap, cursor, rotation, or cadence sleep. `kQuoteFanoutWarningThreshold` is logging-only.
- Each quote is one sequential Coinbase public `GET /products/{symbol}/book?level=2` request. There is no retry/backoff or explicit HTTP-429 handling in the request path. A failed symbol is logged and omitted from that tick.
- The signal API is latest-by-symbol, not cumulative history: in-memory reads dedupe `recent_signals_` by symbol; persisted reads use `DISTINCT ON (symbol)`. `pagination.total_signals` is the number of filtered latest symbols, while the per-row `total_signals` field is a cumulative tick formula and is not used for pagination.
- Active in-memory responses serialize the complete live producer payload, including `criteria_analysis`, `ml_analysis`, `strength_composition`, and `execution_analysis`. Persisted readback preserves the JSON payload but legacy/malformed rows can lack nested fields.
- `active_signals` counts non-`hold` latest rows in the API response, including signals blocked by ML, profitability, spot-only, cash, notional, pending-order, or disabled-live-execution gates. It is not executable order count. Diagnostics separately expose executable intents and blocker counts.
- Start is fail-closed on Coinbase account valuation/recovery and explicit `live_order_execution`; stop prevents new work but lets accepted orders and pending writes settle. The destructor sets shutdown and joins the worker.

## Source map and end-to-end path

1. Route declarations: `include/api/PredictController.hpp:32-41`.
   - `GET /api/orderbook/live-signals`
   - `POST /api/trading/live/start`
   - `POST /api/trading/live/stop`
   - `GET /api/trading/live/status`
   - `POST /api/trading/live/update-strategy-params`
   - live portfolio/close/liquidation/execute routes are adjacent.
2. Route handlers: `src/api/PredictController.cpp:1230-1248,1269-1287,1348-1365`.
   - Live signal query parses comma-separated symbols; defaults are page 1 and `per_page=10`.
   - Start/stop pass JSON or no payload directly to `LiveTradingService`.
3. Service API and state: `include/trading/LiveTradingService.hpp:27-42,97-126,180-237,239-292`.
   - `SignalRecord` stores IDs, symbol, signal, strength, prices, book depth/volume, and `total_signals`.
   - `recent_signals_` and account/order/persistence state are service-local.
4. Worker: `src/trading/LiveTradingService.cpp:2309-2437`.
   - Resolve pending orders; flush writes; select quote batch; fetch quotes/account; generate tick; dispatch orders; flush writes.
5. Coinbase integration: `src/exchange/CoinbaseAdvancedClient.cpp:119-228,230-295,297-394,480-560`.
   - `request` signs authenticated calls, waits up to 15 seconds, parses HTTP status, and returns one result.
   - `getOrderBook` calls the public level-2 book endpoint and aggregates up to 20 bid/ask levels.

## Coverage, cadence, batching, and rotation

- Selected universe input: `startSession` accepts every string in `payload.symbols`, defaults to `BTC-USD, ETH-USD, SOL-USD` when empty (`src/trading/LiveTradingService.cpp:2810-2821`). No backend symbol cap or dedupe is applied here.
- Batch selection: `selectLiveQuoteBatchLocked` copies all `symbols_` into the batch and records attempted count (`src/trading/LiveTradingService.cpp:1244-1263`). The current implementation has no cursor, rotation, or per-tick cap.
- Fetch cadence: `workerLoop` calls `fetchLiveQuotes` once per iteration (`src/trading/LiveTradingService.cpp:2330-2375`). `fetchLiveQuotes` iterates symbols sequentially and calls `getOrderBook` once per symbol (`src/trading/LiveTradingService.cpp:1208-1241`). There is no normal sleep after a completed tick. The only explicit sleep is one second while stopping/settling (`2337-2349`), plus persistence/shutdown polling sleeps.
- Logging/diagnostics: elapsed fetch milliseconds and estimated requests/sec are logged (`2352-2372`). `kQuoteFanoutWarningThreshold=10` is warning-only (`src/trading/LiveTradingService.cpp:41-53,2368-2372`); diagnostics report `live_quote_symbols_per_tick_cap=0` and `quote_fanout_limit_enforced=false` (`2526-2582`).
- Failure coverage: a symbol whose book request fails is logged and skipped (`1215-1227`); no placeholder is created until the API read path adds a response-only missing row.
- Important interpretation: the repository reference in `~/.hermes/skills/software-development/live-trading-systems/references/live-orderbook-signal-coverage.md:7-38` describes the safer bounded rotating pattern, but this checkout deliberately implements the unbounded/logging-only variant. Treat the reference as review guidance, not runtime evidence.

## Signal generation and payload

- Book parsing: Coinbase uses best bid/ask, sums up to 20 levels, computes depth, mid, absolute spread, and `(bid_volume-ask_volume)/(bid_volume+ask_volume)` imbalance (`src/exchange/CoinbaseAdvancedClient.cpp:514-560`).
- Order-book signal: `buildSignalRecordLocked` uses `abs(imbalance)*1.15`, clamps strength to 1, and generates a buy for nonnegative imbalance or sell for negative imbalance when strength >= 0.22 (`src/trading/LiveTradingService.cpp:1516-1581`). Non-order-book strategies use rolling price history and `evaluateStrategySignal` (`1547-1568`).
- Rolling state: one price history per symbol is retained to `kMaxPriceHistory=512` (`151-153,1527-1545`).
- `SignalRecord.total_signals`: set to `tick_ * max(1,symbols_.size()) + symbol_index + 1` (`1580-1581`). This is a cumulative generated-position counter approximation, not the API pagination total and not a persisted-row count.
- Active serializer: `signalToJson` emits IDs/session/symbol/type/signal_generated/strength/price/timestamp/reason/data_status/spread/volume/buy/sell volume/imbalance/prediction plus `criteria_analysis`, `ml_analysis`, `strength_composition`, and `execution_analysis` (`517-542`).
- Criteria analysis: `buildSignalRecordLocked` emits `bid_ask_squeeze`, `volume_imbalance_buy`, and `volume_imbalance_sell` with enabled, meets_criteria, deltas, thresholds, and text (`1608-1631`). The squeeze threshold is imbalance 0.2 while its field is named `threshold_spread` and set to 0.0025; this is a schema/semantic naming question for consumers.
- Data status: only reasons containing `insufficient price history` or `warming up` become `insufficient`; generated/blocked live order-book rows remain `sufficient` (`143-146,1593-1601,1760-1768`).

## ML and profitability gates

- For `ml_enhanced_orderbook`, ready ONNX models provide classifier win probability and regressor or transformer expected PnL (`1633-1684`). If inference fails or models are unavailable, heuristic fallback is labeled `heuristic-fallback`, with configurable `orderbook_expected_return_scale_percent` defaulting to 2.4% (`1686-1703`; constant at `41-47`).
- Non-order-book strategies mark expected return unavailable and report a diagnostic-only profitability structure (`1704-1730`).
- Order-book profitability gate uses expected return, spread/mid, round-trip fee, slippage, and minimum signal strength parameters (`1733-1756`). A failed gate rewrites the signal to HOLD and sets `signal_reason` to the gate reason (`1757-1769`).
- ML confidence gate: non-ML strategies pass; fallback honors `fallback_to_baseline` default true; model signals require buy probability >= `confidence_threshold` default 0.6, or sell probability <= 1-threshold (`1805-1833`).
- Execution analysis (`1835-1931`) starts blocked and classifies: no signal, profitability gate, ML confidence, account management, existing position, pending order, max positions, invalid size/price, below minimum notional, spot cannot open short, insufficient cash, and live execution disabled. Only a buy with all gates passing and explicit execution enabled becomes `executable_intent=true`.
- Position sizing reads parameters and current Coinbase-derived cash/positions, then live stats/cohort metrics (`409-479`). Defaults include 1% percent sizing, `max_positions=100`, and `position_update_interval=5` (`2866-2877`), but the actual position-size and fee/edge values should be recorded from the start payload for any runtime baseline.

## Active signals, pagination, and aggregation semantics

- Tick production iterates every selected symbol but only processes symbols with a valid fetched quote (`src/trading/LiveTradingService.cpp:2226-2253`). Each valid quote produces a signal row, including HOLD rows, and queues it for persistence.
- In-memory query path (`3242-3363`) filters selected symbols, keeps the newest timestamp per symbol (`3260-3272`), adds non-persisted `data_status=missing` HOLD placeholders for requested symbols with no latest row (`3280-3307`), sorts by strength/timestamp/symbol (`3310-3318`), then paginates.
- In-memory `pagination.total_signals`, `total_analyzed`, and `active_signals` are based on `filtered.size()` and non-HOLD rows across the full filtered latest-by-symbol set (`3320-3353`). Thus `total_signals` is latest-symbol coverage, not cumulative signal history; `active_signals` is latest non-HOLD count, not executable count. Missing placeholders count in total and lower average strength but not active count.
- Persisted fallback path (`3366-3461`) counts `COUNT(DISTINCT symbol)` (`3387-3392`), selects `DISTINCT ON (symbol)` latest rows (`3400-3408`), and applies SQL page/offset. It sets active count from returned page rows (`3438-3452`), while `total_signals` is distinct-symbol total (`3456-3461`). This differs from the in-memory path, which computes active count over all filtered latest rows before slicing the page. This is a frontend/API contract risk when persistence is used after a restart.
- Frontend route defaults `per_page=10` (`src/api/PredictController.cpp:1244-1247`), but page size is display-only in the current hook. `frontend/hooks/useTrading.ts:375-445` chunks universes over `ORDERBOOK_SYMBOL_CHUNK_SIZE`, requests each chunk with `per_page=chunk.length`, merges, and then applies UI pagination. Failed chunks are surfaced in diagnostics and make `coverage_complete=false` (`391-429`).
- Frontend type contract is `frontend/types/trading.ts:45-172`. It explicitly models nested criteria/ML/execution diagnostics and coverage fields, but `total_signals` is not represented in the shown signal summary type; the merged response normalizer is therefore the effective contract (`frontend/hooks/useTrading.ts:314-370`).

## Retention, persistence, and diagnostics

- In-memory retention: 100 recent trades and `max(250, symbols_.size())` recent signals (`src/trading/LiveTradingService.cpp:1934-1942`; constants `48-49`). This is enough for one full selected-universe sweep only when the universe is <=250; it is not a durable history contract.
- Schema: `order_book_signals` stores one row per signal with scalar book fields, JSON `signal_data`, and `total_signals` (`332-353`). Writes are batched/upserted outside the mutex; failures requeue pending writes (`1409-1513`).
- `signal_data` is JSON serialized with the full payload, including execution attribution (`1796-1801` and `flushWrites` around `1409-1504`). Persisted readback parses legacy JSON and overlays scalar fields; malformed JSON is guarded into an empty object (`3415-3437`).
- Diagnostics: `buildOrderBookSignalDiagnosticsLocked` counts unique symbols, recent rows, non-HOLD recent rows, executable intents, blocker buckets, strength buckets, and expected-return buckets (`2526-2576`). `coverage_complete` compares unique symbols in retained signal history against requested symbols (`2577-2579`), so it can be false due to quote failures or retention while the worker continues normally. `active_recent_signal_records` is actually all non-HOLD retained records, not only the latest row per symbol; the name is potentially misleading.
- Status stats: `buildStatusJson` reads persisted `individual_trades` for the session, excludes account-managed/liquidation trade types, and falls back to in-memory session inputs when persistence is empty (`2585-2655`). This couples live status statistics to Postgres availability but does not use synthetic capital.

## Account snapshot coupling and order outcomes

- Start creates a Coinbase client, fetches accounts and tickers to value non-USD/USDC holdings, and fails before activation if this snapshot cannot be loaded (`src/trading/LiveTradingService.cpp:2767-2809`; account fetch `1266-1297`). Credentials are read from `COINBASE_API_KEY` and `COINBASE_API_SECRET` (`148-152,2791-2797`).
- Each worker iteration refreshes the account snapshot after market quotes (`2353-2377`) and applies it before signal generation (`2384-2395`). If refresh fails, the tick still proceeds with the last in-memory account state; the error is logged and the live producer readiness can expose the prior error.
- `buildLiveTabProducerJson` reports Coinbase as source, zeroes portfolio fields if no snapshot is loaded, subtracts pending reserved cash, and sets `can_trade` only when active, credentials configured, account loaded, no snapshot error, and explicit live execution enabled (`2658-2764`).
- Existing account holdings are appended to the managed universe only for `manage_exits` or `manage_entries_and_exits`; entries remain blocked unless the latter mode is selected (`1313-1374,1875-1878,1991-1996`).
- Intent persistence: every order is inserted into `live_coinbase_orders` as `submitting` before submission; duplicate client IDs are refused (`895-918`). Accepted orders are marked pending; startup recovers `submitting`/`pending` rows (`921-1033`).
- Dispatch: stop/shutdown prevents remaining unsent intents; definitive rejection clears reservations, while inconclusive failures remain pending for recovery (`1035-1104`).
- Coinbase create success is distinct from fill: client polls fill details five times at 200ms intervals, then returns accepted/fill-pending; worker polling continues until terminal state (`src/exchange/CoinbaseAdvancedClient.cpp:349-372`, service `1106-1206`). Client-order lookup has a three-page recovery window; complete-not-found is retried up to 30 worker resolutions before marking `not_found` (`396-477`, service `1132-1149`). There is no provider-rate-limit-specific branch.
- Fills become `TradeRecord`s with actual fees and closing-leg classification; account-managed/liquidation trade types are excluded from session strategy stats (`654-720`, `608-621`).

## Stop Trading and shutdown safety

- `stopSession` serializes lifecycle, sets `stop_requested=true` and `active=false`, clears unsent intents/reservations, and returns `settling` when accepted Coinbase orders remain (`src/trading/LiveTradingService.cpp:2930-2954`). It does not cancel accepted Coinbase orders.
- Worker behavior after stop: it stops generating new ticks, sleeps while accepted orders/pending writes settle, then exits once those queues are empty (`2309-2349`). It performs up to three final persistence flush attempts with 250ms/500ms delays (`2412-2437`).
- Destructor sets `active=false`, `stop_requested=true`, `shutdown_requested=true`, then joins (`281-293`). In-flight network request timeout is bounded by the client request timeout and fill polling observes shutdown cancellation (`CoinbaseAdvancedClient.cpp:188-192,353-361`; service `1041-1044`).
- Frontend `stopTrading('live')` POSTs `/api/trading/live/stop` and marks parity inactive only after an HTTP-success response (`frontend/lib/api.ts:882-913`). The control disables Stop when inactive or loading (`frontend/components/dashboard/TradingControls.tsx:19-39`). Accepted-order settling is returned by the backend, but the generic frontend stop path does not expose a dedicated settling-state UI contract.

## Configuration/defaults to record for a reproducible baseline

Record the exact start payload and environment (without secrets): selected `symbols`, `strategy`, `parameters`, `position_size_percent` or dollar mode/value, `max_positions`, `position_update_interval`, `confidence_threshold`, `fallback_to_baseline`, `round_trip_fee_percent`, `slippage_buffer_percent`, `min_orderbook_signal_strength`, `orderbook_expected_return_scale_percent`, `account_position_management`, stop-loss/take-profit settings, and `live_order_execution=true`. Defaults observed in source include default symbols above, position size 1% (`409-426`), max positions 100, interval 5, confidence threshold 0.6, fallback true, and heuristic scale 2.4%.

## Unresolved questions / follow-up acceptance targets

1. Is unbounded full-universe polling intentional after the prior cadence-cap change? If yes, define an operator-approved throughput/rate-limit budget and capture provider 429/error evidence; if no, implement a documented cursor/batch policy without silently shrinking the selected universe.
2. Should `active_recent_signal_records` and `active_signals` be renamed or split into latest non-HOLD versus all retained non-HOLD versus executable intents? Acceptance should require each count to have one unambiguous definition.
3. Should `pagination.total_signals` remain latest-by-symbol, and should the per-row `total_signals` field be renamed to avoid implying the same semantic? Acceptance should verify live in-memory, post-restart DB, and frontend chunk-merge responses agree.
4. Persisted fallback computes active count from the returned page while in-memory computes it across all filtered latest rows. Decide and test one contract.
5. `criteria_analysis.bid_ask_squeeze.threshold_spread` currently describes an imbalance threshold. Rename or document its units before using it for operator decisions.
6. Add explicit quote diagnostics for failed symbols and HTTP status/rate-limit counts. Current diagnostics only infer failures as requested minus successes and the quote client collapses HTTP errors into strings.
7. Define freshness/stale-age semantics for missing placeholders and for a latest retained row after quote failure. Current API has `data_status=missing` but no stale age.
8. Define whether a successful account refresh is required before every tick. Current behavior continues using prior account state after refresh failure, while `can_trade` is sensitive to the stored snapshot error.
9. Define frontend behavior for backend `status=settling` after Stop Trading; current generic API wrapper returns JSON but controls only model `isActive`.
10. Runtime baseline remains outstanding: for a fixed selected universe, capture per-tick attempted/succeeded/skipped symbols, fetch duration/request rate, HTTP errors/429s, queue depths, latest signal count, active/latest versus executable counts, signal strength and signed expected edge, blocked-intent reasons, fills/fees, stale age, and stop-settlement duration. No live credentials or network run was used for this audit.

## Verification status

Read-only source inspection completed across C++ service/client/API, frontend hooks/types/control/API wrapper, and the matched Hermes guidance under `/home/kahlil/.hermes/skills/software-development/live-trading-systems/`. No code was changed; no local build/test was run or required for this documentation-only audit. The report is evidence-backed by the line references above, but runtime/provider-limit and exact latency claims require a controlled non-trading observation run.
