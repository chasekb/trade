import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState, useEffect, useCallback } from 'react';
import { apiClient, queryKeys } from '@/lib/api';
import {
  TradingMode,
  TradingStrategy,
  SymbolMode,
  UniverseType,
  OrderBookSignal,
} from '@/types/trading';

// Live Trading Hooks

export function useLiveTrading() {
  const [status, setStatus] = useState({
    isActive: false,
    mode: 'simulated' as TradingMode,
    strategy: 'orderbook' as TradingStrategy,
    symbols: [] as string[],
  });

  // Query to keep status in sync with backend (especially for symbols added in background)
  const { data: backendStatus } = useQuery({
    queryKey: ['trading-status'],
    queryFn: async () => {
      const response = await apiClient.getSimulatedTradingStatus();
      if (response.status === 'error') {
        throw new Error(response.error || 'Failed to fetch trading status');
      }
      return response.data;
    },
    enabled: status.isActive, // Only poll when trading is active
    refetchInterval: status.isActive ? 5000 : false, // Poll every 5 seconds when active
    staleTime: 1000, // Consider data fresh for 1 second
    refetchOnWindowFocus: true, // Refetch when tab becomes visible again
    refetchIntervalInBackground: true, // Continue polling even when tab is hidden
  });

  // Update local status when backend status changes
  useEffect(() => {
    if (backendStatus) {
      setStatus({
        isActive: backendStatus.is_trading || false,
        mode: 'simulated',
        strategy: backendStatus.strategy_type || 'orderbook',
        symbols: backendStatus.symbols || [],
      });
    }
  }, [backendStatus]);

  const startTradingMutation = useMutation({
    mutationFn: async (config: {
      mode: TradingMode;
      strategy: TradingStrategy;
      symbols: string[];
      parameters: Record<string, any>;
      position_size_percent?: number;
      max_positions?: number;
      position_update_interval?: number;
    }) => {
      const apiConfig: {
        position_size_percent?: number;
        max_positions?: number;
        position_update_interval?: number;
      } = {};

      if (config.position_size_percent !== undefined) {
        apiConfig.position_size_percent = config.position_size_percent;
      }
      if (config.max_positions !== undefined) {
        apiConfig.max_positions = config.max_positions;
      }
      if (config.position_update_interval !== undefined) {
        apiConfig.position_update_interval = config.position_update_interval;
      }

      return apiClient.startTrading(
        config.mode,
        config.strategy,
        config.symbols,
        config.parameters,
        apiConfig
      );
    },
    onSuccess: (response, variables) => {
      // The async trading endpoint returns a plain object like:
      // { status: 'started', is_active: true, ... }
      // Fall back to ApiResponse shape if used in future.
      const isStarted = (response as any)?.status === 'started' || (response as any)?.is_active === true || (response as any)?.data?.is_active === true;
      if (isStarted) {
        setStatus({
          isActive: true,
          mode: variables.mode,
          strategy: variables.strategy,
          symbols: variables.symbols,
        });
      }
    },
  });

  const stopTradingMutation = useMutation({
    mutationFn: () => apiClient.stopTrading(),
    onSuccess: (response) => {
      if (response.status === 'success') {
        setStatus(prev => ({ ...prev, isActive: false, symbols: [] }));
      }
    },
  });

  const updateStrategyParamsMutation = useMutation({
    mutationFn: (params: Record<string, any>) => apiClient.updateStrategyParameters(params),
    onSuccess: () => {
      // Optionally refetch status or handle success
    },
  });

  return {
    status,
    startTrading: startTradingMutation.mutateAsync,
    stopTrading: stopTradingMutation.mutateAsync,
    updateStrategyParameters: updateStrategyParamsMutation.mutateAsync,
    loading: startTradingMutation.isPending || stopTradingMutation.isPending,
    error: startTradingMutation.error || stopTradingMutation.error,
  };
}

// Order Book Signals Hook with Pagination Support

export function useOrderBookSignals(
  symbols?: string[],
  enabled: boolean = true,
  page: number = 1,
  perPage: number = 10,
  strategy?: string
) {
  // Enable query when trading is active, even if symbols aren't loaded yet
  // This allows WebSocket updates to populate the widget immediately
  const isEnabled = enabled;

  return useQuery({
    queryKey: ['orderbook-signals', symbols, enabled, page, perPage, strategy], // Include strategy in key to invalidate cache when strategy changes
    queryFn: async () => {
      const response = await apiClient.getOrderBookSignals(symbols, { page, per_page: perPage });
      if (response.status === 'error') {
        throw new Error(response.error || 'Failed to fetch order book signals');
      }
      return response.data;
    },
    enabled: isEnabled,
    staleTime: 3000, // Consider data fresh for 3 seconds
    refetchInterval: false, // Disable auto-refetch to prevent overwriting live WebSocket data
    refetchOnWindowFocus: true,
    refetchIntervalInBackground: true,
    refetchOnMount: 'always', // Always refetch when component mounts
  });
}

// Live Portfolio Hook
export function useLivePortfolio(enabled: boolean = true) {
  return useQuery({
    queryKey: ['live-portfolio-status'],
    queryFn: async () => {
      const response = await apiClient.getLivePortfolioStatus();
      if (response.status === 'error') {
        throw new Error(response.error || 'Failed to fetch live portfolio status');
      }
      return response.data;
    },
    enabled,
    staleTime: 5 * 1000, // 5 seconds
    refetchInterval: enabled ? 10 * 1000 : false, // Refresh every 10 seconds
  });
}

// Generated-signal outcome and blocker attribution report.
export function useExecutionReconciliation(enabled: boolean = true) {
  return useQuery({
    queryKey: ['execution-reconciliation'],
    queryFn: async () => {
      const response = await apiClient.getExecutionReconciliation();
      if (response.status === 'error') {
        throw new Error(response.error || 'Failed to fetch execution attribution');
      }
      const payload = response.data as any;
      return payload?.data || payload;
    },
    enabled,
    staleTime: 5 * 1000,
    refetchInterval: enabled ? 10 * 1000 : false,
    refetchOnWindowFocus: true,
  });
}

// Simulated Trading Statistics Hook

export function useSimulatedTradingStats(enabled: boolean = true) {
  return useQuery({
    queryKey: ['simulated-trading-stats'],
    queryFn: async () => {
      const response = await apiClient.getSimulatedTradingStatus();
      if (response.status === 'error') {
        throw new Error(response.error || 'Failed to fetch simulated trading stats');
      }
      return response.data;
    },
    enabled,
    staleTime: 2 * 1000, // 2 seconds - consider data fresh for 2 seconds
    refetchInterval: enabled ? 3 * 1000 : false, // Refresh every 3 seconds when enabled for near real-time updates
    refetchOnWindowFocus: true, // Refetch when tab becomes visible again
    refetchIntervalInBackground: true, // Continue polling even when tab is hidden
  });
}

// Simulated Trading WebSocket Hook

// Simulated Trading WebSocket Hook with FIFO Signal Queue

export function useSimTradingWebSocket(enabled: boolean = true) {
  const [connected, setConnected] = useState(false);
  const [signalQueue, setSignalQueue] = useState<OrderBookSignal[]>([]);
  const [processingSignal, setProcessingSignal] = useState<OrderBookSignal | null>(null);
  const queryClient = useQueryClient();

  // Queue processing function - processes one signal at a time with delay
  const processNextSignal = useCallback(() => {
    if (signalQueue.length > 0 && !processingSignal) {
      const nextSignal = signalQueue[0];
      setProcessingSignal(nextSignal);
      setSignalQueue(prev => prev.slice(1));

      console.log('🎯 Processing signal from queue:', nextSignal.symbol, nextSignal.timestamp);

      // Add to display cache (same logic as before)
      const allQueries = queryClient.getQueryCache().getAll();
      const orderbookQueries = allQueries.filter((q: any) =>
        q.queryKey[0] === 'orderbook-signals'
      );

      orderbookQueries.forEach((query: any) => {
        const queryKey = query.queryKey;
        const querySymbols = queryKey[1] as string[] | undefined;
        const page = queryKey[3] as number;

        if (page === 1) {
          const isRelevant = !querySymbols || querySymbols.length === 0 || querySymbols.includes(nextSignal.symbol);

          if (isRelevant) {
            queryClient.setQueryData(queryKey, (oldData: any) => {
              // If no data exists yet (initial load), initialize with the new signal
              if (!oldData) {
                return {
                  signals: [nextSignal],
                  total_analyzed: 1,
                  active_signals: nextSignal.signal_generated ? 1 : 0,
                  average_strength: nextSignal.signal_strength || 0,
                  last_updated: new Date().toISOString(),
                  pagination: {
                    current_page: 1,
                    per_page: 100, // Default to larger page size for live view
                    total_signals: 1,
                    total_pages: 1,
                    has_next: false,
                    has_prev: false
                  }
                };
              }

              const currentSignals = oldData.signals || [];

              // Create a map of existing signals by symbol for easy lookup and update
              const signalMap = new Map<string, OrderBookSignal>();
              currentSignals.forEach((s: OrderBookSignal) => signalMap.set(s.symbol, s));

              // Update or add the new signal
              const existingSignal = signalMap.get(nextSignal.symbol);

              // Only update if the new signal is fresher (newer timestamp) or if the symbol doesn't exist
              if (!existingSignal || new Date(nextSignal.timestamp) > new Date(existingSignal.timestamp)) {
                signalMap.set(nextSignal.symbol, nextSignal);
              }

              // Convert map back to array and sort by timestamp descending
              const updatedSignals = Array.from(signalMap.values()).sort((a, b) =>
                new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
              );

              return {
                ...oldData,
                signals: updatedSignals,
                total_analyzed: updatedSignals.length,
                active_signals: updatedSignals.filter(s => s.signal_generated).length,
                last_updated: new Date().toISOString(),
                pagination: {
                  ...oldData.pagination,
                  total_signals: updatedSignals.length,
                  // Update total pages based on current per_page setting
                  total_pages: Math.ceil(updatedSignals.length / (oldData.pagination?.per_page || 10))
                }
              };
            });
          }
        }
      });

      // Process next signal after delay (configurable, default 1 second)
      const processingDelay = parseInt(process.env.NEXT_PUBLIC_SIGNAL_PROCESSING_DELAY || '1000');
      setTimeout(() => {
        setProcessingSignal(null);
        // Continue processing queue if more signals exist
        // The useEffect hook will trigger the next processing cycle when processingSignal becomes null

      }, processingDelay);
    }
  }, [signalQueue, processingSignal, queryClient]);

  useEffect(() => {
    // Auto-process queue when signals are added and not currently processing
    if (signalQueue.length > 0 && !processingSignal) {
      processNextSignal();
    }
  }, [signalQueue, processingSignal, processNextSignal]);

  useEffect(() => {
    console.log('🚀 useSimTradingWebSocket hook called with enabled:', enabled);
    console.log('📊 Current queue length:', signalQueue.length, 'Processing:', !!processingSignal);
    if (!enabled) {
      console.log('🌐 WebSocket disabled - not connecting');
      return;
    }

    const base = process.env.NEXT_PUBLIC_WS_URL || 'http://localhost:8000';
    const wsUrl = base.replace('http://', 'ws://').replace('https://', 'wss://') + '/ws';

    console.log('🔌 Attempting to connect to WebSocket:', wsUrl);
    console.log('📡 Environment NEXT_PUBLIC_WS_URL:', process.env.NEXT_PUBLIC_WS_URL);
    console.log('🌐 Running in browser:', typeof window !== 'undefined');
    console.log('🚀 Trading enabled:', enabled);

    const ws = new WebSocket(wsUrl);
    let pingInterval: NodeJS.Timeout | null = null;
    let connectionTimeout: NodeJS.Timeout | null = null;
    const startHeartbeat = () => {
      // Send ping every 30 seconds to prevent connection timeout
      pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          try {
            ws.send(JSON.stringify({ type: 'ping' }));
            console.log('💓 Sent ping to maintain connection');
          } catch (error) {
            console.error('❌ Failed to send ping:', error);
          }
        }
      }, 30000);
    };

    const onOpen = () => {
      console.log('✅ WebSocket connection opened successfully');
      setConnected(true);
      startHeartbeat();
    };

    const onClose = (event: CloseEvent) => {
      console.log('❌ WebSocket connection closed:', {
        code: event.code,
        reason: event.reason,
        wasClean: event.wasClean
      });
      setConnected(false);
      if (pingInterval) {
        clearInterval(pingInterval);
        pingInterval = null;
      }
      if (connectionTimeout) {
        clearTimeout(connectionTimeout);
        connectionTimeout = null;
      }
    };

    const onError = (event: Event) => {
      console.error('💥 WebSocket connection error:', event);
      setConnected(false);
      if (pingInterval) {
        clearInterval(pingInterval);
        pingInterval = null;
      }
      if (connectionTimeout) {
        clearTimeout(connectionTimeout);
        connectionTimeout = null;
      }
    };

    const onMessage = (event: MessageEvent) => {
      try {
        const payload = JSON.parse(event.data || '{}');
        const type = payload?.type;
        const data = payload?.data;

        if (type === 'pong') {
          console.log('💓 Received pong from server');
          return;
        }

        // Push trading statistics into cache for instant UI updates
        if (type === 'trading_statistics_update' && data) {
          // Expect { portfolio, open_positions, recent_trades, ... }
          // Normalize to the shape expected by useSimulatedTradingStats consumer
          const normalized = {
            ...data,
          };
          // Update the stats query cache
          try {
            queryClient.setQueryData(['simulated-trading-stats'], normalized);
          } catch (e) {
            console.error('❌ Failed to update trading stats cache:', e);
          }
          // Also emit a custom event for components not using React Query
          window.dispatchEvent(new CustomEvent('sim-trading-stats-update', { detail: normalized }));
        }

        // ENQUEUE orderbook signals into FIFO queue for sequential processing
        if (type === 'orderbook_signals_update' && data) {
          console.log('📥 Received orderbook_signals_update WebSocket message:', data);
          apiClient.logMessage('Order book signal received and queued for sequential processing');

          try {
            // Handle both array of signals (from signals key) or single signal object
            const signalsList = Array.isArray(data.signals) ? data.signals : (Array.isArray(data) ? data : [data]);

            if (!signalsList || signalsList.length === 0) return;

            // Add signals to queue (FIFO)
            setSignalQueue(prevQueue => {
              const filteredSignals = signalsList.filter((newSignal: OrderBookSignal) => {
                if (!newSignal || !newSignal.symbol) return false;

                // Avoid duplicates in queue
                const isDuplicate = prevQueue.some(queuedSignal =>
                  queuedSignal.symbol === newSignal.symbol && queuedSignal.timestamp === newSignal.timestamp
                );
                return !isDuplicate;
              });

              const updatedQueue = [...prevQueue, ...filteredSignals];
              console.log('🗂️ Added', filteredSignals.length, 'signals to queue. Queue length:', updatedQueue.length);

              return updatedQueue;
            });

          } catch (e) {
            console.error('❌ Failed to enqueue orderbook signals:', e);
          }
        }
      } catch (e) {
        console.error('❌ Failed to parse WebSocket message:', e);
      }
    };

    ws.addEventListener('open', onOpen);
    ws.addEventListener('close', onClose);
    ws.addEventListener('error', onError);
    ws.addEventListener('message', onMessage);

    // Set timeout for initial connection
    connectionTimeout = setTimeout(() => {
      if (ws.readyState !== WebSocket.OPEN) {
        console.warn('⚠️ WebSocket connection timeout, closing...');
        try {
          ws.close();
        } catch (error) {
          console.error('❌ Error closing timed out connection:', error);
        }
      }
    }, 10000); // 10 second connection timeout

    return () => {
      if (pingInterval) {
        clearInterval(pingInterval);
      }
      if (connectionTimeout) {
        clearTimeout(connectionTimeout);
      }
      try { ws.removeEventListener('open', onOpen); } catch { }
      try { ws.removeEventListener('close', onClose); } catch { }
      try { ws.removeEventListener('error', onError); } catch { }
      try { ws.removeEventListener('message', onMessage); } catch { }
      try { ws.close(); } catch { }
    };
  }, [enabled, queryClient]);

  return {
    connected,
    signalQueue,
    processingSignal,
    queueLength: signalQueue.length
  };
}

// Products/Symbols Hook

export function useProducts() {
  return useQuery({
    queryKey: ['products'],
    queryFn: async () => {
      const response = await apiClient.getProducts();
      if (response.status === 'error') {
        throw new Error(response.error || 'Failed to fetch products');
      }
      return response.data?.categories || {};
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

// ML Models Hook

export function useMLModels(enabled: boolean = true) {
  return useQuery({
    queryKey: ['ml-models'],
    queryFn: async () => {
      const response = await apiClient.getMLModels();
      if (response.status === 'error') {
        throw new Error(response.error || 'Failed to fetch ML models');
      }
      return response.data;
    },
    enabled,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}



// Backtesting Hook

export function useBacktest() {
  return useMutation({
    mutationFn: (config: {
      strategy: TradingStrategy;
      symbols: string[];
      parameters: Record<string, any>;
      start_date: string;
      end_date: string;
    }) => apiClient.runBacktest(config),
  });
}

// Strategy Parameters Hook (computed, not from API)

export function useStrategyParameters() {
  const getStrategyParameters = (strategy: TradingStrategy) => {
    const parameters = {
      'sma': [
        { name: 'short_window', label: 'Short Window', type: 'number' as const, default: 10, min: 2, max: 100 },
        { name: 'long_window', label: 'Long Window', type: 'number' as const, default: 20, min: 5, max: 200 }
      ],
      'ema': [
        { name: 'short_window', label: 'Short Window', type: 'number' as const, default: 10, min: 2, max: 100 },
        { name: 'long_window', label: 'Long Window', type: 'number' as const, default: 20, min: 5, max: 200 }
      ],
      'rsi': [
        { name: 'window', label: 'RSI Window', type: 'number' as const, default: 14, min: 5, max: 50 },
        { name: 'overbought', label: 'Overbought Level', type: 'number' as const, default: 70, min: 60, max: 90 },
        { name: 'oversold', label: 'Oversold Level', type: 'number' as const, default: 30, min: 10, max: 40 }
      ],
      'bollinger': [
        { name: 'window', label: 'Window', type: 'number' as const, default: 20, min: 5, max: 100 },
        { name: 'std_dev', label: 'Standard Deviations', type: 'number' as const, default: 2, min: 1, max: 3, step: 0.1 }
      ],
      'macd': [
        { name: 'fast_window', label: 'Fast Window', type: 'number' as const, default: 12, min: 5, max: 50 },
        { name: 'slow_window', label: 'Slow Window', type: 'number' as const, default: 26, min: 10, max: 100 },
        { name: 'signal_window', label: 'Signal Window', type: 'number' as const, default: 9, min: 5, max: 30 }
      ],
      'stochastic': [
        { name: 'k_window', label: 'K Window', type: 'number' as const, default: 14, min: 5, max: 50 },
        { name: 'd_window', label: 'D Window', type: 'number' as const, default: 3, min: 2, max: 10 },
        { name: 'overbought', label: 'Overbought Level', type: 'number' as const, default: 80, min: 70, max: 90 },
        { name: 'oversold', label: 'Oversold Level', type: 'number' as const, default: 20, min: 10, max: 30 }
      ],
      'fibonacci': [
        { name: 'fib_lookback_period', label: 'Lookback Period', type: 'number' as const, default: 20, min: 10, max: 100 },
        { name: 'fib_levels', label: 'Fibonacci Levels', type: 'text' as const, default: '0.236,0.382,0.5,0.618,0.786' },
        { name: 'fib_confirmation_candles', label: 'Confirmation Candles', type: 'number' as const, default: 2, min: 1, max: 5 }
      ],
      'ml_enhanced_orderbook': [
        { name: 'ml_server_url', label: 'ML Server URL', type: 'text' as const, default: 'http://localhost:8002' },
        { name: 'confidence_threshold', label: 'Confidence Threshold', type: 'number' as const, default: 0.6, min: 0, max: 1, step: 0.1 },
        { name: 'fallback_to_baseline', label: 'Fallback to Baseline', type: 'select' as const, default: 'true', options: ['true', 'false'] }
      ],
      'orderbook': [
        { name: 'order_book_level', label: 'Order Book Level', type: 'number' as const, default: 2, min: 1, max: 3 },
        { name: 'trade_history_limit', label: 'Trade History Limit', type: 'number' as const, default: 1000, min: 10, max: 1000 },
        { name: 'bid_ask_spread_threshold', label: 'Bid-Ask Spread Threshold (%)', type: 'number' as const, default: 0.5, min: 0.01, max: 1.0, step: 0.01 },
        { name: 'volume_imbalance_threshold', label: 'Volume Imbalance Threshold', type: 'number' as const, default: 0.3, min: 0.1, max: 0.9, step: 0.1 },
        { name: 'large_trade_threshold', label: 'Large Trade Threshold ($)', type: 'number' as const, default: 2000, min: 1000, max: 100000 },
        { name: 'data_analysis_mode', label: 'Data Analysis Mode', type: 'select' as const, default: 'all', options: ['recent', 'all', 'sampled'] },
        { name: 'recent_data_limit', label: 'Recent Data Limit', type: 'number' as const, default: 200, min: 10, max: 1000 },
        { name: 'sampling_ratio', label: 'Sampling Ratio', type: 'number' as const, default: 0.1, min: 0.01, max: 1.0, step: 0.01 },
        { name: 'max_symbols_per_request', label: 'Max Symbols Per Request', type: 'number' as const, default: 1000, min: 10, max: 10000 },
        { name: 'max_universe_size', label: 'Max Universe Size', type: 'number' as const, default: 500, min: 1, max: 5000 },
        { name: 'max_positions_per_session', label: 'Max Positions Per Session', type: 'number' as const, default: 100, min: 1, max: 1000 }
      ],
      'dca': [
        { name: 'interval_hours', label: 'Interval (Hours)', type: 'number' as const, default: 24, min: 1, max: 168 },
        { name: 'amount', label: 'Amount per Interval', type: 'number' as const, default: 100, min: 10, max: 10000 }
      ],
      'buyandhold': [
        { name: 'amount', label: 'Investment Amount', type: 'number' as const, default: 1000, min: 100, max: 100000 }
      ]
    };

    return parameters[strategy] || [];
  };

  const getOrderBookPresets = () => ({
    'conservative': {
      order_book_level: 2,
      trade_history_limit: 100,
      bid_ask_spread_threshold: 0.1,
      volume_imbalance_threshold: 0.6,
      large_trade_threshold: 10000,
      data_analysis_mode: 'recent',
      recent_data_limit: 50,
      sampling_ratio: 0.1
    },
    'moderate': {
      order_book_level: 2,
      trade_history_limit: 500,
      bid_ask_spread_threshold: 0.2,
      volume_imbalance_threshold: 0.4,
      large_trade_threshold: 5000,
      data_analysis_mode: 'recent',
      recent_data_limit: 100,
      sampling_ratio: 0.1
    },
    'aggressive': {
      order_book_level: 2,
      trade_history_limit: 1000,
      bid_ask_spread_threshold: 0.5,
      volume_imbalance_threshold: 0.3,
      large_trade_threshold: 2000,
      data_analysis_mode: 'all',
      recent_data_limit: 200,
      sampling_ratio: 0.1
    },
    'very-aggressive': {
      order_book_level: 2,
      trade_history_limit: 1000,
      bid_ask_spread_threshold: 1.0,
      volume_imbalance_threshold: 0.2,
      large_trade_threshold: 1000,
      data_analysis_mode: 'all',
      recent_data_limit: 500,
      sampling_ratio: 0.1
    }
  });

  return {
    getStrategyParameters,
    getOrderBookPresets,
  };
}
