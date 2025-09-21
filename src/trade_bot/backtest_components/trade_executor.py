"""Trade execution component for backtesting."""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from ..config import TradingConfig
from ..strategies import TradeSignal

logger = logging.getLogger(__name__)


class TradeExecutor:
    """Handles trade execution during backtesting."""
    
    def __init__(self, config: TradingConfig, portfolio_percentage: float = 100.0, 
                 initial_capital: float = None):
        self.config = config
        self.portfolio_percentage = max(1.0, min(100.0, portfolio_percentage))
        self.balance = initial_capital if initial_capital is not None else config.max_position_size
        self.initial_balance = self.balance
        self.position = 0.0
        self.entry_price = 0.0
        self.trades = []
        self.fees_paid = 0.0
        
        logger.info(f"TradeExecutor initialized with balance: ${self.balance:.2f}")
    
    def _calculate_fees(self, price: float, quantity: float) -> float:
        """Calculate trading fees."""
        return price * quantity * self.config.trading_fee_percentage
    
    def execute_trade(self, signal: TradeSignal, current_price: float, timestamp: datetime) -> bool:
        """Execute a trade based on the signal.
        
        Args:
            signal: Trading signal
            current_price: Current market price
            timestamp: Timestamp of the trade
            
        Returns:
            True if trade was executed, False otherwise
        """
        if signal.action == 'buy' and self.position == 0:
            # Calculate quantity based on available balance and portfolio percentage
            available_balance = self.balance * (self.portfolio_percentage / 100.0)
            quantity = available_balance / current_price
            
            # Calculate fees
            fees = self._calculate_fees(current_price, quantity)
            
            # Check if we have enough balance
            if available_balance >= (current_price * quantity + fees):
                self.position = quantity
                self.entry_price = current_price
                self.balance -= (current_price * quantity + fees)
                self.fees_paid += fees
                
                trade = {
                    'timestamp': timestamp,
                    'action': 'buy',
                    'price': current_price,
                    'quantity': quantity,
                    'fees': fees,
                    'balance_after': self.balance,
                    'reason': signal.reason
                }
                self.trades.append(trade)
                
                logger.info(f"BUY executed: {quantity:.6f} at ${current_price:.2f}, fees: ${fees:.2f}")
                return True
            else:
                logger.warning(f"Insufficient balance for buy order: need ${current_price * quantity + fees:.2f}, have ${available_balance:.2f}")
                return False
                
        elif signal.action == 'sell' and self.position > 0:
            # Calculate fees
            fees = self._calculate_fees(current_price, self.position)
            
            # Calculate proceeds
            proceeds = current_price * self.position - fees
            self.balance += proceeds
            self.fees_paid += fees
            
            # Calculate P&L
            pnl = proceeds - (self.entry_price * self.position)
            
            trade = {
                'timestamp': timestamp,
                'action': 'sell',
                'price': current_price,
                'quantity': self.position,
                'fees': fees,
                'balance_after': self.balance,
                'pnl': pnl,
                'reason': signal.reason
            }
            self.trades.append(trade)
            
            logger.info(f"SELL executed: {self.position:.6f} at ${current_price:.2f}, P&L: ${pnl:.2f}, fees: ${fees:.2f}")
            
            # Reset position
            self.position = 0.0
            self.entry_price = 0.0
            return True
        
        return False
    
    def get_current_balance(self) -> float:
        """Get current balance."""
        return self.balance
    
    def get_current_position(self) -> float:
        """Get current position size."""
        return self.position
    
    def get_entry_price(self) -> float:
        """Get entry price of current position."""
        return self.entry_price
    
    def get_total_fees(self) -> float:
        """Get total fees paid."""
        return self.fees_paid
    
    def get_trades(self) -> List[Dict[str, Any]]:
        """Get all executed trades."""
        return self.trades.copy()
    
    def get_trade_count(self) -> int:
        """Get number of trades executed."""
        return len(self.trades)
    
    def get_winning_trades(self) -> List[Dict[str, Any]]:
        """Get winning trades (positive P&L)."""
        return [trade for trade in self.trades if trade.get('pnl', 0) > 0]
    
    def get_losing_trades(self) -> List[Dict[str, Any]]:
        """Get losing trades (negative P&L)."""
        return [trade for trade in self.trades if trade.get('pnl', 0) < 0]
    
    def get_total_pnl(self) -> float:
        """Get total P&L from all trades."""
        return sum(trade.get('pnl', 0) for trade in self.trades)
    
    def get_net_profit(self) -> float:
        """Get net profit (P&L - fees)."""
        return self.get_total_pnl() - self.fees_paid
    
    def get_win_rate(self) -> float:
        """Get win rate percentage."""
        trades = self.trades
        if not trades:
            return 0.0
        
        winning_trades = len(self.get_winning_trades())
        return (winning_trades / len(trades)) * 100
    
    def get_average_win(self) -> float:
        """Get average win amount."""
        winning_trades = self.get_winning_trades()
        if not winning_trades:
            return 0.0
        
        return sum(trade.get('pnl', 0) for trade in winning_trades) / len(winning_trades)
    
    def get_average_loss(self) -> float:
        """Get average loss amount."""
        losing_trades = self.get_losing_trades()
        if not losing_trades:
            return 0.0
        
        return sum(trade.get('pnl', 0) for trade in losing_trades) / len(losing_trades)
    
    def get_largest_win(self) -> float:
        """Get largest win amount."""
        winning_trades = self.get_winning_trades()
        if not winning_trades:
            return 0.0
        
        return max(trade.get('pnl', 0) for trade in winning_trades)
    
    def get_largest_loss(self) -> float:
        """Get largest loss amount."""
        losing_trades = self.get_losing_trades()
        if not losing_trades:
            return 0.0
        
        return min(trade.get('pnl', 0) for trade in losing_trades)
    
    def get_profit_factor(self) -> float:
        """Get profit factor (gross profit / gross loss)."""
        winning_trades = self.get_winning_trades()
        losing_trades = self.get_losing_trades()
        
        if not losing_trades:
            return float('inf') if winning_trades else 0.0
        
        gross_profit = sum(trade.get('pnl', 0) for trade in winning_trades)
        gross_loss = abs(sum(trade.get('pnl', 0) for trade in losing_trades))
        
        return gross_profit / gross_loss if gross_loss > 0 else 0.0
