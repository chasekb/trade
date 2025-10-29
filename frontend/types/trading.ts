// Core Trading Data Types

export interface TradingStats {
  total_pnl: number;
  total_fees: number;
  net_pnl: number;
  win_rate: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  avg_win: number;
  avg_loss: number;
  best_trade: number;
  worst_trade: number;
  profit_factor: number;
  sharpe_ratio: number;
  max_drawdown: number;
  total_volume: number;
  avg_trade_size: number;
  trades_today: number;
  last_trade_time?: string;
}

export interface Position {
  symbol: string;
  quantity: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  pnl_percentage: number;
  entry_time: string;
}

export interface Trade {
  id?: string;
  trade_id?: string;
  symbol: string;
  side: 'buy' | 'sell';
  quantity: number;
  price: number;
  pnl: number;
  timestamp: string;
}

export interface OrderBookSignal {
  symbol: string;
  timestamp: string;
  buy_volume: number;
  sell_volume: number;
  imbalance_ratio: number;
  signal_strength: number;
  prediction: 'BUY' | 'SELL' | 'HOLD';
  signal_generated?: boolean;
}

export interface PriceDataPoint {
  timestamp: string;
  price: number;
  volume?: number;
  high?: number;
  low?: number;
  open?: number;
  close?: number;
}

// API Response Types

export interface ApiResponse<T> {
  status: 'success' | 'error';
  data?: T;
  error?: string;
  timestamp: string;
}

export interface PaginationParams {
  page?: number;
  limit?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

export interface PaginatedResponse<T> extends ApiResponse<T[]> {
  pagination: {
    page: number;
    limit: number;
    total: number;
    total_pages: number;
    has_next: boolean;
    has_prev: boolean;
  };
}

// Chart Data Types

export interface ChartDataPoint {
  x: string | number;
  y: number;
  volume?: number;
}

export interface PriceChartData {
  labels: string[];
  datasets: {
    label: string;
    data: ChartDataPoint[];
    borderColor?: string;
    backgroundColor?: string;
    fill?: boolean;
  }[];
}

// Component Props Types

export interface StatCardProps {
  title: string;
  value: number | string;
  format?: 'currency' | 'percentage' | 'number' | 'text';
  change?: number;
  className?: string;
}

export interface DataTableColumn<T> {
  key: keyof T;
  header: string;
  render?: (value: any, item: T) => React.ReactNode;
  sortable?: boolean;
  className?: string;
}

export interface DataTableProps<T> {
  data: T[];
  columns: DataTableColumn<T>[];
  loading?: boolean;
  pagination?: {
    currentPage: number;
    totalPages: number;
    onPageChange: (page: number) => void;
  };
  sorting?: {
    key: string;
    direction: 'asc' | 'desc';
    onSort: (key: string, direction: 'asc' | 'desc') => void;
  };
  onRowClick?: (item: T) => void;
  className?: string;
}

// Trading Strategy Configuration Types

export interface StrategyParameter {
  name: string;
  label: string;
  type: 'number' | 'text' | 'select';
  default: any;
  min?: number;
  max?: number;
  step?: number;
  options?: string[];
}

export interface TradingStrategyConfig {
  name: string;
  displayName: string;
  parameters: StrategyParameter[];
}

export type TradingStrategy =
  | 'sma'
  | 'ema'
  | 'rsi'
  | 'bollinger'
  | 'macd'
  | 'stochastic'
  | 'fibonacci'
  | 'orderbook'
  | 'dca'
  | 'buyandhold';

export type TradingMode = 'live' | 'simulated';
export type SymbolMode = 'single' | 'universe';
export type UniverseType = 'major' | 'minor' | 'crypto' | 'all_usd' | 'all_eur' | 'all_usdt' | 'all_btc' | 'all_products' | 'custom';

export interface TradingConfig {
  mode: TradingMode;
  strategy: TradingStrategy;
  symbolMode: SymbolMode;
  symbols: string[];
  universeType?: UniverseType;
  customSymbols?: string;
  parameters: Record<string, any>;
  positionSizePercent?: number;
  maxPositions?: number;
  positionUpdateInterval?: number;
}

export interface OrderBookPreset {
  name: string;
  label: string;
  config: Record<string, any>;
}

// Live Trading Component Props

export interface LiveTradingPanelProps {
  className?: string;
}

export interface StrategySelectorProps {
  value: TradingStrategy;
  onChange: (strategy: TradingStrategy) => void;
  className?: string;
}

export interface TradingControlsProps {
  status: {
    isActive: boolean;
    mode?: TradingMode;
    strategy?: TradingStrategy;
    symbols?: string[];
  };
  onStart: () => Promise<void>;
  onStop: () => Promise<void>;
  loading?: boolean;
  className?: string;
}

export interface StrategyConfigFormProps {
  strategy: TradingStrategy;
  config: Record<string, any>;
  onChange: (config: Record<string, any>) => void;
  className?: string;
}

// Backtesting Component Props

export interface BacktestFormProps {
  parameters: {
    strategy: TradingStrategy;
    symbols: string[];
    startDate: string;
    endDate: string;
    config: Record<string, any>;
  };
  onChange: (parameters: Partial<BacktestFormProps['parameters']>) => void;
  products: Record<string, string[]>;
}

export interface BacktestControlsProps {
  onRun: () => Promise<void>;
  loading: boolean;
  canRun: boolean;
}

export interface BacktestResultsProps {
  results: any;
  loading: boolean;
}
