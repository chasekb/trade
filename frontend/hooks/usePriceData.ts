import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';
import { PriceDataPoint } from '@/types/trading';

const PRICE_HISTORY_POINTS = 200; // Number of historical data points to keep

// Mock real-time price data generation for development
function generateMockPriceData(symbol: string): PriceDataPoint[] {
  const now = new Date();
  const data: PriceDataPoint[] = [];
  let basePrice = symbol === 'BTC' ? 45000 : symbol === 'ETH' ? 2500 : 100;

  for (let i = PRICE_HISTORY_POINTS; i >= 0; i--) {
    const timestamp = new Date(now.getTime() - i * 60000); // 1 minute intervals
    const volatility = 0.002; // 0.2% volatility
    const change = (Math.random() - 0.5) * volatility * basePrice;
    basePrice += change;

    // Ensure price stays positive
    basePrice = Math.max(basePrice, 0.01);

    data.push({
      timestamp: timestamp.toISOString(),
      price: basePrice,
      volume: Math.floor(Math.random() * 1000) + 100,
      high: basePrice * (1 + Math.random() * 0.005),
      low: basePrice * (1 - Math.random() * 0.005),
      open: basePrice * (1 + (Math.random() - 0.5) * 0.01),
      close: basePrice,
    });
  }

  return data;
}

export function usePriceData(symbol: string = 'BTC', timeframe: string = '1m') {
  return useQuery({
    queryKey: ['price-data', symbol, timeframe] as const,
    queryFn: (): Promise<PriceDataPoint[]> => {
      // Simulate API call delay
      return new Promise(resolve => {
        setTimeout(() => {
          const data = generateMockPriceData(symbol);
          resolve(data);
        }, 100);
      });
    },
    staleTime: 30000, // 30 seconds
    refetchInterval: 60000, // Refetch every minute
    refetchIntervalInBackground: true,
  });
}

export function useRealTimePriceData(symbol: string = 'BTC') {
  const queryClient = useQueryClient();
  const lastPrice = useRef<number>(0);
  const updateInterval = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    // Start real-time updates
    const updatePrice = () => {
      queryClient.setQueryData(['price-data', symbol, '1m'], (oldData: PriceDataPoint[] | undefined) => {
        if (!oldData || oldData.length === 0) return oldData;

        const latestPoint = oldData[oldData.length - 1];
        const now = new Date();

        // Generate small price movement
        const volatility = 0.001; // 0.1% volatility per update
        const change = (Math.random() - 0.5) * volatility * latestPoint.price;
        const newPrice = Math.max(latestPoint.price + change, 0.01);

        lastPrice.current = newPrice;

        const newPoint: PriceDataPoint = {
          timestamp: now.toISOString(),
          price: newPrice,
          volume: Math.floor(Math.random() * 500) + 50,
          high: Math.max(newPrice * (1 + Math.random() * 0.002), latestPoint.high || newPrice),
          low: Math.min(newPrice * (1 - Math.random() * 0.002), latestPoint.low || newPrice),
          open: latestPoint.price,
          close: newPrice,
        };

        // Keep only the last PRICE_HISTORY_POINTS data points
        const newData = [...oldData, newPoint];
        if (newData.length > PRICE_HISTORY_POINTS) {
          newData.shift();
        }

        return newData;
      });
    };

    // Update every 5 seconds for "real-time" effect
    updateInterval.current = setInterval(updatePrice, 5000);

    return () => {
      if (updateInterval.current) {
        clearInterval(updateInterval.current);
      }
    };
  }, [symbol, queryClient]);

  return lastPrice.current;
}
