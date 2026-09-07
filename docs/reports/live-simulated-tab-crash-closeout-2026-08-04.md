# Live and Simulated tab crash isolation closeout — 2026-08-04

Backlog item: `TRADE-BL-0019` — Investigate silent Live and Simulated Trading tab crashes.

## Reproduction and classification

The backlog evidence identified a render-time crash class: `frontend/components/ErrorBoundary.tsx` existed, but the dashboard shell did not mount it around tab content. A render exception inside `LiveTradingPanel` or `SimulatedTradingPanel` could therefore escape the active tab panel and blank/crash the dashboard without a tab-local actionable error state.

Confirmed wiring before the fix:

- `frontend/app/layout.tsx` wrapped children in `QueryProvider` and `ConsoleLogProvider`, but not `ErrorBoundary`.
- `frontend/app/page.tsx` rendered `LiveTradingPanel` and `SimulatedTradingPanel` directly inside `renderTabContent()`.
- `frontend/app/page.tsx` owned `activeTab` in local state, so a full page reload after an escaped crash would reset the user to `overview`.

Failure type classification: render-time component exception. This slice does not claim to fix malformed data, React Query, network, `window.onerror`, or unhandled promise failures unless they surface as render exceptions inside the tab subtree.

## Root cause

Root cause: the reusable `ErrorBoundary` was present but not mounted at the tab-panel seam where Live Trading and Simulated Trading render. Because there was no panel-local boundary, a render exception in either tab had no visible tab-level fallback and could unmount more of the dashboard than necessary.

Traced files/functions:

- `frontend/app/page.tsx`: `renderTabContent()` selected tab components directly.
- `frontend/components/ErrorBoundary.tsx`: existing class boundary catches render/lifecycle errors and exposes a retry callback, but previously was not used by the dashboard shell.

## Implemented fix

- Added a tab-local `ErrorBoundary` around active tab content in `frontend/app/page.tsx`.
- Added a `TabErrorFallback` with a visible `role="alert"`, tab-specific title, diagnostic message, retry button, and guidance that other dashboard tabs remain available.
- Keyed the boundary by `activeTab` so switching tabs clears a failed panel state without reloading the page.
- Removed the footer render-time `new Date()` value and replaced it with static text to avoid client/server hydration drift noise while testing dashboard crashes.
- Kept the existing global/default `ErrorBoundary` behavior intact and only fixed lint issues in `ErrorBoundary.tsx` / `ConsoleLogProvider.tsx` encountered by the targeted verification command.

## Safety scope

This is frontend error-isolation work only. It does not change:

- C++ backend code.
- Coinbase exchange client behavior.
- live order execution enablement.
- start/stop trading mutation semantics.
- pending-order, maximum-position, minimum-notional, cash, profitability, or account-position-management gates.
- any automatic live-trading restart, order submission, liquidation, or mutation replay behavior.

No state restoration contract was added because the reproduced/root-cause class is missing render-error isolation, not proven safe UI-state restoration. The fix keeps other tabs usable after a panel render exception and requires explicit user action to retry the failed tab.

## Verification

Local non-backend/non-Docker checks:

- `npx jest app/page.test.tsx --runInBand` passed.
- `npx eslint app/page.tsx app/page.test.tsx components/ErrorBoundary.tsx components/providers/ConsoleLogProvider.tsx` passed.
- `npx tsc --noEmit` passed.
- `git diff --check` passed.

Browser smoke with Next dev server on port 3010:

- Opened `http://localhost:3010/` in a browser.
- Switched to the Live Trading tab and saw the Live Trading configuration/control UI render.
- Switched to the Simulated Trading tab and saw the Simulated Trading configuration/control UI render.
- Browser console had zero console messages and zero JavaScript errors after the tab smoke path.

Regression tests:

- `frontend/app/page.test.tsx` injects a render exception from mocked `LiveTradingPanel` and verifies a visible "Live Trading tab failed to render" alert with the diagnostic message, then switches to Simulated Trading and confirms the dashboard remains usable.
- The same test injects a render exception from mocked `SimulatedTradingPanel`, verifies the visible tab-level alert, then switches to Live Trading and confirms the dashboard remains usable.

Remote closeout gate:

- This item remains open until the implementation commit is pushed and exact pushed-SHA GitHub Actions Docker Build Validation succeeds.
