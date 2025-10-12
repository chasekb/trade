# Transition to `dashboard_enhanced_modular` — Code Review TODOs

Scope: finalize functional transition from the monolithic `dashboard_enhanced` to the modular dashboard. Use this checklist during review and rollout.

## Phase 0 — Baseline & Routing
- [x] Confirm modular page loads at `/modular` and `/modular-dashboard` (`templates/dashboard_enhanced_modular.html` or `static/dashboard_enhanced_modular.html`).
- [x] Verify WebSocket endpoint `/ws` connects and emits expected payload shape consumed by `static/js/modules/RealTimeData.js`.
- [x] Ensure CDN assets (Plotly, Chart.js, Tailwind, FontAwesome) load without CSP or network errors.

## Phase 1 — API Parity (Server)
- [x] Add alias route: POST `/api/backtests/run` → call existing backtest run handler.
  - File: `src/trade_bot/web/web_server_new.py`
  - Acceptance: calling `/api/backtests/run` returns the same shape as POST `/api/backtest`.
- [x] Confirm these endpoints exist and return shapes expected by modules:
  - GET `/api/real-time-data` (used by `RealTimeData.js`)
  - GET `/api/historical-data` (fallback date handling present)
  - GET `/api/trading/metrics` (overview metrics)
  - GET `/api/products` (categories for symbol universe)
  - GET `/api/orderbook/live-signals` (signals + optional `pagination`)
  - GET `/api/trades/paginated` (history + `pagination`)
  - GET `/api/trading/live/positions` (positions + `pagination`)
  - GET `/api/simulated-trading/status`
  - POST `/api/trading/simulated/start`, POST `/api/trading/simulated/stop`

## Phase 2 — Template Cutover
- [x] Switch GET `/` to serve modular dashboard.
  - Option A: update `DashboardHandlers.get_dashboard` to render `dashboard_enhanced_modular.html`.
  - Option B: serve `static/dashboard_enhanced_modular.html` via `FileResponse` for performance.
- [x] Add legacy route (temporary): GET `/legacy` → `templates/dashboard_enhanced.html`.
- [x] Introduce feature flag `USE_MODULAR` (env) to toggle between templates during staged rollout.

## Phase 3 — Frontend Adjustments (if needed)
- [x] `DataManager.runBacktest`: ensure it hits POST `/api/backtests/run` (or keep `/api/backtest` if parity alias added).
  - File: `static/js/modules/DataManager.js`
- [x] Validate DOM IDs used by modules exist in `dashboard_enhanced_modular.html` (tabs, tables, buttons, charts).
- [x] Confirm pagination controls (`Pagination.js`) are wired to the correct IDs and endpoints.

## Phase 4 — Verification (Manual QA)
- [ ] Overview: price/volume update live; charts render; no console errors.
- [ ] Live Trading: start simulated session, signals load and paginate; stats refresh; stop works.
- [ ] Backtest: run with parameters; results + equity curve populate; metrics refresh.
- [ ] Sessions: navigation between tabs retains state; strategy config hide/show persists via localStorage.
- [ ] Performance: verify no long tasks > 200ms for core interactions; inspect `PerformanceMonitor` logs for slow API calls.

## Phase 5 — Rollout & Cleanup
- [ ] Default `/` cutover behind `USE_MODULAR=true`; monitor for 24–48h.
- [ ] Document switch in `docs/REFACTORING_SUMMARY.md` and project README.
- [ ] Deprecate legacy assets post-stabilization:
  - `static/js/dashboard_enhanced.js`
  - `templates/dashboard_enhanced.html`
  - Any dead CSS/JS not referenced by modular template

## Acceptance Criteria
- [ ] No 404s/500s from any module-initiated requests under normal use.
- [ ] No uncaught exceptions in browser console during standard flows.
- [ ] Backtest, live trading (simulated), signals, pagination, and metrics all functional.
- [ ] Page identifies as “Modular v2.0” in header and loads via GET `/`.

## Files Most Likely to Change
- `src/trade_bot/web/web_server_new.py` (routes, alias, template switch, flag)
- `src/trade_bot/web/web_handlers/dashboard_handlers.py` (template selection)
- `static/js/modules/DataManager.js` (optional backtest endpoint alignment)
- `templates/dashboard_enhanced_modular.html` (ensure required DOM targets exist)

## Review Notes
- Keep files < 500 LOC; split if approaching 400.
- Preserve SRP: orchestrator vs. modules; avoid re-introducing mixed concerns.
- Prefer `FileResponse` for static modular HTML unless server-side templating is required.


