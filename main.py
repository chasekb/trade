"""Main entry point for the trading bot.

This script provides the main entry point for running the trading bot.
It supports both command-line arguments and environment variable configuration.

Usage:
    python main.py                          # Run with default settings
    python main.py --product ETH-USD        # Run with specific product
    python main.py --max-position 2000      # Run with custom position size
    python main.py --log-level DEBUG        # Run with debug logging
"""

import argparse
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


def setup_logging(log_level: str = "INFO") -> None:
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('outputs/trading_bot.log')
        ]
    )


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Advanced Trading Bot")
    parser.add_argument(
        "--product", 
        type=str, 
        help="Trading product ID (e.g., BTC-USD, ETH-USD)"
    )
    parser.add_argument(
        "--max-position", 
        type=float, 
        help="Maximum position size in USD"
    )
    parser.add_argument(
        "--stop-loss", 
        type=float, 
        help="Stop loss percentage (e.g., 0.02 for 2%)"
    )
    parser.add_argument(
        "--take-profit", 
        type=float, 
        help="Take profit percentage (e.g., 0.04 for 4%)"
    )
    parser.add_argument(
        "--log-level", 
        type=str, 
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )
    parser.add_argument(
        "--output-dir", 
        type=str, 
        help="Output directory for logs and data"
    )
    return parser.parse_args()


async def main():
    """Main function."""
    # Parse command line arguments
    args = parse_arguments()
    
    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config = TradingConfig.from_env()
        
        # Override with command line arguments
        if args.product:
            config.product_id = args.product
        if args.max_position:
            config.max_position_size = args.max_position
        if args.stop_loss:
            config.stop_loss_percentage = args.stop_loss
        if args.take_profit:
            config.take_profit_percentage = args.take_profit
        if args.output_dir:
            config.output_dir = args.output_dir
        
        logger.info("🚀 Starting Advanced Trading Bot")
        logger.info(f"📊 Product: {config.product_id}")
        logger.info(f"💰 Max Position: ${config.max_position_size:,.2f}")
        logger.info(f"🛡️ Stop Loss: {config.stop_loss_percentage:.1%}")
        logger.info(f"🎯 Take Profit: {config.take_profit_percentage:.1%}")
        logger.info(f"📁 Output Directory: {config.output_dir}")
        
        # Create and start bot
        bot = TradingBot(config)
        await bot.start()
        
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())