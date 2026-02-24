"""Position management for simulated trading."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any


@dataclass
class Position:
    """Represents a trading position."""
    symbol: str
    side: str  # 'long' or 'short'
    quantity: float
    entry_price: float
    entry_time: datetime
    current_price: float
    unrealized_pnl: float
    realized_pnl: float = 0.0
    status: str = 'open'  # 'open', 'closed'
    
    def update_price(self, new_price: float) -> None:
        """Update current price and calculate unrealized PnL."""
        self.current_price = new_price
        if self.side == 'long':
            self.unrealized_pnl = (new_price - self.entry_price) * self.quantity
        else:  # short
            self.unrealized_pnl = (self.entry_price - new_price) * self.quantity
    
    def close_position(self, exit_price: float, exit_time: datetime) -> float:
        """Close the position and calculate realized PnL.
        
        Args:
            exit_price: Price at which to close the position
            exit_time: Time when position is closed
            
        Returns:
            Realized PnL from closing the position
        """
        if self.side == 'long':
            realized_pnl = (exit_price - self.entry_price) * self.quantity
        else:  # short
            realized_pnl = (self.entry_price - exit_price) * self.quantity
        
        self.realized_pnl = realized_pnl
        self.status = 'closed'
        self.current_price = exit_price
        
        return realized_pnl
    
    def get_total_pnl(self) -> float:
        """Get total PnL (realized + unrealized)."""
        if self.status == 'closed':
            return self.realized_pnl
        else:
            return self.unrealized_pnl
    
    def get_position_value(self) -> float:
        """Get current position value."""
        return self.current_price * self.quantity
    
    def get_position_cost(self) -> float:
        """Get original position cost."""
        return self.entry_price * self.quantity
    
    def get_return_percentage(self) -> float:
        """Get return percentage."""
        if self.entry_price == 0:
            return 0.0
        
        if self.side == 'long':
            return ((self.current_price - self.entry_price) / self.entry_price) * 100
        else:  # short
            return ((self.entry_price - self.current_price) / self.entry_price) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert position to dictionary."""
        return {
            'symbol': self.symbol,
            'side': self.side,
            'quantity': self.quantity,
            'entry_price': self.entry_price,
            'entry_time': self.entry_time.isoformat(),
            'current_price': self.current_price,
            'unrealized_pnl': self.unrealized_pnl,
            'realized_pnl': self.realized_pnl,
            'status': self.status,
            'position_value': self.get_position_value(),
            'position_cost': self.get_position_cost(),
            'return_pct': self.get_return_percentage(),
            'total_pnl': self.get_total_pnl()
        }
    
    def is_profitable(self) -> bool:
        """Check if position is profitable."""
        return self.get_total_pnl() > 0
    
    def is_long(self) -> bool:
        """Check if position is long."""
        return self.side == 'long'
    
    def is_short(self) -> bool:
        """Check if position is short."""
        return self.side == 'short'
    
    def is_open(self) -> bool:
        """Check if position is open."""
        return self.status == 'open'
    
    def is_closed(self) -> bool:
        """Check if position is closed."""
        return self.status == 'closed'
