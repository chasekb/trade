import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { useMLAnalytics } from '@/hooks/useMLAnalytics';
import { useModelTraining } from '@/hooks/useModelTraining';

export function PredictionComparisonChart() {
  const { comparePredictions, isComparing, comparisonData } = useMLAnalytics();
  const { availableModels, isLoadingModels } = useModelTraining();

  const [model1, setModel1] = useState<string>('');
  const [model2, setModel2] = useState<string>('');

  const handleCompare = () => {
    if (!model1 || !model2) {
      alert('Please select two models to compare');
      return;
    }

    if (model1 === model2) {
      alert('Please select two different models');
      return;
    }

    // This is a placeholder for the actual features.
    // In a real application, you would get these from the current market data.
    const features = {
      timestamp: Math.floor(Date.now() / 1000),
      symbol: 'BTC-USD',
      bid_ask_imbalance: 0.5,
      spread_percent: 0.01,
      mid_price: 50000,
      bid_volume: 100,
      ask_volume: 100,
      order_book_depth: 10,
      large_bid_wall: false,
      large_ask_wall: false,
      wall_size: 0,
      volume_weighted_price: 50000,
      price_momentum: 0,
      volatility: 0,
    };

    comparePredictions({ modelIds: [model1, model2], features });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Model Prediction Comparison</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">Model 1</label>
              <select
                className="w-full px-3 py-2 border rounded-md"
                value={model1}
                onChange={(e) => setModel1(e.target.value)}
                disabled={isLoadingModels}
              >
                <option value="">Select a model...</option>
                {availableModels?.map((model: any) => (
                  <option key={model.model_id || model.model_name} value={model.model_id || model.model_name}>
                    {model.model_name} {model.version_id ? `(v${model.version_id})` : ''}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Model 2</label>
              <select
                className="w-full px-3 py-2 border rounded-md"
                value={model2}
                onChange={(e) => setModel2(e.target.value)}
                disabled={isLoadingModels}
              >
                <option value="">Select a model...</option>
                {availableModels?.map((model: any) => (
                  <option key={model.model_id || model.model_name} value={model.model_id || model.model_name}>
                    {model.model_name} {model.version_id ? `(v${model.version_id})` : ''}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <Button onClick={handleCompare} disabled={isComparing || !model1 || !model2}>
            {isComparing ? 'Comparing...' : 'Compare Predictions'}
          </Button>

          {comparisonData && comparisonData.comparisons && (
            <div className="mt-6">
              <h3 className="text-lg font-semibold mb-3">Comparison Results</h3>
              <div className="overflow-x-auto">
                <table className="w-full border-collapse">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left p-2">Model</th>
                      <th className="text-left p-2">Version</th>
                      <th className="text-right p-2">Expected Return</th>
                      <th className="text-right p-2">Win Probability</th>
                      <th className="text-right p-2">Confidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparisonData.comparisons.map((comparison: any, index: number) => (
                      <tr key={index} className="border-b hover:bg-gray-50">
                        <td className="p-2 font-medium">{comparison.model_name}</td>
                        <td className="p-2 text-sm text-muted-foreground">{comparison.version_id || 'N/A'}</td>
                        <td className="p-2 text-right">
                          {comparison.error ? (
                            <span className="text-red-600 text-sm">Error</span>
                          ) : (
                            <span className={comparison.expected_return > 0 ? 'text-green-600' : 'text-red-600'}>
                              {(comparison.expected_return * 100).toFixed(2)}%
                            </span>
                          )}
                        </td>
                        <td className="p-2 text-right">
                          {comparison.error ? (
                            '-'
                          ) : (
                            `${(comparison.win_probability * 100).toFixed(1)}%`
                          )}
                        </td>
                        <td className="p-2 text-right">
                          {comparison.error ? (
                            '-'
                          ) : (
                            `${(comparison.confidence * 100).toFixed(1)}%`
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {comparisonData.comparisons.some((c: any) => c.error) && (
                <div className="mt-3 p-3 bg-yellow-50 border border-yellow-200 rounded">
                  <p className="text-sm text-yellow-800">
                    ⚠️ Some models encountered errors during prediction. Check the logs for details.
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
