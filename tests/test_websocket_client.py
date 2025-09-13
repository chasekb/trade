"""Tests for WebSocket client."""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from src.trade_bot.config import TradingConfig
from src.trade_bot.websocket_client import WebSocketClient


class TestWebSocketClient:
    """Test cases for WebSocketClient."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return TradingConfig(
            api_key="test_key",
            api_secret="test_secret",
            passphrase="test_passphrase"
        )
    
    @pytest.fixture
    def websocket_client(self, config):
        """Create test WebSocket client."""
        return WebSocketClient(config)
    
    def test_initialization(self, websocket_client):
        """Test WebSocket client initialization."""
        assert websocket_client.websocket is None
        assert websocket_client.running is False
        assert len(websocket_client.message_handlers) == 0
    
    def test_register_handler(self, websocket_client):
        """Test message handler registration."""
        handler = Mock()
        websocket_client.register_handler("test_type", handler)
        
        assert "test_type" in websocket_client.message_handlers
        assert websocket_client.message_handlers["test_type"] == handler
    
    @pytest.mark.asyncio
    async def test_connect_success(self, websocket_client):
        """Test successful WebSocket connection."""
        mock_websocket = AsyncMock()
        
        with patch('websockets.connect', return_value=mock_websocket):
            await websocket_client.connect()
            
            assert websocket_client.websocket == mock_websocket
            assert websocket_client.running is True
    
    @pytest.mark.asyncio
    async def test_connect_failure(self, websocket_client):
        """Test WebSocket connection failure."""
        with patch('websockets.connect', side_effect=Exception("Connection failed")):
            with pytest.raises(Exception, match="Connection failed"):
                await websocket_client.connect()
    
    @pytest.mark.asyncio
    async def test_disconnect(self, websocket_client):
        """Test WebSocket disconnection."""
        mock_websocket = AsyncMock()
        websocket_client.websocket = mock_websocket
        websocket_client.running = True
        
        await websocket_client.disconnect()
        
        assert websocket_client.running is False
        mock_websocket.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_subscribe_to_ticker(self, websocket_client):
        """Test ticker subscription."""
        mock_websocket = AsyncMock()
        websocket_client.websocket = mock_websocket
        
        await websocket_client.subscribe_to_ticker("BTC-USD")
        
        # Verify the subscription message was sent
        mock_websocket.send.assert_called_once()
        call_args = mock_websocket.send.call_args[0][0]
        message = json.loads(call_args)
        
        assert message["type"] == "subscribe"
        assert "BTC-USD" in message["product_ids"]
        assert "ticker" in message["channels"]
    
    @pytest.mark.asyncio
    async def test_subscribe_to_ticker_no_connection(self, websocket_client):
        """Test ticker subscription without connection."""
        with pytest.raises(RuntimeError, match="WebSocket not connected"):
            await websocket_client.subscribe_to_ticker("BTC-USD")
    
    @pytest.mark.asyncio
    async def test_subscribe_to_level2(self, websocket_client):
        """Test level2 subscription."""
        mock_websocket = AsyncMock()
        websocket_client.websocket = mock_websocket
        
        await websocket_client.subscribe_to_level2("BTC-USD")
        
        # Verify the subscription message was sent
        mock_websocket.send.assert_called_once()
        call_args = mock_websocket.send.call_args[0][0]
        message = json.loads(call_args)
        
        assert message["type"] == "subscribe"
        assert "BTC-USD" in message["product_ids"]
        assert "level2" in message["channels"]
    
    @pytest.mark.asyncio
    async def test_handle_message_with_handler(self, websocket_client):
        """Test message handling with registered handler."""
        handler = AsyncMock()
        websocket_client.register_handler("test_type", handler)
        
        test_message = {"type": "test_type", "data": "test_data"}
        
        await websocket_client._handle_message(test_message)
        
        handler.assert_called_once_with(test_message)
    
    @pytest.mark.asyncio
    async def test_handle_message_no_handler(self, websocket_client):
        """Test message handling without registered handler."""
        test_message = {"type": "unknown_type", "data": "test_data"}
        
        # Should not raise an exception
        await websocket_client._handle_message(test_message)
    
    @pytest.mark.asyncio
    async def test_handle_message_handler_error(self, websocket_client):
        """Test message handling with handler error."""
        handler = AsyncMock(side_effect=Exception("Handler error"))
        websocket_client.register_handler("test_type", handler)
        
        test_message = {"type": "test_type", "data": "test_data"}
        
        # Should not raise an exception, just log the error
        await websocket_client._handle_message(test_message)
        
        handler.assert_called_once_with(test_message)
    
    @pytest.mark.asyncio
    async def test_listen_no_connection(self, websocket_client):
        """Test listen without connection."""
        with pytest.raises(RuntimeError, match="WebSocket not connected"):
            await websocket_client.listen()
    
    @pytest.mark.asyncio
    async def test_listen_with_messages(self, websocket_client):
        """Test listening with incoming messages."""
        mock_websocket = AsyncMock()
        websocket_client.websocket = mock_websocket
        websocket_client.running = True
        
        # Mock message iteration
        messages = [
            '{"type": "ticker", "price": "50000"}',
            '{"type": "l2update", "changes": []}'
        ]
        mock_websocket.__aiter__.return_value = iter(messages)
        
        # Register handlers
        ticker_handler = AsyncMock()
        l2_handler = AsyncMock()
        websocket_client.register_handler("ticker", ticker_handler)
        websocket_client.register_handler("l2update", l2_handler)
        
        # Run listen (it will process the messages and then stop)
        websocket_client.running = False  # Stop after processing
        await websocket_client.listen()
        
        # Verify handlers were called
        ticker_handler.assert_called_once()
        l2_handler.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_listen_json_decode_error(self, websocket_client):
        """Test listen with invalid JSON."""
        mock_websocket = AsyncMock()
        websocket_client.websocket = mock_websocket
        websocket_client.running = True
        
        # Mock invalid JSON message
        messages = ['invalid json']
        mock_websocket.__aiter__.return_value = iter(messages)
        
        # Should not raise an exception
        websocket_client.running = False
        await websocket_client.listen()
    
    @pytest.mark.asyncio
    async def test_run_success(self, websocket_client):
        """Test successful run."""
        mock_websocket = AsyncMock()
        
        with patch('websockets.connect', return_value=mock_websocket):
            # Mock the listen method to avoid infinite loop
            websocket_client.listen = AsyncMock()
            
            await websocket_client.run()
            
            # Verify connection and subscriptions were called
            mock_websocket.send.assert_called()
            websocket_client.listen.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_run_connection_error(self, websocket_client):
        """Test run with connection error."""
        with patch('websockets.connect', side_effect=Exception("Connection failed")):
            with pytest.raises(Exception, match="Connection failed"):
                await websocket_client.run()
