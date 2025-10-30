'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { DataTable } from '@/components/ui/DataTable';
import { LiveTradingPanelProps, TradingStrategy, TradingMode, SymbolMode, UniverseType, DataTableColumn, OrderBookSignal } from '@/types/trading';
import { useLiveTrading, useOrderBookSignals, useProducts, useStrategyParameters } from '@/hooks/useTrading';

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
    </div>
  );
}

// Order Book Signals Table Component
function OrderBookSignalsTable({ signals }: { signals: OrderBookSignal[] }) {
  const columns: DataTableColumn<OrderBookSignal>[] = [
    {
      key: 'symbol',
      header: 'Symbol',
      sortable: true,
    },
    {
      key: 'signal_generated',
      header: 'Status',
      sortable: true,
      render: (value) => (
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
          value ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
        }`}>
          {value ? 'Active' : 'Inactive'}
        </span>
      ),
    },
    {
      key: 'signal_strength',
      header: 'Strength',
      sortable: true,
      render: (value) => (
        <span className={value >= 0.7 ? 'text-green-600' : value >= 0.4 ? 'text-yellow-600' : 'text-red-600'}>
          {(value || 0).toFixed(2)}
        </span>
      ),
    },
    {
      key: 'timestamp',
      header: 'Time',
      sortable: true,
      render: (value) => new Date(value).toLocaleString(),
    },
  ];

  return (
    <DataTable
      data={signals || []}
      columns={columns}
      loading={false}
      className="w-full"
    />
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
    console.log('Symbol mode change:', mode);
    setSymbolMode(mode);
    if (mode === 'single') {
      onSymbolsChange(['BTC-USD']);
    } else {
      // For universe mode, apply the current universe type
      console.log('Applying universe type:', selectedUniverseType);
      applyUniverseType(selectedUniverseType);
    }
  };

  // Function to get all available symbols
  const getAllSymbols = (products: Record<string, string[]> | null | undefined): string[] => {
    if (!products) return [];
    return Object.values(products).flat().filter((symbol, index, arr) => arr.indexOf(symbol) === index);
  };

  // Function to filter symbols by universe type
  const applyUniverseType = (universeType: string) => {
    console.log('applyUniverseType called with:', universeType);
    console.log('Products data:', products);
    const allSymbols = getAllSymbols(products);
    console.log('All symbols:', allSymbols);

    let filteredSymbols: string[] = [];

    switch (universeType) {
      case 'all_products':
        filteredSymbols = allSymbols;
        console.log('all_products: using all symbols');
        break;
      case 'all_usd':
        filteredSymbols = allSymbols.filter(symbol => symbol.endsWith('-USD'));
        console.log('all_usd: filtered', allSymbols.length, 'to', filteredSymbols.length, 'symbols');
        break;
      case 'all_eur':
        filteredSymbols = allSymbols.filter(symbol => symbol.endsWith('-EUR'));
        console.log('all_eur: filtered', allSymbols.length, 'to', filteredSymbols.length, 'symbols');
        break;
      case 'all_usdt':
        filteredSymbols = allSymbols.filter(symbol => symbol.endsWith('-USDT'));
        console.log('all_usdt: filtered', allSymbols.length, 'to', filteredSymbols.length, 'symbols');
        break;
      case 'all_btc':
        filteredSymbols = allSymbols.filter(symbol => symbol.endsWith('-BTC'));
        console.log('all_btc: filtered', allSymbols.length, 'to', filteredSymbols.length, 'symbols');
        break;
      case 'major':
        // Major currency pairs
        const majorPairs = ['EUR-USD', 'GBP-USD', 'USD-JPY', 'USD-CHF', 'AUD-USD', 'USD-CAD', 'NZD-USD'];
        filteredSymbols = allSymbols.filter(symbol => majorPairs.includes(symbol));
        console.log('major: found', filteredSymbols.length, 'major pairs from', majorPairs.length, 'candidates');
        break;
      case 'minor':
        // Minor currency pairs (excluding major pairs)
        const minorPairs = allSymbols.filter(symbol =>
          symbol.endsWith('-USD') &&
          !['EUR-USD', 'GBP-USD', 'AUD-USD', 'NZD-USD'].includes(symbol) &&
          !symbol.includes('BTC') && !symbol.includes('ETH')
        ).slice(0, 21); // Limit to 21 as indicated
        filteredSymbols = minorPairs;
        console.log('minor: found', filteredSymbols.length, 'minor pairs');
        break;
      case 'crypto':
        // Cryptocurrency pairs
        filteredSymbols = allSymbols.filter(symbol =>
          symbol.includes('BTC') || symbol.includes('ETH') || symbol.includes('ADA') ||
          symbol.includes('SOL') || symbol.includes('DOT') || symbol.includes('XRP')
        ).slice(0, 35); // Limit to 35 as indicated
        console.log('crypto: found', filteredSymbols.length, 'crypto pairs');
        filteredSymbols = filteredSymbols;
        break;
      case 'custom':
      default:
        // For custom, don't auto-populate
        console.log('custom or default: not populating');
        return;
    }

    // Update symbols if filtered symbols were found
    console.log('Final filteredSymbols:', filteredSymbols);
    if (filteredSymbols.length > 0) {
      console.log('Calling onSymbolsChange with', filteredSymbols);
      onSymbolsChange(filteredSymbols);
    } else {
      console.log('No symbols found, not calling onSymbolsChange');
    }
  };

  const handleUniverseTypeChange = (universeType: string) => {
    setSelectedUniverseType(universeType);
    applyUniverseType(universeType);
  };

  useEffect(() => {
    // Update UI based on symbol mode
    const singleConfig = document.getElementById('single-symbol-config-simulated');
    const universeConfig = document.getElementById('universe-config-simulated');

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
                name="trading-symbol-mode-simulated"
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
                name="trading-symbol-mode-simulated"
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
        <div id="single-symbol-config-simulated" className="space-y-2">
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
        <div id="universe-config-simulated" className="space-y-4" style={{ display: 'none' }}>
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
          <div id="custom-symbols-config-simulated" className="space-y-2">
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

// Main Simulated Trading Panel Component
export default function SimulatedTradingPanel({ className = '' }: LiveTradingPanelProps) {
  const { status, startTrading, stopTrading, loading } = useLiveTrading();
  const { data: orderBookData, isLoading: signalsLoading } = useOrderBookSignals(
    status.symbols,
    status.isActive
  );

  const [strategy, setStrategy] = useState<TradingStrategy>('orderbook');
  const [config, setConfig] = useState<Record<string, any>>({});
  const [symbols, setSymbols] = useState<string[]>(['BTC-USD']);

  const handleStartTrading = async () => {
    try {
      await startTrading({
        mode: 'simulated',
        strategy,
        symbols,
        parameters: config,
        position_size_percent: 10,
        max_positions: 10,
        position_update_interval: 5,
      });
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
            <div className="flex items-center space-x-4 text-sm text-gray-600">
              {orderBookData && (
                <>
                  <span>Total Analyzed: {orderBookData.total_analyzed || 0}</span>
                  <span>Active Signals: {orderBookData.active_signals || 0}</span>
                  <span>Avg Strength: {(orderBookData.average_strength || 0).toFixed(2)}</span>
                  <span>Last Updated: {orderBookData.last_updated ? new Date(orderBookData.last_updated).toLocaleTimeString() : 'Never'}</span>
                </>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {!status.isActive ? (
              <div className="text-center py-8 text-gray-500">
                <p>Configure your strategy and start trading to see live signals.</p>
              </div>
            ) : signalsLoading ? (
              <div className="text-center py-8">
                <p>Loading signals...</p>
              </div>
            ) : orderBookData?.signals ? (
              <OrderBookSignalsTable signals={orderBookData.signals} />
            ) : (
              <div className="text-center py-8 text-gray-500">
                <p>No signals available.</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
