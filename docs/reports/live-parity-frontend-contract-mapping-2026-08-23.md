# Simulated Trading live-parity frontend contract mapping

Date: 2026-08-23

Scope: the Simulated Trading tab's two explicitly simulated execution modes. This is a source-level contract map for the follow-up UI and test tasks; it does not claim runtime or deployment verification.

## Safety boundary and mode labels

The tab remains under the `Simulated Trading` surface. Neither option is real live trading.

| UI option (canonical label) | Request field and allowed value | Backend meaning | Required visible qualifier |
| --- | --- | --- | --- |
| `Synthetic simulation` | `parameters.execution_mode: "simulated"` in the POST body to `/api/trading/simulated/start` (the backend also accepts top-level `execution_mode`) | Synthetic market state and synthetic order-book ticks; existing simulated fills/positions are retained | `Synthetic simulation — simulated fills only; no real orders` |
| `Coinbase live-data paper mode` | `parameters.execution_mode: "live_parity"` in the POST body to `/api/trading/simulated/start` (the backend also accepts top-level `execution_mode`) | Coinbase public order-book quotes, live-like spot/minimum/cash/position gates, and local paper settlement; Coinbase orders are never submitted | `Live-data paper execution — simulated only; no Coinbase orders` |

The backend route is registered at both `/api/trading/simulated/start` and the legacy alias `/api/simulated-trading/start`; the frontend's canonical first attempt is the former. `PredictController::startSimulatedTrading` rejects any execution mode other than `simulated` or `live_parity` with HTTP 400 and `error`.

The frontend should continue calling `apiClient.startTrading("simulated", ...)`; `mode: "simulated"` selects the simulated route, while `parameters.execution_mode` selects synthetic versus live-parity behavior. Do not use `mode: "live"` for this selector: that route is the real live-execution surface.

## Request and existing synthetic behavior

Source of request values:

- `SimulatedTradingPanel.executionMode` is the explicit state (`"simulated" | "live_parity"`).
- `handleStartTrading` builds `{ mode: "simulated", strategy, symbols, parameters: { ...config, execution_mode: executionMode }, max_positions, position_update_interval }`.
- `apiClient.startTrading` calls `buildStartTradingPayload`; `parameters` and the compatibility alias `strategy_params` are sent, and the simulated capital aliases are added only for synthetic-compatible simulated starts.
- `PredictController.cpp` reads top-level `execution_mode`, falling back to `parameters.execution_mode`, then defaults to `"simulated"`.
- `SimulatedTradingService::startSession` accepts `parameters` (or legacy `strategy_params`), with selected top-level settings overriding/backfilling the parameter object.

Synthetic mode already has two deliberate behaviors that must not be changed by the live-parity UI:

1. The C++ service generates synthetic market state when no live quote is supplied, and can retain its existing short-capable simulated behavior.
2. The frontend local fallback (`NEXT_PUBLIC_FORCE_LOCAL_SIM_TRADING` or unavailable simulated endpoints) creates a local synthetic session and generates local synthetic signals/portfolio data. It is allowed only when `execution_mode !== "live_parity"`; a live-parity failure must never silently become synthetic data.

The local fallback signal implementation is in `frontend/lib/api.ts` (`buildSyntheticOrderBookSignals`, `buildLocalSimulatedTradingStatus`, and local portfolio helpers). It should be treated as synthetic-only and must not be used to render paper fills or Coinbase quote status.

## Response envelope and authoritative mode fields

Start/status responses are raw backend JSON in the successful `fetch` path (not necessarily wrapped in the frontend `ApiResponse` envelope). The status object contains:

- `status`: `started`, `active`/other status, `settling`, or `error` as applicable.
- `is_active` / `isActive` / `is_trading`: session activity state.
- `mode` and `execution_mode`: authoritative selected mode (`simulated` or `live_parity`).
- `execution_is_paper`: authoritative paper boundary. In `live_parity` this is true because live order execution is disabled.
- `market_data_source`: `synthetic` for synthetic mode, `coinbase_public` for live-parity.
- `session_id`, `strategy_type`, `symbols`, `started_at`, `updated_at`.
- `message`: start/stop or settling explanation; useful as explanatory text, not as fill evidence.

The UI must use the response `mode`/`execution_mode` for the active-mode label when present, with the selected client state only as a pre-start display fallback. A response saying `execution_is_paper: true` is not evidence that an order filled.

## Signal, intent, fill, and blocker mapping

The signal endpoint is `/api/orderbook/simulated-signals?symbols=<comma-separated>&page=<n>&per_page=<n>`. It returns `signals[]`, pagination, summary counters, and `diagnostics`. The same latest signal rows are also available as `portfolio.recent_signals[]` in status.

For every signal row, map values as follows:

| UI value | Source field | Rendering rule |
| --- | --- | --- |
| Symbol/time/quote | `signals[].symbol`, `signals[].timestamp`, `signals[].price` | Show only when the signal row exists; quote is unavailable when no live-parity row exists, not zero. |
| Signal generated | `signals[].signal_generated` (and `signal`/`signal_type`) | `true` is a generated signal; `false` is a valid hold/no-signal state. |
| Signal reason/diagnostic | `signals[].signal_reason`, `signals[].ml_analysis.*`, `signals[].execution_analysis.diagnostic_factor` | Preserve backend wording; absent optional fields are unavailable, not failed. |
| Generated intent | `signals[].execution_analysis.executable_intent === true` plus `signal_generated === true` | Label `Executable paper intent` only in live-parity; this is intent evidence, not fill evidence. |
| Paper-blocked intent | `signals[].execution_analysis.blocked === true` and `executable_intent === false`, or a generated live-parity signal with a non-`paper_fill` `blocker_reason` | Label `Paper blocked`; show `blocker_reason` per intent. Never label this as filled. |
| Per-intent blocker reason | `signals[].execution_analysis.blocker_reason` | Known values include `no_signal`, `profitability_gate`, `ml_confidence_gate`, `existing_position`, `pending_order`, `max_positions`, `nonpositive_position_size_or_price`, `below_minimum_notional`, `spot_cannot_open_short`, `insufficient_cash`; `market_data_unavailable` is an aggregate status blocker when no quote exists. Unknown/absent is `Blocker reason unavailable`. |
| Paper-filled outcome | A matching entry in `portfolio.recent_trades[]`/`portfolio.trades[]` with `trade_type: "live_parity"` (or a matching paper trade record from the status response), together with live-parity mode | Label `Paper filled` only from the persisted/returned trade record. `execution_analysis.blocker_reason: "paper_fill"` and `executable_intent: true` authorize an intent, but alone do not prove settlement. |
| Synthetic outcome | A trade/portfolio result under `mode: "simulated"` / `execution_mode: "simulated"`; local fallback trades have local IDs and `mode: "simulated"` | Use `Synthetic fill`/`Synthetic portfolio` wording. Never call it paper-filled or live-filled. |

Important backend detail: `openPositionLocked` sets `trade_type` to `mode_` for non-live modes, so live-parity paper fills are `live_parity`; a real live order path uses `live` and is outside this tab. The UI should require both the live-parity mode and a returned trade record before showing `Paper filled`.

## Summary, blocker, quote, account, and error mapping

| UI value | Source field | Empty/unavailable/failure behavior |
| --- | --- | --- |
| Signals evaluated | `diagnostics.signals_evaluated` or `portfolio.order_book_signal_diagnostics.signals_evaluated` | Missing means `Unavailable`, not zero, unless the response explicitly supplies zero. |
| Signals generated | `diagnostics.signals_generated` or corresponding portfolio diagnostic | Explicit zero is `0 generated`; missing is unavailable. |
| Executable intents | `diagnostics.executable_order_intent_count` or corresponding portfolio diagnostic | Explicit zero is `0 executable intents`; do not infer from displayed page length. |
| Paper-filled count | Count returned live-parity trade records in `portfolio.recent_trades`/`trades` with `trade_type: "live_parity"`; no dedicated backend count exists | If no authoritative trades list/count is present, show `Paper fills: unavailable`, not zero and not a fill. |
| Paper-blocked count | `diagnostics.execution_blocker_counts` total (or portfolio diagnostic equivalent) for live-parity blocker observations; no dedicated `paper_blocked_count` exists | Show blocker counts when present; otherwise `Blocked intents: unavailable`. Do not derive from `signals_generated - executable` across a paginated subset. |
| Blocker summary | `diagnostics.execution_blocker_counts` or `portfolio.execution_blocker_counts` | Empty object is `No blockers recorded`; absent is `Blocker summary unavailable`. Format each key/count without renaming the source reason. |
| Quote availability | `portfolio.order_book_signal_diagnostics.market_data[symbol]`: `status` (`refreshed`/`failed`), `category`, `error`, `retries`, `last_success_at`; counts in `market_data_refreshed_count`, `market_data_failed_count`, and symbols in `market_data_failures` | `refreshed` means quote available. `failed` or absent for a selected live-parity symbol means `Quote unavailable`; no synthetic replacement. The signal endpoint exposes only aggregate diagnostics and may not include `market_data`; render quote detail as unavailable when that detail is absent. |
| Coverage | `diagnostics.coverage_complete` or portfolio diagnostic equivalent | `false` means partial coverage; show that status and do not present the page as a complete universe result. |
| Account readiness | No account-readiness field is emitted for `live_parity`; this mode intentionally uses public Coinbase data and local paper settlement without credentials/account mutation | Show `Account readiness: Not applicable — paper mode uses no Coinbase account`. If a future backend supplies `account_ready`/`account_readiness`, render its explicit value; never infer readiness from `execution_is_paper` or quote success. |
| Generic backend error | HTTP failure body `error`/`message`, or frontend `ApiResponse.error`; status may be `error` | Show `Live-data paper results unavailable: <error>`. Keep signals/outcomes empty or stale-but-marked-unavailable according to query state. Never activate synthetic fallback for live-parity. |
| Start settling/error | `status: "settling"` plus `error`/`message`, or `status: "error"` plus `error` | Show settling/error state and no fill claim. Stop/start controls must remain consistent with `is_active`. |

The status payload's `stats` object remains the existing portfolio statistics source (`total_trades`, P&L, fees, and so on). It is not a paper-fill ledger by itself; pair it with `recent_trades`/`trades` and `trade_type` when a mode-specific fill count is required.

## Explicit UI state matrix

1. Not started: show the selector and mode explanation; show empty states such as `Start a session to see signals` and `No paper outcomes yet`.
2. Loading: show `Loading live-data paper signals/status…`; do not show zero counts as if they were results.
3. Synthetic active: show `Synthetic simulation` and existing synthetic signals/stats/fills. Do not show Coinbase quote or account readiness claims.
4. Live-parity active with no signals yet: show `Live-data paper execution` and `No live quote-backed signals available yet`; do not synthesize rows.
5. Live-parity generated but not executable: show generated signal plus `Paper blocked — <blocker_reason>`; show aggregate and per-intent reasons.
6. Live-parity executable without matching trade record: show `Paper intent pending/unsettled` (or `Paper outcome unavailable`), never `Paper filled`.
7. Live-parity matching `live_parity` trade record: show `Paper filled` and the trade fields; this is still not a real exchange fill.
8. Quote failure/partial coverage: show `Quote unavailable` with category/retry/error when present and `No paper fill`; do not fall back to synthetic values.
9. Account readiness: show `Not applicable` for the current live-parity contract, or the explicit future backend readiness field if introduced.
10. Generic backend/HTTP error: show the error and a non-filled state. A failed request must not leave a misleading previous `Paper filled` label without marking it stale/unavailable.

## Existing components/types to reuse or extend

- `frontend/components/dashboard/SimulatedTradingPanel.tsx`: selector and active-mode warning already exist; extend its status query/rendering with the mode-specific matrix above.
- `frontend/lib/api.ts`: preserve `buildStartTradingPayload`, `startTrading`, local synthetic fallback isolation, and `getOrderBookSignals`; add explicit live-parity response typing/normalization rather than broad `any` fallback where practical.
- `frontend/hooks/useTrading.ts`: `TradingStatusPayload`, `OrderBookSignalsData`, query/error behavior, and chunk merge are reusable. Ensure live-parity failed requests remain errors/partial coverage rather than becoming synthetic responses.
- `frontend/types/trading.ts`: extend `OrderBookSignal.execution_analysis`, `OrderBookSignalDiagnostics`, and status/portfolio types with the documented optional mode, market-data, and outcome fields; use `??` so explicit zeros survive.
- `frontend/components/dashboard/OrderBookSignalsTable.tsx`: reuse signal and execution-analysis columns plus diagnostics formatting; add mode-aware labels and empty states without treating page length as session totals.
- `frontend/components/dashboard/ExecutionReconciliationTable.tsx` and `frontend/lib/executionReconciliation.ts`: reuse read-only generated/blocked/outcome summary presentation where the response is available, while keeping the live-parity paper label distinct from real live execution.
- `frontend/lib/startTradingPayload.test.ts`, `frontend/lib/liveTabProducer.test.ts`, `frontend/lib/executionReconciliation.test.ts`, and `frontend/components/dashboard/__tests__/dashboard-tables.test.tsx`: existing contract/diagnostic fixtures to extend. Add focused Simulated Trading mode/outcome fixtures for the empty, quote-unavailable, account-not-applicable, blocker, pending, filled, and generic-error states.

## Required implementation/test checkpoints

- Assert the request contains `mode: "simulated"` and `parameters.execution_mode` with exactly `simulated` or `live_parity`; reject/avoid any `mode: "live"` path from this selector.
- Assert the visible labels contain `Synthetic simulation` or `Live-data paper execution` and explicitly state no real/ Coinbase orders.
- Assert only a returned `live_parity` trade record yields `Paper filled`; generated intent, `paper_fill` analysis, blocked intent, unavailable quote, account-not-applicable, and generic error do not.
- Assert blocker summaries use the backend count maps and each blocked row uses its own `execution_analysis.blocker_reason`.
- Assert live-parity quote failure never calls or displays local synthetic signal/portfolio fallback.
- Assert explicit zero counts render as zero and missing fields render as unavailable/empty according to the matrix above.

## Source references

- `src/api/PredictController.cpp:1179-1201` — execution mode validation and start route.
- `src/trading/SimulatedTradingService.cpp:489-601` — signal serialization and execution analysis.
- `src/trading/SimulatedTradingService.cpp:1744-1811` — quote-missing handling, live-parity blocker counting, and paper entry.
- `src/trading/SimulatedTradingService.cpp:1961-2156` — portfolio/status fields, diagnostics, and stats.
- `src/trading/SimulatedTradingService.cpp:2159-2308` — mode initialization and start response.
- `src/trading/SimulatedTradingService.cpp:2399-2500` — simulated signal response and diagnostics.
- `frontend/components/dashboard/SimulatedTradingPanel.tsx:495-810` — current selector, request, and signal diagnostics UI.
- `frontend/lib/api.ts:618-672, 786-879, 968-1069` — payload builder, start/fallback behavior, status/signals API.
- `docs/reports/live-parity-paper-and-blocker-attribution-progress-2026-08-08.md` — prior safety boundary and remaining runtime evidence.
