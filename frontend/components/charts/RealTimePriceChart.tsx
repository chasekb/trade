import React, { useMemo } from 'react';
import { PriceDataPoint } from './PriceChart';
import { usePriceData, useRealTimePriceData } from '@/hooks/usePriceData';
import { PriceChart } from './PriceChart';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { cn } from '@/lib/utils';

export interface RealTimePriceChartProps {
  symbol?: string;
  timeframe?: '1m' | '5m' | '15m' | '1h' | '4h' | '1d';
  height?: number;
  width?: number | string;
  showVolume?: boolean;
  showRealTimeIndicator?: boolean;
  className?: string;
}

export function RealTimePriceChart({
  symbol = 'BTC',
  timeframe = '1m',
  height = 400,
  width = '100%',
  showVolume = false,
  showRealTimeIndicator = true,
  className,
}: RealTimePriceChartProps) {
  const { data: priceData, isLoading, error } = usePriceData(symbol, timeframe);
  const realTimePrice = useRealTimePriceData(symbol);

  // Use the latest price data from React Query
  const chartData = priceData || [];

  // Get the latest price point for display
  const latestPrice = chartData.length > 0 ? chartData[chartData.length - 1]?.price : realTimePrice;
  const previousPrice = chartData.length > 1 ? chartData[chartData.length - 2]?.price : latestPrice;

  const priceChange = latestPrice - previousPrice;
  const priceChangePercent = previousPrice !== 0 ? ((priceChange / previousPrice) * 100) : 0;

  if (error) {
    return (
      <Card className={cn('border-red-200 bg-red-50', className)}>
        <CardContent className="p-6">
          <div className="text-center">
            <p className="text-red-800 font-medium">Failed to load price data</p>
            <p className="text-red-600 text-sm mt-1">{error.message}</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={cn('', className)}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-semibold">
            {symbol}/USD Price Chart {timeframe && `(${timeframe})`}
          </CardTitle>
          {showRealTimeIndicator && (
            <div className="flex items-center space-x-2">
              <div className="flex items-center space-x-1">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                <span className="text-sm text-gray-600">Live</span>
              </div>
            </div>
          )}
        </div>

        {!isLoading && chartData.length > 0 && (
          <div className="flex items-center space-x-4 mt-2">
            <div className="text-2xl font-bold">
              ${latestPrice.toFixed(2)}
            </div>
            <div className={cn(
              'text-sm font-medium',
              priceChange >= 0 ? 'text-green-600' : 'text-red-600'
            )}>
              {priceChange >= 0 ? '+' : ''}${priceChange.toFixed(2)}
              ({priceChangePercent >= 0 ? '+' : ''}{priceChangePercent.toFixed(2)}%)
            </div>
          </div>
        )}
      </CardHeader>

      <CardContent>
        {isLoading ? (
          <div className="flex items-center justify-center" style={{ height }}>
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          </div>
        ) : chartData.length > 0 ? (
          <PriceChart
            data={chartData}
            symbol={symbol}
            timeframe={timeframe}
            height={height}
            width={width}
            showVolume={showVolume}
          />
        ) : (
          <div className="flex items-center justify-center" style={{ height }}>
            <div className="text-center text-gray-500">
              <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              <p className="mt-2 text-sm">No price data available for {symbol}</p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
