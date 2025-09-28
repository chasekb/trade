"""Test script to check websocket connection with live data."""

import asyncio
import logging
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.trade_bot.config import TradingConfig
from src.trade_bot.websocket_client import WebSocketClient


def setup_logging():
    """Setup logging for the test."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


async def test_websocket_connection():
    """Test websocket connection with live data."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config = TradingConfig.from_env()
        logger.info(f"Loaded configuration for {config.product_id}")
        
        # Check if we have all required credentials
        if not config.api_key or not config.api_secret or not config.passphrase:
            logger.error("Missing API credentials. Please check your .env file.")
            logger.error("Required: COINBASE_API_KEY, COINBASE_API_SECRET, COINBASE_PASSPHRASE")
            return
        
        # Create websocket client
        websocket_client = WebSocketClient(config)
        
        # Register a simple message handler
        async def handle_ticker(data):
            logger.info(f"Ticker data: {data}")
        
        async def handle_level2(data):
            logger.info(f"Level2 data: {data}")
        
        websocket_client.register_handler("ticker", handle_ticker)
        websocket_client.register_handler("l2update", handle_level2)
        
        logger.info("Connecting to Coinbase WebSocket...")
        
        # Connect and listen for 30 seconds
        try:
            await websocket_client.connect()
            await websocket_client.subscribe_to_ticker(config.product_id)
            await websocket_client.subscribe_to_level2(config.product_id)
            
            logger.info("Connected! Listening for live data for 30 seconds...")
            logger.info("Press Ctrl+C to stop early")
            
            # Listen for 30 seconds
            await asyncio.wait_for(websocket_client.listen(), timeout=30.0)
            
        except asyncio.TimeoutError:
            logger.info("30 seconds elapsed, stopping...")
        except KeyboardInterrupt:
            logger.info("Stopped by user")
        finally:
            await websocket_client.disconnect()
            logger.info("Disconnected from WebSocket")
            
    except Exception as e:
        logger.error(f"Error: {e}")
        return False
    
    return True


if __name__ == "__main__":
    print("Testing Coinbase WebSocket connection with live data...")
    print("Make sure you have set COINBASE_PASSPHRASE in your .env file")
    print()
    
    success = asyncio.run(test_websocket_connection())
    
    if success:
        print("\n✅ WebSocket test completed successfully!")
    else:
        print("\n❌ WebSocket test failed!")
        sys.exit(1)
