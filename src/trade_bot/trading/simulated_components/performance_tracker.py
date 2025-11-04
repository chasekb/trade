from typing import List
"""Performance tracking for simulated trading."""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class PerformanceTracker:
    """Tracks performance metrics for simulated trading."""
    
    def __init__(self, initial_balance: float = 10000.0):
        self.initial_balance = initial_balance
        self.peak_value = initial_balance
        self.max_drawdown = 0.0
        self.equity_curve = []
        
        logger.info(f"PerformanceTracker initialized with balance: ${initial_balance:.2f}")
    
    def update_equity(self, cash_balance: float, positions_value: float, 
                     timestamp: datetime = None) -> None:
        """Update equity curve with current values.
        
        Args:
            cash_balance: Current cash balance
            positions_value: Current value of all positions
            timestamp: Current timestamp
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        total_value = cash_balance + positions_value
        
        # Update peak value
        if total_value > self.peak_value:
            self.peak_value = total_value
        
        # Calculate current drawdown
        current_drawdown = (self.peak_value - total_value) / self.peak_value * 100
        if current_drawdown > self.max_drawdown:
            self.max_drawdown = current_drawdown
        
        # Record equity point
        equity_point = {
            'timestamp': timestamp,
            'cash_balance': cash_balance,
            'positions_value': positions_value,
            'total_value': total_value,
            'drawdown': current_drawdown,
            'return_pct': (total_value - self.initial_balance) / self.initial_balance * 100
        }
        
        self.equity_curve.append(equity_point)
        logger.debug(f"Equity updated: ${total_value:.2f}, drawdown: {current_drawdown:.2f}%")
    
    def get_current_value(self) -> float:
        """Get current total value."""
        if not self.equity_curve:
            return self.initial_balance
        
        return self.equity_curve[-1]['total_value']
    
    def get_total_return(self) -> float:
        """Get total return percentage."""
        if not self.equity_curve:
            return 0.0
        
        current_value = self.equity_curve[-1]['total_value']
        return (current_value - self.initial_balance) / self.initial_balance * 100
    
    def get_max_drawdown(self) -> float:
        """Get maximum drawdown percentage."""
        return self.max_drawdown
    
    def get_peak_value(self) -> float:
        """Get peak value."""
        return self.peak_value
    
    def get_equity_curve(self) -> List[Dict[str, Any]]:
        """Get equity curve data."""
        return self.equity_curve.copy()
    
    def get_volatility(self) -> float:
        """Get equity curve volatility."""
        if len(self.equity_curve) < 2:
            return 0.0
        
        returns = []
        for i in range(1, len(self.equity_curve)):
            prev_value = self.equity_curve[i-1]['total_value']
            curr_value = self.equity_curve[i]['total_value']
            if prev_value > 0:
                returns.append((curr_value - prev_value) / prev_value)
        
        if not returns:
            return 0.0
        
        import statistics
        return statistics.stdev(returns) * 100  # Return as percentage
    
    def get_sharpe_ratio(self, risk_free_rate: float = 0.02) -> float:
        """Get Sharpe ratio."""
        if len(self.equity_curve) < 2:
            return 0.0
        
        returns = []
        for i in range(1, len(self.equity_curve)):
            prev_value = self.equity_curve[i-1]['total_value']
            curr_value = self.equity_curve[i]['total_value']
            if prev_value > 0:
                returns.append((curr_value - prev_value) / prev_value)
        
        if not returns:
            return 0.0
        
        import statistics
        avg_return = statistics.mean(returns)
        std_return = statistics.stdev(returns)
        
        if std_return == 0:
            return 0.0
        
        # Annualize the ratio (assuming daily data)
        return (avg_return - risk_free_rate/365) / std_return * (365**0.5)
    
    def get_calmar_ratio(self) -> float:
        """Get Calmar ratio (annual return / max drawdown)."""
        if self.max_drawdown == 0:
            return float('inf')
        
        # Calculate annual return
        if not self.equity_curve:
            return 0.0
        
        current_value = self.equity_curve[-1]['total_value']
        total_return = (current_value - self.initial_balance) / self.initial_balance
        
        # Assume daily data, so annualize
        annual_return = total_return * 365
        
        return annual_return / (self.max_drawdown / 100)
    
    def get_sortino_ratio(self) -> float:
        """Get Sortino ratio (return / downside deviation)."""
        if len(self.equity_curve) < 2:
            return 0.0
        
        returns = []
        for i in range(1, len(self.equity_curve)):
            prev_value = self.equity_curve[i-1]['total_value']
            curr_value = self.equity_curve[i]['total_value']
            if prev_value > 0:
                returns.append((curr_value - prev_value) / prev_value)
        
        if not returns:
            return 0.0
        
        import statistics
        avg_return = statistics.mean(returns)
        
        # Calculate downside deviation
        downside_returns = [r for r in returns if r < 0]
        if not downside_returns:
            return float('inf')
        
        downside_std = statistics.stdev(downside_returns)
        
        if downside_std == 0:
            return float('inf')
        
        # Annualize
        return (avg_return * 365) / (downside_std * (365**0.5))
    
    def get_drawdown_periods(self) -> List[Dict[str, Any]]:
        """Get drawdown periods."""
        if not self.equity_curve:
            return []
        
        drawdown_periods = []
        in_drawdown = False
        drawdown_start = None
        
        for point in self.equity_curve:
            if point['total_value'] < self.peak_value:
                if not in_drawdown:
                    in_drawdown = True
                    drawdown_start = point['timestamp']
            else:
                if in_drawdown:
                    in_drawdown = False
                    if drawdown_start:
                        # Find max drawdown in this period
                        period_data = [p for p in self.equity_curve 
                                     if drawdown_start <= p['timestamp'] <= point['timestamp']]
                        max_dd = max(p['drawdown'] for p in period_data) if period_data else 0
                        
                        drawdown_periods.append({
                            'start': drawdown_start,
                            'end': point['timestamp'],
                            'max_drawdown': max_dd
                        })
        
        return drawdown_periods
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        return {
            'initial_balance': self.initial_balance,
            'current_value': self.get_current_value(),
            'peak_value': self.get_peak_value(),
            'total_return': self.get_total_return(),
            'max_drawdown': self.get_max_drawdown(),
            'volatility': self.get_volatility(),
            'sharpe_ratio': self.get_sharpe_ratio(),
            'calmar_ratio': self.get_calmar_ratio(),
            'sortino_ratio': self.get_sortino_ratio(),
            'data_points': len(self.equity_curve),
            'drawdown_periods': len(self.get_drawdown_periods())
        }
    
    def reset(self) -> None:
        """Reset performance tracking."""
        self.peak_value = self.initial_balance
        self.max_drawdown = 0.0
        self.equity_curve.clear()
        logger.info("Performance tracking reset")
