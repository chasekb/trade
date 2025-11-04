from typing import List
"""EMA (Exponential Moving Average) trading strategy."""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base import BaseStrategy, TradeSignal
from ...core.config import TradingConfig

logger = logging.getLogger(__name__)


class EMAStrategy(BaseStrategy):
    """EMA (Exponential Moving Average) trading strategy."""
    
    def __init__(self, config: TradingConfig, short_ema: int = 12, long_ema: int = 26, 
                 alpha: float = None, enable_stop_loss: bool = True, enable_take_profit: bool = True):
        super().__init__(config)
        self.short_ema = short_ema
        self.long_ema = long_ema
        self.enable_stop_loss = enable_stop_loss
        self.enable_take_profit = enable_take_profit
        
        # Alpha is the smoothing factor: 2 / (period + 1)
        # If not provided, calculate from short_ema period
        self.alpha_short = alpha if alpha is not None else 2.0 / (short_ema + 1)
        self.alpha_long = alpha if alpha is not None else 2.0 / (long_ema + 1)
        
        # EMA values
        self.short_ema_value = None
        self.long_ema_value = None
        self.prev_short_ema = None
        self.prev_long_ema = None
        
        # Initialize signal tracking
        self.signals_by_type = {
            'golden_cross': 0,
            'death_cross': 0,
            'momentum_buy': 0,
            'momentum_sell': 0,
            'trend_buy': 0,
            'trend_sell': 0,
            'stop_loss': 0,
            'take_profit': 0
        }
        
    def add_price(self, price: float, timestamp: datetime) -> None:
        """Add a new price point to the history."""
        self.price_history.append(price)
        
        # Keep only recent data to avoid memory issues (increased limit for backtesting)
        if len(self.price_history) > self.long_ema * 5000:
            self.price_history = self.price_history[-self.long_ema * 5000:]
    
    def calculate_ema(self, prices: List[float], alpha: float) -> Optional[float]:
        """Calculate EMA for given prices and alpha."""
        if not prices:
            return None
        
        # Start with the first price
        ema = prices[0]
        
        # Apply EMA formula: EMA = alpha * price + (1 - alpha) * previous_EMA
        for price in prices[1:]:
            ema = alpha * price + (1 - alpha) * ema
        
        return ema
    
    def generate_signal(self, current_price: float, timestamp: datetime, is_end_of_period: bool = False) -> Optional[TradeSignal]:
        """Generate trading signal based on EMA."""
        if len(self.price_history) < self.long_ema:
            return None
        
        # Check stop loss first (highest priority) - only if enabled
        if self.position > 0 and self.enable_stop_loss:
            loss_percentage = (current_price - self.entry_price) / self.entry_price
            if loss_percentage <= -self.config.stop_loss_percentage:
                self.signal_count += 1
                self.signals_by_type['stop_loss'] += 1
                return TradeSignal(
                    action='sell',
                    price=current_price,
                    quantity=self.position,
                    timestamp=timestamp,
                    reason=f"Stop loss triggered: {loss_percentage:.2%} loss"
                )
        
        # Check take profit second - only if enabled
        if self.position > 0 and self.enable_take_profit:
            profit_percentage = (current_price - self.entry_price) / self.entry_price
            if profit_percentage >= self.config.take_profit_percentage:
                self.signal_count += 1
                self.signals_by_type['take_profit'] += 1
                return TradeSignal(
                    action='sell',
                    price=current_price,
                    quantity=self.position,
                    timestamp=timestamp,
                    reason=f"Take profit triggered: {profit_percentage:.2%} profit"
                )
        
        # Calculate current EMAs
        recent_prices = self.price_history[-self.long_ema:]
        self.short_ema_value = self.calculate_ema(recent_prices[-self.short_ema:], self.alpha_short)
        self.long_ema_value = self.calculate_ema(recent_prices, self.alpha_long)
        
        if self.short_ema_value is None or self.long_ema_value is None:
            return None
        
        # Calculate previous EMAs for comparison
        self.prev_short_ema = None
        self.prev_long_ema = None
        
        if len(self.price_history) >= self.long_ema + 1:
            prev_prices = self.price_history[-(self.long_ema + 1):-1]
            self.prev_short_ema = self.calculate_ema(prev_prices[-self.short_ema:], self.alpha_short)
            self.prev_long_ema = self.calculate_ema(prev_prices, self.alpha_long)
        
        # Log EMA values for debugging
        prev_short_str = f"{self.prev_short_ema:.2f}" if self.prev_short_ema is not None else 'N/A'
        prev_long_str = f"{self.prev_long_ema:.2f}" if self.prev_long_ema is not None else 'N/A'
        logger.debug(f"EMA values: short={self.short_ema_value:.2f}, long={self.long_ema_value:.2f}, prev_short={prev_short_str}, prev_long={prev_long_str}, position={self.position}, price_history_length={len(self.price_history)}")
        
        # Log when we have enough data for strategy
        if len(self.price_history) == self.long_ema + 1:
            logger.info(f"EMA strategy now has enough data for full calculations: {len(self.price_history)} points")
        
        # Signal conditions
        if self.prev_short_ema is not None and self.prev_long_ema is not None:
            # Golden cross - Short EMA crosses above Long EMA
            if (self.short_ema_value > self.long_ema_value and 
                self.prev_short_ema <= self.prev_long_ema and
                self.position == 0):
                
                self.signal_count += 1
                self.signals_by_type['golden_cross'] += 1
                quantity = self.config.max_position_size / current_price
                prev_short_str = f"{self.prev_short_ema:.2f}" if self.prev_short_ema is not None else 'N/A'
                prev_long_str = f"{self.prev_long_ema:.2f}" if self.prev_long_ema is not None else 'N/A'
                logger.debug(f"Golden cross detected: prev_short={prev_short_str}, prev_long={prev_long_str}, short={self.short_ema_value:.2f}, long={self.long_ema_value:.2f}, position={self.position}")
                return TradeSignal(
                    action='buy',
                    price=current_price,
                    quantity=quantity,
                    timestamp=timestamp,
                    reason=f"Golden cross: EMA{self.short_ema} crossed above EMA{self.long_ema}"
                )
            
            # Death cross - Short EMA crosses below Long EMA
            elif (self.short_ema_value < self.long_ema_value and 
                  self.prev_short_ema >= self.prev_long_ema and
                  self.position > 0):
                
                self.signal_count += 1
                self.signals_by_type['death_cross'] += 1
                prev_short_str = f"{self.prev_short_ema:.2f}" if self.prev_short_ema is not None else 'N/A'
                prev_long_str = f"{self.prev_long_ema:.2f}" if self.prev_long_ema is not None else 'N/A'
                logger.debug(f"Death cross detected: prev_short={prev_short_str}, prev_long={prev_long_str}, short={self.short_ema_value:.2f}, long={self.long_ema_value:.2f}, position={self.position}")
                return TradeSignal(
                    action='sell',
                    price=current_price,
                    quantity=self.position,
                    timestamp=timestamp,
                    reason=f"Death cross: EMA{self.short_ema} crossed below EMA{self.long_ema}"
                )
            
            # Momentum signals - EMA ratio based
            elif (self.short_ema_value / self.long_ema_value > 1.02 and  # 2% above
                  self.position == 0):
                
                self.signal_count += 1
                self.signals_by_type['momentum_buy'] += 1
                quantity = self.config.max_position_size / current_price
                logger.debug(f"Momentum buy: short={self.short_ema_value:.2f}, long={self.long_ema_value:.2f}, ratio={self.short_ema_value/self.long_ema_value:.4f}")
                return TradeSignal(
                    action='buy',
                    price=current_price,
                    quantity=quantity,
                    timestamp=timestamp,
                    reason=f"Momentum buy: EMA{self.short_ema} is {((self.short_ema_value/self.long_ema_value-1)*100):.1f}% above EMA{self.long_ema}"
                )
            
            elif (self.short_ema_value / self.long_ema_value < 0.98 and  # 2% below
                  self.position > 0):
                
                self.signal_count += 1
                self.signals_by_type['momentum_sell'] += 1
                logger.debug(f"Momentum sell: short={self.short_ema_value:.2f}, long={self.long_ema_value:.2f}, ratio={self.short_ema_value/self.long_ema_value:.4f}")
                return TradeSignal(
                    action='sell',
                    price=current_price,
                    quantity=self.position,
                    timestamp=timestamp,
                    reason=f"Momentum sell: EMA{self.short_ema} is {((self.short_ema_value/self.long_ema_value-1)*100):.1f}% below EMA{self.long_ema}"
                )
            
            # Trend following signals - Price vs EMAs
            elif (current_price > self.short_ema_value and 
                  current_price > self.long_ema_value and
                  self.short_ema_value > self.long_ema_value and
                  self.position == 0):
                
                self.signal_count += 1
                self.signals_by_type['trend_buy'] += 1
                quantity = self.config.max_position_size / current_price
                logger.debug(f"Trend buy: price={current_price:.2f}, short={self.short_ema_value:.2f}, long={self.long_ema_value:.2f}")
                return TradeSignal(
                    action='buy',
                    price=current_price,
                    quantity=quantity,
                    timestamp=timestamp,
                    reason=f"Trend buy: Price above both EMAs (price: ${current_price:.2f})"
                )
            
            elif (current_price < self.short_ema_value and 
                  current_price < self.long_ema_value and
                  self.short_ema_value < self.long_ema_value and
                  self.position > 0):
                
                self.signal_count += 1
                self.signals_by_type['trend_sell'] += 1
                logger.debug(f"Trend sell: price={current_price:.2f}, short={self.short_ema_value:.2f}, long={self.long_ema_value:.2f}")
                return TradeSignal(
                    action='sell',
                    price=current_price,
                    quantity=self.position,
                    timestamp=timestamp,
                    reason=f"Trend sell: Price below both EMAs (price: ${current_price:.2f})"
                )
        
        # Count when we have enough data but no signal is generated
        if len(self.price_history) >= self.long_ema + 1:
            self.no_signal_count += 1
            
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
    
    def get_signal_stats(self) -> dict:
        """Get signal statistics."""
        return {
            'total_signals': self.signal_count,
            'signals_by_type': self.signals_by_type.copy(),
            'price_history_length': len(self.price_history),
            'no_signal_count': self.no_signal_count,
            'signal_rate': self.signal_count / max(len(self.price_history), 1) * 100
        }
    
    def get_position_info(self) -> Dict[str, Any]:
        """Get current position information."""
        return {
            'position': self.position,
            'entry_price': self.entry_price,
            'unrealized_pnl': (self.position * self.entry_price) if self.position > 0 else 0.0
        }
    
    def get_strategy_name(self) -> str:
        """Get the name of this strategy."""
        return f"EMA({self.short_ema},{self.long_ema})"
