# TRADE-BL-0030: Read-only Coinbase paper-session reproduction plan

Status: prerequisite plan only; no trading session was started by this task.

Prepared: 2026-08-23T01:57:39-05:00
Repository branch: `wt/t_078173e4`
Repository commit inspected: `8af7838c9112e4f88c0f358504877d054ce9eb0c` (`feat(trade): remove live quote cadence enforcement`)
Working tree at inspection: clean.

## Objective and non-goals

Reproduce the zero-trade observation in the frontend's **Simulated Trading** tab using Coinbase public live market data, `live_parity` paper execution, the `ml_enhanced_orderbook` strategy, the user-requested symbols, and the newest available Transformer model. The session must remain paper-only: Coinbase public market-data reads are allowed; Coinbase account reads and order submission are not part of this run.

This document establishes inputs, safety gates, and evidence requirements. It does not claim that the runtime was reachable, that a session was started, or that zero trades were observed.

## Repository/runtime contract found

### Frontend entry point and route

- `frontend/app/page.tsx:14-75` exposes the `simulated-trading` tab and renders `SimulatedTradingPanel`.
- The panel's `frontend/components/dashboard/SimulatedTradingPanel.tsx:495-810` owns the selection state and start/stop flow.
- The selected execution mode is explicit at `SimulatedTradingPanel.tsx:661-681`:
  - `simulated`: synthetic market simulation.
  - `live_parity`: Coinbase live-data paper mode.
- `live_parity` must be selected. Do not use the synthetic mode or a local synthetic fallback for this reproduction.

### Start request and backend endpoints

`frontend/components/dashboard/SimulatedTradingPanel.tsx:585-606` creates the request state:

- `mode`: `simulated`
- `strategy`: `ml_enhanced_orderbook`
- `symbols`: the explicitly recorded selected symbol array
- `parameters.execution_mode`: `live_parity`
- default `position_size_mode`: `percent`
- default `position_size_value`: `1`
- default `initial_portfolio_size`: `10000`
- `max_positions`: `100` unless changed and recorded
- `position_update_interval`: `5`

`frontend/lib/api.ts:620-672` serializes the canonical payload. The serialized request is posted first to `POST /api/trading/simulated/start` (`api.ts:812-819`), with the legacy `/api/simulated-trading/start` fallback only if the first endpoint is unavailable. Capture the exact JSON sent over the wire; do not reconstruct it from UI labels after the fact.

The backend routes are declared in `include/api/PredictController.hpp:25-30`. `src/api/PredictController.cpp:1182-1201` accepts only `simulated` or `live_parity` and passes the payload to `SimulatedTradingService::startSession`.

### Paper-mode safety boundary

The source contract is explicit:

- `src/trading/SimulatedTradingService.cpp:144-146` treats `live_parity` as a live-market-data mode.
- `src/trading/SimulatedTradingService.cpp:2177-2187` constructs a Coinbase client for public market data; credentials are not required for public quotes.
- `src/trading/SimulatedTradingService.cpp:575-586` applies live-parity spot/minimum-notional gates.
- `include/trading/SimulatedTradingService.hpp:218-220` states that live-parity fills settle locally and never dispatch an exchange order.
- `src/trading/SimulatedTradingService.cpp:657-663` enables exchange order execution only when `mode_ == "live"`, the client is configured, and `parameters.live_order_execution` is true. `live_parity` therefore cannot enter that dispatch path.
- `src/trading/SimulatedTradingService.cpp:2281-2283` returns a started message identifying that Coinbase orders are disabled.
- `frontend/lib/api.ts:800-810` and `:867-879` do not use the local synthetic fallback when `execution_mode` is `live_parity`.

### Strategy and model controls

- `frontend/components/dashboard/StrategySelector.tsx:11-16` exposes `ml_enhanced_orderbook` as “ML-Enhanced Order Book”.
- `frontend/components/dashboard/StrategyConfigForm.tsx:121-148` lists available models, sorts by descending `trained_at`, and auto-selects the first row. Record the list and selected model rather than relying on the label/date rendered by the browser.
- `GET /api/ml/models` is the model-discovery endpoint (`frontend/lib/api.ts:1288-1294`; backend route `PredictController.hpp:23`).
- `src/api/PredictController.cpp:991-1097` reports base models when their ONNX files exist and trained packages only when `metadata.json` and every required artifact are present. A Transformer requires `transformer.onnx` (`PredictController.cpp:162-169`).
- The model endpoint is read-only. Do not click “Set Active” during this reproduction: `POST /api/ml/models/set_active` changes server model state and is not required to identify the newest model.

### Data and status surfaces

- `GET /api/simulated-trading/status` or `GET /api/trading/simulated/status` (`PredictController.hpp:29-30`) provides session status. Capture `session_id`, `mode`, `strategy`, `symbols`, `started_at`, `updated_at`, worker/activity state, market-data status, and blocker counters when present.
- `GET /api/orderbook/simulated-signals` (`PredictController.hpp:33`) provides latest-by-symbol signal rows and diagnostics. Capture `last_updated`, selected/requested counts, `signals_evaluated`, `signals_generated`, `executable_order_intent_count`, Transformer warming/rejected-input counts, and `execution_blocker_counts`.
- `GET /api/trades/stats?trade_type=simulated&session_id=<id>` is the session-scoped stats check; also capture the simulated portfolio/status response.
- `frontend/hooks/useWebSocket.ts:4-20, 205-215` uses Socket.IO and records `order_book_update`, `trading_signal`, `trading_status`, `position_update`, and `ml_prediction` events. The hook stamps received messages locally with an ISO timestamp; preserve the raw event data and local receive timestamp separately.
- `frontend/components/trading/OrderBookTable.tsx:238-266` renders order-book updates and a `lastUpdate` value. Capture widget state or a screenshot showing symbol, connection state, and update time.

## Inputs known before runtime

| Input | Required value | Source / state |
|---|---|---|
| UI tab | Simulated Trading | `frontend/app/page.tsx:59-75` |
| Execution mode | `live_parity` / Coinbase live-data paper | `SimulatedTradingPanel.tsx:661-681` |
| Strategy | `ml_enhanced_orderbook` | panel default and `StrategySelector.tsx:11-13` |
| Symbols | **Not identified in task context** | See limitation below; must be captured from the actual selection before Start |
| Transformer model | **Not identified without runtime model listing** | Must query `GET /api/ml/models`, filter `type=sequence`/`transformer`, sort by parseable `trained_at`, and record the selected `model_id` |
| Starting capital | `10000` unless changed | `SimulatedTradingPanel.tsx:533-538` |
| Position size | `percent`, value `1` unless changed | `SimulatedTradingPanel.tsx:533-539` |
| Max positions | `100` unless changed | `SimulatedTradingPanel.tsx:588-591` |
| Update interval | `5` seconds unless changed | `SimulatedTradingPanel.tsx:598-600` |
| Real execution | Must remain disabled | `live_parity` safety boundary above |

### Known limitations that block pretending the inputs are complete

1. The task/card context does not contain the user's requested universe symbols. Repository code only provides dynamic universe selectors and a fallback list (`frontend/lib/symbolUniverse.ts:3-17`); it does not establish which symbols the user intended. Do not substitute `FALLBACK_COINBASE_SYMBOLS`, `all_usd`, or a guessed major-pair list. Before execution, obtain the exact symbol array from the originating request or an authoritative runtime selection and record its source. If unavailable, stop and report “requested universe not identified”.
2. No runtime `/api/ml/models` response was available during this planning pass, and model files were not inspected outside the source tree. The most recent Transformer model cannot be named from source alone. The runtime listing is authoritative for this run; if it has no valid `sequence`/`transformer` entry, record the empty response and the endpoint/environment consulted.
3. No browser/runtime session was started. Therefore there is no session ID, model ID, payload capture, WebSocket evidence, screenshot, order-book update window, or zero-trade interval yet.

## Safe execution procedure for the dependent reproduction task

1. Record the environment URL, frontend/backend image or process versions, UTC/local clock, branch/commit, and whether the backend is local, staging, or another explicitly named environment. Do not proceed if the target is an unknown production/live-account environment.
2. Verify `GET /api/ml/models` is reachable. Save the raw response. Select only a valid Transformer (`type` `sequence` or `transformer`) with a parseable `trained_at`; choose the newest timestamp and record `model_id`, `model_name`, `version_id`, `trained_at`, and required artifacts. Do not activate a model unless the environment owner explicitly requires it.
3. Verify the exact requested symbols from an authoritative input. In the UI, switch to Universe or Custom as appropriate, then capture the final ordered symbol array after all filtering. Confirm no silent cap or fallback changed it.
4. Open Simulated Trading, select “Coinbase live-data paper mode”, select `ML-Enhanced Order Book`, and confirm the real-execution warning is visible. Confirm no Live Trading tab or live-start endpoint is being used.
5. Before pressing Start Trading, enable network capture for fetch/XHR and Socket.IO/WebSocket frames, clear the console, and start a synchronized evidence log. Use UTC ISO-8601 timestamps with a monotonic elapsed-seconds column.
6. Press Start Trading once. Save the exact serialized POST URL, headers excluding secrets, JSON body, HTTP status, response body, local click timestamp, response timestamp, and returned `session_id`. Redact credentials/cookies/tokens from all durable evidence.
7. Immediately poll the session status and order-book signals at a documented interval. Preserve raw JSON responses, not only rendered values. Subscribe/observe the Socket.IO events listed above and record every order-book update timestamp by symbol.
8. Maintain the evidence window until the planned end time or an explicit stop condition. The zero-trade interval is `[session started_at, stop requested_at]`; if startup fails, record the narrower attempted interval and failure reason instead of calling it a reproduced zero-trade run.
9. At the end, capture status, stats, portfolio, signals/diagnostics, and the final WebSocket/event counters. Press Stop Trading once and save the stop response plus the worker/session settling-to-stopped transition. Never call `/api/trading/live/start`, `/api/trading/live/execute`, close-position, or liquidation endpoints.

## Required evidence checklist

### Selection and request identity

- [ ] Environment/base URL and runtime identifier.
- [ ] Repository commit, branch, and configuration source (do not copy secrets).
- [ ] Exact ordered selected symbol array and source/selection mode.
- [ ] Raw `/api/ml/models` response and Transformer selection rule.
- [ ] Selected `model_id`, `model_name`, `version_id`, `type`, `trained_at`, and artifact validity.
- [ ] UI route/tab and relevant state: execution mode, strategy, symbols, model, capital, sizing, thresholds/presets.
- [ ] Exact serialized start request payload and endpoint.
- [ ] Start click, request sent, response received, and session-start timestamps.
- [ ] Returned `session_id` and full start response (redacted).

### Safety proof

- [ ] `execution_mode=live_parity` appears in the serialized payload and status response.
- [ ] Status/portfolio identifies Coinbase public market data and paper execution.
- [ ] `live_order_execution` is absent or false; no live endpoint requests occurred.
- [ ] No Coinbase order-submission request, order ID, or account mutation occurred.
- [ ] Stop response and final stopped/settled worker state captured.

### Runtime/zero-trade evidence

- [ ] Raw status snapshots with `active`, `mode`, `strategy`, `symbols`, `session_id`, worker state, and timestamps.
- [ ] Raw API/WebSocket responses and event receive timestamps.
- [ ] Per-symbol order-book widget snapshots/screenshots and update timestamps.
- [ ] `market_data_status` per symbol, including errors/retries/last success where present.
- [ ] Signal diagnostics: evaluated, generated, executable intents, Transformer warming/rejections, and blocker counts.
- [ ] Portfolio/stats snapshots proving `total_trades=0` (or the exact first trade if not zero).
- [ ] Full zero-trade interval with start/end timestamps and polling/event cadence.
- [ ] Any failed request, missing symbol, unavailable model, disconnect, or deviation recorded with endpoint and raw response summary.

## Acceptance / handoff rule

This planning task is complete when this document is committed with the two explicit input limitations above. The dependent execution task must not start until the requested symbols and a valid newest Transformer model are identified (or the limitations are deliberately accepted and recorded), and it must not report “reproduced zero trades” without the full evidence checklist and a final stopped-session snapshot.
