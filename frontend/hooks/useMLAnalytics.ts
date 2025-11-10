import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { MLDashboardData } from '@/types/trading';
import { apiClient } from '@/lib/api';

export function useMLAnalytics() {
  const [sortBy, setSortBy] = useState('pnl');
  const {
    data: mlData,
    isLoading,
    error,
    refetch
  } = useQuery({
    queryKey: ['ml', 'dashboard'],
    queryFn: async (): Promise<MLDashboardData> => {
      const response = await apiClient.getMLDashboard();
      if (response.status === 'error' || !response.data) {
        throw new Error(response.error || 'Failed to fetch ML dashboard data');
      }
      return response.data;
    },
    refetchInterval: 30000, // Refetch every 30 seconds
    staleTime: 25000, // Consider data stale after 25 seconds
  });

  const {
    data: pnlTradesData,
    isLoading: isPnlLoading,
    error: pnlError,
  } = useQuery({
    queryKey: ['ml', 'pnlTrades', sortBy],
    queryFn: async () => {
      const response = await apiClient.getPnlTrades(sortBy);
      if (response.status === 'error' || !response.data) {
        throw new Error(response.error || 'Failed to fetch PnL trades data');
      }
      return response.data;
    },
    refetchInterval: 60000, // Refetch every 60 seconds
    staleTime: 55000,
  });

  const comparePredictionsMutation = useMutation({
    mutationFn: async (features: any) => {
      const response = await apiClient.getPredictionComparison(features);
      if (response.status === 'error' || !response.data) {
        throw new Error(response.error || 'Failed to fetch prediction comparison');
      }
      return response.data;
    },
  });

  return {
    mlData,
    isLoading,
    error: error as Error | null,
    refetch,
    // Convenience getters
    modelStatus: mlData?.status,
    performance: mlData?.performance,
    featureImportance: mlData?.feature_importance,
    pnlTrades: pnlTradesData,
    isPnlLoading,
    pnlError,
    sortBy,
    setSortBy,
    comparePredictions: comparePredictionsMutation.mutate,
    isComparing: comparePredictionsMutation.isPending,
    comparisonData: comparePredictionsMutation.data,
  };
}
