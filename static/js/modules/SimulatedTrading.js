/**
 * SimulatedTrading Module
 * Handles simulated trading statistics and portfolio management
 */
export class SimulatedTrading {
    constructor(dashboard) {
        this.dashboard = dashboard;
    }

    async loadSimulatedTradingStats() {
        try {
            const response = await fetch('/api/simulated-trading/status');
            const data = await response.json();
            
            if (data.portfolio) {
                this.updateSimulatedTradingStats(data.portfolio);
            } else {
                console.error('No portfolio data received');
            }
        } catch (error) {
            console.error('Error loading simulated trading stats:', error);
        }
    }

    updateSimulatedTradingStats(portfolioData) {
        if (!portfolioData) {
            return;
        }

        // Calculate proper statistics from portfolio data
        const trades = portfolioData.trades || [];
        const positions = portfolioData.positions || {};

        // Calculate trade-based metrics
        const winningTrades = trades.filter(trade => trade.pnl > 0);
        const losingTrades = trades.filter(trade => trade.pnl < 0);
        const totalTrades = trades.length;
        const winningTradesCount = winningTrades.length;
        const losingTradesCount = losingTrades.length;

        // Calculate P&L metrics
        const totalPnl = portfolioData.total_pnl || 0;
        const totalFees = portfolioData.total_fees || 0;
        const netPnl = totalPnl - totalFees;

        // Calculate win rate
        const winRate = totalTrades > 0 ? (winningTradesCount / totalTrades) * 100 : 0;

        // Calculate trade size metrics (volume = quantity * price)
        const totalTradeVolume = trades.reduce((sum, trade) => sum + (trade.quantity * trade.price), 0);
        const avgTradeSize = totalTrades > 0 ? totalTradeVolume / totalTrades : 0;

        // Calculate best/worst trades (only from realized trades)
        const bestTrade = trades.length > 0 ? Math.max(...trades.map(t => t.pnl || 0)) : 0;
        const worstTrade = trades.length > 0 ? Math.min(...trades.map(t => t.pnl || 0)) : 0;

        // Calculate average win/loss
        const avgWin = winningTradesCount > 0 ? winningTrades.reduce((sum, trade) => sum + trade.pnl, 0) / winningTradesCount : 0;
        const avgLoss = losingTradesCount > 0 ? losingTrades.reduce((sum, trade) => sum + trade.pnl, 0) / losingTradesCount : 0;

        // Calculate profit factor
        const grossProfit = winningTrades.reduce((sum, trade) => sum + trade.pnl, 0);
        const grossLoss = Math.abs(losingTrades.reduce((sum, trade) => sum + trade.pnl, 0));
        const profitFactor = grossLoss > 0 ? grossProfit / grossLoss : (grossProfit > 0 ? Infinity : 0);

        // Calculate Sharpe ratio (simplified - would need more data for proper calculation)
        const sharpeRatio = 0.0; // Placeholder - would need return series

        // Calculate risk-adjusted return
        const riskAdjustedReturn = 0.0; // Placeholder - would need proper risk metrics

        // Count active positions
        const activePositions = Object.values(positions).filter(pos => pos.status === 'open').length;

        // Update simulated trading stats
        this.dashboard.simulatedTradingStats = {
            totalPnl: totalPnl,
            totalFees: totalFees,
            netPnl: netPnl,
            winRate: winRate,
            totalTrades: totalTrades,
            winningTrades: winningTradesCount,
            losingTrades: losingTradesCount,
            avgWin: avgWin,
            avgLoss: avgLoss,
            bestTrade: bestTrade,
            worstTrade: worstTrade,
            profitFactor: profitFactor,
            sharpeRatio: sharpeRatio,
            riskAdjustedReturn: riskAdjustedReturn,
            totalVolume: totalTradeVolume,
            avgTradeSize: avgTradeSize,
            activePositions: activePositions,
            grossProfit: grossProfit,
            grossLoss: grossLoss
        };

        // Log calculated stats for validation
        console.log('Simulated Trading Stats Calculated:', {
            totalTrades,
            winningTrades: winningTradesCount,
            losingTrades: losingTradesCount,
            winRate: winRate.toFixed(2) + '%',
            totalPnl: totalPnl.toFixed(2),
            netPnl: netPnl.toFixed(2),
            profitFactor: profitFactor === Infinity ? 'Infinity' : profitFactor.toFixed(2),
            avgWin: avgWin.toFixed(2),
            avgLoss: avgLoss.toFixed(2),
            bestTrade: bestTrade.toFixed(2),
            worstTrade: worstTrade.toFixed(2),
            activePositions
        });

        this.updateSimulatedTradingStatsUI();
    }

    updateSimulatedTradingStatsUI() {
        if (!this.dashboard.simulatedTradingStats) {
            return;
        }

        const stats = this.dashboard.simulatedTradingStats;

        // Update main stats
        this.updateElement('sim-total-pnl', stats.netPnl.toFixed(2));
        this.updateElement('sim-total-fees', stats.totalFees.toFixed(2));
        this.updateElement('sim-win-rate', stats.winRate.toFixed(1) + '%');
        this.updateElement('sim-total-trades', stats.totalTrades);
        this.updateElement('sim-winning-trades', stats.winningTrades);
        this.updateElement('sim-losing-trades', stats.losingTrades);

        // Performance Metrics
        this.updateElement('sim-avg-win', stats.avgWin.toFixed(2));
        this.updateElement('sim-avg-loss', stats.avgLoss.toFixed(2));
        this.updateElement('sim-best-trade', stats.bestTrade.toFixed(2));
        this.updateElement('sim-worst-trade', stats.worstTrade.toFixed(2));

        // Risk Metrics
        this.updateElement('sim-profit-factor', stats.profitFactor === Infinity ? '∞' : stats.profitFactor.toFixed(2));
        this.updateElement('sim-sharpe-ratio', stats.sharpeRatio.toFixed(2));
        this.updateElement('sim-risk-adjusted-return', stats.riskAdjustedReturn.toFixed(2));

        // Trading Activity
        this.updateElement('sim-total-volume', stats.totalVolume.toFixed(2));
        this.updateElement('sim-avg-trade-size', stats.avgTradeSize.toFixed(2));

        // Performance Trends (now using proper trade analysis)
        this.updateElement('sim-gross-profit', stats.grossProfit.toFixed(2));
        this.updateElement('sim-gross-loss', stats.grossLoss.toFixed(2));

        // Trading Activity Info
        this.updateElement('sim-active-positions', stats.activePositions);

        // Additional metrics that might be useful
        if (this.dashboard.simulatedTradingStats.profitFactor === Infinity) {
            this.updateElement('sim-profit-factor', '∞');
        }
    }

    updateElement(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
    }
}
