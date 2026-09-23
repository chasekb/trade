# TRADE-BL-0027 investigation — live order-book universe and no-positive-PnL claim

Date: 2026-08-23
Scope: read-only source and evidence classification. No live session, order, account change, production configuration change, or behavior change was made by this investigation.

## Executive determination

The observation that the live order-book universe produced no positive-PnL trades is **not confirmed from the available evidence**. The repository contains the instrumentation and source paths needed to measure the claim, but no reproducible runtime dataset was supplied for a bounded session/time window with signal, intent, order, fill, fee, and realized-PnL joins. The strongest defensible conclusion is:

- **Confirmed:** source-level paths can generate signals, suppress them into explicit blockers, submit accepted orders only when live execution is explicitly enabled, and attribute terminal fills/persistence separately from accepted orders.
- **Confirmed:** several coverage/freshness and observability risks can make runtime outcomes difficult to interpret, especially serial full-universe quote fan-out, no normal cadence sleep in the worker loop, absent quote-age validation, and additive aggregation of chunk-level diagnostics.
- **Ruled out by source inspection:** the widget's display pagination silently caps the selected universe; missing widget rows create order intents; simulated fallback data directly drives live orders; accepted order responses are equivalent to terminal fills.
- **Unknown:** whether the affected deployment actually experienced provider failures/rate limits, stale quotes, adverse selection, unfavorable round-trip costs, model miscalibration, blocker-dominated flow, or accounting distortion. Runtime traces and reconciled data are required.

This is an investigation result, not a strategy or parameter recommendation and not a closeout of TRADE-BL-0027.

## Reproduced dataset and time window

No runtime dataset was available in the repository or task handoffs that can be reproduced as a complete outcome window. Therefore the following are **unavailable**, not zero:

| Required evidence | Status | Consequence |
|---|---|---|
| Session identifier and UTC start/end | Unknown | Cannot establish population or time boundary. |
| Selected symbol list as sent to live start | Unknown at runtime | Source preserves the payload, but deployment selection was not captured. |
| Per-symbol quote request timestamps, status, latency, quote age | Unknown | Cannot quantify coverage, rate limiting, or staleness. |
| Signal rows with execution analysis | Source-supported, runtime absent | Cannot count generated signals or blocker buckets for the affected window. |
| Intent/submission/order IDs and terminal fills | Runtime absent | Cannot distinguish accepted orders from filled trades. |
| Gross PnL, fees, net realized PnL, and closing-leg classification | Runtime absent | Cannot confirm any positive or non-positive PnL claim. |
| Symbol and signal-bucket outcome cohorts | Runtime absent | No defensible ranking by symbol, side, strength, or expected-return bucket. |

The existing execution-attribution closeout explicitly states that TRADE-BL-0027 remains open pending a runtime window with fees, spread, slippage, fills, blockers, and realized PnL (`docs/reports/live-orderbook-execution-attribution-closeout-2026-08-04.md:96-98`).

## Exact code paths

### Universe and quote handling

1. `frontend/components/dashboard/LiveTradingPanel.tsx:560-583` uses the selected symbols for the live order-book view; `:607-632` sends the live start payload, including strategy, symbols, parameters, `max_positions`, `position_update_interval`, and explicit `live_order_execution` confirmation.
2. `frontend/hooks/useTrading.ts:257-444` fetches live signal data in chunks of 50 (`ORDERBOOK_SYMBOL_CHUNK_SIZE`), merges settled responses, and applies display pagination. The chunk mechanism avoids a frontend page-size cap, but failed chunks leave partial coverage and chunk diagnostics are merged in the browser.
3. `frontend/hooks/useTrading.ts:440-442` polls live order-book data every three seconds. The live widget is not updated through the simulated-only WebSocket cache path.
4. `src/api/PredictController.cpp:1230-1248` parses `symbols`, `page`, and `per_page` and delegates `/api/orderbook/live-signals` to `LiveTradingService::getOrderBookSignals`.
5. `src/trading/LiveTradingService.cpp:2810-2821` copies the start payload symbols verbatim (or uses defaults when empty). This boundary does not normalize or deduplicate symbols.
6. `src/trading/LiveTradingService.cpp:1208-1242` fetches every selected symbol serially. Failed order-book requests are logged and omitted from the quote map.
7. `src/trading/LiveTradingService.cpp:1244-1263` selects the entire `symbols_` vector. The threshold is diagnostic-only; it is not a request cap.
8. `src/trading/LiveTradingService.cpp:2309-2403` runs the worker loop: pending orders are reconciled, the full quote batch and account snapshot are fetched, `generateTickLocked(quotes)` runs, orders are dispatched, and writes are flushed. There is no normal post-tick cadence sleep in the inspected live path; only the stop/settling branch sleeps.
9. `src/trading/LiveTradingService.cpp:1266-1297` loads account balances and values non-USD holdings with additional ticker requests. Account refresh failure is logged and the prior state may remain in use; the affected runtime sequence is unknown without logs.

### Signal, intent, blockers, and execution

The source-level execution-attribution contract is documented in `docs/reports/live-orderbook-execution-attribution-closeout-2026-08-04.md:28-80`. It records signal generation separately from executable intent and classifies, without loosening safety gates, profitability, ML confidence, position, pending-order, maximum-position, sizing, minimum-notional, spot-short, cash, and explicit-live-execution blockers.

`src/trading/LiveTradingService.cpp:2286-2298` shows one close/reopen path: opposite signal or age-out closes a position; reopening additionally requires authority, position capacity, and the ML gate. This is an exit/entry policy path, not evidence that the affected run reached it.

`src/trading/LiveTradingService.cpp:2319-2322` and `:1162-1188` establish that accepted orders remain pending until an exchange fill is found, applied, persisted, and marked terminal. Therefore an accepted order count must not be used as a filled-trade count.

### Persistence and PnL attribution

`src/api/PredictController.cpp:1710-1759` reads persisted signal rows with a bounded page size and optional `session_id`/`trade_type` filters, then extracts `execution_analysis` fields including `signal_generated`, `executable_intent`, blocker, side, diagnostic factor, expected return, and fee-adjusted expected return.

`src/api/PredictController.cpp:1762-1786` reads `individual_trades` and computes closing-leg realized PnL as `gross_pnl - fees`. New rows use explicit `is_closing_leg`; legacy NULL rows fall back to the historical nonzero-PnL convention. This is a known accounting limitation for historical exact-flat exits: without explicit legacy classification, a flat gross exit with fees cannot be proven to be a closing leg from that fallback alone.

`docs/reports/execution-reconciliation-closeout-2026-08-08.md:86-89,135-139` records that the reconciliation surface is the instrument for the runtime evidence still required by TRADE-BL-0027.

## Failure-mode classification

| Failure mode | Classification | Evidence and interpretation |
|---|---|---|
| Selected universe silently truncated by widget pagination | Ruled out (source) | The widget paginates already merged rows; requests over 50 are chunked and merged in `frontend/hooks/useTrading.ts:257-444`. This does not rule out a failed chunk or a narrower upstream universe. |
| Frontend fallback narrows the deployed universe | Unknown at runtime; source risk confirmed | Upstream universe discovery/fallback behavior can select fewer symbols, but the affected browser response and selected-symbol payload were not captured. |
| Missing widget rows create executable intents | Ruled out | Missing rows are response/display placeholders; they are not signal records and cannot create orders. |
| Serial quote fan-out causes uneven coverage or latency | Confirmed as source risk; runtime impact unknown | `fetchLiveQuotes` serially requests all symbols and skips failed requests (`src/trading/LiveTradingService.cpp:1208-1242`). No per-symbol runtime latency/status trace is available. |
| Unbounded worker cadence / request pressure | Confirmed as source behavior; runtime impact unknown | The worker loop has no normal sleep after a tick (`src/trading/LiveTradingService.cpp:2309-2403`); fan-out warning is logging-only. No provider headers or request-rate trace exists. |
| Stale quote used for a signal | Unknown | Quote values are read from the current fetch, but no exchange timestamp or max-age validation is attached to `MarketQuote`; quote age and decision latency are not in the evidence. |
| Adverse selection / fill slippage | Unknown | No terminal fill-price versus decision-price join for the affected window. Source instrumentation exposes intended/realized fields but cannot substitute for fills. |
| Round-trip fees/spread/slippage exceed edge | Unknown | The profitability and fee-adjusted expected-return gates are source-supported, but no realized gross PnL, fees, spread, or slippage cohort was supplied. |
| Weak signal or expected-return/model calibration | Unknown | Source gates can produce valid HOLD/block outcomes; no out-of-sample calibration or realized signal-bucket cohort is available. |
| Profitability/ML/position/cash/min-notional blockers suppress intents | Confirmed as possible mechanisms; prevalence unknown | The blocker taxonomy and gates are documented in the attribution closeout; runtime blocker counts were not supplied. |
| Spot-only sell/short direction prevents entries | Confirmed as possible mechanism; prevalence unknown | The attribution taxonomy explicitly includes `spot_cannot_open_short`; no affected-window side counts exist. |
| Accepted orders counted as fills | Ruled out by source contract | Pending-order reconciliation waits for terminal fill evidence (`src/trading/LiveTradingService.cpp:1120-1205`, `:1162-1188`). |
| Simulated fallback drives live orders | Ruled out by source boundary | Live start requires Coinbase account initialization and explicit `live_order_execution`; simulated services use separate endpoints. No evidence of a cross-path leak was found. |
| Account refresh failure affects submission state | Unknown at runtime; source behavior confirmed | Refresh failures are logged (`src/trading/LiveTradingService.cpp:2374-2377`); the affected logs and ordering relative to submission are missing. |
| Legacy accounting misclassifies exact-flat closing legs | Confirmed limitation for legacy NULL rows | `src/api/PredictController.cpp:1778-1785` explicitly falls back to `gross_pnl != 0.0` when `is_closing_leg` is NULL. |
| Frontend diagnostic counts overstate coverage | Confirmed source/reporting defect; PnL impact unknown | Chunk-level snapshot fields are summed in `frontend/hooks/useTrading.ts:329-354`; current/latest populations can overlap. This can mislead coverage interpretation but does not itself change fills or PnL. |
| No-positive-PnL observation itself | Unknown / not confirmed | No bounded, reconciled runtime outcome dataset was supplied. |

## Objective metrics

No affected-window values can be truthfully reported for average win, average loss, expectancy, profit factor, drawdown, or blocked-intent rate. They are **unavailable**, not zero. The repository's objective conventions remain: net realized PnL is after fees; average loss remains negative; profit factor uses gross positive divided by absolute gross negative PnL; drawdown is dollars, not percent; and zero-PnL open legs are excluded from win/loss denominators. See `docs/STRATEGY_OBJECTIVE.md` and `docs/reports/simulated-trading-statistics-audit-2026-08-02.md:21-25`.

The minimum runtime extraction to confirm the claim is: one UTC-bounded session; selected symbols; every quote attempt with timestamp/status/latency; every persisted signal and execution analysis; every intent and blocker; exchange order/client IDs; terminal fill prices and fees; closing-leg classification; and reconciled net realized PnL. Joins must be by session, symbol, signal/intent/order identifiers where available, and time—not by widget row count.

## Validation and coverage limitations

Existing coverage includes deterministic strategy-signal, expectancy, position-sizing, execution-reconciliation, portfolio-accounting, execution-cohort, Coinbase order/portfolio, trading-stats, and frontend universe/API/start-payload/reconciliation/statistics tests. Historical evidence records 10 frontend Jest suites / 58 tests and a prior exact-SHA Docker Build Validation run, but that evidence is not a reproduction of the affected runtime window and must not be used to claim this investigation's runtime hypothesis is proven. No local builds or tests were run for this read-only task under the remote-only policy.

Material missing coverage:

- replay or paper-parity fixture joining quote age, signal, intent, order, fill, fees, and net PnL;
- per-symbol provider failure/rate-limit/latency capture;
- signal-to-intent blocker denominator and bucket-level outcome report;
- exact-flat legacy closing-leg fixture;
- post-fill slippage and decision-to-fill latency cohorts;
- browser-selected-universe capture versus backend `symbols_` and widget payload.

## Ranked next actions (investigation-first)

1. Capture and reconcile one bounded runtime/paper-parity window before changing parameters. This is prerequisite evidence for average win/loss, expectancy, profit factor, drawdown, and blocked-intent rate; preserve all live safety gates and require independent review for any account/execution change.
2. Add non-invasive per-symbol quote attempt/status/latency/timestamp evidence and reconcile it with generated signals. Expected impact: distinguish coverage/freshness causes from legitimate no-trade outcomes and quantify blocked-intent rate; do not add request caps or loosen gates as a substitute for evidence.
3. Produce signal-bucket and blocker-bucket outcome cohorts, including intended side and terminal fill status. Expected impact: identify whether average loss and expectancy are dominated by entries, exits, round-trip costs, or suppression; parameter experiments are not closure.
4. Measure decision-to-fill price/latency and fee/spread/slippage drag for completed round trips. Expected impact: quantify adverse selection and average loss; no execution-policy change should proceed without independent high-risk review and rollback criteria.
5. Repair/validate legacy closing-leg attribution and frontend diagnostic population semantics as separate implementation work. Expected impact: improve accounting/reporting reliability and drawdown/profit-factor observability; neither change proves positive expectancy by itself.

Separate implementation backlog items should carry explicit execution, validation, rollback, safety-gate, independent-review, and closeout criteria. TRADE-BL-0027 remains open until the runtime/replay evidence exists; a parameter change or green build alone is not closure.

## Change and verification record

- Production code/configuration: unchanged.
- Live account/session/orders: untouched.
- Repository artifact: this report only.
- Local builds/tests: not run; remote-only policy followed.
- CI: no new code/configuration change was made by this investigation, so no new Docker Build Validation evidence is claimed here. Historical CI references above are explicitly historical and do not prove the runtime finding.

## Sources

- `src/trading/LiveTradingService.cpp:1120-1205,1208-1297,2286-2305,2309-2408,2767-2859`
- `src/api/PredictController.cpp:1230-1286,1710-1803`
- `frontend/components/dashboard/LiveTradingPanel.tsx:560-632`
- `frontend/hooks/useTrading.ts:257-444`
- `docs/reports/live-orderbook-execution-attribution-closeout-2026-08-04.md`
- `docs/reports/execution-reconciliation-closeout-2026-08-08.md`
- `docs/reports/trade-backlog-current-closeout-2026-08-08.md`
- `docs/STRATEGY_OBJECTIVE.md`
- `docs/reports/simulated-trading-statistics-audit-2026-08-02.md`
