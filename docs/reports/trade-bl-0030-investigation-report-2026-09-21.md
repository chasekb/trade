# TRADE-BL-0030 investigation report: Coinbase live-data paper zero-trade UI behavior

Report date: 2026-09-21 UTC
Status: evidence-backed investigation; no production behavior change
Scope: rendered Simulated Trading UI, Coinbase public market data, live-parity paper execution only

## Executive conclusion

The requested zero-trade UI behavior was reproduced for a fresh Coinbase live-data paper session using the rendered Simulated Trading flow. During the observed active interval the UI persisted zero trades and displayed zero trade rows, while stop diagnostics recorded 806 evaluated signals and 319 generated signals. The evidence therefore supports “zero persisted/executed UI trades,” not “no internal signal generation.” The dominant recorded blocker was `ml_confidence_below_threshold` (173 occurrences); quote failures and inconsistent visible coverage counters are additional limitations.

The approximately one-minute-looking widget behavior is not an intentional one-minute frontend polling interval. Source inspection and runtime evidence show frontend HTTP polling at approximately 3 seconds for simulated signals/stats (and 5 seconds for status in the relevant hook), while the worker processes selected symbols sequentially and only sleeps after each tick. A long visible interval can emerge from exchange requests, retries, signal work, persistence, or a failed/empty WebSocket display path. The fresh capture did not retain enough per-tick/per-symbol timestamps to prove that any particular one-minute interval was caused by Coinbase transport latency, and it does not justify a causal fix claim.

A prior seven-symbol API window supplies the complete per-symbol reconciliation: all seven symbols refreshed successfully, Transformer sequences were warming at 20/60, and every outcome was a hold/no-signal or profitability-gate result with zero paper intents and fills. That earlier interval is evidence of model/readiness and signal-gate blocking, not missing quote data. The newer 403-symbol browser run is the authoritative reproduction of the current UI symptom, but its aggregate diagnostics must not be projected into a per-symbol table because the raw capture did not provide per-symbol quote timestamps and signal counts.

No real Coinbase order execution occurred. The sessions used `execution_mode=live_parity`; no authenticated order endpoint, account mutation, or Coinbase order submission was enabled. Fail-closed behavior and the selected universe were preserved.

## Exact reproduction and frontend context

Frontend route: `http://localhost:3000/`, rendered `Trading Dashboard` -> `Simulated Trading` tab.

Reproduction steps for the current UI symptom:

1. Open the Simulated Trading tab.
2. Select Coinbase live-data paper mode (`execution_mode=live_parity`).
3. Select Universe -> All USD Pairs (`all_usd`).
4. Keep strategy `ml_enhanced_orderbook` (ML-Enhanced Order Book).
5. Select the most recent Transformer model shown by the UI: `transformer_model_1789834654`, displayed date 2026-09-19.
6. Click Start Trading.
7. Capture status, order-book/signal, diagnosis, reconciliation, WebSocket, and rendered trade-widget state.
8. Click Stop Trading and verify the session is inactive.

The current reproduction used the full 403-symbol `all_usd` selection. First selected symbols were `00-USD`, `1INCH-USD`, `2Z-USD`, `A8-USD`, `AAVE-USD`, `ABT-USD`, `ACH-USD`, `ACS-USD`, `ADA-USD`, and `AERGO-USD`. Last selected symbols were `XPL-USD`, `XRP-USD`, `XTZ-USD`, `XYO-USD`, `YB-USD`, `YFI-USD`, `ZAMA-USD`, `ZEC-USD`, `ZEN-USD`, and `ZRX-USD`.

The earlier complete per-symbol runtime window used the seven-symbol selection `BTC-USD`, `ETH-USD`, `SOL-USD`, `ADA-USD`, `DOT-USD`, `XRP-USD`, and `LTC-USD`. It is kept as a separate evidence window below rather than being conflated with the 403-symbol reproduction.

## Current reproduction identifiers and timestamps

All times are UTC.

- Browser/evidence worker session: `20260920_232205_e27e29`.
- Browser harness workspace: `/home/kahlil/.hermes/cache/browser-use/workspace/20260920_231459_f681bb`.
- Start request: `POST /api/trading/simulated/start` at `2026-09-21T04:16:23.349Z`.
- Start response: HTTP 200 at `2026-09-21T04:16:24.663Z`.
- Simulated session ID: `sim_1789964184_0`.
- WebSocket opened: `2026-09-21T04:16:24.728Z`.
- WebSocket closed: `2026-09-21T04:16:24.774Z` (close 1006; no messages observed).
- First active UI observation: approximately `2026-09-21T04:16:28Z`.
- Stop request: `2026-09-21T04:17:26.168Z`.
- Final diagnostics timestamp: `2026-09-21T04:17:26.184Z`.
- Inactive state verified: `2026-09-21T04:17:29.170Z`.
- Observed zero-trade interval: approximately `2026-09-21T04:16:28Z` through `2026-09-21T04:17:29.170Z`.

During that interval the UI showed “No simulated trades have been recorded yet,” `Total Trades` 0, persisted trades 0, and `0 signal rows · 0 trade rows`. This is a UI/session persistence result, not proof that the worker generated no candidate signals.

## Serialized start request and model identity limitation

The observed request included:

- `symbols`: the complete 403-symbol array.
- `strategy` and `strategy_type`: `ml_enhanced_orderbook`.
- `parameters` and `strategy_params`: `position_size_mode=percent`, `position_size_value=1`, `initial_portfolio_size=10000`, `execution_mode=live_parity`, and `diagnostics_enabled=true`.
- `max_positions=100`, `position_size_percent=1`, `position_size=0.01`.
- `position_update_interval=5`, `immediate_start=true`, `batch_size=3`.
- `initial_balance=10000`, `capital=10000`, and `initial_portfolio_size=10000`.
- `training_model_type=transformer`.

The UI displayed `transformer_model_1789834654`, but that model ID was absent from the serialized start request. The evidence proves the UI selection and Transformer type, but not backend use of that exact model ID. This is an open contract/evidence gap, not a claim that the model was ignored or that it caused the zero trades.

## Current reproduction measurements

Stop diagnostics reported:

| Measurement | Observed value |
| --- | ---: |
| Selected symbols | 403 |
| Latest symbol rows | 403 |
| Quote requests | 863 |
| Quote successes | 696 |
| Quote failures | 167 |
| Signals evaluated | 806 |
| Signals generated | 319 |
| Signals not generated | 320 |
| Dominant blocker | `ml_confidence_below_threshold` |
| Dominant blocker count | 173 |
| Persisted UI trades | 0 |
| UI fills | 0 |
| WebSocket messages | 0 |

The order-book/status views repeatedly showed `signal_generated=0` and `quote_received=0` during the captured visible interval even though stop diagnostics later reported generated signals. This counter discrepancy is a diagnostic/display reconciliation gap. It prevents treating the rendered widget as a complete producer ledger without further runtime correlation.

## Prior seven-symbol per-symbol reconciliation window

This table comes from session `sim_1787459668`, captured on 2026-08-23. It is the complete symbol-level evidence available and is intentionally not presented as a per-symbol decomposition of the newer 403-symbol session.

Aggregate prior-window facts: session start `2026-08-23T04:34:28Z`, observed evaluation window `2026-08-23T04:34:41Z`–`2026-08-23T04:35:24Z`, stop `2026-08-23T04:35:38Z`; 7/7 symbols refreshed; 140 evaluations (20 per symbol); 0 generated signals; 0 paper intents; 0 fills; 0 positions; 0 pending orders; `execution_is_paper=true`; `mode=live_parity`; cash `$10,000`; Transformer warming state `20/60`.

| Symbol | Freshness / fetch result | Signal output | Model/readiness | Gate or blocker | Paper intent | Fill/no-fill |
| --- | --- | --- | --- | --- | ---: | --- |
| BTC-USD | Coinbase public quote refreshed; last-success timestamps advanced with the seven-symbol set | Hold / no executable signal | Transformer warming, 20/60 | Profitability gate; warm-up context | 0 | No fill |
| ETH-USD | Coinbase public quote refreshed; no fetch failure | Hold / no executable signal | Transformer warming, 20/60 | Profitability gate; warm-up context | 0 | No fill |
| SOL-USD | Coinbase public quote refreshed; no fetch failure | Hold / no signal | Transformer warming, 20/60 | No-signal gate | 0 | No fill |
| ADA-USD | Coinbase public quote refreshed; no fetch failure | Hold / no executable signal | Transformer warming, 20/60 | Profitability gate; warm-up context | 0 | No fill |
| DOT-USD | Coinbase public quote refreshed; no fetch failure | Hold / no signal | Transformer warming, 20/60 | No-signal gate | 0 | No fill |
| XRP-USD | Coinbase public quote refreshed; no fetch failure | Hold / no signal | Transformer warming, 20/60 | No-signal gate | 0 | No fill |
| LTC-USD | Coinbase public quote refreshed; no fetch failure | Hold / no executable signal | Transformer warming, 20/60 | Profitability gate; warm-up context | 0 | No fill |

Freshness evidence for this prior window includes polls near `04:34:47`, `04:34:52`, and `04:34:57`; ticks 8, 10, and 11; and seven-symbol last-success timestamps advancing roughly every 1–2 seconds. No sizing, minimum-notional, cash, pending-order, or fill gate was reached in that window because no executable intent was created.

## Update-rate and source/function mapping

Frontend:

- `frontend/components/dashboard/SimulatedTradingPanel.tsx` renders the canonical diagnosis/order-book state and applies display pagination; pagination does not cap the selected universe.
- `frontend/hooks/useTrading.ts` configures simulated signal/stats refetches at approximately 3 seconds and active status polling at approximately 5 seconds. The hook also merges WebSocket events into the canonical cache when messages arrive.
- `frontend/lib/api.ts` builds the simulated-start payload and preserves the selected symbols; requests over 50 symbols are chunked for reads and merged for display, not silently dropped.

Backend/controller/session:

- `src/api/PredictController.cpp` validates the simulated start mode, accepts `simulated`/`live_parity`, and forwards the payload and mode to `SimulatedTradingService::startSession`.
- `src/trading/SimulatedTradingService.cpp` copies the supplied symbols into the session vector without an unapproved universe cap; live-parity mode uses Coinbase public market data and paper execution.
- The worker iterates the selected symbols sequentially, fetches order books, generates diagnostics/signals, persists paper outcomes, and sleeps after the tick. The nominal one-second sleep is not a one-minute scheduler.
- `src/exchange/CoinbaseAdvancedClient.cpp` requests public Coinbase order books and reuses the client connection. Sequential request latency, retries, provider failures, signal/model work, and persistence can stretch an iteration.

Measured/known rates must be kept distinct:

- Current 403-symbol capture: 863 quote requests and 806 evaluations over an approximately 63-second active interval, but no retained per-tick/per-symbol timestamp series; no precise producer rate is claimed.
- Prior seven-symbol capture: 140 evaluations over roughly 43 seconds, with last-success timestamps advancing approximately every 1–2 seconds in sampled polls.
- Frontend producer-consumption configuration: approximately 3-second signal/stats polling and 5-second status polling.
- Source worker target: one-second sleep after each sequential-symbol tick; actual tick duration is data/provider dependent.

Classification: the one-minute appearance is confirmed not to be an intentional one-minute frontend interval. It is evidence-compatible with a combination of initial pending state, HTTP polling/display aggregation, failed WebSocket delivery, sequential exchange work, and diagnostic counter lag. The current evidence does not prove one exclusive causal mechanism and does not claim that changing polling would fix the behavior.

## Lead-by-lead disposition

### Coinbase TLS/network issue

Owner: exchange/runtime transport operator.

Status: separate open transport-reliability issue; not proven causal for the current zero-trade UI result. Historical pane evidence associated a YB-USD TLS/network failure with `2026-08-22T16:09:46Z` onward. In the prior seven-symbol window, all 7 symbols refreshed with zero failures. The current 403-symbol reproduction did encounter 167 quote failures out of 863 requests, but the capture did not provide a per-symbol mapping that ties those failures to the zero persisted-trade result or proves TLS as the dominant class. Required follow-up: collect a fresh symbol-level transport/error-category sample and correlate it with per-tick signal and persistence timestamps. No symbol blacklist or retry reduction was introduced.

### Transformer input/readiness issue

Owner: ML/trading runtime operator.

Status: the old “expected input dimension 0” lead is ruled out as a dimensionality blocker; Transformer warm-up is confirmed for the earlier seven-symbol no-trade window. Evidence reported sequences warming at 20/60 and feature width 353, not a usable zero-width input. The current 403-symbol capture reports aggregate ML-confidence blocking but does not prove exact model identity because the selected model ID was omitted from the request. Required follow-up: serialize/resolve the model ID and capture per-symbol readiness and model decision fields in a fresh run. No readiness gate was loosened.

### `is_closing_leg` schema mismatch

Owner: database/API deployment operator.

Status: confirmed historical reconciliation-completeness blocker; not established as a worker or order-generation blocker for the captured paper sessions. Historical `individual_trades.is_closing_leg` query failures occurred during `2026-08-22T15:51:55Z`–`16:08:38Z`. Source-side schema handling exists in the simulated/live service paths, but the deployed database schema and read-side behavior were not captured in the current runtime evidence. Required follow-up: verify deployed schema, migration/read query compatibility, and explicit partial/unavailable error handling. This issue must not be used to infer zero execution without a correlated session failure.

## Proven causes, ruled-out leads, and open blockers

Proven/observed:

- The current UI/session recorded zero persisted trades and zero trade rows during the observed 403-symbol interval.
- The worker was active: 806 signals were evaluated and 319 were generated according to stop diagnostics.
- `ml_confidence_below_threshold` was the largest recorded blocker bucket (173).
- Frontend configured polling is measured in seconds, not one minute.
- The selected 403-symbol universe remained represented in the request and coverage fields; no hidden cap was introduced.
- WebSocket delivery failed/closed before any message, so HTTP polling/diagnosis was the available evidence path.
- In the prior seven-symbol window, all quotes refreshed, Transformer warm-up was visible, and no paper intent/fill was created.

Ruled out or not supported as the claimed cause:

- A deliberate one-minute frontend polling interval.
- A universal “no signals were generated” explanation for the current session.
- Transformer input dimension zero as a confirmed runtime dimensional failure.
- Historical YB-USD TLS or `is_closing_leg` errors as proven causes of the current session without timestamped correlation.
- Any conclusion that increasing refresh frequency alone would fix trade generation.

Open blockers/evidence gaps:

- Current per-symbol freshness, error category, model readiness, signal, gate, intent, and fill rows for the 403-symbol session are not retained in the durable browser report.
- The selected Transformer model ID was omitted from the serialized start request.
- Runtime container Git SHA/image digest was not captured.
- The WebSocket close and visible counter discrepancies need a deployed route/broadcaster and cache reconciliation check.
- Deployed-schema verification for `is_closing_leg` remains outstanding.
- The terminal zero-trade invariant is reproduced at the UI persistence layer, but not as a universal claim about all backend sessions.

## Tests, artifacts, queries, and safe code changes

Artifacts and evidence used:

- `docs/reports/coinbase-paper-zero-trade-investigation-2026-09-19.md` from the prior exact-SHA report lineage.
- Browser evidence artifact from commit `3795276cb975fefc89508c1615d37b848629d168`, documenting the seven-symbol rendered flow.
- Current reproduction report/evidence from the 2026-09-21 browser harness and the upstream reproduction handoff.
- Prior per-symbol reconciliation and blocker artifacts from the upstream investigation tasks.
- Source inspection of `frontend/hooks/useTrading.ts`, `frontend/lib/api.ts`, `frontend/components/dashboard/SimulatedTradingPanel.tsx`, `src/api/PredictController.cpp`, `src/trading/SimulatedTradingService.cpp`, and `src/exchange/CoinbaseAdvancedClient.cpp`.

Tests/verification:

- No local C++ build, Docker build, or local test command was run, per the project remote-only policy.
- Prior upstream exact-SHA Docker Build Validation evidence was reviewed as provenance; this report itself is documentation-only and does not change application behavior.
- Non-build repository hygiene is verified with `git diff --check` before delivery.

Safe code changes in this task: none. No polling interval, retry policy, selected-universe handling, model gate, paper fill path, or live-order path was changed.

## Safety and accounting conclusion

The observed mode was `live_parity`: Coinbase public market data with local paper execution. No authenticated Coinbase order endpoint was enabled or called, no account mutation occurred, and both paper sessions were stopped cleanly. Fail-closed behavior remained intact: missing/invalid market data and unmet model/gate conditions did not become executable orders. The selected universe was preserved; no hidden cap, automatic Coinbase symbol blacklist, synthetic fallback, or replay/submission workaround was introduced.

Because no execution or signal behavior was changed, there is no before/after expectancy, average-win, average-loss, profit-factor, drawdown, or fee claim to make. The report deliberately does not claim that the investigation fixed the one-minute display or zero-trade behavior; it records what was reproduced, what was measured, what was ruled out, and the evidence still required for a causal fix.
