/**
 * TradingStats Module
 * Handles trading statistics and performance metrics
 */
export class TradingStats {
    constructor(dashboard) {
        this.dashboard = dashboard;
        this.statsUpdateInterval = null;
    }

    async loadTradingStats() {
        try {
            const response = await fetch('/api/trades/stats');
            const data = await response.json();
            
            // Support multiple backend shapes:
            // 1) { status: 'success', stats: {...} }
            // 2) Direct stats object { total_trades, total_pnl, ... }
            // 3) Simulated status { portfolio: {...} }
            if (data && data.status === 'success' && data.stats) {
                this.updateTradingStats(data.stats);
                return;
            }

            if (data && (typeof data.total_trades !== 'undefined' || typeof data.total_pnl !== 'undefined')) {
                this.updateTradingStats(data);
                return;
            }

            // Fallback: compute from simulated trading portfolio if present
            if (data && data.portfolio) {
                const computed = this.computeStatsFromPortfolio(data.portfolio);
                this.updateTradingStats(computed);
                return;
            }

            console.error('Failed to load trading stats: unexpected response', data);
        } catch (error) {
            console.error('Error loading trading stats:', error);
        }
    }

    computeStatsFromPortfolio(portfolio) {
        const trades = portfolio.trades || [];
        const totalTrades = trades.length;
        const totalPnl = portfolio.total_pnl || 0;
        const totalFees = portfolio.total_fees || 0;
        const netPnl = totalPnl - totalFees;
        const winningTradesCount = trades.filter(t => (t.pnl || 0) > 0).length;
        const losingTradesCount = trades.filter(t => (t.pnl || 0) < 0).length;
        const winRate = totalTrades > 0 ? (winningTradesCount / totalTrades) * 100 : 0;
        const pnlValues = trades.map(t => t.pnl || 0);
        const bestTrade = pnlValues.length ? Math.max(...pnlValues) : 0;
        const worstTrade = pnlValues.length ? Math.min(...pnlValues) : 0;
        const avgWin = winningTradesCount > 0 ? trades.filter(t => (t.pnl || 0) > 0).reduce((s, t) => s + (t.pnl || 0), 0) / winningTradesCount : 0;
        const avgLoss = losingTradesCount > 0 ? trades.filter(t => (t.pnl || 0) < 0).reduce((s, t) => s + (t.pnl || 0), 0) / losingTradesCount : 0;
        const grossProfit = trades.filter(t => (t.pnl || 0) > 0).reduce((s, t) => s + (t.pnl || 0), 0);
        const grossLoss = Math.abs(trades.filter(t => (t.pnl || 0) < 0).reduce((s, t) => s + (t.pnl || 0), 0));
        const profitFactor = grossLoss > 0 ? grossProfit / grossLoss : (grossProfit > 0 ? Infinity : 0);
        const totalVolume = trades.reduce((sum, t) => sum + ((t.quantity || 0) * (t.price || 0)), 0);
        const avgTradeSize = totalTrades > 0 ? totalVolume / totalTrades : 0;

        return {
            total_pnl: totalPnl,
            total_fees: totalFees,
            net_pnl: netPnl,
            win_rate: winRate,
            total_trades: totalTrades,
            winning_trades: winningTradesCount,
            losing_trades: losingTradesCount,
            avg_win: avgWin,
            avg_loss: avgLoss,
            best_trade: bestTrade,
            worst_trade: worstTrade,
            profit_factor: profitFactor,
            sharpe_ratio: 0,
            max_drawdown: portfolio.max_drawdown || 0,
            total_volume: totalVolume,
            avg_trade_size: avgTradeSize,
            trades_today: 0,
            last_trade_time: trades[0]?.timestamp || null
        };
    }

    updateTradingStats(stats) {
        this.dashboard.tradingStats = {
            totalPnl: stats.total_pnl ?? 0,
            totalFees: stats.total_fees ?? 0,
            netPnl: (stats.net_pnl !== undefined ? stats.net_pnl : ((stats.total_pnl || 0) - (stats.total_fees || 0))),
            winRate: stats.win_rate ?? 0,
            totalTrades: stats.total_trades ?? 0,
            winningTrades: stats.winning_trades ?? 0,
            losingTrades: stats.losing_trades ?? 0,
            avgWin: stats.avg_win ?? 0,
            avgLoss: stats.avg_loss ?? 0,
            bestTrade: stats.best_trade ?? 0,
            worstTrade: stats.worst_trade ?? 0,
            profitFactor: stats.profit_factor ?? 0,
            sharpeRatio: stats.sharpe_ratio ?? 0,
            maxDrawdown: stats.max_drawdown ?? 0,
            totalVolume: stats.total_volume ?? 0,
            avgTradeSize: stats.avg_trade_size ?? 0,
            tradesToday: stats.trades_today ?? 0,
            lastTradeTime: stats.last_trade_time ?? null
        };
        
        this.updateTradingStatsUI();
    }

    updateTradingStatsUI() {
        // Update main stats
        this.updateElement('total-pnl', this.dashboard.tradingStats.netPnl.toFixed(2));
        this.updateElement('total-fees', this.dashboard.tradingStats.totalFees.toFixed(2));
        this.updateElement('win-rate', this.dashboard.tradingStats.winRate.toFixed(1) + '%');
        this.updateElement('total-trades', this.dashboard.tradingStats.totalTrades);
        this.updateElement('winning-trades', this.dashboard.tradingStats.winningTrades);
        this.updateElement('losing-trades', this.dashboard.tradingStats.losingTrades);

        // Performance Metrics
        this.updateElement('avg-win', this.dashboard.tradingStats.avgWin.toFixed(2));
        this.updateElement('avg-loss', this.dashboard.tradingStats.avgLoss.toFixed(2));
        this.updateElement('best-trade', this.dashboard.tradingStats.bestTrade.toFixed(2));
        this.updateElement('worst-trade', this.dashboard.tradingStats.worstTrade.toFixed(2));

        // Risk Metrics
        this.updateElement('profit-factor', this.dashboard.tradingStats.profitFactor.toFixed(2));
        this.updateElement('sharpe-ratio', this.dashboard.tradingStats.sharpeRatio.toFixed(2));
        this.updateElement('max-drawdown', this.dashboard.tradingStats.maxDrawdown.toFixed(2));

        // Trading Activity
        this.updateElement('total-volume', this.dashboard.tradingStats.totalVolume.toFixed(2));
        this.updateElement('avg-trade-size', this.dashboard.tradingStats.avgTradeSize.toFixed(2));

        // Performance Trends
        this.updateElement('trades-today', this.dashboard.tradingStats.tradesToday);

        // Last Trade Time
        if (this.dashboard.tradingStats.lastTradeTime) {
            const lastTradeDate = new Date(this.dashboard.tradingStats.lastTradeTime);
            this.updateElement('last-trade-time', lastTradeDate.toLocaleString());
        }

        // Update position value
        const positionValue = this.dashboard.liveTrading.positions.reduce((sum, pos) => {
            return sum + (pos.quantity * pos.current_price);
        }, 0);
        this.updateElement('position-value', positionValue.toFixed(2));

        // Update trades today
        this.updateElement('trades-today', this.dashboard.tradingStats.tradesToday);

        // Update PnL change (simplified)
        const pnlChange = this.dashboard.tradingStats.totalPnl > 0 ? '+' : '';
        this.updateElement('pnl-change', pnlChange + this.dashboard.tradingStats.totalPnl.toFixed(2));

        // Update win rate change (simplified)
        const winRateChange = this.dashboard.tradingStats.winRate > 50 ? '+' : '';
        this.updateElement('win-rate-change', winRateChange + this.dashboard.tradingStats.winRate.toFixed(1) + '%');
    }

    updateElement(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
    }

    startTradingStatsUpdates() {
        // Clear existing interval
        if (this.statsUpdateInterval) {
            clearInterval(this.statsUpdateInterval);
        }
        
        // Update stats every 30 seconds
        this.statsUpdateInterval = setInterval(() => {
            this.loadTradingStats();
        }, 30000);
    }

    stopTradingStatsUpdates() {
        if (this.statsUpdateInterval) {
            clearInterval(this.statsUpdateInterval);
            this.statsUpdateInterval = null;
        }
    }
}
