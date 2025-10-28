"""WebSocket manager for real-time data connections."""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, Set

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
        self.subscriptions: Dict[str, Set[str]] = {}  # channel -> set of product_ids
        self.connection_heartbeats: Dict[WebSocket, datetime] = {}  # track last heartbeat per connection
    
    async def connect(self, websocket: WebSocket):
        """Handle a new WebSocket connection."""
        self.active_connections.append(websocket)
        self.connection_heartbeats[websocket] = datetime.now()
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

        # Start heartbeat checker if this is the first connection
        if len(self.active_connections) == 1:
            asyncio.create_task(self._heartbeat_checker())

    async def _heartbeat_checker(self):
        """Periodically check connection heartbeats and ping clients."""
        import json
        while self.active_connections:
            try:
                current_time = datetime.now()
                dead_connections = []

                # Check each connection for heartbeat timeout
                for websocket, last_heartbeat in self.connection_heartbeats.items():
                    time_since_heartbeat = (current_time - last_heartbeat).total_seconds()

                    # If no heartbeat for 60 seconds, ping
                    if time_since_heartbeat > 60:
                        try:
                            await websocket.send_text(json.dumps({'type': 'ping'}))
                        except Exception as e:
                            logger.warning(f"Failed to ping connection: {e}")
                            dead_connections.append(websocket)
                            continue

                    # If no heartbeat for 300 seconds (5 minutes), close connection
                    if time_since_heartbeat > 300:
                        logger.warning(f"Connection timeout - no heartbeat for 5 minutes")
                        dead_connections.append(websocket)

                # Clean up dead connections
                for websocket in dead_connections:
                    await self.disconnect(websocket)

                await asyncio.sleep(30)  # Check every 30 seconds

            except Exception as e:
                logger.error(f"Error in heartbeat checker: {e}")
                await asyncio.sleep(30)

    async def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.connection_heartbeats:
            del self.connection_heartbeats[websocket]
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send a message to a specific WebSocket."""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            await self.disconnect(websocket)
    
    async def broadcast(self, message: str):
        """Broadcast a message to all connected WebSockets."""
        for connection in self.active_connections.copy():
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting to connection: {e}")
                await self.disconnect(connection)

    async def handle_message(self, websocket: WebSocket, message: str):
        """Handle incoming WebSocket messages from clients."""
        try:
            # Update heartbeat timestamp for this connection
            self.connection_heartbeats[websocket] = datetime.now()

            # Parse the message (expected to be JSON)
            import json
            data = json.loads(message)

            # Handle different message types
            msg_type = data.get('type', 'unknown')

            if msg_type == 'ping':
                # Respond to ping with pong to keep connection alive
                await websocket.send_text(json.dumps({'type': 'pong'}))
            elif msg_type == 'subscribe':
                # Handle subscription request
                channel = data.get('channel')
                product_id = data.get('product_id', self.config.product_id)
                if channel and product_id:
                    if channel not in self.subscriptions:
                        self.subscriptions[channel] = set()
                    self.subscriptions[channel].add(product_id)
                    logger.info(f"Subscribed to {channel} for {product_id}")
                    await websocket.send_text(json.dumps({
                        'type': 'subscribed',
                        'channel': channel,
                        'product_id': product_id
                    }))
            elif msg_type == 'unsubscribe':
                # Handle unsubscription request
                channel = data.get('channel')
                product_id = data.get('product_id', self.config.product_id)
                if channel and product_id and channel in self.subscriptions:
                    self.subscriptions[channel].discard(product_id)
                    if not self.subscriptions[channel]:
                        del self.subscriptions[channel]
                    logger.info(f"Unsubscribed from {channel} for {product_id}")
                    await websocket.send_text(json.dumps({
                        'type': 'unsubscribed',
                        'channel': channel,
                        'product_id': product_id
                    }))
            else:
                logger.warning(f"Unknown message type: {msg_type}")

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received: {message}")
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
    
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
                        await self._fetch_and_process_signals(symbols)

                # Wait before next check
                await asyncio.sleep(10)  # Check every 10 seconds for more responsive trading

            except Exception as e:
                logger.error(f"Error in simulated trading processing: {e}")
                await asyncio.sleep(10)  # Wait before retrying

    async def _fetch_and_process_signals(self, symbols):
        """Fetch live order book signals and process them automatically."""
        try:
            # Import data handlers to get signals
            from ..web_handlers.data_handlers import DataHandlers

            # Limit symbols to avoid API timeouts
            max_symbols = 50
            if len(symbols) > max_symbols:
                # Prioritize symbols that might have signals - could be improved with more logic
                symbols = symbols[:max_symbols]

            # Create data handler instance
            # We'll need to create a minimal config for this
            class MinimalConfig:
                def __init__(self):
                    self.max_symbols_per_request = 1000

            config = MinimalConfig()
            data_handler = DataHandlers(
                config=config,
                data_provider=None,
                cached_data_provider=None,
                database_manager=None,
                simulated_trading_manager=self.simulated_trading
            )

            # Get the signals string format
            symbols_str = ','.join(symbols)

            # Fetch live order book signals
            signals_response = await data_handler.get_live_orderbook_signals(symbols_str)

            if signals_response and signals_response.get('trading_active') and signals_response.get('signals'):
                signals = signals_response['signals']

                # Filter for active signals that should trigger trades
                active_signals = [
                    signal for signal in signals
                    if signal.get('signal_generated', False) and signal.get('signal') in ['buy', 'sell']
                ]

                if active_signals:
                    logger.info(f"Auto-processing {len(active_signals)} active signals: {[s['symbol'] + ':' + s['signal'] for s in active_signals]}")

                    # Process the signals through the simulated trading manager
                    result = await self.simulated_trading.process_signals(active_signals)

                    executed_trades = result.get('executed_trades', 0)
                    if executed_trades > 0:
                        logger.info(f"Auto-executed {executed_trades} trades from {len(active_signals)} signals")
                    else:
                        logger.debug(f"No trades executed from {len(active_signals)} active signals (may be due to position limits, existing positions, or insufficient funds)")

                    # Broadcast signals update to frontend order book signals widget
                    if result and 'portfolio' in result:
                        signal_data = {
                            "signals": result.get('signals', active_signals),  # Use processed results if available
                            "trading_active": True,
                            "message": f"Signals processed: {len(active_signals)} received, {executed_trades} trades executed",
                            "total_analyzed": self.simulated_trading.get_total_signals_processed(),
                            "active_signals": len([s for s in active_signals if s.get('signal_generated', False)]),
                            "last_updated": datetime.now().isoformat()
                        }

                        try:
                            await self.broadcast(json.dumps({
                                "type": "orderbook_signals_update",
                                "data": signal_data
                            }))
                            logger.debug(f"Broadcasted signal update with {len(active_signals)} signals")
                        except Exception as broadcast_error:
                            logger.warning(f"Failed to broadcast signal update: {broadcast_error}")

        except Exception as e:
            logger.error(f"Error fetching and processing signals: {e}")
    
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
    
    def get_active_subscriptions(self) -> List[Dict[str, Any]]:
        """Get active WebSocket subscriptions."""
        subscriptions = []
        for channel, product_ids in self.subscriptions.items():
            for product_id in product_ids:
                subscriptions.append({
                    "channel": channel,
                    "product_id": product_id
                })
        return subscriptions
    
    def get_connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self.active_connections)
    
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self.websocket_client is not None and self.websocket_client.running
    
    def get_active_channels(self) -> List[str]:
        """Get list of active channels."""
        return list(self.subscriptions.keys())
