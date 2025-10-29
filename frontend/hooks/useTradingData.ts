import { useQuery } from '@tanstack/react-query';
import { apiClient, queryKeys } from '@/lib/api';
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
          // Convert portfolio data to stats
          const portfolio = (response.data as any).portfolio;
          const trades = portfolio.trades || [];
          const totalTrades = trades.length;
          const totalPnl = portfolio.total_pnl || 0;
          const winningTrades = trades.filter((t: any) => (t.pnl || 0) > 0).length;
          const winRate = totalTrades > 0 ? (winningTrades / totalTrades) * 100 : 0;

          const result: TradingStats = {
            total_pnl: totalPnl,
            total_fees: portfolio.total_fees || 0,
            net_pnl: totalPnl - (portfolio.total_fees || 0),
            win_rate: winRate,
            total_trades: totalTrades,
            winning_trades: winningTrades,
            losing_trades: totalTrades - winningTrades,
            avg_win: 0,
            avg_loss: 0,
            best_trade: 0,
            worst_trade: 0,
            profit_factor: 0,
            sharpe_ratio: 0,
            max_drawdown: portfolio.max_drawdown || 0,
            total_volume: 0,
            avg_trade_size: 0,
            trades_today: 0,
          };
          return result;
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
