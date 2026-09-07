# TRADE-BL-0021 — Live/simulated order-book throughput normalization closeout

Timestamp: 2026-08-05T15:08:15Z

## Scope

This report closes the current audit/report-backed implementation state for `TRADE-BL-0021 — Normalize live and simulated order-book signal throughput safely`.

The item asks to document the simulated order-book signal-generation contract, document and diff the live contract, classify each divergence, and normalize live behavior where safe without violating exchange/API limits or live trading expectancy constraints.

This closeout builds on the already-implemented order-book parity, widget coverage, execution-attribution, and non-order-book diagnostic slices, and adds one small simulated-read normalization so active in-memory `active_signals` and `average_strength` are computed across the full latest-by-symbol population before display pagination:

- `docs/reports/live-simulated-signal-execution-delta-2026-07-27.md`
- `docs/reports/live-simulated-orderbook-signal-parity-closeout-2026-08-02.md`
- `docs/reports/live-orderbook-widget-coverage-closeout-2026-08-03.md`
- `docs/reports/live-orderbook-execution-attribution-closeout-2026-08-04.md`
- `docs/reports/non-orderbook-diagnostics-closeout-2026-08-05.md`

No local Docker, CMake, backend build, or compiled C++ test binary was run. No Coinbase orders were submitted. No live session was restarted. This report is source-audit and closeout documentation for checked-in behavior that is still gated by exact pushed-SHA Docker Build Validation.

## Objective and safety constraints

The project objective is risk-adjusted live expectancy, not raw signal count. Throughput normalization therefore means making Live Trading and Simulated Trading expose comparable selected-universe, latest-by-symbol, signal-contract, diagnostics, and pagination semantics where safe. It does not mean removing Coinbase/API cadence limits, live execution preflights, account readiness checks, min-notional checks, pending-order checks, max-position checks, cash/holding checks, explicit `live_order_execution` opt-in, or profitability gates.

## Simulated order-book signal-generation contract

Audited source paths:

- `src/trading/SimulatedTradingService.cpp:940-1180`
- `src/trading/SimulatedTradingService.cpp:2109-2293`

Current simulated contract:

1. Signal source
   - Order-book strategies use imbalance from live quote data when a valid quote is available; otherwise synthetic simulated market state produces price, imbalance, spread, depth, and volume (`src/trading/SimulatedTradingService.cpp:940-961`).
   - Non-order-book strategies use shared indicator evaluation over rolling price history (`src/trading/SimulatedTradingService.cpp:968-990`).

2. Order-book signal fields
   - Rows include `signal_id`, `session_id`, `symbol`, `signal_type`, `signal`, `signal_generated`, `signal_strength`, `price`, `timestamp`, `signal_reason`, `data_status`, `spread`, `volume`, buy/sell volume, imbalance ratio, prediction, criteria analysis, and ML/profitability diagnostics (`src/trading/SimulatedTradingService.cpp:992-1160`).

3. Order-book profitability contract
   - Generated order-book candidates run through `evaluateOrderBookProfitabilityGate(...)` with expected return, spread, round-trip fee, slippage buffer, and minimum signal strength (`src/trading/SimulatedTradingService.cpp:1160-1180`).
   - Gate diagnostics include `fee_adjusted_expected_return`, `required_edge`, `profitability_gate_passed`, and `profitability_gate_reason`.
   - A generated candidate that fails the gate becomes a sufficient-data `hold` instead of an executable buy/sell.

4. Latest-by-symbol read contract
   - The read API returns the latest signal per symbol from in-memory recent signals while active or from persisted `order_book_signals` otherwise (`src/trading/SimulatedTradingService.cpp:2125-2189`, `2192-2293`).
   - `pagination.total_signals` and `total_analyzed` count latest-by-symbol rows, not cumulative signal history (`src/trading/SimulatedTradingService.cpp:2155-2165`, `2183-2185`, `2213-2223`, `2276-2287`).
   - Display pagination slices the latest-by-symbol rows after sorting by strength/timestamp.

5. Counting semantics
   - For active/in-memory reads, `active_signals` counts generated rows across the full latest-by-symbol filtered population before display pagination, matching the live active/read contract (`src/trading/SimulatedTradingService.cpp:2168-2185`).
   - For active/in-memory reads, `average_strength` averages the full latest-by-symbol filtered population before display pagination (`src/trading/SimulatedTradingService.cpp:2168-2185`).
   - Persisted stopped-session fallback reads still share the existing database-page behavior with the live stopped-session fallback path and are not live-throughput evidence (`src/trading/SimulatedTradingService.cpp:2237-2278`).

## Live order-book signal-generation contract

Audited source paths:

- `src/trading/LiveTradingService.cpp:1500-1712`
- `src/trading/LiveTradingService.cpp:2491-2544`
- `src/trading/LiveTradingService.cpp:3205-3326`

Current live contract:

1. Signal source
   - Order-book strategies use Coinbase live quote/order-book snapshots and live imbalance (`src/trading/LiveTradingService.cpp:1500-1539`).
   - Non-order-book strategies use the same shared indicator evaluator over rolling live prices (`src/trading/LiveTradingService.cpp:1540-1552`).

2. Order-book signal fields
   - Live rows emit the same core payload fields as simulated rows: signal identity, symbol, signal type/action, generated flag, strength, price, timestamp, reason, data status, spread, volume, bid/sell volume, imbalance, prediction, criteria analysis, and ML/profitability diagnostics (`src/trading/LiveTradingService.cpp:1554-1619`).

3. Order-book profitability contract
   - Order-book heuristic fallback exposes `expected_return_available=true`, default/clamped expected-return scaling, confidence, and `model_version=heuristic-fallback` (`src/trading/LiveTradingService.cpp:1669-1685`).
   - Generated order-book candidates use the shared profitability gate before remaining actionable, matching the simulated contract from `TRADE-BL-0005`.

4. Live cadence diagnostics
   - This historical report predates the later explicit user request to remove the live quote cap and cadence sleep. Current diagnostics expose request/attempt/success/skip counts, `live_quote_symbols_per_tick_cap=0`, `quote_fanout_limit_enforced=false`, warning threshold, current batch symbols, latest-signal count, recent record count, active recent records, executable order-intent count, execution blocker counts, strength buckets, expected-return buckets, coverage completeness, and a human-readable contract (`src/trading/LiveTradingService.cpp`).

5. Selected-universe widget coverage
   - For active/in-memory reads with selected symbols, live adds response-only placeholder rows for selected symbols without a latest quote/signal yet (`src/trading/LiveTradingService.cpp:3243-3270`).
   - Placeholder rows are `hold`, `data_status=missing`, zero strength/price, and explain Coinbase quote rotation.
   - Placeholder rows are never persisted and never create order intents (`src/trading/LiveTradingService.cpp:3243-3247`).
   - `pagination.total_signals`, `total_analyzed`, `active_signals`, and `average_strength` are computed over the full selected/read latest-by-symbol population before display pagination (`src/trading/LiveTradingService.cpp:3283-3316`).
   - Diagnostics include `selected_symbol_count`, `missing_latest_signal_count`, `missing_latest_signal_symbols`, and `widget_coverage_contract` (`src/trading/LiveTradingService.cpp:3320-3325`).

## Frontend widget/fetch contract

Audited source paths:

- `frontend/hooks/useTrading.ts:300-418`
- `frontend/components/dashboard/OrderBookSignalsTable.tsx:188-235`
- `frontend/components/dashboard/OrderBookSignalsTable.tsx:260-275`
- `frontend/types/trading.ts:94-158`

Current frontend contract:

1. Large selected universes are chunked for API requests, but each chunk requests every selected symbol in that chunk (`per_page = chunk.length`) before client-side merge and display pagination (`frontend/hooks/useTrading.ts:389-410`).
2. Page size controls display only after chunk merge; it does not cap selected-universe coverage (`frontend/hooks/useTrading.ts:391-395`).
3. Diagnostics are merged across chunks, including selected/requested counts, quote attempt/success/skip counts, latest/missing rows, current batch symbols, per-tick cap, execution blocker counts, strength buckets, expected-return buckets, and coverage completeness (`frontend/hooks/useTrading.ts:320-352`).
4. The shared table renders expected return as `Unavailable` when `expected_return_available=false`, and shows fee-adjusted edge, required edge, diagnostic factor, and execution details when present (`frontend/components/dashboard/OrderBookSignalsTable.tsx:188-235`, `260-275`).

## Live versus simulated delta classification

| Delta | Classification | Current handling |
| --- | --- | --- |
| Coinbase live quotes versus synthetic simulated quotes | Required/intended data-source difference | Simulated may synthesize state; live uses Coinbase live quote snapshots. Reports must not claim synthetic rows are live market data. |
| Live per-tick quote cadence cap | Explicitly removed at user request; operational risk is observable rather than enforced | Live requests the full selected universe without a hard cap or normal cadence sleep; each batch logs fan-out, elapsed fetch time, estimated request rate, and warning-threshold crossings. `live_quote_symbols_per_tick_cap=0` and `quote_fanout_limit_enforced=false` make the absence of enforcement explicit. |
| Selected-universe widget coverage | Prior widget/read artifact, now normalized safely | Live read responses include response-only missing rows for selected symbols without latest quotes so pagination and totals represent the selected universe without changing quote cadence or order dispatch. |
| Frontend page size affecting coverage | Prior frontend artifact, now normalized | Chunked selected-universe requests fetch all symbols per chunk before merge; page size is display-only. |
| Latest-by-symbol total semantics | Shared active/read behavior | Both paths report latest-by-symbol counts for signal-widget totals rather than cumulative historical signal row counts. |
| Active-signal and average-strength counting | Prior in-memory simulated read artifact, now normalized | Active live and simulated reads now compute `active_signals` and `average_strength` over the full latest-by-symbol population before display pagination. Stopped-session persisted database fallback reads remain page-scoped and are explicitly not live-throughput evidence. |
| Order-book expected-return/profitability fields | Shared pre-execution signal contract | Both live and simulated order-book paths expose expected return, fee-adjusted edge, required edge, gate pass/fail, and gate reason before live-only blockers. |
| Gated valid HOLD versus insufficient WAITING | Shared UI semantics | Sufficient profitability-gated HOLD remains `HOLD`; insufficient/missing data is separate. |
| Live execution blockers | Required live-only safety deviation | Live execution attribution exposes blockers such as live execution disabled, pending order, max positions, spot-only sell/short, cash, and notional checks after signal generation and before any order submission. |
| Simulated fills versus Coinbase order submission/fills | Required execution difference | `TRADE-BL-0006` remains the dedicated live-parity paper mode item. This closeout does not claim simulated fills equal live fills. |
| Strategy parameter interpretation | Shared for the order-book pre-execution signal contract | Shared fallback scale, fee, slippage, and min-strength fields feed the profitability gate. Tuning/optimization remains under `TRADE-BL-0008` and `TRADE-BL-0016`. |

## Safety preservation

This closeout does not modify live order behavior. The audited implementation preserves:

- explicit `live_order_execution` opt-in;
- Coinbase client/account readiness;
- duplicate pending-order prevention;
- max-position and pending-entry caps;
- minimum-notional checks;
- cash/holding availability checks;
- Coinbase spot-only constraints;
- fee/spread/slippage profitability gates;
- account-position-management authority;
- live quote cadence limits;
- selected live universe values and retry behavior.

The only live selected-universe coverage normalization is read-only response shaping for the widget. Missing rows are explicit `hold`/`missing` placeholders and cannot submit orders.

## Closeout criteria mapping

1. Simulated Trading tab order-book signal-generation contract documented:
   - Covered in “Simulated order-book signal-generation contract” above with source references for per-tick generation, synthetic/live quote source, latest-by-symbol aggregation, pagination totals, payload fields, criteria analysis, ML/profitability gate fields, active-signal counting, and read retention.

2. Live Trading tab order-book signal-generation contract documented and diffed:
   - Covered in “Live order-book signal-generation contract,” “Frontend widget/fetch contract,” and “Live versus simulated delta classification.”
   - Each live/simulated difference is classified as required live safety/data-source deviation, prior artifact now normalized, shared pre-execution signal contract, or remaining backlog boundary.

3. Live order-book signal generation matches simulated semantics except explicitly documented live-exchange safety deviations:
   - Selected-universe coverage goals now match at the widget/read layer through response-only live missing rows and chunk-wide frontend fetches.
   - Payload shape, ML/profitability diagnostic fields, latest-by-symbol total semantics, active-signal counting, average-strength counting, pagination, strategy parameter interpretation, and widget labels are documented as shared or intentionally different.
   - Live-only exchange/account/order blockers remain downstream and visible rather than removed.

4. Exact pushed SHA verified by remote CI:
   - Pending until Docker Build Validation succeeds for the commit that adds this report.

## Remaining backlog boundaries

This closeout does not close:

- `TRADE-BL-0006` — live-parity paper execution/fills;
- `TRADE-BL-0008` — order-book signal-strength/expectancy tuning;
- `TRADE-BL-0014` — representative/runtime blocker attribution closeout;
- `TRADE-BL-0016` — active diagnostic factoring/ablation evidence;
- `TRADE-BL-0027` — root-cause investigation for no positive-PnL live order-book universe trades.

Those items require their own runtime/evaluation evidence and exact-SHA CI before closeout.

## Verification plan before push

Allowed local checks only:

- `git diff --check`;
- source/report contract scan for required report sections and audited field names;
- independent review blocker check that active simulated reads no longer compute active-count/average-strength metrics from only the display page;
- independent fresh-context review focused on overclaiming, live-trading safety, and closeout criteria mapping.

No local Docker/backend build will be run.
