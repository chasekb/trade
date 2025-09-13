"""Tests for trading strategy."""

import pytest
from datetime import datetime
from unittest.mock import Mock

from src.trade_bot.config import TradingConfig
from src.trade_bot.trading_strategy import SimpleMovingAverageStrategy, TradeSignal


class TestSimpleMovingAverageStrategy:
    """Test cases for SimpleMovingAverageStrategy."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return TradingConfig(
            api_key="test_key",
            api_secret="test_secret",
            passphrase="test_passphrase",
            max_position_size=1000.0,
            stop_loss_percentage=0.02,
            take_profit_percentage=0.04
        )
    
    @pytest.fixture
    def strategy(self, config):
        """Create test strategy."""
        return SimpleMovingAverageStrategy(config, short_window=3, long_window=5)
    
    def test_initial_state(self, strategy):
        """Test initial strategy state."""
        assert strategy.position == 0.0
        assert strategy.entry_price == 0.0
        assert len(strategy.price_history) == 0
    
    def test_add_price(self, strategy):
        """Test adding price points."""
        timestamp = datetime.now()
        strategy.add_price(100.0, timestamp)
        
        assert len(strategy.price_history) == 1
        assert strategy.price_history[0]['price'] == 100.0
        assert strategy.price_history[0]['timestamp'] == timestamp
    
    def test_calculate_sma_insufficient_data(self, strategy):
        """Test SMA calculation with insufficient data."""
        strategy.add_price(100.0, datetime.now())
        
        sma = strategy.calculate_sma(5)
        assert sma is None
    
    def test_calculate_sma_sufficient_data(self, strategy):
        """Test SMA calculation with sufficient data."""
        timestamp = datetime.now()
        prices = [100.0, 101.0, 102.0, 103.0, 104.0]
        
        for price in prices:
            strategy.add_price(price, timestamp)
        
        sma = strategy.calculate_sma(5)
        assert sma == 102.0  # (100+101+102+103+104)/5
    
    def test_generate_signal_insufficient_data(self, strategy):
        """Test signal generation with insufficient data."""
        timestamp = datetime.now()
        strategy.add_price(100.0, timestamp)
        
        signal = strategy.generate_signal(100.0, timestamp)
        assert signal is None
    
    def test_generate_signal_no_crossover(self, strategy):
        """Test signal generation with no crossover."""
        timestamp = datetime.now()
        # Create data that won't trigger a crossover
        prices = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0]
        
        for price in prices:
            strategy.add_price(price, timestamp)
        
        signal = strategy.generate_signal(108.0, timestamp)
        assert signal is None
    
    def test_generate_signal_golden_cross(self, strategy):
        """Test golden cross buy signal."""
        timestamp = datetime.now()
        # Create data that triggers golden cross
        # Short SMA will be higher than long SMA
        prices = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0, 110.0]
        
        for price in prices:
            strategy.add_price(price, timestamp)
        
        signal = strategy.generate_signal(111.0, timestamp)
        
        assert signal is not None
        assert signal.action == 'buy'
        assert signal.price == 111.0
        assert signal.quantity > 0
        assert 'Golden cross' in signal.reason
    
    def test_generate_signal_death_cross(self, strategy):
        """Test death cross sell signal."""
        timestamp = datetime.now()
        
        # First create a position
        strategy.position = 1.0
        strategy.entry_price = 100.0
        
        # Create data that triggers death cross
        # Long SMA will be higher than short SMA
        prices = [110.0, 109.0, 108.0, 107.0, 106.0, 105.0, 104.0, 103.0, 102.0, 101.0, 100.0]
        
        for price in prices:
            strategy.add_price(price, timestamp)
        
        signal = strategy.generate_signal(99.0, timestamp)
        
        assert signal is not None
        assert signal.action == 'sell'
        assert signal.price == 99.0
        assert signal.quantity == 1.0
        assert 'Death cross' in signal.reason
    
    def test_generate_signal_stop_loss(self, strategy):
        """Test stop loss signal."""
        timestamp = datetime.now()
        
        # Create a position
        strategy.position = 1.0
        strategy.entry_price = 100.0
        
        # Create price that triggers stop loss (2% loss)
        current_price = 98.0  # 2% loss
        
        signal = strategy.generate_signal(current_price, timestamp)
        
        assert signal is not None
        assert signal.action == 'sell'
        assert signal.price == current_price
        assert signal.quantity == 1.0
        assert 'Stop loss' in signal.reason
    
    def test_generate_signal_take_profit(self, strategy):
        """Test take profit signal."""
        timestamp = datetime.now()
        
        # Create a position
        strategy.position = 1.0
        strategy.entry_price = 100.0
        
        # Create price that triggers take profit (4% gain)
        current_price = 104.0  # 4% gain
        
        signal = strategy.generate_signal(current_price, timestamp)
        
        assert signal is not None
        assert signal.action == 'sell'
        assert signal.price == current_price
        assert signal.quantity == 1.0
        assert 'Take profit' in signal.reason
    
    def test_update_position_buy(self, strategy):
        """Test position update on buy signal."""
        signal = TradeSignal(
            action='buy',
            price=100.0,
            quantity=1.0,
            timestamp=datetime.now(),
            reason='Test buy'
        )
        
        strategy.update_position(signal)
        
        assert strategy.position == 1.0
        assert strategy.entry_price == 100.0
    
    def test_update_position_sell(self, strategy):
        """Test position update on sell signal."""
        # First create a position
        strategy.position = 1.0
        strategy.entry_price = 100.0
        
        signal = TradeSignal(
            action='sell',
            price=105.0,
            quantity=1.0,
            timestamp=datetime.now(),
            reason='Test sell'
        )
        
        strategy.update_position(signal)
        
        assert strategy.position == 0.0
        assert strategy.entry_price == 0.0
    
    def test_get_position_info(self, strategy):
        """Test position info retrieval."""
        # No position
        info = strategy.get_position_info()
        assert info['position'] == 0.0
        assert info['entry_price'] == 0.0
        assert info['unrealized_pnl'] == 0.0
        
        # With position
        strategy.position = 1.0
        strategy.entry_price = 100.0
        
        info = strategy.get_position_info()
        assert info['position'] == 1.0
        assert info['entry_price'] == 100.0
        assert info['unrealized_pnl'] == 100.0
