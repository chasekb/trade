from typing import List
"""Portfolio management for simulated trading."""

from dataclasses import dataclass
from typing import Dict, List, Any
from datetime import datetime

from .position import Position
from .trade import Trade


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
    
    def get_position_count(self) -> int:
        """Get number of open positions."""
        return len([p for p in self.positions.values() if p.is_open()])
    
    def get_total_positions_value(self) -> float:
        """Get total value of all positions."""
        return sum(pos.get_position_value() for pos in self.positions.values() if pos.is_open())
    
    def get_unrealized_pnl(self) -> float:
        """Get total unrealized PnL from open positions."""
        return sum(pos.unrealized_pnl for pos in self.positions.values() if pos.is_open())
    
    def get_realized_pnl(self) -> float:
        """Get total realized PnL from closed positions."""
        return sum(pos.realized_pnl for pos in self.positions.values() if pos.is_closed())
    
    def get_net_pnl(self) -> float:
        """Get net PnL (realized + unrealized - fees)."""
        return self.total_pnl - self.total_fees
    
    def get_return_percentage(self, initial_balance: float) -> float:
        """Get total return percentage."""
        if initial_balance == 0:
            return 0.0
        return ((self.total_value - initial_balance) / initial_balance) * 100
    
    def get_win_rate_percentage(self) -> float:
        """Get win rate as percentage."""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100
    
    def get_average_win(self) -> float:
        """Get average win amount."""
        winning_trades = [t for t in self.trades if t.is_profitable()]
        if not winning_trades:
            return 0.0
        return sum(t.pnl for t in winning_trades) / len(winning_trades)
    
    def get_average_loss(self) -> float:
        """Get average loss amount."""
        losing_trades = [t for t in self.trades if not t.is_profitable() and t.pnl != 0]
        if not losing_trades:
            return 0.0
        return sum(t.pnl for t in losing_trades) / len(losing_trades)
    
    def get_largest_win(self) -> float:
        """Get largest win amount."""
        winning_trades = [t for t in self.trades if t.is_profitable()]
        if not winning_trades:
            return 0.0
        return max(t.pnl for t in winning_trades)
    
    def get_largest_loss(self) -> float:
        """Get largest loss amount."""
        losing_trades = [t for t in self.trades if not t.is_profitable() and t.pnl != 0]
        if not losing_trades:
            return 0.0
        return min(t.pnl for t in losing_trades)
    
    def get_profit_factor(self) -> float:
        """Get profit factor (gross profit / gross loss)."""
        gross_profit = sum(t.pnl for t in self.trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in self.trades if t.pnl < 0))
        
        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0
        
        return gross_profit / gross_loss
    
    def get_trades_by_symbol(self, symbol: str) -> List[Trade]:
        """Get trades for a specific symbol."""
        return [t for t in self.trades if t.symbol == symbol]
    
    def get_positions_by_symbol(self, symbol: str) -> List[Position]:
        """Get positions for a specific symbol."""
        return [p for p in self.positions.values() if p.symbol == symbol]
    
    def get_recent_trades(self, limit: int = 10) -> List[Trade]:
        """Get most recent trades."""
        return sorted(self.trades, key=lambda t: t.timestamp, reverse=True)[:limit]
    
    def get_open_positions(self) -> List[Position]:
        """Get all open positions."""
        return [p for p in self.positions.values() if p.is_open()]
    
    def get_closed_positions(self) -> List[Position]:
        """Get all closed positions."""
        return [p for p in self.positions.values() if p.is_closed()]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert portfolio to dictionary."""
        return {
            'cash_balance': self.cash_balance,
            'total_value': self.total_value,
            'total_positions_value': self.get_total_positions_value(),
            'unrealized_pnl': self.get_unrealized_pnl(),
            'realized_pnl': self.get_realized_pnl(),
            'net_pnl': self.get_net_pnl(),
            'total_fees': self.total_fees,
            'max_drawdown': self.max_drawdown,
            'win_rate': self.get_win_rate_percentage(),
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.total_trades - self.winning_trades,
            'position_count': self.get_position_count(),
            'average_win': self.get_average_win(),
            'average_loss': self.get_average_loss(),
            'largest_win': self.get_largest_win(),
            'largest_loss': self.get_largest_loss(),
            'profit_factor': self.get_profit_factor(),
            'positions': [pos.to_dict() for pos in self.positions.values()],
            'recent_trades': [trade.to_dict() for trade in self.get_recent_trades()]
        }
    
    def get_summary(self) -> str:
        """Get a summary string of the portfolio."""
        return f"""
Portfolio Summary:
=================
Cash Balance: ${self.cash_balance:.2f}
Total Value: ${self.total_value:.2f}
Net PnL: ${self.get_net_pnl():.2f}
Total Trades: {self.total_trades}
Win Rate: {self.get_win_rate_percentage():.1f}%
Max Drawdown: {self.max_drawdown:.2f}%
Open Positions: {self.get_position_count()}
        """.strip()
