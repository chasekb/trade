"""ATR (Average True Range) trading strategy."""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base import BaseStrategy, TradeSignal
from ..config import TradingConfig

logger = logging.getLogger(__name__)


class ATRStrategy(BaseStrategy):
    """ATR (Average True Range) trading strategy."""
    
    def __init__(self, config: TradingConfig, period: int = 14, atr_multiplier: float = 2.0, 
                 enable_stop_loss: bool = True, enable_take_profit: bool = True):
        super().__init__(config)
        self.period = period
        self.atr_multiplier = atr_multiplier
        self.enable_stop_loss = enable_stop_loss
        self.enable_take_profit = enable_take_profit
        
        # ATR values
        self.atr = None
        self.true_ranges = []
        self.high_prices = []
        self.low_prices = []
        self.close_prices = []
        
        # Position tracking
        self.entry_price = None
        self.stop_loss_price = None
        self.take_profit_price = None
        
        # Initialize signal tracking
        self.signals_by_type = {
            'atr_breakout_buy': 0,
            'atr_breakout_sell': 0,
            'atr_stop_loss': 0,
            'atr_take_profit': 0,
            'volatility_expansion': 0,
            'volatility_contraction': 0
        }
        
    def add_price(self, price: float, timestamp: datetime) -> None:
        """Add a new price point to the history."""
        self.price_history.append(price)
        
        # Keep only recent data to avoid memory issues
        if len(self.price_history) > self.period * 5000:
            self.price_history = self.price_history[-self.period * 5000:]
    
    def add_ohlc(self, high: float, low: float, close: float) -> None:
        """Add OHLC data for ATR calculation."""
        self.high_prices.append(high)
        self.low_prices.append(low)
        self.close_prices.append(close)
        
        # Keep only recent data
        if len(self.high_prices) > self.period * 5000:
            self.high_prices = self.high_prices[-self.period * 5000:]
            self.low_prices = self.low_prices[-self.period * 5000:]
            self.close_prices = self.close_prices[-self.period * 5000:]
    
    def calculate_true_range(self, high: float, low: float, prev_close: float) -> float:
        """Calculate true range for a single period."""
        tr1 = high - low
        tr2 = abs(high - prev_close)
        tr3 = abs(low - prev_close)
        
        return max(tr1, tr2, tr3)
    
    def calculate_atr(self) -> Optional[float]:
        """Calculate Average True Range."""
        if len(self.high_prices) < self.period or len(self.low_prices) < self.period or len(self.close_prices) < self.period:
            return None
        
        # Calculate true ranges
        true_ranges = []
        for i in range(1, len(self.high_prices)):
            tr = self.calculate_true_range(
                self.high_prices[i],
                self.low_prices[i],
                self.close_prices[i-1]
            )
            true_ranges.append(tr)
        
        if len(true_ranges) < self.period:
            return None
        
        # Calculate ATR as simple moving average of true ranges
        recent_trs = true_ranges[-self.period:]
        atr = sum(recent_trs) / len(recent_trs)
        
        return atr
    
    def calculate_stop_loss_and_take_profit(self, entry_price: float, atr_value: float) -> tuple:
        """Calculate stop loss and take profit levels based on ATR."""
        atr_distance = atr_value * self.atr_multiplier
        
        stop_loss = entry_price - atr_distance
        take_profit = entry_price + atr_distance
        
        return stop_loss, take_profit
    
    def generate_signal(self, current_price: float, timestamp: datetime, is_end_of_period: bool = False) -> Optional[TradeSignal]:
        """Generate trading signal based on ATR strategy."""
        if len(self.price_history) < self.period:
            return None
        
        # Calculate ATR
        atr_value = self.calculate_atr()
        if atr_value is None:
            return None
        
        self.atr = atr_value
        
        # Check for volatility expansion/contraction
        if len(self.true_ranges) > 0:
            avg_tr = sum(self.true_ranges[-10:]) / min(10, len(self.true_ranges))
            if atr_value > avg_tr * 1.2:
                self.signals_by_type['volatility_expansion'] += 1
            elif atr_value < avg_tr * 0.8:
                self.signals_by_type['volatility_contraction'] += 1
        
        # If we have a position, check for stop loss or take profit
        if self.entry_price is not None:
            if self.enable_stop_loss and current_price <= self.stop_loss_price:
                self.signals_by_type['atr_stop_loss'] += 1
                return TradeSignal(
                    action='sell',
                    price=current_price,
                    quantity=self.calculate_position_size(current_price),
                    reason=f'ATR stop loss triggered at ${current_price:.2f} (ATR: {atr_value:.4f})',
                    timestamp=timestamp
                )
            
            if self.enable_take_profit and current_price >= self.take_profit_price:
                self.signals_by_type['atr_take_profit'] += 1
                return TradeSignal(
                    action='sell',
                    price=current_price,
                    quantity=self.calculate_position_size(current_price),
                    reason=f'ATR take profit triggered at ${current_price:.2f} (ATR: {atr_value:.4f})',
                    timestamp=timestamp
                )
        
        # Look for breakout signals
        if self.entry_price is None:
            # Simple breakout strategy: buy on price increase above ATR threshold
            if len(self.price_history) >= 2:
                price_change = current_price - self.price_history[-2]
                if price_change > atr_value * 0.5:  # Price increased by half ATR
                    self.entry_price = current_price
                    stop_loss, take_profit = self.calculate_stop_loss_and_take_profit(current_price, atr_value)
                    self.stop_loss_price = stop_loss
                    self.take_profit_price = take_profit
                    
                    self.signals_by_type['atr_breakout_buy'] += 1
                    return TradeSignal(
                        action='buy',
                        price=current_price,
                        quantity=self.calculate_position_size(current_price),
                        reason=f'ATR breakout buy at ${current_price:.2f} (ATR: {atr_value:.4f})',
                        timestamp=timestamp
                    )
        
        return None
    
    def get_strategy_name(self) -> str:
        """Get the name of this strategy."""
        return "ATR"
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Get strategy information and statistics."""
        return {
            'strategy_name': 'ATR',
            'parameters': {
                'period': self.period,
                'atr_multiplier': self.atr_multiplier,
                'enable_stop_loss': self.enable_stop_loss,
                'enable_take_profit': self.enable_take_profit
            },
            'current_values': {
                'atr': self.atr,
                'entry_price': self.entry_price,
                'stop_loss_price': self.stop_loss_price,
                'take_profit_price': self.take_profit_price
            },
            'signals_by_type': self.signals_by_type.copy(),
            'total_signals': sum(self.signals_by_type.values()),
            'no_signal_count': self.no_signal_count
        }
