# Live vs Simulated Signal and Execution Delta Reconciliation

Date: 2026-07-27
Scope: Trade project order-book signal and execution parity across Live Trading and Simulated Trading tabs.

## Evidence baseline

- Source branch before implementation: `dev`
- Source SHA before implementation: `d90f26a9f06ffb2583cf8eccc9ed1a5ee9f0c66a`
- Prior verified remote build: GitHub Actions `Docker Build Validation` run `30195476727`, conclusion `success`
- Runtime stack capture: `/tmp/trade_tmux_0_8_0_since_last_up_for_delta.log`
- Runtime stack marker: latest `TAG=dev podman-compose up --no-build`
- Running images observed:
  - `trade_cpp-backend_1 ghcr.io/chasekb/trade/cpp-backend:dev`
  - `trade_frontend_1 ghcr.io/chasekb/trade/frontend:dev`
  - `trade_db_1 docker.io/library/postgres:15-alpine`
  - `trade_redis_1 docker.io/library/redis:7-alpine`

Relevant runtime warnings from the tmux window:
- `data/cpp_assets/feature_params.json` was missing; backend used built-in fallback parameters.
- No usable ONNX models were loaded from `data/onnx`; backend used heuristic fallback signals.
- The capture window had no new `data_status` or `insufficient` signal-readiness warnings.

API/DB evidence window:
- `GET /health`: healthy.
- `GET /api/trading/live/status`: `status=stopped`, `is_active=false`, symbols included `BTC-USD`, `ETH-USD`, `SOL-USD`, `ADA-USD`, `DOT-USD`, `XRP-USD`, `LTC-USD`.
- `GET /api/orderbook/live-signals?per_page=10`: 7 rows, all recent rows were `hold`, `signal_generated=false`, `data_status=sufficient`, model `heuristic-fallback`.
- `GET /api/orderbook/simulated-signals?per_page=10`: 7 rows, several rows were generated `buy`/`sell`, `data_status=sufficient`, model `heuristic-fallback`, but lacked profitability-gate diagnostics before this implementation.
- DB query over recent `order_book_signals` rows showed only `data_status=sufficient` for `buy`, `sell`, and `hold` rows in the last 12 hours.

## Observed delta matrix

| Area | Live tab behavior | Simulated tab behavior before this implementation | Classification | Resolution |
| --- | --- | --- | --- | --- |
| Market data | Uses live Coinbase quote/order-book snapshots and can be inactive/stopped if live session is stopped. | Uses simulated market state unless live-mode quote path is active. | Expected data mismatch | Documented; comparison must record data source and timestamp. |
| ONNX/model state | No usable ONNX models; uses `heuristic-fallback`. | Same model manager path can fallback, but simulated fallback used a separate expected-return scale. | Contract mismatch | Simulated fallback now uses the same default/clamped heuristic edge scale as live. |
| Profitability gate | Generated order-book signals pass through `evaluateOrderBookProfitabilityGate`; failed edge/strength becomes `hold` with `data_status=sufficient` and gate diagnostics. | Generated order-book signals were not passed through the same fee/spread/slippage gate, so they could display/execute as buy/sell when live would downgrade them to HOLD. | Bug | Simulated order-book signals now use the same gate and emit the same diagnostic fields. |
| `data_status` semantics | Valid no-trade/profitability-gated HOLD rows are `sufficient`; warm-up/insufficient-history remains `insufficient`. | Valid order-book rows were already `sufficient` after prior fix. | Expected parity | Preserved. |
| Execution eligibility | Live additionally requires explicit live order execution, account snapshot/cash availability, no pending order, Coinbase minimum notional, and exchange submission success. | Simulated can fill against synthetic capital/session state without exchange submission. | Expected execution mismatch | Documented; report requires distinguishing generated-but-execution-blocked from no signal generated. |
| Frontend rendering | `OrderBookSignalsTable` renders `WAITING` only for insufficient data. | Same table is used for order-book signal rows. | Expected parity | Added test coverage for profitability-gated HOLD rows rendering as `HOLD`, not `WAITING`. |

## Implementation completed

1. Aligned simulated order-book signal generation with the live profitability contract.
   - File: `src/trading/SimulatedTradingService.cpp`
   - Added the same default order-book fee/slippage/min-strength constants used by live.
   - Added the same 2.4% heuristic fallback edge scale default used by live.
   - Added the same finite, clamped `orderbook_expected_return_scale_percent` override range, `0.0` to `5.0` percent.
   - Applied `evaluateOrderBookProfitabilityGate` to generated simulated order-book signals.
   - When the gate fails, simulated signals now become `hold`, keep `data_status=sufficient`, and carry `ml_analysis.fee_adjusted_expected_return`, `required_edge`, `profitability_gate_passed`, and `profitability_gate_reason`.

2. Aligned transformer-only ONNX expected-return semantics.
   - File: `src/trading/LiveTradingService.cpp`
   - Live and simulated producers now both use transformer expected PnL as `ml_analysis.expected_return` when no regressor is present.
   - This prevents transformer-only packs from producing actionable simulated signals while live silently gates the same model output to HOLD because expected return was forced to zero.

3. Strengthened shared gate regression coverage.
   - File: `src/tests/test_strategy_signal.cpp`
   - Added assertions that the shared order-book gate blocks weak signals and treats strong negative expected edge as an actionable sell.
   - Existing assertions already prove old 1.2% fallback scale fails the default hurdle while the 2.4% scale clears it for a strong buy fixture.

4. Added frontend rendering regression coverage.
   - File: `frontend/components/dashboard/__tests__/dashboard-tables.test.tsx`
   - Added a profitability-gated HOLD payload with `data_status=sufficient`.
   - Asserted it renders as `HOLD`, not `WAITING`, and still shows fee-adjusted/required-edge diagnostics.

5. Preserved the backlog recommendation as the durable execution criteria.
   - File: `.hermes/plans/2026-07-27_trade-live-simulated-signal-execution-delta-recommendation.md`

## Closeout evidence required after commit

This implementation is not closed until the following post-commit evidence exists:

- `dev` contains the implementation commit and `origin/dev` points to the same SHA.
- GitHub Actions workflow `Docker Build Validation` completes successfully for that exact pushed SHA.
- The final report references the successful run URL and head SHA.
- If runtime deployment is included in a follow-up, the fixed `dev` image is pulled/recreated, fresh live/simulated rows are generated, and the same API/DB queries show:
  - live and simulated order-book rows both include profitability-gate diagnostics for generated candidates,
  - valid HOLD rows remain `data_status=sufficient`,
  - generated simulated signals no longer bypass a gate that live applies.

## Follow-up backlog items

- Expose or document `orderbook_expected_return_scale_percent` in the order-book strategy UI/presets if operators are expected to tune it.
- Add a dedicated live execution-status field if the operator needs to distinguish `signal generated but blocked by live execution controls` without inspecting logs.
- Add fixture-level service tests that instantiate live/simulated producers directly once the project has a lightweight service-test harness that does not require a full local container build.
