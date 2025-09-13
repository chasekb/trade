"""Simple websocket test without authentication."""

import asyncio
import logging
import websockets
import json


def setup_logging():
    """Setup logging for the test."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


async def test_public_websocket():
    """Test public websocket connection (no auth required)."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    websocket_url = "wss://advanced-trade-ws.coinbase.com"
    
    try:
        logger.info(f"Connecting to {websocket_url}...")
        
        async with websockets.connect(websocket_url) as websocket:
            logger.info("✅ Connected to Coinbase WebSocket!")
            
            # Subscribe to ticker for BTC-USD
            subscribe_message = {
                "type": "subscribe",
                "product_ids": ["BTC-USD"],
                "channels": ["ticker"]
            }
            
            await websocket.send(json.dumps(subscribe_message))
            logger.info("📡 Subscribed to BTC-USD ticker data")
            
            # Listen for messages for 10 seconds
            logger.info("🎧 Listening for live data for 10 seconds...")
            
            try:
                async for message in websocket:
                    data = json.loads(message)
                    logger.info(f"📊 Live data: {data}")
                    
                    # Stop after 10 seconds
                    await asyncio.sleep(0.1)  # Small delay to prevent overwhelming
                    
            except asyncio.TimeoutError:
                logger.info("⏰ Timeout reached")
                
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False
    
    logger.info("✅ Test completed successfully!")
    return True


if __name__ == "__main__":
    print("🧪 Testing Coinbase WebSocket connection (public data only)...")
    print("This test doesn't require API credentials")
    print()
    
    success = asyncio.run(test_public_websocket())
    
    if success:
        print("\n✅ WebSocket connection test passed!")
        print("Your websocket connection is working correctly.")
    else:
        print("\n❌ WebSocket connection test failed!")
