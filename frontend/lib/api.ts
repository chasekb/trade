// API client for trading dashboard
import { ApiResponse, TradingStats, Position, PaginatedResponse, PaginationParams, OrderBookSignal } from '@/types/trading';

// Always use same-origin requests from the browser and let Next.js rewrites
// proxy to the appropriate backend target for the current environment.
const FORCE_LOCAL_SIM_TRADING = process.env.NEXT_PUBLIC_FORCE_LOCAL_SIM_TRADING === 'true' || process.env.NEXT_PUBLIC_FORCE_LOCAL_SIM_TRADING === '1';
const API_BASE_URL = '';

type LocalSimPosition = {
  symbol: string;
  side: 'buy' | 'sell';
  quantity: number;
  entry_price: number;
  entry_notional: number;
  current_price: number;
  unrealized_pnl: number;
  pnl_percentage: number;
  entry_time: string;
  status: 'open';
  age_ticks: number;
  entry_win_probability: number;
  entry_expected_return: number;
  entry_model_confidence: number;
};

type LocalSimTrade = {
  id: string;
  trade_id: string;
  symbol: string;
  side: 'buy' | 'sell';
  quantity: number;
  price: number;
  pnl: number;
  timestamp: string;
  fees: number;
  win_probability: number;
  expected_return: number;
  model_confidence: number;
};

type LocalSimPortfolio = {
  initial_capital: number;
  cash_balance: number;
  total_value: number;
  total_positions_value: number;
  unrealized_pnl: number;
  realized_pnl: number;
  net_pnl: number;
  total_fees: number;
  positions: Record<string, LocalSimPosition>;
  trades: LocalSimTrade[];
  recent_trades: LocalSimTrade[];
};

type LocalSimTradingSession = {
  active: boolean;
  strategy: string;
  symbols: string[];
  parameters: Record<string, any>;
  startedAt: string;
  updatedAt: string;
  tick: number;
  portfolio: LocalSimPortfolio;
};

let localSimTradingSession: LocalSimTradingSession | null = null;

function setLocalSimTradingSession(strategy: string, symbols: string[], parameters: Record<string, any>) {
  const now = new Date().toISOString();
  const initialCapital = Number(parameters.initial_portfolio_size ?? parameters.capital ?? 10000);
  localSimTradingSession = {
    active: true,
    strategy,
    symbols: symbols.length > 0 ? symbols : ['BTC-USD'],
    parameters,
    startedAt: now,
    updatedAt: now,
    tick: 0,
    portfolio: {
      initial_capital: initialCapital,
      cash_balance: initialCapital,
      total_value: initialCapital,
      total_positions_value: 0,
      unrealized_pnl: 0,
      realized_pnl: 0,
      net_pnl: 0,
      total_fees: 0,
      positions: {},
      trades: [],
      recent_trades: [],
    },
  };
}

function clearLocalSimTradingSession() {
  localSimTradingSession = null;
}

function basePriceForSymbol(symbol: string): number {
  const upper = symbol.toUpperCase();
  if (upper.includes('BTC')) return 65000;
  if (upper.includes('ETH')) return 3500;
  if (upper.includes('SOL')) return 160;
  if (upper.includes('ADA')) return 0.45;
  if (upper.includes('XRP')) return 0.55;
  return 100;
}

function syntheticSignalReason(strategy: string): string {
  return strategy === 'ml_enhanced_orderbook'
    ? 'Synthetic ML-enhanced order book pattern detected'
    : 'Synthetic order book imbalance detected';
}

function localSignalWinProbability(signal: OrderBookSignal): number {
  const fromMl = signal.ml_analysis?.win_probability;
  if (typeof fromMl === 'number' && Number.isFinite(fromMl)) {
    return fromMl;
  }
  const fallback = 0.5 + (signal.signal_strength - 0.5) * 0.35;
  return Number(Math.max(0.05, Math.min(0.95, fallback)).toFixed(3));
}

function localSignalComparator(a: OrderBookSignal, b: OrderBookSignal): number {
  const strengthDelta = (b.signal_strength || 0) - (a.signal_strength || 0);
  if (Math.abs(strengthDelta) > 1e-9) {
    return strengthDelta;
  }

  const winProbDelta = localSignalWinProbability(b) - localSignalWinProbability(a);
  if (Math.abs(winProbDelta) > 1e-9) {
    return winProbDelta;
  }

  return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
}

function localTradeId(symbol: string, tick: number, sequence: number): string {
  return `local-trade-${symbol}-${tick}-${sequence}`;
}

function updateLocalPortfolioMarkToMarket(session: LocalSimTradingSession, prices: Record<string, number>) {
  const portfolio = session.portfolio;
  let unrealizedPnl = 0;
  let totalPositionsValue = 0;
  let signedPositionsValue = 0;

  Object.values(portfolio.positions).forEach((position) => {
    const currentPrice = prices[position.symbol] ?? position.current_price;
    position.current_price = currentPrice;
    const isLong = position.side === 'buy';
    const direction = isLong ? 1 : -1;
    const currentNotional = position.quantity * currentPrice;

    position.unrealized_pnl = isLong
      ? (currentPrice - position.entry_price) * position.quantity
      : (position.entry_price - currentPrice) * position.quantity;
    position.pnl_percentage = position.entry_notional > 0
      ? (position.unrealized_pnl / position.entry_notional) * 100
      : 0;
    position.age_ticks += 1;
    unrealizedPnl += position.unrealized_pnl;
    totalPositionsValue += Math.abs(currentNotional);
    signedPositionsValue += direction * currentNotional;
  });

  portfolio.unrealized_pnl = unrealizedPnl;
  portfolio.total_positions_value = totalPositionsValue;
  portfolio.total_fees = portfolio.total_fees || 0;
  portfolio.total_value = portfolio.cash_balance + signedPositionsValue;
  portfolio.net_pnl = portfolio.realized_pnl + portfolio.unrealized_pnl - portfolio.total_fees;
}

function appendLocalTrade(session: LocalSimTradingSession, trade: LocalSimTrade) {
  const portfolio = session.portfolio;
  portfolio.trades.push(trade);
  portfolio.recent_trades.push(trade);
  const maxTrades = 250;
  if (portfolio.trades.length > maxTrades) {
    portfolio.trades.splice(0, portfolio.trades.length - maxTrades);
  }
  if (portfolio.recent_trades.length > 50) {
    portfolio.recent_trades.splice(0, portfolio.recent_trades.length - 50);
  }
}

export function calculateLocalAllocatedUsd(
  totalValue: number,
  initialCapital: number,
  positionSizeValue: number,
  positionSizeMode: 'percent' | 'dollar' = 'percent',
): number {
  if (!Number.isFinite(positionSizeValue)) {
    return 0;
  }
  if (positionSizeMode === 'dollar') {
    return Math.max(0, positionSizeValue);
  }
  const sizingCapital = Number.isFinite(totalValue) && totalValue > 0
    ? totalValue
    : initialCapital;
  if (!Number.isFinite(sizingCapital) || sizingCapital <= 0) {
    return 0;
  }
  return sizingCapital * Math.max(0, positionSizeValue) / 100;
}

function processLocalSignal(session: LocalSimTradingSession, signal: OrderBookSignal) {
  if (!signal.signal_generated || signal.signal === 'hold') {
    return;
  }

  const portfolio = session.portfolio;
  const existingPosition = portfolio.positions[signal.symbol];
  const positionSizeMode = session.parameters.position_size_mode === 'dollar' ? 'dollar' : 'percent';
  const positionSizeValue = Number(
    positionSizeMode === 'dollar'
      ? session.parameters.position_size_value ?? 0
      : session.parameters.position_size_percent ?? session.parameters.position_size_value ?? 1,
  );
  const maxPositions = Math.max(1, Number(session.parameters.max_positions ?? session.parameters.max_positions_per_session ?? 100));
  const holdTicks = Math.max(3, Number(session.parameters.position_update_interval ?? 5) * 2);
  // The configured value is the allocation ceiling: exact dollars in dollar
  // mode, or a percentage of current total value in percent mode.
  const allocatedUsd = calculateLocalAllocatedUsd(
    portfolio.total_value,
    portfolio.initial_capital,
    positionSizeValue,
    positionSizeMode,
  );
  if (allocatedUsd <= 0 || signal.price <= 0) {
    return;
  }
  const quantity = allocatedUsd / signal.price;
  const feeRate = 0.0008;
  const signalSide = signal.signal;
  const winProbability = localSignalWinProbability(signal);
  const expectedReturn = signal.ml_analysis?.expected_return ?? ((signal.signal_strength - 0.5) * 0.05);
  const modelConfidence = signal.ml_analysis?.confidence ?? signal.signal_strength;

  const openTrade = () => {
    if (Object.keys(portfolio.positions).length >= maxPositions) {
      return;
    }

    // Cash-sufficiency gate mirroring the backend: reject, never auto-scale.
    const entryFee = signal.price * quantity * feeRate;
    const requiredCash = signalSide === 'buy' ? allocatedUsd + entryFee : allocatedUsd;
    if (portfolio.cash_balance < requiredCash) {
      return;
    }

    portfolio.positions[signal.symbol] = {
      symbol: signal.symbol,
      side: signalSide as 'buy' | 'sell',
      quantity,
      entry_price: signal.price,
      entry_notional: allocatedUsd,
      current_price: signal.price,
      unrealized_pnl: 0,
      pnl_percentage: 0,
      entry_time: signal.timestamp,
      status: 'open',
      age_ticks: 0,
      entry_win_probability: winProbability,
      entry_expected_return: expectedReturn,
      entry_model_confidence: modelConfidence,
    };

    const fee = signal.price * quantity * feeRate;
    portfolio.total_fees += fee;
    portfolio.cash_balance += signalSide === 'buy' ? -(allocatedUsd + fee) : (allocatedUsd - fee);
    appendLocalTrade(session, {
      id: localTradeId(signal.symbol, session.tick, portfolio.trades.length + 1),
      trade_id: localTradeId(signal.symbol, session.tick, portfolio.trades.length + 1),
      symbol: signal.symbol,
      side: signalSide as 'buy' | 'sell',
      quantity,
      price: signal.price,
      pnl: 0,
      timestamp: signal.timestamp,
      fees: fee,
      win_probability: winProbability,
      expected_return: expectedReturn,
      model_confidence: modelConfidence,
    });
  };

  if (!existingPosition) {
    openTrade();
    return;
  }

  existingPosition.current_price = signal.price;
  existingPosition.age_ticks += 1;
  const oppositeSignal = existingPosition.side !== signalSide;
  const agedOut = existingPosition.age_ticks >= holdTicks;

  if (!oppositeSignal && !agedOut) {
    updateLocalPortfolioMarkToMarket(session, { [signal.symbol]: signal.price });
    return;
  }

  const isLong = existingPosition.side === 'buy';
  const exitPrice = signal.price;
  const grossPnl = isLong
    ? (exitPrice - existingPosition.entry_price) * existingPosition.quantity
    : (existingPosition.entry_price - exitPrice) * existingPosition.quantity;
  const exitFee = exitPrice * existingPosition.quantity * feeRate;
  portfolio.realized_pnl += grossPnl;
  portfolio.total_fees += exitFee;
  portfolio.cash_balance += isLong
    ? exitPrice * existingPosition.quantity - exitFee
    : -(exitPrice * existingPosition.quantity + exitFee);
  delete portfolio.positions[signal.symbol];

  appendLocalTrade(session, {
    id: localTradeId(signal.symbol, session.tick, portfolio.trades.length + 1),
    trade_id: localTradeId(signal.symbol, session.tick, portfolio.trades.length + 1),
    symbol: signal.symbol,
    side: existingPosition.side === 'buy' ? 'sell' : 'buy',
    quantity: existingPosition.quantity,
    price: exitPrice,
    pnl: grossPnl,
    timestamp: signal.timestamp,
    fees: exitFee,
    // Prediction-time values from entry, never outcome-derived hindsight.
    win_probability: existingPosition.entry_win_probability,
    expected_return: existingPosition.entry_expected_return,
    model_confidence: existingPosition.entry_model_confidence,
  });

  if (signalSide && Object.keys(portfolio.positions).length < maxPositions) {
    openTrade();
  }
}

function refreshLocalTradingSession(session: LocalSimTradingSession, signals: OrderBookSignal[]) {
  const priceMap: Record<string, number> = {};
  signals.forEach((signal) => {
    priceMap[signal.symbol] = signal.price;
  });
  updateLocalPortfolioMarkToMarket(session, priceMap);
  signals.forEach((signal) => processLocalSignal(session, signal));
  updateLocalPortfolioMarkToMarket(session, priceMap);
}

function buildSyntheticOrderBookSignals(session: LocalSimTradingSession, page = 1, perPage = 10) {
  session.tick += 1;
  session.updatedAt = new Date().toISOString();

  const signals: OrderBookSignal[] = session.symbols.map((symbol, index) => {
    const phase = session.tick / 2 + index * 0.85;
    const wave = Math.sin(phase);
    const isBuy = wave >= 0;
    const signalType: OrderBookSignal['signal'] = isBuy ? 'buy' : 'sell';
    const signalStrength = Number((0.58 + (Math.abs(wave) * 0.35)).toFixed(3));
    const price = Number((basePriceForSymbol(symbol) * (1 + Math.sin(session.tick / 6 + index) * 0.003)).toFixed(2));
    const spread = Number((0.01 + index * 0.005 + Math.abs(Math.cos(phase)) * 0.01).toFixed(4));
    const volume = Math.round((1000 + index * 200) * (1 + Math.abs(Math.sin(session.tick / 3 + index)) * 0.5));
    const winProbability = Number((0.5 + (signalStrength - 0.5) * 0.45 + (isBuy ? 0.03 : -0.03)).toFixed(3));

    return {
      symbol,
      timestamp: new Date(Date.now() - index * 30_000).toISOString(),
      price,
      signal: signalType,
      signal_generated: true,
      signal_strength: signalStrength,
      signal_type: session.strategy,
      signal_reason: syntheticSignalReason(session.strategy),
      data_status: 'sufficient',
      spread,
      volume,
      criteria_analysis: {
        bid_ask_squeeze: {
          enabled: true,
          meets_criteria: spread < 0.08,
          delta_to_threshold: Number((0.08 - spread).toFixed(4)),
          threshold_spread: 0.08,
          analysis: 'Synthetic order book spread check',
        },
        volume_imbalance_buy: {
          enabled: true,
          meets_criteria: isBuy,
          delta_to_threshold: isBuy ? 0.18 : -0.18,
          threshold: 0.3,
          analysis: 'Synthetic volume imbalance check',
        },
      },
      ml_analysis: {
        ml_enabled: true,
        win_probability: winProbability,
        expected_return: Number(((signalStrength - 0.5) * 0.12).toFixed(4)),
        confidence: Number((0.55 + signalStrength / 3).toFixed(3)),
        model_version: session.strategy === 'ml_enhanced_orderbook' ? 'local-dev-fallback' : 'local-orderbook-fallback',
        features_used: ['order_book_imbalance', 'spread', 'volume'],
        prediction_timestamp: new Date().toISOString(),
        analytics: {
          synthetic: true,
        },
      },
      strength_composition: {
        order_book_imbalance: { value: Number((Math.abs(wave) * 100).toFixed(2)), importance_percent: 42 },
        spread: { value: Number((100 - spread * 1000).toFixed(2)), importance_percent: 28 },
        volume: { value: volume, importance_percent: 30 },
      },
      buy_volume: isBuy ? Math.round(volume * 0.62) : Math.round(volume * 0.38),
      sell_volume: isBuy ? Math.round(volume * 0.38) : Math.round(volume * 0.62),
      imbalance_ratio: Number((isBuy ? 0.35 : -0.35).toFixed(3)),
      prediction: isBuy ? 'BUY' : 'SELL',
    } as OrderBookSignal;
  });

  const orderedSignals = [...signals].sort(localSignalComparator);
  refreshLocalTradingSession(session, orderedSignals);

  const totalAnalyzed = orderedSignals.length;
  const activeSignals = orderedSignals.filter((signal) => signal.signal_generated).length;
  const averageStrength = orderedSignals.reduce((sum, signal) => sum + signal.signal_strength, 0) / Math.max(orderedSignals.length, 1);
  const startIndex = Math.max(0, (page - 1) * perPage);
  const paginatedSignals = orderedSignals.slice(startIndex, startIndex + perPage);

  return {
    signals: paginatedSignals,
    pagination: {
      page,
      limit: perPage,
      total: orderedSignals.length,
      total_pages: Math.max(1, Math.ceil(orderedSignals.length / perPage)),
      has_next: startIndex + perPage < orderedSignals.length,
      has_prev: page > 1,
    },
    total_analyzed: totalAnalyzed,
    active_signals: activeSignals,
    last_updated: session.updatedAt,
    average_strength: Number(averageStrength.toFixed(3)),
  };
}

function buildLocalSimulatedTradingStatus() {
  if (!localSimTradingSession?.active) {
    return {
      is_trading: false,
      is_active: false,
      status: 'inactive',
      session_id: 'local-simulated-trading',
      strategy_type: null,
      symbols: [],
      started_at: null,
      updated_at: null,
      mode: 'simulated',
      portfolio: {
        initial_capital: 0,
        cash_balance: 0,
        total_value: 0,
        total_positions_value: 0,
        unrealized_pnl: 0,
        realized_pnl: 0,
        net_pnl: 0,
        total_fees: 0,
        positions: [],
        recent_trades: [],
        trades: [],
      },
      stats: {
        total_trades: 0,
        open_positions: 0,
        closed_positions: 0,
        realized_pnl: 0,
        unrealized_pnl: 0,
        total_fees: 0,
        net_pnl: 0,
      },
    };
  }

  const portfolio = localSimTradingSession.portfolio;
  return {
    is_trading: true,
    is_active: true,
    status: 'active',
    session_id: 'local-simulated-trading',
    strategy_type: localSimTradingSession.strategy,
    symbols: localSimTradingSession.symbols,
    started_at: localSimTradingSession.startedAt,
    updated_at: localSimTradingSession.updatedAt,
    mode: 'simulated',
    portfolio: {
      ...portfolio,
      positions: Object.values(portfolio.positions),
      recent_trades: [...portfolio.recent_trades],
      trades: [...portfolio.trades],
    },
    stats: {
      total_trades: portfolio.trades.length,
      open_positions: Object.keys(portfolio.positions).length,
      closed_positions: Math.max(0, portfolio.trades.length - Object.keys(portfolio.positions).length),
      realized_pnl: portfolio.realized_pnl,
      unrealized_pnl: portfolio.unrealized_pnl,
      total_fees: portfolio.total_fees,
      net_pnl: portfolio.net_pnl,
    },
  };
}

// Exported for tests: the canonical start-trading payload contract shared with
// SimulatedTradingService::startSession.
export function buildStartTradingPayload(
  strategy: string,
  symbols: string[],
  parameters: Record<string, any>,
  config: {
    position_size_percent?: number;
    max_positions?: number;
    position_update_interval?: number;
  }
) {
  const positionSizeFraction =
    typeof config.position_size_percent === 'number'
      ? config.position_size_percent / 100
      : undefined;
  const initialPortfolioSize = parameters.initial_portfolio_size ?? parameters.capital ?? 10000.0;

  return {
    symbols,
    strategy,
    strategy_type: strategy,
    // Canonical contract: the backend session reads `parameters` (including
    // initial_portfolio_size, position sizing mode, per-strategy tuning, and
    // the ML gate settings). The legacy aliases below are kept for older
    // backend builds.
    parameters: {
      ...parameters,
      initial_portfolio_size: initialPortfolioSize,
    } as Record<string, any>,
    strategy_params: parameters,
    initial_balance: initialPortfolioSize,
    capital: initialPortfolioSize,
    initial_portfolio_size: initialPortfolioSize,
    max_positions: config.max_positions,
    position_size_percent: config.position_size_percent,
    position_size: positionSizeFraction,
    position_update_interval: config.position_update_interval || 5,
    immediate_start: true,
    batch_size: 3,
    order_prioritization: parameters.order_prioritization,
    confidence_threshold: parameters.confidence_threshold,
    fallback_to_baseline: parameters.fallback_to_baseline,
    stop_loss: parameters.stop_loss,
    take_profit: parameters.take_profit,
  };
}

class ApiClient {
  private async request<T>(
    endpoint: string,
    options?: RequestInit
  ): Promise<ApiResponse<T>> {
    try {
      const url = `${API_BASE_URL}${endpoint}`;
      const response = await fetch(url, {
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers,
        },
        ...options,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      // Wrap the backend response in the expected ApiResponse format
      return {
        status: 'success' as const,
        data: data,
        timestamp: new Date().toISOString(),
      };
    } catch (error) {
      console.error(`API request failed for ${endpoint}:`, error);
      return {
        status: 'error' as const,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString(),
      };
    }
  }

  async getTradingStats(): Promise<ApiResponse<TradingStats>> {
    return this.request<TradingStats>('/api/trades/stats');
  }

  async getPositions(params?: PaginationParams): Promise<PaginatedResponse<Position>> {
    const queryParams = new URLSearchParams();
    if (params?.page) queryParams.append('page', params.page.toString());
    if (params?.limit) queryParams.append('limit', params.limit.toString());
    if (params?.sort_by) queryParams.append('sort_by', params.sort_by);
    if (params?.sort_order) queryParams.append('sort_order', params.sort_order);

    const query = queryParams.toString();
    const endpoint = `/api/trading/live/positions${query ? `?${query}` : ''}`;

    return this.request<Position[]>('/api/trading/live/positions')
      .then(response => {
        // Mock pagination for now - in real implementation this would come from backend
        const positions = Array.isArray(response.data) ? response.data : [];
        const page = params?.page || 1;
        const limit = params?.limit || 50;
        const total = positions.length;
        const totalPages = Math.ceil(total / limit);
        const startIndex = (page - 1) * limit;
        const endIndex = startIndex + limit;
        const paginatedData = positions.slice(startIndex, endIndex);

        return {
          ...response,
          data: paginatedData,
          pagination: {
            page,
            limit,
            total,
            total_pages: totalPages,
            has_next: page < totalPages,
            has_prev: page > 1,
          },
        } as PaginatedResponse<Position>;
      });
  }

  async getTradingHistory(params?: PaginationParams): Promise<PaginatedResponse<any>> {
    const queryParams = new URLSearchParams();
    if (params?.page) queryParams.append('page', params.page.toString());
    if (params?.limit) queryParams.append('limit', params.limit.toString());
    if (params?.sort_by) queryParams.append('sort_by', params.sort_by);
    if (params?.sort_order) queryParams.append('sort_order', params.sort_order);

    const query = queryParams.toString();
    return this.request<any[]>(`/api/trades/paginated${query ? `?${query}` : ''}`)
      .then(response => {
        const trades = Array.isArray(response.data) ? response.data : [];
        const page = params?.page || 1;
        const limit = params?.limit || 50;
        const total = trades.length;
        const totalPages = Math.ceil(total / limit);
        const startIndex = (page - 1) * limit;
        const endIndex = startIndex + limit;
        const paginatedData = trades.slice(startIndex, endIndex);

        return {
          ...response,
          data: paginatedData,
          pagination: {
            page,
            limit,
            total,
            total_pages: totalPages,
            has_next: page < totalPages,
            has_prev: page > 1,
          },
        } as PaginatedResponse<any>;
      });
  }

  // Trading operations
  async startTrading(
    mode: 'live' | 'simulated',
    strategy: string,
    symbols: string[],
    parameters: Record<string, any>,
    config: {
      position_size_percent?: number;
      max_positions?: number;
      position_update_interval?: number;
    }
  ): Promise<ApiResponse<{ is_active: boolean; message: string }>> {
    const basePayload = buildStartTradingPayload(strategy, symbols, parameters, config);

    if (mode === 'simulated' && FORCE_LOCAL_SIM_TRADING) {
      setLocalSimTradingSession(strategy, symbols, parameters);
      return {
        status: 'success',
        data: {
          is_active: true,
          message: 'Simulated trading started in local simulation mode.',
        },
        timestamp: new Date().toISOString(),
      };
    }

    const attempts = mode === 'live'
      ? [
          { url: `${API_BASE_URL}/api/trading/live/start`, payload: basePayload },
        ]
      : [
          { url: `${API_BASE_URL}/api/trading/simulated/start`, payload: basePayload },
          { url: `${API_BASE_URL}/api/simulated-trading/start`, payload: basePayload },
        ];

    let lastError: ApiResponse<{ is_active: boolean; message: string }> = {
      status: 'error',
      error: 'Unable to start trading',
      timestamp: new Date().toISOString(),
    };

    for (const attempt of attempts) {
      try {
        const response = await fetch(attempt.url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(attempt.payload),
        });

        if (!response.ok) {
          const contentType = response.headers.get('content-type') || '';
          let responseError = '';
          if (contentType.includes('application/json')) {
            const errorData = await response.json().catch(() => ({} as any));
            responseError = errorData.error || errorData.message || '';
          } else {
            responseError = await response.text().catch(() => '');
          }

          lastError = {
            status: 'error',
            error: responseError || `HTTP ${response.status} from ${new URL(attempt.url, window.location.origin).pathname}`,
            timestamp: new Date().toISOString(),
          };
          continue;
        }

        const data = await response.json();
        return data;
      } catch (error) {
        lastError = {
          status: 'error',
          error: error instanceof Error ? error.message : 'Unknown error',
          timestamp: new Date().toISOString(),
        };
      }
    }

    if (mode === 'simulated') {
      setLocalSimTradingSession(strategy, symbols, parameters);
      return {
        status: 'success',
        data: {
          is_active: true,
          message: 'Simulated trading started in local fallback mode because backend trading endpoints are unavailable.',
        },
        timestamp: new Date().toISOString(),
      };
    }

    return lastError;
  }

  async stopTrading(mode: 'live' | 'simulated' = 'simulated'): Promise<ApiResponse<{ message: string }>> {
    if (localSimTradingSession?.active) {
      clearLocalSimTradingSession();
      return {
        status: 'success',
        data: { message: 'Simulated trading stopped.' },
        timestamp: new Date().toISOString(),
      };
    }

    return fetch(`${API_BASE_URL}/api/trading/${mode === 'live' ? 'live' : 'simulated'}/stop`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    }).then(async (response) => {
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        return {
          status: 'error',
          error: errorData.error || `HTTP ${response.status}`,
          timestamp: new Date().toISOString(),
        };
      }
      return response.json();
    }).catch(error => ({
      status: 'error',
      error: error.message,
      timestamp: new Date().toISOString(),
    }));
  }

  async closePosition(symbol: string): Promise<ApiResponse<{ message: string; trade_id?: string }>> {
    return fetch(`${API_BASE_URL}/api/trading/live/close-position`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ symbol }),
    }).then(async (response) => {
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        return {
          status: 'error',
          error: errorData.error || `HTTP ${response.status}`,
          timestamp: new Date().toISOString(),
        };
      }
      return response.json();
    }).catch(error => ({
      status: 'error',
      error: error.message,
      timestamp: new Date().toISOString(),
    }));
  }

  // Simulated Trading Status
  async getSimulatedTradingStatus(): Promise<ApiResponse<any>> {
    if (FORCE_LOCAL_SIM_TRADING || localSimTradingSession?.active) {
      return {
        status: 'success',
        data: buildLocalSimulatedTradingStatus(),
        timestamp: new Date().toISOString(),
      };
    }

    return this.request('/api/simulated-trading/status').catch((error) => ({
      status: 'error',
      error: error instanceof Error ? error.message : 'Failed to fetch simulated trading status',
      timestamp: new Date().toISOString(),
    }));
  }

  async getLivePortfolioStatus(): Promise<ApiResponse<any>> {
    if (FORCE_LOCAL_SIM_TRADING || localSimTradingSession?.active) {
      const portfolio = localSimTradingSession?.portfolio ?? {
        initial_capital: 0,
        cash_balance: 0,
        total_value: 0,
        total_positions_value: 0,
        unrealized_pnl: 0,
        realized_pnl: 0,
        net_pnl: 0,
        total_fees: 0,
        positions: {},
        trades: [],
        recent_trades: [],
      };
      return {
        status: 'success',
        data: {
          is_active: true,
          positions: Object.values(portfolio.positions),
          total_value: portfolio.total_value,
          cash: portfolio.cash_balance,
          unrealized_pnl: portfolio.unrealized_pnl,
          realized_pnl: portfolio.realized_pnl,
          net_pnl: portfolio.net_pnl,
          total_fees: portfolio.total_fees,
          trades: [...portfolio.trades],
          recent_trades: [...portfolio.recent_trades],
        },
        timestamp: new Date().toISOString(),
      };
    }

    return this.request('/api/live-portfolio/status').catch(() => ({
      status: 'success',
      data: {
        is_active: false,
        positions: [],
        total_value: 0,
        cash: 0,
        unrealized_pnl: 0,
        realized_pnl: 0,
      },
      timestamp: new Date().toISOString(),
    }));
  }

  // Order Book Signals
  async getOrderBookSignals(
    symbols?: string[],
    params?: { page?: number; per_page?: number }
  ): Promise<ApiResponse<{
    signals: OrderBookSignal[];
    pagination?: any;
    total_analyzed?: number;
    active_signals?: number;
    last_updated?: string;
    average_strength?: number;
  }>> {
    if (FORCE_LOCAL_SIM_TRADING || localSimTradingSession?.active) {
      const page = params?.page || 1;
      const perPage = params?.per_page || 10;
      const signals = buildSyntheticOrderBookSignals(localSimTradingSession!, page, perPage);
      return {
        status: 'success',
        data: signals,
        timestamp: new Date().toISOString(),
      };
    }

    const queryParams = new URLSearchParams();
    const requestSymbols = symbols;
    if (requestSymbols && requestSymbols.length > 0) {
      queryParams.append('symbols', requestSymbols.join(','));
    }
    if (params?.page) queryParams.append('page', params.page.toString());
    if (params?.per_page) queryParams.append('per_page', params.per_page.toString());

    const query = queryParams.toString();

    try {
      const response = await this.request<{ signals: OrderBookSignal[]; pagination?: any; total_analyzed?: number; active_signals?: number; last_updated?: string; average_strength?: number; }>(`/api/orderbook/live-signals${query ? `?${query}` : ''}`);
      return response;
    } catch {
      return {
        status: 'success',
        data: {
          signals: [],
          pagination: {
            page: params?.page || 1,
            limit: params?.per_page || 10,
            total: 0,
            total_pages: 0,
            has_next: false,
            has_prev: false,
          },
          total_analyzed: 0,
          active_signals: 0,
          last_updated: new Date().toISOString(),
          average_strength: 0,
        },
        timestamp: new Date().toISOString(),
      } as ApiResponse<{ signals: OrderBookSignal[]; pagination?: any; total_analyzed?: number; active_signals?: number; last_updated?: string; average_strength?: number; }>;
    }
  }

  // Backtesting
  async runBacktest(config: {
    strategy: string;
    symbols: string[];
    parameters: Record<string, any>;
    start_date: string;
    end_date: string;
  }): Promise<ApiResponse<any>> {
    return fetch(`${API_BASE_URL}/api/backtests/run`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(config),
    }).then(async (response) => {
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        return {
          status: 'error',
          error: errorData.error || `HTTP ${response.status}`,
          timestamp: new Date().toISOString(),
        };
      }
      return response.json();
    }).catch(error => ({
      status: 'error',
      error: error.message,
      timestamp: new Date().toISOString(),
    }));
  }

  // Products/Symbols
  async getProducts(): Promise<ApiResponse<{ categories: Record<string, string[]> }>> {
    return this.request('/api/products');
  }

  // ML Analytics
  async getMLDashboard(): Promise<ApiResponse<import('@/types/trading').MLDashboardData>> {
    try {
      const dashboardResponse = await fetch(`${API_BASE_URL}/api/ml/dashboard`, {
        headers: {
          'Content-Type': 'application/json',
        },
      });

      // Preferred endpoint exists
      if (dashboardResponse.ok) {
        const data = await dashboardResponse.json();
        return {
          status: 'success',
          data,
          timestamp: new Date().toISOString(),
        };
      }

      // Backward-compatible fallback for backends without /api/ml/dashboard
      if (dashboardResponse.status === 404) {
        const [statusResp, performanceResp] = await Promise.all([
          fetch(`${API_BASE_URL}/api/ml/status`, {
            headers: { 'Content-Type': 'application/json' },
          }),
          fetch(`${API_BASE_URL}/api/ml/performance`, {
            headers: { 'Content-Type': 'application/json' },
          }),
        ]);

        if (!statusResp.ok || !performanceResp.ok) {
          throw new Error(`HTTP error! status: ${!statusResp.ok ? statusResp.status : performanceResp.status}`);
        }

        const statusData = await statusResp.json();
        const performanceData = await performanceResp.json();

        const trainingStatus = typeof statusData?.status === 'string' ? statusData.status : '';
        const isTraining = trainingStatus === 'training';
        const isTrained = trainingStatus === 'completed';
        const modelStatus: import('@/types/trading').MLModelStatus = {
          is_training: isTraining,
          is_trained: isTrained,
          ...(trainingStatus === 'failed' ? { error: 'Model training failed' } : {}),
        };

        return {
          status: 'success',
          data: {
            status: modelStatus,
            performance: performanceData || {},
            feature_importance: performanceData?.feature_importance || {},
          },
          timestamp: new Date().toISOString(),
        };
      }

      throw new Error(`HTTP error! status: ${dashboardResponse.status}`);
    } catch (error) {
      console.error('API request failed for /api/ml/dashboard:', error);
      return {
        status: 'error',
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString(),
      };
    }
  }

  async trainMLModel(options?: {
    batchTraining?: boolean;
    autoSetActive?: boolean;
    modelType?: 'random_forest' | 'gradient_boosting' | 'transformer';
    modelName?: string;
  }): Promise<ApiResponse<import('@/types/trading').MLTrainingResponse>> {
    const queryParams = new URLSearchParams();
    if (options?.batchTraining !== undefined) {
      queryParams.append('batch_training', options.batchTraining.toString());
    }
    if (options?.autoSetActive !== undefined) {
      queryParams.append('auto_set_active', options.autoSetActive.toString());
    }
    const query = queryParams.toString();

    return fetch(`${API_BASE_URL}/api/ml/train${query ? `?${query}` : ''}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        ...(options?.modelType ? { model_type: options.modelType } : {}),
        ...(options?.modelName ? { model_name: options.modelName } : {}),
      }),
    }).then(async (response) => {
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        return {
          status: 'error',
          error: errorData.error || `HTTP ${response.status}`,
          timestamp: new Date().toISOString(),
        };
      }
      return response.json();
    }).catch(error => ({
      status: 'error',
      error: error.message,
      timestamp: new Date().toISOString(),
    }));
  }

  async getMLStatus(): Promise<ApiResponse<any>> {
    return this.request('/api/ml/status');
  }


  async updateMLModel(): Promise<ApiResponse<import('@/types/trading').MLTrainingResponse>> {
    return fetch(`${API_BASE_URL}/api/ml/update`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    }).then(async (response) => {
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        return {
          status: 'error',
          error: errorData.error || `HTTP ${response.status}`,
          timestamp: new Date().toISOString(),
        };
      }
      return response.json();
    }).catch(error => ({
      status: 'error',
      error: error.message,
      timestamp: new Date().toISOString(),
    }));
  }

  async rollbackMLModel(): Promise<ApiResponse<import('@/types/trading').MLTrainingResponse>> {
    return fetch(`${API_BASE_URL}/api/ml/rollback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    }).then(async (response) => {
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        return {
          status: 'error',
          error: errorData.error || `HTTP ${response.status}`,
          timestamp: new Date().toISOString(),
        };
      }
      return response.json();
    }).catch(error => ({
      status: 'error',
      error: error.message,
      timestamp: new Date().toISOString(),
    }));
  }

  async getPnlTrades(sortBy: string = 'pnl'): Promise<ApiResponse<any>> {
    return this.request(`/api/ml/pnl-trades?sort_by=${sortBy}`);
  }

  async getMLModels(): Promise<ApiResponse<any>> {
    return this.request('/api/ml/models');
  }

  async getAvailableModels(): Promise<ApiResponse<any>> {
    return this.request('/api/ml/models');
  }

  async setActiveModel(modelName: string): Promise<ApiResponse<any>> {
    return this.request(`/api/ml/models/set_active?model_name=${encodeURIComponent(modelName)}`, {
      method: 'POST',
    });
  }

  async deleteModel(modelName: string): Promise<ApiResponse<any>> {
    return this.request(`/api/ml/models/${modelName}`, {
      method: 'DELETE',
    });
  }

  async deleteAllModels(): Promise<ApiResponse<any>> {
    return this.request('/api/ml/models', {
      method: 'DELETE',
    });
  }

  async resetDatabases(): Promise<ApiResponse<any>> {
    return this.request('/api/ml/databases', {
      method: 'DELETE',
    });
  }

  async getPredictionComparison(modelIds: string[], features: any): Promise<ApiResponse<any>> {
    return this.request('/api/ml/prediction-comparison', {
      method: 'POST',
      body: JSON.stringify({
        model_ids: modelIds,
        features: features
      }),
    });
  }

  async getMLConfig(): Promise<ApiResponse<any>> {
    return this.request('/api/ml/config');
  }

  async updateMLConfig(newConfig: any): Promise<ApiResponse<any>> {
    return this.request('/api/ml/config', {
      method: 'POST',
      body: JSON.stringify(newConfig),
    });
  }

  async updateStrategyParameters(parameters: Record<string, any>): Promise<ApiResponse<any>> {
    return this.request('/api/trading/simulated/update-strategy-params', {
      method: 'POST',
      body: JSON.stringify({ parameters }),
    });
  }

  async logMessage(message: string): Promise<ApiResponse<any>> {
    return this.request('/api/log', {
      method: 'POST',
      body: JSON.stringify({ message }),
    });
  }
}

export const apiClient = new ApiClient();

// Query keys for React Query
export const queryKeys = {
  tradingStats: ['trading', 'stats'] as const,
  positions: (params?: PaginationParams) => ['trading', 'positions', params] as const,
  tradingHistory: (params?: PaginationParams) => ['trading', 'history', params] as const,
} as const;
