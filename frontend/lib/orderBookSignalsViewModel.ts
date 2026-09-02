import {
  OrderBookSignal,
  OrderBookSignalDiagnostics,
  SimulatedTradingSymbolDiagnosis,
} from '@/types/trading';

export type OrderBookSignalOutcome =
  | 'pending'
  | 'data_unavailable'
  | 'request_failed'
  | 'quote_invalid'
  | 'quote_stale'
  | 'transformer_not_ready'
  | 'feature_shape_mismatch'
  | 'hold'
  | 'gates_blocked'
  | 'intent_not_executable'
  | 'execution_failed'
  | 'trade_open'
  | 'trade_completed'
  | 'executable';

export type OrderBookGroupBy = 'outcome' | 'blocker' | 'modelState' | 'quoteState';

export interface OrderBookSignalViewRow {
  key: string;
  symbol: string;
  outcome: OrderBookSignalOutcome;
  outcomeLabel: string;
  diagnosis?: SimulatedTradingSymbolDiagnosis;
  signal?: OrderBookSignal;
  reason: string;
  blocker: string;
  modelState: string;
  quoteState: string;
  executionState: string;
  tradeState: string;
  candidateSide?: string;
  finalSide?: string;
  updatedAt?: string;
  retryable: boolean;
  price?: number;
  strength?: number;
  edge?: number;
}

export interface OrderBookSignalViewCounts {
  total: number;
  ready: number;
  hold: number;
  blocked: number;
  executable: number;
  unavailable: number;
  pending: number;
  failed: number;
  traded: number;
  activeSignals: number;
}

export interface BuildOrderBookSignalRowsInput {
  signals?: OrderBookSignal[];
  diagnosis?: OrderBookSignalDiagnostics;
  selectedSymbols?: string[];
  failedSymbols?: string[];
  sessionId?: string;
}

const OUTCOMES = new Set<string>([
  'pending',
  'data_unavailable',
  'request_failed',
  'quote_invalid',
  'quote_stale',
  'transformer_not_ready',
  'feature_shape_mismatch',
  'hold',
  'gates_blocked',
  'intent_not_executable',
  'execution_failed',
  'trade_open',
  'trade_completed',
  'executable',
]);

const OUTCOME_LABELS: Record<OrderBookSignalOutcome, string> = {
  pending: 'Pending evaluation',
  data_unavailable: 'Data unavailable',
  request_failed: 'Request failed',
  quote_invalid: 'Invalid quote',
  quote_stale: 'Stale quote',
  transformer_not_ready: 'Transformer warming',
  feature_shape_mismatch: 'Rejected model input',
  hold: 'Valid HOLD',
  gates_blocked: 'Gate blocked',
  intent_not_executable: 'Intent blocked',
  execution_failed: 'Execution failed',
  trade_open: 'Trade open',
  trade_completed: 'Trade completed',
  executable: 'Executable intent',
};

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function text(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value.trim() : undefined;
}

function bool(value: unknown): boolean | undefined {
  return typeof value === 'boolean' ? value : undefined;
}

function numeric(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function firstText(...values: unknown[]): string | undefined {
  for (const value of values) {
    const result = text(value);
    if (result) return result;
  }
  return undefined;
}

function label(value: string): string {
  return value.replace(/_/g, ' ');
}

function getReason(diagnosis: SimulatedTradingSymbolDiagnosis | undefined, signal: OrderBookSignal | undefined, requestFailed = false): string {
  const status = record(diagnosis?.status);
  const statusReason = record(status.reason);
  const execution = record(diagnosis?.execution);
  const intent = record(diagnosis?.intent);
  const signalDiagnosis = record(diagnosis?.signal);
  const gates = record(diagnosis?.gates);
  const gateReasons: string[] = [];

  Object.values(gates).forEach((gate) => {
    const gateRecord = record(gate);
    const reasons = gateRecord.reasons;
    if (!Array.isArray(reasons)) return;
    reasons.forEach((reason) => {
      const reasonRecord = record(reason);
      const code = text(reasonRecord.code);
      const message = text(reasonRecord.message);
      if (code && message) gateReasons.push(`${code}: ${message}`);
      else if (code || message) gateReasons.push(code || message || '');
    });
  });

  return firstText(
    statusReason.message,
    statusReason.code,
    execution.error,
    execution.blocker_reason,
    intent.blocker_reason,
    gateReasons.join('; '),
    signalDiagnosis.reason,
    signal?.signal_reason,
    requestFailed ? 'Request failed for this symbol' : undefined,
    diagnosis ? undefined : 'Awaiting diagnosis',
  ) || 'Awaiting evaluation';
}

function getModelState(diagnosis: SimulatedTradingSymbolDiagnosis | undefined, signal: OrderBookSignal | undefined): string {
  const transformer = record(diagnosis?.transformer);
  const diagnosisMl = record(record(diagnosis?.signal).ml_analysis);
  const ml = Object.keys(diagnosisMl).length > 0 ? diagnosisMl : record(signal?.ml_analysis);
  return firstText(
    transformer.state,
    transformer.inference_status,
    ml.inference_status,
    ml.model_state,
    signal?.ml_analysis?.model_version,
    signal?.ml_analysis?.ml_enabled === false ? 'not_configured' : undefined,
  ) || (diagnosis || signal ? 'ready' : 'not_evaluated');
}

function getQuoteState(diagnosis: SimulatedTradingSymbolDiagnosis | undefined, signal: OrderBookSignal | undefined): string {
  const quote = record(diagnosis?.quote);
  const marketData = record(diagnosis?.market_data);
  return firstText(quote.state, marketData.state, signal?.data_status) || 'not_evaluated';
}

function getOutcome(
  diagnosis: SimulatedTradingSymbolDiagnosis | undefined,
  signal: OrderBookSignal | undefined,
  reason: string,
  requestFailed = false,
): OrderBookSignalOutcome {
  const status = text(record(diagnosis?.status).primary)?.toLowerCase().replace(/\//g, '_');
  const mappedStatus = status === 'signal_hold' ? 'hold' : status === 'signal_ready' ? 'executable' : status;
  if (mappedStatus && OUTCOMES.has(mappedStatus)) return mappedStatus as OrderBookSignalOutcome;

  const trade = record(diagnosis?.trade);
  const execution = record(diagnosis?.execution);
  const intent = record(diagnosis?.intent);
  const gates = record(diagnosis?.gates);
  const transformer = record(diagnosis?.transformer);
  const quote = record(diagnosis?.quote);
  const diagnosisModel = record(record(diagnosis?.signal).ml_analysis);
  const model = Object.keys(diagnosisModel).length > 0 ? diagnosisModel : record(signal?.ml_analysis);

  if (requestFailed && !diagnosis && !signal) return 'request_failed';

  if (text(trade.state) === 'closed' || text(trade.outcome) === 'completed') return 'trade_completed';
  if (text(trade.state) === 'open') return 'trade_open';
  if (['failed', 'rejected'].includes(text(execution.state) || '')) return 'execution_failed';
  if (bool(intent.executable) === true) return 'executable';
  if (bool(intent.blocked) === true || (intent.executable === false && signal?.signal_generated)) return 'intent_not_executable';
  if (Object.values(gates).some((gate) => record(gate).blocked === true)) return 'gates_blocked';
  if (text(transformer.state) === 'shape_mismatch' || text(model.inference_status) === 'shape_mismatch') return 'feature_shape_mismatch';
  if (['warming_up', 'warming', 'not_ready'].includes(text(transformer.state) || text(model.inference_status) || '')) return 'transformer_not_ready';
  if (['invalid', 'missing'].includes(text(quote.state) || '')) return 'quote_invalid';
  if (text(quote.state) === 'stale') return 'quote_stale';
  if (signal?.data_status === 'none') return 'data_unavailable';
  if (signal?.data_status === 'insufficient') return 'pending';
  if (signal?.signal === 'hold' || text(record(diagnosis?.signal).side)?.toLowerCase() === 'hold') return 'hold';
  if (signal?.signal_generated) return 'executable';
  if (reason.toLowerCase().includes('missing quote')) return 'data_unavailable';
  return 'pending';
}

function getSelectedSymbols(input: BuildOrderBookSignalRowsInput): string[] {
  const selected = input.diagnosis?.selected_symbols;
  const diagnosisSymbols = input.diagnosis?.symbols?.map((item) => item.symbol) || [];
  const failedSymbols = [...(input.diagnosis?.failed_request_symbols || []), ...(input.failedSymbols || [])];
  const source = selected && selected.length > 0
    ? selected
    : input.selectedSymbols && input.selectedSymbols.length > 0
      ? input.selectedSymbols
      : [...diagnosisSymbols, ...failedSymbols, ...(input.signals || []).map((signal) => signal.symbol)];
  return Array.from(new Set(source.filter((symbol): symbol is string => typeof symbol === 'string' && symbol.length > 0))).sort();
}

export function buildOrderBookSignalRows(input: BuildOrderBookSignalRowsInput): OrderBookSignalViewRow[] {
  const diagnosisBySymbol = new Map((input.diagnosis?.symbols || []).map((item) => [item.symbol, item]));
  const signalBySymbol = new Map<string, OrderBookSignal>();
  (input.signals || []).forEach((signal) => {
    const existing = signalBySymbol.get(signal.symbol);
    if (!existing || new Date(signal.timestamp).getTime() >= new Date(existing.timestamp).getTime()) {
      signalBySymbol.set(signal.symbol, signal);
    }
  });

  return getSelectedSymbols(input).map((symbol) => {
    const diagnosis = diagnosisBySymbol.get(symbol);
    const signal = signalBySymbol.get(symbol);
    const requestFailed = input.failedSymbols?.includes(symbol) || input.diagnosis?.failed_request_symbols?.includes(symbol) || false;
    const reason = getReason(diagnosis, signal, requestFailed);
    const outcome = getOutcome(diagnosis, signal, reason, requestFailed);
    const signalDiagnosis = record(diagnosis?.signal);
    const intent = record(diagnosis?.intent);
    const execution = record(diagnosis?.execution);
    const trade = record(diagnosis?.trade);
    const diagnosisModel = record(signalDiagnosis.ml_analysis);
    const model = Object.keys(diagnosisModel).length > 0 ? diagnosisModel : record(signal?.ml_analysis);
    const finalSide = firstText(signalDiagnosis.side, signal?.signal);
    const candidateSide = firstText(
      signalDiagnosis.candidate_side,
      signalDiagnosis.original_side,
      signalDiagnosis.candidate_signal,
      intent.intended_side,
      outcome === 'hold' && finalSide !== 'hold' ? finalSide : undefined,
    );
    const blocker = firstText(
      record(diagnosis?.status).reason && record(record(diagnosis?.status).reason).code,
      execution.blocker_reason,
      intent.blocker_reason,
      outcome === 'gates_blocked' ? reason : undefined,
    ) || (['gates_blocked', 'intent_not_executable', 'execution_failed', 'data_unavailable', 'quote_invalid', 'quote_stale'].includes(outcome) ? reason : '');
    const tradeState = text(trade.state) || (outcome === 'trade_completed' ? 'closed' : outcome === 'trade_open' ? 'open' : 'not_applicable');
    const executionState = text(execution.state) || (outcome === 'executable' ? 'ready' : 'not_applicable');
    const updatedAt = firstText(diagnosis?.updated_at, signal?.timestamp);
    const edge = numeric(signal?.ml_analysis?.fee_adjusted_expected_return ?? model.fee_adjusted_expected_return);

    const price = numeric(signal?.price);
    const strength = numeric(signal?.signal_strength);
    return {
      key: `${input.sessionId || input.diagnosis?.session_id || signal?.session_id || 'current'}:${symbol}`,
      symbol,
      outcome,
      outcomeLabel: OUTCOME_LABELS[outcome],
      ...(diagnosis ? { diagnosis } : {}),
      ...(signal ? { signal } : {}),
      reason,
      blocker,
      modelState: getModelState(diagnosis, signal),
      quoteState: getQuoteState(diagnosis, signal),
      executionState,
      tradeState,
      ...(candidateSide ? { candidateSide } : {}),
      ...(finalSide ? { finalSide } : {}),
      ...(updatedAt ? { updatedAt } : {}),
      retryable: record(diagnosis?.status).reason ? bool(record(record(diagnosis?.status).reason).retryable) !== false : outcome === 'pending' || outcome === 'request_failed' || outcome === 'data_unavailable' || outcome === 'quote_stale' || outcome === 'transformer_not_ready',
      ...(price !== undefined ? { price } : {}),
      ...(strength !== undefined ? { strength } : {}),
      ...(edge !== undefined ? { edge } : {}),
    };
  });
}

export function getOrderBookSignalCounts(rows: OrderBookSignalViewRow[]): OrderBookSignalViewCounts {
  return rows.reduce<OrderBookSignalViewCounts>((counts, row) => {
    counts.total += 1;
    if (row.outcome === 'hold') counts.hold += 1;
    if (row.outcome === 'executable') counts.executable += 1;
    if (['gates_blocked', 'intent_not_executable', 'execution_failed'].includes(row.outcome)) counts.blocked += 1;
    if (['data_unavailable', 'request_failed', 'quote_invalid', 'quote_stale'].includes(row.outcome)) counts.unavailable += 1;
    if (row.outcome === 'pending') counts.pending += 1;
    if (row.outcome === 'execution_failed') counts.failed += 1;
    if (['trade_open', 'trade_completed'].includes(row.outcome)) counts.traded += 1;
    if (['executable', 'hold', 'gates_blocked', 'intent_not_executable', 'execution_failed', 'trade_open', 'trade_completed'].includes(row.outcome)) counts.ready += 1;
    return counts;
  }, { total: 0, ready: 0, hold: 0, blocked: 0, executable: 0, unavailable: 0, pending: 0, failed: 0, traded: 0, activeSignals: rows.filter((row) => row.signal?.signal_generated).length });
}

export function formatOrderBookLabel(value: string): string {
  return label(value);
}

export interface OrderBookSignalVersion {
  sequence?: number;
  eventId?: string;
  timestamp: string;
}

export interface OrderBookSignalsViewModel {
  sessionId?: string;
  selectedSymbols: string[];
  rows: OrderBookSignalViewRow[];
  failedSymbols: string[];
  counts: OrderBookSignalViewCounts;
  diagnostics?: OrderBookSignalDiagnostics;
  coverageComplete: boolean;
  lastUpdated?: string;
  signalVersions: Record<string, OrderBookSignalVersion>;
}

export interface OrderBookSignalEvent {
  sessionId?: string;
  sequence?: number;
  eventId?: string;
  signal: OrderBookSignal;
}

function timestamp(value?: string): number {
  if (!value) return Number.NEGATIVE_INFINITY;
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? Number.NEGATIVE_INFINITY : parsed;
}

function eventVersion(signal: OrderBookSignal, event?: OrderBookSignalEvent): OrderBookSignalVersion {
  return {
    ...(event?.sequence !== undefined ? { sequence: event.sequence } : signal.sequence !== undefined ? { sequence: signal.sequence } : {}),
    ...(event?.eventId || signal.event_id ? { eventId: event?.eventId || signal.event_id } : {}),
    timestamp: signal.timestamp,
  };
}

function isNewerSignal(
  incoming: OrderBookSignalVersion,
  existing: OrderBookSignalVersion | undefined,
): boolean {
  if (!existing) return true;
  if (incoming.eventId && incoming.eventId === existing.eventId) return false;
  if (incoming.sequence !== undefined && existing.sequence !== undefined) {
    return incoming.sequence > existing.sequence;
  }
  // A sequence-bearing event is authoritative over an unsequenced HTTP
  // snapshot. Once a sequence exists, a later poll cannot roll it back.
  if (incoming.sequence !== undefined) return true;
  if (existing.sequence !== undefined) return false;
  if (incoming.eventId && existing.eventId && incoming.eventId !== existing.eventId) {
    return incoming.eventId.localeCompare(existing.eventId) > 0;
  }
  return timestamp(incoming.timestamp) > timestamp(existing.timestamp);
}

function newerDiagnosis(
  incoming: SimulatedTradingSymbolDiagnosis,
  existing: SimulatedTradingSymbolDiagnosis | undefined,
): SimulatedTradingSymbolDiagnosis {
  if (!existing) return incoming;
  if (incoming.sequence !== undefined || existing.sequence !== undefined) {
    if (incoming.sequence === undefined) return existing;
    if (existing.sequence === undefined) return incoming;
    return incoming.sequence >= existing.sequence ? incoming : existing;
  }
  return timestamp(incoming.updated_at) >= timestamp(existing.updated_at) ? incoming : existing;
}

/** Merge diagnostic snapshots without allowing a stale poll to erase events. */
export function reconcileOrderBookSignalDiagnostics(
  current: OrderBookSignalDiagnostics | undefined,
  incoming: OrderBookSignalDiagnostics,
): OrderBookSignalDiagnostics {
  if (!current || (current.session_id && incoming.session_id && current.session_id !== incoming.session_id)) {
    return incoming;
  }

  const selectedSymbols = incoming.selected_symbols ?? current.selected_symbols ?? [];
  const symbolMap = new Map<string, SimulatedTradingSymbolDiagnosis>();
  (current.symbols ?? []).forEach((item) => symbolMap.set(item.symbol, item));
  (incoming.symbols ?? []).forEach((item) => symbolMap.set(item.symbol, newerDiagnosis(item, symbolMap.get(item.symbol))));
  return {
    ...current,
    ...incoming,
    selected_symbols: selectedSymbols,
    symbols: selectedSymbols
      .map((symbol) => symbolMap.get(symbol))
      .filter((item): item is SimulatedTradingSymbolDiagnosis => Boolean(item)),
  };
}

function selectedSymbolsFor(input: BuildOrderBookSignalRowsInput, previous?: OrderBookSignalsViewModel): string[] {
  const requested = input.selectedSymbols && input.selectedSymbols.length > 0
    ? input.selectedSymbols
    : input.diagnosis?.selected_symbols && input.diagnosis.selected_symbols.length > 0
      ? input.diagnosis.selected_symbols
      : [];
  return Array.from(new Set([
    ...requested,
    ...(input.diagnosis?.symbols ?? []).map(({ symbol }) => symbol),
    ...(input.diagnosis?.failed_request_symbols ?? []),
    ...(input.failedSymbols ?? []),
    ...(input.signals ?? []).map(({ symbol }) => symbol),
  ].filter(Boolean))).filter((symbol) => !previous || requested.length === 0 || requested.includes(symbol)).sort();
}

/** Merge HTTP snapshots without replacing newer WebSocket state. */
export function reconcileOrderBookSignals(
  input: BuildOrderBookSignalRowsInput & { previous?: OrderBookSignalsViewModel },
): OrderBookSignalsViewModel {
  const requestedSessionId = input.sessionId ?? input.diagnosis?.session_id;
  const previous = input.previous && (!requestedSessionId || !input.previous.sessionId || input.previous.sessionId === requestedSessionId)
    ? input.previous
    : undefined;
  const sessionId = input.sessionId ?? input.diagnosis?.session_id ?? previous?.sessionId;
  const selectedSymbols = selectedSymbolsFor(input, previous);
  const compatibleDiagnosis = input.diagnosis && (!sessionId || !input.diagnosis.session_id || input.diagnosis.session_id === sessionId)
    ? input.diagnosis
    : undefined;
  const mergedInputDiagnosis = compatibleDiagnosis
    ? reconcileOrderBookSignalDiagnostics(previous?.diagnostics, compatibleDiagnosis)
    : previous?.diagnostics;
  const diagnoses = new Map<string, SimulatedTradingSymbolDiagnosis>();
  previous?.rows.forEach((row) => {
    if (row.diagnosis && selectedSymbols.includes(row.symbol)) diagnoses.set(row.symbol, row.diagnosis);
  });
  (mergedInputDiagnosis?.symbols ?? []).forEach((item) => diagnoses.set(item.symbol, newerDiagnosis(item, diagnoses.get(item.symbol))));

  const signals = new Map<string, OrderBookSignal>();
  const signalVersions: Record<string, OrderBookSignalVersion> = { ...(previous?.signalVersions ?? {}) };
  previous?.rows.forEach((row) => {
    if (row.signal && selectedSymbols.includes(row.symbol)) signals.set(row.symbol, row.signal);
  });
  const failedSymbolSet = new Set<string>([
    ...(previous?.failedSymbols ?? []),
    ...(input.failedSymbols ?? []),
    ...(mergedInputDiagnosis?.failed_request_symbols ?? []),
  ]);
  (input.signals ?? []).forEach((signal) => {
    if (!selectedSymbols.includes(signal.symbol)) return;
    if (sessionId && signal.session_id && signal.session_id !== sessionId) return;
    const version = eventVersion(signal);
    if (isNewerSignal(version, signalVersions[signal.symbol])) {
      signals.set(signal.symbol, signal);
      signalVersions[signal.symbol] = version;
      failedSymbolSet.delete(signal.symbol);
    }
  });

  const failedSymbols = Array.from(failedSymbolSet)
    .filter((symbol) => selectedSymbols.includes(symbol))
    .sort();
  const diagnosis = mergedInputDiagnosis ? {
    ...mergedInputDiagnosis,
    ...(sessionId ? { session_id: sessionId } : {}),
    selected_symbols: selectedSymbols,
    symbols: selectedSymbols.map((symbol) => diagnoses.get(symbol)).filter((item): item is SimulatedTradingSymbolDiagnosis => Boolean(item)),
    failed_request_symbols: failedSymbols,
    failed_request_symbol_count: failedSymbols.length,
  } : previous?.diagnostics;
  const rows = buildOrderBookSignalRows({
    ...(sessionId ? { sessionId } : {}),
    selectedSymbols,
    ...(diagnosis ? { diagnosis } : {}),
    signals: Array.from(signals.values()),
    failedSymbols,
  });
  const lastUpdated = rows.map((row) => row.updatedAt).filter(Boolean).sort((left, right) => timestamp(right) - timestamp(left))[0];
  return {
    ...(sessionId ? { sessionId } : {}),
    selectedSymbols,
    rows,
    counts: getOrderBookSignalCounts(rows),
    failedSymbols,
    ...(diagnosis ? { diagnostics: diagnosis } : {}),
    coverageComplete: (diagnosis?.coverage_complete ?? true) && failedSymbols.length === 0,
    ...(lastUpdated ? { lastUpdated } : {}),
    signalVersions,
  };
}

/** Apply a signal event to the canonical cache, independent of visible page. */
export function mergeOrderBookSignalEvent(
  current: OrderBookSignalsViewModel,
  event: OrderBookSignalEvent,
): OrderBookSignalsViewModel {
  if (!event.signal.symbol || (current.sessionId && event.sessionId && current.sessionId !== event.sessionId)) return current;
  const version = eventVersion(event.signal, event);
  if (!isNewerSignal(version, current.signalVersions[event.signal.symbol])) return current;
  const eventSessionId = event.sessionId ?? event.signal.session_id ?? current.sessionId;
  return reconcileOrderBookSignals({
    ...(eventSessionId ? { sessionId: eventSessionId } : {}),
    selectedSymbols: current.selectedSymbols,
    ...(current.diagnostics ? { diagnosis: current.diagnostics } : {}),
    signals: [{
      ...event.signal,
      ...(event.sequence !== undefined ? { sequence: event.sequence } : {}),
      ...(event.eventId ? { event_id: event.eventId } : {}),
    }],
    previous: current,
  });
}

export function paginateOrderBookSignals(
  model: OrderBookSignalsViewModel,
  page: number,
  perPage: number,
) {
  const boundedPerPage = Math.min(100, Math.max(1, Math.trunc(perPage) || 1));
  const totalPages = Math.max(1, Math.ceil(model.rows.length / boundedPerPage));
  const boundedPage = Math.min(totalPages, Math.max(1, Math.trunc(page) || 1));
  const start = (boundedPage - 1) * boundedPerPage;
  return {
    rows: model.rows.slice(start, start + boundedPerPage),
    pagination: {
      page: boundedPage,
      perPage: boundedPerPage,
      total: model.rows.length,
      totalPages,
      hasNext: boundedPage < totalPages,
      hasPrevious: boundedPage > 1,
    },
  };
}

function compareProjectedSignals(left: OrderBookSignal, right: OrderBookSignal): number {
  const strengthDiff = (right.signal_strength ?? 0) - (left.signal_strength ?? 0);
  if (strengthDiff !== 0) return strengthDiff;
  const leftTimestamp = timestamp(left.timestamp);
  const rightTimestamp = timestamp(right.timestamp);
  if (rightTimestamp !== leftTimestamp) return rightTimestamp - leftTimestamp;
  return left.symbol.localeCompare(right.symbol);
}

/** Project the signal-only API compatibility page from the canonical model. */
export function projectOrderBookSignalPage(
  model: OrderBookSignalsViewModel,
  page: number,
  perPage: number,
) {
  const boundedPerPage = Math.min(100, Math.max(1, Math.trunc(perPage) || 1));
  const signals = model.rows
    .flatMap((row) => row.signal ? [row.signal] : [])
    .sort(compareProjectedSignals);
  const totalPages = signals.length === 0 ? 0 : Math.ceil(signals.length / boundedPerPage);
  const boundedPage = totalPages === 0 ? 1 : Math.min(totalPages, Math.max(1, Math.trunc(page) || 1));
  const start = (boundedPage - 1) * boundedPerPage;
  return {
    signals: signals.slice(start, start + boundedPerPage),
    pagination: {
      page: boundedPage,
      perPage: boundedPerPage,
      total: signals.length,
      totalPages,
      hasNext: boundedPage < totalPages,
      hasPrevious: boundedPage > 1,
    },
  };
}
