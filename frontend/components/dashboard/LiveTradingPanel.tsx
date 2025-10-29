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
    if (strategy === 'orderbook' && presets[presetName]) {
      const presetConfig = presets[presetName];
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
                    step={param.step}
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

        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700">Symbols</label>
          <select
            multiple
            value={symbols}
            onChange={(e) => {
              const selectedSymbols = Array.from(e.target.selectedOptions, option => option.value);
              onSymbolsChange(selectedSymbols);
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
          <p className="text-xs text-gray-500">
            Hold Ctrl/Cmd to select multiple symbols
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
    </div>
  );
}
