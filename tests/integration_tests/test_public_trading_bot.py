"""Test trading bot with public websocket feed."""

import asyncio
import logging
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from trade_bot.config import TradingConfig
from trade_bot.trading_strategy import SimpleMovingAverageStrategy
from trade_bot.data_handler import DataHandler
import websockets


def setup_logging():
    """Setup logging for the test."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


async def test_public_trading_bot():
    """Test trading bot with public websocket feed."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config = TradingConfig.from_env()
        logger.info(f"🤖 Starting trading bot for {config.product_id}")
        
        # Create strategy and data handler
        strategy = SimpleMovingAverageStrategy(config, short_window=3, long_window=5)
        data_handler = DataHandler(config)
        
        # Public websocket URL
        websocket_url = "wss://ws-feed.exchange.coinbase.com"
        
        logger.info(f"🔌 Connecting to public WebSocket: {websocket_url}")
        
        async with websockets.connect(websocket_url) as websocket:
            logger.info("✅ Connected to public WebSocket!")
            
            # Subscribe to ticker for BTC-USD
            subscribe_message = {
                "type": "subscribe",
                "product_ids": [config.product_id],
                "channels": ["ticker"]
            }
            
            await websocket.send(json.dumps(subscribe_message))
            logger.info(f"📡 Subscribed to ticker for {config.product_id}")
            
            # Listen for messages for 30 seconds
            logger.info("🎧 Listening for live data for 30 seconds...")
            logger.info("Press Ctrl+C to stop early")
            
            message_count = 0
            signal_count = 0
            
            try:
                async for message in websocket:
                    data = json.loads(message)
                    message_count += 1
                    
                    if data.get("type") == "ticker":
                        price = float(data.get('price', 0))
                        volume = float(data.get('volume_24h', 0))
                        
                        logger.info(f"📊 TICKER #{message_count}: Price=${price:,.2f} Volume={volume:,.2f}")
                        
                        # Add data to handler
                        data_handler.add_ticker_data(data)
                        
                        # Generate trading signal
                        from datetime import datetime
                        signal = strategy.generate_signal(price, datetime.now())
                        
                        if signal:
                            signal_count += 1
                            logger.info(f"🎯 SIGNAL #{signal_count}: {signal.action.upper()} at ${signal.price:,.2f} - {signal.reason}")
                            
                            # Add signal to handler
                            signal_data = {
                                'timestamp': signal.timestamp.isoformat(),
                                'action': signal.action,
                                'price': signal.price,
                                'quantity': signal.quantity,
                                'reason': signal.reason,
                                'product_id': config.product_id
                            }
                            data_handler.add_signal_data(signal_data)
                            
                            # Update strategy position
                            strategy.update_position(signal)
                            
                        # Show current position
                        position_info = strategy.get_position_info()
                        if position_info['position'] > 0:
                            logger.info(f"💼 Position: {position_info['position']:.6f} BTC @ ${position_info['entry_price']:,.2f}")
                    
                    elif data.get("type") == "subscriptions":
                        logger.info(f"✅ SUBSCRIPTION CONFIRMED: {data}")
                    
                    # Stop after 30 seconds or 50 messages
                    if message_count >= 50:
                        logger.info("📊 Reached 50 messages, stopping...")
                        break
                        
            except asyncio.TimeoutError:
                logger.info("⏰ Timeout reached")
            except KeyboardInterrupt:
                logger.info("🛑 Stopped by user")
                
        # Save all data
        files = data_handler.save_all_data()
        logger.info(f"💾 Saved data files: {files}")
        
        # Get summary stats
        stats = data_handler.get_summary_stats()
        logger.info(f"📊 Summary: {stats}")
        
        logger.info(f"📊 Total messages received: {message_count}")
        logger.info(f"🎯 Total signals generated: {signal_count}")
        
        if message_count == 0:
            logger.warning("⚠️  No messages received")
        else:
            logger.info("✅ Successfully processed live market data!")
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    print("🤖 Testing Trading Bot with Public WebSocket Feed...")
    print("This will process live market data and generate trading signals")
    print()
    
    success = asyncio.run(test_public_trading_bot())
    
    if success:
        print("\n✅ Trading bot test completed!")
    else:
        print("\n❌ Trading bot test failed!")
        sys.exit(1)
