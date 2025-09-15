"""Trading strategy implementation."""

import logging
from typing import Dict, Any, Optional, List
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
    
    def __init__(self, config: TradingConfig, short_window: int = 10, long_window: int = 30, enable_stop_loss: bool = True, enable_take_profit: bool = True):
        self.config = config
        self.short_window = short_window
        self.long_window = long_window
        self.enable_stop_loss = enable_stop_loss
        self.enable_take_profit = enable_take_profit
        self.price_history: list = []
        self.position = 0.0  # Current position size
        self.entry_price = 0.0
        
        # Signal tracking
        self.signal_count = 0
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
        self.no_signal_count = 0  # Count when we have enough data but no signal
        
    def add_price(self, price: float, timestamp: datetime) -> None:
        """Add a new price point to the history."""
        self.price_history.append({
            'price': price,
            'timestamp': timestamp
        })
        
        # Keep only recent history (increased limit for extended backtesting)
        if len(self.price_history) > self.long_window * 5000:
            self.price_history = self.price_history[-self.long_window * 5000:]
    
    def calculate_sma(self, window: int) -> Optional[float]:
        """Calculate simple moving average for given window."""
        if len(self.price_history) < window:
            return None
            
        recent_prices = [p['price'] for p in self.price_history[-window:]]
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
            prev_short_prices = [p['price'] for p in self.price_history[-(self.short_window + 1):-1]]
            prev_long_prices = [p['price'] for p in self.price_history[-(self.long_window + 1):-1]]
            
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


class BollingerBandsStrategy:
    """Bollinger Bands trading strategy."""
    
    def __init__(self, config: TradingConfig, period: int = 20, std_dev: float = 2.0, enable_stop_loss: bool = True, enable_take_profit: bool = True):
        self.config = config
        self.period = period
        self.std_dev = std_dev
        self.enable_stop_loss = enable_stop_loss
        self.enable_take_profit = enable_take_profit
        self.price_history: list = []
        self.position = 0.0  # Current position size
        self.entry_price = 0.0
        
        # Signal tracking
        self.signal_count = 0
        self.signals_by_type = {
            'upper_band_touch': 0,
            'lower_band_touch': 0,
            'middle_band_cross': 0,
            'squeeze': 0,
            'stop_loss': 0,
            'take_profit': 0
        }
        self.no_signal_count = 0  # Count when we have enough data but no signal
        
    def add_price(self, price: float, timestamp: datetime) -> None:
        """Add a new price point to the history."""
        self.price_history.append({
            'price': price,
            'timestamp': timestamp
        })
        
        # Keep only recent data to avoid memory issues
        if len(self.price_history) > self.period * 5000:
            self.price_history = self.price_history[-self.period * 5000:]
    
    def calculate_bollinger_bands(self, prices: List[float]) -> tuple:
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
        recent_prices = [p['price'] for p in self.price_history[-self.period:]]
        upper_band, middle_band, lower_band = self.calculate_bollinger_bands(recent_prices)
        
        if upper_band is None:
            return None
        
        # Calculate previous Bollinger Bands for comparison
        prev_upper_band = None
        prev_middle_band = None
        prev_lower_band = None
        
        if len(self.price_history) >= self.period + 1:
            prev_prices = [p['price'] for p in self.price_history[-(self.period + 1):-1]]
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
                  self.price_history[-2]['price'] <= prev_middle_band and
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
                  self.price_history[-2]['price'] >= prev_middle_band and
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


class RSIStrategy:
    """RSI (Relative Strength Index) trading strategy."""
    
    def __init__(self, config: TradingConfig, period: int = 14, oversold: int = 30, overbought: int = 70, enable_stop_loss: bool = True, enable_take_profit: bool = True):
        self.config = config
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.enable_stop_loss = enable_stop_loss
        self.enable_take_profit = enable_take_profit
        self.price_history: list = []
        self.position = 0.0  # Current position size
        self.entry_price = 0.0
        
        # Signal tracking
        self.signal_count = 0
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
        self.no_signal_count = 0  # Count when we have enough data but no signal
        
    def add_price(self, price: float, timestamp: datetime) -> None:
        """Add a new price point to the history."""
        self.price_history.append({
            'price': price,
            'timestamp': timestamp
        })
        
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
        recent_prices = [p['price'] for p in self.price_history[-self.period-1:]]
        current_rsi = self.calculate_rsi(recent_prices)
        
        if current_rsi is None:
            return None
        
        # Calculate previous RSI for comparison
        prev_rsi = None
        if len(self.price_history) >= self.period + 2:
            prev_prices = [p['price'] for p in self.price_history[-(self.period + 2):-1]]
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
                  current_price <= min([p['price'] for p in self.price_history[-5:]])):  # Price near recent low
                
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
                  current_price >= max([p['price'] for p in self.price_history[-5:]])):  # Price near recent high
                
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


class EMAStrategy:
    """EMA (Exponential Moving Average) trading strategy."""
    
    def __init__(self, config: TradingConfig, short_ema: int = 12, long_ema: int = 26, alpha: float = None, enable_stop_loss: bool = True, enable_take_profit: bool = True):
        self.config = config
        self.short_ema = short_ema
        self.long_ema = long_ema
        self.enable_stop_loss = enable_stop_loss
        self.enable_take_profit = enable_take_profit
        # Alpha is the smoothing factor: 2 / (period + 1)
        # If not provided, calculate from short_ema period
        self.alpha_short = alpha if alpha is not None else 2.0 / (short_ema + 1)
        self.alpha_long = alpha if alpha is not None else 2.0 / (long_ema + 1)
        self.price_history: list = []
        self.position = 0.0  # Current position size
        self.entry_price = 0.0
        
        # EMA values
        self.short_ema_value = None
        self.long_ema_value = None
        self.prev_short_ema = None
        self.prev_long_ema = None
        
        # Signal tracking
        self.signal_count = 0
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
        self.no_signal_count = 0  # Count when we have enough data but no signal
        
    def add_price(self, price: float, timestamp: datetime) -> None:
        """Add a new price point to the history."""
        self.price_history.append({
            'price': price,
            'timestamp': timestamp
        })
        
        # Keep only recent data to avoid memory issues (increased limit for backtesting)
        if len(self.price_history) > self.long_ema * 5000:
            self.price_history = self.price_history[-self.long_ema * 5000:]
    
    def calculate_ema(self, prices: List[float], alpha: float) -> float:
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
        recent_prices = [p['price'] for p in self.price_history[-self.long_ema:]]
        self.short_ema_value = self.calculate_ema(recent_prices[-self.short_ema:], self.alpha_short)
        self.long_ema_value = self.calculate_ema(recent_prices, self.alpha_long)
        
        if self.short_ema_value is None or self.long_ema_value is None:
            return None
        
        # Calculate previous EMAs for comparison
        self.prev_short_ema = None
        self.prev_long_ema = None
        
        if len(self.price_history) >= self.long_ema + 1:
            prev_prices = [p['price'] for p in self.price_history[-(self.long_ema + 1):-1]]
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


class MACDStrategy:
    """MACD (Moving Average Convergence Divergence) trading strategy."""
    
    def __init__(self, config: TradingConfig, fast_ema: int = 12, slow_ema: int = 26, signal_ema: int = 9, enable_stop_loss: bool = True, enable_take_profit: bool = True):
        self.config = config
        self.fast_ema = fast_ema
        self.slow_ema = slow_ema
        self.signal_ema = signal_ema
        self.enable_stop_loss = enable_stop_loss
        self.enable_take_profit = enable_take_profit
        self.price_history: list = []
        self.position = 0.0  # Current position size
        self.entry_price = 0.0
        
        # MACD values
        self.macd_line = None
        self.signal_line = None
        self.histogram = None
        self.prev_macd_line = None
        self.prev_signal_line = None
        self.prev_histogram = None
        
        # Signal tracking
        self.signal_count = 0
        self.signals_by_type = {
            'macd_cross_above': 0,
            'macd_cross_below': 0,
            'histogram_positive': 0,
            'histogram_negative': 0,
            'histogram_cross_zero': 0,
            'macd_divergence_buy': 0,
            'macd_divergence_sell': 0,
            'stop_loss': 0,
            'take_profit': 0
        }
        self.no_signal_count = 0  # Count when we have enough data but no signal
        
    def add_price(self, price: float, timestamp: datetime) -> None:
        """Add a new price point to the history."""
        self.price_history.append({
            'price': price,
            'timestamp': timestamp
        })
        
        # Keep only recent data to avoid memory issues
        if len(self.price_history) > self.slow_ema * 5000:
            self.price_history = self.price_history[-self.slow_ema * 5000:]
    
    def calculate_ema(self, prices: List[float], period: int) -> float:
        """Calculate EMA for given prices and period."""
        if not prices or len(prices) < period:
            return None
        
        # Alpha is the smoothing factor: 2 / (period + 1)
        alpha = 2.0 / (period + 1)
        
        # Start with the first price
        ema = prices[0]
        
        # Apply EMA formula: EMA = alpha * price + (1 - alpha) * previous_EMA
        for price in prices[1:]:
            ema = alpha * price + (1 - alpha) * ema
        
        return ema
    
    def calculate_macd(self, prices: List[float]) -> tuple:
        """Calculate MACD for given prices."""
        if len(prices) < self.slow_ema:
            return None, None, None
        
        # Calculate fast and slow EMAs
        fast_ema = self.calculate_ema(prices, self.fast_ema)
        slow_ema = self.calculate_ema(prices, self.slow_ema)
        
        if fast_ema is None or slow_ema is None:
            return None, None, None
        
        # MACD line = Fast EMA - Slow EMA
        macd_line = fast_ema - slow_ema
        
        # For signal line, we need to calculate EMA of MACD line
        # We'll use a simplified approach with recent MACD values
        if len(prices) >= self.slow_ema + self.signal_ema - 1:
            # Calculate MACD values for signal line
            macd_values = []
            for i in range(self.slow_ema, len(prices) + 1):
                if i >= self.slow_ema:
                    fast_prices = prices[i-self.fast_ema:i]
                    slow_prices = prices[i-self.slow_ema:i]
                    if len(fast_prices) >= self.fast_ema and len(slow_prices) >= self.slow_ema:
                        fast_val = self.calculate_ema(fast_prices, self.fast_ema)
                        slow_val = self.calculate_ema(slow_prices, self.slow_ema)
                        if fast_val is not None and slow_val is not None:
                            macd_values.append(fast_val - slow_val)
            
            if len(macd_values) >= self.signal_ema:
                signal_line = self.calculate_ema(macd_values, self.signal_ema)
            else:
                signal_line = None
        else:
            signal_line = None
        
        # Histogram = MACD line - Signal line
        histogram = macd_line - signal_line if signal_line is not None else None
        
        return macd_line, signal_line, histogram
    
    def generate_signal(self, current_price: float, timestamp: datetime, is_end_of_period: bool = False) -> Optional[TradeSignal]:
        """Generate trading signal based on MACD."""
        if len(self.price_history) < self.slow_ema + self.signal_ema - 1:
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
        
        # Calculate current MACD
        recent_prices = [p['price'] for p in self.price_history[-self.slow_ema:]]
        self.macd_line, self.signal_line, self.histogram = self.calculate_macd(recent_prices)
        
        if self.macd_line is None or self.signal_line is None:
            return None
        
        # Calculate previous MACD for comparison
        self.prev_macd_line = None
        self.prev_signal_line = None
        self.prev_histogram = None
        
        if len(self.price_history) >= self.slow_ema + self.signal_ema:
            prev_prices = [p['price'] for p in self.price_history[-(self.slow_ema + 1):-1]]
            self.prev_macd_line, self.prev_signal_line, self.prev_histogram = self.calculate_macd(prev_prices)
        
        # Log MACD values for debugging
        prev_macd_str = f"{self.prev_macd_line:.4f}" if self.prev_macd_line is not None else 'N/A'
        prev_signal_str = f"{self.prev_signal_line:.4f}" if self.prev_signal_line is not None else 'N/A'
        prev_hist_str = f"{self.prev_histogram:.4f}" if self.prev_histogram is not None else 'N/A'
        logger.debug(f"MACD: macd={self.macd_line:.4f}, signal={self.signal_line:.4f}, histogram={self.histogram:.4f}, prev_macd={prev_macd_str}, prev_signal={prev_signal_str}, prev_hist={prev_hist_str}, position={self.position}")
        
        # Log when we have enough data for strategy
        if len(self.price_history) == self.slow_ema + self.signal_ema:
            logger.info(f"MACD strategy now has enough data for full calculations: {len(self.price_history)} points")
        
        # Signal conditions
        if self.prev_macd_line is not None and self.prev_signal_line is not None:
            # MACD line crosses above signal line
            if (self.macd_line > self.signal_line and 
                self.prev_macd_line <= self.prev_signal_line and
                self.position == 0):
                
                self.signal_count += 1
                self.signals_by_type['macd_cross_above'] += 1
                quantity = self.config.max_position_size / current_price
                logger.debug(f"MACD cross above: macd={self.macd_line:.4f}, signal={self.signal_line:.4f}")
                return TradeSignal(
                    action='buy',
                    price=current_price,
                    quantity=quantity,
                    timestamp=timestamp,
                    reason=f"MACD cross above: MACD {self.macd_line:.4f} > Signal {self.signal_line:.4f}"
                )
            
            # MACD line crosses below signal line
            elif (self.macd_line < self.signal_line and 
                  self.prev_macd_line >= self.prev_signal_line and
                  self.position > 0):
                
                self.signal_count += 1
                self.signals_by_type['macd_cross_below'] += 1
                logger.debug(f"MACD cross below: macd={self.macd_line:.4f}, signal={self.signal_line:.4f}")
                return TradeSignal(
                    action='sell',
                    price=current_price,
                    quantity=self.position,
                    timestamp=timestamp,
                    reason=f"MACD cross below: MACD {self.macd_line:.4f} < Signal {self.signal_line:.4f}"
                )
            
            # Histogram signals
            elif (self.histogram is not None and self.prev_histogram is not None):
                # Histogram crosses above zero (positive momentum)
                if (self.histogram > 0 and 
                    self.prev_histogram <= 0 and
                    self.position == 0):
                    
                    self.signal_count += 1
                    self.signals_by_type['histogram_cross_zero'] += 1
                    quantity = self.config.max_position_size / current_price
                    logger.debug(f"Histogram cross zero: hist={self.histogram:.4f}, prev_hist={self.prev_histogram:.4f}")
                    return TradeSignal(
                        action='buy',
                        price=current_price,
                        quantity=quantity,
                        timestamp=timestamp,
                        reason=f"Histogram cross zero: Histogram {self.histogram:.4f} > 0"
                    )
                
                # Histogram crosses below zero (negative momentum)
                elif (self.histogram < 0 and 
                      self.prev_histogram >= 0 and
                      self.position > 0):
                    
                    self.signal_count += 1
                    self.signals_by_type['histogram_cross_zero'] += 1
                    logger.debug(f"Histogram cross zero: hist={self.histogram:.4f}, prev_hist={self.prev_histogram:.4f}")
                    return TradeSignal(
                        action='sell',
                        price=current_price,
                        quantity=self.position,
                        timestamp=timestamp,
                        reason=f"Histogram cross zero: Histogram {self.histogram:.4f} < 0"
                    )
                
                # Strong positive histogram (momentum)
                elif (self.histogram > 0.001 and  # Strong positive histogram
                      self.position == 0):
                    
                    self.signal_count += 1
                    self.signals_by_type['histogram_positive'] += 1
                    quantity = self.config.max_position_size / current_price
                    logger.debug(f"Histogram positive: hist={self.histogram:.4f}")
                    return TradeSignal(
                        action='buy',
                        price=current_price,
                        quantity=quantity,
                        timestamp=timestamp,
                        reason=f"Histogram positive: Strong momentum {self.histogram:.4f}"
                    )
                
                # Strong negative histogram (momentum)
                elif (self.histogram < -0.001 and  # Strong negative histogram
                      self.position > 0):
                    
                    self.signal_count += 1
                    self.signals_by_type['histogram_negative'] += 1
                    logger.debug(f"Histogram negative: hist={self.histogram:.4f}")
                    return TradeSignal(
                        action='sell',
                        price=current_price,
                        quantity=self.position,
                        timestamp=timestamp,
                        reason=f"Histogram negative: Strong negative momentum {self.histogram:.4f}"
                    )
            
            # MACD divergence signals (simplified)
            # Buy when MACD is positive and price is near recent low
            elif (self.macd_line > 0 and 
                  self.position == 0 and
                  current_price <= min([p['price'] for p in self.price_history[-5:]])):  # Price near recent low
                
                self.signal_count += 1
                self.signals_by_type['macd_divergence_buy'] += 1
                quantity = self.config.max_position_size / current_price
                logger.debug(f"MACD divergence buy: macd={self.macd_line:.4f}, price={current_price:.2f}")
                return TradeSignal(
                    action='buy',
                    price=current_price,
                    quantity=quantity,
                    timestamp=timestamp,
                    reason=f"MACD divergence buy: MACD {self.macd_line:.4f} positive, price near recent low"
                )
            
            # Sell when MACD is negative and price is near recent high
            elif (self.macd_line < 0 and 
                  self.position > 0 and
                  current_price >= max([p['price'] for p in self.price_history[-5:]])):  # Price near recent high
                
                self.signal_count += 1
                self.signals_by_type['macd_divergence_sell'] += 1
                logger.debug(f"MACD divergence sell: macd={self.macd_line:.4f}, price={current_price:.2f}")
                return TradeSignal(
                    action='sell',
                    price=current_price,
                    quantity=self.position,
                    timestamp=timestamp,
                    reason=f"MACD divergence sell: MACD {self.macd_line:.4f} negative, price near recent high"
                )
        
        # Count when we have enough data but no signal is generated
        if len(self.price_history) >= self.slow_ema + self.signal_ema:
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


class StochasticStrategy:
    """Stochastic Oscillator trading strategy."""
    
    def __init__(self, config: TradingConfig, k_period: int = 14, d_period: int = 3, overbought: int = 80, oversold: int = 20, enable_stop_loss: bool = True, enable_take_profit: bool = True):
        self.config = config
        self.k_period = k_period
        self.d_period = d_period
        self.overbought = overbought
        self.oversold = oversold
        self.enable_stop_loss = enable_stop_loss
        self.enable_take_profit = enable_take_profit
        self.price_history: list = []
        self.position = 0.0  # Current position size
        self.entry_price = 0.0
        
        # Stochastic values
        self.k_percent = None
        self.d_percent = None
        self.prev_k_percent = None
        self.prev_d_percent = None
        
        # Signal tracking
        self.signal_count = 0
        self.signals_by_type = {
            "k_cross_above_d": 0,
            "k_cross_below_d": 0,
            "k_cross_oversold": 0,
            "k_cross_overbought": 0,
            "d_cross_oversold": 0,
            "d_cross_overbought": 0,
            "stochastic_divergence_buy": 0,
            "stochastic_divergence_sell": 0,
            "stop_loss": 0,
            "take_profit": 0
        }
        self.no_signal_count = 0  # Count when we have enough data but no signal
        
    def add_price(self, price: float, timestamp: datetime) -> None:
        """Add a new price point to the history."""
        self.price_history.append({
            "price": price,
            "timestamp": timestamp
        })
        
        # Keep only recent data to avoid memory issues
        if len(self.price_history) > self.k_period * 5000:
            self.price_history = self.price_history[-self.k_period * 5000:]
    
    def calculate_stochastic(self, prices: List[float]) -> tuple:
        """Calculate Stochastic Oscillator for given prices."""
        if len(prices) < self.k_period:
            return None, None
        
        # Get the most recent k_period prices
        recent_prices = prices[-self.k_period:]
        
        # Calculate %K
        highest_high = max(recent_prices)
        lowest_low = min(recent_prices)
        
        if highest_high == lowest_low:
            k_percent = 50.0  # Neutral when no range
        else:
            current_close = recent_prices[-1]
            k_percent = ((current_close - lowest_low) / (highest_high - lowest_low)) * 100
        
        # Calculate %D (simple moving average of %K)
        if len(prices) >= self.k_period + self.d_period - 1:
            # Get k_percent values for %D calculation
            k_values = []
            for i in range(self.k_period, len(prices) + 1):
                if i >= self.k_period:
                    period_prices = prices[i-self.k_period:i]
                    if len(period_prices) >= self.k_period:
                        hh = max(period_prices)
                        ll = min(period_prices)
                        if hh == ll:
                            k_val = 50.0
                        else:
                            k_val = ((period_prices[-1] - ll) / (hh - ll)) * 100
                        k_values.append(k_val)
            
            if len(k_values) >= self.d_period:
                d_percent = sum(k_values[-self.d_period:]) / self.d_period
            else:
                d_percent = None
        else:
            d_percent = None
        
        return k_percent, d_percent
    
    def generate_signal(self, current_price: float, timestamp: datetime, is_end_of_period: bool = False) -> Optional[TradeSignal]:
        """Generate trading signal based on Stochastic Oscillator."""
        if len(self.price_history) < self.k_period + self.d_period - 1:
            return None
        
        # Check stop loss first (highest priority)
        if self.position > 0:
            loss_percentage = (current_price - self.entry_price) / self.entry_price
            if loss_percentage <= -self.config.stop_loss_percentage:
                self.signal_count += 1
                self.signals_by_type["stop_loss"] += 1
                return TradeSignal(
                    action="sell",
                    price=current_price,
                    quantity=self.position,
                    timestamp=timestamp,
                    reason=f"Stop loss triggered: {loss_percentage:.2%} loss"
                )
        
        # Check take profit second
        if self.position > 0:
            profit_percentage = (current_price - self.entry_price) / self.entry_price
            if profit_percentage >= self.config.take_profit_percentage:
                self.signal_count += 1
                self.signals_by_type["take_profit"] += 1
                return TradeSignal(
                    action="sell",
                    price=current_price,
                    quantity=self.position,
                    timestamp=timestamp,
                    reason=f"Take profit triggered: {profit_percentage:.2%} profit"
                )
        
        # Calculate current Stochastic
        recent_prices = [p["price"] for p in self.price_history[-self.k_period:]]
        self.k_percent, self.d_percent = self.calculate_stochastic(recent_prices)
        
        if self.k_percent is None or self.d_percent is None:
            return None
        
        # Calculate previous Stochastic for comparison
        self.prev_k_percent = None
        self.prev_d_percent = None
        
        if len(self.price_history) >= self.k_period + self.d_period:
            prev_prices = [p["price"] for p in self.price_history[-(self.k_period + 1):-1]]
            self.prev_k_percent, self.prev_d_percent = self.calculate_stochastic(prev_prices)
        
        # Log Stochastic values for debugging
        prev_k_str = f"{self.prev_k_percent:.2f}" if self.prev_k_percent is not None else "N/A"
        prev_d_str = f"{self.prev_d_percent:.2f}" if self.prev_d_percent is not None else "N/A"
        logger.debug(f"Stochastic: K={self.k_percent:.2f}, D={self.d_percent:.2f}, prev_K={prev_k_str}, prev_D={prev_d_str}, position={self.position}")
        
        # Log when we have enough data for strategy
        if len(self.price_history) == self.k_period + self.d_period:
            logger.info(f"Stochastic strategy now has enough data for full calculations: {len(self.price_history)} points")
        
        # Signal conditions
        if self.prev_k_percent is not None and self.prev_d_percent is not None:
            # %K crosses above %D (bullish signal)
            if (self.k_percent > self.d_percent and 
                self.prev_k_percent <= self.prev_d_percent and
                self.position == 0):
                
                self.signal_count += 1
                self.signals_by_type["k_cross_above_d"] += 1
                quantity = self.config.max_position_size / current_price
                logger.debug(f"K cross above D: K={self.k_percent:.2f}, D={self.d_percent:.2f}")
                return TradeSignal(
                    action="buy",
                    price=current_price,
                    quantity=quantity,
                    timestamp=timestamp,
                    reason=f"K cross above D: %K {self.k_percent:.2f} > %D {self.d_percent:.2f}"
                )
            
            # %K crosses below %D (bearish signal)
            elif (self.k_percent < self.d_percent and 
                  self.prev_k_percent >= self.prev_d_percent and
                  self.position > 0):
                
                self.signal_count += 1
                self.signals_by_type["k_cross_below_d"] += 1
                logger.debug(f"K cross below D: K={self.k_percent:.2f}, D={self.d_percent:.2f}")
                return TradeSignal(
                    action="sell",
                    price=current_price,
                    quantity=self.position,
                    timestamp=timestamp,
                    reason=f"K cross below D: %K {self.k_percent:.2f} < %D {self.d_percent:.2f}"
                )
            
            # %K crosses above oversold level
            elif (self.k_percent > self.oversold and 
                  self.prev_k_percent <= self.oversold and
                  self.position == 0):
                
                self.signal_count += 1
                self.signals_by_type["k_cross_oversold"] += 1
                quantity = self.config.max_position_size / current_price
                logger.debug(f"K cross oversold: K={self.k_percent:.2f}, oversold={self.oversold}")
                return TradeSignal(
                    action="buy",
                    price=current_price,
                    quantity=quantity,
                    timestamp=timestamp,
                    reason=f"K cross oversold: %K {self.k_percent:.2f} > {self.oversold} (oversold level)"
                )
            
            # %K crosses below overbought level
            elif (self.k_percent < self.overbought and 
                  self.prev_k_percent >= self.overbought and
                  self.position > 0):
                
                self.signal_count += 1
                self.signals_by_type["k_cross_overbought"] += 1
                logger.debug(f"K cross overbought: K={self.k_percent:.2f}, overbought={self.overbought}")
                return TradeSignal(
                    action="sell",
                    price=current_price,
                    quantity=self.position,
                    timestamp=timestamp,
                    reason=f"K cross overbought: %K {self.k_percent:.2f} < {self.overbought} (overbought level)"
                )
            
            # %D crosses above oversold level
            elif (self.d_percent > self.oversold and 
                  self.prev_d_percent <= self.oversold and
                  self.position == 0):
                
                self.signal_count += 1
                self.signals_by_type["d_cross_oversold"] += 1
                quantity = self.config.max_position_size / current_price
                logger.debug(f"D cross oversold: D={self.d_percent:.2f}, oversold={self.oversold}")
                return TradeSignal(
                    action="buy",
                    price=current_price,
                    quantity=quantity,
                    timestamp=timestamp,
                    reason=f"D cross oversold: %D {self.d_percent:.2f} > {self.oversold} (oversold level)"
                )
            
            # %D crosses below overbought level
            elif (self.d_percent < self.overbought and 
                  self.prev_d_percent >= self.overbought and
                  self.position > 0):
                
                self.signal_count += 1
                self.signals_by_type["d_cross_overbought"] += 1
                logger.debug(f"D cross overbought: D={self.d_percent:.2f}, overbought={self.overbought}")
                return TradeSignal(
                    action="sell",
                    price=current_price,
                    quantity=self.position,
                    timestamp=timestamp,
                    reason=f"D cross overbought: %D {self.d_percent:.2f} < {self.overbought} (overbought level)"
                )
            
            # Stochastic divergence signals (simplified)
            # Buy when both %K and %D are oversold and price is near recent low
            elif (self.k_percent < self.oversold + 10 and 
                  self.d_percent < self.oversold + 10 and
                  self.position == 0 and
                  current_price <= min([p["price"] for p in self.price_history[-5:]])):  # Price near recent low
                
                self.signal_count += 1
                self.signals_by_type["stochastic_divergence_buy"] += 1
                quantity = self.config.max_position_size / current_price
                logger.debug(f"Stochastic divergence buy: K={self.k_percent:.2f}, D={self.d_percent:.2f}, price={current_price:.2f}")
                return TradeSignal(
                    action="buy",
                    price=current_price,
                    quantity=quantity,
                    timestamp=timestamp,
                    reason=f"Stochastic divergence buy: Both %K {self.k_percent:.2f} and %D {self.d_percent:.2f} oversold, price near recent low"
                )
            
            # Sell when both %K and %D are overbought and price is near recent high
            elif (self.k_percent > self.overbought - 10 and 
                  self.d_percent > self.overbought - 10 and
                  self.position > 0 and
                  current_price >= max([p["price"] for p in self.price_history[-5:]])):  # Price near recent high
                
                self.signal_count += 1
                self.signals_by_type["stochastic_divergence_sell"] += 1
                logger.debug(f"Stochastic divergence sell: K={self.k_percent:.2f}, D={self.d_percent:.2f}, price={current_price:.2f}")
                return TradeSignal(
                    action="sell",
                    price=current_price,
                    quantity=self.position,
                    timestamp=timestamp,
                    reason=f"Stochastic divergence sell: Both %K {self.k_percent:.2f} and %D {self.d_percent:.2f} overbought, price near recent high"
                )
        
        # Count when we have enough data but no signal is generated
        if len(self.price_history) >= self.k_period + self.d_period:
            self.no_signal_count += 1
            
        return None
    
    def update_position(self, signal: TradeSignal) -> None:
        """Update position based on trade signal."""
        if signal.action == "buy":
            self.position = signal.quantity
            self.entry_price = signal.price
            logger.info(f"Position opened: {signal.quantity:.6f} at {signal.price}")
        elif signal.action == "sell":
            self.position = 0.0
            self.entry_price = 0.0
            logger.info(f"Position closed: {signal.quantity:.6f} at {signal.price}")
    
    def get_signal_stats(self) -> dict:
        """Get signal statistics."""
        return {
            "total_signals": self.signal_count,
            "signals_by_type": self.signals_by_type.copy(),
            "price_history_length": len(self.price_history),
            "no_signal_count": self.no_signal_count,
            "signal_rate": self.signal_count / max(len(self.price_history), 1) * 100
        }
    
    def get_position_info(self) -> Dict[str, Any]:
        """Get current position information."""
        return {
            "position": self.position,
            "entry_price": self.entry_price,
            "unrealized_pnl": (self.position * self.entry_price) if self.position > 0 else 0.0
        }


class DCAStrategy:
    """Dollar Cost Averaging strategy that makes regular fixed investments."""
    
    def __init__(self, config: TradingConfig, base_strategy=None):
        self.config = config
        self.base_strategy = base_strategy  # Optional underlying strategy
        self.dca_investments = []  # Track DCA investments
        self.last_dca_date = None
        self.dca_count = 0
        self.total_dca_amount = 0.0
        
        # Signal tracking
        self.signal_count = 0
        self.signals_by_type = {
            'dca_buy': 0,
            'dca_sell': 0,
            'strategy_buy': 0,
            'strategy_sell': 0,
            'stop_loss': 0,
            'take_profit': 0
        }
        self.no_signal_count = 0
        
    def add_price(self, price: float, timestamp: datetime) -> None:
        """Add a new price point to the history."""
        if self.base_strategy:
            self.base_strategy.add_price(price, timestamp)
    
    def should_dca_invest(self, current_date: datetime) -> bool:
        """Check if it's time for a DCA investment."""
        if not self.config.enable_dca:
            return False
            
        if self.dca_count >= self.config.dca_max_investments:
            return False
            
        if self.last_dca_date is None:
            # First DCA investment after start delay
            return True
            
        # Check if enough time has passed since last DCA
        days_since_last = (current_date - self.last_dca_date).days
        return days_since_last >= self.config.dca_frequency
    
    def generate_signal(self, current_price: float, timestamp: datetime, is_end_of_period: bool = False) -> Optional[TradeSignal]:
        """Generate trading signal based on DCA and optional base strategy."""
        signals = []
        
        # Check for DCA investment
        if self.should_dca_invest(timestamp):
            dca_signal = self._create_dca_signal(current_price, timestamp)
            if dca_signal:
                signals.append(dca_signal)
        
        # Check base strategy if available
        if self.base_strategy:
            base_signal = self.base_strategy.generate_signal(current_price, timestamp)
            if base_signal:
                # Modify signal to indicate it's from base strategy
                base_signal.reason = f"Strategy: {base_signal.reason}"
                signals.append(base_signal)
        
        # Return the first signal (DCA takes priority)
        if signals:
            signal = signals[0]
            self.signal_count += 1
            
            # Track signal type
            if 'DCA' in signal.reason:
                self.signals_by_type['dca_buy'] += 1
            elif 'Strategy' in signal.reason:
                if signal.action == 'buy':
                    self.signals_by_type['strategy_buy'] += 1
                else:
                    self.signals_by_type['strategy_sell'] += 1
            elif 'Stop loss' in signal.reason:
                self.signals_by_type['stop_loss'] += 1
            elif 'Take profit' in signal.reason:
                self.signals_by_type['take_profit'] += 1
                
            return signal
        
        self.no_signal_count += 1
        return None
    
    def _create_dca_signal(self, current_price: float, timestamp: datetime) -> TradeSignal:
        """Create a DCA buy signal."""
        # Calculate quantity based on fixed DCA amount
        quantity = self.config.dca_amount / current_price
        
        # Record DCA investment
        self.dca_investments.append({
            'date': timestamp,
            'price': current_price,
            'amount': self.config.dca_amount,
            'quantity': quantity
        })
        
        self.last_dca_date = timestamp
        self.dca_count += 1
        self.total_dca_amount += self.config.dca_amount
        
        logger.info(f"DCA Investment #{self.dca_count}: ${self.config.dca_amount} at ${current_price:.2f} = {quantity:.6f} units")
        
        return TradeSignal(
            action='buy',
            price=current_price,
            quantity=quantity,
            timestamp=timestamp,
            reason=f"DCA Investment #{self.dca_count}: ${self.config.dca_amount} at ${current_price:.2f}"
        )
    
    def update_position(self, signal: TradeSignal) -> None:
        """Update position based on trade signal."""
        if self.base_strategy:
            self.base_strategy.update_position(signal)
        else:
            # Simple position tracking for DCA-only mode
            if signal.action == 'buy':
                # In DCA mode, we accumulate position
                pass  # Position is tracked in dca_investments
            elif signal.action == 'sell':
                # In DCA mode, we might want to sell all
                pass
    
    def get_signal_stats(self) -> dict:
        """Get signal statistics."""
        base_stats = {}
        if self.base_strategy:
            base_stats = self.base_strategy.get_signal_stats()
        
        return {
            'total_signals': self.signal_count,
            'signals_by_type': self.signals_by_type.copy(),
            'dca_investments': len(self.dca_investments),
            'total_dca_amount': self.total_dca_amount,
            'dca_count': self.dca_count,
            'no_signal_count': self.no_signal_count,
            'signal_rate': self.signal_count / max(len(self.dca_investments), 1) * 100,
            'base_strategy_stats': base_stats,
            'price_history_length': len(self.dca_investments)  # DCA doesn't use price_history
        }
    
    def get_position_info(self) -> Dict[str, Any]:
        """Get current position information."""
        if self.base_strategy:
            return self.base_strategy.get_position_info()
        else:
            # Calculate position from DCA investments
            total_quantity = sum(inv['quantity'] for inv in self.dca_investments)
            avg_price = self.total_dca_amount / total_quantity if total_quantity > 0 else 0
            
            return {
                'position': total_quantity,
                'entry_price': avg_price,
                'unrealized_pnl': 0.0  # Would need current price to calculate
            }
    
    def get_dca_summary(self) -> Dict[str, Any]:
        """Get DCA investment summary."""
        if not self.dca_investments:
            return {
                'total_investments': 0,
                'total_amount': 0.0,
                'total_quantity': 0.0,
                'average_price': 0.0,
                'investments': []
            }
        
        total_quantity = sum(inv['quantity'] for inv in self.dca_investments)
        avg_price = self.total_dca_amount / total_quantity if total_quantity > 0 else 0
        
        return {
            'total_investments': len(self.dca_investments),
            'total_amount': self.total_dca_amount,
            'total_quantity': total_quantity,
            'average_price': avg_price,
            'investments': self.dca_investments
        }


class BuyAndHoldStrategy:
    """Buy and Hold strategy that holds positions indefinitely instead of using stop/loss."""
    
    def __init__(self, config: TradingConfig, base_strategy=None):
        self.config = config
        self.base_strategy = base_strategy  # Optional underlying strategy
        self.position = 0.0
        self.entry_price = 0.0
        self.total_invested = 0.0
        self.buy_signals = []  # Track all buy signals
        self.sell_signals = []  # Track any sell signals
        
        # Signal tracking
        self.signal_count = 0
        self.signals_by_type = {
            'buy_and_hold_buy': 0,
            'buy_and_hold_sell': 0,
            'strategy_buy': 0,
            'strategy_sell': 0,
            'profit_target_exit': 0,
            'end_of_period_exit': 0
        }
        self.no_signal_count = 0
        
    def add_price(self, price: float, timestamp: datetime) -> None:
        """Add a new price point to the history."""
        if self.base_strategy:
            self.base_strategy.add_price(price, timestamp)
    
    def should_exit_position(self, current_price: float, timestamp: datetime, is_end_of_period: bool = False) -> bool:
        """Check if position should be exited based on buy and hold rules."""
        if not self.config.enable_buy_hold:
            return False
            
        if self.position <= 0:
            return False
            
        # Check exit conditions
        if self.config.buy_hold_exit_condition == "end_of_period" and is_end_of_period:
            return True
        elif self.config.buy_hold_exit_condition == "profit_target" and self.config.buy_hold_profit_target > 0:
            profit_pct = ((current_price - self.entry_price) / self.entry_price) * 100
            if profit_pct >= self.config.buy_hold_profit_target:
                return True
                
        return False
    
    def generate_signal(self, current_price: float, timestamp: datetime, is_end_of_period: bool = False) -> Optional[TradeSignal]:
        """Generate trading signal based on buy and hold and optional base strategy."""
        signals = []
        
        # Check base strategy if available - pass through the exact same parameters
        # But skip base strategy calls when is_end_of_period=True in pure buy and hold mode
        # to prevent stop loss/take profit signals at the end of backtest
        if self.base_strategy and not (is_end_of_period and self.config.buy_hold_exit_condition == "never"):
            base_signal = self.base_strategy.generate_signal(current_price, timestamp, is_end_of_period)
            if base_signal:
                # In buy and hold mode, we only want to process buy signals from the base strategy
                # and ignore any sell signals (including stop loss, take profit, etc.)
                if base_signal.action == 'buy':
                    # Don't modify the signal - pass it through exactly as generated
                    signals.append(base_signal)
                # Ignore all sell signals from base strategy in buy and hold mode
                elif base_signal.action == 'sell':
                    logger.debug(f"Ignoring sell signal in buy and hold mode: {base_signal.reason}")
        
        # Only check for buy and hold exits if we have exit conditions configured
        # (i.e., not in pure buy and hold mode with "never" exit condition)
        if self.config.enable_buy_hold and self.config.buy_hold_exit_condition != "never":
            if self.should_exit_position(current_price, timestamp, is_end_of_period):
                exit_signal = self._create_exit_signal(current_price, timestamp, is_end_of_period)
                if exit_signal:
                    signals.append(exit_signal)
        
        # Return the first signal
        if signals:
            signal = signals[0]
            self.signal_count += 1
            
            # Track signal type
            if 'Buy and Hold' in signal.reason:
                if signal.action == 'buy':
                    self.signals_by_type['buy_and_hold_buy'] += 1
                else:
                    self.signals_by_type['buy_and_hold_sell'] += 1
            elif 'Profit Target' in signal.reason:
                self.signals_by_type['profit_target_exit'] += 1
            elif 'End of Period' in signal.reason:
                self.signals_by_type['end_of_period_exit'] += 1
            else:
                # This is a signal from the base strategy
                if signal.action == 'buy':
                    self.signals_by_type['strategy_buy'] += 1
                else:
                    self.signals_by_type['strategy_sell'] += 1
                
            return signal
        
        self.no_signal_count += 1
        return None
    
    def _create_exit_signal(self, current_price: float, timestamp: datetime, is_end_of_period: bool) -> TradeSignal:
        """Create a buy and hold exit signal."""
        if is_end_of_period:
            reason = f"Buy and Hold: End of Period Exit at ${current_price:.2f}"
        else:
            profit_pct = ((current_price - self.entry_price) / self.entry_price) * 100
            reason = f"Buy and Hold: Profit Target Exit at ${current_price:.2f} ({profit_pct:.1f}% profit)"
        
        logger.info(f"Buy and Hold Exit: {reason}")
        
        return TradeSignal(
            action='sell',
            price=current_price,
            quantity=self.position,
            timestamp=timestamp,
            reason=reason
        )
    
    def update_position(self, signal: TradeSignal) -> None:
        """Update position based on trade signal."""
        if signal.action == 'buy':
            # Accumulate position
            if self.position == 0:
                self.entry_price = signal.price
            else:
                # Calculate weighted average entry price
                total_value = (self.position * self.entry_price) + (signal.quantity * signal.price)
                self.position += signal.quantity
                self.entry_price = total_value / self.position
            
            self.total_invested += signal.quantity * signal.price
            self.buy_signals.append({
                'timestamp': signal.timestamp,
                'price': signal.price,
                'quantity': signal.quantity,
                'reason': signal.reason
            })
            
            logger.info(f"Buy and Hold: Bought {signal.quantity:.6f} at ${signal.price:.2f}, Total Position: {self.position:.6f}")
            
        elif signal.action == 'sell':
            # Exit entire position
            self.sell_signals.append({
                'timestamp': signal.timestamp,
                'price': signal.price,
                'quantity': self.position,
                'reason': signal.reason
            })
            
            logger.info(f"Buy and Hold: Sold {self.position:.6f} at ${signal.price:.2f}")
            self.position = 0.0
            self.entry_price = 0.0
    
    def get_signal_stats(self) -> dict:
        """Get signal statistics."""
        base_stats = {}
        if self.base_strategy:
            base_stats = self.base_strategy.get_signal_stats()
        
        # Use the base strategy's price_history_length if available, otherwise use buy_signals
        price_history_length = base_stats.get('price_history_length', len(self.buy_signals))
        
        return {
            'total_signals': self.signal_count,
            'signals_by_type': self.signals_by_type.copy(),
            'buy_signals': len(self.buy_signals),
            'sell_signals': len(self.sell_signals),
            'total_invested': self.total_invested,
            'no_signal_count': self.no_signal_count,
            'signal_rate': self.signal_count / max(price_history_length, 1) * 100,
            'base_strategy_stats': base_stats,
            'price_history_length': price_history_length
        }
    
    def get_position_info(self) -> Dict[str, Any]:
        """Get current position information."""
        if self.base_strategy:
            base_info = self.base_strategy.get_position_info()
            # Merge with buy and hold info
            return {
                'position': self.position,
                'entry_price': self.entry_price,
                'total_invested': self.total_invested,
                'unrealized_pnl': 0.0,  # Would need current price to calculate
                'base_strategy_info': base_info
            }
        else:
            return {
                'position': self.position,
                'entry_price': self.entry_price,
                'total_invested': self.total_invested,
                'unrealized_pnl': 0.0  # Would need current price to calculate
            }
    
    def get_buy_hold_summary(self) -> Dict[str, Any]:
        """Get buy and hold investment summary."""
        return {
            'total_buy_signals': len(self.buy_signals),
            'total_sell_signals': len(self.sell_signals),
            'total_invested': self.total_invested,
            'current_position': self.position,
            'average_entry_price': self.entry_price,
            'buy_signals': self.buy_signals,
            'sell_signals': self.sell_signals
        }


class ATRStrategy:
    """Average True Range (ATR) trading strategy based on volatility."""
    
    def __init__(self, config: TradingConfig, period: int = 14, atr_multiplier: float = 2.0, 
                 volatility_threshold: float = 1.5, position_size_atr: float = 0.02, enable_stop_loss: bool = True, enable_take_profit: bool = True):
        self.config = config
        self.period = period
        self.atr_multiplier = atr_multiplier  # Multiplier for ATR-based stop loss
        self.volatility_threshold = volatility_threshold  # ATR threshold for volatility breakout
        self.position_size_atr = position_size_atr  # Position size as % of ATR
        self.enable_stop_loss = enable_stop_loss
        self.enable_take_profit = enable_take_profit
        
        self.price_history: List[Dict[str, float]] = []  # Stores 'high', 'low', 'close'
        self.atr_values: List[float] = []
        self.current_atr = 0.0
        self.position = 0.0
        self.entry_price = 0.0
        self.atr_stop_loss = 0.0
        self.atr_take_profit = 0.0
        
        # Signal tracking
        self.signal_count = 0
        self.signals_by_type = {
            'atr_breakout_buy': 0,
            'atr_breakout_sell': 0,
            'atr_stop_loss': 0,
            'atr_take_profit': 0,
            'volatility_expansion': 0,
            'volatility_contraction': 0,
            'atr_position_size': 0,
            'stop_loss': 0,
            'take_profit': 0
        }
        self.no_signal_count = 0
        
    def add_price(self, price: float, timestamp: datetime) -> None:
        """Add a new price point to the history."""
        # For ATR, we need OHLC data, but we'll use price as close and estimate high/low
        if len(self.price_history) == 0:
            # First price point
            self.price_history.append({
                'high': price * 1.001,  # Estimate 0.1% high
                'low': price * 0.999,   # Estimate 0.1% low
                'close': price
            })
        else:
            # Use previous close as open, estimate high/low based on price movement
            prev_close = self.price_history[-1]['close']
            price_change = abs(price - prev_close) / prev_close
            
            if price > prev_close:
                high = max(price, prev_close * 1.001)
                low = min(prev_close * 0.999, price * 0.999)
            else:
                high = max(prev_close * 1.001, price * 1.001)
                low = min(price, prev_close * 0.999)
            
            self.price_history.append({
                'high': high,
                'low': low,
                'close': price
            })
        
        # Calculate ATR
        self._calculate_atr()
    
    def _calculate_atr(self) -> None:
        """Calculate Average True Range."""
        if len(self.price_history) < 2:
            return
        
        true_ranges = []
        
        for i in range(1, len(self.price_history)):
            current = self.price_history[i]
            previous = self.price_history[i-1]
            
            # True Range = max(high - low, |high - prev_close|, |low - prev_close|)
            tr1 = current['high'] - current['low']
            tr2 = abs(current['high'] - previous['close'])
            tr3 = abs(current['low'] - previous['close'])
            
            true_range = max(tr1, tr2, tr3)
            true_ranges.append(true_range)
        
        if len(true_ranges) >= self.period:
            # Calculate ATR as simple moving average of true ranges
            recent_trs = true_ranges[-self.period:]
            self.current_atr = sum(recent_trs) / len(recent_trs)
            self.atr_values.append(self.current_atr)
        elif len(true_ranges) > 0:
            # Use available true ranges for partial ATR
            self.current_atr = sum(true_ranges) / len(true_ranges)
            self.atr_values.append(self.current_atr)
    
    def _calculate_position_size(self, current_price: float) -> float:
        """Calculate position size based on ATR."""
        if self.current_atr == 0:
            return 0.0
        
        # Position size = (account_balance * position_size_atr) / (current_price * atr_multiplier * current_atr)
        # This ensures position size is inversely proportional to volatility
        account_balance = self.config.max_position_size
        position_value = account_balance * self.position_size_atr
        atr_value = self.current_atr * self.atr_multiplier
        
        if atr_value > 0:
            return position_value / (current_price * atr_value)
        return 0.0
    
    def generate_signal(self, current_price: float, timestamp: datetime, is_end_of_period: bool = False) -> Optional[TradeSignal]:
        """Generate trading signal based on ATR analysis."""
        if len(self.price_history) < self.period + 1:
            self.no_signal_count += 1
            return None
        
        signals = []
        
        # Check for volatility breakout
        if self._check_volatility_breakout(current_price):
            breakout_signal = self._create_breakout_signal(current_price, timestamp)
            if breakout_signal:
                signals.append(breakout_signal)
        
        # Check for ATR-based stop loss
        if self.position > 0 and self._check_atr_stop_loss(current_price):
            stop_signal = self._create_atr_stop_signal(current_price, timestamp)
            if stop_signal:
                signals.append(stop_signal)
        
        # Check for ATR-based take profit
        if self.position > 0 and self._check_atr_take_profit(current_price):
            profit_signal = self._create_atr_take_profit_signal(current_price, timestamp)
            if profit_signal:
                signals.append(profit_signal)
        
        # Return the first signal
        if signals:
            signal = signals[0]
            self.signal_count += 1
            
            # Track signal type
            if 'ATR Breakout' in signal.reason:
                if signal.action == 'buy':
                    self.signals_by_type['atr_breakout_buy'] += 1
                else:
                    self.signals_by_type['atr_breakout_sell'] += 1
            elif 'ATR Stop Loss' in signal.reason:
                self.signals_by_type['atr_stop_loss'] += 1
            elif 'ATR Take Profit' in signal.reason:
                self.signals_by_type['atr_take_profit'] += 1
            elif 'Volatility Expansion' in signal.reason:
                self.signals_by_type['volatility_expansion'] += 1
            elif 'Volatility Contraction' in signal.reason:
                self.signals_by_type['volatility_contraction'] += 1
            elif 'ATR Position Size' in signal.reason:
                self.signals_by_type['atr_position_size'] += 1
            elif 'Stop loss' in signal.reason:
                self.signals_by_type['stop_loss'] += 1
            elif 'Take profit' in signal.reason:
                self.signals_by_type['take_profit'] += 1
                
            return signal
        
        self.no_signal_count += 1
        return None
    
    def _check_volatility_breakout(self, current_price: float) -> bool:
        """Check for volatility breakout based on ATR."""
        if len(self.atr_values) < 2:
            return False
        
        # Check if current price movement exceeds ATR threshold
        prev_close = self.price_history[-2]['close']
        price_change = abs(current_price - prev_close)
        
        # Breakout if price change exceeds ATR * volatility_threshold
        return price_change > (self.current_atr * self.volatility_threshold)
    
    def _check_atr_stop_loss(self, current_price: float) -> bool:
        """Check if ATR-based stop loss should trigger."""
        if self.position <= 0 or self.atr_stop_loss == 0:
            return False
        
        if self.position > 0:  # Long position
            return current_price <= self.atr_stop_loss
        else:  # Short position
            return current_price >= self.atr_stop_loss
    
    def _check_atr_take_profit(self, current_price: float) -> bool:
        """Check if ATR-based take profit should trigger."""
        if self.position <= 0 or self.atr_take_profit == 0:
            return False
        
        if self.position > 0:  # Long position
            return current_price >= self.atr_take_profit
        else:  # Short position
            return current_price <= self.atr_take_profit
    
    def _create_breakout_signal(self, current_price: float, timestamp: datetime) -> TradeSignal:
        """Create volatility breakout signal."""
        prev_close = self.price_history[-2]['close']
        price_change = current_price - prev_close
        
        # Determine direction based on price movement
        if price_change > 0:
            action = 'buy'
            reason = f"ATR Breakout: Volatility expansion upward (ATR: {self.current_atr:.4f})"
        else:
            action = 'sell'
            reason = f"ATR Breakout: Volatility expansion downward (ATR: {self.current_atr:.4f})"
        
        # Calculate position size based on ATR
        quantity = self._calculate_position_size(current_price)
        
        return TradeSignal(
            action=action,
            price=current_price,
            quantity=quantity,
            timestamp=timestamp,
            reason=reason
        )
    
    def _create_atr_stop_signal(self, current_price: float, timestamp: datetime) -> TradeSignal:
        """Create ATR-based stop loss signal."""
        return TradeSignal(
            action='sell',
            price=current_price,
            quantity=abs(self.position),
            timestamp=timestamp,
            reason=f"ATR Stop Loss: Price {current_price:.2f} hit ATR stop at {self.atr_stop_loss:.2f}"
        )
    
    def _create_atr_take_profit_signal(self, current_price: float, timestamp: datetime) -> TradeSignal:
        """Create ATR-based take profit signal."""
        return TradeSignal(
            action='sell',
            price=current_price,
            quantity=abs(self.position),
            timestamp=timestamp,
            reason=f"ATR Take Profit: Price {current_price:.2f} hit ATR target at {self.atr_take_profit:.2f}"
        )
    
    def update_position(self, signal: TradeSignal) -> None:
        """Update position based on trade signal."""
        if signal.action == 'buy':
            self.position += signal.quantity
            if self.position > 0:
                self.entry_price = signal.price
                # Set ATR-based stop loss and take profit
                self.atr_stop_loss = signal.price - (self.current_atr * self.atr_multiplier)
                self.atr_take_profit = signal.price + (self.current_atr * self.atr_multiplier * 2)
                
                logger.info(f"ATR Strategy: Bought {signal.quantity:.6f} at ${signal.price:.2f}, "
                          f"ATR Stop: ${self.atr_stop_loss:.2f}, ATR Target: ${self.atr_take_profit:.2f}")
        elif signal.action == 'sell':
            self.position = 0.0
            self.entry_price = 0.0
            self.atr_stop_loss = 0.0
            self.atr_take_profit = 0.0
            
            logger.info(f"ATR Strategy: Sold position at ${signal.price:.2f}")
    
    def get_signal_stats(self) -> dict:
        """Get signal statistics."""
        return {
            'total_signals': self.signal_count,
            'signals_by_type': self.signals_by_type.copy(),
            'current_atr': self.current_atr,
            'atr_period': self.period,
            'atr_multiplier': self.atr_multiplier,
            'volatility_threshold': self.volatility_threshold,
            'no_signal_count': self.no_signal_count,
            'signal_rate': self.signal_count / max(len(self.price_history), 1) * 100,
            'price_history_length': len(self.price_history)
        }
    
    def get_position_info(self) -> Dict[str, Any]:
        """Get current position information."""
        return {
            "position": self.position,
            "entry_price": self.entry_price,
            "atr_stop_loss": self.atr_stop_loss,
            "atr_take_profit": self.atr_take_profit,
            "current_atr": self.current_atr,
            "unrealized_pnl": (self.position * (self.entry_price - self.entry_price)) if self.position > 0 else 0.0
        }
    
    def get_atr_summary(self) -> Dict[str, Any]:
        """Get ATR analysis summary."""
        if not self.atr_values:
            return {
                'current_atr': 0.0,
                'average_atr': 0.0,
                'max_atr': 0.0,
                'min_atr': 0.0,
                'atr_trend': 'neutral'
            }
        
        avg_atr = sum(self.atr_values) / len(self.atr_values)
        max_atr = max(self.atr_values)
        min_atr = min(self.atr_values)
        
        # Determine ATR trend
        if len(self.atr_values) >= 5:
            recent_avg = sum(self.atr_values[-5:]) / 5
            older_avg = sum(self.atr_values[-10:-5]) / 5 if len(self.atr_values) >= 10 else avg_atr
            if recent_avg > older_avg * 1.1:
                trend = 'increasing'
            elif recent_avg < older_avg * 0.9:
                trend = 'decreasing'
            else:
                trend = 'stable'
        else:
            trend = 'neutral'
        
        return {
            'current_atr': self.current_atr,
            'average_atr': avg_atr,
            'max_atr': max_atr,
            'min_atr': min_atr,
            'atr_trend': trend,
            'volatility_level': 'high' if self.current_atr > avg_atr * 1.2 else 'low' if self.current_atr < avg_atr * 0.8 else 'normal'
        }


class FibonacciRetracementStrategy:
    """Fibonacci retracement strategy for identifying support and resistance levels."""
    
    def __init__(self, config: TradingConfig, lookback_period: int = 50, fib_levels: list = None, 
                 confirmation_candles: int = 2, enable_stop_loss: bool = True, enable_take_profit: bool = True):
        self.config = config
        self.lookback_period = lookback_period
        self.fib_levels = fib_levels or [0.236, 0.382, 0.5, 0.618, 0.786]
        self.confirmation_candles = confirmation_candles
        self.enable_stop_loss = enable_stop_loss
        self.enable_take_profit = enable_take_profit
        
        self.price_history: list = []
        self.high_low_history: list = []
        self.position = 0.0
        self.entry_price = 0.0
        self.current_swing_high = 0.0
        self.current_swing_low = 0.0
        self.fib_levels_calculated = False
        self.support_levels = []
        self.resistance_levels = []
        
        # Signal tracking
        self.signal_count = 0
        self.signals_by_type = {
            'fib_support_buy': 0,
            'fib_resistance_sell': 0,
            'swing_high_buy': 0,
            'swing_low_sell': 0,
            'confirmation_buy': 0,
            'confirmation_sell': 0,
            'stop_loss': 0,
            'take_profit': 0
        }
        self.no_signal_count = 0
        
    def add_price(self, price: float, timestamp: datetime) -> None:
        """Add a new price point to the history."""
        self.price_history.append({
            'price': price,
            'timestamp': timestamp
        })
        
        # Keep only recent history
        if len(self.price_history) > self.lookback_period * 5000:
            self.price_history = self.price_history[-self.lookback_period * 5000:]
    
    def find_swing_points(self) -> tuple:
        """Find swing high and low points in the price history."""
        if len(self.price_history) < self.lookback_period:
            return None, None
        
        prices = [p['price'] for p in self.price_history[-self.lookback_period:]]
        timestamps = [p['timestamp'] for p in self.price_history[-self.lookback_period:]]
        
        # Find swing high (highest point)
        swing_high_idx = prices.index(max(prices))
        swing_high = prices[swing_high_idx]
        swing_high_time = timestamps[swing_high_idx]
        
        # Find swing low (lowest point)
        swing_low_idx = prices.index(min(prices))
        swing_low = prices[swing_low_idx]
        swing_low_time = timestamps[swing_low_idx]
        
        # Determine if we're in an uptrend or downtrend
        if swing_high_idx > swing_low_idx:
            # Uptrend: swing low came first, then swing high
            return swing_low, swing_high
        else:
            # Downtrend: swing high came first, then swing low
            return swing_high, swing_low
    
    def calculate_fibonacci_levels(self, swing_low: float, swing_high: float) -> tuple:
        """Calculate Fibonacci retracement levels."""
        if swing_low is None or swing_high is None:
            return [], []
        
        # Calculate the range
        price_range = abs(swing_high - swing_low)
        
        # Calculate Fibonacci levels
        if swing_high > swing_low:
            # Uptrend: calculate retracement levels from high to low
            support_levels = []
            resistance_levels = []
            
            for level in self.fib_levels:
                retracement_price = swing_high - (price_range * level)
                support_levels.append(retracement_price)
            
            # Add the original swing points
            support_levels.append(swing_low)
            resistance_levels.append(swing_high)
            
        else:
            # Downtrend: calculate retracement levels from low to high
            support_levels = []
            resistance_levels = []
            
            for level in self.fib_levels:
                retracement_price = swing_low + (price_range * level)
                resistance_levels.append(retracement_price)
            
            # Add the original swing points
            support_levels.append(swing_low)
            resistance_levels.append(swing_high)
        
        return sorted(support_levels), sorted(resistance_levels, reverse=True)
    
    def check_fibonacci_support(self, current_price: float) -> bool:
        """Check if current price is near a Fibonacci support level."""
        if not self.support_levels:
            return False
        
        for level in self.support_levels:
            # Check if price is within 1% of the support level
            if abs(current_price - level) / level <= 0.01:
                return True
        return False
    
    def check_fibonacci_resistance(self, current_price: float) -> bool:
        """Check if current price is near a Fibonacci resistance level."""
        if not self.resistance_levels:
            return False
        
        for level in self.resistance_levels:
            # Check if price is within 1% of the resistance level
            if abs(current_price - level) / level <= 0.01:
                return True
        return False
    
    def check_price_confirmation(self, current_price: float, signal_type: str) -> bool:
        """Check if price action confirms the Fibonacci level."""
        if len(self.price_history) < self.confirmation_candles:
            return False
        
        recent_prices = [p['price'] for p in self.price_history[-self.confirmation_candles:]]
        
        if signal_type == 'buy':
            # For buy signals, check if recent prices are showing upward momentum
            return all(recent_prices[i] >= recent_prices[i-1] for i in range(1, len(recent_prices)))
        elif signal_type == 'sell':
            # For sell signals, check if recent prices are showing downward momentum
            return all(recent_prices[i] <= recent_prices[i-1] for i in range(1, len(recent_prices)))
        
        return False
    
    def generate_signal(self, current_price: float, timestamp: datetime, is_end_of_period: bool = False) -> Optional[TradeSignal]:
        """Generate trading signal based on Fibonacci retracement levels."""
        if len(self.price_history) < self.lookback_period:
            return None
        
        # Find swing points and calculate Fibonacci levels
        swing_low, swing_high = self.find_swing_points()
        if swing_low is not None and swing_high is not None:
            self.support_levels, self.resistance_levels = self.calculate_fibonacci_levels(swing_low, swing_high)
            self.fib_levels_calculated = True
        
        if not self.fib_levels_calculated:
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
        
        # Generate Fibonacci-based signals
        if self.position == 0:  # No current position
            # Check for buy signal at Fibonacci support
            if self.check_fibonacci_support(current_price):
                if self.check_price_confirmation(current_price, 'buy'):
                    self.signal_count += 1
                    self.signals_by_type['fib_support_buy'] += 1
                    return TradeSignal(
                        action='buy',
                        price=current_price,
                        quantity=self.config.max_position_size,
                        timestamp=timestamp,
                        reason=f"Fibonacci support buy: Price {current_price:.2f} near support level"
                    )
            
            # Check for sell signal at Fibonacci resistance
            elif self.check_fibonacci_resistance(current_price):
                if self.check_price_confirmation(current_price, 'sell'):
                    self.signal_count += 1
                    self.signals_by_type['fib_resistance_sell'] += 1
                    return TradeSignal(
                        action='sell',
                        price=current_price,
                        quantity=self.config.max_position_size,
                        timestamp=timestamp,
                        reason=f"Fibonacci resistance sell: Price {current_price:.2f} near resistance level"
                    )
        
        self.no_signal_count += 1
        return None
    
    def update_position(self, signal: TradeSignal) -> None:
        """Update position based on trade signal."""
        if signal.action == 'buy':
            self.position += signal.quantity
            if self.position > 0:
                self.entry_price = signal.price
                logger.info(f"Fibonacci Strategy: Bought {signal.quantity:.6f} at ${signal.price:.2f}")
        elif signal.action == 'sell':
            self.position = 0.0
            self.entry_price = 0.0
            logger.info(f"Fibonacci Strategy: Sold position at ${signal.price:.2f}")
    
    def get_signal_stats(self) -> dict:
        """Get signal statistics."""
        return {
            'total_signals': self.signal_count,
            'signals_by_type': self.signals_by_type.copy(),
            'lookback_period': self.lookback_period,
            'fib_levels': self.fib_levels,
            'confirmation_candles': self.confirmation_candles,
            'no_signal_count': self.no_signal_count,
            'signal_rate': self.signal_count / max(len(self.price_history), 1) * 100,
            'price_history_length': len(self.price_history)
        }
    
    def get_position_info(self) -> Dict[str, Any]:
        """Get current position information."""
        return {
            "position": self.position,
            "entry_price": self.entry_price,
            "current_swing_high": self.current_swing_high,
            "current_swing_low": self.current_swing_low,
            "unrealized_pnl": (self.position * (self.entry_price - self.entry_price)) if self.position > 0 else 0.0
        }
    
    def get_fibonacci_summary(self) -> Dict[str, Any]:
        """Get Fibonacci analysis summary."""
        if not self.fib_levels_calculated:
            return {
                'swing_high': 0.0,
                'swing_low': 0.0,
                'support_levels': [],
                'resistance_levels': [],
                'current_price_level': 'unknown'
            }
        
        swing_low, swing_high = self.find_swing_points()
        current_price = self.price_history[-1]['price'] if self.price_history else 0.0
        
        # Determine which level the current price is closest to
        all_levels = self.support_levels + self.resistance_levels
        if all_levels:
            closest_level = min(all_levels, key=lambda x: abs(x - current_price))
            level_type = 'support' if closest_level in self.support_levels else 'resistance'
        else:
            level_type = 'unknown'
        
        return {
            'swing_high': swing_high or 0.0,
            'swing_low': swing_low or 0.0,
            'support_levels': self.support_levels,
            'resistance_levels': self.resistance_levels,
            'current_price_level': level_type,
            'closest_level': closest_level if all_levels else 0.0,
            'price_distance_from_level': abs(current_price - closest_level) if all_levels else 0.0
        }


class OrderBookStrategy:
    """Order book and trade history strategy using market microstructure analysis."""
    
    def __init__(self, config: TradingConfig, order_book_level: int = 2, trade_history_limit: int = 100,
                 bid_ask_spread_threshold: float = 0.001, volume_imbalance_threshold: float = 0.6,
                 large_trade_threshold: float = 10000.0, enable_stop_loss: bool = True, enable_take_profit: bool = True):
        self.config = config
        self.order_book_level = order_book_level
        self.trade_history_limit = trade_history_limit
        self.bid_ask_spread_threshold = bid_ask_spread_threshold
        self.volume_imbalance_threshold = volume_imbalance_threshold
        self.large_trade_threshold = large_trade_threshold
        self.enable_stop_loss = enable_stop_loss
        self.enable_take_profit = enable_take_profit
        
        self.price_history: list = []
        self.order_book_history: list = []
        self.trade_history: list = []
        self.position = 0.0
        self.entry_price = 0.0
        
        # Market microstructure metrics
        self.current_bid_ask_spread = 0.0
        self.current_volume_imbalance = 0.0
        self.current_mid_price = 0.0
        self.large_trade_count = 0
        self.buy_pressure = 0.0
        self.sell_pressure = 0.0
        
        # Signal tracking
        self.signal_count = 0
        self.signals_by_type = {
            'bid_ask_squeeze': 0,
            'volume_imbalance_buy': 0,
            'volume_imbalance_sell': 0,
            'large_trade_buy': 0,
            'large_trade_sell': 0,
            'order_book_pressure_buy': 0,
            'order_book_pressure_sell': 0,
            'spread_expansion_buy': 0,
            'spread_expansion_sell': 0,
            'stop_loss': 0,
            'take_profit': 0
        }
        self.no_signal_count = 0
        
    def add_price(self, price: float, timestamp: datetime) -> None:
        """Add a new price point to the history."""
        self.price_history.append({
            'price': price,
            'timestamp': timestamp
        })
        
        # Keep only recent history
        if len(self.price_history) > 1000:
            self.price_history = self.price_history[-1000:]
    
    def add_order_book(self, order_book: dict, timestamp: datetime) -> None:
        """Add order book data to history."""
        self.order_book_history.append({
            'order_book': order_book,
            'timestamp': timestamp
        })
        
        # Keep only recent history
        if len(self.order_book_history) > 100:
            self.order_book_history = self.order_book_history[-100:]
    
    def add_trades(self, trades: list, timestamp: datetime) -> None:
        """Add trade data to history."""
        for trade in trades:
            self.trade_history.append({
                'trade': trade,
                'timestamp': timestamp
            })
        
        # Keep only recent history
        if len(self.trade_history) > 1000:
            self.trade_history = self.trade_history[-1000:]
    
    def calculate_bid_ask_spread(self, order_book: dict) -> float:
        """Calculate bid-ask spread percentage."""
        if not order_book.get('bids') or not order_book.get('asks'):
            return 0.0
        
        best_bid = order_book['bids'][0]['price']
        best_ask = order_book['asks'][0]['price']
        
        if best_bid == 0 or best_ask == 0:
            return 0.0
        
        spread = (best_ask - best_bid) / best_bid
        return spread
    
    def calculate_volume_imbalance(self, order_book: dict, levels: int = 5) -> float:
        """Calculate volume imbalance between bids and asks."""
        if not order_book.get('bids') or not order_book.get('asks'):
            return 0.0
        
        bid_volume = sum(order['size'] for order in order_book['bids'][:levels])
        ask_volume = sum(order['size'] for order in order_book['asks'][:levels])
        
        if bid_volume + ask_volume == 0:
            return 0.0
        
        imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume)
        return imbalance
    
    def calculate_mid_price(self, order_book: dict) -> float:
        """Calculate mid price from order book."""
        if not order_book.get('bids') or not order_book.get('asks'):
            return 0.0
        
        best_bid = order_book['bids'][0]['price']
        best_ask = order_book['asks'][0]['price']
        
        return (best_bid + best_ask) / 2
    
    def analyze_trade_flow(self, trades: list) -> dict:
        """Analyze trade flow for buy/sell pressure."""
        if not trades:
            return {'buy_pressure': 0.0, 'sell_pressure': 0.0, 'large_trades': 0}
        
        buy_volume = 0.0
        sell_volume = 0.0
        large_trades = 0
        
        for trade_data in trades:
            trade = trade_data['trade']
            size = float(trade.get('size', 0))
            side = trade.get('side', '')
            price = float(trade.get('price', 0))
            
            trade_value = size * price
            
            if side == 'buy':
                buy_volume += trade_value
            elif side == 'sell':
                sell_volume += trade_value
            
            if trade_value >= self.large_trade_threshold:
                large_trades += 1
        
        total_volume = buy_volume + sell_volume
        if total_volume == 0:
            return {'buy_pressure': 0.0, 'sell_pressure': 0.0, 'large_trades': large_trades}
        
        buy_pressure = buy_volume / total_volume
        sell_pressure = sell_volume / total_volume
        
        return {
            'buy_pressure': buy_pressure,
            'sell_pressure': sell_pressure,
            'large_trades': large_trades
        }
    
    def detect_bid_ask_squeeze(self, current_spread: float, historical_spreads: list) -> bool:
        """Detect if bid-ask spread is unusually tight."""
        if len(historical_spreads) < 10:
            return False
        
        avg_spread = sum(historical_spreads) / len(historical_spreads)
        return current_spread < avg_spread * 0.5  # 50% below average
    
    def detect_spread_expansion(self, current_spread: float, historical_spreads: list) -> bool:
        """Detect if bid-ask spread is expanding significantly."""
        if len(historical_spreads) < 5:
            return False
        
        recent_avg = sum(historical_spreads[-5:]) / 5
        return current_spread > recent_avg * 1.5  # 50% above recent average
    
    def generate_signal(self, current_price: float, timestamp: datetime, is_end_of_period: bool = False) -> Optional[TradeSignal]:
        """Generate trading signal based on order book and trade analysis."""
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
        
        # Generate order book-based signals
        if self.position == 0:  # No current position
            # Check for bid-ask squeeze (potential breakout)
            if len(self.order_book_history) >= 10:
                current_order_book = self.order_book_history[-1]['order_book']
                current_spread = self.calculate_bid_ask_spread(current_order_book)
                historical_spreads = [self.calculate_bid_ask_spread(ob['order_book']) 
                                    for ob in self.order_book_history[-10:]]
                
                if self.detect_bid_ask_squeeze(current_spread, historical_spreads):
                    self.signal_count += 1
                    self.signals_by_type['bid_ask_squeeze'] += 1
                    return TradeSignal(
                        action='buy',
                        price=current_price,
                        quantity=self.config.max_position_size,
                        timestamp=timestamp,
                        reason=f"Bid-ask squeeze detected: spread {current_spread:.4f}"
                    )
            
            # Check for volume imbalance
            if len(self.order_book_history) >= 1:
                current_order_book = self.order_book_history[-1]['order_book']
                volume_imbalance = self.calculate_volume_imbalance(current_order_book)
                
                if volume_imbalance > self.volume_imbalance_threshold:
                    self.signal_count += 1
                    self.signals_by_type['volume_imbalance_buy'] += 1
                    return TradeSignal(
                        action='buy',
                        price=current_price,
                        quantity=self.config.max_position_size,
                        timestamp=timestamp,
                        reason=f"Volume imbalance buy: {volume_imbalance:.3f}"
                    )
                elif volume_imbalance < -self.volume_imbalance_threshold:
                    self.signal_count += 1
                    self.signals_by_type['volume_imbalance_sell'] += 1
                    return TradeSignal(
                        action='sell',
                        price=current_price,
                        quantity=self.config.max_position_size,
                        timestamp=timestamp,
                        reason=f"Volume imbalance sell: {volume_imbalance:.3f}"
                    )
            
            # Check for large trades
            if len(self.trade_history) >= 1:
                recent_trades = [t['trade'] for t in self.trade_history[-10:]]
                trade_analysis = self.analyze_trade_flow([{'trade': t} for t in recent_trades])
                
                if trade_analysis['large_trades'] > 0:
                    if trade_analysis['buy_pressure'] > 0.6:
                        self.signal_count += 1
                        self.signals_by_type['large_trade_buy'] += 1
                        return TradeSignal(
                            action='buy',
                            price=current_price,
                            quantity=self.config.max_position_size,
                            timestamp=timestamp,
                            reason=f"Large trade buy pressure: {trade_analysis['buy_pressure']:.3f}"
                        )
                    elif trade_analysis['sell_pressure'] > 0.6:
                        self.signal_count += 1
                        self.signals_by_type['large_trade_sell'] += 1
                        return TradeSignal(
                            action='sell',
                            price=current_price,
                            quantity=self.config.max_position_size,
                            timestamp=timestamp,
                            reason=f"Large trade sell pressure: {trade_analysis['sell_pressure']:.3f}"
                        )
        
        self.no_signal_count += 1
        return None
    
    def update_position(self, signal: TradeSignal) -> None:
        """Update position based on trade signal."""
        if signal.action == 'buy':
            self.position += signal.quantity
            if self.position > 0:
                self.entry_price = signal.price
                logger.info(f"OrderBook Strategy: Bought {signal.quantity:.6f} at ${signal.price:.2f}")
        elif signal.action == 'sell':
            self.position = 0.0
            self.entry_price = 0.0
            logger.info(f"OrderBook Strategy: Sold position at ${signal.price:.2f}")
    
    def get_signal_stats(self) -> dict:
        """Get signal statistics."""
        return {
            'total_signals': self.signal_count,
            'signals_by_type': self.signals_by_type.copy(),
            'order_book_level': self.order_book_level,
            'trade_history_limit': self.trade_history_limit,
            'bid_ask_spread_threshold': self.bid_ask_spread_threshold,
            'volume_imbalance_threshold': self.volume_imbalance_threshold,
            'large_trade_threshold': self.large_trade_threshold,
            'no_signal_count': self.no_signal_count,
            'signal_rate': self.signal_count / max(len(self.price_history), 1) * 100,
            'price_history_length': len(self.price_history)
        }
    
    def get_position_info(self) -> Dict[str, Any]:
        """Get current position information."""
        return {
            "position": self.position,
            "entry_price": self.entry_price,
            "current_bid_ask_spread": self.current_bid_ask_spread,
            "current_volume_imbalance": self.current_volume_imbalance,
            "current_mid_price": self.current_mid_price,
            "large_trade_count": self.large_trade_count,
            "unrealized_pnl": (self.position * (self.entry_price - self.entry_price)) if self.position > 0 else 0.0
        }
    
    def get_order_book_summary(self) -> Dict[str, Any]:
        """Get order book analysis summary."""
        if not self.order_book_history:
            return {
                'current_spread': 0.0,
                'current_imbalance': 0.0,
                'current_mid_price': 0.0,
                'spread_trend': 'unknown',
                'imbalance_trend': 'unknown',
                'order_book_depth': 0
            }
        
        current_order_book = self.order_book_history[-1]['order_book']
        current_spread = self.calculate_bid_ask_spread(current_order_book)
        current_imbalance = self.calculate_volume_imbalance(current_order_book)
        current_mid_price = self.calculate_mid_price(current_order_book)
        
        # Calculate trends
        if len(self.order_book_history) >= 5:
            recent_spreads = [self.calculate_bid_ask_spread(ob['order_book']) 
                            for ob in self.order_book_history[-5:]]
            recent_imbalances = [self.calculate_volume_imbalance(ob['order_book']) 
                               for ob in self.order_book_history[-5:]]
            
            spread_trend = 'increasing' if recent_spreads[-1] > recent_spreads[0] else 'decreasing'
            imbalance_trend = 'increasing' if recent_imbalances[-1] > recent_imbalances[0] else 'decreasing'
        else:
            spread_trend = 'unknown'
            imbalance_trend = 'unknown'
        
        return {
            'current_spread': current_spread,
            'current_imbalance': current_imbalance,
            'current_mid_price': current_mid_price,
            'spread_trend': spread_trend,
            'imbalance_trend': imbalance_trend,
            'order_book_depth': len(current_order_book.get('bids', [])) + len(current_order_book.get('asks', [])),
            'best_bid': current_order_book['bids'][0]['price'] if current_order_book.get('bids') else 0.0,
            'best_ask': current_order_book['asks'][0]['price'] if current_order_book.get('asks') else 0.0
        }
