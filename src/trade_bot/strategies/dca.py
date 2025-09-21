"""DCA (Dollar Cost Averaging) trading strategy."""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from .base import BaseStrategy, TradeSignal
from ..config import TradingConfig

logger = logging.getLogger(__name__)


class DCAStrategy(BaseStrategy):
    """DCA (Dollar Cost Averaging) trading strategy."""
    
    def __init__(self, config: TradingConfig, interval_hours: int = 24, 
                 amount_per_purchase: float = 100.0, enable_stop_loss: bool = False, 
                 enable_take_profit: bool = True):
        super().__init__(config)
        self.interval_hours = interval_hours
        self.amount_per_purchase = amount_per_purchase
        self.enable_stop_loss = enable_stop_loss
        self.enable_take_profit = enable_take_profit
        
        # DCA state
        self.last_purchase_time = None
        self.total_invested = 0.0
        self.total_units = 0.0
        self.average_price = 0.0
        
        # Initialize signal tracking
        self.signals_by_type = {
            'dca_buy': 0,
            'take_profit': 0,
            'stop_loss': 0
        }
        
    def add_price(self, price: float, timestamp: datetime) -> None:
        """Add a new price point to the history."""
        self.price_history.append(price)
        
        # Keep only recent data to avoid memory issues
        if len(self.price_history) > 1000:
            self.price_history = self.price_history[-1000:]
    
    def should_purchase(self, timestamp: datetime) -> bool:
        """Check if it's time for a DCA purchase."""
        if self.last_purchase_time is None:
            return True
        
        time_since_last = timestamp - self.last_purchase_time
        return time_since_last >= timedelta(hours=self.interval_hours)
    
    def calculate_units_to_buy(self, current_price: float) -> float:
        """Calculate how many units to buy with the fixed amount."""
        if current_price <= 0:
            return 0.0
        
        return self.amount_per_purchase / current_price
    
    def update_average_price(self, new_units: float, new_price: float) -> None:
        """Update the average price after a new purchase."""
        if self.total_units == 0:
            self.average_price = new_price
        else:
            # Calculate new average price
            total_value = (self.total_units * self.average_price) + (new_units * new_price)
            self.total_units += new_units
            self.average_price = total_value / self.total_units
        
        self.total_invested += self.amount_per_purchase
        self.total_units += new_units
    
    def generate_signal(self, current_price: float, timestamp: datetime, is_end_of_period: bool = False) -> Optional[TradeSignal]:
        """Generate trading signal based on DCA strategy."""
        if len(self.price_history) < 1:
            return None
        
        # Check if it's time for a DCA purchase
        if self.should_purchase(timestamp):
            units_to_buy = self.calculate_units_to_buy(current_price)
            
            if units_to_buy > 0:
                # Update average price
                self.update_average_price(units_to_buy, current_price)
                self.last_purchase_time = timestamp
                
                self.signals_by_type['dca_buy'] += 1
                return TradeSignal(
                    action='buy',
                    price=current_price,
                    quantity=units_to_buy,
                    reason=f'DCA purchase: ${self.amount_per_purchase} at ${current_price:.2f} (Avg: ${self.average_price:.2f})',
                    timestamp=timestamp
                )
        
        # Check for take profit if enabled
        if self.enable_take_profit and self.total_units > 0:
            profit_percentage = ((current_price - self.average_price) / self.average_price) * 100
            
            # Take profit at 20% gain
            if profit_percentage >= 20.0:
                self.signals_by_type['take_profit'] += 1
                return TradeSignal(
                    action='sell',
                    price=current_price,
                    quantity=self.total_units,
                    reason=f'DCA take profit: {profit_percentage:.1f}% gain (Avg: ${self.average_price:.2f})',
                    timestamp=timestamp
                )
        
        return None
    
    def get_strategy_name(self) -> str:
        """Get the name of this strategy."""
        return "DCA"
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Get strategy information and statistics."""
        current_value = self.total_units * (self.price_history[-1] if self.price_history else 0)
        total_return = current_value - self.total_invested if self.total_invested > 0 else 0
        return_percentage = (total_return / self.total_invested * 100) if self.total_invested > 0 else 0
        
        return {
            'strategy_name': 'DCA',
            'parameters': {
                'interval_hours': self.interval_hours,
                'amount_per_purchase': self.amount_per_purchase,
                'enable_stop_loss': self.enable_stop_loss,
                'enable_take_profit': self.enable_take_profit
            },
            'current_values': {
                'total_invested': self.total_invested,
                'total_units': self.total_units,
                'average_price': self.average_price,
                'current_value': current_value,
                'total_return': total_return,
                'return_percentage': return_percentage
            },
            'signals_by_type': self.signals_by_type.copy(),
            'total_signals': sum(self.signals_by_type.values()),
            'no_signal_count': self.no_signal_count
        }
