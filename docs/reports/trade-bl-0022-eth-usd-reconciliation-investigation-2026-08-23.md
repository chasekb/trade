# TRADE-BL-0022: ETH-USD reconciliation investigation

Date: 2026-08-23
Scope: read-only repository investigation; no exchange orders, fills, liquidation, fabricated account state, local Docker build, or backend build/test was run.

## Executive finding

The captured ETH-USD row was not proven to be a phantom. Independent runtime captures reportedly agreed across the three live endpoints and frontend proxy: Coinbase returned inherited ETH dust (`available=8.4078200000000004e-09`, `hold=0`, approximately `$0.00002`), with an empty/stopped session, no pending order, zero managed quantity, and `reconciliation_status=coinbase_confirmed`. No live filled ETH order was found in the persistence inspection.

The proven defect class is stale internal position authority when a Coinbase account snapshot cannot be refreshed. `positions_` remains the serving read model while the exchange state is unknown. The same state split exists during intentionally bounded pending-settlement and managed-fill-floor reconciliation. A stale row can therefore be visible and included in local value/exposure metrics without a current Coinbase confirmation.

The smallest evidence-supported implementation boundary is not deleting ETH-USD, changing dust thresholds, merging frontend caches, or clearing accepted pending orders. The implementer should make unverified rows explicit and fail closed for live exposure/action/portfolio accounting after the bounded reconciliation authorization expires. A retained row must carry a verifiable accepted pending order or fill-derived authorization; otherwise it must not remain an unlabeled open live position.

## Reproduction / fixture status

No offline `LiveTradingService` fixture for an ETH-USD holding absent from a Coinbase snapshot was found in the inspected `src/tests` files. Existing tests cover Coinbase portfolio/order helpers and execution reconciliation, but not `applyLiveAccountSnapshotLocked`, snapshot-fetch failure, `positions_` retention, managed floor expiry, or the stop/restart lifecycle. The observed ETH row is runtime evidence of a Coinbase-confirmed inherited dust holding, not the absent-snapshot reproduction requested by the issue.

A safe deterministic reproduction for the implementer should use injected/fake snapshot and order state only:

1. Seed `positions_` with an ETH-USD position and a successful Coinbase snapshot that contains ETH.
2. Apply a subsequent successful snapshot with no ETH, with no `pending_order_symbols_`, no unexpired authorized fill/floor, and assert removal.
3. Separately force `fetchLiveAccountSnapshot` failure after the ETH-confirmed snapshot; assert the response reports snapshot error/staleness and does not expose the retained row as a current Coinbase holding or live-risk position.
4. Exercise accepted pending order and fill-authorized settlement cases and assert the row is retained only while the authorization is verifiable and bounded.

Do not use live credentials or mutate account state to reproduce this.

## Source-of-truth and transition map

| Path | Current behavior | Consequence |
| --- | --- | --- |
| `src/trading/LiveTradingService.cpp:1266-1297`, `fetchLiveAccountSnapshot` | `listAccounts` plus non-USD tickers builds a `CoinbasePortfolioSnapshot`; any account/ticker failure returns false. | A failed refresh has no replacement snapshot. |
| `:2374-2392`, worker refresh | Logs a failed account refresh and only calls `applyLiveAccountSnapshotLocked` when the fetch succeeded. | Prior `positions_`, `last_account_snapshot_`, and producer rows remain served. |
| `:1300-1407`, `applyLiveAccountSnapshotLocked` | Builds exact keys as `holding.asset + "-USD"`; successful snapshots erase absent positions unless `pending_order_symbols_` or an unexpired `managed_quantity_floors_` entry protects them. | Successful absence normally removes ETH immediately; protected settlement states intentionally retain it. No case/alias normalization exists. |
| `:567-605`, `positionToJson` | Emits `account_snapshot_present`, `account_snapshot_loaded`, snapshot time, pending flag, floor remaining, and `reconciliation_status` (`coinbase_confirmed`, `pending_settlement`, `awaiting_snapshot_reconciliation`, or `stale_internal`). | Backend has provenance labels, but an unverified row is still serialized as an open position. |
| `:1944-1988`, `updateMarkToMarketLocked` | Iterates every `positions_` row; unmanaged rows get zero unrealized PnL, while quantity/current price contributes to position value. | Retained stale quantity can affect local value/exposure and total value. |
| `:1991-2000`, `openPositionLocked` | Blocks an entry when `positions_` already contains the symbol or a pending symbol exists. | Stale rows can block a new entry; clearing them generically could permit duplicates. |
| `:2446-2507`, `buildPortfolioJson` | Iterates every `positions_` row into directional value, absolute exposure, total value, open count, and serialized positions. Cash is separate (`cash_` minus `pending_reserved_cash_`). | Stale/unverified rows affect local portfolio totals and exposure, not cash directly. |
| `:2658-2764`, `buildLiveTabProducerJson` | `status.positions` is built from `positions_`; `status.portfolio` is separately built from the last Coinbase snapshot. | Rows and Coinbase-authoritative totals can disagree during stale/floor states. Pending orders are emitted separately. |
| `:2930-2954`, `stopSession` | Stops trading but keeps `positions_`; accepted live orders continue settling. | Post-stop reads can retain rows until reconciliation/restart. |
| `:3018-3059`, direct reads/producer refresh | `getOpenPositions` and `getStatus` serialize `positions_` without refreshing. Producer refresh returns the old producer state plus error on fetch failure; on success it applies a replacement snapshot. | Direct endpoints can be temporally stale; successful producer replacement is authoritative for the Live Trading tab. |

Persistence recovery restores pending live orders/settlement state, not an independent authoritative position snapshot. It must not be treated as proof that an absent Coinbase holding exists.

## Endpoint and frontend contract

- `include/api/PredictController.hpp:34-40` and `src/api/PredictController.cpp:1269-1312,1368-1374` expose `/api/live-portfolio/status`, `/api/trading/live/positions`, and `/api/trading/live/status`.
- `/api/live-portfolio/status` calls `refreshLivePortfolioStatus()` -> `refreshLiveTabProducerStatus()`. On success it applies Coinbase state and serializes the producer; on failure it serves the prior in-memory producer state with errors/blockers.
- `/api/trading/live/positions` and `/api/trading/live/status` serialize `positions_` directly and do not independently refresh Coinbase.
- `frontend/hooks/useTrading.ts:464-478` uses React Query key `['live-tab-producer']`, 5-second stale time, 10-second polling, and window-focus refetch. `frontend/components/dashboard/LiveTradingPanel.tsx:288-365,503-516` renders `producer.positions` and uses producer portfolio totals. No optimistic position insertion, `setQueryData`, append, or cross-endpoint row merge was found.
- `frontend/lib/liveTabProducer.ts:48-77` replaces arrays from the current payload; it does not merge old positions. A successful newer response removes ETH from the client. However, `frontend/next.config.ts:125-131` applies public API caching (`max-age=300`, `s-maxage=600`, `stale-while-revalidate=86400`), which can serve an old whole response and requires runtime confirmation before changing.
- `frontend/components/dashboard/OpenPositionsSection.tsx:18-23,129-180` labels management state but does not display backend `reconciliation_status`; pending-settlement and stale-internal rows can appear as generic Coinbase/session rows. This is a labeling gap, not evidence that React Query preserves a row after a successful replacement.

## Downstream impact and invariants

- `positions_` stale quantity contributes to signed position value, absolute exposure, total value, open-position count, and potentially risk/entry gating.
- `cash_` is snapshot-derived and pending reserved cash is tracked separately; a stale row does not directly mutate cash.
- Unmanaged stale rows have zero unrealized PnL. Session-managed/floor-retained rows can contribute unrealized PnL.
- The observed inherited dust is Coinbase-confirmed and should not be deleted or hidden as an accounting correction. A true unverified row must not be marked `coinbase_confirmed`, used for live risk/exposure, or used to synthesize PnL, expectancy, equity, or account cash.
- Preserve accepted pending-order markers, duplicate guards, liquidation available-quantity/minimum-notional guards, exact symbol construction, snapshot timing, and fail-closed `can_trade` behavior.

## Minimal change recommendation for the implementer

1. Preserve the existing successful-snapshot removal and accepted-order/fill settlement safeguards.
2. Define the retained-row authorization explicitly: accepted pending order or verifiable fill-derived settlement state, bounded and persisted as appropriate. Do not use a generic stale row as authorization.
3. Ensure fetch-failure and post-stop retained rows are explicitly labeled with provenance/staleness and cannot be treated as current Coinbase exposure or eligible live action after authorization expiry. Keep Coinbase-authoritative portfolio totals separate from unverified local rows.
4. If the UI displays retained rows, surface `reconciliation_status`/snapshot error rather than rendering them as an unlabeled Coinbase holding. Do not change public HTTP caching without runtime evidence that it is the cause.

## Exact regression cases

Backend-focused coverage should include:

- successful ETH-present snapshot -> successful ETH-absent snapshot, no pending/floor: row is erased;
- failed account/ticker refresh after ETH-present snapshot: prior data is marked stale/error-bearing, not Coinbase-confirmed, and cannot affect eligible live exposure/action;
- accepted pending ETH order with an absent snapshot: row/order reservation remains through settlement, then clears only on verified fill or bounded terminal no-fill;
- zero-fill and complete-not-found expiry: no synthetic position is created and pending symbol is eventually removed;
- fill-derived managed floor: absent ETH is retained only for the documented bounded window, is labeled awaiting reconciliation, and expires without silently remaining open;
- exact `ETH-USD` key behavior and rejection of unsupported symbol case/alias normalization;
- stop with pending settlement and restart after settlement: accepted order recovery is preserved, while an unverified position is not resurrected as current Coinbase state;
- portfolio/accounting assertions: stale/unverified rows are excluded from live exposure/risk/position totals per the chosen contract, cash and pending reserves remain correct, and no synthetic PnL/expectancy is produced;
- API payload assertions for all three endpoints: provenance, snapshot timestamp/error, pending flag, floor/authorization, and consistent status semantics;
- frontend producer replacement: response A contains ETH+BTC, successful response B contains BTC only; ETH disappears, counts/totals follow B, and a late A cannot re-add ETH. Add a separate stale/error labeling test.

## Verification available without local builds

- `git diff --check` for whitespace hygiene.
- Static searches/inspection of the source paths above and CMake test registration in `CMakeLists.txt`.
- Remote CI is the permitted execution path for C++ compilation/tests and frontend tests. Relevant existing CTest targets include `execution_reconciliation`, `portfolio_accounting`, `coinbase_order`, and `coinbase_portfolio` (see `CMakeLists.txt`); frontend scripts are `npm test`, targeted Jest, `npm run lint`, and `npx tsc --noEmit` (see `frontend/package.json`). No such build/test command was run during this investigation, per task policy.

## Rejected unsupported fixes

- Delete the currently observed ETH dust: contradicted by Coinbase-confirmed evidence.
- Clear `positions_` on one failed refresh: risks losing accepted fills and does not distinguish unknown exchange state from confirmed absence.
- Remove all pending/floor retention: risks duplicate orders and premature loss of legitimate settlement state.
- Frontend cache invalidation or endpoint merge as the primary fix: no client merge/optimistic row source was found; public HTTP cache requires runtime evidence.
- Hide all dust or alter portfolio formulas: unsupported accounting/product change.
