"""WebSocket client for real-time market data and trading with full subscription support."""

import asyncio
import json
import logging
import time
import hmac
import hashlib
import base64
import random
from typing import Callable, Dict, Any, Optional, List, Set
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from ..core.config import TradingConfig


logger = logging.getLogger(__name__)


class WebSocketClient:
    """WebSocket client for Coinbase Advanced Trading with full subscription support."""
    
    # Available subscription channels per Coinbase documentation
    # https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/websocket/websocket-channels
    AVAILABLE_CHANNELS = {
        'heartbeats': 'Real-time server pings to keep all connections open',
        'ticker': 'Real-time price updates every time a match happens',
        'ticker_batch': 'Real-time price updates every 5000 milliseconds',
        'level2': 'All updates and easiest way to keep order book snapshot',
        'candles': 'Real-time updates on product candles',
        'status': 'Sends all products and currencies on a preset interval',
        'market_trades': 'Real-time updates every time a market trade happens',
        'user': 'Only sends messages that include the authenticated user (requires authentication)',
        'futures_balance_summary': 'Real-time updates every time a user\'s futures balance changes (requires authentication)'
    }
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.running = False
        self.message_handlers: Dict[str, Callable] = {}
        self.subscriptions: Dict[str, Set[str]] = {}  # channel -> set of product_ids
        self.authenticated = False
        
        # Use public WebSocket URL for most channels
        # For public channels, we should not need authentication
        self.public_websocket_url = "wss://advanced-trade-ws.coinbase.com"
        self.authenticated_websocket_url = "wss://advanced-trade-ws-user.coinbase.com"
        
        # Rate limiting per Coinbase documentation:
        # - WebSocket connections: 750 per second per IP address
        # - WebSocket messages: No specific limit mentioned in docs, using conservative approach
        # - REST API: 10,000 requests per hour per API key (handled separately in web_server.py)
        # Reference: https://docs.cdp.coinbase.com/coinbase-app/api-architecture/rate-limiting
        self.max_messages_per_second = 20  # Conservative limit for WebSocket messages
        self.message_timestamps: List[float] = []
        self.last_message_time = 0.0
        
        # Connection stability
        self.max_retries = 5
        self.retry_delay = 1.0  # Start with 1 second
        self.max_retry_delay = 60.0  # Max 60 seconds
        self.connection_attempts = 0
        
    def register_handler(self, message_type: str, handler: Callable) -> None:
        """Register a message handler for a specific message type."""
        self.message_handlers[message_type] = handler
    
    async def _rate_limit_check(self) -> None:
        """Check and enforce rate limiting per Coinbase documentation."""
        current_time = time.time()
        
        # Remove timestamps older than 1 second
        self.message_timestamps = [ts for ts in self.message_timestamps if current_time - ts < 1.0]
        
        # If we're at the limit, wait
        if len(self.message_timestamps) >= self.max_messages_per_second:
            sleep_time = 1.0 - (current_time - self.message_timestamps[0])
            if sleep_time > 0:
                logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
                await asyncio.sleep(sleep_time)
                # Clean up timestamps again after sleep
                current_time = time.time()
                self.message_timestamps = [ts for ts in self.message_timestamps if current_time - ts < 1.0]
        
        # Add current timestamp
        self.message_timestamps.append(current_time)
        self.last_message_time = current_time
    
    async def _resubscribe_all(self) -> None:
        """Resubscribe to all previous subscriptions after reconnection."""
        if not self.subscriptions:
            return
            
        logger.info("Resubscribing to previous channels after reconnection...")
        for channel, product_ids in self.subscriptions.items():
            try:
                await self.subscribe_to_channel(channel, list(product_ids))
                # Add a small delay between subscriptions to respect rate limits
                await asyncio.sleep(0.2)
            except Exception as e:
                logger.error(f"Failed to resubscribe to {channel}: {e}")
        
    async def connect(self) -> None:
        """Connect to the WebSocket with retry logic and rate limiting."""
        retry_count = 0
        
        while retry_count < self.max_retries:
            try:
                # Add jitter to prevent thundering herd
                if retry_count > 0:
                    jitter = random.uniform(0.1, 0.5)
                    delay = min(self.retry_delay * (2 ** retry_count) + jitter, self.max_retry_delay)
                    logger.info(f"Retrying connection in {delay:.2f} seconds (attempt {retry_count + 1}/{self.max_retries})")
                    await asyncio.sleep(delay)
                
                # Use public WebSocket URL for public channels
                self.websocket = await websockets.connect(
                    self.public_websocket_url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=10
                )
                logger.info(f"Connected to {self.public_websocket_url}")
                self.running = True
                self.authenticated = True  # Public channels don't need auth
                self.connection_attempts = 0  # Reset on successful connection
                return

            except Exception as e:
                retry_count += 1
                self.connection_attempts += 1
                logger.warning(f"Connection attempt {retry_count} failed: {e}")
                
                if retry_count >= self.max_retries:
                    logger.error(f"Failed to connect after {self.max_retries} attempts: {e}")
                    raise
    
    async def disconnect(self) -> None:
        """Disconnect from the WebSocket."""
        self.running = False
        if self.websocket:
            await self.websocket.close()
            logger.info("Disconnected from WebSocket")
    
    def _generate_jwt_token(self) -> str:
        """Generate JWT token for Coinbase Advanced Trading authentication.
        
        Note: This is a simplified implementation. For production use, 
        implement proper ES256 signature with the private key as shown in:
        https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/websocket/websocket-authentication
        """
        # Create JWT header
        header = {
            "alg": "ES256",
            "typ": "JWT"
        }
        
        # Create JWT payload
        now = int(time.time())
        payload = {
            "sub": self.config.api_key,
            "iss": "coinbase-cloud",
            "nbf": now,
            "exp": now + 120,  # 2 minutes expiration
            "aud": ["retail_websocket_api"]
        }
        
        # Encode header and payload
        header_encoded = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
        payload_encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
        
        # Create signature
        message = f"{header_encoded}.{payload_encoded}"
        
        # For now, we'll use HMAC-SHA256 instead of ES256 for simplicity
        # In production, you'd need to implement proper ES256 with private key
        signature = hmac.new(
            self.config.api_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).digest()
        
        signature_encoded = base64.urlsafe_b64encode(signature).decode().rstrip('=')
        
        return f"{message}.{signature_encoded}"
    
    async def authenticate(self) -> None:
        """Authenticate with the WebSocket using JWT token."""
        if not self.websocket:
            raise RuntimeError("WebSocket not connected")
            
        try:
            # Generate JWT token
            jwt_token = self._generate_jwt_token()
            
            # Send authentication message (not a subscription)
            auth_message = {
                "type": "authenticate",
                "jwt": jwt_token
            }
            
            await self.websocket.send(json.dumps(auth_message))
            logger.info("Authentication request sent")
            
            # Wait for authentication response
            await asyncio.sleep(1)  # Give time for response
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            self.authenticated = False
            raise
    
    async def subscribe_to_channel(self, channel: str, product_ids: List[str]) -> None:
        """Subscribe to a specific channel for given product IDs with rate limiting."""
        if not self.websocket:
            raise RuntimeError("WebSocket not connected")
            
        if channel not in self.AVAILABLE_CHANNELS:
            raise ValueError(f"Unknown channel: {channel}. Available: {list(self.AVAILABLE_CHANNELS.keys())}")
        
        # Check if authentication is required for user channels
        if channel == 'user' and not self.authenticated:
            logger.warning("User channel requires authentication - skipping")
            return
        
        # Apply rate limiting per Coinbase documentation
        await self._rate_limit_check()
            
        # Use the correct subscription format for Coinbase Advanced Trading public channels
        # Based on: https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/websocket/websocket-channels
        if channel == "heartbeats":
            # Heartbeats channel doesn't require product_ids
            subscribe_message = {
                "type": "subscribe",
                "channel": "heartbeats"
            }
            # Track heartbeats subscription with a special marker
            if channel not in self.subscriptions:
                self.subscriptions[channel] = set()
            self.subscriptions[channel].add("heartbeat")  # Special marker for heartbeats
        else:
            subscribe_message = {
                "type": "subscribe",
                "product_ids": product_ids,
                "channel": channel
            }
        
        try:
            await self.websocket.send(json.dumps(subscribe_message))
            
            # Track subscriptions (we'll update this when we get confirmation)
            if channel not in self.subscriptions:
                self.subscriptions[channel] = set()
            self.subscriptions[channel].update(product_ids)
            
            logger.info(f"Subscription request sent for {channel} and {product_ids}")
        except Exception as e:
            logger.error(f"Failed to send subscription request for {channel}: {e}")
            raise
    
    async def unsubscribe_from_channel(self, channel: str, product_ids: List[str]) -> None:
        """Unsubscribe from a specific channel for given product IDs with rate limiting."""
        if not self.websocket:
            raise RuntimeError("WebSocket not connected")
        
        # Apply rate limiting per Coinbase documentation
        await self._rate_limit_check()
            
        # Use the correct unsubscribe format for Coinbase Advanced Trading public channels
        unsubscribe_message = {
            "type": "unsubscribe",
            "product_ids": product_ids,
            "channel": channel
        }
        
        await self.websocket.send(json.dumps(unsubscribe_message))
        
        # Update subscription tracking
        if channel in self.subscriptions:
            self.subscriptions[channel].difference_update(product_ids)
            if not self.subscriptions[channel]:
                del self.subscriptions[channel]
        
        logger.info(f"Unsubscribed from {channel} for {product_ids}")
    
    async def subscribe_to_ticker(self, product_id: str) -> None:
        """Subscribe to ticker updates for a product."""
        await self.subscribe_to_channel('ticker', [product_id])
    
    async def subscribe_to_level2(self, product_id: str) -> None:
        """Subscribe to level2 order book updates."""
        await self.subscribe_to_channel('level2', [product_id])
    
    async def subscribe_to_candles(self, product_id: str) -> None:
        """Subscribe to candlestick data for a product."""
        await self.subscribe_to_channel('candles', [product_id])
    
    async def subscribe_to_matches(self, product_id: str) -> None:
        """Subscribe to trade matches for a product."""
        await self.subscribe_to_channel('matches', [product_id])
    
    async def subscribe_to_status(self, product_id: str) -> None:
        """Subscribe to product status updates."""
        await self.subscribe_to_channel('status', [product_id])
    
    async def subscribe_to_market_trades(self, product_id: str) -> None:
        """Subscribe to market trades feed."""
        await self.subscribe_to_channel('market_trades', [product_id])
    
    async def subscribe_to_all_channels(self, product_id: str) -> None:
        """Subscribe to all available channels for a product."""
        for channel in self.AVAILABLE_CHANNELS.keys():
            if channel != 'user':  # Skip user channel as it requires auth
                try:
                    await self.subscribe_to_channel(channel, [product_id])
                except Exception as e:
                    logger.error(f"Failed to subscribe to {channel}: {e}")
    
    async def get_subscription_info(self) -> Dict[str, Any]:
        """Get information about current subscriptions."""
        # Check if we have an active WebSocket connection
        is_connected = (self.websocket is not None and 
                       not self.websocket.closed and 
                       self.running)
        
        return {
            'channels': dict(self.subscriptions),
            'available_channels': self.AVAILABLE_CHANNELS,
            'authenticated': self.authenticated,
            'connected': is_connected,
            'connection_status': 'connected' if is_connected else 'disconnected',
            'websocket_url': self.public_websocket_url if is_connected else None
        }
    
    async def listen(self) -> None:
        """Listen for incoming messages with auto-reconnect."""
        while self.running:
            try:
                if not self.websocket or self.websocket.closed:
                    await self.connect()
                    # Resubscribe to all previous subscriptions after reconnection
                    await self._resubscribe_all()
                
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
                logger.warning("WebSocket connection closed, attempting to reconnect...")
                self.websocket = None
                if self.running:
                    await asyncio.sleep(2)  # Shorter wait for faster reconnection
                    continue
                    
            except WebSocketException as e:
                logger.error(f"WebSocket error: {e}")
                self.websocket = None
                if self.running:
                    await asyncio.sleep(10)  # Wait longer for WebSocket errors
                    continue
                    
            except Exception as e:
                logger.error(f"Unexpected error in listen loop: {e}")
                self.websocket = None
                if self.running:
                    await asyncio.sleep(15)  # Wait even longer for unexpected errors
                    continue
    
    async def _handle_message(self, data: Dict[str, Any]) -> None:
        """Handle incoming WebSocket messages per Coinbase documentation format."""
        message_type = data.get("type", "unknown")
        channel = data.get("channel", "unknown")
        
        # Log subscription confirmations
        if message_type == "subscriptions":
            channels = data.get("channels", [])
            logger.info(f"Subscription confirmed for channels: {channels}")
            return
        
        # Handle authentication responses
        if message_type == "authenticated":
            logger.info("Authentication successful")
            self.authenticated = True
            return
        
        # Handle error messages
        if message_type == "error":
            error_message = data.get("message", "Unknown error")
            if "authentication failure" in error_message.lower():
                logger.warning(f"Authentication error for channel - this may be expected for some channels: {data}")
                # Don't treat authentication errors as fatal for public channels
                return
            else:
                logger.error(f"WebSocket error: {data}")
                return
        
        # Handle heartbeats - critical for keeping connections alive
        if channel == "heartbeats":
            logger.debug(f"Heartbeat received: {data}")
            # Update connection status when we receive heartbeats
            self.authenticated = True
            return
        
        # Route to appropriate handler based on channel
        if channel in self.message_handlers:
            try:
                await self.message_handlers[channel](data)
            except Exception as e:
                logger.error(f"Error in message handler for channel {channel}: {e}")
        else:
            logger.debug(f"No handler for channel: {channel}, message: {message_type}")
    
    async def run(self) -> None:
        """Run the WebSocket client with all subscriptions."""
        try:
            await self.connect()
            
            # Subscribe to all available channels for the configured product
            await self.subscribe_to_all_channels(self.config.product_id)
            
            await self.listen()
        except Exception as e:
            logger.error(f"WebSocket client error: {e}")
            raise
        finally:
            await self.disconnect()
