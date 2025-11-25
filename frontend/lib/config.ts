// Environment-specific configuration with TypeScript interfaces
interface AppConfig {
  api: {
    baseUrl: string;
    endpoints: {
      trading: {
        stats: string;
        positions: string;
        history: string;
      };
      ml: {
        dashboard: string;
        train: string;
      };
      backtest: string;
    };
  };
  websocket: {
    url: string;
    reconnectInterval: number;
    maxReconnectAttempts: number;
  };
  trading: {
    defaultSymbols: string[];
    updateInterval: number;
    chartRefreshRate: number;
  };
  ui: {
    itemsPerPage: number;
    maxRetries: number;
    timeout: number;
  };
}

const getConfig = (): AppConfig => {
  const isDevelopment = process.env.NODE_ENV === 'development';
  const isTest = process.env.NODE_ENV === 'test';

  return {
    api: {
      baseUrl: process.env.NEXT_PUBLIC_API_URL || (isDevelopment ? 'http://localhost:8000' : ''),
      endpoints: {
        trading: {
          stats: '/api/trades/stats',
          positions: '/api/trading/live/positions',
          history: '/api/trades/paginated',
        },
        ml: {
          dashboard: '/api/ml/dashboard',
          train: '/api/ml/train',
        },
        backtest: '/api/backtests/run',
      },
    },
    websocket: {
      url: process.env.NEXT_PUBLIC_WS_URL || (isDevelopment ? 'ws://localhost:8000' : ''),
      reconnectInterval: 5000,
      maxReconnectAttempts: 10,
    },
    trading: {
      defaultSymbols: ['BTC-USD', 'ETH-USD'],
      updateInterval: isDevelopment ? 10000 : 30000, // Faster updates in dev
      chartRefreshRate: isDevelopment ? 5000 : 30000,
    },
    ui: {
      itemsPerPage: 25,
      maxRetries: 3,
      timeout: 30000,
    },
  };
};

export const config = getConfig();
export type { AppConfig };
