"""Trade representation for simulated trading."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any


@dataclass
class Trade:
    """Represents a completed trade."""
    trade_id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: float
    price: float
    timestamp: datetime
    reason: str
    pnl: float = 0.0
    fees: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert trade to dictionary."""
        return {
            'trade_id': self.trade_id,
            'symbol': self.symbol,
            'side': self.side,
            'quantity': self.quantity,
            'price': self.price,
            'timestamp': self.timestamp.isoformat(),
            'reason': self.reason,
            'pnl': self.pnl,
            'fees': self.fees,
            'value': self.price * self.quantity,
            'net_pnl': self.pnl - self.fees
        }
    
    def is_buy(self) -> bool:
        """Check if trade is a buy."""
        return self.side == 'buy'
    
    def is_sell(self) -> bool:
        """Check if trade is a sell."""
        return self.side == 'sell'
    
    def is_profitable(self) -> bool:
        """Check if trade is profitable."""
        return self.pnl > 0
    
    def get_net_pnl(self) -> float:
        """Get net PnL after fees."""
        return self.pnl - self.fees
    
    def get_value(self) -> float:
        """Get trade value."""
        return self.price * self.quantity
    
    def get_return_percentage(self, entry_price: float) -> float:
        """Get return percentage based on entry price.
        
        Args:
            entry_price: Price at which position was entered
            
        Returns:
            Return percentage
        """
        if entry_price == 0:
            return 0.0
        
        if self.is_buy():
            return ((self.price - entry_price) / entry_price) * 100
        else:  # sell
            return ((entry_price - self.price) / entry_price) * 100
