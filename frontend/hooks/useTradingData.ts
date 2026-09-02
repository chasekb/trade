import { useQuery } from '@tanstack/react-query';
import { apiClient, queryKeys } from '@/lib/api';
import { deriveStats, mergeStats } from '@/lib/simulatedTradingStats';
import { TradingStats, Position, PaginationParams } from '@/types/trading';

export function useTradingStats() {
  return useQuery({
    queryKey: queryKeys.tradingStats,
    queryFn: async (): Promise<TradingStats> => {
      const response = await apiClient.getTradingStats();
      if (response.status === 'error') {
        throw new Error(response.error || 'Failed to fetch trading stats');
      }

      if (!response.data) {
        throw new Error('No trading stats data received');
      }

      // Handle different backend response formats
      if (typeof response.data === 'object' && 'stats' in response.data) {
        // Format: { status: 'success', stats: {...} }
        return (response.data as any).stats;
      }

      if (typeof response.data === 'object' && ('total_trades' in response.data || 'portfolio' in response.data)) {
        // Format: Direct stats object or portfolio data
        if ((response.data as any).portfolio) {
          // Convert portfolio data to stats: derive every metric from the trade
          // list, then let any stats the portfolio explicitly provides win.
          const portfolio = (response.data as any).portfolio;
          const trades = (response.data as any).recent_trades || portfolio.trades || [];
          const derived = deriveStats(
            trades,
            portfolio.total_fees !== undefined ? Number(portfolio.total_fees) : undefined,
          );
          return mergeStats(portfolio as Partial<TradingStats>, derived);
        }

        return response.data as TradingStats;
      }

      throw new Error('Unexpected trading stats response format');
    },
    staleTime: 30 * 1000, // 30 seconds
    refetchInterval: 30 * 1000, // Refetch every 30 seconds
    retry: 3,
  });
}

export function usePositions(params?: PaginationParams) {
  return useQuery({
    queryKey: queryKeys.positions(params),
    queryFn: async () => {
      const response = await apiClient.getPositions(params);
      if (response.status === 'error') {
        throw new Error(response.error || 'Failed to fetch positions');
      }
      return response;
    },
    staleTime: 10 * 1000, // 10 seconds
    refetchInterval: 10 * 1000, // Refetch every 10 seconds
  });
}

export function useTradingHistory(params?: PaginationParams) {
  return useQuery({
    queryKey: queryKeys.tradingHistory(params),
    queryFn: async () => {
      const response = await apiClient.getTradingHistory(params);
      if (response.status === 'error') {
        throw new Error(response.error || 'Failed to fetch trading history');
      }
      return response;
    },
    staleTime: 60 * 1000, // 1 minute
    enabled: false, // Only fetch when explicitly requested
  });
}
