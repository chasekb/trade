from typing import List
"""MACD (Moving Average Convergence Divergence) trading strategy."""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base import BaseStrategy, TradeSignal
from ...core.config import TradingConfig

logger = logging.getLogger(__name__)


class MACDStrategy(BaseStrategy):
    """MACD (Moving Average Convergence Divergence) trading strategy."""
    
    def __init__(self, config: TradingConfig, fast_period: int = 12, slow_period: int = 26, 
                 signal_period: int = 9, enable_stop_loss: bool = True, enable_take_profit: bool = True):
        super().__init__(config)
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.enable_stop_loss = enable_stop_loss
        self.enable_take_profit = enable_take_profit
        
        # MACD values
        self.macd_line = None
        self.signal_line = None
        self.histogram = None
        self.prev_macd = None
        self.prev_signal = None
        
        # Initialize signal tracking
        self.signals_by_type = {
            'macd_cross_above': 0,
            'macd_cross_below': 0,
            'histogram_positive': 0,
            'histogram_negative': 0,
            'divergence_bullish': 0,
            'divergence_bearish': 0,
            'stop_loss': 0,
            'take_profit': 0
        }
        
    def add_price(self, price: float, timestamp: datetime) -> None:
        """Add a new price point to the history."""
        self.price_history.append(price)
        
        # Keep only recent data to avoid memory issues
        if len(self.price_history) > self.slow_period * 5000:
            self.price_history = self.price_history[-self.slow_period * 5000:]
    
    def calculate_ema(self, prices: List[float], period: int) -> Optional[float]:
        """Calculate exponential moving average."""
        if len(prices) < period:
            return None
        
        alpha = 2.0 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = alpha * price + (1 - alpha) * ema
        
        return ema
    
    def calculate_macd(self) -> Optional[Dict[str, float]]:
        """Calculate MACD values."""
        if len(self.price_history) < self.slow_period:
            return None
        
        # Calculate EMAs
        fast_ema = self.calculate_ema(self.price_history, self.fast_period)
        slow_ema = self.calculate_ema(self.price_history, self.slow_period)
        
        if fast_ema is None or slow_ema is None:
            return None
        
        # MACD line = Fast EMA - Slow EMA
        macd_line = fast_ema - slow_ema
        
        # For signal line, we need to calculate EMA of MACD line
        # This is a simplified version - in practice, you'd maintain a history of MACD values
        signal_line = macd_line  # Simplified for this implementation
        
        # Histogram = MACD line - Signal line
        histogram = macd_line - signal_line
        
        return {
            'macd_line': macd_line,
            'signal_line': signal_line,
            'histogram': histogram
        }
    
    def generate_signal(self, current_price: float, timestamp: datetime, is_end_of_period: bool = False) -> Optional[TradeSignal]:
        """Generate trading signal based on MACD."""
        if len(self.price_history) < self.slow_period:
            return None
        
        # Calculate MACD
        macd_data = self.calculate_macd()
        if macd_data is None:
            return None
        
        self.macd_line = macd_data['macd_line']
        self.signal_line = macd_data['signal_line']
        self.histogram = macd_data['histogram']
        
        # Check for MACD line crossing signal line
        if self.prev_macd is not None and self.prev_signal is not None:
            # MACD crosses above signal line (bullish)
            if self.prev_macd <= self.prev_signal and self.macd_line > self.signal_line:
                self.signals_by_type['macd_cross_above'] += 1
                return TradeSignal(
                    action='buy',
                    price=current_price,
                    quantity=self.calculate_position_size(current_price),
                    reason=f'MACD cross above signal line (MACD: {self.macd_line:.4f}, Signal: {self.signal_line:.4f})',
                    timestamp=timestamp
                )
            
            # MACD crosses below signal line (bearish)
            elif self.prev_macd >= self.prev_signal and self.macd_line < self.signal_line:
                self.signals_by_type['macd_cross_below'] += 1
                return TradeSignal(
                    action='sell',
                    price=current_price,
                    quantity=self.calculate_position_size(current_price),
                    reason=f'MACD cross below signal line (MACD: {self.macd_line:.4f}, Signal: {self.signal_line:.4f})',
                    timestamp=timestamp
                )
        
        # Check histogram for momentum
        if self.histogram > 0:
            self.signals_by_type['histogram_positive'] += 1
        else:
            self.signals_by_type['histogram_negative'] += 1
        
        # Store current values for next iteration
        self.prev_macd = self.macd_line
        self.prev_signal = self.signal_line
        
        return None
    
    def get_strategy_name(self) -> str:
        """Get the name of this strategy."""
        return "MACD"
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Get strategy information and statistics."""
        return {
            'strategy_name': 'MACD',
            'parameters': {
                'fast_period': self.fast_period,
                'slow_period': self.slow_period,
                'signal_period': self.signal_period,
                'enable_stop_loss': self.enable_stop_loss,
                'enable_take_profit': self.enable_take_profit
            },
            'current_values': {
                'macd_line': self.macd_line,
                'signal_line': self.signal_line,
                'histogram': self.histogram
            },
            'signals_by_type': self.signals_by_type.copy(),
            'total_signals': sum(self.signals_by_type.values()),
            'no_signal_count': self.no_signal_count
        }
