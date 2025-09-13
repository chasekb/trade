"""Detailed websocket test with enhanced logging."""

import asyncio
import logging
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from trade_bot.config import TradingConfig
from trade_bot.websocket_client import WebSocketClient


def setup_logging():
    """Setup detailed logging for the test."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


async def test_websocket_detailed():
    """Test websocket connection with detailed logging."""
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
            return False
        
        # Create websocket client
        websocket_client = WebSocketClient(config)
        
        # Message counters
        ticker_count = 0
        level2_count = 0
        
        # Register message handlers with counters
        async def handle_ticker(data):
            nonlocal ticker_count
            ticker_count += 1
            logger.info(f"📊 TICKER #{ticker_count}: {data}")
        
        async def handle_level2(data):
            nonlocal level2_count
            level2_count += 1
            logger.info(f"📈 LEVEL2 #{level2_count}: {data}")
        
        websocket_client.register_handler("ticker", handle_ticker)
        websocket_client.register_handler("l2update", handle_level2)
        
        logger.info("🔌 Connecting to Coinbase WebSocket...")
        
        # Connect and listen for 60 seconds
        try:
            await websocket_client.connect()
            logger.info("✅ Connected successfully!")
            
            await websocket_client.subscribe_to_ticker(config.product_id)
            logger.info(f"📡 Subscribed to ticker for {config.product_id}")
            
            await websocket_client.subscribe_to_level2(config.product_id)
            logger.info(f"📡 Subscribed to level2 for {config.product_id}")
            
            logger.info("🎧 Listening for live data for 60 seconds...")
            logger.info("Press Ctrl+C to stop early")
            
            # Listen for 60 seconds
            await asyncio.wait_for(websocket_client.listen(), timeout=60.0)
            
        except asyncio.TimeoutError:
            logger.info("⏰ 60 seconds elapsed, stopping...")
        except KeyboardInterrupt:
            logger.info("🛑 Stopped by user")
        finally:
            await websocket_client.disconnect()
            logger.info("🔌 Disconnected from WebSocket")
            
        # Report results
        logger.info(f"📊 Total ticker messages received: {ticker_count}")
        logger.info(f"📈 Total level2 messages received: {level2_count}")
        logger.info(f"📨 Total messages received: {ticker_count + level2_count}")
        
        if ticker_count + level2_count == 0:
            logger.warning("⚠️  No messages received. This could mean:")
            logger.warning("   - Market is quiet")
            logger.warning("   - Subscription parameters need adjustment")
            logger.warning("   - Network connectivity issues")
        else:
            logger.info("✅ Successfully received live market data!")
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    print("🧪 Testing Coinbase WebSocket connection with detailed logging...")
    print("This will run for 60 seconds to capture more data")
    print()
    
    success = asyncio.run(test_websocket_detailed())
    
    if success:
        print("\n✅ WebSocket test completed!")
    else:
        print("\n❌ WebSocket test failed!")
        sys.exit(1)
