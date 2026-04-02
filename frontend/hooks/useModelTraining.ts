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

  const watchTrainingCompletion = () => {
    let attempts = 0;
    const maxAttempts = 120; // ~4 minutes at 2s interval
    const intervalId = setInterval(async () => {
      attempts += 1;
      try {
        const statusResp = await apiClient.getMLStatus();
        if (statusResp.status === 'error' || !statusResp.data) {
          if (attempts >= maxAttempts) {
            clearInterval(intervalId);
          }
          return;
        }

        const status = statusResp.data.status;
        if (status === 'completed') {
          clearInterval(intervalId);
          queryClient.invalidateQueries({ queryKey: ['ml', 'models'] });
          queryClient.invalidateQueries({ queryKey: ['ml', 'dashboard'] });
          return;
        }

        if (status === 'failed') {
          clearInterval(intervalId);
          queryClient.invalidateQueries({ queryKey: ['ml', 'dashboard'] });
          showError('Model training failed');
          return;
        }

        if (attempts >= maxAttempts) {
          clearInterval(intervalId);
        }
      } catch {
        if (attempts >= maxAttempts) {
          clearInterval(intervalId);
        }
      }
    }, 2000);
  };

  const trainMutation = useMutation({
    mutationFn: async (
      input?: boolean | { batchTraining?: boolean; autoSetActive?: boolean }
    ): Promise<MLTrainingResponse> => {
      const batchTraining = typeof input === 'boolean' ? input : input?.batchTraining;
      const autoSetActive = typeof input === 'boolean' ? undefined : input?.autoSetActive;

      const response = await apiClient.trainMLModel(batchTraining, autoSetActive);
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
        watchTrainingCompletion();
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

  const deleteModelMutation = useMutation({
    mutationFn: async (modelName: string) => {
      if (!confirm(`Are you sure you want to delete model "${modelName}"? This action cannot be undone.`)) {
        throw new Error('Deletion cancelled by user');
      }
      const response = await apiClient.deleteModel(modelName);
      if (response.status === 'error' || !response.data) {
        throw new Error(response.error || 'Failed to delete model');
      }
      return response.data;
    },
    onSuccess: (data) => {
      if (data.status === 'success') {
        showSuccess(data.message || 'Model deleted successfully');
        queryClient.invalidateQueries({ queryKey: ['ml', 'models'] });
        queryClient.invalidateQueries({ queryKey: ['ml', 'dashboard'] });
      } else {
        showError(data.error || 'Failed to delete model');
      }
    },
    onError: (error) => {
      if (error.message !== 'Deletion cancelled by user') {
        showError(error.message || 'Failed to delete model');
      }
    },
  });

  const deleteAllModelsMutation = useMutation({
    mutationFn: async () => {
      if (!confirm('Are you sure you want to delete ALL models? This action cannot be undone and will remove all trained models.')) {
        throw new Error('Deletion cancelled by user');
      }
      const response = await apiClient.deleteAllModels();
      if (response.status === 'error' || !response.data) {
        throw new Error(response.error || 'Failed to delete all models');
      }
      return response.data;
    },
    onSuccess: (data) => {
      if (data.status === 'success') {
        showSuccess(data.message || 'All models deleted successfully');
        queryClient.invalidateQueries({ queryKey: ['ml', 'models'] });
        queryClient.invalidateQueries({ queryKey: ['ml', 'dashboard'] });
      } else {
        showError(data.error || 'Failed to delete all models');
      }
    },
    onError: (error) => {
      if (error.message !== 'Deletion cancelled by user') {
        showError(error.message || 'Failed to delete all models');
      }
    },
  });

  const resetDatabasesMutation = useMutation({
    mutationFn: async () => {
      if (!confirm('Are you sure you want to RESET ALL DATABASES? This will delete all training data, trading history, and cache. This action CANNOT be undone.')) {
        throw new Error('Reset cancelled by user');
      }
      const response = await apiClient.resetDatabases();
      if (response.status === 'error' || !response.data) {
        throw new Error(response.error || 'Failed to reset databases');
      }
      return response.data;
    },
    onSuccess: (data) => {
      if (data.status === 'success') {
        showSuccess(data.message || 'Databases reset successfully');
        // Invalidate all relevant queries
        queryClient.invalidateQueries({ queryKey: ['ml'] });
        queryClient.invalidateQueries({ queryKey: ['trading'] });
      } else {
        showError(data.error || 'Failed to reset databases');
      }
    },
    onError: (error) => {
      if (error.message !== 'Reset cancelled by user') {
        showError(error.message || 'Failed to reset databases');
      }
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
    
    // Deletion
    deleteModel: deleteModelMutation.mutate,
    isDeletingModel: deleteModelMutation.isPending,
    deleteAllModels: deleteAllModelsMutation.mutate,
    isDeletingAllModels: deleteAllModelsMutation.isPending,
    
    // Reset Databases
    resetDatabases: resetDatabasesMutation.mutate,
    isResettingDatabases: resetDatabasesMutation.isPending,
  };
}
