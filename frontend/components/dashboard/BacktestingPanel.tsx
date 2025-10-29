'use client';

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { DataTable } from '@/components/ui/DataTable';
import {
  BacktestFormProps,
  BacktestControlsProps,
  BacktestResultsProps,
  TradingStrategy,
  DataTableColumn
} from '@/types/trading';
import { useProducts, useBacktest, useStrategyParameters } from '@/hooks/useTrading';

// Backtest Form Component
function BacktestForm({
  parameters,
  onChange,
  products
}: BacktestFormProps) {
  const { getStrategyParameters } = useStrategyParameters();
  const strategyParams = getStrategyParameters(parameters.strategy);

  const handleStrategyChange = (strategy: TradingStrategy) => {
    onChange({ strategy });
  };

  const handleSymbolsChange = (symbols: string[]) => {
    onChange({ symbols });
  };

  const handleDateChange = (field: 'startDate' | 'endDate', value: string) => {
    onChange({ [field]: value });
  };

  const handleConfigChange = (config: Record<string, any>) => {
    onChange({ config });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Backtest Configuration</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Strategy Selection */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700">Strategy</label>
          <select
            value={parameters.strategy}
            onChange={(e) => handleStrategyChange(e.target.value as TradingStrategy)}
            className="w-full border border-gray-300 rounded-md px-3 py-2"
          >
            <option value="orderbook">Order Book Signals</option>
            <option value="sma">Simple Moving Average</option>
            <option value="ema">Exponential Moving Average</option>
            <option value="rsi">RSI Strategy</option>
            <option value="bollinger">Bollinger Bands</option>
            <option value="macd">MACD Strategy</option>
            <option value="stochastic">Stochastic Oscillator</option>
            <option value="fibonacci">Fibonacci Retracement</option>
            <option value="dca">Dollar Cost Average</option>
            <option value="buyandhold">Buy and Hold</option>
          </select>
        </div>

        {/* Symbol Selection */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700">Symbols</label>
          <select
            multiple
            value={parameters.symbols}
            onChange={(e) => {
              const selectedSymbols = Array.from(e.target.selectedOptions, option => option.value);
              handleSymbolsChange(selectedSymbols);
            }}
            className="w-full border border-gray-300 rounded-md px-3 py-2"
          >
            {Object.entries(products).map(([category, categorySymbols]) =>
              categorySymbols.map((symbol: string) => (
                <option key={symbol} value={symbol}>
                  {symbol}
                </option>
              ))
            )}
          </select>
          <p className="text-xs text-gray-500">
            Hold Ctrl/Cmd to select multiple symbols. Selected: {parameters.symbols.join(', ') || 'None'}
          </p>
        </div>

        {/* Date Range Selection */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-700">Start Date</label>
            <Input
              type="date"
              value={parameters.startDate}
              onChange={(e) => handleDateChange('startDate', e.target.value)}
              className="w-full"
            />
          </div>
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-700">End Date</label>
            <Input
              type="date"
              value={parameters.endDate}
              onChange={(e) => handleDateChange('endDate', e.target.value)}
              className="w-full"
            />
          </div>
        </div>

        {/* Strategy Parameters */}
        {strategyParams.length > 0 && (
          <div className="space-y-4">
            <h4 className="text-md font-semibold text-gray-700">Strategy Parameters</h4>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {strategyParams.map(param => (
                <div key={param.name} className="space-y-2">
                  <label className="block text-sm font-medium text-gray-700">
                    {param.label}
                  </label>
                  {param.type === 'select' ? (
                    <select
                      value={parameters.config[param.name] || param.default}
                      onChange={(e) => handleConfigChange({
                        ...parameters.config,
                        [param.name]: e.target.value
                      })}
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
                      value={parameters.config[param.name] || param.default}
                      onChange={(e) => handleConfigChange({
                        ...parameters.config,
                        [param.name]: e.target.value
                      })}
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
      </CardContent>
    </Card>
  );
}

// Backtest Controls Component
function BacktestControls({ onRun, loading, canRun }: BacktestControlsProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Backtest Execution</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between">
          <div className="text-sm text-gray-600">
            {loading ? 'Running backtest...' : 'Ready to run backtest'}
          </div>
          <Button
            onClick={onRun}
            disabled={loading || !canRun}
            variant="primary"
          >
            {loading ? 'Running...' : 'Run Backtest'}
          </Button>
        </div>

        {loading && (
          <div className="mt-4 w-full bg-gray-200 rounded-full h-2">
            <div className="bg-blue-600 h-2 rounded-full animate-pulse" style={{ width: '100%' }}></div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// Backtest Results Component
function BacktestResults({ results, loading }: BacktestResultsProps) {
  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Backtest Results</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Processing backtest results...</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!results) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Backtest Results</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-gray-500">
            <p>No backtest results available. Run a backtest to see results.</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Mock results structure - in real implementation this would match the API response
  const mockResults = {
    summary: {
      total_trades: results.total_trades || 0,
      winning_trades: results.winning_trades || 0,
      losing_trades: results.losing_trades || 0,
      win_rate: results.win_rate || 0,
      total_pnl: results.total_pnl || 0,
      net_pnl: results.net_pnl || 0,
      max_drawdown: results.max_drawdown || 0,
      sharpe_ratio: results.sharpe_ratio || 0,
      profit_factor: results.profit_factor || 0,
    },
    trades: results.trades || [],
    performance: results.performance || {},
    charts: results.charts || {},
  };

  const summaryColumns: DataTableColumn<any>[] = [
    { key: 'metric', header: 'Metric', sortable: true },
    { key: 'value', header: 'Value', sortable: true, render: (value, item) => {
      if (item.format === 'currency') {
        return <span className={value >= 0 ? 'text-green-600' : 'text-red-600'}>
          ${typeof value === 'number' ? value.toFixed(2) : value}
        </span>;
      }
      if (item.format === 'percentage') {
        return `${typeof value === 'number' ? value.toFixed(2) : value}%`;
      }
      return value;
    }},
  ];

  const summaryData = [
    { metric: 'Total Trades', value: mockResults.summary.total_trades, format: 'number' },
    { metric: 'Winning Trades', value: mockResults.summary.winning_trades, format: 'number' },
    { metric: 'Losing Trades', value: mockResults.summary.losing_trades, format: 'number' },
    { metric: 'Win Rate', value: mockResults.summary.win_rate, format: 'percentage' },
    { metric: 'Total P&L', value: mockResults.summary.total_pnl, format: 'currency' },
    { metric: 'Net P&L', value: mockResults.summary.net_pnl, format: 'currency' },
    { metric: 'Max Drawdown', value: mockResults.summary.max_drawdown, format: 'currency' },
    { metric: 'Sharpe Ratio', value: mockResults.summary.sharpe_ratio, format: 'number' },
    { metric: 'Profit Factor', value: mockResults.summary.profit_factor, format: 'number' },
  ];

  const tradeColumns: DataTableColumn<any>[] = [
    { key: 'timestamp', header: 'Date', sortable: true, render: (value) => new Date(value).toLocaleString() },
    { key: 'symbol', header: 'Symbol', sortable: true },
    { key: 'side', header: 'Side', sortable: true, render: (value) => (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
        value?.toLowerCase() === 'buy' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
      }`}>
        {value?.toUpperCase()}
      </span>
    )},
    { key: 'quantity', header: 'Quantity', sortable: true, render: (value) => typeof value === 'number' ? value.toFixed(6) : value },
    { key: 'price', header: 'Price', sortable: true, render: (value) => `$${typeof value === 'number' ? value.toFixed(2) : value}` },
    { key: 'pnl', header: 'P&L', sortable: true, render: (value) => (
      <span className={value >= 0 ? 'text-green-600' : 'text-red-600'}>
        ${typeof value === 'number' ? value.toFixed(2) : value}
      </span>
    )},
  ];

  return (
    <div className="space-y-6">
      {/* Performance Summary */}
      <Card>
        <CardHeader>
          <CardTitle>Performance Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <DataTable
            data={summaryData}
            columns={summaryColumns}
            className="w-full"
          />
        </CardContent>
      </Card>

      {/* Trade History */}
      {mockResults.trades.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Trade History ({mockResults.trades.length} trades)</CardTitle>
          </CardHeader>
          <CardContent>
            <DataTable
              data={mockResults.trades}
              columns={tradeColumns}
              className="w-full"
              pagination={{
                currentPage: 1,
                totalPages: Math.ceil(mockResults.trades.length / 10),
                onPageChange: () => {},
              }}
            />
          </CardContent>
        </Card>
      )}

      {/* Performance Chart Placeholder */}
      <Card>
        <CardHeader>
          <CardTitle>Equity Curve</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-64 bg-gray-50 rounded-lg flex items-center justify-center">
            <div className="text-center text-gray-500">
              <div className="w-16 h-16 bg-gray-200 rounded-full mx-auto mb-4 flex items-center justify-center">
                📈
              </div>
              <p>Equity curve visualization would be displayed here</p>
              <p className="text-sm">Chart implementation would use Chart.js or similar library</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// Main Backtesting Panel Component
export default function BacktestingPanel() {
  const { data: products } = useProducts();
  const backtestMutation = useBacktest();

  const [parameters, setParameters] = useState({
    strategy: 'orderbook' as TradingStrategy,
    symbols: ['BTC-USD'],
    startDate: new Date(Date.now() - 365 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    endDate: new Date().toISOString().split('T')[0],
    config: {} as Record<string, any>,
  });

  const [results, setResults] = useState<any>(null);

  const handleRunBacktest = async () => {
    try {
      setResults(null); // Clear previous results
      const response = await backtestMutation.mutateAsync({
        strategy: parameters.strategy,
        symbols: parameters.symbols,
        parameters: parameters.config,
        start_date: parameters.startDate,
        end_date: parameters.endDate,
      });

      if (response.status === 'success') {
        setResults(response.data);
      } else {
        console.error('Backtest failed:', response.error);
      }
    } catch (error) {
      console.error('Backtest error:', error);
    }
  };

  const canRun = Boolean(
    parameters.symbols.length > 0 &&
    parameters.startDate &&
    parameters.endDate &&
    new Date(parameters.startDate) < new Date(parameters.endDate)
  );

  return (
    <div className="space-y-6">
      {/* Backtest Form */}
      <BacktestForm
        parameters={parameters}
        onChange={(updates) => setParameters(prev => ({ ...prev, ...updates }))}
        products={products || {}}
      />

      {/* Backtest Controls */}
      <BacktestControls
        onRun={handleRunBacktest}
        loading={backtestMutation.isPending}
        canRun={canRun}
      />

      {/* Backtest Results */}
      <BacktestResults
        results={results}
        loading={backtestMutation.isPending && !results}
      />
    </div>
  );
}
