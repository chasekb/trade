"""Backtesting CLI script for trading strategies."""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from trade_bot.config import TradingConfig
from trade_bot.backtester import Backtester
from trade_bot.trading_strategy import SimpleMovingAverageStrategy
from trade_bot.data_provider import CoinbaseDataProvider, MockDataProvider


def setup_logging():
    """Setup logging for the backtest."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def print_backtest_results(result):
    """Print backtest results in a formatted way."""
    print("\n" + "="*60)
    print("📊 BACKTEST RESULTS")
    print("="*60)
    
    print(f"📅 Period: {result.start_date.strftime('%Y-%m-%d')} to {result.end_date.strftime('%Y-%m-%d')}")
    print(f"💰 Initial Balance: ${result.initial_balance:,.2f}")
    print(f"💰 Final Balance: ${result.final_balance:,.2f}")
    print(f"📈 Total Return: {result.total_return:.2%}")
    print(f"💵 Net Profit: ${result.net_profit:,.2f}")
    print(f"💸 Total Fees: ${result.total_fees:,.2f}")
    
    print("\n📊 TRADE STATISTICS")
    print("-" * 30)
    print(f"Total Trades: {result.total_trades}")
    print(f"Winning Trades: {result.winning_trades}")
    print(f"Losing Trades: {result.losing_trades}")
    print(f"Win Rate: {result.win_rate:.1%}")
    
    print("\n💰 PROFIT/LOSS ANALYSIS")
    print("-" * 30)
    print(f"Average Win: ${result.avg_win:,.2f}")
    print(f"Average Loss: ${result.avg_loss:,.2f}")
    print(f"Largest Win: ${result.largest_win:,.2f}")
    print(f"Largest Loss: ${result.largest_loss:,.2f}")
    print(f"Profit Factor: {result.profit_factor:.2f}")
    
    print("\n📉 RISK METRICS")
    print("-" * 30)
    print(f"Max Drawdown: {result.max_drawdown:.2%}")
    print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
    
    print("="*60)


async def run_backtest():
    """Run a backtest with the SMA strategy."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config = TradingConfig.from_env()
        logger.info(f"Starting backtest for {config.product_id}")
        
        # Always use real Coinbase data
        data_provider = CoinbaseDataProvider(config.product_id)
        logger.info("Using real Coinbase data")
        
        # Define backtest period (last 7 days to avoid API limits)
        end_time = datetime.now()
        start_time = end_time - timedelta(days=7)
        
        # Get historical data
        logger.info(f"Fetching data from {start_time} to {end_time}")
        historical_data = await data_provider.get_historical_candles(
            start_time=start_time,
            end_time=end_time,
            granularity=3600  # 1-hour candles
        )
        
        if not historical_data:
            logger.error("No historical data available")
            # Try with a shorter period
            logger.info("Trying with 3 days of data...")
            start_time = end_time - timedelta(days=3)
            historical_data = await data_provider.get_historical_candles(
                start_time=start_time,
                end_time=end_time,
                granularity=3600
            )
            
            if not historical_data:
                logger.error("Still no data available. Check your internet connection and API access.")
                return False
        
        logger.info(f"Retrieved {len(historical_data)} data points")
        
        # Define strategy parameters
        strategy_params = {
            'short_window': 5,
            'long_window': 20
        }
        
        # Create backtester
        backtester = Backtester(
            config=config,
            strategy_class=SimpleMovingAverageStrategy,
            strategy_params=strategy_params
        )
        
        # Run backtest
        logger.info("Running backtest...")
        result = await backtester.run_backtest(historical_data)
        
        # Print results
        print_backtest_results(result)
        
        # Save detailed results
        trades_df = backtester.get_trades_df()
        equity_df = backtester.get_equity_curve_df()
        
        if not trades_df.empty:
            trades_file = f"backtest_trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            trades_df.to_csv(trades_file)
            logger.info(f"Saved trades to {trades_file}")
        
        if not equity_df.empty:
            equity_file = f"backtest_equity_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            equity_df.to_csv(equity_file)
            logger.info(f"Saved equity curve to {equity_file}")
        
        return True
        
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_parameter_optimization():
    """Run parameter optimization for the SMA strategy."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config = TradingConfig.from_env()
        
        # Use real data for optimization
        data_provider = CoinbaseDataProvider(config.product_id)
        
        # Define backtest period
        end_time = datetime.now()
        start_time = end_time - timedelta(days=3)  # 3 days for optimization
        
        # Get historical data
        historical_data = await data_provider.get_historical_candles(
            start_time=start_time,
            end_time=end_time,
            granularity=3600
        )
        
        if not historical_data:
            logger.error("No historical data available")
            return False
        
        # Test different parameter combinations
        short_windows = [3, 5, 10, 15]
        long_windows = [10, 20, 30, 50]
        
        best_result = None
        best_return = -float('inf')
        best_params = None
        
        print("\n🔍 PARAMETER OPTIMIZATION")
        print("="*60)
        
        for short_window in short_windows:
            for long_window in long_windows:
                if short_window >= long_window:
                    continue
                
                logger.info(f"Testing SMA({short_window}, {long_window})")
                
                # Create backtester
                backtester = Backtester(
                    config=config,
                    strategy_class=SimpleMovingAverageStrategy,
                    strategy_params={
                        'short_window': short_window,
                        'long_window': long_window
                    }
                )
                
                # Run backtest
                result = await backtester.run_backtest(historical_data)
                
                print(f"SMA({short_window:2d}, {long_window:2d}): "
                      f"Return: {result.total_return:6.2%}, "
                      f"Trades: {result.total_trades:3d}, "
                      f"Win Rate: {result.win_rate:5.1%}, "
                      f"Sharpe: {result.sharpe_ratio:5.2f}")
                
                if result.total_return > best_return:
                    best_return = result.total_return
                    best_result = result
                    best_params = (short_window, long_window)
        
        print("\n🏆 BEST PARAMETERS")
        print("="*60)
        print(f"Best SMA({best_params[0]}, {best_params[1]})")
        print_backtest_results(best_result)
        
        return True
        
    except Exception as e:
        logger.error(f"Optimization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Backtest trading strategies")
    parser.add_argument("--optimize", action="store_true", help="Run parameter optimization")
    parser.add_argument("--mock", action="store_true", help="Use mock data instead of real data")
    
    args = parser.parse_args()
    
    if args.optimize:
        print("🔍 Running parameter optimization...")
        success = asyncio.run(run_parameter_optimization())
    else:
        print("📊 Running backtest...")
        success = asyncio.run(run_backtest())
    
    if success:
        print("\n✅ Backtest completed successfully!")
    else:
        print("\n❌ Backtest failed!")
        sys.exit(1)
