"""RSI (Relative Strength Index) trading strategy."""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base import BaseStrategy, TradeSignal
from ...core.config import TradingConfig

logger = logging.getLogger(__name__)


class RSIStrategy(BaseStrategy):
    """RSI (Relative Strength Index) trading strategy."""
    
    def __init__(self, config: TradingConfig, period: int = 14, oversold: int = 30, 
                 overbought: int = 70, enable_stop_loss: bool = True, enable_take_profit: bool = True):
        super().__init__(config)
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.enable_stop_loss = enable_stop_loss
        self.enable_take_profit = enable_take_profit
        
        # Initialize signal tracking
        self.signals_by_type = {
            'oversold_buy': 0,
            'overbought_sell': 0,
            'rsi_divergence_buy': 0,
            'rsi_divergence_sell': 0,
            'rsi_cross_oversold': 0,
            'rsi_cross_overbought': 0,
            'stop_loss': 0,
            'take_profit': 0
        }
        
    def add_price(self, price: float, timestamp: datetime) -> None:
        """Add a new price point to the history."""
        self.price_history.append(price)
        
        # Keep only recent data to avoid memory issues
        if len(self.price_history) > self.period * 5000:
            self.price_history = self.price_history[-self.period * 5000:]
    
    def calculate_rsi(self, prices: List[float]) -> Optional[float]:
        """Calculate RSI for given prices."""
        if len(prices) < self.period + 1:
            return None
        
        # Calculate price changes
        price_changes = []
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            price_changes.append(change)
        
        # Separate gains and losses
        gains = [max(change, 0) for change in price_changes]
        losses = [abs(min(change, 0)) for change in price_changes]
        
        # Calculate average gains and losses
        avg_gain = sum(gains) / len(gains)
        avg_loss = sum(losses) / len(losses)
        
        # Avoid division by zero
        if avg_loss == 0:
            return 100.0
        
        # Calculate RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def generate_signal(self, current_price: float, timestamp: datetime, is_end_of_period: bool = False) -> Optional[TradeSignal]:
        """Generate trading signal based on RSI."""
        if len(self.price_history) < self.period + 1:
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
        
        # Calculate RSI
        recent_prices = self.price_history[-self.period-1:]
        current_rsi = self.calculate_rsi(recent_prices)
        
        if current_rsi is None:
            return None
        
        # Calculate previous RSI for comparison
        prev_rsi = None
        if len(self.price_history) >= self.period + 2:
            prev_prices = self.price_history[-(self.period + 2):-1]
            prev_rsi = self.calculate_rsi(prev_prices)
        
        # Log RSI values for debugging
        prev_rsi_str = f"{prev_rsi:.2f}" if prev_rsi is not None else 'N/A'
        logger.debug(f"RSI: current={current_rsi:.2f}, prev={prev_rsi_str}, price={current_price:.2f}, position={self.position}")
        
        # Log when we have enough data for strategy
        if len(self.price_history) == self.period + 1:
            logger.info(f"RSI strategy now has enough data for full calculations: {len(self.price_history)} points")
        
        # Signal conditions
        if prev_rsi is not None:
            # Oversold conditions - Buy signals
            if (current_rsi <= self.oversold and 
                self.position == 0 and
                prev_rsi > self.oversold):  # RSI crossing below oversold level
                
                self.signal_count += 1
                self.signals_by_type['rsi_cross_oversold'] += 1
                quantity = self.config.max_position_size / current_price
                logger.debug(f"RSI cross oversold: rsi={current_rsi:.2f}, oversold={self.oversold}")
                return TradeSignal(
                    action='buy',
                    price=current_price,
                    quantity=quantity,
                    timestamp=timestamp,
                    reason=f"RSI cross oversold: RSI {current_rsi:.2f} <= {self.oversold} (oversold level)"
                )
            
            # Overbought conditions - Sell signals
            elif (current_rsi >= self.overbought and 
                  self.position > 0 and
                  prev_rsi < self.overbought):  # RSI crossing above overbought level
                
                self.signal_count += 1
                self.signals_by_type['rsi_cross_overbought'] += 1
                logger.debug(f"RSI cross overbought: rsi={current_rsi:.2f}, overbought={self.overbought}")
                return TradeSignal(
                    action='sell',
                    price=current_price,
                    quantity=self.position,
                    timestamp=timestamp,
                    reason=f"RSI cross overbought: RSI {current_rsi:.2f} >= {self.overbought} (overbought level)"
                )
            
            # Simple oversold/overbought signals (without cross requirement)
            elif (current_rsi <= self.oversold and 
                  self.position == 0):
                
                self.signal_count += 1
                self.signals_by_type['oversold_buy'] += 1
                quantity = self.config.max_position_size / current_price
                logger.debug(f"RSI oversold buy: rsi={current_rsi:.2f}, oversold={self.oversold}")
                return TradeSignal(
                    action='buy',
                    price=current_price,
                    quantity=quantity,
                    timestamp=timestamp,
                    reason=f"RSI oversold: RSI {current_rsi:.2f} <= {self.oversold} (oversold level)"
                )
            
            elif (current_rsi >= self.overbought and 
                  self.position > 0):
                
                self.signal_count += 1
                self.signals_by_type['overbought_sell'] += 1
                logger.debug(f"RSI overbought sell: rsi={current_rsi:.2f}, overbought={self.overbought}")
                return TradeSignal(
                    action='sell',
                    price=current_price,
                    quantity=self.position,
                    timestamp=timestamp,
                    reason=f"RSI overbought: RSI {current_rsi:.2f} >= {self.overbought} (overbought level)"
                )
            
            # RSI divergence signals (simplified)
            # Buy when RSI is oversold and price is near recent low
            elif (current_rsi <= self.oversold + 5 and  # Near oversold
                  self.position == 0 and
                  current_price <= min(self.price_history[-5:])):  # Price near recent low
                
                self.signal_count += 1
                self.signals_by_type['rsi_divergence_buy'] += 1
                quantity = self.config.max_position_size / current_price
                logger.debug(f"RSI divergence buy: rsi={current_rsi:.2f}, price={current_price:.2f}")
                return TradeSignal(
                    action='buy',
                    price=current_price,
                    quantity=quantity,
                    timestamp=timestamp,
                    reason=f"RSI divergence buy: RSI {current_rsi:.2f} near oversold, price near recent low"
                )
            
            # Sell when RSI is overbought and price is near recent high
            elif (current_rsi >= self.overbought - 5 and  # Near overbought
                  self.position > 0 and
                  current_price >= max(self.price_history[-5:])):  # Price near recent high
                
                self.signal_count += 1
                self.signals_by_type['rsi_divergence_sell'] += 1
                logger.debug(f"RSI divergence sell: rsi={current_rsi:.2f}, price={current_price:.2f}")
                return TradeSignal(
                    action='sell',
                    price=current_price,
                    quantity=self.position,
                    timestamp=timestamp,
                    reason=f"RSI divergence sell: RSI {current_rsi:.2f} near overbought, price near recent high"
                )
        
        # Count when we have enough data but no signal is generated
        if len(self.price_history) >= self.period + 1:
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
        return f"RSI({self.period},{self.oversold},{self.overbought})"
