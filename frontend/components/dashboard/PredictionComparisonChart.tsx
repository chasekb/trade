import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { useMLAnalytics } from '@/hooks/useMLAnalytics';

export function PredictionComparisonChart() {
  const { comparePredictions, isComparing, comparisonData } = useMLAnalytics();

  const handleCompare = () => {
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
    comparePredictions(features);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Model Prediction Comparison</CardTitle>
      </CardHeader>
      <CardContent>
        <Button onClick={handleCompare} disabled={isComparing}>
          {isComparing ? 'Comparing...' : 'Compare Predictions'}
        </Button>
        {comparisonData && (
          <div className="mt-4">
            <pre>{JSON.stringify(comparisonData, null, 2)}</pre>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
