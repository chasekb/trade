"""Position management for simulated trading."""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from .position import Position

logger = logging.getLogger(__name__)


class PositionManager:
    """Manages trading positions."""
    
    def __init__(self, max_positions: int = 5):
        self.max_positions = max_positions
        self.positions: Dict[str, Position] = {}
        self.logger = logging.getLogger(__name__)
    
    def can_open_position(self, symbol: str) -> bool:
        """Check if we can open a new position for a symbol.
        
        Args:
            symbol: Symbol to check
            
        Returns:
            True if position can be opened
        """
        # Check if we already have a position for this symbol
        if symbol in self.positions and self.positions[symbol].is_open():
            return False
        
        # Check if we've reached max positions
        open_positions = len([p for p in self.positions.values() if p.is_open()])
        return open_positions < self.max_positions
    
    def open_position(self, symbol: str, side: str, quantity: float, 
                     entry_price: float, entry_time: datetime) -> Optional[Position]:
        """Open a new position.
        
        Args:
            symbol: Symbol to trade
            side: 'long' or 'short'
            quantity: Position size
            entry_price: Entry price
            entry_time: Entry time
            
        Returns:
            Position object if successful, None otherwise
        """
        if not self.can_open_position(symbol):
            self.logger.warning(f"Cannot open position for {symbol}: max positions reached or position already exists")
            return None
        
        position = Position(
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            entry_time=entry_time,
            current_price=entry_price,
            unrealized_pnl=0.0
        )
        
        self.positions[symbol] = position
        self.logger.info(f"Opened {side} position for {symbol}: {quantity} at ${entry_price:.2f}")
        
        return position
    
    def close_position(self, symbol: str, exit_price: float, exit_time: datetime, 
                      reason: str = "Manual close") -> Optional[float]:
        """Close an existing position.
        
        Args:
            symbol: Symbol to close
            exit_price: Exit price
            exit_time: Exit time
            reason: Reason for closing
            
        Returns:
            Realized PnL if successful, None otherwise
        """
        if symbol not in self.positions:
            self.logger.warning(f"No position found for {symbol}")
            return None
        
        position = self.positions[symbol]
        if not position.is_open():
            self.logger.warning(f"Position for {symbol} is already closed")
            return None
        
        realized_pnl = position.close_position(exit_price, exit_time)
        self.logger.info(f"Closed position for {symbol}: PnL ${realized_pnl:.2f}, reason: {reason}")
        
        return realized_pnl
    
    def update_position_price(self, symbol: str, new_price: float) -> bool:
        """Update position price.
        
        Args:
            symbol: Symbol to update
            new_price: New price
            
        Returns:
            True if successful, False otherwise
        """
        if symbol not in self.positions:
            return False
        
        position = self.positions[symbol]
        if position.is_open():
            position.update_price(new_price)
            return True
        
        return False
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a symbol.
        
        Args:
            symbol: Symbol to get position for
            
        Returns:
            Position object or None
        """
        return self.positions.get(symbol)
    
    def get_open_positions(self) -> List[Position]:
        """Get all open positions."""
        return [p for p in self.positions.values() if p.is_open()]
    
    def get_closed_positions(self) -> List[Position]:
        """Get all closed positions."""
        return [p for p in self.positions.values() if p.is_closed()]
    
    def get_positions_by_symbol(self, symbol: str) -> List[Position]:
        """Get all positions for a symbol."""
        return [p for p in self.positions.values() if p.symbol == symbol]
    
    def get_position_count(self) -> int:
        """Get number of open positions."""
        return len(self.get_open_positions())
    
    def get_total_unrealized_pnl(self) -> float:
        """Get total unrealized PnL from all open positions."""
        return sum(pos.unrealized_pnl for pos in self.get_open_positions())
    
    def get_total_realized_pnl(self) -> float:
        """Get total realized PnL from all closed positions."""
        return sum(pos.realized_pnl for pos in self.get_closed_positions())
    
    def get_total_pnl(self) -> float:
        """Get total PnL (realized + unrealized)."""
        return self.get_total_realized_pnl() + self.get_total_unrealized_pnl()
    
    def get_positions_summary(self) -> Dict[str, Any]:
        """Get summary of all positions."""
        open_positions = self.get_open_positions()
        closed_positions = self.get_closed_positions()
        
        return {
            'total_positions': len(self.positions),
            'open_positions': len(open_positions),
            'closed_positions': len(closed_positions),
            'max_positions': self.max_positions,
            'can_open_new': self.get_position_count() < self.max_positions,
            'total_unrealized_pnl': self.get_total_unrealized_pnl(),
            'total_realized_pnl': self.get_total_realized_pnl(),
            'total_pnl': self.get_total_pnl(),
            'positions': [pos.to_dict() for pos in self.positions.values()]
        }
    
    def remove_closed_positions(self) -> int:
        """Remove closed positions to free up memory.
        
        Returns:
            Number of positions removed
        """
        closed_positions = self.get_closed_positions()
        removed_count = 0
        
        for position in closed_positions:
            if position.is_closed():
                del self.positions[position.symbol]
                removed_count += 1
        
        self.logger.info(f"Removed {removed_count} closed positions")
        return removed_count
    
    def clear_all_positions(self) -> None:
        """Clear all positions."""
        self.positions.clear()
        self.logger.info("Cleared all positions")
    
    def get_symbols_with_positions(self) -> List[str]:
        """Get list of symbols that have positions."""
        return list(self.positions.keys())
    
    def has_position(self, symbol: str) -> bool:
        """Check if we have a position for a symbol."""
        return symbol in self.positions
    
    def has_open_position(self, symbol: str) -> bool:
        """Check if we have an open position for a symbol."""
        return symbol in self.positions and self.positions[symbol].is_open()
