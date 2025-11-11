'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { DataTable } from '@/components/ui/DataTable';
import Tooltip from '@/components/ui/Tooltip';
import { LiveTradingPanelProps, TradingStrategy, TradingMode, SymbolMode, UniverseType, DataTableColumn, OrderBookSignal } from '@/types/trading';
import { useLiveTrading, useOrderBookSignals, useProducts, useStrategyParameters, useLivePortfolio, useMLModels } from '@/hooks/useTrading';

// Strategy Selector Component
interface StrategySelectorProps {
  value: TradingStrategy;
  onChange: (strategy: TradingStrategy) => void;
  className?: string;
}

function StrategySelector({ value, onChange, className = '' }: StrategySelectorProps) {
  const strategies: { value: TradingStrategy; label: string }[] = [
    { value: 'orderbook', label: 'Order Book Signals' },
    { value: 'sma', label: 'Simple Moving Average' },
    { value: 'ema', label: 'Exponential Moving Average' },
    { value: 'rsi', label: 'RSI Strategy' },
    { value: 'bollinger', label: 'Bollinger Bands' },
    { value: 'macd', label: 'MACD Strategy' },
    { value: 'stochastic', label: 'Stochastic Oscillator' },
    { value: 'fibonacci', label: 'Fibonacci Retracement' },
    { value: 'dca', label: 'Dollar Cost Average' },
    { value: 'buyandhold', label: 'Buy and Hold' },
  ];

  return (
    <div className={`space-y-2 ${className}`}>
      <label className="block text-sm font-medium text-gray-700">Trading Strategy</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as TradingStrategy)}
        className="w-full border border-gray-300 rounded-md px-3 py-2"
      >
        {strategies.map(strategy => (
          <option key={strategy.value} value={strategy.value}>
            {strategy.label}
          </option>
        ))}
      </select>
    </div>
  );
}

// Trading Controls Component
interface TradingControlsProps {
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

function TradingControls({ status, onStart, onStop, loading = false, className = '' }: TradingControlsProps) {
  return (
    <div className={`flex gap-3 ${className}`}>
      <Button
        onClick={onStart}
        disabled={loading || status.isActive}
        className="flex-1"
        variant={status.isActive ? 'secondary' : 'primary'}
      >
        {loading ? 'Starting...' : status.isActive ? 'Trading Active' : 'Start Trading'}
      </Button>
      <Button
        onClick={onStop}
        disabled={loading || !status.isActive}
        variant="danger"
        className="flex-1"
      >
        {loading ? 'Stopping...' : 'Stop Trading'}
      </Button>
    </div>
  );
}

// Strategy Configuration Form Component
interface StrategyConfigFormProps {
  strategy: TradingStrategy;
  config: Record<string, any>;
  onChange: (config: Record<string, any>) => void;
  className?: string;
}

function StrategyConfigForm({ strategy, config, onChange, className = '' }: StrategyConfigFormProps) {
  const { getStrategyParameters, getOrderBookPresets } = useStrategyParameters();
  const { data: mlModels } = useMLModels(strategy === 'ml_enhanced_orderbook');
  const [selectedPreset, setSelectedPreset] = useState('aggressive');

  const parameters = getStrategyParameters(strategy);
  const presets = getOrderBookPresets();

  const applyPreset = (presetName: string) => {
    if (strategy === 'orderbook' && presetName in presets) {
      const typeSafePresetName = presetName as keyof typeof presets;
      const presetConfig = presets[typeSafePresetName];
      onChange({ ...config, ...presetConfig });
      setSelectedPreset(presetName);
    }
  };

  useEffect(() => {
    applyPreset(selectedPreset);
  }, [strategy]);

  const handleParameterChange = (name: string, value: any) => {
    onChange({ ...config, [name]: value });
  };

  return (
    <div className={`space-y-4 ${className}`}>
      {strategy === 'orderbook' && (
        <div className="p-4 bg-gray-50 rounded-lg">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Configuration Preset
          </label>
          <select
            value={selectedPreset}
            onChange={(e) => applyPreset(e.target.value)}
            className="w-full border border-gray-300 rounded-md px-3 py-2 mb-3"
          >
            <option value="custom">Custom Configuration</option>
            <option value="conservative">Conservative (Few High-Quality Signals)</option>
            <option value="moderate">Moderate (Balanced Signals)</option>
            <option value="aggressive">Aggressive (More Signals) - Recommended</option>
            <option value="very-aggressive">Very Aggressive (Maximum Signals)</option>
          </select>
          <p className="text-xs text-gray-500">
            Select a preset to automatically configure parameters for different signal frequencies
          </p>
        </div>
      )}

      {strategy === 'ml_enhanced_orderbook' && (
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700">Active Model</label>
          <select
            value={config.active_model || ''}
            onChange={(e) => handleParameterChange('active_model', e.target.value)}
            className="w-full border border-gray-300 rounded-md px-3 py-2"
          >
            <option value="">-- Select a Model --</option>
            {mlModels?.map((model: any) => (
              <option key={model.model_name} value={model.model_name}>
                {model.model_name} (v{model.version_id})
              </option>
            ))}
          </select>
        </div>
      )}

      {parameters.length > 0 && (
        <div className="space-y-4">
          <h4 className="text-md font-semibold text-gray-700">Strategy Parameters</h4>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {parameters.map(param => (
              <div key={param.name} className="space-y-2">
                <label className="block text-sm font-medium text-gray-700">
                  {param.label}
                </label>
                {param.type === 'select' ? (
                  <select
                    value={config[param.name] || param.default}
                    onChange={(e) => handleParameterChange(param.name, e.target.value)}
                    className="w-full border border-gray-300 rounded-md px-3 py-2"
                  >
                    {param.options?.map(option => (
                      <option key={option} value={option}>
                        {option.charAt(0).toUpperCase() + option.slice(1)}
                      </option>
                    ))}
                  </select>
                ) : (
                  <Input
                    type={param.type}
                    value={config[param.name] || param.default}
                    onChange={(e) => handleParameterChange(param.name, e.target.value)}
                    min={param.min}
                    max={param.max}
                    step={('step' in param) ? param.step : undefined}
                    className="w-full"
                  />
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Risk Settings: Max Position Size */}
      <div className="space-y-3 p-4 bg-gray-50 rounded-lg">
        <h4 className="text-md font-semibold text-gray-700">Risk Settings</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 items-end">
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-700">Initial Portfolio Size ($)</label>
            <Input
              type="number"
              min={1}
              step={100}
              value={config.initial_portfolio_size || 10000}
              onChange={(e) => handleParameterChange('initial_portfolio_size', Number(e.target.value))}
              className="w-full"
            />
          </div>
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-700">Position Size Mode</label>
            <select
              value={config.position_size_mode || 'percent'}
              onChange={(e) => {
                const newMode = e.target.value;
                const newValue = newMode === 'percent' ? 1 : 100;
                onChange({
                  ...config,
                  position_size_mode: newMode,
                  position_size_value: newValue,
                });
              }}
              className="w-full border border-gray-300 rounded-md px-3 py-2"
            >
              <option value="percent">Percentage of Portfolio</option>
              <option value="dollar">Fixed Dollar Amount</option>
            </select>
          </div>
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-700">Position Size Value</label>
            <Input
              type="number"
              min={0}
              step={(config.position_size_mode || 'percent') === 'percent' ? 0.1 : 1}
              value={config.position_size_value ?? ((config.position_size_mode || 'percent') === 'percent' ? 1 : 100)}
              onChange={(e) => handleParameterChange('position_size_value', Number(e.target.value))}
              className="w-full"
            />
          </div>
          <div className="text-xs text-gray-500">
            {(config.position_size_mode || 'percent') === 'percent'
              ? 'Example: 1 means 1% of portfolio per position'
              : 'Example: 250 means allocate $250 per position'}
          </div>
        </div>
      </div>
    </div>
  );
}

// Order Book Signals Table Component with Pagination
function OrderBookSignalsTable({
  signals,
  pagination,
  onPageChange,
  onPageSizeChange,
  summary,
}: {
  signals: OrderBookSignal[];
  pagination?: {
    current_page: number;
    per_page: number;
    total_pages: number;
    total_signals: number;
    has_next: boolean;
    has_prev: boolean;
  };
  onPageChange?: (page: number) => void;
  onPageSizeChange?: (pageSize: number) => void;
  summary?: {
    total_analyzed?: number;
    active_signals?: number;
    average_strength?: number;
    last_updated?: string;
  };
}) {
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  // Use pagination from props if available, otherwise use local state
  const activePage = pagination?.current_page || currentPage;
  const activePageSize = pagination?.per_page || pageSize;
  const totalPages = pagination?.total_pages || Math.ceil((signals?.length || 0) / activePageSize);
  const totalSignals = (summary?.total_analyzed ?? pagination?.total_signals ?? (signals?.length || 0));

  // Calculate paginated data if no server-side pagination
  const paginatedSignals = pagination ? signals : signals?.slice(
    (activePage - 1) * activePageSize,
    activePage * activePageSize
  ) || [];

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    onPageChange?.(page);
  };

  const handlePageSizeChange = (newPageSize: number) => {
    setPageSize(newPageSize);
    setCurrentPage(1); // Reset to first page
    onPageSizeChange?.(newPageSize);
  };

  const columns: DataTableColumn<OrderBookSignal>[] = [
    {
      key: 'timestamp',
      header: 'Time',
      sortable: true,
      render: (value) => new Date(value).toLocaleString(),
    },
    {
      key: 'symbol',
      header: 'Symbol',
      sortable: true,
      render: (value, row) => (
        <div className="flex items-center space-x-2">
          <div className="text-sm font-medium text-gray-900">{value}</div>
          <span className="text-xs" title={`Data Status: ${row.data_status}`}>
            {row.data_status === 'sufficient' ? '✓' :
             row.data_status === 'insufficient' ? '⚠' : '✗'}
          </span>
        </div>
      ),
    },
    {
      key: 'price',
      header: 'Price',
      sortable: true,
      render: (value) => `$${value?.toFixed(2) || '0.00'}`,
    },
    {
      key: 'signal_generated',
      header: 'Signal',
      sortable: true,
      render: (value, row) => {
        const signalClass = row.data_status === 'sufficient'
          ? (row.signal === 'buy' ? 'text-green-600 bg-green-50' :
             row.signal === 'sell' ? 'text-red-600 bg-red-50' :
             'text-gray-600 bg-gray-50')
          : row.data_status === 'insufficient'
          ? 'text-yellow-600 bg-yellow-50'
          : 'text-gray-400 bg-gray-100';

        // Get the actual signal value, fallback to 'hold' if undefined
        const actualSignal = row.signal || 'hold';
        
        return (
          <span className={`px-2 py-1 rounded-full text-xs font-medium ${signalClass}`}>
            {row.data_status === 'sufficient' ? actualSignal.toUpperCase() :
             row.data_status === 'insufficient' ? 'WAITING' : 'NO DATA'}
          </span>
        );
      },
    },
    {
      key: 'signal_strength',
      header: 'Strength',
      sortable: true,
      render: (value, row) => {
        const composition = row.strength_composition || {};
        const tooltipContent = (
          <div>
            <p className="font-bold mb-1">Signal Strength: {(value || 0).toFixed(2)}</p>
            <p className="text-xs mb-2">This is the ML model's confidence in the signal. It is composed of the following features, weighted by their learned importance:</p>
            <ul className="list-disc list-inside text-xs">
              {Object.entries(composition).map(([key, val]) => (
                <li key={key}>
                  <span className="font-semibold">{key.replace(/_/g, ' ')}:</span> {val.importance_percent.toFixed(1)}%
                </li>
              ))}
            </ul>
          </div>
        );

        return (
          <Tooltip text={tooltipContent}>
            <div className="flex items-center">
              <div className="w-16 bg-gray-200 rounded-full h-2 mr-2">
                <div className="bg-blue-600 h-2 rounded-full" style={{ width: `${(value || 0) * 100}%` }}></div>
              </div>
              <span className={`text-sm font-medium ${
                (value || 0) >= 0.7 ? 'text-green-600' :
                (value || 0) >= 0.4 ? 'text-yellow-600' : 'text-red-600'
              }`}>
                {(value || 0).toFixed(2)}
              </span>
            </div>
          </Tooltip>
        );
      },
    },
    {
      key: 'spread',
      header: 'Spread',
      sortable: true,
      render: (value) => `${(value || 0).toFixed(4)}%`,
    },
    {
      key: 'volume',
      header: 'Volume',
      sortable: true,
      render: (value) => (value || 0).toFixed(2),
    },
    {
      key: 'criteria_analysis',
      header: 'Criteria',
      render: (value, row) => {
        const criteria = value || {};
        const squeeze = criteria.bid_ask_squeeze || {};
        const imbalanceBuy = criteria.volume_imbalance_buy || {};
        const largeTradeBuy = criteria.large_trade_buy || {};

        const composition = row.strength_composition || {};
        const squeeze_importance = composition['spread_percent']?.importance_percent || 0;
        const imbalance_importance = composition['bid_ask_imbalance']?.importance_percent || 0;

        const tooltipContent = (
          <div>
            <p className="font-bold mb-1">Market Criteria</p>
            <p className="text-xs mb-2">These are market conditions used as features for the ML model. A checkmark (✓) means the condition was met.</p>
            <ul className="list-disc list-inside text-xs">
              <li>Bid-Ask Squeeze ({(squeeze_importance).toFixed(1)}% importance)</li>
              <li>Volume Imbalance ({(imbalance_importance).toFixed(1)}% importance)</li>
              <li>Large Trade Detection</li>
            </ul>
          </div>
        );

        return (
          <Tooltip text={tooltipContent}>
            <div className="text-xs space-y-1">
              <div className="flex items-center space-x-1">
                <span className={squeeze.meets_criteria ? 'text-green-600' : 'text-red-600'}>
                  {squeeze.enabled ? (squeeze.meets_criteria ? '✓' : '✗') : '○'}
                </span>
                <span className="text-gray-600">Squeeze</span>
              </div>
              <div className="flex items-center space-x-1">
                <span className={imbalanceBuy.meets_criteria ? 'text-green-600' : 'text-red-600'}>
                  {imbalanceBuy.enabled ? (imbalanceBuy.meets_criteria ? '✓' : '✗') : '○'}
                </span>
                <span className="text-gray-600">Imbalance</span>
              </div>
              <div className="flex items-center space-x-1">
                <span className={largeTradeBuy.meets_criteria ? 'text-green-600' : 'text-red-600'}>
                  {largeTradeBuy.enabled ? (largeTradeBuy.meets_criteria ? '✓' : '✗') : '○'}
                </span>
                <span className="text-gray-600">Large Trade</span>
              </div>
            </div>
          </Tooltip>
        );
      },
    },
    {
      key: 'ml_analysis',
      header: 'ML Analysis',
      render: (value, row) => {
        const ml = value || {};
        if (!ml.ml_enabled) {
          return <span className="text-xs text-gray-400">No ML</span>;
        }

        const composition = row.strength_composition || {};
        const ml_importance = composition['ml_confidence']?.importance_percent || 50; // Default to 50 if not available

        const tooltipContent = (
          <div>
            <p className="font-bold mb-1">ML Model Prediction</p>
            <p className="text-xs mb-2">The model's confidence is the primary driver of the signal strength, contributing {ml_importance.toFixed(1)}% to the score.</p>
            <ul className="list-disc list-inside text-xs">
              <li>Win Probability: The model's prediction of a successful trade.</li>
              <li>Expected Return: The potential profit from the trade.</li>
            </ul>
          </div>
        );

        return (
          <Tooltip text={tooltipContent}>
            <div className="text-xs space-y-1">
              <div className="flex items-center space-x-1">
                <span className="text-blue-600">🤖</span>
                <span className={`font-medium ${
                  (ml.win_probability || 0) >= 0.6 ? 'text-green-600' :
                  (ml.win_probability || 0) >= 0.4 ? 'text-yellow-600' : 'text-red-600'
                }`}>
                  {(ml.win_probability || 0).toFixed(1)}%
                </span>
              </div>
              <div className="text-gray-500">
                Exp: ${(ml.expected_return || 0).toFixed(2)}
              </div>
            </div>
          </Tooltip>
        );
      },
    },
    {
      key: 'timestamp' as keyof OrderBookSignal,
      header: 'Details',
      render: (value, row) => (
        <button
          onClick={() => {
            // Create a modal or tooltip with detailed analysis
            const details = `
Signal: ${row.signal || 'None'}
Reason: ${row.signal_reason || 'N/A'}
Type: ${row.signal_type || 'N/A'}

Criteria Analysis:
- Bid-Ask Squeeze: ${row.criteria_analysis?.bid_ask_squeeze?.analysis || 'N/A'}
- Volume Imbalance Buy: ${row.criteria_analysis?.volume_imbalance_buy?.analysis || 'N/A'}
- Volume Imbalance Sell: ${row.criteria_analysis?.volume_imbalance_sell?.analysis || 'N/A'}
- Large Trade Buy: ${row.criteria_analysis?.large_trade_buy?.analysis || 'N/A'}
- Large Trade Sell: ${row.criteria_analysis?.large_trade_sell?.analysis || 'N/A'}

${row.ml_analysis?.ml_enabled ? `
ML Analysis:
- Win Probability: ${(row.ml_analysis.win_probability * 100).toFixed(1)}%
- Expected Return: ${(row.ml_analysis.expected_return * 100).toFixed(2)}%
- Confidence: ${(row.ml_analysis.confidence * 100).toFixed(1)}%
- Model: ${row.ml_analysis.model_version}
- Features: ${row.ml_analysis.features_used?.length || 0}
- Prediction Time: ${new Date(row.ml_analysis.prediction_timestamp).toLocaleString()}
` : 'ML Analysis: Not enabled'}
            `;
            alert(details); // Replace with proper modal in production
          }}
          className="text-blue-600 hover:text-blue-800 text-xs font-medium"
        >
          <i className="fas fa-info-circle mr-1"></i>Details
        </button>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      {/* Pagination Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <label className="text-sm text-gray-700">Show:</label>
          <select
            value={activePageSize}
            onChange={(e) => handlePageSizeChange(parseInt(e.target.value))}
            className="border border-gray-300 rounded-md px-2 py-1 text-sm"
          >
            <option value={10}>10</option>
            <option value={25}>25</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
          </select>
          <span className="text-sm text-gray-600">
            per page
          </span>
        </div>

        <div className="text-sm text-gray-600">
          Page {activePage} of {totalPages} ({totalSignals} total signals)
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => handlePageChange(activePage - 1)}
            disabled={activePage <= 1}
            className="px-3 py-1 border border-gray-300 rounded-md text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
          >
            <i className="fas fa-chevron-left mr-1"></i>Prev
          </button>

          <div className="flex items-center space-x-1">
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              const pageNum = Math.max(1, Math.min(totalPages - 4, activePage - 2)) + i;
              if (pageNum > totalPages) return null;

              return (
                <button
                  key={pageNum}
                  onClick={() => handlePageChange(pageNum)}
                  className={`px-3 py-1 border rounded-md text-sm ${
                    pageNum === activePage
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  {pageNum}
                </button>
              );
            })}
          </div>

          <button
            onClick={() => handlePageChange(activePage + 1)}
            disabled={activePage >= totalPages}
            className="px-3 py-1 border border-gray-300 rounded-md text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
          >
            Next<i className="fas fa-chevron-right ml-1"></i>
          </button>
        </div>
      </div>

      {/* Data Table */}
      <DataTable
        data={paginatedSignals}
        columns={columns}
        loading={false}
        className="w-full"
      />

      {/* Statistics Summary */}
      {signals && signals.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mt-4 p-4 bg-gray-50 rounded-lg">
          <div className="text-center">
            <div className="text-lg font-semibold text-gray-900">{totalSignals}</div>
            <div className="text-sm text-gray-600">Total Analyzed</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-semibold text-green-600">
              {summary?.active_signals ?? signals.filter(s => s.signal_generated === true).length}
            </div>
            <div className="text-sm text-gray-600">Active Signals</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-semibold text-blue-600">
              {(
                summary?.average_strength ??
                (signals.length > 0 ? (signals.reduce((sum, s) => sum + (s.signal_strength || 0), 0) / signals.length) : 0)
              ).toFixed(2)}
            </div>
            <div className="text-sm text-gray-600">Avg Strength</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-semibold text-gray-900">
              {(summary?.last_updated ? new Date(summary.last_updated) : new Date()).toLocaleTimeString()}
            </div>
            <div className="text-sm text-gray-600">Last Updated</div>
          </div>
        </div>
      )}
    </div>
  );
}

// Trading Configuration Section
function TradingConfiguration({
  strategy,
  onStrategyChange,
  config,
  onConfigChange,
  symbols,
  onSymbolsChange,
}: {
  strategy: TradingStrategy;
  onStrategyChange: (strategy: TradingStrategy) => void;
  config: Record<string, any>;
  onConfigChange: (config: Record<string, any>) => void;
  symbols: string[];
  onSymbolsChange: (symbols: string[]) => void;
}) {
  const { data: products } = useProducts();
  const [symbolMode, setSymbolMode] = useState<'single' | 'universe'>('single');
  const [selectedUniverseType, setSelectedUniverseType] = useState('all_usd');

  const handleSymbolModeChange = (mode: 'single' | 'universe') => {
    setSymbolMode(mode);
    if (mode === 'single') {
      onSymbolsChange(['BTC-USD']);
    } else {
      // For universe mode, apply the current universe type
      applyUniverseType(selectedUniverseType);
    }
  };

  // Function to get all available symbols
  const getAllSymbols = (products: Record<string, string[]> | null | undefined): string[] => {
    if (!products) return [];
    return Object.values(products).flat().filter((symbol, index, arr) => arr.indexOf(symbol) === index);
  };

  // Fetch products directly from Coinbase API
  const fetchCoinbaseSymbols = async (): Promise<string[]> => {
    try {
      console.log('Fetching products from Coinbase API...');
      const response = await fetch('https://api.exchange.coinbase.com/products');
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const products = await response.json();
      const symbols = products
        .filter((product: any) => product.status === 'online' && !product.trading_disabled)
        .map((product: any) => product.id)
        .sort();
      console.log(`Fetched ${symbols.length} symbols from Coinbase`);
      return symbols;
    } catch (error) {
      console.error('Error fetching Coinbase symbols:', error);
      throw error;
    }
  };

  // Function to filter symbols by universe type
  const applyUniverseType = async (universeType: string) => {
    console.log('applyUniverseType called with:', universeType);

    let allSymbols = getAllSymbols(products);

    // If no symbols from hook, try to fetch from Coinbase directly
    if (allSymbols.length === 0) {
      console.log('No products from hook, fetching from Coinbase API...');
      try {
        const symbols = await fetchCoinbaseSymbols();
        allSymbols = symbols;
        console.log('Fetched symbols from Coinbase:', allSymbols.length);
      } catch (error) {
        console.warn('Failed to fetch Coinbase symbols:', error);
        allSymbols = ['BTC-USD', 'ETH-USD', 'ADA-USD', 'SOL-USD', 'DOT-USD', 'XRP-USD'];
      }
    }

    console.log('All symbols available:', allSymbols.length);

    let filteredSymbols: string[] = [];

    switch (universeType) {
      case 'all_products':
        filteredSymbols = allSymbols;
        break;
      case 'all_usd':
        filteredSymbols = allSymbols.filter(symbol => symbol.endsWith('-USD'));
        break;
      case 'all_eur':
        filteredSymbols = allSymbols.filter(symbol => symbol.endsWith('-EUR'));
        break;
      case 'all_usdt':
        filteredSymbols = allSymbols.filter(symbol => symbol.endsWith('-USDT'));
        break;
      case 'all_btc':
        filteredSymbols = allSymbols.filter(symbol => symbol.endsWith('-BTC'));
        break;
      case 'major':
        // Major currency pairs
        const majorPairs = ['EUR-USD', 'GBP-USD', 'USD-JPY', 'USD-CHF', 'AUD-USD', 'USD-CAD', 'NZD-USD'];
        filteredSymbols = allSymbols.filter(symbol => majorPairs.includes(symbol));
        break;
      case 'minor':
        // Minor currency pairs (excluding major pairs)
        const minorPairs = allSymbols.filter(symbol =>
          symbol.endsWith('-USD') &&
          !['EUR-USD', 'GBP-USD', 'AUD-USD', 'NZD-USD'].includes(symbol) &&
          !symbol.includes('BTC') && !symbol.includes('ETH')
        ).slice(0, 21); // Limit to 21 as indicated
        filteredSymbols = minorPairs;
        break;
      case 'crypto':
        // Cryptocurrency pairs
        filteredSymbols = allSymbols.filter(symbol =>
          symbol.includes('BTC') || symbol.includes('ETH') || symbol.includes('ADA') ||
          symbol.includes('SOL') || symbol.includes('DOT') || symbol.includes('XRP')
        ).slice(0, 35); // Limit to 35 as indicated
        filteredSymbols = filteredSymbols;
        break;
      case 'custom':
      default:
        // For custom, don't auto-populate
        return;
    }

    // Update symbols if filtered symbols were found
    if (filteredSymbols.length > 0) {
      onSymbolsChange(filteredSymbols);
    }
  };

  const handleUniverseTypeChange = (universeType: string) => {
    setSelectedUniverseType(universeType);
    applyUniverseType(universeType);
  };

  useEffect(() => {
    // Update UI based on symbol mode
    const singleConfig = document.getElementById('single-symbol-config');
    const universeConfig = document.getElementById('universe-config');

    if (singleConfig && universeConfig) {
      singleConfig.style.display = symbolMode === 'single' ? 'block' : 'none';
      universeConfig.style.display = symbolMode === 'universe' ? 'block' : 'none';
    }
  }, [symbolMode]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Trading Configuration</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <StrategySelector
          value={strategy}
          onChange={onStrategyChange}
        />

        {/* Symbol Selection Mode */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700">Symbol Selection Mode</label>
          <div className="flex space-x-4">
            <label className="flex items-center">
              <input
                type="radio"
                name="trading-symbol-mode"
                value="single"
                checked={symbolMode === 'single'}
                onChange={() => handleSymbolModeChange('single')}
                className="mr-2"
              />
              <span className="text-sm text-gray-700">Single Symbol</span>
            </label>
            <label className="flex items-center">
              <input
                type="radio"
                name="trading-symbol-mode"
                value="universe"
                checked={symbolMode === 'universe'}
                onChange={() => handleSymbolModeChange('universe')}
                className="mr-2"
              />
              <span className="text-sm text-gray-700">Universe</span>
            </label>
          </div>
        </div>

        {/* Single Symbol Configuration */}
        <div id="single-symbol-config" className="space-y-2">
          <label className="block text-sm font-medium text-gray-700">Trading Symbol</label>
          <select
            value={symbols.length > 1 ? symbols[0] : symbols[0] || 'BTC-USD'}
            onChange={(e) => {
              onSymbolsChange([e.target.value]);
            }}
            className="w-full border border-gray-300 rounded-md px-3 py-2"
          >
            {Object.entries(products || {}).map(([category, categorySymbols]) =>
              categorySymbols.map((symbol: string) => (
                <option key={symbol} value={symbol}>
                  {symbol}
                </option>
              ))
            )}
          </select>
        </div>

        {/* Universe Configuration */}
        <div id="universe-config" className="space-y-4" style={{ display: 'none' }}>
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-700">Universe Type</label>
            <select
              value={selectedUniverseType}
              onChange={(e) => handleUniverseTypeChange(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2"
            >
              <option value="all_products">All Products (Complete List)</option>
              <option value="all_usd">All USD Pairs (Recommended)</option>
              <option value="all_eur">All EUR Pairs</option>
              <option value="all_usdt">All USDT Pairs</option>
              <option value="all_btc">All BTC Pairs</option>
              <option value="major">Major Pairs (7 symbols)</option>
              <option value="minor">Minor Pairs (21 symbols)</option>
              <option value="crypto">Cryptocurrency (35 symbols)</option>
              <option value="custom">Custom</option>
            </select>
          </div>

          {/* Custom Symbols Configuration */}
          <div id="custom-symbols-config" className="space-y-2">
            <label className="block text-sm font-medium text-gray-700">Custom Symbols (comma-separated)</label>
            <Input
              type="text"
              placeholder="BTC-USD,ETH-USD,ADA-USD"
              value={symbols.join(',')}
              onChange={(e) => {
                const customSymbols = e.target.value.split(',').map(s => s.trim()).filter(s => s);
                onSymbolsChange(customSymbols);
              }}
              className="w-full"
            />
          </div>

          <p className="text-xs text-gray-500">
            Selected {symbols.length} symbols
          </p>
        </div>

        <StrategyConfigForm
          strategy={strategy}
          config={config}
          onChange={onConfigChange}
        />
      </CardContent>
    </Card>
  );
}

// Main Live Trading Panel Component
export default function LiveTradingPanel({ className = '' }: LiveTradingPanelProps) {
  const { status, startTrading, stopTrading, loading } = useLiveTrading();
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const { data: orderBookData, isLoading: signalsLoading } = useOrderBookSignals(
    status.symbols,
    status.isActive,
    currentPage,
    pageSize
  );
  const { data: portfolioData } = useLivePortfolio(true);

  const [strategy, setStrategy] = useState<TradingStrategy>('orderbook');
  const [config, setConfig] = useState<Record<string, any>>({
    position_size_mode: 'percent',
    position_size_value: 1,
    initial_portfolio_size: 10000,
  });
  const [symbols, setSymbols] = useState<string[]>(['BTC-USD']);

  useEffect(() => {
    if (portfolioData?.total_balance_usd) {
      setConfig(prevConfig => ({
        ...prevConfig,
        initial_portfolio_size: portfolioData.total_balance_usd,
      }));
    }
  }, [portfolioData]);

  const handleStartTrading = async () => {
    try {
      // Get max_positions from config, defaulting to 100 (max_positions_per_session default)
      const maxPositions = config.max_positions_per_session
        ? Number(config.max_positions_per_session)
        : 100;

      const tradingPayload: Parameters<typeof startTrading>[0] = {
        mode: 'live',
        strategy,
        symbols,
        parameters: {
          ...config,
          ...(config.position_size_mode === 'dollar' && config.position_size_value
            ? { position_size_usd: config.position_size_value }
            : {}),
        },
        max_positions: maxPositions,
        position_update_interval: 5,
      };

      if (config.position_size_mode === 'percent' && typeof config.position_size_value === 'number') {
        tradingPayload.position_size_percent = config.position_size_value;
      }

      await startTrading(tradingPayload);
    } catch (error) {
      console.error('Failed to start trading:', error);
    }
  };

  const handleStopTrading = async () => {
    try {
      await stopTrading();
    } catch (error) {
      console.error('Failed to stop trading:', error);
    }
  };

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Trading Configuration */}
      <TradingConfiguration
        strategy={strategy}
        onStrategyChange={setStrategy}
        config={config}
        onConfigChange={setConfig}
        symbols={symbols}
        onSymbolsChange={setSymbols}
      />

      {/* Trading Controls */}
      <Card>
        <CardHeader>
          <CardTitle>Trading Controls</CardTitle>
        </CardHeader>
        <CardContent>
          <TradingControls
            status={status}
            onStart={handleStartTrading}
            onStop={handleStopTrading}
            loading={loading}
          />

          {status.isActive && (
            <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded-md">
              <div className="flex items-center">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse mr-2"></div>
                <span className="text-sm text-green-800">
                  Trading active: {status.strategy} strategy with {status.symbols?.join(', ')}
                </span>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Order Book Signals */}
      {strategy === 'orderbook' && status.isActive && (
        <Card>
          <CardHeader>
            <CardTitle>Order Book Signals</CardTitle>
          </CardHeader>
          <CardContent>
            <OrderBookSignalsTable
              signals={orderBookData?.signals || []}
              pagination={orderBookData?.pagination}
              onPageChange={setCurrentPage}
              onPageSizeChange={setPageSize}
              summary={{
                total_analyzed: orderBookData?.total_analyzed ?? 0,
                active_signals: orderBookData?.active_signals ?? 0,
                average_strength: orderBookData?.average_strength ?? 0,
                last_updated: orderBookData?.last_updated ?? '',
              }}
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
