"""Trade execution for simulated trading."""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid

from .trade import Trade
from .position_manager import PositionManager

logger = logging.getLogger(__name__)


class SimulatedTradeExecutor:
    """Handles trade execution for simulated trading."""
    
    def __init__(self, trading_fee: float = 0.001, position_size_percent: float = 0.2):
        self.trading_fee = trading_fee
        self.position_size_percent = position_size_percent
        self.trades: List[Trade] = []
        self.position_manager = PositionManager()
        self.trade_counter = 0
        
        logger.info(f"SimulatedTradeExecutor initialized with fee: {trading_fee:.3f}, position size: {position_size_percent:.1%}")
    
    def calculate_position_size(self, symbol: str, price: float, available_balance: float) -> float:
        """Calculate position size based on available balance.
        
        Args:
            symbol: Symbol to trade
            price: Current price
            available_balance: Available cash balance
            
        Returns:
            Position size in units
        """
        if price <= 0 or available_balance <= 0:
            return 0.0
        
        position_value = available_balance * self.position_size_percent
        return position_value / price
    
    def calculate_fees(self, price: float, quantity: float) -> float:
        """Calculate trading fees.
        
        Args:
            price: Trade price
            quantity: Trade quantity
            
        Returns:
            Fee amount
        """
        return price * quantity * self.trading_fee
    
    def execute_buy(self, symbol: str, price: float, quantity: float, 
                   reason: str, timestamp: datetime = None) -> Optional[Trade]:
        """Execute a buy trade.
        
        Args:
            symbol: Symbol to buy
            price: Buy price
            quantity: Quantity to buy
            reason: Reason for the trade
            timestamp: Trade timestamp
            
        Returns:
            Trade object if successful, None otherwise
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        # Check if we can open a position
        if not self.position_manager.can_open_position(symbol):
            logger.warning(f"Cannot execute buy for {symbol}: position limit reached or position already exists")
            return None
        
        # Calculate fees
        fees = self.calculate_fees(price, quantity)
        
        # Create trade
        trade_id = f"buy_{symbol}_{self.trade_counter}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        trade = Trade(
            trade_id=trade_id,
            symbol=symbol,
            side='buy',
            quantity=quantity,
            price=price,
            timestamp=timestamp,
            reason=reason,
            fees=fees
        )
        
        # Open position
        position = self.position_manager.open_position(
            symbol=symbol,
            side='long',
            quantity=quantity,
            entry_price=price,
            entry_time=timestamp
        )
        
        if position:
            self.trades.append(trade)
            self.trade_counter += 1
            logger.info(f"Executed buy: {quantity} {symbol} at ${price:.2f}, fees: ${fees:.2f}")
            return trade
        else:
            logger.error(f"Failed to open position for buy trade: {symbol}")
            return None
    
    def execute_sell(self, symbol: str, price: float, quantity: float, 
                    reason: str, timestamp: datetime = None) -> Optional[Trade]:
        """Execute a sell trade.
        
        Args:
            symbol: Symbol to sell
            price: Sell price
            quantity: Quantity to sell
            reason: Reason for the trade
            timestamp: Trade timestamp
            
        Returns:
            Trade object if successful, None otherwise
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        # Check if we have an open position
        if not self.position_manager.has_open_position(symbol):
            logger.warning(f"Cannot execute sell for {symbol}: no open position")
            return None
        
        position = self.position_manager.get_position(symbol)
        if not position:
            logger.error(f"Position not found for {symbol}")
            return None
        
        # Calculate fees
        fees = self.calculate_fees(price, quantity)
        
        # Calculate PnL
        pnl = (price - position.entry_price) * quantity
        
        # Create trade
        trade_id = f"sell_{symbol}_{self.trade_counter}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        trade = Trade(
            trade_id=trade_id,
            symbol=symbol,
            side='sell',
            quantity=quantity,
            price=price,
            timestamp=timestamp,
            reason=reason,
            pnl=pnl,
            fees=fees
        )
        
        # Close position
        realized_pnl = self.position_manager.close_position(symbol, price, timestamp, reason)
        
        if realized_pnl is not None:
            self.trades.append(trade)
            self.trade_counter += 1
            logger.info(f"Executed sell: {quantity} {symbol} at ${price:.2f}, PnL: ${pnl:.2f}, fees: ${fees:.2f}")
            return trade
        else:
            logger.error(f"Failed to close position for sell trade: {symbol}")
            return None
    
    def get_trades(self) -> List[Trade]:
        """Get all trades."""
        return self.trades.copy()
    
    def get_trades_by_symbol(self, symbol: str) -> List[Trade]:
        """Get trades for a specific symbol."""
        return [t for t in self.trades if t.symbol == symbol]
    
    def get_recent_trades(self, limit: int = 10) -> List[Trade]:
        """Get most recent trades."""
        return sorted(self.trades, key=lambda t: t.timestamp, reverse=True)[:limit]
    
    def get_winning_trades(self) -> List[Trade]:
        """Get winning trades."""
        return [t for t in self.trades if t.is_profitable()]
    
    def get_losing_trades(self) -> List[Trade]:
        """Get losing trades."""
        return [t for t in self.trades if not t.is_profitable() and t.pnl != 0]
    
    def get_total_trades(self) -> int:
        """Get total number of trades."""
        return len(self.trades)
    
    def get_total_fees(self) -> float:
        """Get total fees paid."""
        return sum(t.fees for t in self.trades)
    
    def get_total_pnl(self) -> float:
        """Get total PnL from all trades."""
        return sum(t.pnl for t in self.trades)
    
    def get_net_pnl(self) -> float:
        """Get net PnL (total PnL - fees)."""
        return self.get_total_pnl() - self.get_total_fees()
    
    def get_win_rate(self) -> float:
        """Get win rate percentage."""
        if not self.trades:
            return 0.0
        
        winning_trades = len(self.get_winning_trades())
        return (winning_trades / len(self.trades)) * 100
    
    def get_average_win(self) -> float:
        """Get average win amount."""
        winning_trades = self.get_winning_trades()
        if not winning_trades:
            return 0.0
        
        return sum(t.pnl for t in winning_trades) / len(winning_trades)
    
    def get_average_loss(self) -> float:
        """Get average loss amount."""
        losing_trades = self.get_losing_trades()
        if not losing_trades:
            return 0.0
        
        return sum(t.pnl for t in losing_trades) / len(losing_trades)
    
    def get_profit_factor(self) -> float:
        """Get profit factor."""
        gross_profit = sum(t.pnl for t in self.trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in self.trades if t.pnl < 0))
        
        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0
        
        return gross_profit / gross_loss
    
    def get_trade_stats(self) -> Dict[str, Any]:
        """Get comprehensive trade statistics."""
        return {
            'total_trades': self.get_total_trades(),
            'winning_trades': len(self.get_winning_trades()),
            'losing_trades': len(self.get_losing_trades()),
            'win_rate': self.get_win_rate(),
            'total_pnl': self.get_total_pnl(),
            'net_pnl': self.get_net_pnl(),
            'total_fees': self.get_total_fees(),
            'average_win': self.get_average_win(),
            'average_loss': self.get_average_loss(),
            'profit_factor': self.get_profit_factor(),
            'open_positions': self.position_manager.get_position_count(),
            'total_unrealized_pnl': self.position_manager.get_total_unrealized_pnl()
        }
    
    def clear_trades(self) -> None:
        """Clear all trades."""
        self.trades.clear()
        self.trade_counter = 0
        logger.info("Cleared all trades")
