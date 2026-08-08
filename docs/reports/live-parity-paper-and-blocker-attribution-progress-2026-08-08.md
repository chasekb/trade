# Live-parity paper execution and blocker attribution

Date: 2026-08-08

Backlog items: `TRADE-BL-0006` and the live-parity portion of `TRADE-BL-0014`.

## Implemented contract

The Simulated Trading service accepts `execution_mode=live_parity` through `/api/trading/simulated/start`. In this mode:

- market data comes from Coinbase public order-book requests;
- missing or invalid quotes do not produce synthetic ticks;
- spot-only, minimum-notional, cash, position, pending-order, max-position, and ML/profitability checks are evaluated before a paper fill;
- fills settle in the simulated service and do not call Coinbase order submission;
- status and portfolio payloads identify `mode=live_parity`, `market_data_source=coinbase_public`, and paper execution;
- generated signal rows include `execution_analysis`, including the diagnostic factor, expected-return fields, allocation, blocker reason, and executable-intent flag;
- paper blocker counts are aggregated in the session status/portfolio payload.

Synthetic simulation remains separate. It retains its existing synthetic market behavior and does not label synthetic short-capable behavior as a live exchange blocker.

## Code paths

- `src/api/PredictController.cpp:1109-1131` validates and starts the requested simulated execution mode.
- `src/trading/SimulatedTradingService.cpp:760-790` fetches public Coinbase order books for live-data modes.
- `src/trading/SimulatedTradingService.cpp:1903-2039` selects the mode, constructs the public-data client, and starts the worker.
- `src/trading/SimulatedTradingService.cpp:458-575` serializes signal diagnostics.
- `src/trading/SimulatedTradingService.cpp:488-582` builds parity blocker attribution.
- `src/trading/SimulatedTradingService.cpp:1670-1715` applies parity analysis before paper fills and records blocked intents.
- `frontend/components/dashboard/SimulatedTradingPanel.tsx:537-674` exposes the explicit Synthetic versus Coinbase live-data paper selector and warning.
- `frontend/lib/api.ts:798-819` bypasses the local synthetic fallback when `execution_mode=live_parity`.

## Safety boundary

No Coinbase order is submitted by live-parity mode. The existing live execution path remains gated by `mode=live`, configured exchange credentials, and `live_order_execution=true`. No live account mutation or live-order test was performed.

## Verification scope

Allowed non-build verification for this change is `git diff --check`, the targeted frontend Jest test for `startTradingPayload`, TypeScript no-emit, and source-level contract inspection. Local Docker, CMake, C++, and production builds are intentionally not run. Remote Docker Build Validation for the pushed commit is required before backlog closure.

## Remaining closeout evidence

A complete runtime parity/attribution closeout still requires remote CI and, for the broader `TRADE-BL-0014` item, a representative runtime window proving reconciliation from generated signals to paper/live outcomes by strategy and blocker bucket. This report does not claim live profitability or deployment validation.
