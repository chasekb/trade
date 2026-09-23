import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';
import {
  ExecutionAttributionReport,
  normalizeExecutionAttribution,
} from '@/lib/executionAttribution';

export interface UseExecutionAttributionOptions {
  hours?: number;
  sessionId?: string;
  tradeType?: string;
  enabled?: boolean;
}

// Distinct from `useExecutionReconciliation` (blocker-mix reconciliation by
// strategy/symbol): this hook reads the execution-attribution endpoint,
// which breaks evaluated/blocked/executed intents down by strategy,
// diagnostic factor, symbol, side, strength bucket, and expected-return
// bucket. This is a diagnostic read: it never starts, stops, or authorizes
// trading.
export function useExecutionAttribution(options: UseExecutionAttributionOptions = {}) {
  const { hours = 24, sessionId, tradeType, enabled = true } = options;

  const query = useQuery<ExecutionAttributionReport>({
    queryKey: ['trading', 'executionAttribution', hours, sessionId ?? '', tradeType ?? ''],
    queryFn: async () => {
      const response = await apiClient.getExecutionAttribution({ hours, sessionId, tradeType });
      if (response.status === 'error' || !response.data) {
        throw new Error(response.error || 'Failed to fetch execution attribution');
      }
      return normalizeExecutionAttribution(response.data);
    },
    enabled,
    refetchInterval: 60000,
    staleTime: 55000,
  });

  return {
    report: query.data ?? null,
    isLoading: query.isLoading,
    error: query.error as Error | null,
    refetch: query.refetch,
  };
}
