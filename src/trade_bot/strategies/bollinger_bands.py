"""Bollinger Bands trading strategy."""

import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from .base import BaseStrategy, TradeSignal
from ..config import TradingConfig

logger = logging.getLogger(__name__)


class BollingerBandsStrategy(BaseStrategy):
    """Bollinger Bands trading strategy."""
    
    def __init__(self, config: TradingConfig, period: int = 20, std_dev: float = 2.0, 
                 enable_stop_loss: bool = True, enable_take_profit: bool = True):
        super().__init__(config)
        self.period = period
        self.std_dev = std_dev
        self.enable_stop_loss = enable_stop_loss
        self.enable_take_profit = enable_take_profit
        
        # Initialize signal tracking
        self.signals_by_type = {
            'upper_band_touch': 0,
            'lower_band_touch': 0,
            'middle_band_cross': 0,
            'squeeze': 0,
            'stop_loss': 0,
            'take_profit': 0
        }
        
    def add_price(self, price: float, timestamp: datetime) -> None:
        """Add a new price point to the history."""
        self.price_history.append(price)
        
        # Keep only recent data to avoid memory issues
        if len(self.price_history) > self.period * 5000:
            self.price_history = self.price_history[-self.period * 5000:]
    
    def calculate_bollinger_bands(self, prices: List[float]) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """Calculate Bollinger Bands for given prices."""
        if len(prices) < self.period:
            return None, None, None
        
        # Calculate SMA (middle band)
        sma = sum(prices) / len(prices)
        
        # Calculate standard deviation
        variance = sum((price - sma) ** 2 for price in prices) / len(prices)
        std = variance ** 0.5
        
        # Calculate upper and lower bands
        upper_band = sma + (self.std_dev * std)
        lower_band = sma - (self.std_dev * std)
        
        return upper_band, sma, lower_band
    
    def generate_signal(self, current_price: float, timestamp: datetime, is_end_of_period: bool = False) -> Optional[TradeSignal]:
        """Generate trading signal based on Bollinger Bands."""
        if len(self.price_history) < self.period:
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
        
        # Calculate Bollinger Bands
        recent_prices = self.price_history[-self.period:]
        upper_band, middle_band, lower_band = self.calculate_bollinger_bands(recent_prices)
        
        if upper_band is None:
            return None
        
        # Calculate previous Bollinger Bands for comparison
        prev_upper_band = None
        prev_middle_band = None
        prev_lower_band = None
        
        if len(self.price_history) >= self.period + 1:
            prev_prices = self.price_history[-(self.period + 1):-1]
            prev_upper_band, prev_middle_band, prev_lower_band = self.calculate_bollinger_bands(prev_prices)
        
        # Log Bollinger Bands values for debugging
        logger.debug(f"Bollinger Bands: upper={upper_band:.2f}, middle={middle_band:.2f}, lower={lower_band:.2f}, price={current_price:.2f}, position={self.position}")
        
        # Log when we have enough data for strategy
        if len(self.price_history) == self.period + 1:
            logger.info(f"Bollinger Bands strategy now has enough data for full calculations: {len(self.price_history)} points")
        
        # Signal conditions
        if prev_upper_band is not None and prev_middle_band is not None and prev_lower_band is not None:
            # Upper band touch - Sell signal (price hits upper band)
            if (current_price >= upper_band and 
                self.position > 0 and
                prev_upper_band is not None and current_price > prev_upper_band):
                
                self.signal_count += 1
                self.signals_by_type['upper_band_touch'] += 1
                logger.debug(f"Upper band touch: price={current_price:.2f}, upper_band={upper_band:.2f}")
                return TradeSignal(
                    action='sell',
                    price=current_price,
                    quantity=self.position,
                    timestamp=timestamp,
                    reason=f"Upper band touch: Price ${current_price:.2f} >= Upper Band ${upper_band:.2f}"
                )
            
            # Lower band touch - Buy signal (price hits lower band)
            elif (current_price <= lower_band and 
                  self.position == 0 and
                  prev_lower_band is not None and current_price < prev_lower_band):
                
                self.signal_count += 1
                self.signals_by_type['lower_band_touch'] += 1
                quantity = self.config.max_position_size / current_price
                logger.debug(f"Lower band touch: price={current_price:.2f}, lower_band={lower_band:.2f}")
                return TradeSignal(
                    action='buy',
                    price=current_price,
                    quantity=quantity,
                    timestamp=timestamp,
                    reason=f"Lower band touch: Price ${current_price:.2f} <= Lower Band ${lower_band:.2f}"
                )
            
            # Middle band cross - Trend following
            # Buy when price crosses above middle band from below
            elif (current_price > middle_band and 
                  self.price_history[-2] <= prev_middle_band and
                  self.position == 0):
                
                self.signal_count += 1
                self.signals_by_type['middle_band_cross'] += 1
                quantity = self.config.max_position_size / current_price
                logger.debug(f"Middle band cross up: price={current_price:.2f}, middle_band={middle_band:.2f}")
                return TradeSignal(
                    action='buy',
                    price=current_price,
                    quantity=quantity,
                    timestamp=timestamp,
                    reason=f"Middle band cross up: Price ${current_price:.2f} > Middle Band ${middle_band:.2f}"
                )
            
            # Sell when price crosses below middle band from above
            elif (current_price < middle_band and 
                  self.price_history[-2] >= prev_middle_band and
                  self.position > 0):
                
                self.signal_count += 1
                self.signals_by_type['middle_band_cross'] += 1
                logger.debug(f"Middle band cross down: price={current_price:.2f}, middle_band={middle_band:.2f}")
                return TradeSignal(
                    action='sell',
                    price=current_price,
                    quantity=self.position,
                    timestamp=timestamp,
                    reason=f"Middle band cross down: Price ${current_price:.2f} < Middle Band ${middle_band:.2f}"
                )
            
            # Bollinger Bands squeeze - Low volatility signal
            # Buy when bands are squeezed (low volatility) and price is near middle
            elif (self.position == 0 and
                  (upper_band - lower_band) / middle_band < 0.05 and  # 5% band width
                  abs(current_price - middle_band) / middle_band < 0.02):  # Within 2% of middle
                
                self.signal_count += 1
                self.signals_by_type['squeeze'] += 1
                quantity = self.config.max_position_size / current_price
                logger.debug(f"Bollinger squeeze: price={current_price:.2f}, band_width={((upper_band - lower_band) / middle_band * 100):.2f}%")
                return TradeSignal(
                    action='buy',
                    price=current_price,
                    quantity=quantity,
                    timestamp=timestamp,
                    reason=f"Bollinger squeeze: Low volatility, Price ${current_price:.2f} near Middle Band ${middle_band:.2f}"
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
        return f"BollingerBands({self.period},{self.std_dev})"
