"""Buy and Hold trading strategy."""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base import BaseStrategy, TradeSignal
from ..config import TradingConfig

logger = logging.getLogger(__name__)


class BuyAndHoldStrategy(BaseStrategy):
    """Buy and Hold trading strategy."""
    
    def __init__(self, config: TradingConfig, initial_investment: float = 1000.0, 
                 enable_stop_loss: bool = False, enable_take_profit: bool = True):
        super().__init__(config)
        self.initial_investment = initial_investment
        self.enable_stop_loss = enable_stop_loss
        self.enable_take_profit = enable_take_profit
        
        # Buy and Hold state
        self.has_bought = False
        self.buy_price = 0.0
        self.buy_quantity = 0.0
        self.buy_timestamp = None
        
        # Initialize signal tracking
        self.signals_by_type = {
            'initial_buy': 0,
            'take_profit': 0,
            'stop_loss': 0
        }
        
    def add_price(self, price: float, timestamp: datetime) -> None:
        """Add a new price point to the history."""
        self.price_history.append(price)
        
        # Keep only recent data to avoid memory issues
        if len(self.price_history) > 1000:
            self.price_history = self.price_history[-1000:]
    
    def calculate_initial_quantity(self, price: float) -> float:
        """Calculate how many units to buy with initial investment."""
        if price <= 0:
            return 0.0
        
        return self.initial_investment / price
    
    def generate_signal(self, current_price: float, timestamp: datetime, is_end_of_period: bool = False) -> Optional[TradeSignal]:
        """Generate trading signal based on Buy and Hold strategy."""
        if len(self.price_history) < 1:
            return None
        
        # Initial buy if we haven't bought yet
        if not self.has_bought:
            quantity = self.calculate_initial_quantity(current_price)
            
            if quantity > 0:
                self.has_bought = True
                self.buy_price = current_price
                self.buy_quantity = quantity
                self.buy_timestamp = timestamp
                
                self.signals_by_type['initial_buy'] += 1
                return TradeSignal(
                    action='buy',
                    price=current_price,
                    quantity=quantity,
                    reason=f'Buy and Hold initial purchase: ${self.initial_investment} at ${current_price:.2f}',
                    timestamp=timestamp
                )
        
        # Check for take profit if enabled
        if self.enable_take_profit and self.has_bought:
            profit_percentage = ((current_price - self.buy_price) / self.buy_price) * 100
            
            # Take profit at 50% gain (configurable)
            if profit_percentage >= 50.0:
                self.signals_by_type['take_profit'] += 1
                return TradeSignal(
                    action='sell',
                    price=current_price,
                    quantity=self.buy_quantity,
                    reason=f'Buy and Hold take profit: {profit_percentage:.1f}% gain',
                    timestamp=timestamp
                )
        
        # Check for stop loss if enabled
        if self.enable_stop_loss and self.has_bought:
            loss_percentage = ((self.buy_price - current_price) / self.buy_price) * 100
            
            # Stop loss at 20% loss (configurable)
            if loss_percentage >= 20.0:
                self.signals_by_type['stop_loss'] += 1
                return TradeSignal(
                    action='sell',
                    price=current_price,
                    quantity=self.buy_quantity,
                    reason=f'Buy and Hold stop loss: {loss_percentage:.1f}% loss',
                    timestamp=timestamp
                )
        
        return None
    
    def get_strategy_name(self) -> str:
        """Get the name of this strategy."""
        return "Buy and Hold"
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Get strategy information and statistics."""
        current_value = self.buy_quantity * (self.price_history[-1] if self.price_history else 0) if self.has_bought else 0
        total_return = current_value - self.initial_investment if self.has_bought else 0
        return_percentage = (total_return / self.initial_investment * 100) if self.initial_investment > 0 else 0
        
        return {
            'strategy_name': 'Buy and Hold',
            'parameters': {
                'initial_investment': self.initial_investment,
                'enable_stop_loss': self.enable_stop_loss,
                'enable_take_profit': self.enable_take_profit
            },
            'current_values': {
                'has_bought': self.has_bought,
                'buy_price': self.buy_price,
                'buy_quantity': self.buy_quantity,
                'current_value': current_value,
                'total_return': total_return,
                'return_percentage': return_percentage
            },
            'signals_by_type': self.signals_by_type.copy(),
            'total_signals': sum(self.signals_by_type.values()),
            'no_signal_count': self.no_signal_count
        }
