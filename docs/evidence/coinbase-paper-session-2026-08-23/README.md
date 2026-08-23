# Coinbase live-data paper-session reproduction

Capture date: 2026-08-23 UTC
Runtime: `trade_cpp-backend_1` (`ghcr.io/chasekb/trade/cpp-backend:dev`) and `trade_frontend_1` (`ghcr.io/chasekb/trade/frontend:dev`), Podman Compose project `trade`; frontend `127.0.0.1:3000`, backend `127.0.0.1:8081`; backend `/health` returned 200.

## Safety

The captured session was `mode=live_parity`, `execution_mode=live_parity`, `execution_is_paper=true`, and `market_data_source=coinbase_public`. The start response explicitly said `Live-parity paper trading started; Coinbase orders are disabled`. No real Coinbase order endpoint was called. The session was stopped at 2026-08-23T04:35:38Z and final status was inactive.

## Reproduction context

The browser harness could not be used because Chrome required an operator to approve remote debugging in `chrome://inspect` (the harness stopped before navigation). Therefore this is a runtime/API reproduction of the exact frontend contract, not a claim that the button was clicked in a browser. The frontend source was traced directly:

- `frontend/components/dashboard/SimulatedTradingPanel.tsx:664-680` exposes `Coinbase live-data paper mode`; `:585-606` builds the start state and passes `execution_mode` inside `parameters`.
- `frontend/lib/api.ts:620-672` builds the serialized start payload; `:812-835` POSTs `/api/trading/simulated/start` first.
- `frontend/hooks/useTrading.ts:388-444` polls order-book signals every 3 seconds while active.
- `frontend/components/dashboard/SimulatedTradingPanel.tsx:498-511` enables the simulated WebSocket and immediately refetches stats/signals after activation.
- `src/api/PredictController.cpp:1180-1201` accepts `execution_mode` from the top-level payload or `parameters` and passes it to `SimulatedTradingService`.
- `src/trading/SimulatedTradingService.cpp:1832-1907` runs the worker loop; live quotes are fetched before each tick and the loop sleeps one second.
- `src/trading/SimulatedTradingService.cpp:2375-2475` returns latest-by-symbol signals; pagination is display-only.

## Selected state and identifiers

- Universe: `all_usd` equivalent, seven symbols: BTC-USD, ETH-USD, SOL-USD, ADA-USD, DOT-USD, XRP-USD, LTC-USD.
- Strategy: `ml_enhanced_orderbook`.
- Most recent Transformer model observed from `GET /api/ml/models`: `transformer_model_1787458223`, trained at `2026-08-23T04:10:23Z`, version `1787458223`. The active-model cache was already the most recent model at capture; the start contract itself does not serialize a model ID—model selection is consumed through the active-model cache.
- Session ID: `sim_1787459668`.
- Start request timestamp: 2026-08-23T04:34:26Z; backend `started_at`: 2026-08-23T04:34:28Z.
- Stop timestamp: 2026-08-23T04:35:38Z.
- Payload: `request-payload.json` (the exact JSON sent to `/api/trading/simulated/start`; no credentials).

## Fresh evidence window

The window ran for 15 samples from 2026-08-23T04:34:41Z through 2026-08-23T04:35:24Z, approximately 43 seconds after the session started. Evidence is in `status-and-signal-window.jsonl`.

- Worker tick advanced from 6 to 20 (with one sample at tick 12 before the next tick), and `signals_evaluated` advanced from 42 to 140: seven selected symbols per tick.
- Every sample reported `market_data_source=coinbase_public`, all seven symbols `status=refreshed`, and no market-data failures in the captured window.
- The signal endpoint returned seven latest-by-symbol records and `coverage_complete=true`; its `last_updated` advanced approximately once per worker tick, not once per minute.
- The frontend contract polls this endpoint every 3 seconds. This evidence therefore rules out a backend one-minute producer cadence for this runtime window. Any observed one-minute widget behavior is a display/browser/cache/refetch issue or a different runtime window, not proven to be exchange cadence here.
- The final response had seven records, `total_analyzed=7`, `active_signals=0`, `signals_generated=0`, `executable_order_intent_count=0`, `total_trades=0`, and all P&L/fee/drawdown metrics zero.

## Per-symbol reconciliation at final snapshot

| Symbol | Data | Transformer | Signal | Blocker | Intent | Fill |
|---|---|---|---|---|---:|---:|
| BTC-USD | sufficient/refreshed | warming_up | hold | profitability_gate | no | no |
| ETH-USD | sufficient/refreshed | warming_up | hold | profitability_gate | no | no |
| SOL-USD | sufficient/refreshed | warming_up | hold | no_signal | no | no |
| ADA-USD | sufficient/refreshed | warming_up | hold | profitability_gate | no | no |
| DOT-USD | sufficient/refreshed | warming_up | hold | no_signal | no | no |
| XRP-USD | sufficient/refreshed | warming_up | hold | no_signal | no | no |
| LTC-USD | sufficient/refreshed | warming_up | hold | profitability_gate | no | no |

The final signal payload records `inference_status=warming_up`, `model_version=transformer-warming-up`, `transformer_expected_lookback=60`, `transformer_feature_width=353`, and `transformer_sequence_length=42` for all symbols. For profitability-gate rows, expected return was zero and the fee/spread/slippage hurdle was positive; for no-signal rows, the activity threshold was not met. These are the observed immediate no-trade reasons; they do not establish whether a longer warm-up would later produce executable signals.

## Runtime log evidence

Backend logs recorded worker start at 04:34:28.092 and worker stop at 04:35:38.191 for `sim_1787459668`. No Coinbase order submission log appeared. A separate database warning at 04:31:54 (`pg_input_is_valid` missing) predates this session and was not used to classify its no-trade outcome.

## Artifacts

- `request-payload.json`
- `start-response.json`
- `status-and-signal-window.jsonl`
- `final-signals.json`
- `stop-response.json`
- `final-status.json`

No source code was changed. Browser screenshot, browser console, query/refetch, and WebSocket event capture remain blocked until Chrome remote-debugging approval is granted; the source-level polling/WebSocket contract and backend API window are recorded above.
