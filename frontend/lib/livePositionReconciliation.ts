// Mirrors the `reconciliation_status` values produced by
// `livePositionReconciliationStatus()` in
// src/trading/LivePositionReconciliation.cpp. The backend already excludes
// the two `unverified_*` states from exposure/PnL math via
// `livePositionContributesToExposure()`; this module lets the frontend apply
// the same exclusion to displayed counts and gate destructive actions on
// positions Coinbase hasn't confirmed exist.
export type LivePositionReconciliationStatus =
  | 'coinbase_confirmed'
  | 'pending_settlement'
  | 'awaiting_snapshot_reconciliation'
  | 'unverified_missing_from_snapshot'
  | 'unverified_no_snapshot';

const UNVERIFIED_STATUSES = new Set<string>([
  'unverified_missing_from_snapshot',
  'unverified_no_snapshot',
]);

export function isUnverifiedReconciliationStatus(status?: string | null): boolean {
  return Boolean(status) && UNVERIFIED_STATUSES.has(status as string);
}

const RECONCILIATION_STATUS_LABELS: Record<string, string> = {
  pending_settlement: 'Pending settlement',
  awaiting_snapshot_reconciliation: 'Awaiting Coinbase snapshot',
  unverified_missing_from_snapshot: 'Reconciliation pending',
  unverified_no_snapshot: 'Reconciliation pending',
};

export function reconciliationStatusLabel(status?: string | null): string | null {
  if (!status) return null;
  return RECONCILIATION_STATUS_LABELS[status] ?? null;
}
