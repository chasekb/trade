import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { MLDashboardData, MLConfig } from '@/types/trading';
import { apiClient } from '@/lib/api';

export function useMLAnalytics() {
  const queryClient = useQueryClient();
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

  const { data: mlConfig, isLoading: isConfigLoading } = useQuery<MLConfig, Error>({
    queryKey: ['mlConfig'],
    queryFn: async () => {
      const response = await apiClient.getMLConfig();
      if (response.status === 'error' || !response.data) {
        throw new Error(response.error || 'Failed to fetch ML config');
      }
      return response.data;
    },
  });

  const updateConfigMutation = useMutation({
    mutationFn: async (newConfig: Partial<MLConfig>) => {
      const response = await apiClient.updateMLConfig(newConfig);
      if (response.status === 'error') {
        throw new Error(response.error || 'Failed to update ML config');
      }
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mlConfig'] });
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
    mlConfig,
    isConfigLoading,
    updateMlConfig: updateConfigMutation.mutate,
    isUpdatingConfig: updateConfigMutation.isPending,
  };
}
