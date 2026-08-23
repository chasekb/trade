import { OrderBookSignal, OrderBookSignalDiagnostics } from '@/types/trading';

export type OrderBookSignalsMode = 'live' | 'simulated';

/**
 * The single view-model consumed by both order-book signal tables.
 *
 * Optional summary and pagination values remain optional on purpose: older
 * backends did not send all of them, and an absent value must not become a
 * fabricated zero or a client-side total. `deviations` describes known
 * live-only semantics without changing the shared signal fields.
 */
export interface NormalizedOrderBookSignals {
  signals: OrderBookSignal[];
  pagination: {
    page: number | undefined;
    limit: number | undefined;
    total: number | undefined;
    totalPages: number | undefined;
    hasNext: boolean | undefined;
    hasPrev: boolean | undefined;
  };
  summary: {
    totalAnalyzed: number | undefined;
    activeSignals: number | undefined;
    averageStrength: number | undefined;
    lastUpdated: string | undefined;
  };
  diagnostics?: OrderBookSignalDiagnostics;
  mode: OrderBookSignalsMode;
  deviations: {
    liveExecutionBlockersVisible: boolean;
    unavailableFields: string[];
  };
}

type UnknownRecord = Record<string, unknown>;

function asRecord(value: unknown): UnknownRecord {
  return value && typeof value === 'object' ? value as UnknownRecord : {};
}

function asFiniteNumber(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function asBoolean(value: unknown): boolean | undefined {
  return typeof value === 'boolean' ? value : undefined;
}

function asString(value: unknown): string | undefined {
  return typeof value === 'string' && value.length > 0 ? value : undefined;
}

function normalizePagination(raw: unknown) {
  const pagination = asRecord(raw);
  return {
    page: asFiniteNumber(pagination.page ?? pagination.current_page),
    limit: asFiniteNumber(pagination.limit ?? pagination.per_page),
    total: asFiniteNumber(pagination.total ?? pagination.total_signals),
    totalPages: asFiniteNumber(pagination.totalPages ?? pagination.total_pages),
    hasNext: asBoolean(pagination.hasNext ?? pagination.has_next),
    hasPrev: asBoolean(pagination.hasPrev ?? pagination.has_prev),
  };
}

export function normalizeOrderBookSignalsResponse(
  raw: unknown,
  mode: OrderBookSignalsMode,
): NormalizedOrderBookSignals {
  const payload = asRecord(raw);
  const signals = Array.isArray(payload.signals)
    ? payload.signals.filter((signal): signal is OrderBookSignal => Boolean(signal) && typeof signal === 'object')
    : [];
  const pagination = normalizePagination(payload.pagination);
  const summary = {
    totalAnalyzed: asFiniteNumber(payload.total_analyzed ?? payload.totalAnalyzed),
    activeSignals: asFiniteNumber(payload.active_signals ?? payload.activeSignals),
    averageStrength: asFiniteNumber(payload.average_strength ?? payload.averageStrength),
    lastUpdated: asString(payload.last_updated ?? payload.lastUpdated),
  };
  const diagnostics = payload.diagnostics && typeof payload.diagnostics === 'object'
    ? payload.diagnostics as OrderBookSignalDiagnostics
    : undefined;

  const unavailableFields = [
    summary.totalAnalyzed === undefined ? 'total analyzed' : '',
    summary.activeSignals === undefined ? 'active signals' : '',
    pagination.total === undefined ? 'pagination total' : '',
    pagination.totalPages === undefined ? 'pagination total pages' : '',
  ].filter(Boolean);

  return {
    signals,
    pagination,
    summary,
    diagnostics,
    mode,
    deviations: {
      liveExecutionBlockersVisible: mode === 'live' && signals.some((signal) => Boolean(signal.execution_analysis?.blocked || signal.execution_analysis?.blocker_reason)),
      unavailableFields,
    },
  };
}

export function mergeNormalizedOrderBookSignals(
  responses: NormalizedOrderBookSignals[],
  page: number,
  requestedLimit: number,
): NormalizedOrderBookSignals {
  const valid = responses.filter(Boolean);
  const signals = valid.flatMap((response) => response.signals);
  signals.sort((left, right) => {
    const strength = (right.signal_strength ?? 0) - (left.signal_strength ?? 0);
    if (strength !== 0) return strength;
    return new Date(right.timestamp).getTime() - new Date(left.timestamp).getTime();
  });

  const start = Math.max(0, page - 1) * requestedLimit;
  const first = valid[0];
  const total = valid.every((response) => response.pagination.total !== undefined)
    ? valid.reduce((sum, response) => sum + (response.pagination.total ?? 0), 0)
    : undefined;
  const totalPages = valid.every((response) => response.pagination.totalPages !== undefined)
    ? (total === undefined ? undefined : Math.ceil(total / requestedLimit))
    : undefined;
  const totalAnalyzed = valid.every((response) => response.summary.totalAnalyzed !== undefined)
    ? valid.reduce((sum, response) => sum + (response.summary.totalAnalyzed ?? 0), 0)
    : undefined;
  const activeSignals = valid.every((response) => response.summary.activeSignals !== undefined)
    ? valid.reduce((sum, response) => sum + (response.summary.activeSignals ?? 0), 0)
    : undefined;
  const strengths = signals.map((signal) => signal.signal_strength).filter((value) => Number.isFinite(value));
  const lastUpdated = valid.map((response) => response.summary.lastUpdated).filter(Boolean).sort().at(-1);

  return {
    signals: signals.slice(start, start + requestedLimit),
    pagination: {
      page,
      limit: requestedLimit,
      total,
      totalPages,
      hasNext: totalPages === undefined ? undefined : page < totalPages,
      hasPrev: valid.some((response) => response.pagination.hasPrev) || page > 1,
    },
    summary: {
      totalAnalyzed,
      activeSignals,
      averageStrength: strengths.length > 0 ? strengths.reduce((sum, value) => sum + value, 0) / strengths.length : first?.summary.averageStrength,
      lastUpdated,
    },
    diagnostics: valid.map((response) => response.diagnostics).find(Boolean),
    mode: first?.mode ?? 'live',
    deviations: {
      liveExecutionBlockersVisible: valid.some((response) => response.deviations.liveExecutionBlockersVisible),
      unavailableFields: [...new Set(valid.flatMap((response) => response.deviations.unavailableFields))],
    },
  };
}