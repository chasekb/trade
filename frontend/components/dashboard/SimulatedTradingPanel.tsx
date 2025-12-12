'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { LiveTradingPanelProps, TradingStrategy } from '@/types/trading';
import { useQueryClient } from '@tanstack/react-query';
import { useLiveTrading, useOrderBookSignals, useProducts, useSimulatedTradingStats, useSimTradingWebSocket } from '@/hooks/useTrading';
import { OpenPositionsSection } from './OpenPositionsSection';
import { StrategySelector } from './StrategySelector';
import { TradingControls } from './TradingControls';
import { StrategyConfigForm } from './StrategyConfigForm';
import { OrderBookSignalsTable } from './OrderBookSignalsTable';
// Trading Configuration Section
function TradingConfiguration({
  strategy,
  onStrategyChange,
  config,
  onConfigChange,
  symbols,
  onSymbolsChange,
  onHide,
  status,
  updateStrategyParameters,
}: {
  strategy: TradingStrategy;
  onStrategyChange: (strategy: TradingStrategy) => void;
  config: Record<string, any>;
  onConfigChange: (config: Record<string, any>) => void;
  symbols: string[];
  onSymbolsChange: (symbols: string[]) => void;
  onHide?: () => void;
  status: { isActive: boolean };
  updateStrategyParameters: (params: Record<string, any>) => void;
}) {
  const { data: products } = useProducts();
  const [symbolMode, setSymbolMode] = useState<'single' | 'universe'>('single');
  const [selectedUniverseType, setSelectedUniverseType] = useState('all_usd');
  const [customInput, setCustomInput] = useState(symbols.join(','));

  // Sync customInput with symbols when symbols change externally
  useEffect(() => {
    const currentParsed = customInput.split(',').map(s => s.trim()).filter(s => s);
    const isDifferent = symbols.length !== currentParsed.length ||
      !symbols.every((s, i) => s === currentParsed[i]);

    if (isDifferent) {
      setCustomInput(symbols.join(','));
    }
  }, [symbols, customInput]);

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

    // First try to use backend categories if available
    if (products && products[universeType]) {
      filteredSymbols = products[universeType];
      console.log(`${universeType}: using backend category with ${filteredSymbols.length} symbols`);
    } else {
      // Fallback to client-side filtering
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
          // Major crypto pairs (fallback)
          const majorPairs = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'ADA-USD', 'DOT-USD', 'XRP-USD', 'LTC-USD'];
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
        <div className="flex items-center justify-between">
          <CardTitle>Trading Configuration</CardTitle>
          {onHide && (
            <Button size="sm" variant="secondary" onClick={onHide}>
              <i className="fas fa-eye-slash mr-1"></i>Hide Configuration
            </Button>
          )}
        </div>
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
              <option value="major">Major Pairs</option>
              <option value="minor">Minor Pairs</option>
              <option value="crypto">Cryptocurrency</option>
              <option value="custom">Custom</option>
            </select>
          </div>

          {/* Custom Symbols Configuration */}
          <div id="custom-symbols-config-simulated" className="space-y-2">
            <label className="block text-sm font-medium text-gray-700">Custom Symbols (comma-separated)</label>
            <Input
              type="text"
              placeholder="BTC-USD,ETH-USD,ADA-USD"
              value={customInput}
              onChange={(e) => {
                const newValue = e.target.value;
                setCustomInput(newValue);
                const customSymbols = newValue.split(',').map(s => s.trim()).filter(s => s);
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
          status={status}
          updateStrategyParameters={updateStrategyParameters}
        />
      </CardContent>
    </Card>
  );
}

// Main Simulated Trading Panel Component
// Simulated Trading Statistics Component
function SimulatedTradingStatistics({ isTradingActive }: { isTradingActive: boolean }) {
  const queryClient = useQueryClient();
  const { data: stats, isLoading, error } = useSimulatedTradingStats(isTradingActive);

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['simulated-trading-stats'] });
  };

  if (!isTradingActive) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Simulated Trading Statistics</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-gray-500">
            <p>Start trading to see simulated trading statistics.</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Simulated Trading Statistics</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8">
            <p>Loading statistics...</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || !stats?.portfolio) {
    return (
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <CardTitle>Simulated Trading Statistics</CardTitle>
            <Button variant="secondary" size="sm" onClick={handleRefresh}>
              <i className="fas fa-sync-alt mr-1"></i>Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-gray-500">
            <p>No statistics available. Trading may not be active.</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const portfolio = stats.portfolio;
  const trades = portfolio.trades || [];
  const positions = portfolio.positions || {};
  // Normalize positions to an array of open positions
  const openPositions = Array.isArray(positions)
    ? positions
    : Object.values(positions).filter((pos: any) => (pos?.status || 'open') === 'open');

  // Calculate derived statistics (similar to vanilla JS implementation)
  const winningTrades = trades.filter((trade: any) => trade.pnl > 0);
  const losingTrades = trades.filter((trade: any) => trade.pnl < 0);
  const totalTrades = trades.length;
  const winningTradesCount = winningTrades.length;
  const losingTradesCount = losingTrades.length;

  const completedTradesCount = trades.filter((t: any) => (t.side || '').toLowerCase() === 'sell').length;
  const denom = completedTradesCount || totalTrades;
  const winRate = denom > 0 ? (winningTradesCount / denom) * 100 : 0;

  const totalVolume = trades.reduce((sum: number, trade: any) => sum + (trade.quantity * trade.price), 0);
  const avgTradeSize = totalTrades > 0 ? totalVolume / totalTrades : 0;

  const bestTrade = trades.length > 0 ? Math.max(...trades.map((t: any) => t.pnl || 0)) : 0;
  const worstTrade = trades.length > 0 ? Math.min(...trades.map((t: any) => t.pnl || 0)) : 0;

  const avgWin = winningTradesCount > 0 ? winningTrades.reduce((sum: number, trade: any) => sum + trade.pnl, 0) / winningTradesCount : 0;
  const avgLoss = losingTradesCount > 0 ? losingTrades.reduce((sum: number, trade: any) => sum + trade.pnl, 0) / losingTradesCount : 0;

  const grossProfit = winningTrades.reduce((sum: number, trade: any) => sum + trade.pnl, 0);
  const grossLoss = Math.abs(losingTrades.reduce((sum: number, trade: any) => sum + trade.pnl, 0));
  const profitFactor = grossLoss > 0 ? grossProfit / grossLoss : (grossProfit > 0 ? Infinity : 0);

  const cashBalance = portfolio.cash_balance || 0;
  const totalValue = portfolio.total_value || 0;
  const totalPositionsValue = portfolio.total_positions_value || 0;
  const unrealizedPnl = portfolio.unrealized_pnl || 0;
  const realizedPnl = portfolio.realized_pnl || 0;
  const netPnl = portfolio.net_pnl || (unrealizedPnl + realizedPnl);
  const totalFees = portfolio.total_fees || 0;

  const activePositions = openPositions.length;

  const recentTrades = (portfolio.recent_trades || trades).slice(0, 10);
  // Merge and sort recent trades to ensure sells are included and latest first
  const mergedRecentTrades = Array.from(
    new Map(
      [...(portfolio.recent_trades || []), ...trades]
        .map((t: any) => [t.id || t.trade_id || `${t.symbol}-${t.timestamp}-${t.side}`, t])
    ).values()
  )
    .filter((t: any) => t && t.timestamp)
    .sort((a: any, b: any) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
    .slice(0, 10);

  return (
    <Card>
      <CardHeader>
        <div className="flex justify-between items-center">
          <CardTitle>Simulated Trading Statistics</CardTitle>
          <Button variant="secondary" size="sm" onClick={handleRefresh}>
            <i className="fas fa-sync-alt mr-1"></i>Refresh
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Main Statistics */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="text-center p-4 bg-blue-50 rounded-lg">
            <p className="text-sm text-gray-600">Total Net P&L</p>
            <p className={`text-2xl font-bold ${netPnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              ${netPnl.toFixed(2)}
            </p>
          </div>
          <div className="text-center p-4 bg-green-50 rounded-lg">
            <p className="text-sm text-gray-600">Win Rate</p>
            <p className="text-2xl font-bold text-green-600">{winRate.toFixed(1)}%</p>
          </div>
          <div className="text-center p-4 bg-purple-50 rounded-lg">
            <p className="text-sm text-gray-600">Total Trades</p>
            <p className="text-2xl font-bold text-purple-600">{totalTrades}</p>
          </div>
        </div>

        {/* Portfolio Overview */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-3 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-600">Cash Balance</p>
            <p className="text-lg font-semibold">${cashBalance.toFixed(2)}</p>
          </div>
          <div className="p-3 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-600">Total Value</p>
            <p className="text-lg font-semibold">${totalValue.toFixed(2)}</p>
          </div>
          <div className="p-3 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-600">Positions Value</p>
            <p className="text-lg font-semibold">${totalPositionsValue.toFixed(2)}</p>
          </div>
          <div className="p-3 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-600">Active Positions</p>
            <p className="text-lg font-semibold">{activePositions}</p>
          </div>
        </div>

        {/* P&L Breakdown */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-3 bg-blue-50 rounded-lg">
            <p className="text-sm text-gray-600">Unrealized P&L</p>
            <p className={`text-lg font-semibold ${unrealizedPnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              ${unrealizedPnl.toFixed(2)}
            </p>
          </div>
          <div className="p-3 bg-green-50 rounded-lg">
            <p className="text-sm text-gray-600">Realized P&L</p>
            <p className={`text-lg font-semibold ${realizedPnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              ${realizedPnl.toFixed(2)}
            </p>
          </div>
          <div className="p-3 bg-red-50 rounded-lg">
            <p className="text-sm text-gray-600">Total Fees</p>
            <p className="text-lg font-semibold text-red-600">${totalFees.toFixed(2)}</p>
          </div>
        </div>

        {/* Performance Metrics */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="space-y-4">
            <h4 className="font-semibold text-gray-700">Trade Performance</h4>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Average Win</span>
                <span className="text-sm font-medium text-green-600">${avgWin.toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Average Loss</span>
                <span className="text-sm font-medium text-red-600">${avgLoss.toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Best Trade</span>
                <span className="text-sm font-medium text-green-600">${bestTrade.toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Worst Trade</span>
                <span className="text-sm font-medium text-red-600">${worstTrade.toFixed(2)}</span>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <h4 className="font-semibold text-gray-700">Risk Metrics</h4>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Profit Factor</span>
                <span className="text-sm font-medium">
                  {profitFactor === Infinity ? '∞' : profitFactor.toFixed(2)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Total Volume</span>
                <span className="text-sm font-medium">${totalVolume.toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Avg Trade Size</span>
                <span className="text-sm font-medium">${avgTradeSize.toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Winning Trades</span>
                <span className="text-sm font-medium text-green-600">{winningTradesCount}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Losing Trades</span>
                <span className="text-sm font-medium text-red-600">{losingTradesCount}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Open Positions Table with Pagination */}
        {openPositions.length > 0 && (
          <OpenPositionsSection positions={openPositions} />
        )}

        {/* Recent Trades Table */}
        {mergedRecentTrades.length > 0 && (
          <div className="space-y-4">
            <h4 className="font-semibold text-gray-700">Recent Trades</h4>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Time</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Symbol</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Side</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Quantity</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Price</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">P&L</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {mergedRecentTrades.map((trade: any, index: number) => (
                    <tr key={index}>
                      <td className="px-4 py-2 text-sm text-gray-900">
                        {new Date(trade.timestamp || Date.now()).toLocaleString()}
                      </td>
                      <td className="px-4 py-2 text-sm text-gray-900">{trade.symbol || '-'}</td>
                      <td className="px-4 py-2 text-sm">
                        <span className={`px-2 py-1 rounded-full text-xs ${(trade.side || '').toUpperCase() === 'BUY'
                          ? 'bg-green-100 text-green-800'
                          : 'bg-red-100 text-red-800'
                          }`}>
                          {(trade.side || '').toUpperCase() || '-'}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-sm text-gray-900">
                        {typeof trade.quantity === 'number' ? trade.quantity.toFixed(4) : trade.quantity || 0}
                      </td>
                      <td className="px-4 py-2 text-sm text-gray-900">
                        ${typeof trade.price === 'number' ? trade.price.toFixed(2) : trade.price || 0}
                      </td>
                      <td className={`px-4 py-2 text-sm font-medium ${(trade.pnl || 0) >= 0 ? 'text-green-600' : 'text-red-600'
                        }`}>
                        ${(trade.pnl || 0).toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function SimulatedTradingPanel({ className = '' }: LiveTradingPanelProps) {
  const { status, startTrading, stopTrading, loading, updateStrategyParameters } = useLiveTrading();
  // Start native WebSocket to receive live updates for stats/signals
  useSimTradingWebSocket(status.isActive);

  // Use sessionStorage to persist pagination state across tab switches and component remounts
  const getStoredPage = () => {
    if (typeof window !== 'undefined') {
      const stored = sessionStorage.getItem('orderbook-signals-page');
      return stored ? parseInt(stored, 10) : 1;
    }
    return 1;
  };

  const getStoredPageSize = () => {
    if (typeof window !== 'undefined') {
      const stored = sessionStorage.getItem('orderbook-signals-pageSize');
      return stored ? parseInt(stored, 10) : 10;
    }
    return 10;
  };

  const [currentPage, setCurrentPage] = useState(getStoredPage);
  const [pageSize, setPageSize] = useState(getStoredPageSize);
  const queryClient = useQueryClient();

  const [strategy, setStrategy] = useState<TradingStrategy>('ml_enhanced_orderbook');
  const [config, setConfig] = useState<Record<string, any>>({
    position_size_mode: 'percent',
    position_size_value: 1,
    initial_portfolio_size: 10000,
  });
  const [symbols, setSymbols] = useState<string[]>(['BTC-USD']);

  // Use local symbols for polling; fallback to backend status if empty
  // Always pass symbols (even if empty) to enable query when trading is active

  // Sync local symbols state with active trading status
  useEffect(() => {
    if (status.isActive && status.symbols && status.symbols.length > 0) {
      // Only update if different to avoid infinite loops (though React handles identical state updates efficiently)
      const isDifferent = symbols.length !== status.symbols.length ||
        !symbols.every((s, i) => s === status.symbols![i]);

      if (isDifferent) {
        setSymbols(status.symbols);
      }
    }
  }, [status.isActive, status.symbols, symbols]);

  // Always pass symbols (even if empty) to enable query when trading is active
  const activeSymbols = (symbols && symbols.length > 0) ? symbols : (status.symbols || []);
  // Fetch a larger set of signals to enable proper sorting across all data while using client-side pagination
  const { data: orderBookData, isLoading: signalsLoading } = useOrderBookSignals(
    activeSymbols,
    status.isActive,
    1, // Always start from page 1 for the larger dataset
    10000, // Fetch many signals to enable sorting across all data
    strategy // Include strategy in query key to invalidate cache when strategy changes
  );
  const [configHidden, setConfigHidden] = useState(false);

  // The client-side merging logic has been removed.
  // The useOrderBookSignals hook will now refetch from the backend cache when the component mounts.


  // Handle pagination changes with persistence
  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('orderbook-signals-page', page.toString());
    }
  };

  const handlePageSizeChange = (newPageSize: number) => {
    setPageSize(newPageSize);
    setCurrentPage(1); // Reset to first page when changing page size
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('orderbook-signals-pageSize', newPageSize.toString());
      sessionStorage.setItem('orderbook-signals-page', '1');
    }
  };

  const handleStartTrading = async () => {
    try {
      // Get max_positions from config, defaulting to 100 (max_positions_per_session default)
      const maxPositions = config.max_positions_per_session
        ? Number(config.max_positions_per_session)
        : 100;

      const tradingPayload: Parameters<typeof startTrading>[0] = {
        mode: 'simulated',
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

      // Auto-hide strategy configuration when trading starts (like vanilla JS dashboard)
      setConfigHidden(true);
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

  const showConfiguration = () => {
    setConfigHidden(false);
  };

  const hideConfiguration = () => {
    setConfigHidden(true);
  };

  const signalsToDisplay = orderBookData?.signals || [];

  // Normalize optional summary fields for order book signals (prefer WebSocket data for real-time updates)
  const signalsSummary = {
    ...(orderBookData?.total_analyzed !== undefined ? { total_analyzed: orderBookData.total_analyzed as number } : {}),
    ...(orderBookData?.active_signals !== undefined ? { active_signals: orderBookData.active_signals as number } : {}),
    ...(orderBookData?.average_strength !== undefined ? { average_strength: orderBookData.average_strength as number } : {}),
    ...(orderBookData?.last_updated ? { last_updated: orderBookData.last_updated as string } : {}),
  } as {
    total_analyzed?: number;
    active_signals?: number;
    average_strength?: number;
    last_updated?: string;
  };

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Trading Configuration */}
      {!configHidden && (
        <TradingConfiguration
          strategy={strategy}
          onStrategyChange={setStrategy}
          config={config}
          onConfigChange={setConfig}
          symbols={symbols}
          onSymbolsChange={setSymbols}
          onHide={hideConfiguration}
          status={status}
          updateStrategyParameters={updateStrategyParameters}
        />
      )}

      {/* Show Strategy Configuration Button */}
      {configHidden && (
        <div className="text-center">
          <Button
            onClick={showConfiguration}
            className="px-4 py-2"
            variant="primary"
          >
            <i className="fas fa-eye mr-1"></i>Show Strategy Configuration
          </Button>
        </div>
      )}

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

      {/* Simulated Trading Statistics */}
      <SimulatedTradingStatistics isTradingActive={status.isActive} />

      {/* Order Book Signals */}
      {(strategy === 'orderbook' || strategy === 'ml_enhanced_orderbook') && status.isActive && (
        <Card>
          <CardHeader>
            <CardTitle>Order Book Signals</CardTitle>
          </CardHeader>
          <CardContent>
            <OrderBookSignalsTable
              signals={signalsToDisplay}
              pagination={orderBookData?.pagination}
              currentPage={currentPage}
              pageSize={pageSize}
              onPageChange={handlePageChange}
              onPageSizeChange={handlePageSizeChange}
              summary={signalsSummary}
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
