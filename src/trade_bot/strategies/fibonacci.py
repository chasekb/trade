"""Fibonacci Retracement trading strategy."""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base import BaseStrategy, TradeSignal
from ..config import TradingConfig

logger = logging.getLogger(__name__)


class FibonacciRetracementStrategy(BaseStrategy):
    """Fibonacci Retracement trading strategy."""
    
    def __init__(self, config: TradingConfig, lookback_period: int = 50, 
                 enable_stop_loss: bool = True, enable_take_profit: bool = True):
        super().__init__(config)
        self.lookback_period = lookback_period
        self.enable_stop_loss = enable_stop_loss
        self.enable_take_profit = enable_take_profit
        
        # Fibonacci levels
        self.fib_levels = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
        
        # Swing points
        self.swing_high = None
        self.swing_low = None
        self.swing_high_time = None
        self.swing_low_time = None
        
        # Current position
        self.entry_price = None
        self.stop_loss_price = None
        self.take_profit_price = None
        
        # Initialize signal tracking
        self.signals_by_type = {
            'fib_support_buy': 0,
            'fib_resistance_sell': 0,
            'fib_bounce_buy': 0,
            'fib_rejection_sell': 0,
            'stop_loss': 0,
            'take_profit': 0
        }
        
    def add_price(self, price: float, timestamp: datetime) -> None:
        """Add a new price point to the history."""
        self.price_history.append(price)
        
        # Keep only recent data to avoid memory issues
        if len(self.price_history) > self.lookback_period * 5000:
            self.price_history = self.price_history[-self.lookback_period * 5000:]
    
    def find_swing_points(self) -> tuple:
        """Find recent swing high and low points."""
        if len(self.price_history) < self.lookback_period:
            return None, None
        
        recent_prices = self.price_history[-self.lookback_period:]
        
        # Find swing high (highest point in recent period)
        swing_high = max(recent_prices)
        swing_high_idx = recent_prices.index(swing_high)
        
        # Find swing low (lowest point in recent period)
        swing_low = min(recent_prices)
        swing_low_idx = recent_prices.index(swing_low)
        
        return swing_high, swing_low
    
    def calculate_fibonacci_levels(self, swing_high: float, swing_low: float) -> Dict[str, float]:
        """Calculate Fibonacci retracement levels."""
        price_range = swing_high - swing_low
        fib_levels = {}
        
        for level in self.fib_levels:
            fib_price = swing_low + (price_range * level)
            fib_levels[f'fib_{level}'] = fib_price
        
        return fib_levels
    
    def find_nearest_fib_level(self, current_price: float, fib_levels: Dict[str, float]) -> tuple:
        """Find the nearest Fibonacci level to current price."""
        min_distance = float('inf')
        nearest_level = None
        nearest_price = None
        
        for level_name, fib_price in fib_levels.items():
            distance = abs(current_price - fib_price)
            if distance < min_distance:
                min_distance = distance
                nearest_level = level_name
                nearest_price = fib_price
        
        return nearest_level, nearest_price
    
    def is_support_level(self, current_price: float, fib_price: float, tolerance: float = 0.01) -> bool:
        """Check if current price is near a Fibonacci support level."""
        return abs(current_price - fib_price) / fib_price <= tolerance
    
    def is_resistance_level(self, current_price: float, fib_price: float, tolerance: float = 0.01) -> bool:
        """Check if current price is near a Fibonacci resistance level."""
        return abs(current_price - fib_price) / fib_price <= tolerance
    
    def generate_signal(self, current_price: float, timestamp: datetime, is_end_of_period: bool = False) -> Optional[TradeSignal]:
        """Generate trading signal based on Fibonacci retracement levels."""
        if len(self.price_history) < self.lookback_period:
            return None
        
        # Find swing points
        swing_high, swing_low = self.find_swing_points()
        if swing_high is None or swing_low is None:
            return None
        
        # Calculate Fibonacci levels
        fib_levels = self.calculate_fibonacci_levels(swing_high, swing_low)
        
        # Find nearest Fibonacci level
        nearest_level, nearest_price = self.find_nearest_fib_level(current_price, fib_levels)
        
        if nearest_level is None:
            return None
        
        # Check for support level bounces (buy signals)
        if nearest_level in ['fib_0.382', 'fib_0.5', 'fib_0.618']:
            if self.is_support_level(current_price, nearest_price):
                self.signals_by_type['fib_support_buy'] += 1
                return TradeSignal(
                    action='buy',
                    price=current_price,
                    quantity=self.calculate_position_size(current_price),
                    reason=f'Fibonacci support at {nearest_level} level: ${current_price:.2f}',
                    timestamp=timestamp
                )
        
        # Check for resistance level rejections (sell signals)
        if nearest_level in ['fib_0.236', 'fib_0.382', 'fib_0.5']:
            if self.is_resistance_level(current_price, nearest_price):
                self.signals_by_type['fib_resistance_sell'] += 1
                return TradeSignal(
                    action='sell',
                    price=current_price,
                    quantity=self.calculate_position_size(current_price),
                    reason=f'Fibonacci resistance at {nearest_level} level: ${current_price:.2f}',
                    timestamp=timestamp
                )
        
        # Check for bounce off support levels
        if len(self.price_history) >= 2:
            prev_price = self.price_history[-2]
            if prev_price < current_price and nearest_level in ['fib_0.382', 'fib_0.5', 'fib_0.618']:
                if self.is_support_level(prev_price, nearest_price):
                    self.signals_by_type['fib_bounce_buy'] += 1
                    return TradeSignal(
                        action='buy',
                        price=current_price,
                        quantity=self.calculate_position_size(current_price),
                        reason=f'Fibonacci bounce from {nearest_level} level: ${current_price:.2f}',
                        timestamp=timestamp
                    )
        
        # Check for rejection from resistance levels
        if len(self.price_history) >= 2:
            prev_price = self.price_history[-2]
            if prev_price > current_price and nearest_level in ['fib_0.236', 'fib_0.382', 'fib_0.5']:
                if self.is_resistance_level(prev_price, nearest_price):
                    self.signals_by_type['fib_rejection_sell'] += 1
                    return TradeSignal(
                        action='sell',
                        price=current_price,
                        quantity=self.calculate_position_size(current_price),
                        reason=f'Fibonacci rejection from {nearest_level} level: ${current_price:.2f}',
                        timestamp=timestamp
                    )
        
        return None
    
    def get_strategy_name(self) -> str:
        """Get the name of this strategy."""
        return "Fibonacci Retracement"
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Get strategy information and statistics."""
        swing_high, swing_low = self.find_swing_points()
        fib_levels = self.calculate_fibonacci_levels(swing_high, swing_low) if swing_high and swing_low else {}
        
        return {
            'strategy_name': 'Fibonacci Retracement',
            'parameters': {
                'lookback_period': self.lookback_period,
                'enable_stop_loss': self.enable_stop_loss,
                'enable_take_profit': self.enable_take_profit
            },
            'current_values': {
                'swing_high': swing_high,
                'swing_low': swing_low,
                'fibonacci_levels': fib_levels,
                'entry_price': self.entry_price,
                'stop_loss_price': self.stop_loss_price,
                'take_profit_price': self.take_profit_price
            },
            'signals_by_type': self.signals_by_type.copy(),
            'total_signals': sum(self.signals_by_type.values()),
            'no_signal_count': self.no_signal_count
        }
