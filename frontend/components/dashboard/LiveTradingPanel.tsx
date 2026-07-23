'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { DataTable } from '@/components/ui/DataTable';
import Tooltip from '@/components/ui/Tooltip';
import { LiveTradingPanelProps, TradingStrategy, TradingMode, SymbolMode, UniverseType, DataTableColumn, OrderBookSignal } from '@/types/trading';
import { useQueryClient } from '@tanstack/react-query';
import { useLiveTrading, useOrderBookSignals, useProducts, useStrategyParameters, useLiveTabProducer, useMLModels } from '@/hooks/useTrading';
import { useModelTraining } from '@/hooks/useModelTraining';
import { normalizeSimulatedTradingSnapshot } from '@/lib/simulatedTradingStats';
import { firstLiveTabProducerBlocker, normalizeLiveTabProducerSnapshot } from '@/lib/liveTabProducer';

import { OpenPositionsSection } from './OpenPositionsSection';
import { RecentTradesTable } from './RecentTradesTable';
import { StrategySelector } from './StrategySelector';
import { TradingControls } from './TradingControls';
import { StrategyConfigForm } from './StrategyConfigForm';
import { OrderBookSignalsTable } from './OrderBookSignalsTable';
import { ManualTradeSection } from './ManualTradeSection';
import { BotActivityLog } from './BotActivityLog';

type TradingConfigState = {
  position_size_mode: 'percent' | 'dollar' | string;
  position_size_value: number;
  initial_portfolio_size: number;
  max_positions_per_session?: number | string;
  [key: string]: string | number | boolean | undefined;
};

type CoinbaseProduct = {
  status?: string;
  trading_disabled?: boolean;
  id?: string;
};

type TradeLike = {
  id?: string;
  trade_id?: string;
  symbol?: string;
  side?: string;
  quantity?: number;
  price?: number;
  fee?: number;
  pnl?: number;
  timestamp?: string | number;
};

type PositionLike = {
  symbol?: string;
  status?: string;
  session_managed?: boolean;
  asset?: string;
  balance_crypto?: number;
  balance_fiat?: number;
  unrealized_pnl?: number;
};

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
  config: TradingConfigState;
  onConfigChange: React.Dispatch<React.SetStateAction<TradingConfigState>>;
  symbols: string[];
  onSymbolsChange: (symbols: string[]) => void;
  onHide?: () => void;
  status: { isActive: boolean };
  updateStrategyParameters: (params: Record<string, string | number | boolean | undefined>) => void;
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
      const response = await fetch('https://api.exchange.coinbase.com/products');
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const products: CoinbaseProduct[] = await response.json();
      const symbols = products
        .filter((product) => product.status === 'online' && !product.trading_disabled && typeof product.id === 'string')
        .map((product) => product.id)
        .filter((id): id is string => Boolean(id))
        .sort();
      return symbols;
    } catch (error) {
      console.error('Error fetching Coinbase symbols:', error);
      throw error;
    }
  };

  // Function to filter symbols by universe type
  const applyUniverseType = async (universeType: string) => {

    let allSymbols = getAllSymbols(products);

    // If no symbols from hook, try to fetch from Coinbase directly
    if (allSymbols.length === 0) {
      try {
        const symbols = await fetchCoinbaseSymbols();
        allSymbols = symbols;
      } catch (error) {
        console.warn('Failed to fetch Coinbase symbols:', error);
        allSymbols = ['BTC-USD', 'ETH-USD', 'ADA-USD', 'SOL-USD', 'DOT-USD', 'XRP-USD'];
      }
    }


    let filteredSymbols: string[] = [];

    // First try to use backend categories if available
    if (products && products[universeType]) {
      filteredSymbols = products[universeType];
    } else {
      // Fallback to client-side filtering
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
          // Major crypto pairs (fallback)
          const majorPairs = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'ADA-USD', 'DOT-USD', 'XRP-USD', 'LTC-USD'];
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
    }

    // Update symbols if filtered symbols were found
    if (filteredSymbols.length > 0) {
      onSymbolsChange(filteredSymbols);
    } else {
    }
  };

  const handleUniverseTypeChange = (universeType: string) => {
    setSelectedUniverseType(universeType);
    applyUniverseType(universeType);
  };

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
                name="trading-symbol-mode-live"
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
                name="trading-symbol-mode-live"
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
        {symbolMode === 'single' && (
        <div className="space-y-2">
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
        )}

        {/* Universe Configuration */}
        {symbolMode === 'universe' && (
        <div className="space-y-4">
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
          <div className="space-y-2">
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
        )}

        <StrategyConfigForm
          strategy={strategy}
          config={config}
          onChange={onConfigChange}
          status={status}
          updateStrategyParameters={updateStrategyParameters}
          showInitialPortfolioSize={false}
        />
      </CardContent>
    </Card>
  );
}

// Live Trading Statistics: session statistics come from the canonical
// snapshot layer (full-session stats block, not the capped trade list);
// portfolio tiles prefer the real Coinbase account portfolio when configured.
function LiveTradingStatistics() {
  const queryClient = useQueryClient();
  const { closePosition, liquidateCoinbaseHoldings } = useLiveTrading('live');
  const { data: portfolioData, isLoading: portfolioLoading, error: portfolioError } = useLiveTabProducer(true);
  const sessionData = portfolioData;

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['live-portfolio-status'] });
    queryClient.invalidateQueries({ queryKey: ['live-tab-producer'] });
    queryClient.invalidateQueries({ queryKey: ['trading-status', 'live'] });
  };

  const handleClosePosition = async (symbol: string) => {
    try {
      await closePosition(symbol);
    } catch (error) {
      console.error('Failed to close position:', error);
    }
  };

  const handleLiquidateHoldings = async (symbols?: string[]) => {
    const target = symbols && symbols.length === 1 ? symbols[0] : 'all Coinbase holdings';
    const confirmed = window.confirm(
      `This will submit real Coinbase sell orders to liquidate ${target}. Continue?`
    );
    if (!confirmed) {
      return;
    }
    try {
      await liquidateCoinbaseHoldings(symbols);
      handleRefresh();
    } catch (error) {
      console.error('Failed to liquidate Coinbase holdings:', error);
    }
  };

  if (portfolioLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Live Portfolio & Trading Statistics</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8">
            <p>Loading portfolio data...</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const liveProducer = normalizeLiveTabProducerSnapshot(portfolioData ?? {});
  const setupRequired = !liveProducer.credentialsConfigured || Boolean(
    portfolioError && (portfolioError.message.includes('400') || portfolioError.message.includes('setup_required'))
  );

  const snapshot = normalizeSimulatedTradingSnapshot(sessionData ?? {});
  const statsView = snapshot.stats;

  // Portfolio tiles are produced from the authoritative Coinbase account snapshot.
  const cashBalance = liveProducer.cashBalance;
  const totalValue = liveProducer.totalValue;
  const totalPositionsValue = liveProducer.totalPositionsValue;

  const coinbasePositions = liveProducer.positions as PositionLike[];
  const openPositions = coinbasePositions;
  const activePositions = coinbasePositions.length;
  const liquidationDisabledReason = liveProducer.canTrade
    ? null
    : firstLiveTabProducerBlocker(liveProducer) || 'Live trading and explicit Coinbase order execution are required.';

  const profitFactor = Number(statsView.profit_factor);
  const formattedProfitFactor = profitFactor >= 999 ? '∞' : profitFactor.toFixed(2);

  return (
    <Card>
      <CardHeader>
        <div className="flex justify-between items-center">
          <CardTitle>Live Portfolio & Trading Statistics</CardTitle>
          <Button variant="secondary" size="sm" onClick={handleRefresh}>
            <i className="fas fa-sync-alt mr-1"></i>Refresh
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {setupRequired && (
          <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-md">
            <h3 className="text-sm font-medium text-yellow-900 mb-1">
              <i className="fas fa-exclamation-circle mr-1"></i>Coinbase API Setup Required
            </h3>
            <p className="text-sm text-yellow-800 mb-2">
              Configure Coinbase credentials to view your real portfolio and place live orders.
            </p>
            <p className="text-xs font-mono text-yellow-900">COINBASE_API_KEY=your_key</p>
            <p className="text-xs font-mono text-yellow-900">COINBASE_API_SECRET=your_secret</p>
          </div>
        )}

        {/* Main Statistics */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="text-center p-4 bg-blue-50 rounded-lg">
            <p className="text-sm text-gray-600">Total Net P&L</p>
            <p className={`text-2xl font-bold ${snapshot.netPnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              ${snapshot.netPnl.toFixed(2)}
            </p>
          </div>
          <div className="text-center p-4 bg-green-50 rounded-lg">
            <p className="text-sm text-gray-600">Win Rate</p>
            <p className="text-2xl font-bold text-green-600">{statsView.win_rate.toFixed(1)}%</p>
          </div>
          <div className="text-center p-4 bg-purple-50 rounded-lg">
            <p className="text-sm text-gray-600">Total Trades</p>
            <p className="text-2xl font-bold text-purple-600">{statsView.total_trades}</p>
          </div>
        </div>

        {/* Portfolio Overview */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-3 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-600">Cash Balance (Coinbase)</p>
            <p className="text-lg font-semibold">${cashBalance.toFixed(2)}</p>
          </div>
          <div className="p-3 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-600">Total Value (Coinbase)</p>
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
            <p className={`text-lg font-semibold ${snapshot.unrealizedPnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              ${snapshot.unrealizedPnl.toFixed(2)}
            </p>
          </div>
          <div className="p-3 bg-green-50 rounded-lg">
            <p className="text-sm text-gray-600">Realized P&L</p>
            <p className={`text-lg font-semibold ${snapshot.realizedPnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              ${snapshot.realizedPnl.toFixed(2)}
            </p>
          </div>
          <div className="p-3 bg-red-50 rounded-lg">
            <p className="text-sm text-gray-600">Total Fees</p>
            <p className="text-lg font-semibold text-red-600">${snapshot.totalFees.toFixed(2)}</p>
          </div>
        </div>

        {/* Performance Metrics */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="space-y-4">
            <h4 className="font-semibold text-gray-700">Trade Performance</h4>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Average Win</span>
                <span className="text-sm font-medium text-green-600">${statsView.avg_win.toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Average Loss</span>
                <span className="text-sm font-medium text-red-600">${statsView.avg_loss.toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Best Trade</span>
                <span className="text-sm font-medium text-green-600">${statsView.best_trade.toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Worst Trade</span>
                <span className="text-sm font-medium text-red-600">${statsView.worst_trade.toFixed(2)}</span>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <h4 className="font-semibold text-gray-700">Risk Metrics</h4>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Profit Factor</span>
                <span className="text-sm font-medium">{formattedProfitFactor}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Total Volume</span>
                <span className="text-sm font-medium">${statsView.total_volume.toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Avg Trade Size</span>
                <span className="text-sm font-medium">${statsView.avg_trade_size.toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Winning Trades</span>
                <span className="text-sm font-medium text-green-600">{statsView.winning_trades}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Losing Trades</span>
                <span className="text-sm font-medium text-red-600">{statsView.losing_trades}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Open Positions Table with Pagination */}
        {openPositions.length > 0 && (
          <OpenPositionsSection
            positions={openPositions}
            onClose={handleClosePosition}
            onLiquidateHolding={(symbol) => handleLiquidateHoldings([symbol])}
            onLiquidateAllHoldings={() => handleLiquidateHoldings()}
            liquidationDisabledReason={liquidationDisabledReason}
          />
        )}

        {/* Recent Trades Table */}
        {snapshot.recentTrades.length > 0 && (
          <RecentTradesTable trades={snapshot.recentTrades} includeFees />
        )}
      </CardContent>
    </Card>
  );
}

export default function LiveTradingPanel({ className = '' }: LiveTradingPanelProps) {
  const { status, startTrading, stopTrading, loading, updateStrategyParameters } = useLiveTrading('live');
  const { data: producerData, isLoading: producerLoading } = useLiveTabProducer(true);
  const producer = normalizeLiveTabProducerSnapshot(producerData ?? {});

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

  const [strategy, setStrategy] = useState<TradingStrategy>('ml_enhanced_orderbook');
  const [config, setConfig] = useState<TradingConfigState>({
    position_size_mode: 'percent',
    position_size_value: 1,
    initial_portfolio_size: 0,
    stop_loss_percent: 0,
    take_profit_percent: 0,
    // Safety default: signals run on live market data but no exchange orders
    // are placed until this is explicitly enabled.
    live_order_execution: false,
  });
  const [symbols, setSymbols] = useState<string[]>(['BTC-USD']);
  const startDisabledReason = useMemo(() => {
    if (producerLoading) return 'Loading Coinbase portfolio readiness...';
    if (!producer.credentialsConfigured) return 'Configure Coinbase credentials before starting live trading.';
    if (!producer.accountSnapshotLoaded) return firstLiveTabProducerBlocker(producer) || 'Coinbase account snapshot is not loaded.';
    if (producer.errors.length > 0) return firstLiveTabProducerBlocker(producer) || 'Coinbase portfolio refresh is currently failing.';
    if (!config.live_order_execution) return 'Confirm that this session may place real Coinbase orders.';
    return null;
  }, [config.live_order_execution, producer, producerLoading]);

  // Use local symbols for polling; fallback to backend status if empty
  // Always pass symbols (even if empty) to enable query when trading is active
  const activeSymbols = (status.isActive && status.symbols && status.symbols.length > 0)
    ? status.symbols
    : (symbols && symbols.length > 0 ? symbols : []);
  const { data: orderBookData, isLoading: signalsLoading } = useOrderBookSignals(
    activeSymbols,
    status.isActive,
    currentPage,
    pageSize,
    strategy
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
        mode: 'live',
        strategy,
        symbols,
        parameters: Object.fromEntries(
          Object.entries(config).filter(
            ([key]) => !['initial_portfolio_size', 'initial_balance', 'capital'].includes(key)
          )
        ),
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
          <div className="mb-4 flex items-center space-x-2">
            <input
              type="checkbox"
              id="live-order-execution"
              checked={Boolean(config.live_order_execution)}
              onChange={(e) => setConfig((prev) => ({ ...prev, live_order_execution: e.target.checked }))}
              disabled={status.isActive}
            />
            <label htmlFor="live-order-execution" className="text-sm text-gray-700">
              I confirm this session may place real Coinbase orders (required to start live trading)
            </label>
          </div>
          <TradingControls
            status={status}
            onStart={handleStartTrading}
            onStop={handleStopTrading}
            loading={loading}
            startDisabledReason={startDisabledReason}
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

      {/* Bot Activity Log */}
      <BotActivityLog />

      {/* Manual Trade Execution */}
      <ManualTradeSection symbols={activeSymbols} />

      {/* Live Trading Statistics */}
      <LiveTradingStatistics />

      {/* Order Book Signals */}
      {status.isActive && (
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
