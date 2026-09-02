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
  session_id?: string;
  event_id?: string;
  sequence?: number;
  timestamp: string;
  price: number;
  signal: 'buy' | 'sell' | 'hold';
  signal_generated: boolean;
  signal_strength: number;
  signal_type?: string;
  signal_reason?: string;
  cadence?: OrderBookCadenceEvent;
  data_status: 'sufficient' | 'insufficient' | 'none';
  spread: number;
  volume: number;
  criteria_analysis?: {
    bid_ask_squeeze?: {
      enabled: boolean;
      meets_criteria: boolean;
      delta_to_threshold: number;
      threshold_spread: number;
      analysis?: string;
    };
    volume_imbalance_buy?: {
      enabled: boolean;
      meets_criteria: boolean;
      delta_to_threshold: number;
      threshold: number;
      analysis?: string;
    };
    volume_imbalance_sell?: {
      enabled: boolean;
      meets_criteria: boolean;
      delta_to_threshold: number;
      threshold: number;
      analysis?: string;
    };
    large_trade_buy?: {
      enabled: boolean;
      meets_criteria: boolean;
      delta_to_threshold: number;
      large_trades_count: number;
      analysis?: string;
    };
    large_trade_sell?: {
      enabled: boolean;
      meets_criteria: boolean;
      delta_to_threshold: number;
      large_trades_count: number;
      analysis?: string;
    };
  };
  ml_analysis?: {
    ml_enabled: boolean;
    win_probability: number;
    expected_return: number;
    expected_return_available?: boolean;
    diagnostics_available?: boolean;
    fee_adjusted_expected_return?: number;
    required_edge?: number;
    profitability_gate_passed?: boolean;
    profitability_gate_reason?: string;
    diagnostic_factor?: string;
    factoring_semantics?: string;
    confidence: number;
    model_version: string;
    features_used?: string[];
    prediction_timestamp: string;
    // Backend analytics are model-version specific and intentionally opaque to the table layer.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    analytics?: any;
  };
  strength_composition?: {
    [featureName: string]: {
      value: number;
      importance_percent: number;
    };
  };
  execution_analysis?: {
    strategy?: string;
    symbol?: string;
    signal_generated?: boolean;
    intended_action?: string;
    intended_side?: string;
    executable_intent?: boolean;
    blocked?: boolean;
    blocker_reason?: string;
    diagnostic_factor?: string;
    strength_bucket?: string;
    expected_return_bucket?: string;
    expected_return?: number;
    fee_adjusted_expected_return?: number;
    required_edge?: number;
    allocated_usd?: number;
    available_cash?: number;
    estimated_fee?: number;
    minimum_notional?: number;
  };
  // Legacy properties for backward compatibility
  buy_volume?: number;
  sell_volume?: number;
  imbalance_ratio?: number;
  prediction?: 'BUY' | 'SELL' | 'HOLD';
}

export interface OrderBookSignalDiagnostics {
  schema_version?: string;
  session_id?: string;
  as_of?: string;
  selected_symbols?: string[];
  symbols?: SimulatedTradingSymbolDiagnosis[];
  summary?: SimulatedTradingDiagnosisSummary;
  selected_symbol_count?: number;
  requested_symbol_count?: number;
  quote_attempted_symbol_count?: number;
  quote_success_symbol_count?: number;
  quote_skipped_symbol_count?: number;
  current_batch_symbols?: string[];
  current_latest_signal_count?: number;
  missing_latest_signal_count?: number;
  missing_latest_signal_symbols?: string[];
  failed_request_symbol_count?: number;
  failed_request_symbols?: string[];
  recent_signal_record_count?: number;
  active_recent_signal_records?: number;
  signals_evaluated?: number;
  signals_generated?: number;
  transformer_warming_symbols?: number;
  transformer_rejected_inputs?: number;
  executable_order_intent_count?: number;
  execution_blocker_counts?: Record<string, number>;
  execution_strength_bucket_counts?: Record<string, number>;
  execution_expected_return_bucket_counts?: Record<string, number>;
  coverage_complete?: boolean;
  widget_coverage_contract?: string;
  contract?: string;
  cadence?: OrderBookCadenceSnapshot;
  quote_scheduler?: OrderBookQuoteSchedulerSnapshot;
  stage_counts?: SimulatedTradingDiagnosisStageCounts;
  dominant_blocker?: SimulatedTradingDiagnosisBlocker;
}

export type OrderBookCadenceState =
  | 'generated' | 'not_generated' | 'delayed' | 'retried' | 'merged'
  | 'dropped' | 'stale_displayed' | 'error';

export interface OrderBookCadenceEvent {
  schema_version?: string;
  session_id?: string;
  universe_generation?: number;
  trace_id?: string;
  tick_id?: number;
  batch_id?: string;
  event_id?: string;
  symbol?: string;
  attempt?: number;
  attempts?: number;
  producer?: Record<string, string>;
  durations_ms?: Record<string, number>;
  state?: OrderBookCadenceState | string;
  reason?: string | null;
}

export interface OrderBookCadenceSnapshot {
  schema_version?: string;
  session_id?: string;
  universe_generation?: number;
  as_of?: string;
  thresholds_ms?: Record<string, number>;
  last_tick?: Record<string, unknown>;
  counters?: Record<string, number>;
  histograms?: Record<string, {
    bounds_ms?: number[];
    counts?: number[];
    count?: number;
    sum_ms?: number;
    max_ms?: number;
  }>;
  coverage?: Record<string, number>;
  recent_errors?: Array<Record<string, unknown>>;
  enabled?: boolean;
}

export interface OrderBookQuoteSchedulerSnapshot {
  enabled?: boolean;
  batch_size?: number;
  cursor?: number;
  batch_symbols?: string[];
}

export interface OrderBookSignalPagination {
  current_page?: number;
  page?: number;
  per_page?: number;
  limit?: number;
  total_signals?: number;
  total?: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface OrderBookSignalsResponse {
  signals: OrderBookSignal[];
  pagination?: OrderBookSignalPagination;
  total_analyzed?: number;
  active_signals?: number;
  last_updated?: string;
  average_strength?: number;
  diagnostics?: OrderBookSignalDiagnostics;
}

export interface SimulatedTradingSymbolDiagnosis {
  symbol: string;
  sequence?: number;
  updated_at?: string;
  status?: {
    primary?: string;
    terminal?: boolean;
    reason?: { code?: string; message?: string; retryable?: boolean } | null;
    evaluated_at?: string | null;
  };
  market_data?: Record<string, unknown>;
  quote?: Record<string, unknown>;
  transformer?: Record<string, unknown>;
  signal?: Record<string, unknown>;
  gates?: Record<string, unknown>;
  intent?: Record<string, unknown>;
  execution?: Record<string, unknown>;
  trade?: Record<string, unknown>;
  cadence?: OrderBookCadenceEvent;
}

export interface SimulatedTradingDiagnosisSummary {
  status?: string;
  outcome?: string;
  selected_count?: number;
  terminal_count?: number;
  trade_count?: number;
  by_primary_status?: Record<string, number>;
  no_trade_reasons?: Array<{ code: string; count: number }>;
  stage_counts?: SimulatedTradingDiagnosisStageCounts;
  dominant_blocker?: SimulatedTradingDiagnosisBlocker;
  message?: string;
}

export interface SimulatedTradingDiagnosisStageCounts {
  selected_symbols?: number;
  diagnosis_evaluations?: number;
  quote_success_evaluations?: number;
  quote_failures?: number;
  transformer_warmup_events?: number;
  transformer_ready_evaluations?: number;
  signal_holds?: number;
  generated_candidates?: number;
  profitability_gate_passed?: number;
  profitability_gate_blocked?: number;
  ml_gate_passed?: number;
  ml_gate_blocked?: number;
  executable_intents?: number;
  simulated_fills?: number;
  persisted_trades?: number;
  trade_open_events?: number;
  trade_completed_events?: number;
  persistence_failures?: number;
}

export interface SimulatedTradingDiagnosisBlocker {
  code?: string | null;
  category?: string | null;
  count?: number;
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
  client?: ApiClientObservation;
}

export interface ApiClientObservation {
  transport: 'api_poll' | 'websocket';
  client_request_id: string;
  requested_at?: string;
  received_at: string;
  received_mono_ms: number;
  api_duration_ms: number;
  parse_duration_ms?: number;
  error_class?: string;
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
  header: React.ReactNode;
  // Column renderers are key-specific but the table stores them in a shared array.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
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
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
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
  | 'ml_enhanced_orderbook'
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
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  parameters: Record<string, any>;
  positionSizePercent?: number;
  maxPositions?: number;
  positionUpdateInterval?: number;
}

export interface OrderBookPreset {
  name: string;
  label: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
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
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  config: Record<string, any>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
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
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
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
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  results: any;
  loading: boolean;
}

// ML Analytics Types

export interface MLModelStatus {
  is_trained: boolean;
  is_training?: boolean;
  last_training_time?: string;
  current_model?: {
    model_name: string;
    version_id: string;
  };
  error?: string;
}

export interface MLPerformanceMetrics {
  r2?: number;
  rmse?: number;
  mae?: number;
  profit_factor?: number;
  sharpe_ratio?: number;
  win_rate?: number;
  total_feature_vectors?: number;
  total_used_samples?: number;
  validation_strategy?: string;
  feature_set_version?: string;
  walk_forward_folds?: Array<{
    fold_index?: number;
    train_start_timestamp?: number;
    train_end_timestamp?: number;
    test_start_timestamp?: number;
    test_end_timestamp?: number;
    metrics?: Record<string, number | string>;
  }>;
  cohort_metrics?: Array<{
    regime?: string;
    sample_count?: number;
    winning_trades?: number;
    losing_trades?: number;
    win_rate?: number;
    avg_pnl?: number;
    profit_factor?: number;
    max_drawdown?: number;
  }>;
  error?: string;
}

export type MLFeatureImportance = Record<string, number> | Array<{
  name?: string;
  importance?: number;
  correlation_to_pnl?: number;
}>;

export interface MLDashboardData {
  status: MLModelStatus;
  performance: MLPerformanceMetrics;
  feature_importance: MLFeatureImportance;
}

export interface MLTrainingResponse {
  status: 'success' | 'error' | 'training_started';
  message?: string;
  error?: string;
}

export interface MLTrainingProgress {
  is_training: boolean;
  progress_percentage?: number;
  current_step?: string;
  estimated_time_remaining?: number;
}

export interface MLConfig {
  continuous_training_enabled: boolean;
  training_interval: number;
  new_data_threshold: number;
  batch_training_enabled: boolean;
  batch_size: number;
}
