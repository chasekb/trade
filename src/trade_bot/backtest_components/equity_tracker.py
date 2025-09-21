"""Equity curve tracking component for backtesting."""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class EquityTracker:
    """Tracks equity curve and drawdown during backtesting."""
    
    def __init__(self, initial_balance: float):
        self.initial_balance = initial_balance
        self.equity_curve = []
        self.peak_balance = initial_balance
        self.max_drawdown = 0.0
        
        logger.info(f"EquityTracker initialized with balance: ${initial_balance:.2f}")
    
    def update_equity(self, current_price: float, timestamp: datetime, 
                     position: float, entry_price: float, balance: float) -> None:
        """Update equity curve with current values.
        
        Args:
            current_price: Current market price
            timestamp: Current timestamp
            position: Current position size
            entry_price: Entry price of position
            balance: Current cash balance
        """
        # Calculate unrealized P&L
        unrealized_pnl = 0.0
        if position > 0:
            unrealized_pnl = (current_price - entry_price) * position
        
        # Calculate total equity
        total_equity = balance + unrealized_pnl
        
        # Update peak balance
        if total_equity > self.peak_balance:
            self.peak_balance = total_equity
        
        # Calculate current drawdown
        current_drawdown = (self.peak_balance - total_equity) / self.peak_balance * 100
        if current_drawdown > self.max_drawdown:
            self.max_drawdown = current_drawdown
        
        # Record equity point
        equity_point = {
            'timestamp': timestamp,
            'price': current_price,
            'position': position,
            'entry_price': entry_price,
            'balance': balance,
            'unrealized_pnl': unrealized_pnl,
            'total_equity': total_equity,
            'drawdown': current_drawdown,
            'return_pct': (total_equity - self.initial_balance) / self.initial_balance * 100
        }
        
        self.equity_curve.append(equity_point)
        logger.debug(f"Equity updated: ${total_equity:.2f}, drawdown: {current_drawdown:.2f}%")
    
    def get_equity_curve(self) -> List[Dict[str, Any]]:
        """Get the equity curve data."""
        return self.equity_curve.copy()
    
    def get_equity_curve_df(self) -> pd.DataFrame:
        """Get equity curve as pandas DataFrame."""
        if not self.equity_curve:
            return pd.DataFrame()
        
        return pd.DataFrame(self.equity_curve)
    
    def get_max_drawdown(self) -> float:
        """Get maximum drawdown percentage."""
        return self.max_drawdown
    
    def get_current_equity(self) -> float:
        """Get current total equity."""
        if not self.equity_curve:
            return self.initial_balance
        
        return self.equity_curve[-1]['total_equity']
    
    def get_total_return(self) -> float:
        """Get total return percentage."""
        if not self.equity_curve:
            return 0.0
        
        current_equity = self.equity_curve[-1]['total_equity']
        return (current_equity - self.initial_balance) / self.initial_balance * 100
    
    def get_peak_equity(self) -> float:
        """Get peak equity value."""
        return self.peak_balance
    
    def get_equity_at_date(self, target_date: datetime) -> Optional[float]:
        """Get equity value at a specific date."""
        for point in reversed(self.equity_curve):
            if point['timestamp'] <= target_date:
                return point['total_equity']
        
        return None
    
    def get_drawdown_periods(self) -> List[Dict[str, Any]]:
        """Get drawdown periods (when equity was below peak)."""
        if not self.equity_curve:
            return []
        
        drawdown_periods = []
        in_drawdown = False
        drawdown_start = None
        
        for point in self.equity_curve:
            if point['total_equity'] < self.peak_balance:
                if not in_drawdown:
                    in_drawdown = True
                    drawdown_start = point['timestamp']
            else:
                if in_drawdown:
                    in_drawdown = False
                    if drawdown_start:
                        drawdown_periods.append({
                            'start': drawdown_start,
                            'end': point['timestamp'],
                            'max_drawdown': max(p['drawdown'] for p in self.equity_curve 
                                              if drawdown_start <= p['timestamp'] <= point['timestamp'])
                        })
        
        return drawdown_periods
    
    def get_volatility(self) -> float:
        """Get equity curve volatility (standard deviation of returns)."""
        if len(self.equity_curve) < 2:
            return 0.0
        
        returns = []
        for i in range(1, len(self.equity_curve)):
            prev_equity = self.equity_curve[i-1]['total_equity']
            curr_equity = self.equity_curve[i]['total_equity']
            if prev_equity > 0:
                returns.append((curr_equity - prev_equity) / prev_equity)
        
        if not returns:
            return 0.0
        
        import statistics
        return statistics.stdev(returns) * 100  # Return as percentage
    
    def get_sharpe_ratio(self, risk_free_rate: float = 0.02) -> float:
        """Get Sharpe ratio (annualized)."""
        if len(self.equity_curve) < 2:
            return 0.0
        
        returns = []
        for i in range(1, len(self.equity_curve)):
            prev_equity = self.equity_curve[i-1]['total_equity']
            curr_equity = self.equity_curve[i]['total_equity']
            if prev_equity > 0:
                returns.append((curr_equity - prev_equity) / prev_equity)
        
        if not returns:
            return 0.0
        
        import statistics
        avg_return = statistics.mean(returns)
        std_return = statistics.stdev(returns)
        
        if std_return == 0:
            return 0.0
        
        # Annualize the ratio (assuming daily data)
        return (avg_return - risk_free_rate/365) / std_return * (365**0.5)
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics for the equity curve."""
        if not self.equity_curve:
            return {
                'initial_balance': self.initial_balance,
                'final_equity': self.initial_balance,
                'total_return': 0.0,
                'max_drawdown': 0.0,
                'volatility': 0.0,
                'sharpe_ratio': 0.0
            }
        
        return {
            'initial_balance': self.initial_balance,
            'final_equity': self.get_current_equity(),
            'peak_equity': self.get_peak_equity(),
            'total_return': self.get_total_return(),
            'max_drawdown': self.get_max_drawdown(),
            'volatility': self.get_volatility(),
            'sharpe_ratio': self.get_sharpe_ratio(),
            'data_points': len(self.equity_curve)
        }
