// Normalization for `/api/trading/execution-reconciliation`.
//
// The backend reconciles generated signals to execution outcomes by strategy
// and blocker bucket. This layer keeps the parsing and derived display fields
// out of the components, matching the convention used by
// `lib/simulatedTradingStats.ts`.
//
// Backend unit conventions preserved here: `win_rate` is already a 0-100
// percentage and is never scaled again; `average_loss` is a positive
// magnitude; `expectancy` is per decided (non-zero-PnL) closing leg.

export interface ExecutionBlockerBucket {
  reason: string;
  count: number;
  share: number; // 0-1 fraction of the strategy's blocked intents
  blockedExpectedReturnSum: number;
}

export interface StrategyReconciliation {
  strategy: string;
  signalsEvaluated: number;
  signalsGenerated: number;
  executableIntents: number;
  blockedIntents: number;
  closingLegs: number;
  winners: number;
  losers: number;
  winRate: number;
  averageWin: number;
  averageLoss: number;
  expectancy: number;
  profitFactor: number;
  profitFactorUndefined: boolean;
  totalPnl: number;
  totalFees: number;
  intentConversionRate: number;
  outcomeCoverage: number;
  outcomesUnexplained: boolean;
  negativeExpectancyFlag: boolean;
  dominantBlocker: string;
  blockers: ExecutionBlockerBucket[];
}

export interface ExecutionReconciliationSnapshot {
  windowHours: number;
  sessionId: string;
  tradeType: string;
  signalRows: number;
  outcomeRows: number;
  signalRowsTruncated: boolean;
  error: string | null;
  byStrategy: StrategyReconciliation[];
  overall: StrategyReconciliation;
}

const toNumber = (value: unknown, fallback = 0): number => {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
};

const toBool = (value: unknown, fallback = false): boolean =>
  typeof value === 'boolean' ? value : fallback;

const toStr = (value: unknown, fallback = ''): string =>
  typeof value === 'string' ? value : fallback;

export const emptyStrategyReconciliation = (strategy = 'overall'): StrategyReconciliation => ({
  strategy,
  signalsEvaluated: 0,
  signalsGenerated: 0,
  executableIntents: 0,
  blockedIntents: 0,
  closingLegs: 0,
  winners: 0,
  losers: 0,
  winRate: 0,
  averageWin: 0,
  averageLoss: 0,
  expectancy: 0,
  profitFactor: 0,
  profitFactorUndefined: false,
  totalPnl: 0,
  totalFees: 0,
  intentConversionRate: 0,
  outcomeCoverage: 0,
  outcomesUnexplained: false,
  negativeExpectancyFlag: false,
  dominantBlocker: '',
  blockers: [],
});

const normalizeBlockers = (raw: unknown, blockedIntents: number): ExecutionBlockerBucket[] => {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((row): row is Record<string, unknown> => !!row && typeof row === 'object')
    .map((row) => {
      const count = toNumber(row.count);
      const rawShare = row.share;
      return {
        reason: toStr(row.reason, 'unknown') || 'unknown',
        count,
        // A backend that omits `share` still gets a usable mix rather than 0.
        share:
          rawShare === undefined || rawShare === null
            ? blockedIntents > 0
              ? count / blockedIntents
              : 0
            : toNumber(rawShare),
        blockedExpectedReturnSum: toNumber(row.blocked_expected_return_sum),
      };
    })
    .sort((a, b) => (b.count !== a.count ? b.count - a.count : a.reason.localeCompare(b.reason)));
};

export const normalizeStrategyReconciliation = (raw: unknown): StrategyReconciliation => {
  if (!raw || typeof raw !== 'object') return emptyStrategyReconciliation();
  const row = raw as Record<string, unknown>;
  const blockedIntents = toNumber(row.blocked_intents);
  return {
    strategy: toStr(row.strategy, 'unknown') || 'unknown',
    signalsEvaluated: toNumber(row.signals_evaluated),
    signalsGenerated: toNumber(row.signals_generated),
    executableIntents: toNumber(row.executable_intents),
    blockedIntents,
    closingLegs: toNumber(row.closing_legs),
    winners: toNumber(row.winners),
    losers: toNumber(row.losers),
    winRate: toNumber(row.win_rate),
    averageWin: toNumber(row.average_win),
    averageLoss: toNumber(row.average_loss),
    expectancy: toNumber(row.expectancy),
    profitFactor: toNumber(row.profit_factor),
    profitFactorUndefined: toBool(row.profit_factor_undefined),
    totalPnl: toNumber(row.total_pnl),
    totalFees: toNumber(row.total_fees),
    intentConversionRate: toNumber(row.intent_conversion_rate),
    outcomeCoverage: toNumber(row.outcome_coverage),
    outcomesUnexplained: toBool(row.outcomes_unexplained),
    negativeExpectancyFlag: toBool(row.negative_expectancy_flag),
    dominantBlocker: toStr(row.dominant_blocker),
    blockers: normalizeBlockers(row.blockers, blockedIntents),
  };
};

export const normalizeExecutionReconciliation = (
  raw: unknown,
): ExecutionReconciliationSnapshot => {
  const row = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>;
  const byStrategy = Array.isArray(row.by_strategy)
    ? row.by_strategy.map(normalizeStrategyReconciliation)
    : [];
  return {
    windowHours: toNumber(row.window_hours),
    sessionId: toStr(row.session_id),
    tradeType: toStr(row.trade_type),
    signalRows: toNumber(row.signal_rows),
    outcomeRows: toNumber(row.outcome_rows),
    signalRowsTruncated: toBool(row.signal_rows_truncated),
    error: typeof row.error === 'string' && row.error !== '' ? row.error : null,
    byStrategy,
    overall: row.overall
      ? normalizeStrategyReconciliation(row.overall)
      : emptyStrategyReconciliation(),
  };
};

// Ranks strategies by the diagnostic that matters for expectancy work: the
// most negative total PnL first, then the largest blocked-intent backlog.
export const rankStrategiesByExpectancyRisk = (
  strategies: StrategyReconciliation[],
): StrategyReconciliation[] =>
  [...strategies].sort((a, b) => {
    if (a.totalPnl !== b.totalPnl) return a.totalPnl - b.totalPnl;
    if (a.blockedIntents !== b.blockedIntents) return b.blockedIntents - a.blockedIntents;
    return a.strategy.localeCompare(b.strategy);
  });

export const formatBlockerMix = (strategy: StrategyReconciliation): string => {
  if (strategy.blockers.length === 0) return 'none';
  return strategy.blockers
    .map((bucket) => `${bucket.reason}: ${bucket.count} (${(bucket.share * 100).toFixed(0)}%)`)
    .join(', ');
};
