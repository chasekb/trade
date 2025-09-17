"""
Tests for SimulatedTradingManager.

This module contains comprehensive tests for the simulated trading manager,
including position tracking, trade execution, portfolio management, and signal processing.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import sys
import os

# Add the src directory to the path so we can import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from trade_bot.simulated_trading_manager import SimulatedTradingManager, Position, Trade, Portfolio


class TestSimulatedTradingManager:
    """Test cases for SimulatedTradingManager."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.manager = SimulatedTradingManager(
            initial_balance=10000.0,
            max_positions=3,
            position_size_percent=20.0,
            trading_fee=0.001
        )
    
    def test_initialization(self):
        """Test SimulatedTradingManager initialization."""
        assert self.manager.initial_balance == 10000.0
        assert self.manager.cash_balance == 10000.0
        assert self.manager.max_positions == 3
        assert self.manager.position_size_percent == 0.2
        assert self.manager.trading_fee == 0.001
        assert not self.manager.is_trading
        assert self.manager.symbols_to_trade == []
        assert len(self.manager.positions) == 0
        assert len(self.manager.trades) == 0
    
    def test_start_trading(self):
        """Test starting simulated trading."""
        symbols = ['BTC-USD', 'ETH-USD', 'ADA-USD']
        self.manager.start_trading(symbols)
        
        assert self.manager.is_trading
        assert self.manager.symbols_to_trade == symbols
        assert self.manager.last_signal_check is not None
    
    def test_stop_trading(self):
        """Test stopping simulated trading."""
        # Start trading first
        self.manager.start_trading(['BTC-USD'])
        self.manager.is_trading = True
        
        # Add a mock position
        position = Position(
            symbol='BTC-USD',
            side='long',
            quantity=0.1,
            entry_price=50000.0,
            entry_time=datetime.now(),
            current_price=51000.0,
            unrealized_pnl=100.0
        )
        self.manager.positions['BTC-USD'] = position
        
        # Stop trading
        self.manager.stop_trading()
        
        assert not self.manager.is_trading
        assert self.manager.positions['BTC-USD'].status == 'closed'
    
    def test_get_portfolio_summary(self):
        """Test portfolio summary calculation."""
        # Add a mock position
        position = Position(
            symbol='BTC-USD',
            side='long',
            quantity=0.1,
            entry_price=50000.0,
            entry_time=datetime.now(),
            current_price=51000.0,
            unrealized_pnl=100.0
        )
        self.manager.positions['BTC-USD'] = position
        
        # Add a mock trade
        trade = Trade(
            trade_id='test_1',
            symbol='BTC-USD',
            side='buy',
            quantity=0.1,
            price=50000.0,
            timestamp=datetime.now(),
            reason='Test trade',
            pnl=50.0,
            fees=5.0
        )
        self.manager.trades.append(trade)
        
        portfolio = self.manager.get_portfolio_summary()
        
        assert portfolio.cash_balance == 10000.0
        assert portfolio.total_value > 10000.0  # Should include position value
        assert portfolio.total_pnl > 0
        assert portfolio.total_fees == 5.0
        assert portfolio.total_trades == 1
        assert portfolio.winning_trades == 1
        assert portfolio.win_rate == 100.0
    
    @pytest.mark.asyncio
    async def test_process_buy_signal(self):
        """Test processing a buy signal."""
        # Start trading
        self.manager.start_trading(['BTC-USD'])
        
        # Create a buy signal
        signals = [{
            'symbol': 'BTC-USD',
            'signal': 'buy',
            'signal_generated': True,
            'price': 50000.0,
            'signal_strength': 0.8,
            'signal_reason': 'Volume imbalance buy'
        }]
        
        result = await self.manager.process_signals(signals)
        
        assert result['status'] == 'processed'
        assert result['executed_trades'] == 1
        assert 'BTC-USD' in self.manager.positions
        assert self.manager.positions['BTC-USD'].side == 'long'
        assert self.manager.positions['BTC-USD'].status == 'open'
    
    @pytest.mark.asyncio
    async def test_process_sell_signal(self):
        """Test processing a sell signal."""
        # Start trading and create a position
        self.manager.start_trading(['BTC-USD'])
        
        # Create a position first
        position = Position(
            symbol='BTC-USD',
            side='long',
            quantity=0.1,
            entry_price=50000.0,
            entry_time=datetime.now(),
            current_price=50000.0,
            unrealized_pnl=0.0
        )
        self.manager.positions['BTC-USD'] = position
        
        # Create a sell signal
        signals = [{
            'symbol': 'BTC-USD',
            'signal': 'sell',
            'signal_generated': True,
            'price': 51000.0,
            'signal_strength': 0.9,
            'signal_reason': 'Volume imbalance sell'
        }]
        
        result = await self.manager.process_signals(signals)
        
        assert result['status'] == 'processed'
        assert result['executed_trades'] == 1
        assert result['closed_positions'] == 1
        assert self.manager.positions['BTC-USD'].status == 'closed'
        assert len(self.manager.trades) == 1
        assert self.manager.trades[0].side == 'sell'
    
    @pytest.mark.asyncio
    async def test_process_hold_signal(self):
        """Test processing a hold signal (no action)."""
        self.manager.start_trading(['BTC-USD'])
        
        signals = [{
            'symbol': 'BTC-USD',
            'signal': 'hold',
            'signal_generated': False,
            'price': 50000.0,
            'signal_strength': 0.3
        }]
        
        result = await self.manager.process_signals(signals)
        
        assert result['status'] == 'processed'
        assert result['executed_trades'] == 0
        assert len(self.manager.positions) == 0
    
    @pytest.mark.asyncio
    async def test_max_positions_limit(self):
        """Test that max positions limit is respected."""
        self.manager.max_positions = 2
        self.manager.start_trading(['BTC-USD', 'ETH-USD', 'ADA-USD'])
        
        # Fill up to max positions
        signals = [
            {
                'symbol': 'BTC-USD',
                'signal': 'buy',
                'signal_generated': True,
                'price': 50000.0,
                'signal_strength': 0.8
            },
            {
                'symbol': 'ETH-USD',
                'signal': 'buy',
                'signal_generated': True,
                'price': 3000.0,
                'signal_strength': 0.7
            }
        ]
        
        result = await self.manager.process_signals(signals)
        assert result['executed_trades'] == 2
        assert len([p for p in self.manager.positions.values() if p.status == 'open']) == 2
        
        # Try to add a third position
        signals = [{
            'symbol': 'ADA-USD',
            'signal': 'buy',
            'signal_generated': True,
            'price': 1.0,
            'signal_strength': 0.9
        }]
        
        result = await self.manager.process_signals(signals)
        assert result['executed_trades'] == 0  # Should be rejected
    
    @pytest.mark.asyncio
    async def test_insufficient_balance(self):
        """Test trade rejection due to insufficient balance."""
        # Set very low balance
        self.manager.cash_balance = 10.0
        self.manager.start_trading(['BTC-USD'])
        
        signals = [{
            'symbol': 'BTC-USD',
            'signal': 'buy',
            'signal_generated': True,
            'price': 50000.0,
            'signal_strength': 0.8
        }]
        
        result = await self.manager.process_signals(signals)
        assert result['executed_trades'] == 0
    
    @pytest.mark.asyncio
    async def test_duplicate_position_rejection(self):
        """Test that duplicate positions are rejected."""
        self.manager.start_trading(['BTC-USD'])
        
        # Create first position
        signals = [{
            'symbol': 'BTC-USD',
            'signal': 'buy',
            'signal_generated': True,
            'price': 50000.0,
            'signal_strength': 0.8
        }]
        
        result = await self.manager.process_signals(signals)
        assert result['executed_trades'] == 1
        
        # Try to create duplicate position
        result = await self.manager.process_signals(signals)
        assert result['executed_trades'] == 0
    
    def test_position_price_update(self):
        """Test updating position price and PnL calculation."""
        position = Position(
            symbol='BTC-USD',
            side='long',
            quantity=0.1,
            entry_price=50000.0,
            entry_time=datetime.now(),
            current_price=50000.0,
            unrealized_pnl=0.0
        )
        
        # Update price
        position.update_price(51000.0)
        
        assert position.current_price == 51000.0
        assert position.unrealized_pnl == 100.0  # (51000 - 50000) * 0.1
        
        # Test short position
        position.side = 'short'
        position.update_price(49000.0)
        
        assert position.unrealized_pnl == 100.0  # (50000 - 49000) * 0.1
    
    def test_get_open_positions(self):
        """Test getting open positions."""
        # Add open and closed positions
        open_position = Position(
            symbol='BTC-USD',
            side='long',
            quantity=0.1,
            entry_price=50000.0,
            entry_time=datetime.now(),
            current_price=51000.0,
            unrealized_pnl=100.0
        )
        
        closed_position = Position(
            symbol='ETH-USD',
            side='long',
            quantity=0.5,
            entry_price=3000.0,
            entry_time=datetime.now(),
            current_price=3100.0,
            unrealized_pnl=50.0,
            status='closed'
        )
        
        self.manager.positions['BTC-USD'] = open_position
        self.manager.positions['ETH-USD'] = closed_position
        
        open_positions = self.manager.get_open_positions()
        
        assert len(open_positions) == 1
        assert open_positions[0]['symbol'] == 'BTC-USD'
        assert open_positions[0]['side'] == 'long'
        assert open_positions[0]['unrealized_pnl'] == 100.0
    
    def test_get_recent_trades(self):
        """Test getting recent trades."""
        # Add some trades
        trade1 = Trade(
            trade_id='1',
            symbol='BTC-USD',
            side='buy',
            quantity=0.1,
            price=50000.0,
            timestamp=datetime.now() - timedelta(minutes=10),
            reason='Test 1',
            pnl=0.0,
            fees=5.0
        )
        
        trade2 = Trade(
            trade_id='2',
            symbol='BTC-USD',
            side='sell',
            quantity=0.1,
            price=51000.0,
            timestamp=datetime.now() - timedelta(minutes=5),
            reason='Test 2',
            pnl=100.0,
            fees=5.1
        )
        
        self.manager.trades.extend([trade1, trade2])
        
        recent_trades = self.manager.get_recent_trades(limit=1)
        
        assert len(recent_trades) == 1
        assert recent_trades[0]['trade_id'] == '2'  # Most recent
        assert recent_trades[0]['side'] == 'sell'
        assert recent_trades[0]['pnl'] == 100.0
    
    def test_reset_portfolio(self):
        """Test portfolio reset."""
        # Add some data
        self.manager.cash_balance = 5000.0
        self.manager.positions['BTC-USD'] = Position(
            symbol='BTC-USD',
            side='long',
            quantity=0.1,
            entry_price=50000.0,
            entry_time=datetime.now(),
            current_price=51000.0,
            unrealized_pnl=100.0
        )
        self.manager.trades.append(Trade(
            trade_id='1',
            symbol='BTC-USD',
            side='buy',
            quantity=0.1,
            price=50000.0,
            timestamp=datetime.now(),
            reason='Test'
        ))
        
        # Reset
        self.manager.reset_portfolio()
        
        assert self.manager.cash_balance == 10000.0
        assert len(self.manager.positions) == 0
        assert len(self.manager.trades) == 0
        assert self.manager.trade_counter == 0
        assert self.manager.peak_value == 10000.0
        assert self.manager.max_drawdown == 0.0
    
    @pytest.mark.asyncio
    async def test_trading_not_active(self):
        """Test processing signals when trading is not active."""
        signals = [{
            'symbol': 'BTC-USD',
            'signal': 'buy',
            'signal_generated': True,
            'price': 50000.0,
            'signal_strength': 0.8
        }]
        
        result = await self.manager.process_signals(signals)
        
        assert result['status'] == 'not_trading'
        assert 'message' in result
    
    def test_position_data_structure(self):
        """Test Position dataclass structure."""
        position = Position(
            symbol='BTC-USD',
            side='long',
            quantity=0.1,
            entry_price=50000.0,
            entry_time=datetime.now(),
            current_price=51000.0,
            unrealized_pnl=100.0,
            realized_pnl=50.0,
            status='open'
        )
        
        assert position.symbol == 'BTC-USD'
        assert position.side == 'long'
        assert position.quantity == 0.1
        assert position.entry_price == 50000.0
        assert position.current_price == 51000.0
        assert position.unrealized_pnl == 100.0
        assert position.realized_pnl == 50.0
        assert position.status == 'open'
    
    def test_trade_data_structure(self):
        """Test Trade dataclass structure."""
        trade = Trade(
            trade_id='test_123',
            symbol='BTC-USD',
            side='buy',
            quantity=0.1,
            price=50000.0,
            timestamp=datetime.now(),
            reason='Test trade',
            pnl=100.0,
            fees=5.0
        )
        
        assert trade.trade_id == 'test_123'
        assert trade.symbol == 'BTC-USD'
        assert trade.side == 'buy'
        assert trade.quantity == 0.1
        assert trade.price == 50000.0
        assert trade.reason == 'Test trade'
        assert trade.pnl == 100.0
        assert trade.fees == 5.0
    
    def test_portfolio_data_structure(self):
        """Test Portfolio dataclass structure."""
        portfolio = Portfolio(
            cash_balance=10000.0,
            total_value=10500.0,
            positions={},
            trades=[],
            total_pnl=500.0,
            total_fees=10.0,
            max_drawdown=0.05,
            win_rate=75.0,
            total_trades=4,
            winning_trades=3
        )
        
        assert portfolio.cash_balance == 10000.0
        assert portfolio.total_value == 10500.0
        assert portfolio.total_pnl == 500.0
        assert portfolio.total_fees == 10.0
        assert portfolio.max_drawdown == 0.05
        assert portfolio.win_rate == 75.0
        assert portfolio.total_trades == 4
        assert portfolio.winning_trades == 3


class TestSimulatedTradingIntegration:
    """Integration tests for simulated trading with realistic scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.manager = SimulatedTradingManager(
            initial_balance=10000.0,
            max_positions=5,
            position_size_percent=20.0,
            trading_fee=0.001
        )
    
    @pytest.mark.asyncio
    async def test_complete_trading_cycle(self):
        """Test a complete trading cycle: start, buy, sell, stop."""
        # Start trading
        self.manager.start_trading(['BTC-USD'])
        
        # Buy signal
        buy_signals = [{
            'symbol': 'BTC-USD',
            'signal': 'buy',
            'signal_generated': True,
            'price': 50000.0,
            'signal_strength': 0.8,
            'signal_reason': 'Volume imbalance buy'
        }]
        
        result = await self.manager.process_signals(buy_signals)
        assert result['executed_trades'] == 1
        assert 'BTC-USD' in self.manager.positions
        assert self.manager.positions['BTC-USD'].status == 'open'
        
        # Sell signal
        sell_signals = [{
            'symbol': 'BTC-USD',
            'signal': 'sell',
            'signal_generated': True,
            'price': 51000.0,
            'signal_strength': 0.9,
            'signal_reason': 'Volume imbalance sell'
        }]
        
        result = await self.manager.process_signals(sell_signals)
        assert result['executed_trades'] == 1
        assert result['closed_positions'] == 1
        assert self.manager.positions['BTC-USD'].status == 'closed'
        
        # Check portfolio
        portfolio = self.manager.get_portfolio_summary()
        assert portfolio.total_trades == 2  # Buy + Sell
        assert portfolio.winning_trades == 1  # Profitable sell
    
    @pytest.mark.asyncio
    async def test_multiple_symbols_trading(self):
        """Test trading multiple symbols simultaneously."""
        symbols = ['BTC-USD', 'ETH-USD', 'ADA-USD']
        self.manager.start_trading(symbols)
        
        # Create signals for all symbols
        signals = []
        for i, symbol in enumerate(symbols):
            signals.append({
                'symbol': symbol,
                'signal': 'buy',
                'signal_generated': True,
                'price': 50000.0 + (i * 1000),  # Different prices
                'signal_strength': 0.7 + (i * 0.1),
                'signal_reason': f'Volume imbalance buy for {symbol}'
            })
        
        result = await self.manager.process_signals(signals)
        assert result['executed_trades'] == 3
        assert len([p for p in self.manager.positions.values() if p.status == 'open']) == 3
        
        # Check that all symbols have positions
        for symbol in symbols:
            assert symbol in self.manager.positions
            assert self.manager.positions[symbol].status == 'open'
    
    @pytest.mark.asyncio
    async def test_fee_calculation(self):
        """Test that fees are calculated correctly."""
        self.manager.start_trading(['BTC-USD'])
        
        signals = [{
            'symbol': 'BTC-USD',
            'signal': 'buy',
            'signal_generated': True,
            'price': 50000.0,
            'signal_strength': 0.8
        }]
        
        result = await self.manager.process_signals(signals)
        assert result['executed_trades'] == 1
        
        # Check that fees were calculated
        trade = self.manager.trades[0]
        expected_fees = 50000.0 * trade.quantity * 0.001
        assert abs(trade.fees - expected_fees) < 0.01  # Allow for small floating point differences


if __name__ == '__main__':
    # Run the tests
    pytest.main([__file__, '-v'])
