"""Backtesting module for trading strategies."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
from dataclasses import dataclass

from .config import TradingConfig
from .trading_strategy import SimpleMovingAverageStrategy, TradeSignal
from .data_handler import DataHandler


@dataclass
class BacktestResult:
    """Results from a backtest run."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_return: float
    max_drawdown: float
    sharpe_ratio: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    total_fees: float
    net_profit: float
    start_date: datetime
    end_date: datetime
    initial_balance: float
    final_balance: float


class Backtester:
    """Backtesting engine for trading strategies."""
    
    def __init__(self, config: TradingConfig, strategy_class, strategy_params: Dict[str, Any] = None):
        """Initialize the backtester.
        
        Args:
            config: Trading configuration
            strategy_class: Strategy class to test
            strategy_params: Parameters for the strategy
        """
        self.config = config
        self.strategy_class = strategy_class
        self.strategy_params = strategy_params or {}
        self.logger = logging.getLogger(__name__)
        
        # Backtest state
        self.balance = config.max_position_size
        self.initial_balance = self.balance
        self.position = 0.0
        self.entry_price = 0.0
        self.trades = []
        self.equity_curve = []
        self.fees_paid = 0.0
        
        # Performance tracking
        self.peak_balance = self.balance
        self.max_drawdown = 0.0
        
    def _calculate_fees(self, price: float, quantity: float) -> float:
        """Calculate trading fees."""
        return price * quantity * self.config.trading_fee_percentage
    
    def _execute_trade(self, signal: TradeSignal, current_price: float, timestamp: datetime) -> bool:
        """Execute a trade based on the signal.
        
        Args:
            signal: Trading signal
            current_price: Current market price
            timestamp: Timestamp of the trade
            
        Returns:
            True if trade was executed, False otherwise
        """
        if signal.action == 'buy' and self.position == 0:
            # Calculate quantity based on available balance
            available_balance = self.balance * 0.95  # Leave 5% buffer
            quantity = available_balance / current_price
            
            if quantity > 0.001:  # Minimum quantity threshold
                # Calculate fees
                fees = self._calculate_fees(current_price, quantity)
                
                # Check if we have enough balance (use full balance for the check)
                total_cost = (current_price * quantity) + fees
                if total_cost <= self.balance:
                    # Execute buy
                    self.position = quantity
                    self.entry_price = current_price
                    self.balance -= total_cost
                    self.fees_paid += fees
                    
                    # Record trade
                    trade = {
                        'timestamp': timestamp,
                        'action': 'buy',
                        'price': current_price,
                        'quantity': quantity,
                        'fees': fees,
                        'balance': self.balance,
                        'reason': signal.reason
                    }
                    self.trades.append(trade)
                    
                    self.logger.debug(f"BUY: {quantity:.6f} @ ${current_price:.2f}, Fees: ${fees:.2f}")
                    return True
                    
        elif signal.action == 'sell' and self.position > 0:
            # Execute sell
            proceeds = current_price * self.position
            fees = self._calculate_fees(current_price, self.position)
            net_proceeds = proceeds - fees
            
            self.balance += net_proceeds
            self.fees_paid += fees
            
            # Record trade
            trade = {
                'timestamp': timestamp,
                'action': 'sell',
                'price': current_price,
                'quantity': self.position,
                'fees': fees,
                'balance': self.balance,
                'reason': signal.reason,
                'profit_loss': net_proceeds - (self.entry_price * self.position)
            }
            self.trades.append(trade)
            
            self.logger.debug(f"SELL: {self.position:.6f} @ ${current_price:.2f}, P&L: ${trade['profit_loss']:.2f}")
            
            # Reset position
            self.position = 0.0
            self.entry_price = 0.0
            return True
            
        return False
    
    def _update_equity_curve(self, current_price: float, timestamp: datetime):
        """Update the equity curve with current portfolio value."""
        if self.position > 0:
            # Include unrealized P&L
            unrealized_pnl = (current_price - self.entry_price) * self.position
            current_value = self.balance + (current_price * self.position)
        else:
            current_value = self.balance
            
        self.equity_curve.append({
            'timestamp': timestamp,
            'balance': self.balance,
            'position': self.position,
            'position_value': self.position * current_price if self.position > 0 else 0,
            'total_value': current_value,
            'unrealized_pnl': (current_price - self.entry_price) * self.position if self.position > 0 else 0
        })
        
        # Update peak and drawdown
        if current_value > self.peak_balance:
            self.peak_balance = current_value
            
        current_drawdown = (self.peak_balance - current_value) / self.peak_balance
        if current_drawdown > self.max_drawdown:
            self.max_drawdown = current_drawdown
    
    def _calculate_metrics(self) -> BacktestResult:
        """Calculate backtest performance metrics."""
        if not self.trades:
            return BacktestResult(
                total_trades=0, winning_trades=0, losing_trades=0, win_rate=0.0,
                total_return=0.0, max_drawdown=0.0, sharpe_ratio=0.0, profit_factor=0.0,
                avg_win=0.0, avg_loss=0.0, largest_win=0.0, largest_loss=0.0,
                total_fees=self.fees_paid, net_profit=0.0,
                start_date=datetime.now(), end_date=datetime.now(),
                initial_balance=self.initial_balance, final_balance=self.balance
            )
        
        # Calculate trade statistics
        completed_trades = [t for t in self.trades if t['action'] == 'sell']
        total_trades = len(completed_trades)
        
        if total_trades == 0:
            return BacktestResult(
                total_trades=0, winning_trades=0, losing_trades=0, win_rate=0.0,
                total_return=0.0, max_drawdown=0.0, sharpe_ratio=0.0, profit_factor=0.0,
                avg_win=0.0, avg_loss=0.0, largest_win=0.0, largest_loss=0.0,
                total_fees=self.fees_paid, net_profit=0.0,
                start_date=datetime.now(), end_date=datetime.now(),
                initial_balance=self.initial_balance, final_balance=self.balance
            )
        
        # Calculate P&L for each trade
        trade_pnl = [t['profit_loss'] for t in completed_trades]
        winning_trades = [pnl for pnl in trade_pnl if pnl > 0]
        losing_trades = [pnl for pnl in trade_pnl if pnl < 0]
        
        winning_trade_count = len(winning_trades)
        losing_trade_count = len(losing_trades)
        win_rate = winning_trade_count / total_trades if total_trades > 0 else 0.0
        
        # Calculate returns
        total_return = (self.balance - self.initial_balance) / self.initial_balance
        net_profit = self.balance - self.initial_balance
        
        # Calculate average win/loss
        avg_win = np.mean(winning_trades) if winning_trades else 0.0
        avg_loss = np.mean(losing_trades) if losing_trades else 0.0
        
        # Calculate largest win/loss
        largest_win = max(winning_trades) if winning_trades else 0.0
        largest_loss = min(losing_trades) if losing_trades else 0.0
        
        # Calculate profit factor
        total_wins = sum(winning_trades) if winning_trades else 0.0
        total_losses = abs(sum(losing_trades)) if losing_trades else 0.0
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        # Calculate Sharpe ratio (simplified)
        if len(trade_pnl) > 1:
            sharpe_ratio = np.mean(trade_pnl) / np.std(trade_pnl) if np.std(trade_pnl) > 0 else 0.0
        else:
            sharpe_ratio = 0.0
        
        # Get date range
        start_date = min(t['timestamp'] for t in self.trades)
        end_date = max(t['timestamp'] for t in self.trades)
        
        return BacktestResult(
            total_trades=total_trades,
            winning_trades=winning_trade_count,
            losing_trades=losing_trade_count,
            win_rate=win_rate,
            total_return=total_return,
            max_drawdown=self.max_drawdown,
            sharpe_ratio=sharpe_ratio,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            total_fees=self.fees_paid,
            net_profit=net_profit,
            start_date=start_date,
            end_date=end_date,
            initial_balance=self.initial_balance,
            final_balance=self.balance
        )
    
    async def run_backtest(self, historical_data: List[Dict[str, Any]]) -> BacktestResult:
        """Run backtest on historical data.
        
        Args:
            historical_data: List of historical price data points
            
        Returns:
            BacktestResult with performance metrics
        """
        self.logger.info(f"Starting backtest with {len(historical_data)} data points")
        
        # Initialize strategy
        strategy = self.strategy_class(self.config, **self.strategy_params)
        
        # Process each data point
        for i, data_point in enumerate(historical_data):
            price = float(data_point['price'])
            timestamp = datetime.fromisoformat(data_point['timestamp'].replace('Z', '+00:00'))
            
            # Add price to strategy
            strategy.add_price(price, timestamp)
            
            # Generate signal
            signal = strategy.generate_signal(price, timestamp)
            
            # Execute trade if signal exists
            if signal:
                self.logger.debug(f"Signal generated: {signal.action} at ${price:.2f}, reason: {signal.reason}")
                if self._execute_trade(signal, price, timestamp):
                    # Update strategy position to keep it in sync
                    strategy.update_position(signal)
                    self.logger.debug(f"Trade executed: {signal.action}, new position: {strategy.position}")
                else:
                    self.logger.debug(f"Trade not executed: {signal.action} at ${price:.2f}")
            
            # Update equity curve
            self._update_equity_curve(price, timestamp)
            
            # Log progress
            if i % 1000 == 0:
                self.logger.info(f"Processed {i}/{len(historical_data)} data points")
        
        # Close any remaining position
        if self.position > 0:
            last_price = float(historical_data[-1]['price'])
            last_timestamp = datetime.fromisoformat(historical_data[-1]['timestamp'].replace('Z', '+00:00'))
            
            # Force close position
            signal = TradeSignal(
                action='sell',
                price=last_price,
                quantity=self.position,
                timestamp=last_timestamp,
                reason="Backtest end - force close"
            )
            self._execute_trade(signal, last_price, last_timestamp)
        
        # Calculate final metrics
        result = self._calculate_metrics()
        
        self.logger.info(f"Backtest completed: {result.total_trades} trades, {result.win_rate:.1%} win rate, {result.total_return:.1%} return")
        
        return result
    
    def get_equity_curve_df(self) -> pd.DataFrame:
        """Get equity curve as a pandas DataFrame."""
        if not self.equity_curve:
            return pd.DataFrame()
        
        df = pd.DataFrame(self.equity_curve)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        return df
    
    def get_trades_df(self) -> pd.DataFrame:
        """Get trades as a pandas DataFrame."""
        if not self.trades:
            return pd.DataFrame()
        
        df = pd.DataFrame(self.trades)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
