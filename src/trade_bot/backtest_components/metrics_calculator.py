"""Metrics calculation component for backtesting."""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
import numpy as np

from .backtest_result import BacktestResult
from .trade_executor import TradeExecutor
from .equity_tracker import EquityTracker

logger = logging.getLogger(__name__)


class MetricsCalculator:
    """Calculates performance metrics for backtesting results."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def calculate_metrics(self, trade_executor: TradeExecutor, equity_tracker: EquityTracker,
                         start_date: datetime, end_date: datetime, 
                         signal_stats: Optional[Dict[str, Any]] = None,
                         final_price: Optional[float] = None) -> BacktestResult:
        """Calculate comprehensive backtesting metrics.
        
        Args:
            trade_executor: Trade executor with trade history
            equity_tracker: Equity tracker with equity curve
            start_date: Backtest start date
            end_date: Backtest end date
            signal_stats: Optional signal statistics
            final_price: Final price for unrealized P&L calculation
            
        Returns:
            BacktestResult with all calculated metrics
        """
        # Basic trade metrics
        total_trades = trade_executor.get_trade_count()
        winning_trades = len(trade_executor.get_winning_trades())
        losing_trades = len(trade_executor.get_losing_trades())
        win_rate = trade_executor.get_win_rate()
        
        # P&L metrics
        total_pnl = trade_executor.get_total_pnl()
        total_fees = trade_executor.get_total_fees()
        net_profit = trade_executor.get_net_profit()
        
        # Average metrics
        avg_win = trade_executor.get_average_win()
        avg_loss = trade_executor.get_average_loss()
        largest_win = trade_executor.get_largest_win()
        largest_loss = trade_executor.get_largest_loss()
        
        # Profit factor
        profit_factor = trade_executor.get_profit_factor()
        
        # Equity metrics
        initial_balance = trade_executor.initial_balance
        final_balance = trade_executor.get_current_balance()
        
        # Add unrealized P&L if position is still open
        if trade_executor.get_current_position() > 0 and final_price:
            unrealized_pnl = (final_price - trade_executor.get_entry_price()) * trade_executor.get_current_position()
            final_balance += unrealized_pnl
        
        total_return = equity_tracker.get_total_return()
        max_drawdown = equity_tracker.get_max_drawdown()
        sharpe_ratio = equity_tracker.get_sharpe_ratio()
        
        # Signal metrics
        signal_stats = signal_stats or {}
        total_signals = signal_stats.get('total_signals', 0)
        signals_by_type = signal_stats.get('signals_by_type', {})
        signal_rate = signal_stats.get('signal_rate', 0.0)
        no_signal_count = signal_stats.get('no_signal_count', 0)
        
        return BacktestResult(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            total_return=total_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            total_fees=total_fees,
            net_profit=net_profit,
            start_date=start_date,
            end_date=end_date,
            initial_balance=initial_balance,
            final_balance=final_balance,
            total_signals=total_signals,
            signals_by_type=signals_by_type,
            signal_rate=signal_rate,
            no_signal_count=no_signal_count
        )
    
    def calculate_advanced_metrics(self, equity_curve: list) -> Dict[str, float]:
        """Calculate advanced performance metrics.
        
        Args:
            equity_curve: List of equity curve data points
            
        Returns:
            Dictionary of advanced metrics
        """
        if len(equity_curve) < 2:
            return {}
        
        # Extract returns
        returns = []
        for i in range(1, len(equity_curve)):
            prev_equity = equity_curve[i-1]['total_equity']
            curr_equity = equity_curve[i]['total_equity']
            if prev_equity > 0:
                returns.append((curr_equity - prev_equity) / prev_equity)
        
        if not returns:
            return {}
        
        returns = np.array(returns)
        
        # Calculate metrics
        metrics = {}
        
        # Basic statistics
        metrics['mean_return'] = float(np.mean(returns))
        metrics['std_return'] = float(np.std(returns))
        metrics['skewness'] = float(self._calculate_skewness(returns))
        metrics['kurtosis'] = float(self._calculate_kurtosis(returns))
        
        # Risk metrics
        metrics['var_95'] = float(np.percentile(returns, 5))  # 95% VaR
        metrics['var_99'] = float(np.percentile(returns, 1))  # 99% VaR
        metrics['cvar_95'] = float(np.mean(returns[returns <= metrics['var_95']]))  # CVaR
        metrics['cvar_99'] = float(np.mean(returns[returns <= metrics['var_99']]))  # CVaR
        
        # Calmar ratio (annual return / max drawdown)
        annual_return = metrics['mean_return'] * 365
        max_dd = max(point['drawdown'] for point in equity_curve) / 100
        metrics['calmar_ratio'] = annual_return / max_dd if max_dd > 0 else 0
        
        # Sortino ratio (return / downside deviation)
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 0:
            downside_std = np.std(downside_returns)
            metrics['sortino_ratio'] = annual_return / downside_std if downside_std > 0 else 0
        else:
            metrics['sortino_ratio'] = float('inf')
        
        # Information ratio (excess return / tracking error)
        # Assuming risk-free rate of 2% annually
        risk_free_rate = 0.02 / 365
        excess_returns = returns - risk_free_rate
        metrics['information_ratio'] = float(np.mean(excess_returns) / np.std(excess_returns)) if np.std(excess_returns) > 0 else 0
        
        return metrics
    
    def _calculate_skewness(self, returns: np.ndarray) -> float:
        """Calculate skewness of returns."""
        if len(returns) < 3:
            return 0.0
        
        mean = np.mean(returns)
        std = np.std(returns)
        if std == 0:
            return 0.0
        
        return np.mean(((returns - mean) / std) ** 3)
    
    def _calculate_kurtosis(self, returns: np.ndarray) -> float:
        """Calculate kurtosis of returns."""
        if len(returns) < 4:
            return 0.0
        
        mean = np.mean(returns)
        std = np.std(returns)
        if std == 0:
            return 0.0
        
        return np.mean(((returns - mean) / std) ** 4) - 3  # Excess kurtosis
    
    def calculate_rolling_metrics(self, equity_curve: list, window: int = 30) -> Dict[str, list]:
        """Calculate rolling metrics over time.
        
        Args:
            equity_curve: List of equity curve data points
            window: Rolling window size
            
        Returns:
            Dictionary of rolling metrics
        """
        if len(equity_curve) < window:
            return {}
        
        rolling_metrics = {
            'returns': [],
            'volatility': [],
            'sharpe_ratio': [],
            'max_drawdown': []
        }
        
        for i in range(window, len(equity_curve) + 1):
            window_data = equity_curve[i-window:i]
            
            # Calculate returns for this window
            returns = []
            for j in range(1, len(window_data)):
                prev_equity = window_data[j-1]['total_equity']
                curr_equity = window_data[j]['total_equity']
                if prev_equity > 0:
                    returns.append((curr_equity - prev_equity) / prev_equity)
            
            if returns:
                returns_array = np.array(returns)
                rolling_metrics['returns'].append(np.mean(returns_array))
                rolling_metrics['volatility'].append(np.std(returns_array))
                
                # Rolling Sharpe ratio
                if np.std(returns_array) > 0:
                    rolling_metrics['sharpe_ratio'].append(np.mean(returns_array) / np.std(returns_array))
                else:
                    rolling_metrics['sharpe_ratio'].append(0)
                
                # Rolling max drawdown
                peak = max(point['total_equity'] for point in window_data)
                current = window_data[-1]['total_equity']
                rolling_metrics['max_drawdown'].append((peak - current) / peak * 100)
            else:
                rolling_metrics['returns'].append(0)
                rolling_metrics['volatility'].append(0)
                rolling_metrics['sharpe_ratio'].append(0)
                rolling_metrics['max_drawdown'].append(0)
        
        return rolling_metrics
