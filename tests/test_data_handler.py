"""Tests for data handler."""

import pytest
import os
import tempfile
from datetime import datetime
from unittest.mock import patch

from src.trade_bot.config import TradingConfig
from src.trade_bot.data_handler import DataHandler


class TestDataHandler:
    """Test cases for DataHandler."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return TradingConfig(
            api_key="test_key",
            api_secret="test_secret",
            passphrase="test_passphrase",
            output_dir="test_outputs"
        )
    
    @pytest.fixture
    def data_handler(self, config):
        """Create test data handler."""
        return DataHandler(config)
    
    def test_initialization(self, data_handler):
        """Test data handler initialization."""
        assert len(data_handler.ticker_data) == 0
        assert len(data_handler.trade_data) == 0
        assert len(data_handler.signal_data) == 0
        assert os.path.exists(data_handler.config.output_dir)
    
    def test_add_ticker_data(self, data_handler):
        """Test adding ticker data."""
        ticker_data = {
            'product_id': 'BTC-USD',
            'price': '50000.0',
            'volume_24h': '1000.0',
            'best_bid': '49999.0',
            'best_ask': '50001.0'
        }
        
        data_handler.add_ticker_data(ticker_data)
        
        assert len(data_handler.ticker_data) == 1
        record = data_handler.ticker_data[0]
        assert record['product_id'] == 'BTC-USD'
        assert record['price'] == 50000.0
        assert record['volume_24h'] == 1000.0
        assert 'timestamp' in record
    
    def test_add_trade_data(self, data_handler):
        """Test adding trade data."""
        trade_data = {
            'trade_id': '12345',
            'product_id': 'BTC-USD',
            'side': 'buy',
            'price': 50000.0,
            'size': 0.1,
            'value': 5000.0,
            'fee': 5.0,
            'status': 'filled'
        }
        
        data_handler.add_trade_data(trade_data)
        
        assert len(data_handler.trade_data) == 1
        record = data_handler.trade_data[0]
        assert record['trade_id'] == '12345'
        assert record['side'] == 'buy'
        assert record['price'] == 50000.0
        assert 'timestamp' in record
    
    def test_add_signal_data(self, data_handler):
        """Test adding signal data."""
        signal_data = {
            'action': 'buy',
            'price': 50000.0,
            'quantity': 0.1,
            'reason': 'Golden cross',
            'product_id': 'BTC-USD'
        }
        
        data_handler.add_signal_data(signal_data)
        
        assert len(data_handler.signal_data) == 1
        record = data_handler.signal_data[0]
        assert record['action'] == 'buy'
        assert record['price'] == 50000.0
        assert record['reason'] == 'Golden cross'
        assert 'timestamp' in record
    
    def test_save_ticker_data_empty(self, data_handler):
        """Test saving empty ticker data."""
        filename = data_handler.save_ticker_data()
        assert filename == ""
    
    def test_save_ticker_data_with_data(self, data_handler):
        """Test saving ticker data with data."""
        # Add some data
        data_handler.add_ticker_data({
            'product_id': 'BTC-USD',
            'price': '50000.0'
        })
        
        filename = data_handler.save_ticker_data()
        
        assert filename != ""
        assert os.path.exists(filename)
        assert filename.endswith('.csv')
        
        # Clean up
        os.remove(filename)
    
    def test_save_trade_data_with_data(self, data_handler):
        """Test saving trade data with data."""
        # Add some data
        data_handler.add_trade_data({
            'trade_id': '12345',
            'product_id': 'BTC-USD',
            'side': 'buy',
            'price': 50000.0,
            'size': 0.1
        })
        
        filename = data_handler.save_trade_data()
        
        assert filename != ""
        assert os.path.exists(filename)
        assert filename.endswith('.csv')
        
        # Clean up
        os.remove(filename)
    
    def test_save_signal_data_with_data(self, data_handler):
        """Test saving signal data with data."""
        # Add some data
        data_handler.add_signal_data({
            'action': 'buy',
            'price': 50000.0,
            'quantity': 0.1,
            'reason': 'Test signal'
        })
        
        filename = data_handler.save_signal_data()
        
        assert filename != ""
        assert os.path.exists(filename)
        assert filename.endswith('.csv')
        
        # Clean up
        os.remove(filename)
    
    def test_save_all_data(self, data_handler):
        """Test saving all data."""
        # Add data to all categories
        data_handler.add_ticker_data({'product_id': 'BTC-USD', 'price': '50000.0'})
        data_handler.add_trade_data({'trade_id': '12345', 'product_id': 'BTC-USD', 'side': 'buy', 'price': 50000.0, 'size': 0.1})
        data_handler.add_signal_data({'action': 'buy', 'price': 50000.0, 'quantity': 0.1, 'reason': 'Test'})
        
        files = data_handler.save_all_data()
        
        assert 'ticker' in files
        assert 'trades' in files
        assert 'signals' in files
        
        # All files should exist
        for filepath in files.values():
            assert os.path.exists(filepath)
            os.remove(filepath)  # Clean up
    
    def test_get_summary_stats_empty(self, data_handler):
        """Test summary stats with no data."""
        stats = data_handler.get_summary_stats()
        
        assert stats['ticker_records'] == 0
        assert stats['trade_records'] == 0
        assert stats['signal_records'] == 0
    
    def test_get_summary_stats_with_data(self, data_handler):
        """Test summary stats with data."""
        # Add trade data
        data_handler.add_trade_data({
            'trade_id': '12345',
            'product_id': 'BTC-USD',
            'side': 'buy',
            'price': 50000.0,
            'size': 0.1,
            'value': 5000.0,
            'fee': 5.0
        })
        
        data_handler.add_trade_data({
            'trade_id': '12346',
            'product_id': 'BTC-USD',
            'side': 'sell',
            'price': 51000.0,
            'size': 0.1,
            'value': 5100.0,
            'fee': 5.1
        })
        
        stats = data_handler.get_summary_stats()
        
        assert stats['ticker_records'] == 0
        assert stats['trade_records'] == 2
        assert stats['signal_records'] == 0
        assert stats['total_trades'] == 2
        assert stats['total_volume'] == 0.2
        assert stats['total_value'] == 10100.0
        assert stats['total_fees'] == 10.1
        assert stats['avg_price'] == 50500.0
        assert stats['min_price'] == 50000.0
        assert stats['max_price'] == 51000.0
