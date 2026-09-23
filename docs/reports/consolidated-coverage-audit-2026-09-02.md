# Consolidated selected-universe, execution, and realized-PnL coverage audit

Date: 2026-09-02
Scope: read-only source review and existing focused contract evidence for the Live Trading path. No live session, account mutation, order, database write, or unrelated product change was performed.

## Executive conclusion

The selected-symbol list is propagated from the Live Trading UI into the live-start payload, `LiveTradingService::symbols_`, the live order-book API, and the latest-by-symbol widget response. The visible table is not an execution ledger: a row can be a signal/diagnostic or a response-only missing placeholder, while an executable intent is a separately gated field. Accepted exchange orders are also not fills; terminal fill and realized-PnL evidence is downstream.

The audit confirms several coverage and accounting risks, but does not establish that a functioning strategy is currently producing positive PnL that is merely hidden by the table. The release decision remains fail-closed until runtime evidence reconciles one representative selected symbol through signal, blocker/intent, submission, fill, position update, and realized-PnL reporting.

## Evidence chain

### 1. Selected universe

- `frontend/lib/symbolUniverse.ts:74-160` derives online/tradable category universes and rejects incomplete/aliased category responses. Custom symbols are trimmed, uppercased, and deduplicated at `:28-43` and `:122-160`.
- `frontend/lib/api.ts:787-879` sends the selected `symbols[]` in the start payload. `frontend/components/dashboard/LiveTradingPanel.tsx:560-583` uses local selection before activation and then `status.symbols` for order-book polling. The live payload at `:607-632` includes `mode`, `strategy`, `symbols`, `parameters`, `max_positions`, `position_update_interval=5`, and explicitly requires `live_order_execution`.
- `src/api/PredictController.cpp:1386-1413` exposes only hardcoded `major`, `all_usd`, and aliased `all_products` categories (the latter 18 USD products). Normal frontend discovery therefore bypasses this incomplete category contract; discovery failure can fall back to the static six-symbol list in `symbolUniverse.ts`.
- `src/trading/LiveTradingService.cpp:2810-2821` copies payload symbols into `symbols_` and only defaults an empty list. `:2452-2459` and `:2589-2596` serialize the same vector. No backend normalization or deduplication is applied at the live-start boundary.

Classification: **confirmed** incomplete/hardcoded backend category contract and possible fallback narrowing; **confirmed** verbatim live-start boundary; **unknown** deployed discovery/CORS outcome, actual production universe cardinality, and whether duplicate products occur in the live payload.

### 2. Widget/display coverage

- Routes are declared in `include/api/PredictController.hpp:32-43`; handlers parse comma-separated `symbols`, `page`, and `per_page` at `src/api/PredictController.cpp:1230-1266`.
- `frontend/hooks/useTrading.ts:257-444` fetches all selected symbols in chunks of 50 using `page=1` and `per_page=chunk.length`, then merges and applies client-side display pagination. `OrderBookSignalsTable.tsx:291-400` offers visible page sizes 10/25/50/100. `DataTable.tsx:9-154` contains no additional hidden slice.
- `LiveTradingService.cpp:3274-3363` deduplicates active recent rows by symbol, adds response-only `data_status=missing`/HOLD placeholders for selected symbols without a latest quote/signal, sorts, and then paginates. Missing rows are explicitly not intent inputs. Stopped-session persistence fallback at `:3366-3461` uses latest-by-symbol SQL with `LIMIT/OFFSET` and does not add the same placeholders.
- The widget query has `staleTime=3s` and `refetchInterval=3s` (`useTrading.ts:440-442`). The Live Trading panel does not use the simulated WebSocket updater; live display is HTTP polling.
- For >50 symbols, chunk diagnostics at `useTrading.ts:329-354` sum/concatenate fields that can describe snapshot populations. Thus `current_latest_signal_count`, `recent_signal_record_count`, and related coverage totals can overstate cardinality when the same state appears in multiple chunks. Failed chunks produce partial coverage and are surfaced only through diagnostics.

Classification: **ruled out** hidden DataTable truncation and widget page size silently capping selected-universe requests; **confirmed** response-only missing rows, 3-second display polling, and potentially misleading chunk aggregation; **unknown** deployed browser/API/CORS behavior, runtime partial-chunk frequency, and stale stopped-session fallback behavior.

### 3. Quote acquisition and signal generation

- `LiveTradingService.cpp:1208-1242` (`fetchLiveQuotes`) requests every selected symbol sequentially through `CoinbaseAdvancedClient::getOrderBook`; failures are logged/omitted. `:1244-1263` returns the full selected vector; the warning threshold of 10 is logging-only, not a cap.
- `CoinbaseAdvancedClient.cpp:514-560` consumes public level-2 data (up to 20 bid/ask levels) and derives best bid/ask, midpoint, spread, depth, and imbalance. `MarketQuote` has no quote timestamp in this path, and no max-age validation was found.
- `LiveTradingService.cpp:2309-2403` repeats quote/account/signal/dispatch/persistence work without an identified normal sleep. `position_update_interval` is accepted/configured but no controlling cadence sleep was found in the inspected loop. Diagnostics at `:2363-2373` can report `attempted=requested` and `skipped=0` despite fetch failures.
- `generateTickLocked` at `:2226-2307` skips symbols with no valid quote, persists signals for valid quotes, and attaches `execution_analysis`. No quote means no signal and no intent. `signalToJson` at `:517-542` serializes signal, prediction, ML, criteria, and execution-analysis fields.

Classification: **confirmed** unbounded/provider-latency-dependent source cadence, missing quote freshness validation, and overoptimistic fan-out diagnostics; **ruled out** a confirmed enforced universe cap and synthetic simulated fallback driving live orders; **unknown** provider rate limits, quote age, actual request rate, and account-refresh/old-state sequencing at runtime.

### 4. Blocked intents, submitted orders, and fills

- `buildEntryExecutionAnalysisLocked` (`LiveTradingService.cpp:1835-1931`) turns generated signals into executable/non-executable decisions. Blockers include ML confidence, existing/pending position, max positions, nonpositive size/price, minimum notional, spot shorting, insufficient cash, and disabled live execution.
- `openPositionLocked` (`:1991-2049`) repeats safety gates and creates an `OrderIntent` with `product_id=signal.symbol`, buy side, quote amount, and reserved cash. Therefore `signal_generated`, `signal`, `prediction`, `strength`, expected return, and criteria analysis do not prove an order intent. The relevant evidence is `execution_analysis.executable_intent`, `blocker_reason`, `intended_side`, `allocated_usd`, and executable-intent diagnostics.
- `dispatchOrders` (`:1035-1103`) persists intents to `live_coinbase_orders` before submission, rejects duplicate client IDs, and then calls Coinbase. `CoinbaseAdvancedClient::placeMarketOrder` (`src/exchange/CoinbaseAdvancedClient.cpp:297-359`) submits product/side/quote-or-base size. An acknowledgement is not a fill.
- `resolvePendingLiveOrders` (`LiveTradingService.cpp:1106-1205`) polls order/fill state, applies exchange fills and fees, persists settlement, and refreshes account state. The chain is therefore: signal → blocker or intent → persisted/submitted order → pending acknowledgement/fill → terminal fill/fees → position update → realized trade/PnL.

Classification: **confirmed** display signal versus executable-intent separation and acceptance-versus-fill separation; **ruled out** missing quote rows creating intents, order acceptance being treated as confirmed fill/fee, and response-only missing rows entering dispatch; **unknown** runtime counts at each boundary and database retry-queue drain behavior.

### 5. Realized-PnL and reporting

The order/fill audit (source report `docs/reports/order-fill-realized-pnl-audit-2026-08-23.md`, commit `06f4fadc1c0d3c6ec07d5c653547297b1dce95ec`) found:

- **Confirmed:** mixed inherited/session-managed close handling can suppress valid managed realized PnL (`src/trading/LiveTradingService.cpp:711-725`).
- **Confirmed:** `TradingStatsService` includes opening legs in generic trade/volume denominators, which can distort summary rates/counts even though opening legs are not positive closing trades.
- **Confirmed:** global `/api/ml/pnl-trades` is an unscoped nonzero-PnL top/bottom view and diverges from session-scoped live-trading statistics.
- **Confirmed:** terminal close fills can be dropped when both internal and persisted position context are absent.
- **Ruled out:** opening fills counted as positive trades, exact-flat reconciliation loss, portfolio cash sign/quantity identity as the primary cause, and frontend DataTable pagination deleting fills.
- **Unknown:** production frequency of mixed inherited closes or missing-position early returns; actual deployed positive-PnL counts; realized slippage/fee totals; and current browser staleness.

The simulated execution evidence additionally establishes that existing frontend tests cover positive/negative PnL, fees, opening/closing legs, zero-PnL win-rate exclusion, unexplained outcomes, and normalized portfolio/realized-PnL reporting. These are deterministic contract checks, not proof of a live production reconciliation.

## Verification and limitations

- Focused frontend contract set: **7 suites / 45 tests passed** using the repository-installed Jest dependencies via `NODE_PATH`; complete frontend suite: **10 suites / 58 tests passed**. Covered universe propagation, start payload, live readiness, missing responses, table pagination/diagnostics, execution reconciliation, and simulated stats.
- The initial worktree-local `npx jest` attempt was blocked before collection because `node_modules` was absent and `next/jest` could not resolve; no dependency files changed.
- C++ targets `execution_reconciliation`, `strategy_expectancy_harness`, and `coinbase_order` were inspected but not built locally under the remote-only policy. No live runtime, provider replay, exchange submission, fill polling, database query, or browser/API/CORS check was run.
- Exact-SHA remote CI evidence exists for the order/fill report commit `06f4fadc1c0d3c6ec07d5c653547297b1dce95ec`: Docker Build Validation run `32623785485` completed successfully for four architecture builds and both manifest-publication jobs. Earlier evidence for SHA `8af7838c...` was queued at the time of the universe audit; it must not be substituted for a current run of any new consolidated commit.

## Focused follow-up only

1. Capture a read-only representative runtime trace keyed by symbol/client order ID, reconciling selected universe cardinality, quote success/age, generated signal, blocker or executable intent, persisted/submitted order, terminal fill/fees, position update, and realized PnL.
2. Add contract tests for >50-symbol chunk merging, overlapping/duplicate responses, failed chunks, diagnostics cardinality, live polling freshness, and active versus stopped-session missing-row behavior.
3. Instrument and measure live worker cadence, provider response failures/rate limits, and quote age before choosing any cap, retry, sleep, or recovery behavior.
4. Reconcile the mixed inherited-close and missing-position paths against persisted records before implementing accounting changes; do not infer a restoration contract from source evidence alone.

No broad UI rewrite, universe cap, retry policy, or live execution behavior change is recommended by this audit alone.
