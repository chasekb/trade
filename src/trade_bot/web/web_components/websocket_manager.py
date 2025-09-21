"""WebSocket manager for real-time data connections."""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any

from fastapi import WebSocket
from ...core.config import TradingConfig
from ...data.websocket_client import WebSocketClient
from ...data.data_handler import DataHandler

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections for real-time data."""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.active_connections: List[WebSocket] = []
        self.websocket_client = None
        self.data_handler = DataHandler(config)
        self.real_time_data: Dict[str, Any] = {}
        self.trading_state: Dict[str, Any] = {}
        self.simulated_trading = None
    
    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send a message to a specific WebSocket."""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: str):
        """Broadcast a message to all connected WebSockets."""
        for connection in self.active_connections.copy():
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting to connection: {e}")
                self.disconnect(connection)
    
    async def start_real_time_data(self):
        """Start the real-time data feed with all subscription types."""
        if not self.websocket_client:
            self.websocket_client = WebSocketClient(self.config)
            
            # Register message handlers for Coinbase channel names
            self.websocket_client.register_handler('ticker', self._handle_ticker_message)
            self.websocket_client.register_handler('ticker_batch', self._handle_ticker_message)
            self.websocket_client.register_handler('level2', self._handle_level2_message)
            self.websocket_client.register_handler('candles', self._handle_candles_message)
            self.websocket_client.register_handler('status', self._handle_status_message)
            self.websocket_client.register_handler('market_trades', self._handle_market_trades_message)
            self.websocket_client.register_handler('user', self._handle_user_message)
            
            # Start the websocket client (with error handling)
            asyncio.create_task(self._run_websocket_client())
            
            # Start the data collection task
            asyncio.create_task(self._collect_real_time_data())
            
            # Start the simulated trading task
            asyncio.create_task(self._process_simulated_trading())
    
    async def _process_simulated_trading(self):
        """Process simulated trading signals in the background."""
        while True:
            try:
                # Check if trading is active
                if self.trading_state.get("is_active") and self.trading_state.get("strategy_type") == "orderbook":
                    # Get live order book signals
                    symbols = self.trading_state.get("symbols", [])
                    if symbols and self.simulated_trading:
                        # Process signals through simulated trading
                        # This would need to be implemented based on the actual signal processing logic
                        pass
                
                # Wait before next check
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in simulated trading processing: {e}")
                await asyncio.sleep(30)  # Wait before retrying
    
    async def _run_websocket_client(self):
        """Run the websocket client in the background."""
        try:
            await self.websocket_client.connect()
            
            # Subscribe to heartbeats first to keep connection alive
            await self.websocket_client.subscribe_to_channel('heartbeats', [])
            
            # Subscribe to data channels
            await self.websocket_client.subscribe_to_ticker(self.config.product_id)
            await self.websocket_client.subscribe_to_level2(self.config.product_id)
            await self.websocket_client.subscribe_to_candles(self.config.product_id)
            
            await self.websocket_client.listen()
        except Exception as e:
            logger.error(f"WebSocket client error: {e}")
    
    async def _handle_ticker_message(self, data):
        """Handle ticker messages per Coinbase documentation format."""
        events = data.get('events', [])
        for event in events:
            if 'tickers' in event:
                for ticker in event['tickers']:
                    self.data_handler.add_ticker_data(ticker)
    
    async def _handle_level2_message(self, data):
        """Handle level2 messages per Coinbase documentation format."""
        events = data.get('events', [])
        for event in events:
            if event.get('type') in ['snapshot', 'update']:
                self.data_handler.add_level2_data(event)
    
    async def _handle_candles_message(self, data):
        """Handle candles/OHLCV messages per Coinbase documentation format."""
        events = data.get('events', [])
        for event in events:
            if 'candles' in event:
                for candle in event['candles']:
                    self.data_handler.add_candles_data(candle)
    
    async def _handle_status_message(self, data):
        """Handle product status messages per Coinbase documentation format."""
        events = data.get('events', [])
        for event in events:
            if 'products' in event:
                for product in event['products']:
                    self.data_handler.add_status_data(product)
    
    async def _handle_market_trades_message(self, data):
        """Handle market trades messages per Coinbase documentation format."""
        events = data.get('events', [])
        for event in events:
            if 'trades' in event:
                for trade in event['trades']:
                    self.data_handler.add_market_trades_data(trade)
    
    async def _handle_user_message(self, data):
        """Handle user messages per Coinbase documentation format."""
        events = data.get('events', [])
        for event in events:
            if 'orders' in event:
                for order in event['orders']:
                    self.data_handler.add_trade_data(order)
            elif 'positions' in event:
                for position in event['positions']:
                    self.data_handler.add_trade_data(position)
    
    async def _collect_real_time_data(self):
        """Collect real-time data and broadcast to clients."""
        while True:
            try:
                # Check if data handler is initialized
                if not self.data_handler:
                    await asyncio.sleep(1)
                    continue
                    
                # Get latest data from data handler for all types
                ticker_data = self.data_handler.get_latest_ticker()
                trade_data = self.data_handler.get_latest_trades()
                level2_data = self.data_handler.get_latest_level2()
                candles_data = self.data_handler.get_latest_candles()
                matches_data = self.data_handler.get_latest_matches()
                status_data = self.data_handler.get_latest_status()
                market_trades_data = self.data_handler.get_latest_market_trades()
                
                # Prepare comprehensive real-time data
                current_data = {
                    'ticker': ticker_data,
                    'trades': trade_data,
                    'level2': level2_data,
                    'candles': candles_data,
                    'matches': matches_data,
                    'status': status_data,
                    'market_trades': market_trades_data,
                    'timestamp': datetime.now().isoformat()
                }
                
                # Only broadcast if we have some data
                if any([ticker_data, trade_data, level2_data, candles_data, 
                       matches_data, status_data, market_trades_data]):
                    self.real_time_data[self.config.product_id] = current_data
                    
                    # Broadcast to all connected clients
                    await self.broadcast(f"data:{current_data}")
                
                # Wait before next collection
                await asyncio.sleep(1)  # Collect every second
                
            except Exception as e:
                logger.error(f"Error collecting real-time data: {e}")
                await asyncio.sleep(5)  # Wait before retrying
    
    def get_real_time_data(self) -> Dict[str, Any]:
        """Get the current real-time data."""
        return self.real_time_data
    
    def set_trading_state(self, state: Dict[str, Any]):
        """Set the trading state."""
        self.trading_state = state
    
    def set_simulated_trading(self, simulated_trading):
        """Set the simulated trading manager."""
        self.simulated_trading = simulated_trading
