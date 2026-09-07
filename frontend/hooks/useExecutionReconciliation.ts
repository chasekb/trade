import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';
import {
  ExecutionReconciliationSnapshot,
  normalizeExecutionReconciliation,
} from '@/lib/executionReconciliation';

export interface UseExecutionReconciliationOptions {
  hours?: number;
  sessionId?: string;
  tradeType?: string;
  enabled?: boolean;
}

// Reconciles generated signals to execution outcomes by strategy and blocker
// bucket over a trailing window. This is a diagnostic read: it never starts,
// stops, or authorizes trading.
export function useExecutionReconciliation(options: UseExecutionReconciliationOptions = {}) {
  const { hours = 24, sessionId, tradeType, enabled = true } = options;

  const query = useQuery<ExecutionReconciliationSnapshot>({
    queryKey: ['trading', 'executionReconciliation', hours, sessionId ?? '', tradeType ?? ''],
    queryFn: async () => {
      const response = await apiClient.getExecutionReconciliation({ hours, sessionId, tradeType });
      if (response.status === 'error' || !response.data) {
        throw new Error(response.error || 'Failed to fetch execution reconciliation');
      }
      return normalizeExecutionReconciliation(response.data);
    },
    enabled,
    refetchInterval: 60000,
    staleTime: 55000,
  });

  return {
    reconciliation: query.data ?? null,
    isLoading: query.isLoading,
    error: query.error as Error | null,
    refetch: query.refetch,
  };
}
