import type { TradingStats, Trade } from '@/types/trading';

export type TradeLike = Partial<Trade> & {
  id?: string;
  trade_id?: string;
  pnl?: number;
  fees?: number;
  quantity?: number;
  price?: number;
  timestamp?: string;
  side?: string;
};

type PositionLike = Record<string, unknown>;

type RawSimulatedTradingSnapshot = {
  portfolio?: Record<string, unknown>;
  stats?: Partial<TradingStats>;
  trades?: unknown;
  recent_trades?: unknown;
  positions?: unknown;
  cash_balance?: unknown;
  current_capital?: unknown;
  available_balance_usd?: unknown;
  unrealized_pnl?: unknown;
  total_unrealized_pnl?: unknown;
  realized_pnl?: unknown;
  total_fees?: unknown;
  total_positions_value?: unknown;
  total_value?: unknown;
  open_positions_count?: unknown;
  active_positions?: unknown;
  open_positions?: unknown;
  net_pnl?: unknown;
  total_trades?: unknown;
  winning_trades?: unknown;
  losing_trades?: unknown;
  avg_win?: unknown;
  avg_loss?: unknown;
  best_trade?: unknown;
  worst_trade?: unknown;
  profit_factor?: unknown;
  sharpe_ratio?: unknown;
  max_drawdown?: unknown;
  total_volume?: unknown;
  avg_trade_size?: unknown;
  trades_today?: unknown;
  last_trade_time?: unknown;
  [key: string]: unknown;
};

export interface NormalizedSimulatedTradingSnapshot {
  portfolio: Record<string, unknown>;
  stats: TradingStats;
  trades: TradeLike[];
  recentTrades: TradeLike[];
  openPositions: PositionLike[];
  cashBalance: number;
  totalValue: number;
  totalPositionsValue: number;
  activePositions: number;
  unrealizedPnl: number;
  realizedPnl: number;
  totalFees: number;
  netPnl: number;
}

function toArray(value: unknown): unknown[] {
  if (Array.isArray(value)) {
    return value;
  }

  if (value && typeof value === 'object') {
    return Object.values(value as Record<string, unknown>);
  }

  return [];
}

function toNumber(value: unknown, fallback = 0): number {
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function tradeKey(trade: TradeLike): string {
  return trade.id || trade.trade_id || `${trade.symbol ?? 'trade'}-${trade.timestamp ?? 'unknown'}-${trade.side ?? 'unknown'}`;
}

function mergeRecentTrades(primary: unknown, secondary: unknown): TradeLike[] {
  const merged = new Map<string, TradeLike>();

  for (const trade of [...toArray(primary), ...toArray(secondary)]) {
    if (!trade || typeof trade !== 'object') {
      continue;
    }
    const typedTrade = trade as TradeLike;
    merged.set(tradeKey(typedTrade), typedTrade);
  }

  return Array.from(merged.values())
    .filter((trade) => Boolean(trade && trade.timestamp))
    .sort((left, right) => new Date(String(right.timestamp)).getTime() - new Date(String(left.timestamp)).getTime())
    .slice(0, 10);
}

export function deriveStats(trades: TradeLike[], knownTotalFees?: number): TradingStats {
  const today = new Date().toISOString().slice(0, 10);
  const pnlValues: number[] = [];
  const positivePnls: number[] = [];
  const negativePnls: number[] = [];
  let totalPnl = 0;
  let tradeFees = 0;
  let totalVolume = 0;
  let winningTrades = 0;
  let losingTrades = 0;
  let bestTrade = Number.NEGATIVE_INFINITY;
  let worstTrade = Number.POSITIVE_INFINITY;
  let cumulativePnl = 0;
  let peakPnl = 0;
  let maxDrawdown = 0;
  let tradesToday = 0;
  let lastTradeTime = '';
  let lastTradeTimeMs = Number.NEGATIVE_INFINITY;

  for (const trade of trades) {
    const pnl = toNumber(trade.pnl, 0);
    const fees = toNumber(trade.fees, 0);
    const quantity = toNumber(trade.quantity, 0);
    const price = toNumber(trade.price, 0);
    const volume = quantity * price;

    totalPnl += pnl;
    tradeFees += fees;
    totalVolume += volume;
    pnlValues.push(pnl);
    if (trade.timestamp) {
      const timestampMs = new Date(trade.timestamp).getTime();
      if (Number.isFinite(timestampMs) && timestampMs >= lastTradeTimeMs) {
        lastTradeTimeMs = timestampMs;
        lastTradeTime = trade.timestamp;
      }
    }

    if (pnl > 0) {
      winningTrades += 1;
      positivePnls.push(pnl);
    } else if (pnl < 0) {
      losingTrades += 1;
      negativePnls.push(pnl);
    }

    bestTrade = Math.max(bestTrade, pnl);
    worstTrade = Math.min(worstTrade, pnl);

    cumulativePnl += pnl;
    peakPnl = Math.max(peakPnl, cumulativePnl);
    maxDrawdown = Math.max(maxDrawdown, peakPnl - cumulativePnl);

    if (trade.timestamp && trade.timestamp.slice(0, 10) === today) {
      tradesToday += 1;
    }
  }

  const totalTrades = trades.length;
  const avgWin = positivePnls.length > 0
    ? positivePnls.reduce((sum, value) => sum + value, 0) / positivePnls.length
    : 0;
  const avgLoss = negativePnls.length > 0
    ? negativePnls.reduce((sum, value) => sum + value, 0) / negativePnls.length
    : 0;
  const profitFactor = (() => {
    const grossProfit = positivePnls.reduce((sum, value) => sum + value, 0);
    const grossLoss = Math.abs(negativePnls.reduce((sum, value) => sum + value, 0));
    if (grossLoss === 0) {
      return grossProfit > 0 ? 999 : 0;
    }
    return grossProfit / grossLoss;
  })();
  const sharpeRatio = (() => {
    if (pnlValues.length === 0) {
      return 0;
    }
    const mean = pnlValues.reduce((sum, value) => sum + value, 0) / pnlValues.length;
    const variance = pnlValues.reduce((sum, value) => sum + ((value - mean) ** 2), 0) / pnlValues.length;
    const stdDev = Math.sqrt(variance);
    // Per-trade Sharpe (mean/std of trade PnL). No annualization factor: the
    // trade series is not a daily return series, so sqrt(252) would overstate it.
    return stdDev > 0 ? mean / stdDev : 0;
  })();

  // A provided portfolio-level fee total already includes per-trade fees, so it
  // must replace (not add to) the per-trade sum to avoid double counting.
  const totalFees = knownTotalFees !== undefined ? knownTotalFees : tradeFees;

  const stats: TradingStats = {
    total_pnl: totalPnl,
    total_fees: totalFees,
    net_pnl: totalPnl - totalFees,
    win_rate: (winningTrades + losingTrades) > 0 ? (winningTrades / (winningTrades + losingTrades)) * 100 : 0,
    total_trades: totalTrades,
    winning_trades: winningTrades,
    losing_trades: losingTrades,
    avg_win: avgWin,
    avg_loss: avgLoss,
    best_trade: Number.isFinite(bestTrade) ? bestTrade : 0,
    worst_trade: Number.isFinite(worstTrade) ? worstTrade : 0,
    profit_factor: profitFactor,
    sharpe_ratio: sharpeRatio,
    max_drawdown: maxDrawdown,
    total_volume: totalVolume,
    avg_trade_size: totalTrades > 0 ? totalVolume / totalTrades : 0,
    trades_today: tradesToday,
  };

  if (!lastTradeTime) {
    return stats;
  }

  return { ...stats, last_trade_time: lastTradeTime };
}

export function mergeStats(base: Partial<TradingStats> | undefined, fallback: TradingStats): TradingStats {
  const stats: TradingStats = {
    total_pnl: toNumber(base?.total_pnl, fallback.total_pnl),
    total_fees: toNumber(base?.total_fees, fallback.total_fees),
    net_pnl: toNumber(base?.net_pnl, fallback.net_pnl),
    win_rate: toNumber(base?.win_rate, fallback.win_rate),
    total_trades: Math.trunc(toNumber(base?.total_trades, fallback.total_trades)),
    winning_trades: Math.trunc(toNumber(base?.winning_trades, fallback.winning_trades)),
    losing_trades: Math.trunc(toNumber(base?.losing_trades, fallback.losing_trades)),
    avg_win: toNumber(base?.avg_win, fallback.avg_win),
    avg_loss: toNumber(base?.avg_loss, fallback.avg_loss),
    best_trade: toNumber(base?.best_trade, fallback.best_trade),
    worst_trade: toNumber(base?.worst_trade, fallback.worst_trade),
    profit_factor: toNumber(base?.profit_factor, fallback.profit_factor),
    sharpe_ratio: toNumber(base?.sharpe_ratio, fallback.sharpe_ratio),
    max_drawdown: toNumber(base?.max_drawdown, fallback.max_drawdown),
    total_volume: toNumber(base?.total_volume, fallback.total_volume),
    avg_trade_size: toNumber(base?.avg_trade_size, fallback.avg_trade_size),
    trades_today: Math.trunc(toNumber(base?.trades_today, fallback.trades_today)),
  };

  const lastTradeTime = base?.last_trade_time || fallback.last_trade_time;
  if (!lastTradeTime) {
    return stats;
  }

  return { ...stats, last_trade_time: lastTradeTime };
}

export function normalizeSimulatedTradingSnapshot(rawStats: RawSimulatedTradingSnapshot): NormalizedSimulatedTradingSnapshot {
  const portfolio = rawStats.portfolio ?? rawStats;
  const trades = toArray(portfolio.trades ?? rawStats.trades ?? portfolio.recent_trades ?? rawStats.recent_trades) as TradeLike[];
  const recentTrades = mergeRecentTrades(portfolio.recent_trades ?? rawStats.recent_trades, trades);
  const openPositions = toArray(portfolio.positions ?? rawStats.positions).filter(Boolean) as PositionLike[];

  const cashBalance = toNumber(
    portfolio.cash_balance ?? portfolio.current_capital ?? portfolio.available_balance_usd,
    0,
  );
  const unrealizedPnl = toNumber(portfolio.unrealized_pnl ?? rawStats.unrealized_pnl ?? rawStats.total_unrealized_pnl, 0);
  const realizedPnl = toNumber(portfolio.realized_pnl ?? rawStats.realized_pnl, 0);
  const rawTotalFees = portfolio.total_fees ?? rawStats.total_fees;
  const totalFees = toNumber(rawTotalFees, 0);
  // Signed market value (shorts negative), matching the backend convention so
  // the Total Value = Cash + Positions Value identity holds either way.
  const totalPositionsValue = toNumber(
    portfolio.total_positions_value,
    openPositions.reduce(
      (sum, pos) => {
        const notional = toNumber(pos.current_price ?? pos.price ?? pos.entry_price, 0) * toNumber(pos.quantity ?? pos.size, 0);
        return sum + (pos.side === 'sell' ? -Math.abs(notional) : Math.abs(notional));
      },
      0,
    ),
  );
  // Keep the identity Total Value = Cash + Positions Value so the tiles reconcile.
  const totalValue = toNumber(
    portfolio.total_value,
    cashBalance + totalPositionsValue,
  );
  const activePositions = Math.trunc(toNumber(
    portfolio.open_positions_count ?? portfolio.active_positions ?? rawStats.open_positions,
    openPositions.length,
  ));
  const netPnl = toNumber(portfolio.net_pnl ?? rawStats.net_pnl, realizedPnl + unrealizedPnl - totalFees);

  const derivedStats = deriveStats(trades, rawTotalFees !== undefined ? totalFees : undefined);
  const statsSource = rawStats.stats ?? (rawStats.total_trades !== undefined ? (rawStats as Partial<TradingStats>) : undefined);
  const stats = mergeStats(statsSource, derivedStats);

  return {
    portfolio,
    stats,
    trades,
    recentTrades,
    openPositions,
    cashBalance,
    totalValue,
    totalPositionsValue,
    activePositions,
    unrealizedPnl,
    realizedPnl,
    totalFees,
    netPnl,
  };
}
