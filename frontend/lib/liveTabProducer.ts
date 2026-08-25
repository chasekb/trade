type UnknownRecord = Record<string, unknown>;

export type LiveTabProducerSnapshot = {
  source: string;
  isActive: boolean;
  cashBalance: number;
  cashHold: number;
  totalPositionsValue: number;
  totalValue: number;
  holdings: UnknownRecord[];
  positions: UnknownRecord[];
  pendingOrders: UnknownRecord[];
  stats: UnknownRecord;
  credentialsConfigured: boolean;
  accountSnapshotLoaded: boolean;
  liveOrderExecutionEnabled: boolean;
  canTrade: boolean;
  blockers: string[];
  errors: string[];
  accountSnapshotAt?: string;
};

function asRecord(value: unknown): UnknownRecord {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as UnknownRecord)
    : {};
}

function asArray(value: unknown): UnknownRecord[] {
  return Array.isArray(value) ? (value.filter((item) => item && typeof item === 'object') as UnknownRecord[]) : [];
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
}

function asNumber(value: unknown, fallback = 0): number {
  const numeric = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(numeric) ? numeric : fallback;
}

function asBoolean(value: unknown, fallback = false): boolean {
  if (typeof value === 'boolean') return value;
  if (typeof value === 'string') return value.toLowerCase() === 'true';
  return fallback;
}

function livePositions(value: unknown): UnknownRecord[] {
  return asArray(value).filter((position) => position.reconciliation_status !== 'stale_internal');
}

export function normalizeLiveTabProducerSnapshot(input: unknown): LiveTabProducerSnapshot {
  const root = asRecord(input);
  const portfolio = asRecord(root.portfolio);
  const readiness = asRecord(root.readiness);

  const blockers = asStringArray(readiness.blockers);
  const errors = asStringArray(root.errors);

  const snapshot: LiveTabProducerSnapshot = {
    source: typeof root.source === 'string' ? root.source : 'coinbase',
    isActive: asBoolean(root.is_active ?? root.isActive ?? root.is_trading),
    cashBalance: asNumber(portfolio.cash_balance ?? root.cash_balance ?? root.available_balance_usd),
    cashHold: asNumber(portfolio.cash_hold ?? root.cash_hold),
    totalPositionsValue: asNumber(portfolio.total_positions_value ?? root.total_positions_value),
    totalValue: asNumber(portfolio.total_value ?? root.total_value ?? root.total_balance_usd),
    holdings: asArray(portfolio.holdings ?? root.holdings),
    // The latest server response is authoritative; stale internal rows must
    // not survive in the live exposure cache after reconciliation.
    positions: livePositions(root.positions ?? portfolio.positions),
    pendingOrders: asArray(root.pending_orders),
    stats: asRecord(root.stats),
    credentialsConfigured: asBoolean(root.credentials_configured ?? readiness.credentials_configured),
    accountSnapshotLoaded: asBoolean(root.account_snapshot_loaded ?? readiness.account_snapshot_loaded),
    liveOrderExecutionEnabled: asBoolean(root.live_order_execution_enabled ?? readiness.live_order_execution_enabled),
    canTrade: asBoolean(root.can_trade ?? readiness.can_trade),
    blockers,
    errors,
  };
  if (typeof root.account_snapshot_at === 'string') {
    snapshot.accountSnapshotAt = root.account_snapshot_at;
  }
  return snapshot;
}

export function firstLiveTabProducerBlocker(snapshot: LiveTabProducerSnapshot): string | null {
  return snapshot.blockers[0] ?? snapshot.errors[0] ?? null;
}
