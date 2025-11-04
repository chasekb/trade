from typing import List
"""Base classes for trading strategies."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional, List

from ...core.config import TradingConfig

logger = logging.getLogger(__name__)


@dataclass
class TradeSignal:
    """Represents a trading signal."""
    action: str  # 'buy', 'sell', 'hold'
    price: float
    quantity: float
    timestamp: datetime
    reason: str


class BaseStrategy(ABC):
    """Base class for all trading strategies."""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.price_history: List[float] = []
        self.position = 0.0  # Current position size
        self.entry_price = 0.0
        
        # Signal tracking
        self.signal_count = 0
        self.signals_by_type: Dict[str, int] = {}
        self.no_signal_count = 0
        
    @abstractmethod
    def generate_signal(self, current_price: float, timestamp: datetime) -> Optional[TradeSignal]:
        """Generate a trading signal based on current price and timestamp."""
        pass
    
    @abstractmethod
    def get_strategy_name(self) -> str:
        """Get the name of this strategy."""
        pass
    
    def update_position(self, action: str, price: float, quantity: float) -> None:
        """Update the current position."""
        if action == 'buy':
            self.position += quantity
            if self.position > 0:
                self.entry_price = price
        elif action == 'sell':
            self.position -= quantity
            if self.position <= 0:
                self.entry_price = 0.0
                self.position = 0.0
    
    def get_position_info(self) -> Dict[str, Any]:
        """Get current position information."""
        return {
            'position': self.position,
            'entry_price': self.entry_price,
            'signal_count': self.signal_count,
            'signals_by_type': self.signals_by_type,
            'no_signal_count': self.no_signal_count
        }
    
    def reset_position(self) -> None:
        """Reset position and tracking variables."""
        self.position = 0.0
        self.entry_price = 0.0
        self.signal_count = 0
        self.signals_by_type = {}
        self.no_signal_count = 0
