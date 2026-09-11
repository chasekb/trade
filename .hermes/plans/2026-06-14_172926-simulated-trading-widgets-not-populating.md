# Fix Simulated Trading Widgets Not Populating After Start Trading

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Make the simulated trading statistics and order book signals widgets populate immediately and reliably after the user presses Start Trading on the Simulated Trading tab.

**Architecture:** The simulated trading tab should treat the Start Trading event as a state transition that immediately refreshes the trading-status, simulated-statistics, and order-book-signals data paths. The UI must not depend on a later polling cycle or WebSocket arrival before showing meaningful content. Backend and frontend contracts should be verified together so the widgets can render both initial data and live updates, with visible loading and error states when data is unavailable.

**Tech Stack:** Next.js frontend, React Query, simulated trading API endpoints, WebSocket signal stream, C++ backend service.

---

## Problem Statement

On the Simulated Trading tab, pressing Start Trading does not reliably populate two user-visible widgets:

- Trading statistics dashboard
- Order book signals table

The failure appears silent from the user’s point of view: the tab can transition to active trading while the widgets remain empty or stuck in their initial state.

## Recommendation Summary

Prioritize a fix that makes the start-trading action immediately invalidate and refetch the simulated trading data queries, and ensure the widgets have explicit loading/error/empty states so they cannot appear broken without feedback. Confirm the backend returns the fields the frontend expects for simulated status, statistics, and signal pagination, and that the WebSocket/live cache path can seed the widgets before the first live tick arrives.

## Likely Scope

Primary files to review and probably change:

- `frontend/components/dashboard/SimulatedTradingPanel.tsx`
- `frontend/hooks/useTrading.ts`
- `frontend/lib/api.ts`
- `frontend/components/dashboard/TradingStatisticsDashboard.tsx`
- `frontend/components/dashboard/OrderBookSignalsTable.tsx`
- `src/trading/SimulatedTradingService.cpp`
- `src/api/PredictController.cpp`

## Execution Checklist

### Discovery
- [ ] Reproduce the issue on the Simulated Trading tab with browser devtools open.
- [ ] Capture the exact network requests made when Start Trading is pressed.
- [ ] Confirm whether `getSimulatedTradingStatus`, `getOrderBookSignals`, and the WebSocket stream all return data after activation.
- [ ] Verify whether the statistics widget is reading from `/api/trades/stats`, `/api/simulated-trading/status`, or a mixed response shape.
- [ ] Check whether the order book signals query is disabled, cached, or waiting on symbols/status to synchronize.
- [ ] Inspect console logs for silent failures, rejected promises, or query-key mismatches.

### Frontend implementation
- [ ] Make Start Trading trigger immediate invalidation/refetch of the simulated trading status, simulated statistics, and order book signal queries.
- [ ] Ensure the simulated trading tab passes a stable active-symbol list into the signals query as soon as trading starts.
- [ ] Add or tighten empty/loading/error states so the widgets visibly explain why they are not yet populated.
- [ ] Keep the WebSocket hook as a live-update source, but do not rely on it as the only initial data source.
- [ ] Align query keys and invalidation keys so the start-trading mutation refreshes the same caches the widgets consume.

### Backend / contract verification
- [ ] Confirm the simulated trading status endpoint includes the fields the frontend uses to derive active state, strategy, symbols, and portfolio data.
- [ ] Confirm the order book signals endpoint returns pagination metadata and summary fields even when the signal set is initially small.
- [ ] Verify the signal delivery path respects the 100-symbol request cap and still returns a deterministic first page.
- [ ] Check that the backend seeds simulated stats quickly enough for the dashboard to render non-empty state after start.

### Testing and verification
- [ ] Add or update frontend tests for the start-trading flow to assert the widgets refetch immediately.
- [ ] Add a regression test for the order book signals widget showing data after simulated trading starts.
- [ ] Add a regression test for the statistics widget showing active or loading state instead of remaining blank.
- [ ] Run the frontend test suite covering the affected dashboard components.
- [ ] Run the relevant backend tests or targeted service checks for simulated trading status and signal generation.
- [ ] Validate the full flow in the browser: Start Trading -> active banner -> statistics render -> signals render -> live updates continue.

## Parallel Workstreams

### Lane A: Frontend state flow
- Instrument the simulated trading start mutation.
- Fix cache invalidation and refetch timing.
- Add visible loading/error/empty states.

### Lane B: Backend contract and data seeding
- Confirm status, stats, and signals response shapes.
- Verify pagination and first-page content.
- Ensure the backend has enough initial data to avoid a blank UI.

### Lane C: End-to-end QA
- Reproduce the issue before the fix.
- Verify the widgets populate after the fix.
- Check tab switching, refresh behavior, and WebSocket recovery.

## Closeout Criteria

### User-visible behavior
- [ ] Pressing Start Trading on the Simulated Trading tab causes the active state to appear immediately.
- [ ] The statistics widget shows populated values or a clear loading state within a single refresh cycle.
- [ ] The order book signals widget shows at least one populated page or a clear empty-state message if no signals exist yet.
- [ ] The UI does not stay blank or appear stuck after trading starts.
- [ ] Switching tabs or reloading the page does not lose the active simulated trading state unexpectedly.

### Technical acceptance
- [ ] The simulated trading start action invalidates the exact query keys used by the statistics and signals widgets.
- [ ] The widgets render correctly from both initial API data and subsequent WebSocket-driven updates.
- [ ] The backend/frontend response contract is documented or verified in code comments/tests.
- [ ] The fix has a regression test for the silent-population failure.

### Verification evidence
- [ ] Screenshot or browser recording of the active simulated trading tab with both widgets populated.
- [ ] Network log showing the refetches after Start Trading.
- [ ] Test output confirming the affected frontend/backend tests pass.

## Notes

- Keep the fix focused on the start-trading activation path; do not broaden scope into unrelated dashboard cleanup.
- If a contract mismatch is discovered, treat it as the root issue rather than papering over it with additional polling.
- If data is legitimately absent, prefer a visible empty state over an apparently broken widget.

## Tags

`trade`, `simulated-trading`, `frontend`, `backend`, `react-query`, `websocket`, `dashboard`, `bugfix`
