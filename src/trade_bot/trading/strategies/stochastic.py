"""Stochastic Oscillator trading strategy."""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base import BaseStrategy, TradeSignal
from ...core.config import TradingConfig

logger = logging.getLogger(__name__)


class StochasticStrategy(BaseStrategy):
    """Stochastic Oscillator trading strategy."""
    
    def __init__(self, config: TradingConfig, k_period: int = 14, d_period: int = 3, 
                 oversold: int = 20, overbought: int = 80, enable_stop_loss: bool = True, 
                 enable_take_profit: bool = True):
        super().__init__(config)
        self.k_period = k_period
        self.d_period = d_period
        self.oversold = oversold
        self.overbought = overbought
        self.enable_stop_loss = enable_stop_loss
        self.enable_take_profit = enable_take_profit
        
        # Stochastic values
        self.k_percent = None
        self.d_percent = None
        self.prev_k = None
        self.prev_d = None
        
        # Initialize signal tracking
        self.signals_by_type = {
            'oversold_buy': 0,
            'overbought_sell': 0,
            'k_cross_above_d': 0,
            'k_cross_below_d': 0,
            'divergence_bullish': 0,
            'divergence_bearish': 0,
            'stop_loss': 0,
            'take_profit': 0
        }
        
    def add_price(self, price: float, timestamp: datetime) -> None:
        """Add a new price point to the history."""
        self.price_history.append(price)
        
        # Keep only recent data to avoid memory issues
        if len(self.price_history) > self.k_period * 5000:
            self.price_history = self.price_history[-self.k_period * 5000:]
    
    def calculate_stochastic(self) -> Optional[Dict[str, float]]:
        """Calculate Stochastic Oscillator values."""
        if len(self.price_history) < self.k_period:
            return None
        
        # Get recent prices for calculation
        recent_prices = self.price_history[-self.k_period:]
        
        # Calculate %K
        highest_high = max(recent_prices)
        lowest_low = min(recent_prices)
        current_close = recent_prices[-1]
        
        if highest_high == lowest_low:
            k_percent = 50.0  # Neutral when no range
        else:
            k_percent = ((current_close - lowest_low) / (highest_high - lowest_low)) * 100
        
        # Calculate %D (simple moving average of %K)
        # For simplicity, we'll use the current %K as %D
        # In practice, you'd maintain a history of %K values
        d_percent = k_percent
        
        return {
            'k_percent': k_percent,
            'd_percent': d_percent
        }
    
    def generate_signal(self, current_price: float, timestamp: datetime, is_end_of_period: bool = False) -> Optional[TradeSignal]:
        """Generate trading signal based on Stochastic Oscillator."""
        if len(self.price_history) < self.k_period:
            return None
        
        # Calculate Stochastic values
        stoch_data = self.calculate_stochastic()
        if stoch_data is None:
            return None
        
        self.k_percent = stoch_data['k_percent']
        self.d_percent = stoch_data['d_percent']
        
        # Check for oversold conditions
        if self.k_percent <= self.oversold and self.d_percent <= self.oversold:
            self.signals_by_type['oversold_buy'] += 1
            return TradeSignal(
                action='buy',
                price=current_price,
                quantity=self.calculate_position_size(current_price),
                reason=f'Stochastic oversold (K: {self.k_percent:.2f}, D: {self.d_percent:.2f})',
                timestamp=timestamp
            )
        
        # Check for overbought conditions
        if self.k_percent >= self.overbought and self.d_percent >= self.overbought:
            self.signals_by_type['overbought_sell'] += 1
            return TradeSignal(
                action='sell',
                price=current_price,
                quantity=self.calculate_position_size(current_price),
                reason=f'Stochastic overbought (K: {self.k_percent:.2f}, D: {self.d_percent:.2f})',
                timestamp=timestamp
            )
        
        # Check for %K crossing %D
        if self.prev_k is not None and self.prev_d is not None:
            # %K crosses above %D (bullish)
            if self.prev_k <= self.prev_d and self.k_percent > self.d_percent:
                self.signals_by_type['k_cross_above_d'] += 1
                return TradeSignal(
                    action='buy',
                    price=current_price,
                    quantity=self.calculate_position_size(current_price),
                    reason=f'Stochastic K cross above D (K: {self.k_percent:.2f}, D: {self.d_percent:.2f})',
                    timestamp=timestamp
                )
            
            # %K crosses below %D (bearish)
            elif self.prev_k >= self.prev_d and self.k_percent < self.d_percent:
                self.signals_by_type['k_cross_below_d'] += 1
                return TradeSignal(
                    action='sell',
                    price=current_price,
                    quantity=self.calculate_position_size(current_price),
                    reason=f'Stochastic K cross below D (K: {self.k_percent:.2f}, D: {self.d_percent:.2f})',
                    timestamp=timestamp
                )
        
        # Store current values for next iteration
        self.prev_k = self.k_percent
        self.prev_d = self.d_percent
        
        return None
    
    def get_strategy_name(self) -> str:
        """Get the name of this strategy."""
        return "Stochastic"
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Get strategy information and statistics."""
        return {
            'strategy_name': 'Stochastic',
            'parameters': {
                'k_period': self.k_period,
                'd_period': self.d_period,
                'oversold': self.oversold,
                'overbought': self.overbought,
                'enable_stop_loss': self.enable_stop_loss,
                'enable_take_profit': self.enable_take_profit
            },
            'current_values': {
                'k_percent': self.k_percent,
                'd_percent': self.d_percent
            },
            'signals_by_type': self.signals_by_type.copy(),
            'total_signals': sum(self.signals_by_type.values()),
            'no_signal_count': self.no_signal_count
        }
