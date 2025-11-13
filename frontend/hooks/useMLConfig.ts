'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';
import { MLConfig } from '@/types/trading';

export const useMLConfig = () => {
  const queryClient = useQueryClient();

  const { data: mlConfig, isLoading: isLoadingMLConfig } = useQuery<MLConfig, Error>({
    queryKey: ['mlConfig'],
    queryFn: async () => {
      const response = await apiClient.getMLConfig();
      if (response.status === 'error') {
        throw new Error(response.error);
      }
      return response.data;
    },
  });

  const { mutate: updateMLConfig, isPending: isUpdatingMLConfig } = useMutation<
    void,
    Error,
    Partial<MLConfig>
  >({
    mutationFn: async (newConfig) => {
      const response = await apiClient.updateMLConfig(newConfig);
      if (response.status === 'error') {
        throw new Error(response.error);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mlConfig'] });
    },
  });

  return {
    mlConfig,
    isLoadingMLConfig,
    updateMLConfig,
    isUpdatingMLConfig,
  };
};
