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
    # Signal statistics
    total_signals: int = 0
    signals_by_type: dict = None
    signal_rate: float = 0.0
    no_signal_count: int = 0


class Backtester:
    """Backtesting engine for trading strategies."""
    
    def __init__(self, config: TradingConfig, strategy_class, strategy_params: Dict[str, Any] = None, portfolio_percentage: float = 100.0, initial_capital: float = None, enable_stop_loss: bool = True, enable_take_profit: bool = True, data_provider=None):
        """Initialize the backtester.
        
        Args:
            config: Trading configuration
            strategy_class: Strategy class to test
            strategy_params: Parameters for the strategy
            portfolio_percentage: Percentage of portfolio to use per trade (1-100%)
            initial_capital: Initial capital for backtesting (overrides config.max_position_size)
            enable_stop_loss: Whether to enable stop loss functionality
            enable_take_profit: Whether to enable take profit functionality
        """
        self.config = config
        self.strategy_class = strategy_class
        self.strategy_params = strategy_params or {}
        self.portfolio_percentage = max(1.0, min(100.0, portfolio_percentage))  # Clamp between 1-100%
        self.data_provider = data_provider
        self.enable_stop_loss = enable_stop_loss
        self.enable_take_profit = enable_take_profit
        self.logger = logging.getLogger(__name__)
        
        # Backtest state
        self.balance = initial_capital if initial_capital is not None else config.max_position_size
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
            # Calculate quantity based on available balance and portfolio percentage
            available_balance = self.balance * (self.portfolio_percentage / 100.0)
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
                        'side': 'buy',
                        'price': current_price,
                        'entry_price': current_price,
                        'exit_price': None,
                        'quantity': quantity,
                        'fees': fees,
                        'balance': self.balance,
                        'reason': signal.reason,
                        'signal': signal.reason,
                        'entry_time': timestamp,
                        'exit_time': None,
                        'profit_loss': None,
                        'pnl': None
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
            
            # Calculate P&L
            pnl = net_proceeds - (self.entry_price * self.position)
            
            # Record trade
            trade = {
                'timestamp': timestamp,
                'action': 'sell',
                'side': 'sell',
                'price': current_price,
                'entry_price': self.entry_price,
                'exit_price': current_price,
                'quantity': self.position,
                'fees': fees,
                'balance': self.balance,
                'reason': signal.reason,
                'signal': signal.reason,
                'entry_time': None,  # Will be filled from previous buy trade
                'exit_time': timestamp,
                'profit_loss': pnl,
                'pnl': pnl
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
    
    def _adjust_order_book_to_price(self, order_book: Dict[str, Any], target_price: float) -> Dict[str, Any]:
        """Adjust order book prices to match the target historical price."""
        if not order_book or not order_book.get('bids') or not order_book.get('asks'):
            return order_book
        
        # Calculate the current mid-price from the order book
        best_bid = float(order_book['bids'][0]['price'])
        best_ask = float(order_book['asks'][0]['price'])
        current_mid = (best_bid + best_ask) / 2
        
        # Calculate the adjustment factor
        if current_mid == 0:
            return order_book
        
        adjustment_factor = target_price / current_mid
        
        # Create adjusted order book
        adjusted_order_book = {
            'bids': [],
            'asks': [],
            'timestamp': order_book.get('timestamp'),
            'product_id': order_book.get('product_id')
        }
        
        # Adjust bids
        for bid in order_book['bids']:
            adjusted_price = float(bid['price']) * adjustment_factor
            adjusted_order_book['bids'].append({
                'price': round(adjusted_price, 2),
                'size': bid['size']
            })
        
        # Adjust asks
        for ask in order_book['asks']:
            adjusted_price = float(ask['price']) * adjustment_factor
            adjusted_order_book['asks'].append({
                'price': round(adjusted_price, 2),
                'size': ask['size']
            })
        
        return adjusted_order_book
    
    def _adjust_trades_to_price(self, trades: List[Dict[str, Any]], target_price: float) -> List[Dict[str, Any]]:
        """Adjust trade prices to match the target historical price."""
        if not trades:
            return trades
        
        # Calculate the current average price from trades
        total_value = 0
        total_size = 0
        for trade in trades:
            price = float(trade.get('price', 0))
            size = float(trade.get('size', 0))
            total_value += price * size
            total_size += size
        
        if total_size == 0:
            return trades
        
        current_avg_price = total_value / total_size
        
        # Calculate the adjustment factor
        if current_avg_price == 0:
            return trades
        
        adjustment_factor = target_price / current_avg_price
        
        # Create adjusted trades
        adjusted_trades = []
        for trade in trades:
            adjusted_price = float(trade.get('price', 0)) * adjustment_factor
            adjusted_trade = trade.copy()
            adjusted_trade['price'] = str(round(adjusted_price, 2))
            adjusted_trades.append(adjusted_trade)
        
        return adjusted_trades
    
    def _calculate_metrics(self, signal_stats: dict = None, final_price: float = None) -> BacktestResult:
        """Calculate backtest performance metrics."""
        # Calculate final balance including market value of held positions
        final_balance = self.balance
        if self.position > 0 and final_price is not None:
            # Add market value of held position to cash balance
            market_value = self.position * final_price
            final_balance += market_value
            self.logger.info(f"Final balance calculation: Cash=${self.balance:.2f} + Position Value=${market_value:.2f} (${self.position:.6f} @ ${final_price:.2f}) = ${final_balance:.2f}")
        else:
            self.logger.info(f"Final balance: ${final_balance:.2f} (no held positions)")
        
        if not self.trades:
            return BacktestResult(
                total_trades=0, winning_trades=0, losing_trades=0, win_rate=0.0,
                total_return=0.0, max_drawdown=0.0, sharpe_ratio=0.0, profit_factor=0.0,
                avg_win=0.0, avg_loss=0.0, largest_win=0.0, largest_loss=0.0,
                total_fees=self.fees_paid, net_profit=0.0,
                start_date=datetime.now(), end_date=datetime.now(),
                initial_balance=self.initial_balance, final_balance=final_balance,
                total_signals=signal_stats.get('total_signals', 0) if signal_stats else 0,
                signals_by_type=signal_stats.get('signals_by_type', {}) if signal_stats else {},
                signal_rate=signal_stats.get('signal_rate', 0.0) if signal_stats else 0.0,
                no_signal_count=signal_stats.get('no_signal_count', 0) if signal_stats else 0
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
                initial_balance=self.initial_balance, final_balance=final_balance,
                total_signals=signal_stats.get('total_signals', 0) if signal_stats else 0,
                signals_by_type=signal_stats.get('signals_by_type', {}) if signal_stats else {},
                signal_rate=signal_stats.get('signal_rate', 0.0) if signal_stats else 0.0,
                no_signal_count=signal_stats.get('no_signal_count', 0) if signal_stats else 0
            )
        
        # Calculate P&L for each trade
        trade_pnl = [t['profit_loss'] for t in completed_trades]
        winning_trades = [pnl for pnl in trade_pnl if pnl > 0]
        losing_trades = [pnl for pnl in trade_pnl if pnl < 0]
        
        winning_trade_count = len(winning_trades)
        losing_trade_count = len(losing_trades)
        win_rate = winning_trade_count / total_trades if total_trades > 0 else 0.0
        
        # Calculate returns using final balance (including market value of held positions)
        total_return = (final_balance - self.initial_balance) / self.initial_balance
        net_profit = final_balance - self.initial_balance
        
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
            final_balance=final_balance,
            total_signals=signal_stats.get('total_signals', 0) if signal_stats else 0,
            signals_by_type=signal_stats.get('signals_by_type', {}) if signal_stats else {},
            signal_rate=signal_stats.get('signal_rate', 0.0) if signal_stats else 0.0,
            no_signal_count=signal_stats.get('no_signal_count', 0) if signal_stats else 0
        )
    
    async def run_backtest(self, historical_data: List[Dict[str, Any]]) -> BacktestResult:
        """Run backtest on historical data.
        
        Args:
            historical_data: List of historical price data points
            
        Returns:
            BacktestResult with performance metrics
        """
        self.logger.info(f"Starting backtest with {len(historical_data)} data points")
        self.logger.info(f"Strategy parameters: {self.strategy_params}")
        
        # Log data sample for debugging
        if historical_data:
            self.logger.info(f"First data point: {historical_data[0]}")
            self.logger.info(f"Last data point: {historical_data[-1]}")
            if len(historical_data) > 1:
                time_diff = (datetime.fromisoformat(historical_data[1]['timestamp'].replace('Z', '+00:00')) - 
                           datetime.fromisoformat(historical_data[0]['timestamp'].replace('Z', '+00:00')))
                self.logger.info(f"Data frequency: {time_diff.total_seconds()} seconds between points")
                
                # Calculate expected vs actual data points
                start_time = datetime.fromisoformat(historical_data[0]['timestamp'].replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(historical_data[-1]['timestamp'].replace('Z', '+00:00'))
                total_seconds = (end_time - start_time).total_seconds()
                expected_points = int(total_seconds / time_diff.total_seconds()) + 1
                self.logger.info(f"Data coverage: {len(historical_data)} actual vs {expected_points} expected points")
        
        # Initialize strategy with enable flags
        strategy_params = self.strategy_params.copy()
        strategy_params['enable_stop_loss'] = self.enable_stop_loss
        strategy_params['enable_take_profit'] = self.enable_take_profit
        strategy = self.strategy_class(self.config, **strategy_params)
        
        # Track signals for debugging
        signal_count = 0
        
        # Process each data point
        for i, data_point in enumerate(historical_data):
            price = float(data_point['price'])
            timestamp = datetime.fromisoformat(data_point['timestamp'].replace('Z', '+00:00'))
            
            # Add price to strategy
            strategy.add_price(price, timestamp)
            
            # For OrderBookStrategy, we need to provide order book and trade data
            if hasattr(strategy, 'add_order_book') and hasattr(strategy, 'add_trades'):
                try:
                    # Get current order book data from Coinbase API for all historical points
                    # This uses current market data for backtesting (not ideal but functional)
                    order_book = await self.data_provider.get_order_book(level=2)
                    if order_book:
                        # Adjust order book prices to match historical price
                        adjusted_order_book = self._adjust_order_book_to_price(order_book, price)
                        strategy.add_order_book(adjusted_order_book, timestamp)
                    
                    # Get recent trades from Coinbase API
                    trades = await self.data_provider.get_recent_trades(limit=100)
                    if trades:
                        # Adjust trade prices to match historical price
                        adjusted_trades = self._adjust_trades_to_price(trades, price)
                        strategy.add_trades(adjusted_trades, timestamp)
                except Exception as e:
                    self.logger.warning(f"Failed to add order book/trade data: {e}")
            
            # Generate signal
            is_end_of_period = (i == len(historical_data) - 1)
            signal = strategy.generate_signal(price, timestamp, is_end_of_period)
            
            # Execute trade if signal exists
            if signal:
                signal_count += 1
                self.logger.info(f"Signal #{signal_count} generated: {signal.action} at ${price:.2f}, reason: {signal.reason}")
                if self._execute_trade(signal, price, timestamp):
                    # Update strategy position to keep it in sync
                    strategy.update_position(signal)
                    self.logger.info(f"Trade executed: {signal.action}, new position: {strategy.position}")
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
        
        # Get signal statistics from strategy
        signal_stats = strategy.get_signal_stats()
        
        # Get final price for calculating market value of held positions
        final_price = float(historical_data[-1]['price']) if historical_data else None
        
        # Calculate final metrics
        result = self._calculate_metrics(signal_stats, final_price)
        
        self.logger.info(f"Backtest completed: {signal_count} signals generated, {result.total_trades} trades executed, {result.win_rate:.1%} win rate, {result.total_return:.1%} return")
        self.logger.info(f"Signal breakdown: {signal_stats['signals_by_type']}")
        self.logger.info(f"Strategy processed {signal_stats['price_history_length']} price points")
        self.logger.info(f"No signal count: {signal_stats['no_signal_count']}, Signal rate: {signal_stats['signal_rate']:.2f}%")
        
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
        
        # Process trades to create proper trade pairs
        processed_trades = self._process_trade_pairs()
        
        df = pd.DataFrame(processed_trades)
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    
    def _process_trade_pairs(self) -> List[Dict[str, Any]]:
        """Process trades to create completed trade pairs with complete information."""
        completed_trades = []
        open_positions = []
        
        for trade in self.trades:
            if trade['action'] == 'buy':
                # Store as open position
                open_positions.append(trade)
                
            elif trade['action'] == 'sell' and open_positions:
                # Find the most recent open position to close
                buy_trade = open_positions.pop(0)  # FIFO - first in, first out
                
                # Create completed trade entry
                completed_trade = {
                    'timestamp': trade['timestamp'],  # Use sell timestamp as trade completion time
                    'action': 'completed',
                    'side': 'long',  # Assuming long positions for now
                    'entry_price': buy_trade['entry_price'],
                    'exit_price': trade['exit_price'],
                    'quantity': trade['quantity'],
                    'entry_time': buy_trade['entry_time'],
                    'exit_time': trade['exit_time'],
                    'profit_loss': trade['profit_loss'],
                    'pnl': trade['pnl'],
                    'fees': buy_trade['fees'] + trade['fees'],
                    'signal': trade['signal'],
                    'reason': trade['reason'],
                    'duration': (trade['exit_time'] - buy_trade['entry_time']).total_seconds() / 3600  # hours
                }
                completed_trades.append(completed_trade)
        
        return completed_trades
