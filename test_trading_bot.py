"""Test the full trading bot with live data."""

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
from trade_bot.trading_bot import TradingBot


def setup_logging():
    """Setup logging for the test."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


async def test_trading_bot():
    """Test the full trading bot with live data."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config = TradingConfig.from_env()
        logger.info(f"🤖 Starting trading bot for {config.product_id}")
        
        # Create trading bot
        bot = TradingBot(config)
        
        # Get initial status
        status = bot.get_status()
        logger.info(f"📊 Initial status: {status}")
        
        logger.info("🚀 Starting bot for 30 seconds...")
        logger.info("Press Ctrl+C to stop early")
        
        # Start the bot for 30 seconds
        try:
            # Create a task that will run the bot
            bot_task = asyncio.create_task(bot.start())
            
            # Wait for 30 seconds or until the task completes
            await asyncio.wait_for(bot_task, timeout=30.0)
            
        except asyncio.TimeoutError:
            logger.info("⏰ 30 seconds elapsed, stopping bot...")
            bot.running = False
        except KeyboardInterrupt:
            logger.info("🛑 Stopped by user")
            bot.running = False
        finally:
            await bot.stop()
            
        # Get final status
        final_status = bot.get_status()
        logger.info(f"📊 Final status: {final_status}")
        
        logger.info("✅ Trading bot test completed!")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    print("🤖 Testing Full Trading Bot with Live Data...")
    print("This will run the complete trading bot for 30 seconds")
    print()
    
    success = asyncio.run(test_trading_bot())
    
    if success:
        print("\n✅ Trading bot test completed!")
    else:
        print("\n❌ Trading bot test failed!")
        sys.exit(1)
