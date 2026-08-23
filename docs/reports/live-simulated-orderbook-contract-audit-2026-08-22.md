# Live/Simulated Order-Book Contract Audit

Date: 2026-08-22
Task: `t_ca98b8d9`
Scope: checked-in C++ services, API controller, frontend client/widget, and the existing runtime-oriented parity references. This is an audit and instrumentation baseline; it does not submit live orders.

## Executive summary

The repository currently has two simulated surfaces:

1. The normal backend simulated service uses deterministic synthetic market state and a one-second worker tick.
2. The frontend local fallback (`FORCE_LOCAL_SIM_TRADING` or an active local session) synthesizes its own signals in `frontend/lib/api.ts`.

The Live Trading service uses Coinbase public order-book quotes and, on every worker iteration, requests the complete selected universe. It has no enforced quote cap or cadence sleep; a warning threshold of 10 is logging-only. The live worker also refreshes the Coinbase account snapshot before signal generation and dispatches exchange orders only after the signal tick and persistence handoff.

The backend simulated service and live service share the signal serializer and profitability/ML gate semantics, but they do not have identical source data, retention, diagnostics, or execution authority. The frontend local fallback is not a faithful backend simulation: it uses a separate synthetic formula, paginates in memory, and does not expose the backend diagnostics contract.

No runtime tab replay was performed in this checkout: no live credentials, running stack, selected universe, or captured API session was available, and this audit must not invent timings or account outcomes. Existing code instrumentation provides live quote fetch elapsed time and estimated request rate; the normalized metric capture plan below identifies the remaining measurements needed for a same-universe run.

## Source map

| Surface | Source/function | Evidence |
|---|---|---|
| Live route | `include/api/PredictController.hpp:32-33`, `src/api/PredictController.cpp:1230-1266` | `/api/orderbook/live-signals` and `/api/orderbook/simulated-signals`; `page`/`per_page` default to 1/10. |
| Live worker | `src/trading/LiveTradingService.cpp:2309-2409` | Fetches quotes outside mutex, refreshes account snapshot, generates tick, dispatches orders and flushes writes outside mutex. |
| Live quote selection | `LiveTradingService.cpp:1244-1263` | Copies all `symbols_`; requested/attempted fields are set to the full selected universe. |
| Live quote timing | `LiveTradingService.cpp:2352-2377` | `fetch_ms`, estimated quote requests/sec, fan-out warning, and account-refresh warning are logged. |
| Live diagnostics | `LiveTradingService.cpp:2526-2582` | Counts latest symbols, active latest rows, blockers, strength/expected-return buckets, batch, coverage, and contract text. |
| Live API aggregation | `LiveTradingService.cpp:3242-3467` | In-memory latest-by-symbol path plus DB `COUNT(DISTINCT symbol)`/`DISTINCT ON` fallback; missing selected symbols become response-only rows. |
| Live stop | `LiveTradingService.cpp:2930-2954` | Sets inactive, clears undispatched intents/reserves, and reports `settling` while accepted Coinbase orders remain pending. |
| Simulated worker | `src/trading/SimulatedTradingService.cpp:1832-1935` | One-second loop; synthetic or live-parity quotes, tick generation, order/persistence handoff outside mutex. |
| Simulated signal state | `SimulatedTradingService.cpp:2006-2064`, `include/trading/SimulatedTradingService.hpp:239-252` | Latest signal per selected symbol; cumulative session counters; market-data status per symbol. |
| Simulated API aggregation | `SimulatedTradingService.cpp:2420-2476` | Latest-by-symbol filtering, pagination, all-row active count and average strength. |
| Simulated stop/start | `SimulatedTradingService.cpp:2220-2305` | Resets session state at start; stop marks inactive and lets worker drain pending work. |
| Shared payload | `LiveTradingService.cpp:517-542`, `SimulatedTradingService.cpp:489-515` | Same top-level signal fields and nested criteria/ML/strength/execution objects. |
| Frontend backend client | `frontend/lib/api.ts:1011-1071` | Backend endpoint selection; local simulated short-circuit; fallback response on request failure. |
| Frontend local fallback | `frontend/lib/api.ts:432-548` | Generates every selected symbol, paginates locally, and reports only basic summary fields. |
| Frontend widget | `frontend/components/dashboard/OrderBookSignalsTable.tsx:51-54`, `355-430` | Uses `pagination.total_signals`/`total`; displays coverage diagnostics and active count. |
| Frontend type contract | `frontend/types/trading.ts:45-120`, diagnostics at `:121-170` | Signal, criteria, ML, execution, and diagnostic fields consumed by UI. |

## Parity matrix

Classification vocabulary: **safety-required**, **accidental drift**, **frontend artifact**, or **intentionally different but undocumented**.

| Contract area | Simulated backend | Live backend | Classification and consequence |
|---|---|---|---|
| Selected universe | `symbols_`; one generated signal per selected symbol per worker tick. | `symbols_`; full vector copied into each quote batch. Account-exit management may append account holdings to `symbols_` (`LiveTradingService.cpp:1317-1325`). | Full-universe target is shared. Account-managed symbol expansion is **safety-required** and must be shown as selected-universe change. |
| Quote source | Synthetic state unless `mode_ == live_parity`; persistent imbalance/price state feeds the next tick. | Coinbase public order-book summary (`mid`, spread, bid/ask, imbalance, volume, depth). | **Intentionally different but documented**: synthetic data cannot equal exchange data. `market_data_source` identifies it. |
| Per-tick coverage | All selected symbols; one-second loop. | All selected symbols per iteration; no hard cap, no cadence sleep; warning threshold 10 only. | Same coverage goal. Network fan-out/rate-limit risk is **safety-required**. Current no-cap policy is observable only in logs/diagnostics, not a backend budget. |
| Batching/rotation | No quote queue or rotation; vector snapshot then tick. | `selectLiveQuoteBatchLocked` currently returns all symbols; no cursor/rotation. | No hidden rotation. Any future bounded scheduler must preserve full-universe coverage and expose lag/backpressure. |
| Tick timing | One-second sleep after tick; synthetic generation and DB flush are separate phases. | No explicit cadence sleep in the inspected tail; iteration duration is dominated by quote/account network calls, dispatch, flush, and loop sleep shown later in the worker. | **Intentionally different but undocumented** at metric level: live has no normalized tick/sweep timing payload. |
| Latest-by-symbol state | `recent_signals_` is a map, one latest record per symbol (`SimulatedTradingService.hpp:239-243`). | `recent_signals_` is a deque capped by `kMaxRecentSignals=250`; API rebuilds latest-by-symbol from it. | **Accidental drift**: live retention can under-represent a universe larger than 250, while simulated state is universe-sized. The API emits missing placeholders only when request symbols are supplied. |
| `pagination.total_signals` | Count of filtered latest-by-symbol rows, not cumulative DB/session history (`SimulatedTradingService.cpp:2426-2436`). | Active in-memory path count includes latest rows plus response-only missing placeholders; DB fallback is `COUNT(DISTINCT symbol)` (`LiveTradingService.cpp:3387-3397`). | **Frontend/API artifact risk**: callers must treat this as current response population, not generated history. Missing placeholders make live total selected-universe-oriented. Normalize with explicit `total_scope`. |
| Page size | API clamps page/per-page to >=1; widget defaults to 10 and allows 10/25/50/100. | Same. | **Frontend artifact** if a visible 10 is mistaken for generation cap. |
| Signal payload | `signal_id`, session, symbol, type/signal, generated, strength, price, timestamp, reason, data status, spread/volume, volumes, imbalance, prediction, criteria, ML, strength composition, execution analysis. | Same serializer fields. | Shared normalized shape. |
| `criteria_analysis` | Produced by synthetic/backend signal builder; frontend local fallback has squeeze and buy imbalance examples. | Produced from Coinbase-derived feature evaluation. | Data-source difference is **intentionally different**; field names and units must remain shared. Frontend should tolerate optional criteria entries. |
| ML/profitability gate | Shared gate; gated candidates become `hold`, `signal_generated=false`, `data_status=sufficient`; execution analysis identifies `profitability_gate`. | Same shared gate and serializer; account/order gates occur downstream. | Shared safety contract; **safety-required** live blockers must not be collapsed into no-data. |
| `active_signals` | Counts non-`hold` latest rows across the filtered population, not current page. | Same in-memory path; DB fallback counts returned page rows, which can disagree with all-population semantics. | **Accidental drift** in cold/DB fallback; fix by counting the same latest population used for `total_signals`, independent of page. |
| Average strength | All filtered latest rows, not current page, in in-memory simulated path. | All filtered rows in active path; DB fallback divides by returned page row count. | **Accidental drift** in DB fallback; normalized contract should define population scope. |
| Recent signal retention | Latest-per-symbol map is not an arbitrary history cap. | `kMaxRecentSignals=250` deque; history cap is separate from latest API aggregation. | **Intentionally different but undocumented** operational retention, but accidental for parity if selected universe exceeds 250. Expose retained count and oldest age. |
| Diagnostics | Selected/latest/retained/evaluated/generated/executable/warming/rejected/blockers; per-symbol market-data status and failures. | Requested/attempted/succeeded/skipped, batch, latest/retained/active/executable, blocker/strength/edge buckets, coverage, contract. | **Accidental drift** in field availability: live lacks simulated-style cumulative evaluation/warming fields and simulated lacks live quote timing/rate fields. Add a normalized envelope rather than overload fields. |
| Account snapshot | Synthetic capital/cash; live-parity paper mode can use live public quotes and live-like gates but remains paper. | Account snapshot is refreshed each worker iteration before tick; cash/holds/positions are authoritative for live execution. | **Safety-required**. Account refresh failure must block live execution and be visible separately from signal generation. |
| Expected/realized edge | Expected return and fee-adjusted edge in signal ML analysis; paper fills update realized/unrealized PnL. | Same expected fields; realized outcomes are exchange-fill/accounting dependent and use confirmed Coinbase fees. | Data/execution difference is **safety-required**; report expected vs realized separately. |
| Order dispatch | Normal simulated mode creates paper fills; `live_parity` uses live-like gates but no exchange dispatch. | `dispatchOrders` happens after tick and outside mutex; pending orders settle asynchronously. | **Safety-required** live-only authority, cash/hold, spot-side, minimum-notional, pending-order, exchange acceptance/fill blockers. |
| Stop Trading | Sets inactive; worker stops generating, drains pending writes/orders according to mode. | Sets inactive; undispatched intents are cleared and reserves released; accepted orders remain pending until terminal resolution; response can be `settling`. | **Safety-required** difference. UI must preserve `settling` and never claim all external orders are canceled. |
| Frontend local simulation | Separate synthetic sine/phase formula; every selected symbol; local portfolio and recent trades in browser; `pagination.total` only. | Backend route and live status polling. | **Accidental drift / frontend artifact**: local simulation is a fallback, not a parity fixture. It lacks diagnostics, `total_signals`, and backend execution blockers. |

## Signal payload and normalized response contract

The recommended normalized response is:

```json
{
  "signals": ["<page of latest-by-symbol rows>"],
  "pagination": {
    "page": 1,
    "per_page": 10,
    "total_signals": 0,
    "total_scope": "latest_by_symbol_selected_universe",
    "total_pages": 0,
    "has_next": false,
    "has_prev": false
  },
  "summary": {
    "selected_symbol_count": 0,
    "evaluated_symbol_count": 0,
    "latest_signal_count": 0,
    "active_signal_count": 0,
    "average_strength": 0,
    "last_updated": null
  },
  "diagnostics": {
    "coverage_contract": "full_selected_universe_latest_by_symbol",
    "attempted_symbols_this_tick": [],
    "quote_success_count": 0,
    "missing_latest_symbols": [],
    "stale_symbol_age_seconds": null,
    "oldest_signal_age_seconds": null,
    "tick_duration_ms": null,
    "sweep_duration_ms": null,
    "queue_depth": 0,
    "api_error_count": 0,
    "rate_limit_count": 0,
    "blocked_intents": {},
    "expected_edge": null,
    "realized_edge": null,
    "execution_outcomes": {},
    "account_snapshot": {"loaded": false, "age_seconds": null, "error": null},
    "stop_state": "running"
  }
}
```

Each `signals[]` row should preserve the existing fields: `signal_id`, `session_id`, `symbol`, `signal_type`/`signal`, `signal_generated`, `strength`/`signal_strength`, `price`, ISO `timestamp`, `signal_reason`, `data_status`, `spread`, `volume`, `buy_volume`, `sell_volume`, `imbalance_ratio`, `prediction`, `criteria_analysis`, `ml_analysis`, `strength_composition`, and `execution_analysis`. `data_status=sufficient` means evaluation data was usable even when the strategy decided HOLD; `insufficient`/`missing` are reserved for unavailable or warming data.

`total_signals` must never mean cumulative generated records. It is the count of the latest signal row per selected symbol after request filtering, and the response must say so. Pagination must not change `active_signal_count` or `average_strength` population scope.

## Instrumentation and baseline capture

### Already instrumented in source

- Live quote batch: selected/requested, attempted, succeeded, skipped, current batch (`LiveTradingService.cpp:1244-1263`, `2526-2576`).
- Live quote elapsed time and estimated request rate (`LiveTradingService.cpp:2352-2372`).
- Live account snapshot success/failure warning (`LiveTradingService.cpp:2374-2377`); account age/error are not serialized yet.
- Latest signal count, retained records, active records, executable intents, blocker counts, strength buckets, expected-return buckets, coverage (`LiveTradingService.cpp:2526-2582`).
- Simulated evaluated/generated/executable/warming/rejected counters and per-symbol market-data status (`SimulatedTradingService.cpp:2012-2064`).
- Frontend widget displays selected, attempted, quote successes, missing/latest, retained, executable, blockers, strength and expected-return buckets (`OrderBookSignalsTable.tsx:355-389`).

### Missing measurements required for a same-universe run

The repository does not currently serialize a comparable per-tick record for sweep duration, tick duration distribution, stale age, queue depth, rate-limit count, account snapshot age, or realized-vs-expected edge. Capture these without changing live behavior:

1. Start both tabs with the exact same ordered symbol list and strategy parameters; record git SHA, mode, session IDs, parameter JSON (excluding secrets), and start/stop timestamps.
2. Sample every status/signal response with page 1 and a page size large enough to cover the universe; retain raw JSON and timestamp.
3. Derive per tick: selected count, attempted symbols, latest count, generated/active count, oldest/latest timestamp age, quote success ratio, sweep and tick duration, and request errors/rate limits from logs.
4. Join `execution_analysis` blocker reasons with persisted signal/outcome rows. Report expected edge, realized net edge after confirmed fees, blocked intents, accepted orders, fills, rejects, and pending settlement separately.
5. Report p50/p95 over at least 20 ticks only after raw timestamps are available. Until then, all values are `unobserved`, not zero.

### Baseline status from this audit

| Metric | Backend static evidence | Runtime observation in this run |
|---|---|---|
| Selected symbols / attempted per tick | Full selected vector in both backend workers | Unobserved; no live session replay |
| Generated/latest signals | Simulated map; live deque + latest aggregation | Unobserved |
| Sweep/tick duration | Live quote `fetch_ms` log exists; simulated one-second loop exists | No log/session capture |
| Stale-symbol age/freshness | Missing response field; timestamp is available per row | Unobserved |
| Queue depth | Pending order vectors exist; no quote queue metric | Unobserved |
| API errors/rate limits | Per-symbol live fetch warnings; no structured 429 counter | Unobserved |
| Blocked intents | Backend blocker counters and execution analysis exist | Unobserved |
| Active/strength/expected edge | Response/diagnostic fields exist | Unobserved |
| Realized edge/execution outcomes | Trade persistence and live fill reconciliation exist | Unobserved; no orders submitted |

## Bottleneck classification

| Candidate bottleneck | Current evidence | Classification / required observation |
|---|---|---|
| Network/API I/O | Live fetches Coinbase order books serially in `fetchLiveQuotes`; account snapshot then lists accounts and values holdings with tickers. | Likely primary live bottleneck; measure per-symbol and account call latency, errors, 429/timeout response class. Do not increase fan-out without an exchange budget. |
| Rate limits | Warning threshold is logging-only; no structured rate-limit counter or token bucket. | Safety gap/unknown. Add provider response classification and configured request budget before adaptive concurrency. |
| Account snapshots | Live refresh is coupled to every worker iteration before signal generation. | Safety-required authority, but cadence can dominate tick time. Measure snapshot latency/age and separate snapshot cadence only with explicit stale-account execution gate. |
| CPU/ML | Signal generation occurs while service mutex is held; transformer warming/rejected counters exist only in simulated diagnostics. | Measure inference duration and mutex wait. A future worker pool must keep order-intent decisions serialized per symbol. |
| Database flushes | Writes are taken under mutex and flushed outside mutex in both workers. | API starvation is reduced, but flush time and pending write depth are not exposed. Measure batch size/duration/failures. |
| Mutex contention | API status and tick mutation share `mutex_`; network/DB/dispatch are outside it. | Measure lock wait/hold time before redesign. Avoid holding the mutex over network or DB. |
| Frontend polling/page size | Widget page size is display-only; local fallback slices after generating all symbols. | Frontend artifact can make 10 look like a cap. Label totals as latest-by-symbol and keep diagnostics outside page slicing. |
| Order dispatch | Live intents are dispatched after generation; pending symbols prevent duplicates and fills settle asynchronously. | Safety-required serialization. Measure queue/pending age, accepted/rejected/fill latency; Stop Trading must prevent new intents but not abandon accepted orders. |

## Stop Trading state contract

- UI stop calls local clear for browser-only simulated mode (`frontend/lib/api.ts:882-890`); this does not contact the backend.
- Backend simulated stop sets `active=false`, requests worker stop, and returns `settling` if pending order symbols exist (`SimulatedTradingService.cpp:2287-2305`).
- Backend live stop clears undispatched orders and releases their reserved cash, marks inactive, and returns `settling` if accepted live orders remain (`LiveTradingService.cpp:2930-2954`).
- Accepted exchange orders must continue fill lookup and persistence reconciliation. A successful Stop Trading response is not proof of cancellation or zero fills.
- No new signal generation or order intent may occur after the stop flag is observed. A quote fetch already in flight may complete, but the post-fetch stop check must discard its tick, as implemented at `LiveTradingService.cpp:2383-2398` and `SimulatedTradingService.cpp:1884-1896`.

## Recommended follow-up contract and verification

1. Add a shared diagnostic envelope with explicit `total_scope`, `summary` population scope, per-tick timing, freshness, queue/backpressure, provider error/rate-limit, account snapshot, and execution outcome fields.
2. Replace live deque-only latest state with a bounded structure whose capacity is at least the selected universe, or expose an explicit retention/missing contract when that cannot be guaranteed. Do not silently multiply global diagnostics when the frontend chunks symbol requests.
3. Fix DB fallback active-count and average-strength scope to use the full latest population, not only the current page.
4. Add structured timing/error instrumentation to simulated and live paths before any throughput change; retain raw samples for p50/p95 comparison.
5. Design bounded adaptive quote scheduling using provider budget, queue depth, tick duration, error/429 rate, and stale age. Reject unbounded `hardware_concurrency` fan-out.
6. Add tests for: latest-by-symbol totals, active-count across pages, missing placeholders, shared payload fields, sufficient HOLD vs insufficient data, live stop during quote fetch, accepted-order settlement, account snapshot failure, rate-limit backoff, bounded queue cancellation, and duplicate-order prevention.
7. Run the same-universe comparison only in a safe paper/sandbox or read-only live-data mode. Do not use live order submission as a benchmark. Record expectancy/profit-factor/drawdown only when authoritative outcomes exist.

## Verification boundary

No local C++/Docker build or live order was run for this audit. The artifact is a source-grounded design/audit document. Any implementation that follows must use the repository's remote-CI-only delivery policy and must not be considered closed until the exact pushed SHA has green required GitHub Actions jobs. Runtime metrics in this report remain explicitly unobserved until a same-universe instrumented session is captured.
