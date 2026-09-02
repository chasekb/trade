# Dashboard warning cleanup closeout — 2026-08-04

Backlog item: `TRADE-BL-0003` — Clean dashboard warning debt without trading regressions.

## Scope

This slice removes warning-level frontend debt from the active live/simulated trading dashboard paths without changing trading behavior, API routes, or live order execution gates.

Changed files:

- `frontend/components/dashboard/LiveTradingPanel.tsx`
- `frontend/components/dashboard/SimulatedTradingPanel.tsx`
- `frontend/components/dashboard/OrderBookSignalsTable.tsx`
- `frontend/components/dashboard/StrategyConfigForm.tsx`
- `frontend/components/ui/DataTable.tsx`
- `frontend/hooks/useTrading.ts`
- `frontend/types/trading.ts`

## Implementation notes

- Removed dead dashboard imports and unused local row helper types.
- Removed unused order-book tooltip scaffolding that had no rendered `Tooltip` wrapper.
- Replaced a status-mirroring effect in `useLiveTrading` with a derived display status to avoid React hook warning debt while preserving local optimistic start/stop status fallback.
- Tightened `useTrading.ts` local payload/query-cache types enough to remove `any` usage from the touched hook paths.
- Documented existing intentionally opaque `any` fields in shared frontend type declarations with narrow per-field lint comments; no new runtime `any`-based behavior was introduced.
- Removed unused `DataTable` imports and narrowed its generic constraint from `Record<string, any>` to `object`.

## Verification performed

No local backend/Docker build was run.

Passed:

- `git diff --check`
- `cd frontend && npx eslint components/dashboard/LiveTradingPanel.tsx components/dashboard/SimulatedTradingPanel.tsx components/dashboard/OrderBookSignalsTable.tsx components/dashboard/StrategyConfigForm.tsx components/ui/DataTable.tsx hooks/useTrading.ts types/trading.ts`
- `cd frontend && npx tsc --noEmit`
- `cd frontend && npx jest components/dashboard/__tests__/dashboard-tables.test.tsx hooks/useTradingStrategyParameters.test.tsx --runInBand`

Known non-scope status:

- `cd frontend && npm run lint` still fails on unrelated pre-existing lint debt outside this slice, including `app/not-found.tsx`, chart components, websocket hooks, `lib/api.ts`, and other dashboard/analytics files. The targeted TRADE-BL-0003 files listed above pass with zero warnings/errors.

## Safety

This is frontend warning cleanup only. It does not change C++ backend strategy evaluation, exchange clients, account/position management, live order execution opt-in, duplicate order prevention, position caps, minimum notional checks, cash checks, or order submission logic.
