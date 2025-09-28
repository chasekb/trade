"""Tests for the backtesting module."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.trade_bot.config import TradingConfig
from src.trade_bot.backtester import Backtester, BacktestResult
from src.trade_bot.trading_strategy import SimpleMovingAverageStrategy, TradeSignal


class TestBacktester:
    """Test cases for the Backtester class."""
    
    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return TradingConfig(
            api_key="test_key",
            api_secret="test_secret",
            passphrase="test_passphrase",
            product_id="BTC-USD",
            max_position_size=10000.0,
            trading_fee_percentage=0.001,
            stop_loss_percentage=0.02,
            take_profit_percentage=0.05
        )
    
    @pytest.fixture
    def backtester(self, config):
        """Create a backtester instance."""
        return Backtester(
            config=config,
            strategy_class=SimpleMovingAverageStrategy,
            strategy_params={'short_window': 3, 'long_window': 5}
        )
    
    @pytest.fixture
    def sample_data(self):
        """Create sample historical data."""
        base_time = datetime.now() - timedelta(hours=10)
        data = []
        
        # Create a price trend that will trigger SMA crossovers
        prices = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0, 110.0, 111.0, 112.0, 113.0, 114.0, 115.0, 116.0, 117.0, 118.0, 119.0, 120.0]
        
        for i, price in enumerate(prices):
            data.append({
                'timestamp': (base_time + timedelta(hours=i)).isoformat() + 'Z',
                'price': price,
                'open': price - 0.5,
                'high': price + 0.5,
                'low': price - 1.0,
                'close': price,
                'volume': 1.0
            })
        
        return data
    
    def test_backtester_initialization(self, backtester, config):
        """Test backtester initialization."""
        assert backtester.config == config
        assert backtester.balance == config.max_position_size
        assert backtester.initial_balance == config.max_position_size
        assert backtester.position == 0.0
        assert backtester.entry_price == 0.0
        assert len(backtester.trades) == 0
        assert len(backtester.equity_curve) == 0
        assert backtester.fees_paid == 0.0
    
    def test_calculate_fees(self, backtester):
        """Test fee calculation."""
        fees = backtester._calculate_fees(100.0, 1.0)
        expected_fees = 100.0 * 1.0 * 0.001  # 0.1
        assert fees == expected_fees
    
    def test_execute_trade_buy(self, backtester):
        """Test executing a buy trade."""
        signal = TradeSignal(
            action='buy',
            price=100.0,
            quantity=1.0,
            timestamp=datetime.now(),
            reason="Test buy"
        )
        
        success = backtester._execute_trade(signal, 100.0, datetime.now())
        
        assert success is True
        # The backtester calculates quantity based on available balance (95% of 10000 = 9500)
        # So quantity = 9500 / 100 = 95
        expected_quantity = 9500.0 / 100.0  # 95.0
        assert backtester.position == expected_quantity
        assert backtester.entry_price == 100.0
        assert len(backtester.trades) == 1
        assert backtester.trades[0]['action'] == 'buy'
        assert backtester.trades[0]['price'] == 100.0
        assert backtester.trades[0]['quantity'] == expected_quantity
    
    def test_execute_trade_sell(self, backtester):
        """Test executing a sell trade."""
        # First buy
        buy_signal = TradeSignal(
            action='buy',
            price=100.0,
            quantity=1.0,
            timestamp=datetime.now(),
            reason="Test buy"
        )
        backtester._execute_trade(buy_signal, 100.0, datetime.now())
        
        # Get the actual quantity that was bought
        actual_quantity = backtester.position
        
        # Then sell
        sell_signal = TradeSignal(
            action='sell',
            price=110.0,
            quantity=actual_quantity,  # Use actual quantity
            timestamp=datetime.now(),
            reason="Test sell"
        )
        
        success = backtester._execute_trade(sell_signal, 110.0, datetime.now())
        
        assert success is True
        assert backtester.position == 0.0
        assert backtester.entry_price == 0.0
        assert len(backtester.trades) == 2
        assert backtester.trades[1]['action'] == 'sell'
        assert backtester.trades[1]['price'] == 110.0
        # Calculate expected profit: (110 - 100) * quantity - fees
        expected_profit = (110.0 - 100.0) * actual_quantity - backtester.trades[1]['fees']
        assert abs(backtester.trades[1]['profit_loss'] - expected_profit) < 0.01
    
    def test_execute_trade_insufficient_balance(self, backtester):
        """Test executing a trade with insufficient balance."""
        # Reset backtester state
        backtester.position = 0.0
        backtester.entry_price = 0.0
        backtester.trades = []
        
        # Set very low balance - less than what's needed for even a small trade
        # With balance = 0.01, available_balance = 0.0095, quantity = 0.000095
        # total_cost = 0.000095 * 100 + fees = 0.0095 + fees > 0.01
        backtester.balance = 0.01  # Very low balance
        
        signal = TradeSignal(
            action='buy',
            price=100.0,
            quantity=1.0,
            timestamp=datetime.now(),
            reason="Test buy"
        )
        
        success = backtester._execute_trade(signal, 100.0, datetime.now())
        
        # Now it should fail because the quantity is too small
        assert success is False
        assert backtester.position == 0.0
        assert len(backtester.trades) == 0
    
    def test_update_equity_curve(self, backtester):
        """Test equity curve update."""
        timestamp = datetime.now()
        
        # Update with no position
        backtester._update_equity_curve(100.0, timestamp)
        
        assert len(backtester.equity_curve) == 1
        assert backtester.equity_curve[0]['total_value'] == backtester.balance
        assert backtester.equity_curve[0]['position'] == 0.0
        
        # Update with position
        backtester.position = 1.0
        backtester.entry_price = 100.0
        backtester._update_equity_curve(110.0, timestamp)
        
        assert len(backtester.equity_curve) == 2
        assert backtester.equity_curve[1]['position'] == 1.0
        assert backtester.equity_curve[1]['unrealized_pnl'] == 10.0  # 110 - 100
    
    def test_calculate_metrics_no_trades(self, backtester):
        """Test metrics calculation with no trades."""
        result = backtester._calculate_metrics()
        
        assert result.total_trades == 0
        assert result.winning_trades == 0
        assert result.losing_trades == 0
        assert result.win_rate == 0.0
        assert result.total_return == 0.0
        assert result.net_profit == 0.0
    
    def test_calculate_metrics_with_trades(self, backtester):
        """Test metrics calculation with trades."""
        # Add some trades
        backtester.trades = [
            {
                'timestamp': datetime.now(),
                'action': 'buy',
                'price': 100.0,
                'quantity': 1.0,
                'fees': 0.1,
                'balance': 9899.9,
                'reason': 'Test buy'
            },
            {
                'timestamp': datetime.now(),
                'action': 'sell',
                'price': 110.0,
                'quantity': 1.0,
                'fees': 0.11,
                'balance': 10999.79,
                'reason': 'Test sell',
                'profit_loss': 9.79  # 110 - 100 - 0.1 - 0.11
            }
        ]
        
        backtester.balance = 10999.79
        backtester.fees_paid = 0.21
        
        result = backtester._calculate_metrics()
        
        assert result.total_trades == 1
        assert result.winning_trades == 1
        assert result.losing_trades == 0
        assert result.win_rate == 1.0
        assert abs(result.total_return - 0.099979) < 0.000001  # (10999.79 - 10000) / 10000
        assert abs(result.net_profit - 999.79) < 0.01
        assert result.total_fees == 0.21
    
    @pytest.mark.asyncio
    async def test_run_backtest(self, backtester, sample_data):
        """Test running a complete backtest."""
        result = await backtester.run_backtest(sample_data)
        
        assert isinstance(result, BacktestResult)
        assert result.total_trades >= 0
        assert result.initial_balance == 10000.0
        assert result.final_balance >= 0.0
        assert result.start_date <= result.end_date
    
    def test_get_equity_curve_df(self, backtester):
        """Test getting equity curve as DataFrame."""
        # Add some equity curve data
        backtester.equity_curve = [
            {
                'timestamp': datetime.now(),
                'balance': 10000.0,
                'position': 0.0,
                'position_value': 0.0,
                'total_value': 10000.0,
                'unrealized_pnl': 0.0
            }
        ]
        
        df = backtester.get_equity_curve_df()
        
        assert not df.empty
        assert 'balance' in df.columns
        assert 'total_value' in df.columns
        assert df.index.name == 'timestamp'
    
    def test_get_trades_df(self, backtester):
        """Test getting trades as DataFrame."""
        # Add some trades
        backtester.trades = [
            {
                'timestamp': datetime.now(),
                'action': 'buy',
                'price': 100.0,
                'quantity': 1.0,
                'fees': 0.1,
                'balance': 9899.9,
                'reason': 'Test buy'
            }
        ]
        
        df = backtester.get_trades_df()
        
        assert not df.empty
        assert 'action' in df.columns
        assert 'price' in df.columns
        assert 'quantity' in df.columns
        assert len(df) == 1
