# TRADE-BL-0022 — Minimal evidence-backed reconciliation fix design

Status: implementation-ready design; no production code change proposed in this task.
Evidence inputs: `trade-bl-0022-final-evidence-2026-08-23.md` at commit `a130828a7533b7e3c07d6a36c75ea54a9251d17c2`, plus the parent state-transition trace.

## Evidence boundary and decision

The captured ETH-USD row is a real Coinbase-confirmed inherited dust holding (`8.4078200000000004e-09` ETH), not a frontend-only row, simulated/session state, pending settlement, or persisted filled live trade. Therefore this design does not delete Coinbase holdings, infer historical origin, or change account-management eligibility. The fix targets the separately reproduced failure mode in which an internal position survives a successful account snapshot without current account, accepted-pending-order, or fill evidence.

The Coinbase account snapshot is authoritative for live holdings and producer portfolio totals. `positions_` is an internal/rendering collection, not independent proof of exposure. A refresh error is not an empty account and must never be converted into an invented zero snapshot.

## Canonical reconciliation state

Implement one reconciliation decision per symbol and reuse it in `positionToJson`, portfolio totals, mark-to-market/P&L, risk gating, `/api/live-portfolio/status`, `/api/trading/live/positions`, and `/api/trading/live/status`. The product identity must use the existing canonical asset-to-product helper (`coinbaseProductIdForAsset`); do not compare ad-hoc `asset + "-USD"` strings in one consumer and normalized symbols in another.

For each internal position, compute these inputs from the same locked state:

- `account_snapshot_present`: true only when a successful snapshot contains the canonical symbol.
- `account_snapshot_loaded`: whether any successful snapshot has ever been applied.
- `pending_order_present`: true only for a verifiable accepted live order for this symbol: non-empty exchange `order_id`, not canceled/rejected, not fully fill-applied. Do not derive this from `pending_order_symbols_` alone.
- `managed_quantity_floor_remaining`: the remaining quantity floor, or zero if no floor exists.
- `last_seen_in_account_snapshot_at`: timestamp of the most recent successful snapshot containing this symbol; retain it after later refresh failures.
- `last_fill_order_id`: the exchange order ID of the latest verified fill applied to this position, if any.
- `snapshot_refresh_ok` and `snapshot_refresh_error`: current refresh outcome, separate from cached snapshot contents.

The reconciliation state machine is:

| State | Required evidence | Row label | Exposure/totals/risk |
|---|---|---|---|
| `coinbase_confirmed` | Current successful snapshot contains the symbol | Live Coinbase exposure | Included, subject to normal side/quantity rules |
| `pending_settlement` | No current snapshot holding, but accepted pending order exists | Pending settlement | Excluded from confirmed position totals and risk metrics; represented in explicit pending/reserved fields exactly once |
| `awaiting_snapshot_reconciliation` | No current holding; a positive managed floor remains from a verified accepted order/fill and its bounded grace has not expired | Awaiting Coinbase reconciliation | A verified fill may contribute its bounded managed floor to position value, but not to fresh-entry/liquidation risk decisions |
| `stale_account_snapshot` | Refresh failed after a prior successful snapshot | Coinbase snapshot stale | Display last-known data with a stale label; disable destructive actions and risk decisions. Do not create or remove exposure from the failed refresh |
| `unverified_missing_from_snapshot` | Successful snapshot does not contain the symbol and no pending/floor/fill evidence remains | Internal/unverified state | Excluded from position value, P&L, totals, counts, and risk metrics; remove from the live exposure collection after reconciliation |
| `unverified_no_snapshot` | No successful snapshot is available and no pending/fill/floor evidence exists | Coinbase state unavailable | Excluded from exposure and risk; retain only diagnostic state, never invent an account holding |

A verified fill is evidence only when tied to a non-empty exchange order ID and an accepted/persisted fill or an exchange-confirmed fill response. A historical rejected order, a simulated trade, a client order ID without exchange acceptance, or a symbol-only pending flag cannot retain live exposure.

## Exact transition and timing rules

1. On a successful snapshot, atomically replace the authoritative account snapshot and timestamp. For every holding, update/create the Coinbase row using the canonical symbol.
2. For an internal symbol absent from that successful snapshot:
   - keep it only if `hasAcceptedPendingOrderLocked(symbol)` is true, or if a positive managed floor has verified order/fill provenance and remaining grace;
   - otherwise erase the internal live position immediately and clear any zero/unproven floor.
3. The grace counter is bounded by the existing maximum of 30 successful snapshot reconciliations. It decrements only after a successful snapshot, never on a failed request, timer tick, or frontend poll. It must be attached to the specific accepted order/fill provenance, not merely to a symbol.
4. A successful snapshot containing quantity at least the verified floor clears the floor and resolves to `coinbase_confirmed`. A lower quantity updates the managed quantity to the observed quantity and retains only the still-verified remainder; never increase quantity from the internal row.
5. An accepted pending order keeps `pending_settlement` while it has a non-empty exchange order ID and is not fill-applied. On a fill, record `last_fill_order_id`, apply the fill exactly once by exchange order ID, and transition to `coinbase_confirmed` when the next successful snapshot observes the balance; until then use `awaiting_snapshot_reconciliation` with the verified floor.
6. When an order is rejected, canceled, or proven fully applied, remove its pending evidence. If no current snapshot, verified fill, or remaining floor exists, transition to `unverified_missing_from_snapshot` and exclude/remove the row.
7. On a refresh failure, preserve the last successful snapshot and `last_seen_in_account_snapshot_at`, set a diagnostic error and stale age, and do not call snapshot-application/removal logic. A stale cached row is never evidence for a new order, liquidation, or strategy risk decision. After a bounded stale-display TTL, hide it from live exposure while retaining the diagnostic record; the TTL is a display safety bound, not a reconciliation grace that invents state.
8. Snapshot application, pending-order/fill updates, floor updates, and position removal must be atomic under the service mutex. The same reconciled result must feed every endpoint in the request cycle; no endpoint may independently merge cached positions.

## API and diagnostics contract

Every live position row and the producer envelope should carry the following fields with stable types:

- `source`: `coinbase`, `pending_order`, `managed_fill`, or `internal_unverified`.
- `account_snapshot_present`: boolean.
- `account_snapshot_loaded`: boolean.
- `account_snapshot_at`: latest successful snapshot timestamp, if any.
- `last_seen_in_account_snapshot_at`: latest timestamp at which this symbol was present, if any.
- `pending_order_present`: boolean based on accepted order evidence.
- `managed_quantity_floor_remaining`: finite non-negative number.
- `last_fill_order_id`: string or empty (never synthesize an ID).
- `reconciliation_status`: one of the state-machine values above.
- `reconciliation_reason`: stable reason code such as `snapshot_contains_holding`, `accepted_order_not_settled`, `verified_fill_awaiting_snapshot`, `snapshot_missing_after_grace`, `snapshot_refresh_failed`, or `no_snapshot_evidence`.
- `snapshot_refresh_ok`, `snapshot_refresh_error`, and `snapshot_stale_seconds`.
- `contributes_to_exposure`: explicit backend boolean used by all totals/risk code.

`/api/live-portfolio/status` should be the canonical producer. The two trading status endpoints must serialize the same reconciled rows and diagnostic fields, rather than exposing a second interpretation of `positions_`. Frontend normalization should consume this contract without merging rows from a second source or using React Query cache invalidation as reconciliation.

## Frontend labels and metrics

Use visibly distinct labels:

- `Live Coinbase exposure` for `coinbase_confirmed`.
- `Pending settlement — awaiting Coinbase` for `pending_settlement`.
- `Awaiting Coinbase reconciliation` for a verified fill/floor not yet present in the snapshot.
- `Stale Coinbase snapshot — trading actions disabled` for refresh failure.
- `Internal/unverified — excluded from exposure` for either unverified state.

The frontend must not imply that a pending or stale row is a confirmed Coinbase balance. It must disable close/liquidate controls unless the backend also authorizes that action for the current state. Display diagnostics and last-seen time separately from portfolio totals.

Backend totals, mark-to-market, unrealized P&L, open-position counts, and risk gates must iterate only rows with `contributes_to_exposure=true`. Synthetic, simulated, absent, unverified, and pending-without-fill rows must contribute zero to confirmed position exposure. Pending reservations may affect available cash exactly once, but must not also be counted as confirmed account quantity. A verified fill may contribute only its bounded managed floor while awaiting the snapshot, and must additionally be marked ineligible for new risk actions. `coinbase_unmanaged`/inherited eligibility remains a management label and must not be used as proof of session ownership.

## Regression scenarios and acceptance checks

1. Fresh snapshot contains inherited ETH dust: one Coinbase row, `coinbase_confirmed`, correct account value, no session trade/P&L fabrication.
2. Fresh snapshot omits an internal ETH row with no pending order, fill, or positive verified floor: row becomes unverified/excluded and is removed from live exposure immediately.
3. A symbol-only pending flag or rejected historical order exists: it does not retain exposure or report `pending_settlement`.
4. Accepted order has an exchange order ID but no snapshot fill yet: row is `pending_settlement`; reservation appears once; no duplicate order can be submitted.
5. Accepted order receives a verified fill: fill is applied once by order ID, floor is retained only until snapshot reconciliation, and no liquidation is triggered by temporary absence.
6. Thirty successful snapshots omit the symbol after verified floor creation: grace expires, row becomes unverified/excluded, floor is cleared, and no nonexistent exposure is liquidated.
7. Coinbase refresh fails after a known holding: prior snapshot is retained and labeled stale; no row is falsely deleted, no new exposure is invented, destructive/risk actions are blocked, and stale-display expiry is bounded.
8. All three live endpoints and the frontend proxy return the same symbol identity, status, diagnostics, and exposure totals for each scenario.
9. Repeated snapshot application is idempotent: no duplicate positions, pending reservations, fills, or totals.
10. Existing simulated positions remain on simulated paths and cannot enter live totals or live order recovery.

## Safety invariants

- Never submit duplicate orders for a symbol/order intent already represented by an accepted pending exchange order.
- Never liquidate or otherwise act on exposure that is absent from Coinbase and lacks accepted pending or verified fill/floor evidence.
- Never discard an accepted pending order solely because a snapshot temporarily omits its fill; retain it through the bounded settlement path.
- Never invent account state from a failed request, stale internal position, client-only order ID, rejected order, or simulated record.
- Coinbase-confirmed account quantity remains authoritative; internal state may not increase it.
- A position can affect totals/risk only through the single reconciled `contributes_to_exposure` decision.
- Account-management eligibility and inherited provenance remain separate from session ownership and must not fabricate strategy P&L.
- All refresh/reconciliation transitions are fail-closed and observable through stable diagnostics.

## Implementation scope and verification gate

Expected implementation surface in the C++ live service and its tests: the shared reconciliation helper/state type, snapshot application/removal, pending-order recovery/fill handling, mark-to-market and portfolio aggregation, all live serializers/routes, and frontend row normalization/labels. Do not change exchange behavior, account holdings, selected universes, or live execution enablement as part of this fix.

Before implementation closeout, add focused unit/regression coverage for every scenario above, run the project’s prescribed test/build workflow remotely, and verify the exact pushed SHA’s required CI jobs. This design itself was produced from read-only evidence; no live calls, orders, session mutations, local builds, or local tests were performed.
