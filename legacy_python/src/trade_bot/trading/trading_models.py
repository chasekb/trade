from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

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
    win_probability: Optional[float] = None
    expected_return: Optional[float] = None
    model_confidence: Optional[float] = None


@dataclass
class Portfolio:
    """Represents the trading portfolio."""
    cash_balance: float
    total_value: float
    positions: Dict[str, Position]
    trades: List[Trade]
    total_pnl: float
    total_fees: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    winning_trades: int
    # Added explicit fields for clarity and correct frontend calculations
    total_positions_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    net_pnl: float = 0.0
    position_count: int = 0
