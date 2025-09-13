"""WebSocket client for real-time market data and trading."""

import asyncio
import json
import logging
from typing import Callable, Dict, Any, Optional
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from .config import TradingConfig


logger = logging.getLogger(__name__)


class WebSocketClient:
    """WebSocket client for Coinbase Advanced Trading."""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.running = False
        self.message_handlers: Dict[str, Callable] = {}
        
    def register_handler(self, message_type: str, handler: Callable) -> None:
        """Register a message handler for a specific message type."""
        self.message_handlers[message_type] = handler
        
    async def connect(self) -> None:
        """Connect to the WebSocket."""
        try:
            self.websocket = await websockets.connect(
                self.config.websocket_url,
                ping_interval=20,
                ping_timeout=10
            )
            logger.info(f"Connected to {self.config.websocket_url}")
            self.running = True
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from the WebSocket."""
        self.running = False
        if self.websocket:
            await self.websocket.close()
            logger.info("Disconnected from WebSocket")
    
    async def subscribe_to_ticker(self, product_id: str) -> None:
        """Subscribe to ticker updates for a product."""
        if not self.websocket:
            raise RuntimeError("WebSocket not connected")
            
        subscribe_message = {
            "type": "subscribe",
            "product_ids": [product_id],
            "channels": ["ticker"]
        }
        
        await self.websocket.send(json.dumps(subscribe_message))
        logger.info(f"Subscribed to ticker for {product_id}")
    
    async def subscribe_to_level2(self, product_id: str) -> None:
        """Subscribe to level2 order book updates."""
        if not self.websocket:
            raise RuntimeError("WebSocket not connected")
            
        subscribe_message = {
            "type": "subscribe",
            "product_ids": [product_id],
            "channels": ["level2"]
        }
        
        await self.websocket.send(json.dumps(subscribe_message))
        logger.info(f"Subscribed to level2 for {product_id}")
    
    async def listen(self) -> None:
        """Listen for incoming messages."""
        if not self.websocket:
            raise RuntimeError("WebSocket not connected")
            
        try:
            async for message in self.websocket:
                if not self.running:
                    break
                    
                try:
                    data = json.loads(message)
                    await self._handle_message(data)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse message: {e}")
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
                    
        except ConnectionClosed:
            logger.info("WebSocket connection closed")
        except WebSocketException as e:
            logger.error(f"WebSocket error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in listen loop: {e}")
    
    async def _handle_message(self, data: Dict[str, Any]) -> None:
        """Handle incoming WebSocket messages."""
        message_type = data.get("type", "unknown")
        
        if message_type in self.message_handlers:
            try:
                await self.message_handlers[message_type](data)
            except Exception as e:
                logger.error(f"Error in message handler for {message_type}: {e}")
        else:
            logger.debug(f"No handler for message type: {message_type}")
    
    async def run(self) -> None:
        """Run the WebSocket client."""
        try:
            await self.connect()
            await self.subscribe_to_ticker(self.config.product_id)
            await self.subscribe_to_level2(self.config.product_id)
            await self.listen()
        except Exception as e:
            logger.error(f"WebSocket client error: {e}")
            raise
        finally:
            await self.disconnect()
