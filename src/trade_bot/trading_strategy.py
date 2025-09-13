"""Trading strategy implementation."""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import pandas as pd

from .config import TradingConfig


logger = logging.getLogger(__name__)


@dataclass
class TradeSignal:
    """Represents a trading signal."""
    action: str  # 'buy', 'sell', 'hold'
    price: float
    quantity: float
    timestamp: datetime
    reason: str


class SimpleMovingAverageStrategy:
    """Simple moving average crossover strategy."""
    
    def __init__(self, config: TradingConfig, short_window: int = 10, long_window: int = 30):
        self.config = config
        self.short_window = short_window
        self.long_window = long_window
        self.price_history: list = []
        self.position = 0.0  # Current position size
        self.entry_price = 0.0
        
    def add_price(self, price: float, timestamp: datetime) -> None:
        """Add a new price point to the history."""
        self.price_history.append({
            'price': price,
            'timestamp': timestamp
        })
        
        # Keep only recent history
        if len(self.price_history) > self.long_window * 2:
            self.price_history = self.price_history[-self.long_window * 2:]
    
    def calculate_sma(self, window: int) -> Optional[float]:
        """Calculate simple moving average for given window."""
        if len(self.price_history) < window:
            return None
            
        recent_prices = [p['price'] for p in self.price_history[-window:]]
        return sum(recent_prices) / len(recent_prices)
    
    def generate_signal(self, current_price: float, timestamp: datetime) -> Optional[TradeSignal]:
        """Generate trading signal based on current market conditions."""
        self.add_price(current_price, timestamp)
        
        if len(self.price_history) < self.long_window:
            return None
            
        short_sma = self.calculate_sma(self.short_window)
        long_sma = self.calculate_sma(self.long_window)
        
        if short_sma is None or long_sma is None:
            return None
            
        # Check for crossover
        if len(self.price_history) >= 2:
            prev_short_sma = self.calculate_sma(self.short_window)
            prev_long_sma = self.calculate_sma(self.long_window)
            
            # Get previous values
            if len(self.price_history) > self.short_window:
                prev_prices = [p['price'] for p in self.price_history[-(self.short_window + 1):-1]]
                prev_short_sma = sum(prev_prices) / len(prev_prices)
            
            if len(self.price_history) > self.long_window:
                prev_prices = [p['price'] for p in self.price_history[-(self.long_window + 1):-1]]
                prev_long_sma = sum(prev_prices) / len(prev_prices)
            
            # Golden cross (short SMA crosses above long SMA) - Buy signal
            if (prev_short_sma <= prev_long_sma and 
                short_sma > long_sma and 
                self.position == 0):
                
                quantity = self.config.max_position_size / current_price
                return TradeSignal(
                    action='buy',
                    price=current_price,
                    quantity=quantity,
                    timestamp=timestamp,
                    reason=f"Golden cross: SMA{self.short_window} crossed above SMA{self.long_window}"
                )
            
            # Death cross (short SMA crosses below long SMA) - Sell signal
            elif (prev_short_sma >= prev_long_sma and 
                  short_sma < long_sma and 
                  self.position > 0):
                
                return TradeSignal(
                    action='sell',
                    price=current_price,
                    quantity=self.position,
                    timestamp=timestamp,
                    reason=f"Death cross: SMA{self.short_window} crossed below SMA{self.long_window}"
                )
        
        # Check stop loss
        if self.position > 0:
            loss_percentage = (current_price - self.entry_price) / self.entry_price
            if loss_percentage <= -self.config.stop_loss_percentage:
                return TradeSignal(
                    action='sell',
                    price=current_price,
                    quantity=self.position,
                    timestamp=timestamp,
                    reason=f"Stop loss triggered: {loss_percentage:.2%} loss"
                )
        
        # Check take profit
        if self.position > 0:
            profit_percentage = (current_price - self.entry_price) / self.entry_price
            if profit_percentage >= self.config.take_profit_percentage:
                return TradeSignal(
                    action='sell',
                    price=current_price,
                    quantity=self.position,
                    timestamp=timestamp,
                    reason=f"Take profit triggered: {profit_percentage:.2%} profit"
                )
        
        return None
    
    def update_position(self, signal: TradeSignal) -> None:
        """Update position based on trade signal."""
        if signal.action == 'buy':
            self.position = signal.quantity
            self.entry_price = signal.price
            logger.info(f"Position opened: {signal.quantity:.6f} at {signal.price}")
        elif signal.action == 'sell':
            self.position = 0.0
            self.entry_price = 0.0
            logger.info(f"Position closed: {signal.quantity:.6f} at {signal.price}")
    
    def get_position_info(self) -> Dict[str, Any]:
        """Get current position information."""
        return {
            'position': self.position,
            'entry_price': self.entry_price,
            'unrealized_pnl': (self.position * self.entry_price) if self.position > 0 else 0.0
        }
