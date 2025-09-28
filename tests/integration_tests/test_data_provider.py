"""Tests for the data provider module."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from src.trade_bot.data_provider import CoinbaseDataProvider, MockDataProvider


class TestCoinbaseDataProvider:
    """Test cases for the CoinbaseDataProvider class."""
    
    @pytest.fixture
    def provider(self):
        """Create a CoinbaseDataProvider instance."""
        return CoinbaseDataProvider("BTC-USD")
    
    def test_initialization(self, provider):
        """Test provider initialization."""
        assert provider.product_id == "BTC-USD"
        assert provider.base_url == "https://api.exchange.coinbase.com"
    
    def test_process_candle_data(self, provider):
        """Test processing raw candle data."""
        raw_data = [
            [1609459200, 29000.0, 30000.0, 29500.0, 29750.0, 1.5],  # 2021-01-01 00:00:00
            [1609462800, 29750.0, 30500.0, 29750.0, 30250.0, 2.0],  # 2021-01-01 01:00:00
        ]
        
        processed = provider._process_candle_data(raw_data)
        
        assert len(processed) == 2
        assert processed[0]['timestamp'] == '2020-12-31T18:00:00Z'  # UTC conversion
        assert processed[0]['open'] == 29500.0
        assert processed[0]['high'] == 30000.0
        assert processed[0]['low'] == 29000.0
        assert processed[0]['close'] == 29750.0
        assert processed[0]['volume'] == 1.5
        assert processed[0]['price'] == 29750.0
    
    def test_process_trade_data(self, provider):
        """Test processing raw trade data."""
        raw_data = [
            {
                'time': '2021-01-01T00:00:00Z',
                'price': '29750.0',
                'size': '0.5',
                'side': 'buy',
                'trade_id': '12345'
            },
            {
                'time': '2021-01-01T00:01:00Z',
                'price': '29800.0',
                'size': '0.3',
                'side': 'sell',
                'trade_id': '12346'
            }
        ]
        
        processed = provider._process_trade_data(raw_data)
        
        assert len(processed) == 2
        assert processed[0]['timestamp'] == '2021-01-01T00:00:00Z'
        assert processed[0]['price'] == 29750.0
        assert processed[0]['size'] == 0.5
        assert processed[0]['side'] == 'buy'
        assert processed[0]['trade_id'] == '12345'
    
    @pytest.mark.asyncio
    async def test_get_historical_candles_success(self, provider):
        """Test successful historical candles fetch."""
        mock_response_data = [
            [1609459200, 29000.0, 30000.0, 29500.0, 29750.0, 1.5],
            [1609462800, 29750.0, 30500.0, 29750.0, 30250.0, 2.0],
        ]
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            mock_get.return_value.__aenter__.return_value = mock_response
            
            start_time = datetime(2021, 1, 1)
            end_time = datetime(2021, 1, 2)
            
            result = await provider.get_historical_candles(start_time, end_time)
            
            assert len(result) == 2
            assert result[0]['price'] == 29750.0
            assert result[1]['price'] == 30250.0
    
    @pytest.mark.asyncio
    async def test_get_historical_candles_failure(self, provider):
        """Test historical candles fetch failure."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 400
            mock_get.return_value.__aenter__.return_value = mock_response
            
            start_time = datetime(2021, 1, 1)
            end_time = datetime(2021, 1, 2)
            
            result = await provider.get_historical_candles(start_time, end_time)
            
            assert len(result) == 0
    
    @pytest.mark.asyncio
    async def test_get_historical_trades_success(self, provider):
        """Test successful historical trades fetch."""
        mock_response_data = [
            {
                'time': '2021-01-01T00:00:00Z',
                'price': '29750.0',
                'size': '0.5',
                'side': 'buy',
                'trade_id': '12345'
            }
        ]
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            mock_get.return_value.__aenter__.return_value = mock_response
            
            start_time = datetime(2021, 1, 1)
            end_time = datetime(2021, 1, 2)
            
            result = await provider.get_historical_trades(start_time, end_time)
            
            assert len(result) == 1
            assert result[0]['price'] == 29750.0


class TestMockDataProvider:
    """Test cases for the MockDataProvider class."""
    
    @pytest.fixture
    def provider(self):
        """Create a MockDataProvider instance."""
        return MockDataProvider("BTC-USD")
    
    def test_initialization(self, provider):
        """Test provider initialization."""
        assert provider.product_id == "BTC-USD"
    
    @pytest.mark.asyncio
    async def test_get_historical_candles(self, provider):
        """Test getting mock historical candles."""
        start_time = datetime(2021, 1, 1)
        end_time = datetime(2021, 1, 2)
        
        result = await provider.get_historical_candles(start_time, end_time, granularity=3600)
        
        assert len(result) > 0
        assert all('timestamp' in candle for candle in result)
        assert all('price' in candle for candle in result)
        assert all('open' in candle for candle in result)
        assert all('high' in candle for candle in result)
        assert all('low' in candle for candle in result)
        assert all('close' in candle for candle in result)
        assert all('volume' in candle for candle in result)
        
        # Check that timestamps are in order
        timestamps = [datetime.fromisoformat(candle['timestamp'].replace('Z', '+00:00')) for candle in result]
        assert timestamps == sorted(timestamps)
    
    @pytest.mark.asyncio
    async def test_get_historical_trades(self, provider):
        """Test getting mock historical trades."""
        start_time = datetime(2021, 1, 1)
        end_time = datetime(2021, 1, 2)
        
        result = await provider.get_historical_trades(start_time, end_time, limit=10)
        
        assert len(result) <= 10
        assert all('timestamp' in trade for trade in result)
        assert all('price' in trade for trade in result)
        assert all('size' in trade for trade in result)
        assert all('side' in trade for trade in result)
        assert all('trade_id' in trade for trade in result)
        
        # Check that all sides are valid
        sides = [trade['side'] for trade in result]
        assert all(side in ['buy', 'sell'] for side in sides)
    
    @pytest.mark.asyncio
    async def test_get_historical_candles_different_granularity(self, provider):
        """Test getting candles with different granularity."""
        start_time = datetime(2021, 1, 1)
        end_time = datetime(2021, 1, 2)
        
        # Test 1-hour candles
        result_1h = await provider.get_historical_candles(start_time, end_time, granularity=3600)
        
        # Test 4-hour candles
        result_4h = await provider.get_historical_candles(start_time, end_time, granularity=14400)
        
        # 4-hour candles should have fewer data points
        assert len(result_4h) < len(result_1h)
        
        # Both should have valid data
        assert len(result_1h) > 0
        assert len(result_4h) > 0
