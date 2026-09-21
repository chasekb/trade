# TRADE-BL-0030 reproduction report: Coinbase paper session with zero UI trades

Report date: 2026-09-21 (UTC)
Evidence execution date: 2026-09-21 (UTC)

## Verdict

The zero-trade UI behavior reproduced for a read-only Coinbase live-data paper session. The session started successfully, remained active during the observation window, and stopped cleanly. The UI showed zero persisted trades and zero trade rows for the entire observed active interval.

This is not evidence that the backend generated no signals. The stop diagnostics recorded 319 generated signals and 806 evaluated signals, while execution was blocked primarily by `ml_confidence_below_threshold`. Quote failures and the absence of WebSocket messages are material limitations and must remain attached to the result.

## Exact selected inputs

- Frontend route: `http://localhost:3000/`, `Simulated Trading` tab.
- Safety mode: Coinbase live-data paper mode (`execution_mode=live_parity`). The UI stated that Coinbase public order-book data is used and that Coinbase orders are never submitted. No real execution or account mutation was enabled.
- Strategy: `ml_enhanced_orderbook`.
- Symbol mode: `universe`.
- Universe: `all_usd` / All USD Pairs (recommended).
- Selected symbol count: 403.
- First selected symbols: `00-USD`, `1INCH-USD`, `2Z-USD`, `A8-USD`, `AAVE-USD`, `ABT-USD`, `ACH-USD`, `ACS-USD`, `ADA-USD`, `AERGO-USD`.
- Last selected symbols: `XPL-USD`, `XRP-USD`, `XTZ-USD`, `XYO-USD`, `YB-USD`, `YFI-USD`, `ZAMA-USD`, `ZEC-USD`, `ZEN-USD`, `ZRX-USD`.
- Model selected in the UI: Transformer model `transformer_model_1789834654`, displayed date `2026-09-19`.
- Important serialization gap: the selected model ID was not present in the observed `/api/trading/simulated/start` request body. The UI selection is therefore documented, but the backend request alone cannot prove model identity.

## Session and timestamps

All timestamps below are UTC and use ISO-8601 precision where available.

- Start request: `2026-09-21T04:16:23.349Z`.
- Request: `POST /api/trading/simulated/start`.
- Start response: HTTP 200; response cadence timestamp `2026-09-21T04:16:24.663Z`.
- Session ID: `sim_1789964184_0`.
- Worker/browser evidence session: `20260920_231459_f681bb`.
- WebSocket opened: `2026-09-21T04:16:24.728Z`.
- WebSocket closed: `2026-09-21T04:16:24.774Z`.
- First active UI observation: `2026-09-21T04:16:28` (approximately five seconds after start).
- Final active diagnostics: `2026-09-21T04:17:26.184Z`.
- Stop submitted: `2026-09-21T04:17:26.168Z`.
- Session inactive verified: `2026-09-21T04:17:29.170Z`.

Zero-trade interval: from the first active-state observation at approximately `2026-09-21T04:16:28` through the stop/inactive verification at `2026-09-21T04:17:29.170Z`. During that interval the UI displayed “No simulated trades have been recorded yet”, `Total Trades` 0, `Persisted trades` 0, and reconciliation `0 signal rows · 0 trade rows`.

## Serialized start request

The observed request contained:

- `symbols`: the 403-symbol array identified above.
- `strategy` and `strategy_type`: `ml_enhanced_orderbook`.
- `parameters` and `strategy_params`: `position_size_mode=percent`, `position_size_value=1`, `initial_portfolio_size=10000`, `execution_mode=live_parity`, and `diagnostics_enabled=true`.
- `max_positions=100`.
- `position_size_percent=1`.
- `position_size=0.01`.
- `position_update_interval=5`.
- `immediate_start=true`.
- `batch_size=3`.
- `initial_balance=10000`, `capital=10000`, and `initial_portfolio_size=10000`.

The request did not serialize the UI-selected `transformer_model_1789834654` identifier.

## API, WebSocket, order-book, and worker observations

- The simulated start request returned HTTP 200 and created the session `sim_1789964184_0`.
- Order-book polling returned HTTP 200. Early cadence coverage repeatedly reported `selected_symbols=403`, `latest_symbol_rows=403`, `signal_generated=0`, and `quote_received=0`.
- Order-book/session coverage reported `active_signals=0` during the observed zero-trade UI interval.
- The WebSocket endpoint was `ws://cpp-backend:8080/ws`. It opened and closed within 46 ms and delivered zero messages.
- The session was stopped after capture; inactive state was verified at `2026-09-21T04:17:29.170Z`.
- Stop diagnostics reported `quote_requests=863`, `quote_success=696`, `quote_failures=167`, `signals_evaluated=806`, `signals_generated=319`, and `signals_not_generated=320`.
- Dominant blocker: `ml_confidence_below_threshold`, count 173.
- Final coverage still reported `selected_symbols=403`, `latest_symbol_rows=403`, and `signal_generated=0`, with exchange-response quote failures.

Interpretation: the reproduced symptom is zero persisted/executed trades in the UI. It cannot be reduced to “the model produced no signal,” because the worker diagnostics recorded internal signal generation. Quote failures, coverage discrepancies, and the failed/empty WebSocket stream prevent a clean end-to-end parity conclusion.

## Environment, repository, and configuration provenance

- Frontend URL observed: `http://localhost:3000/`.
- Backend WebSocket host observed: `cpp-backend:8080`.
- Repository under investigation: `chasecapitalmanagement/etl/trade`.
- Report checkout reference (this worktree): branch `wt/t_095c8b1c`, commit `4128a23f224f3d0b9e2dbc31f592aeeadf072e5a` (`docs: document Hermes Kanban board integration in CLAUDE.md`).
- The evidence-producing browser run did not record the deployed/runtime Git SHA in its raw artifact. Upstream task history identifies PR #35 squash commit `5b471bf` as the planned change lineage, but that is not sufficient proof that the running local services used that exact commit or image. Treat runtime commit as unknown until captured from the service/image metadata.
- Relevant repository contract: `src/api/PredictController.cpp` accepts `execution_mode` values `simulated` and `live_parity`; `src/trading/SimulatedTradingService.cpp` treats `live_parity` as live market data without making this paper flow a real order-submission path.
- No credentials, real orders, exchange account mutations, or destructive actions were used.

## Raw evidence and reproducibility pointers

Primary structured evidence artifact from the execution task:

- `docs/investigations/trade-bl-0030-paper-session-evidence-2026-09-21.md` in the evidence worker worktree.
- Absolute source path at capture time: `/run/media/unordered_map/priority_queue/log(perplexity)/-sum/log/Pr(context_for_token)/chasecapitalmanagement/etl/trade/.worktrees/t_f088b2fe/docs/investigations/trade-bl-0030-paper-session-evidence-2026-09-21.md`.

Browser screenshots and in-page structured request/response capture:

- Browser harness workspace: `/home/kahlil/.hermes/cache/browser-use/workspace/20260920_231459_f681bb`.
- The harness captured initial configuration, active-session, and post-stop screenshots, plus start/status/order-book/diagnosis/reconciliation/stop responses and WebSocket observations. The harness workspace is outside the repository and may be pruned; copy it into durable task storage before relying on it for long-term replay.

## Reproduction limitations and follow-up requirements

1. The selected model ID was visible in UI state but omitted from the start payload. A future run must capture the serialized model field or record an explicit backend model-resolution response.
2. The evidence artifact does not contain the exact runtime container image digest or Git SHA. Capture `/health`/build metadata and image digests for the next run.
3. The WebSocket delivered no messages because the connection closed almost immediately. This limits conclusions about real-time dashboard updates.
4. Quote failures occurred (`167/863` requests), so the run is not a clean exchange-data success case.
5. Early/final coverage showed `signal_generated=0` while stop diagnostics showed 319 internally generated signals. Reconcile these counters before treating the dashboard as a faithful signal view.
6. The observed zero persisted trades proves zero executions recorded by the UI/session, not zero candidate signals or zero worker activity.
7. The raw browser workspace is external to the repository and should be archived or attached if this report is used as a long-lived regression fixture.
