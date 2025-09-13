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
    
    def __init__(self, config: TradingConfig, short_window: int = 10, long_window: int = 30):
        self.config = config
        self.short_window = short_window
        self.long_window = long_window
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
        
        # Check stop loss first (highest priority)
        if self.position > 0:
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
        
        # Check take profit second
        if self.position > 0:
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
    
    def __init__(self, config: TradingConfig, period: int = 20, std_dev: float = 2.0):
        self.config = config
        self.period = period
        self.std_dev = std_dev
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
        if len(self.price_history) > self.period * 3:
            self.price_history = self.price_history[-self.period * 2:]
    
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
    
    def generate_signal(self, current_price: float, timestamp: datetime) -> Optional[TradeSignal]:
        """Generate trading signal based on Bollinger Bands."""
        if len(self.price_history) < self.period:
            return None
        
        # Check stop loss first (highest priority)
        if self.position > 0:
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
        
        # Check take profit second
        if self.position > 0:
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
    
    def __init__(self, config: TradingConfig, period: int = 14, oversold: int = 30, overbought: int = 70):
        self.config = config
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
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
        if len(self.price_history) > self.period * 3:
            self.price_history = self.price_history[-self.period * 2:]
    
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
    
    def generate_signal(self, current_price: float, timestamp: datetime) -> Optional[TradeSignal]:
        """Generate trading signal based on RSI."""
        if len(self.price_history) < self.period + 1:
            return None
        
        # Check stop loss first (highest priority)
        if self.position > 0:
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
        
        # Check take profit second
        if self.position > 0:
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
    
    def __init__(self, config: TradingConfig, short_ema: int = 12, long_ema: int = 26, alpha: float = None):
        self.config = config
        self.short_ema = short_ema
        self.long_ema = long_ema
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
        
        # Keep only recent data to avoid memory issues
        if len(self.price_history) > self.long_ema * 3:
            self.price_history = self.price_history[-self.long_ema * 2:]
    
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
    
    def generate_signal(self, current_price: float, timestamp: datetime) -> Optional[TradeSignal]:
        """Generate trading signal based on EMA."""
        if len(self.price_history) < self.long_ema:
            return None
        
        # Check stop loss first (highest priority)
        if self.position > 0:
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
        
        # Check take profit second
        if self.position > 0:
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
    
    def __init__(self, config: TradingConfig, fast_ema: int = 12, slow_ema: int = 26, signal_ema: int = 9):
        self.config = config
        self.fast_ema = fast_ema
        self.slow_ema = slow_ema
        self.signal_ema = signal_ema
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
        if len(self.price_history) > self.slow_ema * 3:
            self.price_history = self.price_history[-self.slow_ema * 2:]
    
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
    
    def generate_signal(self, current_price: float, timestamp: datetime) -> Optional[TradeSignal]:
        """Generate trading signal based on MACD."""
        if len(self.price_history) < self.slow_ema + self.signal_ema - 1:
            return None
        
        # Check stop loss first (highest priority)
        if self.position > 0:
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
        
        # Check take profit second
        if self.position > 0:
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
