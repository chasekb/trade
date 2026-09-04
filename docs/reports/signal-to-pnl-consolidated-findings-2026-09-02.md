# Consolidated signal-to-PnL findings

Date: 2026-09-02 (consolidated and revalidated 2026-09-04)
Repository: `https://github.com/chasekb/trade`
Scope: read-only source and evidence synthesis from the four upstream investigations.

## Executive conclusion

The implementation has a fail-closed path between a generated signal and a submitted live order. A valid market-data observation can produce a persisted signal, but it becomes an executable intent only after profitability, model-confidence, account, position, pending-order, risk, sizing, minimum-notional, direction, and explicit-live-execution checks. An executable intent is persisted before exchange submission; acknowledgement is not a fill, and fills are settled from exchange data before terminal accounting.

The source and deterministic fixtures prove the gate relationships and several accounting transformations. They do not prove the observed runtime cause of any particular low-signal, no-order, or no-positive-PnL period. The missing proof is a representative, read-only runtime join from selected symbols through quote timestamps, signals, intents, orders, fills, and realized PnL, together with browser payload/render evidence and calibrated model outcomes.

No live parameters, production behavior, credentials, account state, sessions, orders, or external trading systems were changed by this investigation or report.

## Ordered end-to-end flow

### 1. Universe selection and start payload

* `frontend/components/dashboard/SimulatedTradingPanel.tsx:57-60` owns product data, symbol mode, selected universe type (default `all_usd`), and custom text.
* `frontend/components/dashboard/SimulatedTradingPanel.tsx:87-124` fetches Coinbase `/products` when backend categories are missing or aliased, filters online/non-disabled products, and derives the selection without a slice cap. Discovery failure falls back to `frontend/lib/symbolUniverse.ts:3` (`FALLBACK_COINBASE_SYMBOLS`).
* `frontend/lib/symbolUniverse.ts:68-95` derives predefined categories; `:109-119` rejects incomplete/aliased backend categories; `:122-160` resolves predefined or custom selections and returns null for invalid custom input.
* `src/api/PredictController.cpp:1386-1413` emits hardcoded category responses. The response omits several declared keys and contains a narrower static `all_usd` list, so the frontend normally compensates with direct Coinbase discovery.
* `frontend/lib/api.ts:787-879` constructs the start payload and sends the exact symbols array to `/api/trading/live/start`. Live mode removes synthetic capital fields; simulated mode keeps them.
* `src/api/PredictController.cpp:1348-1357` forwards the JSON body to `LiveTradingService::startSession`.
* `src/trading/LiveTradingService.cpp:2810-2821` copies `payload.symbols` verbatim, defaulting only an empty selection to BTC-USD/ETH-USD/SOL-USD. It does not revalidate products before starting the worker.

Confirmed implication: frontend-selected symbols and backend category output can differ; discovery/CORS/fallback behavior is not proven for a specific runtime without captured browser/network evidence.

### 2. Session initialization and persistence

`src/trading/LiveTradingService.cpp:2767-2927` takes the lifecycle lock, ensures tables, obtains the Coinbase account snapshot, installs symbols/strategy/parameters, rejects synthetic capital fields in live mode, requires explicit `live_order_execution`, establishes the account baseline, recovers persisted submitting/pending orders, and starts the worker.

`src/trading/LiveTradingService.cpp:332-402` creates or repairs `order_book_signals`, `individual_trades`, and `live_coinbase_orders`. Signals and trades are queued and batch-upserted by `flushWrites` at `:1409-1513`; accepted orders are persisted before exchange submission and terminal status is updated after settlement.

`include/trading/LiveTradingService.hpp:97-146` defines market state, rolling history, signal fields, and `MarketQuote`; `:239-291` defines session state, caches, pending writes/orders, account snapshot, and exchange client. `recent_signals_` is trimmed at `src/trading/LiveTradingService.cpp:1934-1941`; current-session `session_trade_inputs_` is retained separately.

### 3. Quotes, cadence, and freshness

`src/trading/LiveTradingService.cpp:1208-1242` (`fetchLiveQuotes`) iterates selected symbols sequentially and calls Coinbase `getOrderBook`; failures are logged and omitted. `src/exchange/CoinbaseAdvancedClient.cpp:514-560` requests level-2 books, derives best bid/ask, midpoint, absolute spread, aggregate depth, and imbalance, and rejects empty/invalid books.

`src/exchange/CoinbaseAdvancedClient.cpp:119-227` uses a 10-second Drogon request timeout and 15-second future wait. Public order-book requests have no retry/backoff. No exchange quote timestamp or max-age check is carried into `MarketQuote`.

`src/trading/LiveTradingService.cpp:1244-1263` selects the full symbols vector. Diagnostics at `:2561-2568` explicitly report no quote cap and no fan-out limit. `workerLoop` at `:2309-2437` resolves pending fills, flushes writes, snapshots symbols, fetches all quotes and account state, generates one tick, dispatches orders, and immediately repeats; there is no normal cadence sleep or hard cap. Fetch duration and estimated request rate are logged at `:2352-2373`.

Confirmed source defect: the fan-out diagnostic reports attempted=requested and skipped=0 at `:2363-2367` even when individual requests fail; actual quote success is based on valid quote count. This can distort coverage displays, but a runtime sample is needed to quantify its effect.

### 4. Signal construction

`src/trading/LiveTradingService.cpp:2226-2307` (`generateTickLocked`) skips symbols without valid quotes, calls `buildSignalRecordLocked`, stores each signal, builds execution analysis, and only then considers opens/adds/closes.

`src/trading/LiveTradingService.cpp:1516-1802` updates per-symbol state, records local generation time, computes return, appends midpoint to a 512-entry rolling history, and records spread/bid/ask/depth/volume/imbalance. Order-book strength is `min(1, abs(imbalance)*1.15)` and requires strength >= 0.22; direction follows imbalance sign.

`src/trading/StrategySignal.cpp:113-303` implements buy-and-hold, DCA, SMA/EMA, RSI, Bollinger, MACD, stochastic, Fibonacci, warm-up holds, and unknown-strategy holds. Indicator strategies require rolling history. Warm-up states are marked `data_status=insufficient` at `LiveTradingService.cpp:1593-1600`; valid no-trade states remain sufficient.

For `ml_enhanced_orderbook`, `LiveTradingService.cpp:1633-1684` computes features and model outputs when the model pack is ready. If inference is unavailable or fails, `:1686-1730` uses the labeled heuristic fallback or marks expected-return diagnostics unavailable. This is not empirical calibration evidence.

### 5. Profitability and confidence gates

`src/trading/StrategySignal.cpp:305-341` (`evaluateOrderBookProfitabilityGate`) requires minimum strength and a directional expected edge strictly greater than round-trip fee + spread + slippage. Equality, negative edge, or unavailable expected return fails closed.

Defaults are declared at `src/trading/LiveTradingService.cpp:38-47` (1.5% round-trip fee, 0.2% slippage buffer, 0.22 minimum strength). Parameter application and diagnostic recording are at `:1733-1770`. A generated candidate that fails becomes a sufficient HOLD with a gate reason.

The ML confidence gate is at `:1805-1832`; loaded-model buys require `win_probability >= confidence_threshold`, sells require `<= 1-confidence_threshold`. Heuristic fallback behavior depends on `fallback_to_baseline`.

### 6. Generated signal versus executable intent

`buildEntryExecutionAnalysisLocked` at `src/trading/LiveTradingService.cpp:1835-1931` records whether the candidate is an executable intent and names blockers including:

* no signal or insufficient data;
* profitability or ML confidence gate;
* account/position management disabled;
* existing position or pending order;
* max positions;
* non-positive position size or price;
* below minimum notional;
* spot cannot open short;
* insufficient cash; and
* live execution disabled.

This is the key divergence boundary: signal fields describe the generated observation and model decision, while executable analysis adds current account, position, reservation, risk, and mode state. A generated signal therefore may be persisted and displayed while no intent is queued.

`openPositionLocked` at `:1991-2049` repeats safety checks and calls `positionSizeUsdForSignal` (`:409-479`). It uses current cash/positions, initial capital where applicable, cached live metrics, estimated fees, pending reservations, Coinbase minimum notional, spot-only direction rules, and explicit live execution. Close paths at `:2104-2149` use managed/account quantities and pending-order checks; liquidation checks at `:2154-2223` include finite values and minimum notional.

The complete divergence list established by source is:

| Generated signal condition | Execution consequence | Classification |
|---|---|---|
| Missing/invalid quote | No signal for that symbol in the tick | Market-data coverage/freshness; fail-closed suppression |
| Indicator warm-up / insufficient history | Sufficient or insufficient HOLD, no intent | Legitimate market/strategy outcome |
| Weak order-book strength | Candidate converted to HOLD | Profitability hurdle / blocker suppression |
| Expected edge <= fee + spread + slippage | Candidate converted to HOLD | Profitability hurdle / trading economics |
| Missing expected-return diagnostic | Fail-closed attribution/no intent | Blocker suppression; calibration evidence gap |
| ML confidence outside threshold | HOLD/no intent | Blocker suppression/calibration |
| Existing position | Duplicate/open suppression or close-policy path | Blocker suppression |
| Pending order | Duplicate submission suppressed | Blocker suppression |
| Max-position cap | Open suppressed | Sizing/blocker suppression |
| Non-positive/invalid size or price | Open suppressed | Sizing/blocker suppression |
| Coinbase minimum notional | Open/close suppressed | Sizing |
| Insufficient cash after pending reservations and estimated fee | Buy suppressed | Sizing/blocker suppression |
| Spot-only sell/short restriction | Opening short suppressed | Blocker suppression/legitimate policy |
| Account snapshot/authority unavailable | Session start fails or account state remains prior in memory | Market-data freshness/unknown runtime behavior |
| `live_order_execution` disabled | No live submission | Explicit safety gate |
| Accepted order unresolved | Order remains pending; not a fill | Fill lifecycle, not a signal divergence |

No source evidence proves how often each divergence occurs in production or which one explains a particular observed period.

### 7. Intent persistence, submission, and fills

Accepted intents are persisted before exchange submission. `src/exchange/CoinbaseAdvancedClient.cpp:297-393` submits quote/base market IOC orders, polls up to five times, and leaves accepted-but-unresolved orders pending. `src/trading/LiveTradingService.cpp:1106-1205` resolves order IDs/fills, applies actual `fill.total_fees` at `:654-857`, writes the trade, marks terminal status, and refreshes account state.

This ordering distinguishes generated signal, executable intent, accepted exchange order, and settled fill. A displayed signal or accepted order is not evidence of a fill or realized PnL.

### 8. Position, accounting, attribution, and frontend reporting

The fill/PnL trace identified these confirmed or source-established issues:

* Mixed inherited/session-managed closes can suppress managed-slice realized-PnL attribution (high-severity accounting/attribution finding).
* Live cash is snapshot-dependent after settlement (medium).
* Portfolio `realized_pnl` is gross while reconciliation is net unless the consumer applies the documented distinction (medium).
* No durable execution-vs-quote/order-to-fill linkage exists for realized slippage attribution (unknown until runtime persistence is inspected).
* Paper fills do not model bid/ask or realized slippage; this is a model limitation, not evidence of a live defect.
* Recent-trade JSON omits an explicit `is_closing_leg` marker, creating a frontend attribution ambiguity.

The relevant verification scope includes `src/trading/LiveTradingService.cpp`, portfolio/accounting paths, durable `live_coinbase_orders` and `individual_trades` records, and the reconciliation endpoint described below. The exact exchange fill payloads and persisted samples were unavailable in the read-only investigation.

## Failure-mode classification table

| Observed/source-established issue | Classification | Status and impact | Missing evidence or boundary |
|---|---|---|---|
| Sequential full-universe fetch on every loop; no cap, retry, backoff, cadence sleep, or freshness threshold | Market-data coverage/freshness; trading economics | Confirmed source behavior; can create uneven effective freshness and provider pressure | Timestamped loop, per-symbol latency/status, headers, request counts, selected-universe size |
| Attempted/skipped diagnostics hardcoded to requested/zero | Frontend artifact | Confirmed observability defect; can overstate coverage | Runtime batch with provider failure and rendered dashboard comparison |
| No exchange quote timestamp/max-age validation | Market-data coverage/freshness | Confirmed source gap; valid delayed response cannot be distinguished from fresh data | Exchange timestamps, response timing, worker timestamps, agreed max age |
| Backend category list incomplete; frontend direct discovery/fallback may narrow universe | Frontend artifact; market-data coverage | Confirmed contract mismatch; environment-dependent selected universe | Browser payloads, CORS/network result, selected symbols, product-list completeness |
| Expected return/confidence fallback/model output not empirically calibrated | Calibration | Confirmed evidence gap, not proof of bad predictions | Versioned model metadata, calibration curves, cohorts, realized after-cost joins |
| Fee/spread/slippage hurdle blocks otherwise valid candidate | Profitability hurdle; trading economics | Confirmed intentional gate; actual frequency unknown | Runtime signal and gate-reason counts |
| Warm-up HOLD or strategy-specific one-shot/interval behavior | Legitimate market outcome | Confirmed policy behavior | Per-symbol history/tick sequence for a disputed timestamp |
| Existing/pending/max-position/min-notional/cash/direction blockers | Sizing; blocker suppression; legitimate policy | Confirmed deterministic safety behavior; transforms/suppresses intent | Runtime blocker counts and account/position snapshots |
| Account refresh failure leaves prior in-memory state while worker can continue processing | Market-data coverage/freshness; unknown | Source path is established; unsafe observed consequence is unproven | Runtime failure followed by intent/submission, snapshot age, exchange state |
| Mixed inherited/session-managed close attribution | Accounting/attribution | Confirmed source-level high-severity defect; reproduction still needed | Representative mixed partial-close reproduction and row-level joins |
| Gross portfolio PnL versus net reconciliation labels | Accounting/attribution | Confirmed semantic mismatch risk | Same-session API payload comparison and consumer calculations |
| Missing quote-to-fill durable linkage | Fill slippage | Unknown realized slippage, not proof of slippage amount | Persisted order/fill records plus contemporaneous quote/order payloads |
| Paper fills omit bid/ask and realized slippage | Trading economics | Confirmed legitimate model limitation | Live-parity comparison if paper/live discrepancy is alleged |
| Recent-trade JSON omits closing-leg marker | Frontend artifact | Confirmed attribution ambiguity | Same-session backend payload and browser rendering |
| Any particular no-positive-PnL result or Coinbase rate-limit claim | Unknown until runtime evidence | Cannot be assigned to a single cause from source or fixtures | Authorized representative runtime window joining all stages |

## Verification surfaces and observed evidence

Backend targets are registered in `CMakeLists.txt:89-234` and selected by the remote `Dockerfile.cpp:244-256` CTest filter: `transformer_onnx_export|portfolio_accounting|trading_stats_calculator|position_sizing_policy|strategy_signal|strategy_expectancy_harness|execution_reconciliation|coinbase_auth|coinbase_order|coinbase_portfolio`.

Relevant deterministic tests and harnesses:

* `src/tests/test_strategy_signal.cpp`: indicator fixtures, warm-up and unknown-strategy HOLDs, unavailable expected-return fail-safe, directional fee/spread/slippage semantics, and order-book fallback.
* `src/tests/test_strategy_expectancy_harness.cpp`: strategy fixture rows, generated/fill/blocked counts, fee-negative blocks, positive expectancy and negative-expectancy regression.
* `src/tests/test_position_sizing_policy.cpp`: risk inputs, caps, zero sizing, minimum profitable notional, fee/slippage/spread blocks, and unprofitable override.
* `src/tests/test_execution_reconciliation.cpp`: generated/executable/blocked counts, open/close outcomes, blocker buckets, PnL/fees, unexplained outcomes, and coverage metrics.
* `src/tests/test_portfolio_accounting.cpp`: open/mark/close identity, cash, exposure, sizing capital, exits, and managed versus pre-existing holdings.
* Frontend suites: `frontend/lib/symbolUniverse.test.ts`, `apiSizing.test.ts`, `startTradingPayload.test.ts`, `executionReconciliation.test.ts`, `liveTabProducer.test.ts`, `simulatedTradingStats.test.ts`, `localSimulatedFallbackSignals.test.ts`, `frontend/hooks/useTradingStrategyParameters.test.tsx`, `frontend/components/dashboard/__tests__/dashboard-tables.test.tsx`, and `frontend/app/page.test.tsx`.

Replay and read-only evidence paths include `include/trading/StrategyExpectancyHarness.hpp`, `src/trading/StrategyExpectancyHarness.cpp`, `docs/reports/strategy-expectancy-harness-closeout-2026-08-03.md`, `docs/reports/live-parity-paper-and-blocker-attribution-progress-2026-08-08.md`, `docs/reports/execution-reconciliation-closeout-2026-08-08.md`, and `docs/reports/simulated-vs-live-trading-gap-review.md`. The reconciliation endpoint is `GET /api/trading/execution-reconciliation?hours=&session_id=&trade_type=&max_signals=`; it joins `order_book_signals.signal_data` to `individual_trades` and reports truncation/unexplained outcomes.

Historical evidence recorded by the upstream test inventory: frontend Jest 10 suites/58 tests and standalone C++ reconciliation assertions passed; exact-SHA Docker Build Validation run `31274960164` passed all six required jobs for historical commit `d5a21160f24fe1ea6b6729a1bbac7611d12f20f2`. These are historical receipts, not a claim about this documentation commit or a current runtime window. Upstream source-trace reports separately record successful exact-SHA validation for their own commits (`653f7420a77ce17052e601d0aa9885ec8145ea52` and `e3787a929a86575e1d449f5ec365c3d15eb5561b`). No local builds or tests were run for this documentation-only synthesis.

## Conflicting findings and evidence precedence

1. Historical throughput closeout documents describe bounded cadence, while the current source trace at `LiveTradingService.cpp:2309-2437` reports immediate full-universe repetition and diagnostics showing no cap. Current source is authoritative for current behavior; deployment image/runtime evidence is still required to establish production behavior.
2. Frontend unit tests prove category normalization and no hidden slicing, but backend category output is incomplete and direct browser discovery/fallback is environment-dependent. Unit behavior is not browser/network proof.
3. Deterministic expectancy and gate fixtures prove arithmetic and fail-closed relationships, but they do not establish empirical calibration, realized slippage, or live after-cost expectancy.
4. Reconciliation schemas can report blocker and PnL relationships, but without a representative joined runtime window they cannot explain an individual reported discrepancy.

## Required next evidence

* A read-only, authorized representative runtime batch with selected-universe count, every symbol's provider status/error/latency, request headers where safe, quote/exchange timestamps, worker start/end, account snapshot age, and generated signal rows.
* A joined signal -> execution-analysis -> intent -> durable order -> acknowledgement/fill -> position/PnL export for that same window, including blocker reasons, fees, quantities, and terminal states.
* Versioned model-pack metadata and out-of-sample calibration/reliability by symbol/regime, joined to realized after-cost outcomes.
* Captured browser network/API payloads and rendered values for selected universe, coverage diagnostics, blocker attribution, recent trades, and PnL.
* A controlled mixed inherited/session-managed partial-close reproduction and a persisted fill/quote comparison for realized slippage.

Until those artifacts exist, classify actual runtime no-trade and no-positive-PnL causes as unknown rather than inferring them from source-only evidence.

## Safety statement

This report is documentation-only. No live parameters or production behavior were changed; no live session, order, account mutation, credential, or external trading action was performed.
