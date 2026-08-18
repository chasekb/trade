import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { DashboardGrid } from '@/components/layout/DashboardGrid';
import { cn } from '@/lib/utils';
import { useMLAnalytics } from '@/hooks/useMLAnalytics';
import { useModelTraining } from '@/hooks/useModelTraining';
import { PnlTradesTable } from './PnlTradesTable';
import { PredictionComparisonChart } from './PredictionComparisonChart';

interface ModelStatusCardProps {
  status: import('@/types/trading').MLModelStatus;
}

function ModelStatusCard({ status }: ModelStatusCardProps) {
  const isTrained = status.is_trained;
  const isTraining = status.is_training;
  const dotClass = isTraining ? 'bg-yellow-500' : (isTrained ? 'bg-green-500' : 'bg-red-500');
  const statusText = isTraining ? 'Training In Progress...' : (isTrained ? 'Model Trained' : 'Model Not Trained');

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <div className={`w-3 h-3 rounded-full ${dotClass} animate-pulse`}></div>
          Model Status
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          <p className={cn(
            'font-medium',
            isTrained ? 'text-green-700' : 'text-red-700'
          )}>
            {statusText}
          </p>

          {isTrained && status.current_model && (
            <div className="text-sm text-muted-foreground space-y-1">
              <p><strong>Name:</strong> {status.current_model.model_name}</p>
              <p><strong>Version:</strong> {status.current_model.version_id}</p>
              {status.last_training_time && (
                <p><strong>Last Trained:</strong> {new Date(status.last_training_time).toLocaleString()}</p>
              )}
            </div>
          )}

          {status.error && (
            <p className="text-red-600 text-sm">{status.error}</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

interface PerformanceMetricsProps {
  metrics: import('@/types/trading').MLPerformanceMetrics;
}

function PerformanceMetricsCard({ metrics }: PerformanceMetricsProps) {
  if (metrics.error) {
    return (
      <Card className="border-red-200">
        <CardHeader>
          <CardTitle>Performance Metrics</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-red-600">{metrics.error}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Performance Metrics</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-3">
            <div>
              <p className="text-sm text-muted-foreground">R² Score</p>
              <p className="text-lg font-semibold">
                {metrics.r2 !== undefined ? metrics.r2.toFixed(4) : 'N/A'}
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">RMSE</p>
              <p className="text-lg font-semibold">
                {metrics.rmse !== undefined ? metrics.rmse.toFixed(4) : 'N/A'}
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">MAE</p>
              <p className="text-lg font-semibold">
                {metrics.mae !== undefined ? metrics.mae.toFixed(4) : 'N/A'}
              </p>
            </div>
          </div>
          <div className="space-y-3">
            <div>
              <p className="text-sm text-muted-foreground">Profit Factor</p>
              <p className="text-lg font-semibold">
                {metrics.profit_factor !== undefined ? metrics.profit_factor.toFixed(2) : 'N/A'}
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Sharpe Ratio</p>
              <p className="text-lg font-semibold">
                {metrics.sharpe_ratio !== undefined ? metrics.sharpe_ratio.toFixed(2) : 'N/A'}
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Win Rate</p>
              <p className="text-lg font-semibold">
                {/* Backend win_rate values are already percentages (0-100). */}
                {metrics.win_rate !== undefined ? `${metrics.win_rate.toFixed(1)}%` : 'N/A'}
              </p>
            </div>
          </div>
          <div className="space-y-3 col-span-2 border-t pt-3 mt-1 grid grid-cols-3 gap-4">
            <div>
              <p className="text-sm text-muted-foreground">Total Vectors</p>
              <p className="text-lg font-semibold">
                {metrics.total_feature_vectors !== undefined ? metrics.total_feature_vectors.toLocaleString() : 'N/A'}
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Used Samples</p>
              <p className="text-lg font-semibold">
                {metrics.total_used_samples !== undefined ? metrics.total_used_samples.toLocaleString() : 'N/A'}
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Data Utilization</p>
              <p className="text-lg font-semibold">
                {metrics.total_feature_vectors !== undefined
                  && metrics.total_used_samples !== undefined
                  && metrics.total_feature_vectors > 0
                  ? `${((metrics.total_used_samples / metrics.total_feature_vectors) * 100).toFixed(1)}%`
                  : 'N/A'}
              </p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

interface FeatureImportanceChartProps {
  features: import('@/types/trading').MLFeatureImportance;
}

function FeatureImportanceChart({ features }: FeatureImportanceChartProps) {
  const normalizedFeatures = Array.isArray(features)
    ? features.reduce<Record<string, number>>((result, feature) => {
      if (feature.name) {
        result[feature.name] = feature.importance ?? feature.correlation_to_pnl ?? 0;
      }
      return result;
    }, {})
    : features;
  // Sort features by importance and take top 10
  const sortedFeatures = Object.entries(normalizedFeatures)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 10);

  if (sortedFeatures.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Feature Importance</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">No feature importance data available</p>
        </CardContent>
      </Card>
    );
  }

  const maxValue = Math.max(...sortedFeatures.map(([, value]) => value));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Top 10 Feature Importance</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {sortedFeatures.map(([feature, importance]) => {
            const percentage = (importance / maxValue) * 100;
            return (
              <div key={feature} className="flex items-center gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate" title={feature}>
                    {feature}
                  </p>
                </div>
                <div className="flex-1 max-w-[120px]">
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-blue-600 h-2 rounded-full"
                      style={{ width: `${percentage}%` }}
                    ></div>
                  </div>
                </div>
                <div className="text-right min-w-[60px]">
                  <span className="text-sm font-mono">
                    {importance.toFixed(3)}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

function ModelControls() {
  const {
    trainModel, isTraining,
    updateModel, isUpdating,
    rollbackModel, isRollingBack,
    availableModels, isLoadingModels,
    setActiveModel, isSettingActiveModel,
    deleteModel, isDeletingModel,
    deleteAllModels, isDeletingAllModels,
    resetDatabases, isResettingDatabases
  } = useModelTraining();

  const [selectedModel, setSelectedModel] = React.useState<string>('');

  React.useEffect(() => {
    if (availableModels && availableModels.length > 0 && !selectedModel) {
      const firstModel = availableModels[0];
      setSelectedModel(firstModel.model_id || firstModel.model_name);
    }
  }, [availableModels]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Model Controls</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <Button
              onClick={() => trainModel(undefined)}
              disabled={isTraining}
              variant="primary"
            >
              {isTraining ? 'Training...' : 'Train Model'}
            </Button>


            <Button
              onClick={() => updateModel()}
              disabled={isUpdating}
              variant="secondary"
            >
              {isUpdating ? 'Updating...' : 'Update Model'}
            </Button>

            <Button
              onClick={() => rollbackModel()}
              disabled={isRollingBack}
              variant="outline"
            >
              {isRollingBack ? 'Rolling Back...' : 'Rollback'}
            </Button>
          </div>
          
          <div className="border-t pt-4">
            <h4 className="text-sm font-medium mb-3">Model Management</h4>
            <div className="flex gap-3">
              <select
                className="flex-1 px-3 py-2 border rounded-md"
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                disabled={isLoadingModels || isSettingActiveModel || isDeletingModel}
              >
                {isLoadingModels ? (
                  <option>Loading models...</option>
                ) : (
                  availableModels?.map((model: { model_id?: string; model_name?: string; version_id?: string }) => (
                    <option key={model.model_id || model.model_name} value={model.model_id || model.model_name}>
                      {model.model_name} {model.version_id ? `(${model.version_id})` : ''}
                    </option>
                  ))
                )}
              </select>
              <Button
                onClick={() => {
                  if (selectedModel) {
                    setActiveModel(selectedModel);
                  }
                }}
                disabled={isSettingActiveModel || !selectedModel}
              >
                {isSettingActiveModel ? 'Activating...' : 'Set Active'}
              </Button>
              <Button
                onClick={() => {
                  if (selectedModel) {
                    deleteModel(selectedModel);
                  }
                }}
                disabled={isDeletingModel || !selectedModel}
                variant="danger"
                className="bg-red-600 hover:bg-red-700 text-white"
              >
                {isDeletingModel ? 'Deleting...' : 'Delete'}
              </Button>
            </div>
          </div>

          <div className="border-t pt-4">
            <h4 className="text-sm font-medium mb-3 text-red-600">Danger Zone</h4>
            <div className="space-y-3">
              <Button
                onClick={() => deleteAllModels()}
                disabled={isDeletingAllModels}
                variant="danger"
                className="w-full bg-red-100 text-red-700 hover:bg-red-200 border-red-200"
              >
                {isDeletingAllModels ? 'Deleting All Models...' : 'Delete All Models'}
              </Button>
              <Button
                onClick={() => resetDatabases()}
                disabled={isResettingDatabases}
                variant="danger"
                className="w-full bg-red-100 text-red-700 hover:bg-red-200 border-red-200"
              >
                {isResettingDatabases ? 'Resetting Databases...' : 'Reset All Databases'}
              </Button>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function ValidationArtifactsCard({ metrics }: { metrics: import('@/types/trading').MLPerformanceMetrics }) {
  const folds = metrics.walk_forward_folds ?? [];
  const cohorts = metrics.cohort_metrics ?? [];

  return (
    <Card>
      <CardHeader><CardTitle>Validation Artifacts</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div><span className="text-muted-foreground">Strategy</span><div className="font-medium">{metrics.validation_strategy || 'Not reported'}</div></div>
          <div><span className="text-muted-foreground">Feature set</span><div className="font-medium">{metrics.feature_set_version || 'Not reported'}</div></div>
        </div>
        <div>
          <h4 className="font-medium mb-2">Walk-forward folds ({folds.length})</h4>
          {folds.length === 0 ? <p className="text-sm text-muted-foreground">No walk-forward fold data available.</p> : (
            <div className="space-y-1 text-sm">
              {folds.map((fold, index) => (
                <div key={`${fold.fold_index ?? index}`} className="flex justify-between border-b py-1">
                  <span>Fold {fold.fold_index ?? index + 1}</span>
                  <span className="text-muted-foreground">{fold.metrics?.profit_factor !== undefined ? `PF ${Number(fold.metrics.profit_factor).toFixed(2)}` : 'Metrics available'}</span>
                </div>
              ))}
            </div>
          )}
        </div>
        <div>
          <h4 className="font-medium mb-2">Execution cohorts ({cohorts.length})</h4>
          {cohorts.length === 0 ? <p className="text-sm text-muted-foreground">No cohort metrics available.</p> : (
            <div className="space-y-1 text-sm">
              {cohorts.slice(0, 8).map((cohort, index) => (
                <div key={`${cohort.regime ?? 'cohort'}-${index}`} className="flex justify-between border-b py-1">
                  <span className="truncate max-w-[65%]" title={cohort.regime}>{cohort.regime || `Cohort ${index + 1}`}</span>
                  <span className="text-muted-foreground">{cohort.sample_count ?? 0} samples · {cohort.win_rate?.toFixed(1) ?? '0.0'}%</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

interface MLAnalyticsDashboardProps {
  className?: string;
}

function ConfigControls() {
  const { mlConfig, isConfigLoading, updateMlConfig, isUpdatingConfig } = useMLAnalytics();
  const [config, setConfig] = React.useState<import('@/types/trading').MLConfig | null>(null);

  React.useEffect(() => {
    if (mlConfig) {
      setConfig(mlConfig);
    }
  }, [mlConfig]);

  const handleSave = () => {
    if (config) {
      updateMlConfig(config);
    }
  };

  if (isConfigLoading || !config) {
    return <Card><CardHeader><CardTitle>Configuration</CardTitle></CardHeader><CardContent><p>Loading...</p></CardContent></Card>;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Configuration</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between">
          <label htmlFor="continuous-training">Enable Continuous Training</label>
          <input
            id="continuous-training"
            type="checkbox"
            checked={config.continuous_training_enabled}
            onChange={(e) => setConfig({ ...config, continuous_training_enabled: e.target.checked })}
          />
        </div>
        <div>
          <label htmlFor="training-interval">Training Interval (seconds)</label>
          <input
            id="training-interval"
            type="number"
            value={config.training_interval}
            onChange={(e) => setConfig({ ...config, training_interval: parseInt(e.target.value, 10) })}
            className="w-full p-2 border rounded"
          />
        </div>
        <div>
          <label htmlFor="data-threshold">New Data Threshold</label>
          <input
            id="data-threshold"
            type="number"
            value={config.new_data_threshold}
            onChange={(e) => setConfig({ ...config, new_data_threshold: parseInt(e.target.value, 10) })}
            className="w-full p-2 border rounded"
          />
        </div>
        <div className="flex items-center justify-between">
          <label htmlFor="batch-training">Enable Batch Training</label>
          <input
            id="batch-training"
            type="checkbox"
            checked={config.batch_training_enabled !== false}
            onChange={(e) => setConfig({ ...config, batch_training_enabled: e.target.checked })}
          />
        </div>
        <div>
          <label htmlFor="batch-size">Batch Size</label>
          <input
            id="batch-size"
            type="number"
            value={config.batch_size || 1000}
            onChange={(e) => setConfig({ ...config, batch_size: parseInt(e.target.value, 10) })}
            className="w-full p-2 border rounded"
            disabled={config.batch_training_enabled === false}
          />
        </div>
        <Button onClick={handleSave} disabled={isUpdatingConfig}>
          {isUpdatingConfig ? 'Saving...' : 'Save Configuration'}
        </Button>
      </CardContent>
    </Card>
  );
}

export default function MLAnalyticsDashboard({ className }: MLAnalyticsDashboardProps) {
  const { mlData, isLoading, error } = useMLAnalytics();

  if (error) {
    return (
      <Card className="border-red-200 bg-red-50">
        <CardContent className="p-6">
          <div className="text-center">
            <p className="text-red-800 font-medium">Failed to load ML analytics</p>
            <p className="text-red-600 text-sm mt-1">{error.message}</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (isLoading || !mlData) {
    return <MLAnalyticsSkeleton />;
  }

  return (
    <div className={cn('space-y-6', className)}>
      <div className="flex items-center gap-2 mb-6">
        <span className="text-2xl">🤖</span>
        <h2 className="text-2xl font-bold">ML Trading Optimization</h2>
      </div>

      <DashboardGrid>
        <ModelStatusCard status={mlData.status} />
        <PerformanceMetricsCard metrics={mlData.performance} />
      </DashboardGrid>

      <DashboardGrid className="grid-cols-1 lg:grid-cols-2">
        <FeatureImportanceChart features={mlData.feature_importance} />
        <ValidationArtifactsCard metrics={mlData.performance} />
      </DashboardGrid>

      <ModelControls />

      <ConfigControls />

      <PnlTradesTable />

      <PredictionComparisonChart />
    </div>
  );
}

function MLAnalyticsSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 mb-6">
        <div className="w-8 h-8 bg-gray-200 rounded animate-pulse"></div>
        <div className="w-64 h-8 bg-gray-200 rounded animate-pulse"></div>
      </div>

      <DashboardGrid>
        {Array.from({ length: 2 }).map((_, i) => (
          <Card key={i} className="animate-pulse">
            <CardContent className="p-6">
              <div className="space-y-3">
                <div className="h-6 bg-gray-200 rounded w-32"></div>
                <div className="h-4 bg-gray-200 rounded w-48"></div>
                <div className="space-y-2">
                  <div className="h-4 bg-gray-200 rounded w-36"></div>
                  <div className="h-4 bg-gray-200 rounded w-40"></div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </DashboardGrid>

      <DashboardGrid className="grid-cols-1 lg:grid-cols-2">
        <Card className="animate-pulse">
          <CardContent className="p-6">
            <div className="h-6 bg-gray-200 rounded w-40 mb-4"></div>
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="flex items-center gap-3">
                  <div className="flex-1 h-4 bg-gray-200 rounded"></div>
                  <div className="flex-1 h-4 bg-gray-200 rounded"></div>
                  <div className="w-16 h-4 bg-gray-200 rounded"></div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="animate-pulse">
          <CardContent className="p-6">
            <div className="h-6 bg-gray-200 rounded w-32 mb-4"></div>
            <div className="flex gap-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="flex-1 h-10 bg-gray-200 rounded"></div>
              ))}
            </div>
          </CardContent>
        </Card>
      </DashboardGrid>
    </div>
  );
}
