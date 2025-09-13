"""Test public websocket feed (no authentication required)."""

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
    
    # Use the public websocket feed
    websocket_url = "wss://ws-feed.exchange.coinbase.com"
    
    try:
        logger.info(f"🔌 Connecting to public Coinbase WebSocket: {websocket_url}")
        
        async with websockets.connect(websocket_url) as websocket:
            logger.info("✅ Connected to public Coinbase WebSocket!")
            
            # Subscribe to ticker for BTC-USD (public feed)
            subscribe_message = {
                "type": "subscribe",
                "product_ids": ["BTC-USD"],
                "channels": ["ticker", "level2"]
            }
            
            await websocket.send(json.dumps(subscribe_message))
            logger.info("📡 Subscribed to BTC-USD ticker and level2 data")
            
            # Listen for messages for 30 seconds
            logger.info("🎧 Listening for live data for 30 seconds...")
            logger.info("Press Ctrl+C to stop early")
            
            message_count = 0
            
            try:
                async for message in websocket:
                    data = json.loads(message)
                    message_count += 1
                    
                    if data.get("type") == "ticker":
                        logger.info(f"📊 TICKER #{message_count}: Price=${data.get('price', 'N/A')} Volume={data.get('volume_24h', 'N/A')}")
                    elif data.get("type") == "l2update":
                        logger.info(f"📈 LEVEL2 #{message_count}: {data}")
                    elif data.get("type") == "subscriptions":
                        logger.info(f"✅ SUBSCRIPTION CONFIRMED: {data}")
                    else:
                        logger.info(f"📨 MESSAGE #{message_count}: {data}")
                    
                    # Stop after 30 seconds
                    if message_count >= 50:  # Limit to 50 messages for readability
                        logger.info("📊 Reached 50 messages, stopping...")
                        break
                        
            except asyncio.TimeoutError:
                logger.info("⏰ Timeout reached")
            except KeyboardInterrupt:
                logger.info("🛑 Stopped by user")
                
        logger.info(f"📊 Total messages received: {message_count}")
        
        if message_count == 0:
            logger.warning("⚠️  No messages received. This could mean:")
            logger.warning("   - Market is quiet")
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
    print("🧪 Testing Coinbase Public WebSocket connection...")
    print("This uses the public feed (no authentication required)")
    print()
    
    success = asyncio.run(test_public_websocket())
    
    if success:
        print("\n✅ Public WebSocket test completed!")
    else:
        print("\n❌ Public WebSocket test failed!")
