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

class ExecutionReconciliationError extends Error {
  readonly retryable: boolean;
  readonly requestId?: string;

  constructor(message: string, retryable: boolean, requestId?: string) {
    super(message);
    this.name = 'ExecutionReconciliationError';
    this.retryable = retryable;
    this.requestId = requestId;
  }
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
        throw new ExecutionReconciliationError(
          response.requestId
            ? `${response.error || 'Execution reconciliation is temporarily unavailable. Retry shortly.'} (request ${response.requestId})`
            : response.error || 'Execution reconciliation is temporarily unavailable. Retry shortly.',
          response.retryable === true,
          response.requestId,
        );
      }
      return normalizeExecutionReconciliation(response.data);
    },
    enabled,
    retry: (failureCount, error) =>
      error instanceof ExecutionReconciliationError && error.retryable && failureCount < 2,
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
