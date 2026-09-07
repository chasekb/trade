# Simulated Trading vs Live Trading tab gap review

Date: 2026-07-26
Project: trade
Backlog: 215

## Scope

Reviewed the Simulated Trading tab against the Live Trading tab for route usage, payload shape, polling/status semantics, controls, order-book signals, positions/trades, stats normalization, and error handling. No secrets or account-specific live trading data are included here.

## Gap matrix

| Surface | Simulated tab evidence | Live tab evidence | Finding | Action |
|---|---|---|---|---|
| Default strategy | `frontend/components/dashboard/SimulatedTradingPanel.tsx:582` defaults to `ml_enhanced_orderbook`. | `frontend/components/dashboard/LiveTradingPanel.tsx:606` defaults to `ml_enhanced_orderbook`. | Same default strategy, so shared strategy controls must cover ML-enhanced order-book in both tabs. | Fixed by exposing order-book controls for `ml_enhanced_orderbook` in `frontend/hooks/useTrading.ts`. |
| Start payload | Simulated builds `{ mode: 'simulated', strategy, symbols, parameters: { ...config }, max_positions }` at `frontend/components/dashboard/SimulatedTradingPanel.tsx:630`. | Live filters synthetic capital fields and sends `mode: 'live'` at `frontend/components/dashboard/LiveTradingPanel.tsx:662`. | Payload shape is intentionally different for live capital safety, but both depend on `max_positions_per_session` flowing into `max_positions`. | Covered by `frontend/lib/startTradingPayload.test.ts`. |
| Order-book risk controls | Simulated uses `TradingConfiguration` and `StrategyConfigForm` at `frontend/components/dashboard/SimulatedTradingPanel.tsx:697`. | Live uses the same `TradingConfiguration` at `frontend/components/dashboard/LiveTradingPanel.tsx:730`. | Shared form was the right fix point; controls should not be forked per tab. | Fixed in shared `StrategyConfigForm` and `useStrategyParameters`. |
| Preset behavior | Presets previously rendered only for `orderbook` in `frontend/components/dashboard/StrategyConfigForm.tsx:251`. | Live ML-enhanced default had no preset path despite using order-book controls. | Silent no-op risk when users expected order-book presets to apply to the default ML-enhanced strategy. | Fixed: presets now apply to `orderbook` and `ml_enhanced_orderbook`; unsupported preset attempts surface feedback. |
| Start failures | Simulated stores and renders `actionError` at `frontend/components/dashboard/SimulatedTradingPanel.tsx:607` and `:729`. | Live logs start errors at `frontend/components/dashboard/LiveTradingPanel.tsx:690` without a visible error banner. | Simulated tab already fails louder than live. Live could adopt the same action-error surface later. | Follow-up backlog recommended if desired; not bundled here because item 214/216 are implementation scope. |
| Order-book signals | Simulated passes mode `'simulated'` into `useOrderBookSignals` at `frontend/components/dashboard/SimulatedTradingPanel.tsx:598`. | Live passes the active strategy without mode override at `frontend/components/dashboard/LiveTradingPanel.tsx:632`. | Route usage is intentionally split by mode; shared table rendering prevents format drift. | No action. |
| Local fallback simulation | `frontend/lib/api.ts:208` processes local synthetic signals when `NEXT_PUBLIC_FORCE_LOCAL_SIM_TRADING` is enabled. | Live has no local paper fallback; it must require Coinbase account readiness. | Correct separation: simulated can run synthetic/local, live must validate producer/account state. | No action. |
| Profitability/minimum size policy | Local simulated fallback opened every generated signal up to cap in `frontend/lib/api.ts:208`; backend simulated sizing uses `SimulatedTradingService::positionSizeUsdForSignal`. | Live backend sizing already uses `PositionSizingPolicy` and live/cohort feedback. | Simulated needed expected-return profitability gating to avoid unprofitable tiny trades. | Fixed by adding shared minimum-trade-size policy in C++ and local fallback TS. |

## Follow-up recommendations

1. Add a visible live-tab action error banner matching the simulated tab if live start/stop mutations fail. This is a UX consistency issue, not required for safe simulated trading.
2. Consider extracting the common start-payload construction used by `LiveTradingPanel` and `SimulatedTradingPanel` into `frontend/lib/api.ts` once the current tab-specific capital handling has more tests.
3. Add an operator-facing training-artifact viewer for walk-forward folds, feature importance, and cohort metrics after backend metadata is accumulated across several training runs.

## Verification hooks added

- `frontend/hooks/useTradingStrategyParameters.test.tsx` verifies ML-enhanced order-book controls and presets.
- `frontend/lib/startTradingPayload.test.ts` verifies ML-enhanced order-book caps and risk thresholds reach the start payload.
- `frontend/lib/apiSizing.test.ts` verifies simulated expected-return profitability gates.
- `src/tests/test_training_validation.cpp` verifies chronological walk-forward folds and feature importance artifacts.
- `src/tests/test_position_sizing_policy.cpp` verifies profitability, fee/slippage/spread, cap, and override decisions.
