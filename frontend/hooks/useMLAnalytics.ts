import { useQuery } from '@tanstack/react-query';
import { MLDashboardData } from '@/types/trading';
import { apiClient } from '@/lib/api';

export function useMLAnalytics() {
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

  return {
    mlData,
    isLoading,
    error: error as Error | null,
    refetch,
    // Convenience getters
    modelStatus: mlData?.status,
    performance: mlData?.performance,
    featureImportance: mlData?.feature_importance,
  };
}
