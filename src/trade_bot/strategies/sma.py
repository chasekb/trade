"""Simple Moving Average (SMA) trading strategy."""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base import BaseStrategy, TradeSignal
from ..config import TradingConfig

logger = logging.getLogger(__name__)


class SimpleMovingAverageStrategy(BaseStrategy):
    """Simple moving average crossover strategy."""
    
    def __init__(self, config: TradingConfig, short_window: int = 10, long_window: int = 30, 
                 enable_stop_loss: bool = True, enable_take_profit: bool = True):
        super().__init__(config)
        self.short_window = short_window
        self.long_window = long_window
        self.enable_stop_loss = enable_stop_loss
        self.enable_take_profit = enable_take_profit
        
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
        
        # Keep only recent history (increased limit for extended backtesting)
        if len(self.price_history) > self.long_window * 5000:
            self.price_history = self.price_history[-self.long_window * 5000:]
    
    def calculate_sma(self, window: int) -> Optional[float]:
        """Calculate simple moving average for given window."""
        if len(self.price_history) < window:
            return None
            
        recent_prices = self.price_history[-window:]
        return sum(recent_prices) / len(recent_prices)
    
    def generate_signal(self, current_price: float, timestamp: datetime, is_end_of_period: bool = False) -> Optional[TradeSignal]:
        """Generate trading signal based on current market conditions."""
        if len(self.price_history) < self.long_window:
            return None
            
        short_sma = self.calculate_sma(self.short_window)
        long_sma = self.calculate_sma(self.long_window)
        
        if short_sma is None or long_sma is None:
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
            
        # Check for crossover
        prev_short_sma = None
        prev_long_sma = None
        
        if len(self.price_history) >= self.long_window + 1:
            # Get previous values (exclude the current price)
            prev_short_prices = self.price_history[-(self.short_window + 1):-1]
            prev_long_prices = self.price_history[-(self.long_window + 1):-1]
            
            prev_short_sma = sum(prev_short_prices) / len(prev_short_prices) if len(prev_short_prices) >= self.short_window else None
            prev_long_sma = sum(prev_long_prices) / len(prev_long_prices) if len(prev_long_prices) >= self.long_window else None
            
            # Log SMA values for debugging
            prev_short_str = f"{prev_short_sma:.2f}" if prev_short_sma is not None else 'N/A'
            prev_long_str = f"{prev_long_sma:.2f}" if prev_long_sma is not None else 'N/A'
            logger.debug(f"SMA values: short={short_sma:.2f}, long={long_sma:.2f}, prev_short={prev_short_str}, prev_long={prev_long_str}, position={self.position}, price_history_length={len(self.price_history)}")
            
            # Log when we have enough data for strategy
            if len(self.price_history) == self.long_window + 1:
                logger.info(f"Strategy now has enough data for full calculations: {len(self.price_history)} points")
        
        # Only check for crossovers if we have valid previous SMAs
        if prev_short_sma is not None and prev_long_sma is not None:
            # Golden cross (short SMA crosses above long SMA) - Buy signal
            if (prev_short_sma <= prev_long_sma and 
                short_sma > long_sma and 
                self.position == 0):
                
                self.signal_count += 1
                self.signals_by_type['golden_cross'] += 1
                quantity = self.config.max_position_size / current_price
                prev_short_str = f"{prev_short_sma:.2f}" if prev_short_sma is not None else 'N/A'
                prev_long_str = f"{prev_long_sma:.2f}" if prev_long_sma is not None else 'N/A'
                logger.debug(f"Golden cross detected: prev_short={prev_short_str}, prev_long={prev_long_str}, short={short_sma:.2f}, long={long_sma:.2f}, position={self.position}")
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
                
                self.signal_count += 1
                self.signals_by_type['death_cross'] += 1
                prev_short_str = f"{prev_short_sma:.2f}" if prev_short_sma is not None else 'N/A'
                prev_long_str = f"{prev_long_sma:.2f}" if prev_long_sma is not None else 'N/A'
                logger.debug(f"Death cross detected: prev_short={prev_short_str}, prev_long={prev_long_str}, short={short_sma:.2f}, long={long_sma:.2f}, position={self.position}")
                return TradeSignal(
                    action='sell',
                    price=current_price,
                    quantity=self.position,
                    timestamp=timestamp,
                    reason=f"Death cross: SMA{self.short_window} crossed below SMA{self.long_window}"
                )
                
            # Additional signals for more trading opportunities
            # Buy when short SMA is significantly above long SMA (momentum)
            elif (short_sma > long_sma * 1.02 and  # 2% above
                  self.position == 0 and
                  len(self.price_history) > self.long_window * 2):  # Wait for some history
                
                self.signal_count += 1
                self.signals_by_type['momentum_buy'] += 1
                quantity = self.config.max_position_size / current_price
                logger.debug(f"Momentum buy: short={short_sma:.2f}, long={long_sma:.2f}, ratio={short_sma/long_sma:.4f}")
                return TradeSignal(
                    action='buy',
                    price=current_price,
                    quantity=quantity,
                    timestamp=timestamp,
                    reason=f"Momentum buy: SMA{self.short_window} is {((short_sma/long_sma-1)*100):.1f}% above SMA{self.long_window}"
                )
                
            # Sell when short SMA is significantly below long SMA (momentum)
            elif (short_sma < long_sma * 0.98 and  # 2% below
                  self.position > 0):
                
                self.signal_count += 1
                self.signals_by_type['momentum_sell'] += 1
                logger.debug(f"Momentum sell: short={short_sma:.2f}, long={long_sma:.2f}, ratio={short_sma/long_sma:.4f}")
                return TradeSignal(
                    action='sell',
                    price=current_price,
                    quantity=self.position,
                    timestamp=timestamp,
                    reason=f"Momentum sell: SMA{self.short_window} is {((short_sma/long_sma-1)*100):.1f}% below SMA{self.long_window}"
                )
                
            # Additional trend-following signals
            # Buy when price is above both SMAs and we're not in position
            elif (current_price > short_sma and 
                  current_price > long_sma and 
                  short_sma > long_sma and
                  self.position == 0 and
                  len(self.price_history) > self.long_window * 2):
                
                self.signal_count += 1
                self.signals_by_type['trend_buy'] += 1
                quantity = self.config.max_position_size / current_price
                logger.debug(f"Trend buy: price={current_price:.2f}, short={short_sma:.2f}, long={long_sma:.2f}")
                return TradeSignal(
                    action='buy',
                    price=current_price,
                    quantity=quantity,
                    timestamp=timestamp,
                    reason=f"Trend buy: Price above both SMAs (price: ${current_price:.2f})"
                )
                
            # Sell when price is below both SMAs and we're in position
            elif (current_price < short_sma and 
                  current_price < long_sma and 
                  short_sma < long_sma and
                  self.position > 0):
                
                self.signal_count += 1
                self.signals_by_type['trend_sell'] += 1
                logger.debug(f"Trend sell: price={current_price:.2f}, short={short_sma:.2f}, long={long_sma:.2f}")
                return TradeSignal(
                    action='sell',
                    price=current_price,
                    quantity=self.position,
                    timestamp=timestamp,
                    reason=f"Trend sell: Price below both SMAs (price: ${current_price:.2f})"
                )
        
        # Count when we have enough data but no signal is generated
        if len(self.price_history) >= self.long_window + 1:
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
        return f"SMA({self.short_window},{self.long_window})"
