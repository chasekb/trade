# Live signal-to-executable-intent blocker trace — 2026-08-23

Task: `t_1d68dd6f`

Scope: read-only trace of the checked-in live path from Coinbase market data and generated signals through preflight, order intent queuing, Coinbase submission, fill settlement, and realized-PnL attribution. No live parameters, production behavior, credentials, or account state were changed.

## Executive summary

The live worker is a Coinbase-only, selected-universe loop. Each iteration requests one order book per selected symbol, creates one `SignalRecord` per valid quote, applies the order-book profitability gate before the record is finalized, computes an allocation from current account equity and performance inputs, then runs live-only entry blockers before queuing an `OrderIntent`. Queued intents are persisted to `live_coinbase_orders` before the authenticated Coinbase order call. Accepted orders remain pending until a terminal historical-order response provides actual fill size, value, average price, and fees.

The strongest confirmed signal/execution divergences are:

* A raw order-book candidate that fails the fee/spread/slippage gate is rewritten to `hold` before persistence. It therefore appears as a non-generated signal, not as a generated-but-profitability-blocked intent. The separate `execution_analysis` field can identify `profitability_gate` only for the post-gate hold; the original candidate is not retained as a row.
* A generated signal can be blocked by ML confidence, account-position authority, existing position, pending order, max positions, non-positive size/price, Coinbase minimum notional, spot-only direction, insufficient available cash, or explicit live-execution state. These blockers are classified in `execution_analysis` and counted in recent diagnostics.
* The automated entry path checks Coinbase's $1 quote minimum, but automated closes and manual orders do not apply an equivalent minimum-notional guard. Dust closes can therefore become Coinbase-rejected orders; liquidation of unmanaged holdings does perform the minimum-notional check.
* There is no explicit quote timestamp age, stale-data TTL, market-hours gate, or duplicate-signal cooldown. Missing quote responses suppress that symbol's tick; a valid but old provider response is not independently freshness-validated. `last_entry_tick` is used for DCA timing and position age, not as a general duplicate-signal freshness gate.
* The current checked-in worker requests the full selected universe each iteration with no symbol cap or cadence sleep. This is intentional in the current code, but provider rate limits, timeout/error coverage, and actual runtime cadence remain external evidence requirements.

## Ordered runtime flow

### 1. Live request and account baseline

1. `frontend/lib/api.ts:620-672`, `buildStartTradingPayload`, removes synthetic capital fields for `mode === 'live'`; it sends `symbols`, `strategy`, `parameters`, top-level sizing/max-position fields, and the explicit execution flag.
2. `frontend/lib/api.ts:812-815` posts the live payload to `/api/trading/live/start`.
3. `src/api/PredictController.cpp:1348-1357` forwards the request to `LiveTradingService::startSession` (route declaration: `include/api/PredictController.hpp:24-35`, exact route declarations should be checked there for deployment wiring).
4. `src/trading/LiveTradingService.cpp:2767-2809` loads Coinbase credentials from `Config::getInstance()` (`COINBASE_API_KEY`, `COINBASE_API_SECRET`), constructs `CoinbaseAdvancedClient`, and requires an authenticated account snapshot before activation.
5. `src/trading/LiveTradingService.cpp:2810-2877` selects the requested universe (default `BTC-USD`, `ETH-USD`, `SOL-USD`), accepts `parameters` or legacy `strategy_params`, rejects `initial_portfolio_size`, `initial_balance`, and `capital`, requires `live_order_execution=true`, and sets `max_positions_` and `position_update_interval_`.
6. `src/trading/LiveTradingService.cpp:2883-2917` resets session state, applies the Coinbase snapshot (`cash_`, `cash_hold_`, holdings/value, `initial_capital_`), recovers persisted `submitting`/`pending` orders, and starts the worker.

Configuration sources are therefore: frontend payload construction in `frontend/lib/api.ts`, request JSON, process `.env`/environment resolution in `src/config/Config.cpp:23-70`, and runtime `parameters_` in `LiveTradingService`. No live strategy values are read from a separate static production config in this path.

### 2. Quote acquisition and coverage

1. `src/trading/LiveTradingService.cpp:2309-2403`, `workerLoop`, resolves pending orders, selects the full `symbols_` vector, fetches quotes and the account snapshot outside the mutex, then applies the snapshot and calls `generateTickLocked`.
2. `src/trading/LiveTradingService.cpp:1244-1263`, `selectLiveQuoteBatchLocked`, copies the entire selected universe. `live_quote_symbols_per_tick_cap=0` and `quote_fanout_limit_enforced=false` are serialized at `src/trading/LiveTradingService.cpp:2561-2568`.
3. `src/trading/LiveTradingService.cpp:1208-1242`, `fetchLiveQuotes`, calls `CoinbaseAdvancedClient::getOrderBook` once per symbol. Failed requests are logged and omitted from the returned map; valid responses provide mid, spread, best bid/ask, imbalance, volume, and depth.
4. `include/exchange/CoinbaseAdvancedClient.hpp:63-67` states calls are blocking with bounded timeout and must not run while holding service/API locks. `src/exchange/CoinbaseAdvancedClient.cpp` implements the public order-book request.
5. The worker logs requested/attempted/succeeded/skipped counts and estimated request rate at `src/trading/LiveTradingService.cpp:2352-2373`, but the current log hard-codes attempted to `symbols_snapshot.size()` and skipped to `0`, even when `fetchLiveQuotes` omitted failed symbols. The serialized success count is the actual `quotes.size()`.

Classification: missing quote coverage is `market-data coverage/freshness` when a provider call fails; the missing evidence for an unknown runtime cause is the per-symbol provider response/error and quote timestamps. There is no confirmed market-hours or stale-age suppression. A valid response can be used in that iteration regardless of its age because no timestamp is carried into `MarketQuote`.

### 3. Signal construction

1. `src/trading/LiveTradingService.cpp:1516-1803`, `buildSignalRecordLocked`, updates per-symbol price/imbalance state, appends rolling price history, and emits either an order-book imbalance direction or an indicator strategy result.
2. Order-book candidates use `abs(imbalance) * 1.15`, with a raw activity threshold of `0.22` (`:1553-1557`). Non-order-book strategies delegate to `evaluateStrategySignal` in `src/trading/StrategySignal.cpp:113-303`; warm-up returns `hold` with an insufficient-history reason.
3. The signal payload includes `signal_type`, `signal_generated`, strength, price, timestamp, data status, criteria, ML analysis, and composition (`:1583-1606`, `:1796-1802`). `data_status` is `insufficient` only for known warm-up/insufficient-history reasons (`:143-146`, `:1600`); a provider failure produces no signal row at all.
4. ML-enhanced order-book inference uses `PredictController::featureEngineer()` and `modelManager()` (`:1637-1684`). Without a model, the fallback is explicitly labeled `heuristic-fallback` and derives expected return from imbalance and `orderbook_expected_return_scale_percent` (`:1686-1702`).
5. For generated order-book candidates, `evaluateOrderBookProfitabilityGate` in `src/trading/StrategySignal.cpp:305-341` applies directional expected return against fee + spread + slippage. Parameters are `round_trip_fee_percent`, `slippage_buffer_percent`, and `min_orderbook_signal_strength`; defaults are defined in `LiveTradingService.cpp:38-47` and `StrategySignal.hpp:46-54`.
6. If that gate fails, `buildSignalRecordLocked` mutates the candidate to `hold` and writes the gate reason (`src/trading/LiveTradingService.cpp:1733-1769`). This is blocker suppression before the signal is persisted, not a generated signal that reaches live preflight.

Classification: weak activity is `calibration`/strategy signal quality; missing expected return for indicator strategies is an explicit `unknown`/`profitability hurdle` diagnostic rather than evidence of a bad trade; fee-negative expected edge is `trading economics`/`profitability hurdle`.

### 4. Live preflight and executable-intent decision

`src/trading/LiveTradingService.cpp:1835-1931`, `buildEntryExecutionAnalysisLocked`, is the readable preflight contract. It starts blocked and returns the first blocker below:

| Order | Condition and source | Effect | Classification |
|---|---|---|---|
| 1 | signal is post-gate `hold` (`:1863-1868`) | suppresses candidate; reason is `no_signal` or `profitability_gate` | blocker suppression / trading economics |
| 2 | `signalPassesMlGateLocked` (`:1805-1832`, ML confidence threshold, fallback policy) | suppresses entry | blocker suppression / calibration |
| 3 | account-managed symbol without `manage_entries_and_exits` (`:1875-1878`) | suppresses entry | blocker suppression / account authority |
| 4 | existing position (`:1880-1882`) | suppresses duplicate entry | blocker suppression / duplicate-order prevention |
| 5 | `pending_order_symbols_` (`:1884-1886`) | suppresses another order for the symbol | blocker suppression / pending order |
| 6 | managed positions + pending entries >= `max_positions_` (`:1888-1897`) | suppresses entry | sizing / risk cap |
| 7 | `positionSizeUsdForSignal` <= 0 or invalid price (`:1900-1904`) | suppresses entry | sizing / missing market data |
| 8 | quote allocation below `coinbaseMinQuoteOrderUsd()` (`:1906-1909`; $1 in `src/exchange/CoinbaseOrder.cpp:15-40`) | suppresses entry | sizing / trading economics |
| 9 | sell/open-short direction (`:1911-1913`) | suppresses entry because Coinbase spot cannot open synthetic shorts | legitimate market/account constraint |
| 10 | `cash_ - pending_reserved_cash_` fails `hasSufficientCash` (`:1915-1921`; helper `include/trading/PortfolioAccounting.hpp:43-50`) | suppresses entry; buy requires allocation + estimated fee | sizing / blocker suppression |
| 11 | `liveOrderExecutionEnabledLocked` (`:1923-1926`; configured credentials + explicit flag) | suppresses order submission | safety gate / blocker suppression |
| 12 | otherwise | marks `executable_intent=true`, then `generateTickLocked` calls `openPositionLocked` | transforms signal into queued intent | executable intent |

`positionSizeUsdForSignal` (`src/trading/LiveTradingService.cpp:409-479`) uses percent of current signed equity or explicit dollar sizing, then `calculate_position_size_usd` (`src/trading/PositionSizingPolicy.cpp:78-84`) only reduces the configured ceiling based on signal/ML/performance/cohort inputs. It does not scale upward to satisfy an exchange minimum. Cash is sourced from the latest Coinbase snapshot (`:1300-1311`) and pending reservations are subtracted.

`openPositionLocked` (`src/trading/LiveTradingService.cpp:1991-2049`) repeats the safety gates before queuing. This duplication is fail-closed but means `execution_analysis` is a diagnostic prediction, not a durable reservation: account state can change between analysis and intent queueing. `addToPositionLocked` (`:2051-2102`) repeats pending, inherited-account, size, minimum, cash, execution, and spot-side checks for DCA additions.

### 5. Intent queue, persistence, and Coinbase submission

1. `queueOrderIntentLocked` (`src/trading/LiveTradingService.cpp:638-645`) marks the symbol pending and increases `pending_reserved_cash_` by the intent reserve.
2. `workerLoop` takes intents after `generateTickLocked` (`:2380-2403`) and dispatches them outside the mutex.
3. `dispatchOrders` (`src/trading/LiveTradingService.cpp:1035-1104`) generates a random client order id, persists the full signal/position snapshot to `live_coinbase_orders` via `persistSubmittedOrder` (`:859-918`), then calls `CoinbaseAdvancedClient::placeMarketOrder`.
4. The database primary key on `client_order_id`, plus `ON CONFLICT ... DO NOTHING RETURNING`, rejects a duplicate locally before the exchange call (`:895-913`). Symbol-level `pending_order_symbols_` prevents concurrent same-symbol intents in memory. Persisted recovery handles crash windows in `recoverPendingOrders` (`:963-1033`).
5. Coinbase acceptance and actual fill are separate. `CoinbaseAdvancedClient::placeMarketOrder` (`src/exchange/CoinbaseAdvancedClient.cpp:299-380`) uses market IOC and polls briefly; accepted-but-not-terminal orders are retained as pending. Definitive exchange rejection clears the symbol and reservation; inconclusive failures remain recoverable.
6. `resolvePendingLiveOrders` (`src/trading/LiveTradingService.cpp:1106-1205`) recovers missing order ids by client id, requires a terminal historical order, and only then applies settlement.

Classification: persistence failure or inconclusive provider response is `unknown` until the database row, client-order lookup, and Coinbase history are compared. It must not be classified as a legitimate market outcome from logs alone.

### 6. Fill handling and realized-PnL attribution

1. `src/exchange/CoinbaseOrder.cpp:53-109`, `parseOrderFill`, requires terminal status and finite non-negative values. A positive fill requires actual filled value, average price, and actual fees; no-fill terminal orders are accepted for rejection handling.
2. `src/trading/LiveTradingService.cpp:654-857`, `applyLiveFillLocked`, releases pending reservations, ignores zero-fill terminal outcomes, creates the trade row from actual fill values/fees, and marks closing legs for `close` and `liquidate_holding`.
3. For managed closes (`:689-745`), gross PnL is `(exit - managed_entry) * managed_closed_quantity * direction`; actual Coinbase fees are stored separately and accumulated in `total_fees_`. Inherited-account closes are marked `live_account_managed_close` and PnL-excluded.
4. Opens/adds update managed quantity and entry basis (`:777-850`). Inherited adds/closes are separately typed and excluded from session performance inputs by `queueTradeWriteLocked` (`:612-620`).
5. `flushWrites` (`:1409-1513`) upserts `individual_trades`; `buildStatusJson` (`:2597-2620`) reads persisted session rows and excludes account-managed/liquidation rows from strategy stats.
6. Shared accounting invariants are in `include/trading/PortfolioAccounting.hpp`; execution attribution is independently tested by `src/trading/ExecutionReconciliation.cpp` and `src/tests/test_execution_reconciliation.cpp`.

Classification: actual fill slippage/fees are `trading economics`/`fill slippage`; inherited-basis exclusion is `accounting/attribution`; a missing terminal fill or unexplained outcome is `unknown` pending exchange history and database evidence.

## Manual and liquidation paths

* Manual route: `PredictController.cpp:1290-1303` -> `LiveTradingService::submitLiveOrder` (`src/trading/LiveTradingService.cpp:3062-3147`). It requires active session, explicit execution, positive finite amount, correct buy quote/base sell amount type, no pending symbol, buy cash, and available Coinbase sell quantity plus an existing position. It does not check buy minimum notional, sell estimated minimum notional, market hours, quote freshness, or max-position. A manual sell can target any existing holding in `positions_`; `close` later rejects unmanaged holdings, but the manual method itself chooses `action="close"` before that downstream behavior.
* Automated managed close: `closePositionLocked` (`:2104-2152`) requires session-managed position, no pending order, execution enabled, and exchange-available quantity bounded by `managedSellQuantity`. It does not check minimum notional or a current quote. Therefore dust and stale internal price/exchange availability are unresolved failure modes until Coinbase responds.
* Unmanaged liquidation: `liquidateCoinbaseHoldingLocked` (`:2154-2224`) requires active/execution-enabled mode, no pending order, available quantity, and estimated notional >= $1 using `current_price` or `entry_price`. It is the only sell path with an explicit min-notional check.

## Signal fields versus execution fields

| Signal field | Producer | Execution consumer / divergence |
|---|---|---|
| `signal_type`, `signal`, `signal_generated` | `buildSignalRecordLocked` | `buildEntryExecutionAnalysisLocked`, `openPositionLocked`; profitability failure mutates the producer value to `hold` before persistence |
| `strength` / `signal_strength` | raw imbalance or indicator | ML threshold, min activity, sizing multiplier; no direct exchange field |
| `price`, `mid_price`, bid/ask, spread | `MarketQuote` | sizing, fee estimate, profitability spread; no age/timestamp freshness check beyond creation time |
| `ml_analysis.expected_return` | model or heuristic | directional profitability gate and sizing; zero/unavailable for indicator strategies becomes diagnostic-unavailable |
| `ml_analysis.win_probability`, `confidence` | model/fallback | `signalPassesMlGateLocked` for ML-enhanced strategy and sizing |
| `data_status` | reason string | frontend/diagnostic display; missing quote creates no row rather than `insufficient` row |
| `execution_analysis` | live preflight | counts recent blockers, but it is computed before `openPositionLocked` repeats gates and is not persisted separately from signal JSON |
| `quantity`/`notional` | not a raw signal field | computed allocation is quote USD for buys; base quantity is computed for fills/sells. Coinbase minimum is quote USD only |
| entry metadata | signal payload | captured into `live_coinbase_orders.signal_json`; fill PnL uses persisted position basis, not outcome-derived ML fields |

## Failure-mode classification and missing evidence

| Observed behavior | Classification | Confirmed evidence / missing evidence |
|---|---|---|
| Provider quote request fails; symbol omitted from tick | market-data coverage/freshness | Confirmed in `fetchLiveQuotes`; need per-symbol Coinbase HTTP status/error and timestamp to quantify |
| Full-universe sequential request fan-out, no cap/sleep | market-data coverage/freshness / trading economics | Confirmed in `selectLiveQuoteBatchLocked` and worker; need runtime rate-limit/latency logs and provider responses |
| Raw imbalance below threshold or indicator warm-up | calibration / legitimate strategy hold | Confirmed in signal builders and `StrategySignal`; no failed execution occurred |
| Fee/spread/slippage hurdle fails | trading economics / profitability hurdle | Confirmed by `evaluateOrderBookProfitabilityGate`; raw candidate is rewritten to hold |
| ML confidence or fallback policy fails | calibration / blocker suppression | Confirmed in `signalPassesMlGateLocked`; need model-version and prediction distribution for performance attribution |
| Allocation below $1 | sizing / trading economics | Confirmed in `buildEntryExecutionAnalysisLocked`, `openPositionLocked`, Coinbase helper; need signal allocation distribution to quantify |
| Insufficient cash after pending reservations | sizing / blocker suppression | Confirmed; need account snapshots, pending order rows, and intent allocation to quantify |
| Existing position, pending symbol, max positions | blocker suppression / risk | Confirmed; no duplicate concurrent same-symbol entry is allowed in memory |
| Sell order from spot strategy | legitimate market/account outcome | Confirmed `spot_cannot_open_short`; not evidence of provider failure |
| Account-managed/inherited authority restrictions | blocker suppression / account authority | Confirmed; inherited PnL excluded by trade type |
| Automated or manual dust close without min-notional preflight | sizing / blocker suppression gap | Confirmed missing check; actual cause of any rejection requires Coinbase rejection payload and order record |
| No market-hours gate | legitimate market outcome or unknown operational policy | Confirmed absent in this path; whether Coinbase 24/7 spot is intended requires product policy, not runtime evidence |
| No stale-age or duplicate-signal cooldown | market-data freshness / blocker suppression gap | Confirmed absent; need provider timestamps and tick timing to determine actual stale/repeated-order impact |
| Accepted order later fills, partially fills, cancels, or remains inconclusive | fill slippage / legitimate market outcome / unknown | Terminal status and actual fee/value parser are confirmed; missing evidence is Coinbase historical order JSON plus `live_coinbase_orders` row |
| Dashboard shows signal/intent counts | frontend artifact risk | `frontend/lib/liveTabProducer.ts` and dashboard consumers normalize backend data; need browser/runtime snapshot to prove any display mismatch |

## Tests, replay tools, and verification evidence

Relevant checked-in tests and harnesses:

* `src/tests/test_strategy_signal.cpp` + `CMakeLists.txt:151-156`: indicator warm-up, directional signal behavior, fee-adjusted expected-return diagnostics, and order-book profitability semantics.
* `src/tests/test_position_sizing_policy.cpp` + `CMakeLists.txt:138-143`: weak/strong size multipliers, hard configured ceiling, no automatic exchange-minimum inflation, fee/spread/slippage hurdle, max-cap block, explicit unprofitable override.
* `src/tests/test_coinbase_order.cpp` + `CMakeLists.txt:184-192`: $1 minimum, quote formatting, terminal/no-fill/partial fill parsing, malformed actual fees/value/price rejection.
* `src/tests/test_portfolio_accounting.cpp` + `CMakeLists.txt:145-149`: cash/position identity, cash sufficiency, managed sell quantity, inherited holdings.
* `src/tests/test_execution_reconciliation.cpp` + `CMakeLists.txt:166-171`: generated signals vs executable intents, blocker buckets, closing-leg coverage, fees, flat closes, unexplained outcomes.
* `src/trading/StrategyExpectancyHarness.cpp` / `include/trading/StrategyExpectancyHarness.hpp` and `src/tests/test_strategy_expectancy_harness.cpp`: deterministic indicator fixtures and blocked-vs-filled expectancy metrics. This is a paper/backtest replay harness, not a Coinbase live replay.
* There is no checked-in end-to-end live-worker replay with mocked Coinbase account/order-book/order endpoints, no targeted `LiveTradingService` unit test for each preflight branch, and no test asserting automated/manual close min-notional behavior. These are missing evidence for unknown live failure attribution.

## Conclusions

The backend is fail-closed for live activation, synthetic capital, explicit execution opt-in, quote absence, invalid sizing, minimum-notional entries, insufficient cash, existing/pending symbols, max positions, spot short entries, account authority, and persisted-order recovery. The remaining evidence gaps are runtime/provider-specific: stale or delayed quote age, actual API rate-limit behavior, market-hours policy, close-side dust rejection, and any frontend display mismatch. No live parameters or production behavior were changed by this trace.
