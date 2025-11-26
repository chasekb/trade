import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { MLTrainingResponse } from '@/types/trading';
import { apiClient } from '@/lib/api';

// Custom toast hook - can be replaced with react-hot-toast or any toast provider
const useToast = () => {
  const showSuccess = (message: string) => {
    console.log('✅', message);
    // In a real app, this would show a toast notification
  };

  const showError = (message: string) => {
    console.error('❌', message);
    // In a real app, this would show an error toast
  };

  return { showSuccess, showError };
};

export function useModelTraining() {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();

  const trainMutation = useMutation({
    mutationFn: async (batchTraining?: boolean): Promise<MLTrainingResponse> => {
      const response = await apiClient.trainMLModel(batchTraining);
      if (response.status === 'error' || !response.data) {
        throw new Error(response.error || 'Failed to train model');
      }
      return response.data;
    },
    onSuccess: (data) => {
      if (data.status === 'success' || data.status === 'training_started') {
        showSuccess(data.message || 'Model training completed successfully');
        // Refetch ML dashboard data
        queryClient.invalidateQueries({ queryKey: ['ml', 'dashboard'] });
      } else {
        showError(data.error || 'Model training failed');
      }
    },
    onError: (error) => {
      showError(error.message || 'Failed to train model');
    },
  });

  const updateMutation = useMutation({
    mutationFn: async (): Promise<MLTrainingResponse> => {
      const response = await apiClient.updateMLModel();
      if (response.status === 'error' || !response.data) {
        throw new Error(response.error || 'Failed to update model');
      }
      return response.data;
    },
    onSuccess: (data) => {
      if (data.status === 'success') {
        showSuccess(data.message || 'Model updated successfully');
        queryClient.invalidateQueries({ queryKey: ['ml', 'dashboard'] });
      } else {
        showError(data.error || 'Model update failed');
      }
    },
    onError: (error) => {
      showError(error.message || 'Failed to update model');
    },
  });

  const rollbackMutation = useMutation({
    mutationFn: async (): Promise<MLTrainingResponse> => {
      // Show confirmation before proceeding
      if (!confirm('Are you sure you want to rollback to the previous model version?')) {
        throw new Error('Rollback cancelled by user');
      }

      const response = await apiClient.rollbackMLModel();
      if (response.status === 'error' || !response.data) {
        throw new Error(response.error || 'Failed to rollback model');
      }
      return response.data;
    },
    onSuccess: (data) => {
      if (data.status === 'success') {
        showSuccess(data.message || 'Model rolled back successfully');
        queryClient.invalidateQueries({ queryKey: ['ml', 'dashboard'] });
      } else {
        showError(data.error || 'Model rollback failed');
      }
    },
    onError: (error) => {
      if (error.message !== 'Rollback cancelled by user') {
        showError(error.message || 'Failed to rollback model');
      }
    },
  });

  const { data: availableModels, isLoading: isLoadingModels } = useQuery({
    queryKey: ['ml', 'models'],
    queryFn: async () => {
      const response = await apiClient.getAvailableModels();
      if (response.status === 'error' || !response.data) {
        throw new Error(response.error || 'Failed to fetch available models');
      }
      return response.data;
    },
  });

  const setActiveModelMutation = useMutation({
    mutationFn: async (modelName: string) => {
      const response = await apiClient.setActiveModel(modelName);
      if (response.status === 'error' || !response.data) {
        throw new Error(response.error || 'Failed to set active model');
      }
      return response.data;
    },
    onSuccess: (data) => {
      if (data.status === 'success') {
        showSuccess(data.message || 'Model activated successfully');
        queryClient.invalidateQueries({ queryKey: ['ml', 'dashboard'] });
      } else {
        showError(data.error || 'Failed to activate model');
      }
    },
    onError: (error) => {
      showError(error.message || 'Failed to set active model');
    },
  });

  return {
    // Training
    trainModel: trainMutation.mutate,
    isTraining: trainMutation.isPending,
    trainingError: trainMutation.error as Error | null,

    // Update
    updateModel: updateMutation.mutate,
    isUpdating: updateMutation.isPending,
    updatingError: updateMutation.error as Error | null,

    // Rollback
    rollbackModel: rollbackMutation.mutate,
    isRollingBack: rollbackMutation.isPending,
    rollbackError: rollbackMutation.error as Error | null,

    // Model Selection
    availableModels,
    isLoadingModels,
    setActiveModel: setActiveModelMutation.mutate,
    isSettingActiveModel: setActiveModelMutation.isPending,
  };
}
