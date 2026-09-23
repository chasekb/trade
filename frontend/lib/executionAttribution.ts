// Normalization for `/api/trading/execution-attribution`.
//
// The backend attributes evaluated signals and their realized outcomes
// across strategy, symbol, side, strength, and expected-return dimensions,
// plus the diagnostic factors that explain blocked intents. This is a
// `report`-classified diagnostic (docs/STRATEGY_OBJECTIVE.md's diagnostics
// factoring contract): it never gates, sizes, or affects execution.
//
// Backend unit conventions preserved here: `win_rate_pct` is already a
// 0-100 percentage and is never scaled again. Missing outcome evidence
// serializes as `null`, not `0`, and is normalized to `null` here too so a
// real zero is never confused with an absence of data.
//
// This is intentionally a separate normalization layer from
// `lib/executionReconciliation.ts` (blocker-mix reconciliation by strategy
// and symbol only): the two features do not share a hook, endpoint, or
// aggregation shape.

export interface AttributionDimensionRow {
  evaluated: number;
  blockedIntents: number;
  explicitSkips: number;
  executableIntents: number;
  executedCount: number;
  pnlPopulation: number;
  winCount: number;
  lossCount: number;
  winRatePct: number | null;
  averageRealizedPnl: number | null;
}

export interface AttributionRow {
  key: string;
  evaluated: number;
  signalsGenerated: number;
  explicitSkips: number;
  executableIntents: number;
  blockedIntents: number;
  executedCount: number;
  pnlPopulation: number;
  winCount: number;
  lossCount: number;
  winRatePct: number | null;
  averageRealizedPnl: number | null;
  averageWinPnl: number | null;
  averageLossMagnitude: number | null;
  outcomeCoverage: number | null;
  insufficientData: boolean;
  blockerCounts: Record<string, number>;
  diagnosticFactorCounts: Record<string, number>;
  dimensions: Record<string, Record<string, AttributionDimensionRow>>;
}

export interface ExecutionAttributionReport {
  contractVersion: number;
  windowHours: number;
  sessionId: string;
  tradeType: string;
  coverageComplete: boolean;
  signalRows: number;
  outcomeRows: number;
  signalRowsTruncated: boolean;
  bucketPolicyVersion: string;
  warning: string | null;
  byStrategy: AttributionRow[];
  byDiagnosticFactor: AttributionRow[];
  overall: AttributionRow;
}

const toNumber = (value: unknown, fallback = 0): number => {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
};

const toNullableNumber = (value: unknown): number | null =>
  typeof value === 'number' && Number.isFinite(value) ? value : null;

const toBool = (value: unknown, fallback = false): boolean =>
  typeof value === 'boolean' ? value : fallback;

const toStr = (value: unknown, fallback = ''): string =>
  typeof value === 'string' ? value : fallback;

const toCountRecord = (value: unknown): Record<string, number> => {
  if (!value || typeof value !== 'object') return {};
  const out: Record<string, number> = {};
  for (const [key, count] of Object.entries(value as Record<string, unknown>)) {
    out[key] = toNumber(count);
  }
  return out;
};

export const emptyAttributionDimensionRow = (): AttributionDimensionRow => ({
  evaluated: 0,
  blockedIntents: 0,
  explicitSkips: 0,
  executableIntents: 0,
  executedCount: 0,
  pnlPopulation: 0,
  winCount: 0,
  lossCount: 0,
  winRatePct: null,
  averageRealizedPnl: null,
});

export const normalizeAttributionDimensionRow = (raw: unknown): AttributionDimensionRow => {
  if (!raw || typeof raw !== 'object') return emptyAttributionDimensionRow();
  const row = raw as Record<string, unknown>;
  return {
    evaluated: toNumber(row.evaluated),
    blockedIntents: toNumber(row.blocked_intents),
    explicitSkips: toNumber(row.explicit_skips),
    executableIntents: toNumber(row.executable_intents),
    executedCount: toNumber(row.executed_count),
    pnlPopulation: toNumber(row.pnl_population),
    winCount: toNumber(row.win_count),
    lossCount: toNumber(row.loss_count),
    winRatePct: toNullableNumber(row.win_rate_pct),
    averageRealizedPnl: toNullableNumber(row.average_realized_pnl),
  };
};

const normalizeDimensions = (
  raw: unknown,
): Record<string, Record<string, AttributionDimensionRow>> => {
  if (!raw || typeof raw !== 'object') return {};
  const out: Record<string, Record<string, AttributionDimensionRow>> = {};
  for (const [dimensionName, buckets] of Object.entries(raw as Record<string, unknown>)) {
    if (!buckets || typeof buckets !== 'object') continue;
    const bucketOut: Record<string, AttributionDimensionRow> = {};
    for (const [bucketKey, bucketRow] of Object.entries(buckets as Record<string, unknown>)) {
      bucketOut[bucketKey] = normalizeAttributionDimensionRow(bucketRow);
    }
    out[dimensionName] = bucketOut;
  }
  return out;
};

export const emptyAttributionRow = (key = 'unknown'): AttributionRow => ({
  key,
  evaluated: 0,
  signalsGenerated: 0,
  explicitSkips: 0,
  executableIntents: 0,
  blockedIntents: 0,
  executedCount: 0,
  pnlPopulation: 0,
  winCount: 0,
  lossCount: 0,
  winRatePct: null,
  averageRealizedPnl: null,
  averageWinPnl: null,
  averageLossMagnitude: null,
  outcomeCoverage: null,
  insufficientData: true,
  blockerCounts: {},
  diagnosticFactorCounts: {},
  dimensions: {},
});

export const normalizeAttributionRow = (raw: unknown, fallbackKey = 'unknown'): AttributionRow => {
  if (!raw || typeof raw !== 'object') return emptyAttributionRow(fallbackKey);
  const row = raw as Record<string, unknown>;
  const key = toStr(row.strategy) || toStr(row.factor) || toStr(row.key, fallbackKey);
  return {
    key,
    evaluated: toNumber(row.evaluated),
    signalsGenerated: toNumber(row.signals_generated),
    explicitSkips: toNumber(row.explicit_skips),
    executableIntents: toNumber(row.executable_intents),
    blockedIntents: toNumber(row.blocked_intents),
    executedCount: toNumber(row.executed_count),
    pnlPopulation: toNumber(row.pnl_population),
    winCount: toNumber(row.win_count),
    lossCount: toNumber(row.loss_count),
    winRatePct: toNullableNumber(row.win_rate_pct),
    averageRealizedPnl: toNullableNumber(row.average_realized_pnl),
    averageWinPnl: toNullableNumber(row.average_win_pnl),
    averageLossMagnitude: toNullableNumber(row.average_loss_magnitude),
    outcomeCoverage: toNullableNumber(row.outcome_coverage),
    insufficientData: toBool(row.insufficient_data, true),
    blockerCounts: toCountRecord(row.blocker_counts),
    diagnosticFactorCounts: toCountRecord(row.diagnostic_factor_counts),
    dimensions: normalizeDimensions(row.dimensions),
  };
};

export const normalizeExecutionAttribution = (raw: unknown): ExecutionAttributionReport => {
  const row = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>;
  const byStrategy = Array.isArray(row.by_strategy)
    ? row.by_strategy.map((entry) => normalizeAttributionRow(entry))
    : [];
  const byDiagnosticFactor = Array.isArray(row.by_diagnostic_factor)
    ? row.by_diagnostic_factor.map((entry) => normalizeAttributionRow(entry))
    : [];
  return {
    contractVersion: toNumber(row.contract_version),
    windowHours: toNumber(row.window_hours),
    sessionId: toStr(row.session_id),
    tradeType: toStr(row.trade_type),
    coverageComplete: toBool(row.coverage_complete, true),
    signalRows: toNumber(row.signal_rows),
    outcomeRows: toNumber(row.outcome_rows),
    signalRowsTruncated: toBool(row.signal_rows_truncated),
    bucketPolicyVersion: toStr(row.bucket_policy_version),
    warning: typeof row.warning === 'string' && row.warning !== '' ? row.warning : null,
    byStrategy,
    byDiagnosticFactor,
    overall: row.overall ? normalizeAttributionRow(row.overall, 'overall') : emptyAttributionRow('overall'),
  };
};
