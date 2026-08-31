import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@/lib/api';
import {
  TradingMode,
  TradingStrategy,
  OrderBookSignal,
  OrderBookSignalDiagnostics,
  SimulatedTradingDiagnosisSummary,
  SimulatedTradingSymbolDiagnosis,
} from '@/types/trading';

type TradingParameterValue = string | number | boolean | undefined;
type TradingParameters = Record<string, TradingParameterValue>;

type TradingStatusPayload = {
  status?: string;
  isActive?: boolean;
  is_active?: boolean;
  is_trading?: boolean;
  mode?: TradingMode;
  strategy?: TradingStrategy;
  strategy_type?: TradingStrategy;
  symbols?: string[];
  session_id?: string;
  data?: TradingStatusPayload;
  portfolio?: unknown;
  stats?: unknown;
  recent_trades?: unknown;
  current_capital?: unknown;
};

export type TradingDisplayStatus = {
  isActive: boolean;
  mode: TradingMode;
  strategy: TradingStrategy;
  symbols: string[];
  sessionId?: string | undefined;
};

function unwrapTradingStatusPayload(payload: unknown): TradingStatusPayload | undefined {
  let current: unknown = payload;
  for (let depth = 0; depth < 3 && isRecord(current); depth += 1) {
    if (isRecord(current.data)) {
      current = current.data;
      continue;
    }
    return current as TradingStatusPayload;
  }
  return isRecord(current) ? current as TradingStatusPayload : undefined;
}

export function normalizeTradingStatusPayload(
  payload: unknown,
  fallback: TradingDisplayStatus,
): TradingDisplayStatus {
  const candidate = unwrapTradingStatusPayload(payload);
  if (!candidate) {
    return fallback;
  }

  const status = typeof candidate.status === 'string' ? candidate.status.toLowerCase() : '';
  const explicitActive = candidate.isActive ?? candidate.is_active ?? candidate.is_trading;
  const isActive = typeof explicitActive === 'boolean'
    ? explicitActive
    : ['active', 'started', 'starting', 'running'].includes(status)
      ? true
      : ['inactive', 'stopped', 'stopping', 'settling', 'failed', 'error'].includes(status)
        ? false
        : fallback.isActive;

  return {
    isActive,
    mode: candidate.mode ?? fallback.mode,
    strategy: candidate.strategy_type ?? candidate.strategy ?? fallback.strategy,
    symbols: Array.isArray(candidate.symbols) ? candidate.symbols : fallback.symbols,
    ...(candidate.session_id ? { sessionId: candidate.session_id } : fallback.sessionId ? { sessionId: fallback.sessionId } : {}),
  };
}

type OrderBookSignalsData = {
  signals: OrderBookSignal[];
  pagination?: {
    current_page?: number;
    page?: number;
    per_page?: number;
    limit?: number;
    total_signals?: number;
    total_pages?: number;
    has_next?: boolean;
    has_prev?: boolean;
  };
  total_analyzed?: number;
  active_signals?: number;
  last_updated?: string;
  average_strength?: number;
  diagnostics?: OrderBookSignalDiagnostics;
};

type WebSocketPayload = {
  type?: string;
  event_type?: string;
  data?: unknown;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function parseWebSocketPayload(raw: string): WebSocketPayload {
  const parsed: unknown = JSON.parse(raw || '{}');
  return isRecord(parsed) ? parsed : {};
}

// Live Trading Hooks

export function useLiveTrading(mode: TradingMode = 'simulated') {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<TradingDisplayStatus>({
    isActive: false,
    mode,
    strategy: 'orderbook' as TradingStrategy,
    symbols: [] as string[],
  });

  // Query to keep status in sync with backend (especially for symbols added in background)
  const { data: backendStatus } = useQuery({
    queryKey: ['trading-status', mode],
    queryFn: async () => {
      const response = await apiClient.getTradingStatus(mode);
      if (response.status === 'error') {
        throw new Error(response.error || 'Failed to fetch trading status');
      }
      return response.data;
    },
    enabled: mode === 'live' || status.isActive,
    refetchInterval: status.isActive ? 5000 : (mode === 'live' ? 10000 : false),
    staleTime: 1000, // Consider data fresh for 1 second
    refetchOnWindowFocus: true, // Refetch when tab becomes visible again
  });

  const displayStatus = normalizeTradingStatusPayload(backendStatus, status);

  const startTradingMutation = useMutation({
    mutationFn: async (config: {
      mode: TradingMode;
      strategy: TradingStrategy;
      symbols: string[];
      parameters: TradingParameters;
      position_size_percent?: number;
      max_positions?: number;
      position_update_interval?: number;
    }) => {
      const apiConfig: {
        position_size_percent?: number;
        max_positions?: number;
        position_update_interval?: number;
      } = {};

      if (config.position_size_percent !== undefined) {
        apiConfig.position_size_percent = config.position_size_percent;
      }
      if (config.max_positions !== undefined) {
        apiConfig.max_positions = config.max_positions;
      }
      if (config.position_update_interval !== undefined) {
        apiConfig.position_update_interval = config.position_update_interval;
      }

      const response = await apiClient.startTrading(
        config.mode,
        config.strategy,
        config.symbols,
        config.parameters,
        apiConfig
      );

      if (response.status === 'error') {
        throw new Error(response.error || 'Failed to start trading');
      }

      return response;
    },
    onSuccess: (response, variables) => {
      const responseData: TradingStatusPayload = response.data ?? response;
      // Accept multiple response shapes from backend variants:
      // - { status: 'started', is_active: true }
      // - { status: 'success', session_id: '...' }
      // - ApiResponse-wrapped payloads with data.is_active/session_id
      const isStarted =
        responseData.status === 'started' ||
        responseData.status === 'success' ||
        responseData.is_active === true ||
        responseData.isActive === true ||
        Boolean(responseData.session_id) ||
        responseData.data?.is_active === true ||
        Boolean(responseData.data?.session_id);

      if (isStarted) {
        if (variables.mode === 'simulated') {
          queryClient.removeQueries({ queryKey: ['simulated-trading-stats'] });
          queryClient.removeQueries({ queryKey: ['orderbook-signals', variables.mode] });
        }
        setStatus({
          isActive: true,
          mode: variables.mode,
          strategy: variables.strategy,
          symbols: variables.symbols,
          ...(responseData.session_id ? { sessionId: responseData.session_id } : {}),
        });

        queryClient.setQueryData(['trading-status', mode], responseData);
        if (
          mode === 'simulated' &&
          responseData &&
          typeof responseData === 'object' &&
          ('portfolio' in responseData || 'stats' in responseData || 'recent_trades' in responseData || 'current_capital' in responseData)
        ) {
          queryClient.setQueryData(['simulated-trading-stats'], responseData);
        }

        queryClient.invalidateQueries({ queryKey: ['trading-status', mode] });
        if (mode === 'simulated') {
          queryClient.invalidateQueries({ queryKey: ['simulated-trading-stats'] });
        }
        if (mode === 'live') {
          queryClient.invalidateQueries({ queryKey: ['live-portfolio-status'] });
          queryClient.invalidateQueries({ queryKey: ['live-tab-producer'] });
        }
        queryClient.invalidateQueries({ queryKey: ['orderbook-signals', mode] });
      }
    },
  });

  const stopTradingMutation = useMutation({
    mutationFn: async () => {
      const response = await apiClient.stopTrading(mode);
      if (response.status === 'error') {
        throw new Error(response.error || 'Failed to stop trading');
      }
      return response;
    },
    onSuccess: (response) => {
      const responseStatus = (response as { status: string }).status;
      if (responseStatus === 'success' || responseStatus === 'settling') {
        setStatus(prev => ({ ...prev, isActive: false, symbols: [], sessionId: undefined }));
        queryClient.setQueryData(['trading-status', mode], response);
        queryClient.invalidateQueries({ queryKey: ['trading-status', mode] });
        // A stopped session must not leave portfolio or signal rows available
        // for a later restart while its first requests are still in flight.
        if (mode === 'simulated') {
          queryClient.removeQueries({ queryKey: ['simulated-trading-stats'] });
          queryClient.removeQueries({ queryKey: ['orderbook-signals', mode] });
        }
        if (mode === 'simulated') {
          queryClient.invalidateQueries({ queryKey: ['simulated-trading-stats'] });
        }
        if (mode === 'live') {
          queryClient.invalidateQueries({ queryKey: ['live-portfolio-status'] });
          queryClient.invalidateQueries({ queryKey: ['live-tab-producer'] });
        }
        queryClient.invalidateQueries({ queryKey: ['orderbook-signals', mode] });
      }
    },
  });

  const updateStrategyParamsMutation = useMutation({
    mutationFn: (params: TradingParameters) => apiClient.updateStrategyParameters(params, mode),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trading-status', mode] });
      if (mode === 'simulated') {
        queryClient.invalidateQueries({ queryKey: ['simulated-trading-stats'] });
      }
      if (mode === 'live') {
        queryClient.invalidateQueries({ queryKey: ['live-tab-producer'] });
      }
      queryClient.invalidateQueries({ queryKey: ['orderbook-signals', mode] });
    },
  });

  const closePositionMutation = useMutation({
    mutationFn: (symbol: string) => apiClient.closePosition(symbol),
    onSuccess: () => {
      // Refetch portfolio status to update positions list
      queryClient.invalidateQueries({ queryKey: ['live-portfolio-status'] });
      queryClient.invalidateQueries({ queryKey: ['live-tab-producer'] });
    },
  });

  const liquidateCoinbaseHoldingsMutation = useMutation({
    mutationFn: (symbols?: string[]) => apiClient.liquidateCoinbaseHoldings(symbols),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['live-portfolio-status'] });
      queryClient.invalidateQueries({ queryKey: ['live-tab-producer'] });
      queryClient.invalidateQueries({ queryKey: ['trading-status', 'live'] });
    },
  });

  return {
    status: displayStatus,
    startTrading: startTradingMutation.mutateAsync,
    stopTrading: stopTradingMutation.mutateAsync,
    updateStrategyParameters: updateStrategyParamsMutation.mutateAsync,
    closePosition: closePositionMutation.mutateAsync,
    liquidateCoinbaseHoldings: liquidateCoinbaseHoldingsMutation.mutateAsync,
    loading: startTradingMutation.isPending || stopTradingMutation.isPending || closePositionMutation.isPending || liquidateCoinbaseHoldingsMutation.isPending,
    error: startTradingMutation.error || stopTradingMutation.error || closePositionMutation.error || liquidateCoinbaseHoldingsMutation.error,
  };
}

// Order Book Signals Hook with Pagination Support
const ORDERBOOK_SYMBOL_CHUNK_SIZE = 50;

function chunkOrderBookSymbols(symbols?: string[]) {
  if (!symbols || symbols.length === 0) {
    return [] as string[][];
  }

  const chunks: string[][] = [];
  for (let i = 0; i < symbols.length; i += ORDERBOOK_SYMBOL_CHUNK_SIZE) {
    chunks.push(symbols.slice(i, i + ORDERBOOK_SYMBOL_CHUNK_SIZE));
  }
  return chunks;
}

function mergeCountMap(left?: Record<string, number>, right?: Record<string, number>) {
  const merged: Record<string, number> = { ...(left ?? {}) };
  for (const [key, value] of Object.entries(right ?? {})) {
    merged[key] = (merged[key] ?? 0) + value;
  }
  return merged;
}

function mergeDiagnosisSummaries(
  summaries: Array<SimulatedTradingDiagnosisSummary | undefined>,
): SimulatedTradingDiagnosisSummary | undefined {
  const available = summaries.filter(
    (summary): summary is SimulatedTradingDiagnosisSummary => Boolean(summary),
  );
  if (available.length === 0) {
    return undefined;
  }

  const byPrimaryStatus = available.reduce(
    (merged, summary) => mergeCountMap(merged, summary.by_primary_status),
    {} as Record<string, number>,
  );
  const reasonCounts = available.reduce((merged, summary) => {
    for (const reason of summary.no_trade_reasons ?? []) {
      merged[reason.code] = (merged[reason.code] ?? 0) + reason.count;
    }
    return merged;
  }, {} as Record<string, number>);
  const noTradeReasons = Object.entries(reasonCounts)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([code, count]) => ({ code, count }));
  const tradeCount = Math.max(...available.map((summary) => summary.trade_count ?? 0));
  const selectedCount = available.reduce(
    (total, summary) => total + (summary.selected_count ?? 0),
    0,
  );
  const terminalCount = available.reduce(
    (total, summary) => total + (summary.terminal_count ?? 0),
    0,
  );
  const latest = available[available.length - 1];
  const message = tradeCount > 0
    ? `${tradeCount} trade${tradeCount === 1 ? '' : 's'} recorded`
    : noTradeReasons.length > 0
      ? `No trades recorded: ${noTradeReasons.map(({ code, count }) => `${code} (${count})`).join(', ')}.`
      : latest.message;

  const mergedSummary: SimulatedTradingDiagnosisSummary = {
    ...latest,
    selected_count: selectedCount,
    terminal_count: terminalCount,
    trade_count: tradeCount,
    by_primary_status: byPrimaryStatus,
    no_trade_reasons: noTradeReasons,
  };
  if (message !== undefined) {
    mergedSummary.message = message;
  }
  return mergedSummary;
}

export type SimulatedTradingDiagnosisEvent = {
  event_type?: string;
  session_id?: string;
  symbol: string;
  sequence: number;
  diagnosis: SimulatedTradingSymbolDiagnosis;
};

function diagnosisReasonCodes(diagnosis?: SimulatedTradingSymbolDiagnosis): string[] {
  if (!diagnosis) {
    return [];
  }
  const codes: string[] = [];
  const statusCode = diagnosis.status?.reason?.code;
  if (typeof statusCode === 'string' && statusCode) {
    codes.push(statusCode);
  }
  for (const gate of Object.values(diagnosis.gates ?? {})) {
    if (!gate || typeof gate !== 'object') {
      continue;
    }
    const reasons = (gate as { reasons?: unknown }).reasons;
    if (!Array.isArray(reasons)) {
      continue;
    }
    for (const reason of reasons) {
      if (!reason || typeof reason !== 'object') {
        continue;
      }
      const code = (reason as { code?: unknown }).code;
      if (typeof code === 'string' && code) {
        codes.push(code);
      }
    }
  }
  return codes;
}

function adjustDiagnosisReasonCounts(
  counts: Record<string, number>,
  diagnosis: SimulatedTradingSymbolDiagnosis | undefined,
  delta: number,
) {
  for (const code of diagnosisReasonCodes(diagnosis)) {
    counts[code] = (counts[code] ?? 0) + delta;
    if (counts[code] <= 0) {
      delete counts[code];
    }
  }
}

/**
 * Apply one sequence-numbered symbol event to the canonical diagnosis cache.
 * The reducer is deliberately immutable and idempotent: retries with the
 * same trade ID or an older sequence cannot inflate aggregate counts.
 */
export function applySimulatedTradingDiagnosisEvent(
  current: OrderBookSignalDiagnostics | undefined,
  event: SimulatedTradingDiagnosisEvent,
): OrderBookSignalDiagnostics | undefined {
  if (event.event_type && event.event_type !== 'simulated_trading.symbol_diagnosis') {
    return current;
  }
  if (!event.symbol || !Number.isInteger(event.sequence) || event.sequence < 0 ||
      event.diagnosis.symbol !== event.symbol) {
    return current;
  }
  if (current?.session_id && event.session_id && current.session_id !== event.session_id) {
    return current;
  }
  if (current?.selected_symbols?.length && !current.selected_symbols.includes(event.symbol)) {
    return current;
  }

  const existing = current?.symbols?.find((diagnosis) => diagnosis.symbol === event.symbol);
  if (existing?.sequence !== undefined && event.sequence <= existing.sequence) {
    return current;
  }

  const previousSymbols = current?.symbols ?? [];
  const selectedSymbols = [...(current?.selected_symbols ?? previousSymbols.map(({ symbol }) => symbol))];
  if (!selectedSymbols.includes(event.symbol)) {
    selectedSymbols.push(event.symbol);
  }
  const symbolMap = new Map(previousSymbols.map((diagnosis) => [diagnosis.symbol, diagnosis]));
  symbolMap.set(event.symbol, event.diagnosis);
  const symbols = selectedSymbols.map((symbol) => symbolMap.get(symbol)).filter(
    (diagnosis): diagnosis is SimulatedTradingSymbolDiagnosis => Boolean(diagnosis),
  );

  const previousSummary = current?.summary;
  const byPrimaryStatus = { ...(previousSummary?.by_primary_status ?? {}) };
  const previousPrimary = existing?.status?.primary;
  const nextPrimary = event.diagnosis.status?.primary;
  if (previousPrimary) {
    byPrimaryStatus[previousPrimary] = (byPrimaryStatus[previousPrimary] ?? 0) - 1;
    if (byPrimaryStatus[previousPrimary] <= 0) {
      delete byPrimaryStatus[previousPrimary];
    }
  }
  if (nextPrimary) {
    byPrimaryStatus[nextPrimary] = (byPrimaryStatus[nextPrimary] ?? 0) + 1;
  }

  const previousTerminal = existing?.status?.terminal === true;
  const nextTerminal = event.diagnosis.status?.terminal === true;
  const terminalCount = Math.max(0, (previousSummary?.terminal_count ?? 0)
    - (previousTerminal ? 1 : 0) + (nextTerminal ? 1 : 0));
  const previousTradeId = existing?.trade?.trade_id;
  const nextTradeId = event.diagnosis.trade?.trade_id;
  const knownTradeIds = new Set(previousSymbols.flatMap((diagnosis) => {
    const tradeId = diagnosis.trade?.trade_id;
    return typeof tradeId === 'string' && tradeId.length > 0 ? [tradeId] : [];
  }));
  const addedTrade = typeof nextTradeId === 'string' && nextTradeId.length > 0 &&
    nextTradeId !== previousTradeId && !knownTradeIds.has(nextTradeId);
  const tradeCount = (previousSummary?.trade_count ?? 0) + (addedTrade ? 1 : 0);
  const reasonCounts: Record<string, number> = {};
  for (const reason of previousSummary?.no_trade_reasons ?? []) {
    reasonCounts[reason.code] = reason.count;
  }
  adjustDiagnosisReasonCounts(reasonCounts, existing, -1);
  adjustDiagnosisReasonCounts(reasonCounts, event.diagnosis, 1);
  const noTradeReasons = Object.entries(reasonCounts)
    .filter(([, count]) => count > 0)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([code, count]) => ({ code, count }));

  const updated: OrderBookSignalDiagnostics = {
    ...(current ?? {}),
    schema_version: current?.schema_version ?? 'simulated_trading_diagnosis.v1',
    selected_symbols: selectedSymbols,
    symbols,
    summary: {
      ...(previousSummary ?? {}),
      selected_count: Math.max(previousSummary?.selected_count ?? 0, selectedSymbols.length),
      terminal_count: terminalCount,
      trade_count: tradeCount,
      by_primary_status: byPrimaryStatus,
      no_trade_reasons: noTradeReasons,
    },
  };
  const sessionId = event.session_id ?? current?.session_id;
  const asOf = event.diagnosis.updated_at ?? current?.as_of;
  if (sessionId !== undefined) {
    updated.session_id = sessionId;
  }
  if (asOf !== undefined) {
    updated.as_of = asOf;
  }
  return updated;
}

function mergeOrderBookSignalResponses(responses: OrderBookSignalsData[], page: number, perPage: number) {
  const normalizedResponses = responses.filter(Boolean);
  const allSignals = normalizedResponses.flatMap((response) => response.signals ?? []);
  allSignals.sort((left, right) => {
    const strengthDiff = (right.signal_strength ?? 0) - (left.signal_strength ?? 0);
    if (strengthDiff !== 0) {
      return strengthDiff;
    }

    const timeDiff = new Date(right.timestamp).getTime() - new Date(left.timestamp).getTime();
    if (timeDiff !== 0) {
      return timeDiff;
    }

    return left.symbol.localeCompare(right.symbol);
  });

  const total = allSignals.length;
  const totalPages = total === 0 ? 0 : Math.ceil(total / perPage);
  const currentPage = Math.max(1, page);
  const startIndex = (currentPage - 1) * perPage;
  const pageSignals = allSignals.slice(startIndex, startIndex + perPage);

  const lastUpdated = responses.reduce((latest, response) => {
    if (!response.last_updated) {
      return latest;
    }
    if (!latest) {
      return response.last_updated;
    }
    return new Date(response.last_updated).getTime() > new Date(latest).getTime()
      ? response.last_updated
      : latest;
  }, '' as string);

  const totalAnalyzed = responses.reduce((sum, response) => sum + (response.total_analyzed ?? response.signals?.length ?? 0), 0);
  const activeSignals = responses.reduce((sum, response) => {
    const computedActiveSignals = response.signals?.reduce(
      (count: number, signal: OrderBookSignal) => count + (signal.signal_generated ? 1 : 0),
      0
    );
    return sum + (response.active_signals ?? computedActiveSignals ?? 0);
  }, 0);
  const averageStrength = total === 0
    ? 0
    : allSignals.reduce((sum, signal) => sum + (signal.signal_strength ?? 0), 0) / total;
  const diagnosticRows = normalizedResponses
    .map((response) => response.diagnostics)
    .filter(Boolean) as OrderBookSignalDiagnostics[];
  const diagnostics = diagnosticRows.length === 0 ? undefined : diagnosticRows.reduce((merged, current) => ({
    ...merged,
    ...current,
    selected_symbol_count: (merged.selected_symbol_count ?? 0) + (current.selected_symbol_count ?? current.requested_symbol_count ?? 0),
    requested_symbol_count: (merged.requested_symbol_count ?? 0) + (current.requested_symbol_count ?? 0),
    quote_attempted_symbol_count: (merged.quote_attempted_symbol_count ?? 0) + (current.quote_attempted_symbol_count ?? 0),
    quote_success_symbol_count: (merged.quote_success_symbol_count ?? 0) + (current.quote_success_symbol_count ?? 0),
    quote_skipped_symbol_count: (merged.quote_skipped_symbol_count ?? 0) + (current.quote_skipped_symbol_count ?? 0),
    current_latest_signal_count: (merged.current_latest_signal_count ?? 0) + (current.current_latest_signal_count ?? 0),
    recent_signal_record_count: (merged.recent_signal_record_count ?? 0) + (current.recent_signal_record_count ?? 0),
    active_recent_signal_records: (merged.active_recent_signal_records ?? 0) + (current.active_recent_signal_records ?? 0),
    executable_order_intent_count: (merged.executable_order_intent_count ?? 0) + (current.executable_order_intent_count ?? 0),
    execution_blocker_counts: mergeCountMap(merged.execution_blocker_counts, current.execution_blocker_counts),
    execution_strength_bucket_counts: mergeCountMap(merged.execution_strength_bucket_counts, current.execution_strength_bucket_counts),
    execution_expected_return_bucket_counts: mergeCountMap(merged.execution_expected_return_bucket_counts, current.execution_expected_return_bucket_counts),
    missing_latest_signal_count: (merged.missing_latest_signal_count ?? 0) + (current.missing_latest_signal_count ?? 0),
    missing_latest_signal_symbols: [
      ...((merged.missing_latest_signal_symbols as string[] | undefined) ?? []),
      ...((current.missing_latest_signal_symbols as string[] | undefined) ?? []),
    ],
    current_batch_symbols: [
      ...((merged.current_batch_symbols as string[] | undefined) ?? []),
      ...((current.current_batch_symbols as string[] | undefined) ?? []),
    ],
    symbols: Array.from(new Map<string, SimulatedTradingSymbolDiagnosis>([
      ...((merged.symbols ?? [])),
      ...((current.symbols ?? [])),
    ].map((diagnosis): [string, SimulatedTradingSymbolDiagnosis] => [diagnosis.symbol, diagnosis])).values()),
    selected_symbols: Array.from(new Set([
      ...((merged.selected_symbols ?? [])),
      ...((current.selected_symbols ?? [])),
    ])),
    summary: mergeDiagnosisSummaries([merged.summary, current.summary]),
    schema_version: current.schema_version ?? merged.schema_version,
    session_id: current.session_id ?? merged.session_id,
    as_of: current.as_of ?? merged.as_of,
    coverage_complete: (merged.coverage_complete ?? true) && (current.coverage_complete ?? true),
  } as OrderBookSignalDiagnostics), {} as OrderBookSignalDiagnostics);

  return {
    signals: pageSignals,
    pagination: {
      page: currentPage,
      limit: perPage,
      total,
      total_pages: totalPages,
      has_next: currentPage < totalPages,
      has_prev: currentPage > 1,
    },
    total_analyzed: totalAnalyzed,
    active_signals: activeSignals,
    last_updated: lastUpdated,
    average_strength: averageStrength,
    ...(diagnostics ? { diagnostics } : {}),
  };
}


export function useOrderBookSignals(
  symbols?: string[],
  enabled: boolean = true,
  page: number = 1,
  perPage: number = 10,
  strategy?: string,
  mode: 'live' | 'simulated' = 'live',
  sessionId?: string,
) {
  // Enable query when trading is active, even if symbols aren't loaded yet
  // This allows WebSocket updates to populate the widget immediately
  const isEnabled = enabled;
  const requestSymbols = symbols && symbols.length > 0
    ? Array.from(new Set(symbols)).sort()
    : undefined;

  return useQuery({
    queryKey: ['orderbook-signals', mode, requestSymbols, page, perPage, strategy, sessionId],
    queryFn: async () => {
      if (requestSymbols && requestSymbols.length > ORDERBOOK_SYMBOL_CHUNK_SIZE) {
        const chunks = chunkOrderBookSymbols(requestSymbols);
        const chunkRequests = chunks.map((chunk) =>
          // Fetch every selected symbol in each request chunk, then apply widget
          // pagination after merging. The page size controls display only; it
          // must not cap selected-universe signal coverage.
          sessionId
            ? apiClient.getOrderBookSignals(chunk, { page: 1, per_page: chunk.length }, mode, sessionId)
            : apiClient.getOrderBookSignals(chunk, { page: 1, per_page: chunk.length }, mode)
        );
        const settled = await Promise.allSettled(chunkRequests);
        const successfulResponses = settled
          .filter((result): result is PromiseFulfilledResult<Awaited<typeof chunkRequests[number]>> => result.status === 'fulfilled')
          .map((result) => result.value)
          .filter((response) => response.status === 'success' && response.data);
        const failedChunks = settled.flatMap((result, index) => {
          if (result.status === 'rejected' || result.value.status === 'error') {
            return chunks[index];
          }
          return [];
        });

        if (successfulResponses.length === 0 && failedChunks.length > 0) {
          throw new Error(`Order-book signal requests failed for ${failedChunks.length} selected symbols`);
        }

        const merged = mergeOrderBookSignalResponses(
          successfulResponses
            .map((response) => response.data)
            .filter((data): data is OrderBookSignalsData => Boolean(data)),
          page,
          perPage
        );
        if (failedChunks.length > 0) {
          merged.diagnostics = {
            ...(merged.diagnostics ?? {}),
            failed_request_symbol_count: failedChunks.length,
            failed_request_symbols: failedChunks,
            coverage_complete: false,
          };
        }
        return merged;
      }

      const response = await (sessionId
        ? apiClient.getOrderBookSignals(requestSymbols, { page, per_page: perPage }, mode, sessionId)
        : apiClient.getOrderBookSignals(requestSymbols, { page, per_page: perPage }, mode));
      if (response.status === 'error') {
        throw new Error(response.error || 'Failed to fetch order book signals');
      }
      return response.data;
    },
    enabled: isEnabled,
    staleTime: 3000, // Consider data fresh for 3 seconds
    refetchInterval: enabled ? 3000 : false, // Keep signals moving in active simulation sessions
    refetchOnWindowFocus: true,
    refetchOnMount: 'always', // Always refetch when component mounts
  });
}

// Live Portfolio Hook
export function useLivePortfolio(enabled: boolean = true) {
  return useQuery({
    queryKey: ['live-portfolio-status'],
    queryFn: async () => {
      const response = await apiClient.getLivePortfolioStatus();
      if (response.status === 'error') {
        throw new Error(response.error || 'Failed to fetch live portfolio status');
      }
      return response.data;
    },
    enabled,
    staleTime: 5 * 1000, // 5 seconds
    refetchInterval: enabled ? 10 * 1000 : false, // Refresh every 10 seconds
  });
}

export function useLiveTabProducer(enabled: boolean = true) {
  return useQuery({
    queryKey: ['live-tab-producer'],
    queryFn: async () => {
      const response = await apiClient.getLiveTabProducerStatus();
      if (response.status === 'error') {
        throw new Error(response.error || 'Failed to fetch live tab producer status');
      }
      return response.data;
    },
    enabled,
    staleTime: 5 * 1000,
    refetchInterval: enabled ? 10 * 1000 : false,
    refetchOnWindowFocus: true,
  });
}

// Simulated Trading Statistics Hook

export function useSimulatedTradingStats(enabled: boolean = true) {
  return useQuery({
    queryKey: ['simulated-trading-stats'],
    queryFn: async () => {
      const response = await apiClient.getSimulatedTradingStatus();
      if (response.status === 'error') {
        throw new Error(response.error || 'Failed to fetch simulated trading stats');
      }
      return response.data;
    },
    enabled,
    staleTime: 2 * 1000, // 2 seconds - consider data fresh for 2 seconds
    refetchInterval: enabled ? 3 * 1000 : false, // Refresh every 3 seconds when enabled for near real-time updates
    refetchOnWindowFocus: true, // Refetch when tab becomes visible again
  });
}

export function useSimulatedTradingDiagnosis(enabled: boolean = true, sessionId?: string) {
  return useQuery({
    queryKey: ['simulated-trading-diagnosis', sessionId],
    queryFn: async () => {
      const response = await apiClient.getSimulatedTradingDiagnosis(sessionId);
      if (response.status === 'error') {
        throw new Error(response.error || 'Failed to fetch simulated trading diagnosis');
      }
      return response.data ?? undefined;
    },
    enabled,
    staleTime: 2 * 1000,
    refetchInterval: enabled ? 3 * 1000 : false,
    refetchOnWindowFocus: true,
  });
}

// Simulated Trading WebSocket Hook

export function useSimTradingWebSocket(enabled: boolean = true, sessionId?: string) {
  const [connected, setConnected] = useState(false);
  const queryClient = useQueryClient();

  // Apply every incoming signal to the display cache immediately. Coinbase
  // pacing is enforced server-side; the UI must not throttle signal updates.
  const applySignals = useCallback((incomingSignals: OrderBookSignal[]) => {
    if (incomingSignals.length === 0) {
      return;
    }

    const allQueries = queryClient.getQueryCache().getAll();
    const orderbookQueries = allQueries.filter((q) =>
      q.queryKey[0] === 'orderbook-signals' && q.queryKey[1] === 'simulated'
    );

    orderbookQueries.forEach((query) => {
      const queryKey = query.queryKey;
      const querySymbols = queryKey[2] as string[] | undefined;
      const querySessionId = queryKey[6] as string | undefined;
      const page = queryKey[3] as number;

      if (page !== 1) {
        return;
      }

      const relevantSignals = incomingSignals.filter((signal) =>
        (!querySymbols || querySymbols.length === 0 || querySymbols.includes(signal.symbol)) &&
        (!querySessionId || !signal.session_id || signal.session_id === querySessionId)
      );
      if (relevantSignals.length === 0) {
        return;
      }

      queryClient.setQueryData<OrderBookSignalsData>(queryKey, (oldData) => {
        const currentSignals = oldData?.signals || [];

        // Merge by symbol, keeping whichever signal has the freshest timestamp
        const signalMap = new Map<string, OrderBookSignal>();
        currentSignals.forEach((s: OrderBookSignal) => signalMap.set(s.symbol, s));
        relevantSignals.forEach((signal) => {
          const existingSignal = signalMap.get(signal.symbol);
          if (!existingSignal || new Date(signal.timestamp) > new Date(existingSignal.timestamp)) {
            signalMap.set(signal.symbol, signal);
          }
        });

        const updatedSignals = Array.from(signalMap.values()).sort((a, b) =>
          new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
        );
        const latestTimestamp = updatedSignals.reduce((latest, signal) => {
          return !latest || new Date(signal.timestamp).getTime() > new Date(latest).getTime()
            ? signal.timestamp
            : latest;
        }, '');

        if (!oldData) {
          return {
            signals: updatedSignals,
            total_analyzed: updatedSignals.length,
            active_signals: updatedSignals.filter(s => s.signal_generated).length,
            average_strength: updatedSignals.length === 0
              ? 0
              : updatedSignals.reduce((sum, s) => sum + (s.signal_strength ?? 0), 0) / updatedSignals.length,
            last_updated: latestTimestamp,
            pagination: {
              current_page: 1,
              per_page: 100, // Default to larger page size for live view
              total_signals: updatedSignals.length,
              total_pages: 1,
              has_next: false,
              has_prev: false
            }
          };
        }

        return {
          ...oldData,
          signals: updatedSignals,
          total_analyzed: updatedSignals.length,
          active_signals: updatedSignals.filter(s => s.signal_generated).length,
          last_updated: latestTimestamp,
          pagination: {
            ...oldData.pagination,
            total_signals: updatedSignals.length,
            // Update total pages based on current per_page setting
            total_pages: Math.ceil(updatedSignals.length / (oldData.pagination?.per_page || 10))
          }
        };
      });
    });
  }, [queryClient]);

  useEffect(() => {
    if (!enabled) {
      return;
    }

    const base = process.env.NEXT_PUBLIC_WS_URL || 'http://localhost:8081';
    const wsUrl = base.replace('http://', 'ws://').replace('https://', 'wss://') + '/ws';


    const ws = new WebSocket(wsUrl);
    let pingInterval: NodeJS.Timeout | null = null;
    let connectionTimeout: NodeJS.Timeout | null = null;
    const startHeartbeat = () => {
      // Send ping every 30 seconds to prevent connection timeout
      pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          try {
            ws.send(JSON.stringify({ type: 'ping' }));
          } catch (error) {
            console.error('❌ Failed to send ping:', error);
          }
        }
      }, 30000);
    };

    const onOpen = () => {
      setConnected(true);
      startHeartbeat();
    };

    const onClose = (event: CloseEvent) => {
      if (!event.wasClean) {
        console.warn('WebSocket connection closed unexpectedly:', event.code, event.reason);
      }
      setConnected(false);
      if (pingInterval) {
        clearInterval(pingInterval);
        pingInterval = null;
      }
      if (connectionTimeout) {
        clearTimeout(connectionTimeout);
        connectionTimeout = null;
      }
    };

    const onError = (event: Event) => {
      console.error('💥 WebSocket connection error:', event);
      setConnected(false);
      if (pingInterval) {
        clearInterval(pingInterval);
        pingInterval = null;
      }
      if (connectionTimeout) {
        clearTimeout(connectionTimeout);
        connectionTimeout = null;
      }
    };

    const onMessage = (event: MessageEvent) => {
      try {
        const payload = parseWebSocketPayload(event.data);
        const type = payload?.type ?? payload?.event_type;
        const data = payload?.data ?? payload;

        if (type === 'pong') {
          return;
        }

        // Push trading statistics into cache for instant UI updates
        const eventSessionId = isRecord(data) && typeof data.session_id === 'string'
          ? data.session_id
          : undefined;
        if (sessionId && eventSessionId && eventSessionId !== sessionId) {
          return;
        }

        if (type === 'simulated_trading.symbol_diagnosis' && isRecord(data)) {
          const diagnosisValue = data.diagnosis;
          const symbol = typeof data.symbol === 'string'
            ? data.symbol
            : isRecord(diagnosisValue) && typeof diagnosisValue.symbol === 'string'
              ? diagnosisValue.symbol
              : '';
          const sequence = typeof data.sequence === 'number' ? data.sequence : undefined;
          if (symbol && sequence !== undefined && isRecord(diagnosisValue)) {
            const diagnosis = {
              ...diagnosisValue,
              symbol,
              sequence: typeof diagnosisValue.sequence === 'number'
                ? diagnosisValue.sequence
                : sequence,
            } as SimulatedTradingSymbolDiagnosis;
            const diagnosisEvent: SimulatedTradingDiagnosisEvent = {
              event_type: type,
              ...(eventSessionId ? { session_id: eventSessionId } : {}),
              symbol,
              sequence,
              diagnosis,
            };
            const diagnosisQueryKey = ['simulated-trading-diagnosis', eventSessionId ?? sessionId];
            queryClient.setQueryData<OrderBookSignalDiagnostics>(diagnosisQueryKey, (current) =>
              applySimulatedTradingDiagnosisEvent(current, diagnosisEvent));
            window.dispatchEvent(new CustomEvent('sim-trading-diagnosis-update', { detail: diagnosisEvent }));
          }
          return;
        }

        if (type === 'trading_statistics_update' && data) {
          // Expect { portfolio, open_positions, recent_trades, ... }
          // Normalize to the shape expected by useSimulatedTradingStats consumer
          const normalized = {
            ...data,
          };
          // Update the stats query cache
          try {
            queryClient.setQueryData(['simulated-trading-stats'], normalized);
          } catch (e) {
            console.error('❌ Failed to update trading stats cache:', e);
          }
          // Also emit a custom event for components not using React Query
          window.dispatchEvent(new CustomEvent('sim-trading-stats-update', { detail: normalized }));
        }

        // Handle log messages
        if (type === 'log_message' && data) {
          window.dispatchEvent(new CustomEvent('bot-log-message', { detail: data }));
        }

        // Apply orderbook signals to the display cache as soon as they arrive
        if (type === 'orderbook_signals_update' && data) {
          try {
            // Handle both array of signals (from signals key) or single signal object
            const signalsList = isRecord(data) && Array.isArray(data.signals)
              ? data.signals
              : (Array.isArray(data) ? data : [data]);

            if (!signalsList || signalsList.length === 0) return;

            const validSignals = signalsList.filter((newSignal): newSignal is OrderBookSignal =>
              isRecord(newSignal) && typeof newSignal.symbol === 'string'
            );

            applySignals(validSignals);
          } catch (e) {
            console.error('❌ Failed to apply orderbook signals:', e);
          }
        }
      } catch (e) {
        console.error('❌ Failed to parse WebSocket message:', e);
      }
    };

    ws.addEventListener('open', onOpen);
    ws.addEventListener('close', onClose);
    ws.addEventListener('error', onError);
    ws.addEventListener('message', onMessage);

    // Set timeout for initial connection
    connectionTimeout = setTimeout(() => {
      if (ws.readyState !== WebSocket.OPEN) {
        console.warn('⚠️ WebSocket connection timeout, closing...');
        try {
          ws.close();
        } catch (error) {
          console.error('❌ Error closing timed out connection:', error);
        }
      }
    }, 10000); // 10 second connection timeout

    return () => {
      if (pingInterval) {
        clearInterval(pingInterval);
      }
      if (connectionTimeout) {
        clearTimeout(connectionTimeout);
      }
      try { ws.removeEventListener('open', onOpen); } catch { }
      try { ws.removeEventListener('close', onClose); } catch { }
      try { ws.removeEventListener('error', onError); } catch { }
      try { ws.removeEventListener('message', onMessage); } catch { }
      try { ws.close(); } catch { }
    };
  }, [enabled, queryClient, applySignals, sessionId]);

  return {
    connected,
  };
}

// Products/Symbols Hook

export function useProducts() {
  return useQuery({
    queryKey: ['products'],
    queryFn: async () => {
      const response = await apiClient.getProducts();
      if (response.status === 'error') {
        throw new Error(response.error || 'Failed to fetch products');
      }
      return response.data?.categories || {};
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

// ML Models Hook

export function useMLModels(enabled: boolean = true) {
  return useQuery({
    queryKey: ['ml-models'],
    queryFn: async () => {
      const response = await apiClient.getMLModels();
      if (response.status === 'error') {
        throw new Error(response.error || 'Failed to fetch ML models');
      }
      return response.data;
    },
    enabled,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}



// Backtesting Hook

export function useBacktest() {
  return useMutation({
    mutationFn: (config: {
      strategy: TradingStrategy;
      symbols: string[];
      parameters: TradingParameters;
      start_date: string;
      end_date: string;
    }) => apiClient.runBacktest(config),
  });
}

// Strategy Parameters Hook (computed, not from API)

export function useStrategyParameters() {
  const getStrategyParameters = (strategy: TradingStrategy) => {
    const parameters = {
      'sma': [
        { name: 'short_window', label: 'Short Window', type: 'number' as const, default: 10, min: 2, max: 100 },
        { name: 'long_window', label: 'Long Window', type: 'number' as const, default: 20, min: 5, max: 200 }
      ],
      'ema': [
        { name: 'short_window', label: 'Short Window', type: 'number' as const, default: 10, min: 2, max: 100 },
        { name: 'long_window', label: 'Long Window', type: 'number' as const, default: 20, min: 5, max: 200 }
      ],
      'rsi': [
        { name: 'window', label: 'RSI Window', type: 'number' as const, default: 14, min: 5, max: 50 },
        { name: 'overbought', label: 'Overbought Level', type: 'number' as const, default: 70, min: 60, max: 90 },
        { name: 'oversold', label: 'Oversold Level', type: 'number' as const, default: 30, min: 10, max: 40 }
      ],
      'bollinger': [
        { name: 'window', label: 'Window', type: 'number' as const, default: 20, min: 5, max: 100 },
        { name: 'std_dev', label: 'Standard Deviations', type: 'number' as const, default: 2, min: 1, max: 3, step: 0.1 }
      ],
      'macd': [
        { name: 'fast_window', label: 'Fast Window', type: 'number' as const, default: 12, min: 5, max: 50 },
        { name: 'slow_window', label: 'Slow Window', type: 'number' as const, default: 26, min: 10, max: 100 },
        { name: 'signal_window', label: 'Signal Window', type: 'number' as const, default: 9, min: 5, max: 30 }
      ],
      'stochastic': [
        { name: 'k_window', label: 'K Window', type: 'number' as const, default: 14, min: 5, max: 50 },
        { name: 'd_window', label: 'D Window', type: 'number' as const, default: 3, min: 2, max: 10 },
        { name: 'overbought', label: 'Overbought Level', type: 'number' as const, default: 80, min: 70, max: 90 },
        { name: 'oversold', label: 'Oversold Level', type: 'number' as const, default: 20, min: 10, max: 30 }
      ],
      'fibonacci': [
        { name: 'fib_lookback_period', label: 'Lookback Period', type: 'number' as const, default: 20, min: 10, max: 100 },
        { name: 'fib_levels', label: 'Fibonacci Levels', type: 'text' as const, default: '0.236,0.382,0.5,0.618,0.786' },
        { name: 'fib_confirmation_candles', label: 'Confirmation Candles', type: 'number' as const, default: 2, min: 1, max: 5 }
      ],
      'ml_enhanced_orderbook': [
        { name: 'ml_server_url', label: 'ML Server URL', type: 'text' as const, default: 'http://localhost:8002' },
        { name: 'confidence_threshold', label: 'Confidence Threshold', type: 'number' as const, default: 0.6, min: 0, max: 1, step: 0.1 },
        { name: 'fallback_to_baseline', label: 'Fallback to Baseline', type: 'select' as const, default: 'true', options: ['true', 'false'] },
        { name: 'order_book_level', label: 'Order Book Level', type: 'number' as const, default: 2, min: 1, max: 3 },
        { name: 'trade_history_limit', label: 'Trade History Limit', type: 'number' as const, default: 1000, min: 10, max: 1000 },
        { name: 'bid_ask_spread_threshold', label: 'Bid-Ask Spread Threshold (%)', type: 'number' as const, default: 0.5, min: 0.01, max: 1.0, step: 0.01 },
        { name: 'volume_imbalance_threshold', label: 'Volume Imbalance Threshold', type: 'number' as const, default: 0.3, min: 0.1, max: 0.9, step: 0.1 },
        { name: 'large_trade_threshold', label: 'Large Trade Threshold ($)', type: 'number' as const, default: 2000, min: 1000, max: 100000 },
        { name: 'data_analysis_mode', label: 'Data Analysis Mode', type: 'select' as const, default: 'all', options: ['recent', 'all', 'sampled'] },
        { name: 'recent_data_limit', label: 'Recent Data Limit', type: 'number' as const, default: 200, min: 10, max: 1000 },
        { name: 'sampling_ratio', label: 'Sampling Ratio', type: 'number' as const, default: 0.1, min: 0.01, max: 1.0, step: 0.01 },
        { name: 'max_symbols_per_request', label: 'Max Symbols Per Request', type: 'number' as const, default: 1000, min: 10, max: 10000 },
        { name: 'max_universe_size', label: 'Max Universe Size', type: 'number' as const, default: 500, min: 1, max: 5000 },
        { name: 'round_trip_fee_percent', label: 'Round-Trip Fee Hurdle (%)', type: 'number' as const, default: 1.5, min: 0, max: 5, step: 0.1 },
        { name: 'slippage_buffer_percent', label: 'Slippage Buffer (%)', type: 'number' as const, default: 0.2, min: 0, max: 5, step: 0.1 },
        { name: 'min_orderbook_signal_strength', label: 'Minimum Fee-Adjusted Signal Strength', type: 'number' as const, default: 0.22, min: 0, max: 1, step: 0.01 },
        { name: 'minimum_net_pnl_usd', label: 'Minimum Net P&L Per Trade ($)', type: 'number' as const, default: 0, min: 0, max: 100, step: 0.01 },
        { name: 'allow_unprofitable_trades', label: 'Allow Unprofitable Sim Trades', type: 'select' as const, default: 'false', options: ['true', 'false'] },
        { name: 'max_positions_per_session', label: 'Max Positions Per Session', type: 'number' as const, default: 100, min: 1, max: 1000 }
      ],
      'orderbook': [
        { name: 'order_book_level', label: 'Order Book Level', type: 'number' as const, default: 2, min: 1, max: 3 },
        { name: 'trade_history_limit', label: 'Trade History Limit', type: 'number' as const, default: 1000, min: 10, max: 1000 },
        { name: 'bid_ask_spread_threshold', label: 'Bid-Ask Spread Threshold (%)', type: 'number' as const, default: 0.5, min: 0.01, max: 1.0, step: 0.01 },
        { name: 'volume_imbalance_threshold', label: 'Volume Imbalance Threshold', type: 'number' as const, default: 0.3, min: 0.1, max: 0.9, step: 0.1 },
        { name: 'large_trade_threshold', label: 'Large Trade Threshold ($)', type: 'number' as const, default: 2000, min: 1000, max: 100000 },
        { name: 'data_analysis_mode', label: 'Data Analysis Mode', type: 'select' as const, default: 'all', options: ['recent', 'all', 'sampled'] },
        { name: 'recent_data_limit', label: 'Recent Data Limit', type: 'number' as const, default: 200, min: 10, max: 1000 },
        { name: 'sampling_ratio', label: 'Sampling Ratio', type: 'number' as const, default: 0.1, min: 0.01, max: 1.0, step: 0.01 },
        { name: 'max_symbols_per_request', label: 'Max Symbols Per Request', type: 'number' as const, default: 1000, min: 10, max: 10000 },
        { name: 'max_universe_size', label: 'Max Universe Size', type: 'number' as const, default: 500, min: 1, max: 5000 },
        { name: 'round_trip_fee_percent', label: 'Round-Trip Fee Hurdle (%)', type: 'number' as const, default: 1.5, min: 0, max: 5, step: 0.1 },
        { name: 'slippage_buffer_percent', label: 'Slippage Buffer (%)', type: 'number' as const, default: 0.2, min: 0, max: 5, step: 0.1 },
        { name: 'min_orderbook_signal_strength', label: 'Minimum Fee-Adjusted Signal Strength', type: 'number' as const, default: 0.22, min: 0, max: 1, step: 0.01 },
        { name: 'max_positions_per_session', label: 'Max Positions Per Session', type: 'number' as const, default: 100, min: 1, max: 1000 }
      ],
      'dca': [
        { name: 'interval_hours', label: 'Interval (Hours)', type: 'number' as const, default: 24, min: 1, max: 168 },
        { name: 'amount', label: 'Amount per Interval', type: 'number' as const, default: 100, min: 10, max: 10000 }
      ],
      'buyandhold': [
        { name: 'amount', label: 'Investment Amount', type: 'number' as const, default: 1000, min: 100, max: 100000 }
      ]
    };

    return parameters[strategy] || [];
  };

  const getOrderBookPresets = () => ({
    'conservative': {
      order_book_level: 2,
      trade_history_limit: 100,
      bid_ask_spread_threshold: 0.1,
      volume_imbalance_threshold: 0.6,
      large_trade_threshold: 10000,
      data_analysis_mode: 'recent',
      recent_data_limit: 50,
      sampling_ratio: 0.1,
      round_trip_fee_percent: 1.5,
      slippage_buffer_percent: 0.2,
      min_orderbook_signal_strength: 0.6,
      max_positions_per_session: 25,
      minimum_net_pnl_usd: 0.25,
      allow_unprofitable_trades: 'false'
    },
    'moderate': {
      order_book_level: 2,
      trade_history_limit: 500,
      bid_ask_spread_threshold: 0.2,
      volume_imbalance_threshold: 0.4,
      large_trade_threshold: 5000,
      data_analysis_mode: 'recent',
      recent_data_limit: 100,
      sampling_ratio: 0.1,
      round_trip_fee_percent: 1.5,
      slippage_buffer_percent: 0.2,
      min_orderbook_signal_strength: 0.4,
      max_positions_per_session: 100,
      minimum_net_pnl_usd: 0.1,
      allow_unprofitable_trades: 'false'
    },
    'aggressive': {
      order_book_level: 2,
      trade_history_limit: 1000,
      bid_ask_spread_threshold: 0.5,
      volume_imbalance_threshold: 0.3,
      large_trade_threshold: 2000,
      data_analysis_mode: 'all',
      recent_data_limit: 200,
      sampling_ratio: 0.1,
      round_trip_fee_percent: 1.5,
      slippage_buffer_percent: 0.2,
      min_orderbook_signal_strength: 0.22,
      max_positions_per_session: 100,
      minimum_net_pnl_usd: 0,
      allow_unprofitable_trades: 'false'
    },
    'very-aggressive': {
      order_book_level: 2,
      trade_history_limit: 1000,
      bid_ask_spread_threshold: 1.0,
      volume_imbalance_threshold: 0.2,
      large_trade_threshold: 1000,
      data_analysis_mode: 'all',
      recent_data_limit: 500,
      sampling_ratio: 0.1,
      round_trip_fee_percent: 1.5,
      slippage_buffer_percent: 0.2,
      min_orderbook_signal_strength: 0.15,
      max_positions_per_session: 250,
      minimum_net_pnl_usd: 0,
      allow_unprofitable_trades: 'false'
    }
  });

  return {
    getStrategyParameters,
    getOrderBookPresets,
  };
}
