"""Comprehensive backtesting script with real historical data."""

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
from trade_bot.data_provider import CoinbaseDataProvider


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


async def run_backtest_with_period(days: int, strategy_params: dict, product_id: str = "BTC-USD"):
    """Run backtest for a specific period."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config = TradingConfig.from_env()
        config.product_id = product_id
        logger.info(f"Starting backtest for {product_id} over {days} days")
        
        # Create data provider
        data_provider = CoinbaseDataProvider(product_id)
        
        # Define backtest period
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        # Get historical data
        logger.info(f"Fetching data from {start_time} to {end_time}")
        historical_data = await data_provider.get_historical_candles(
            start_time=start_time,
            end_time=end_time,
            granularity=3600  # 1-hour candles
        )
        
        if not historical_data:
            logger.error("No historical data available")
            return None
        
        logger.info(f"Retrieved {len(historical_data)} data points")
        
        # Create backtester
        backtester = Backtester(
            config=config,
            strategy_class=SimpleMovingAverageStrategy,
            strategy_params=strategy_params
        )
        
        # Run backtest
        logger.info("Running backtest...")
        result = await backtester.run_backtest(historical_data)
        
        return result, backtester
        
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        return None


async def run_multiple_backtests():
    """Run backtests with different time periods and strategies."""
    print("🚀 COMPREHENSIVE BACKTESTING WITH REAL DATA")
    print("="*60)
    
    # Different strategy configurations to test
    strategies = [
        {"short_window": 5, "long_window": 20, "name": "SMA(5,20)"},
        {"short_window": 10, "long_window": 30, "name": "SMA(10,30)"},
        {"short_window": 3, "long_window": 10, "name": "SMA(3,10)"},
        {"short_window": 15, "long_window": 50, "name": "SMA(15,50)"},
    ]
    
    # Different time periods
    periods = [3, 7, 14, 30]
    
    # Different products
    products = ["BTC-USD", "ETH-USD", "ADA-USD"]
    
    all_results = []
    
    for product in products:
        print(f"\n🔍 Testing {product}")
        print("-" * 40)
        
        for days in periods:
            print(f"\n📅 {days} days period:")
            
            for strategy in strategies:
                print(f"  Testing {strategy['name']}...")
                
                # Remove 'name' from strategy params before passing to backtester
                strategy_params = {k: v for k, v in strategy.items() if k != 'name'}
                
                result, backtester = await run_backtest_with_period(
                    days=days,
                    strategy_params=strategy_params,
                    product_id=product
                )
                
                if result:
                    all_results.append({
                        'product': product,
                        'days': days,
                        'strategy': strategy['name'],
                        'result': result
                    })
                    
                    print(f"    ✅ {result.total_trades} trades, {result.win_rate:.1%} win rate, {result.total_return:.1%} return")
                else:
                    print(f"    ❌ Failed")
    
    # Find best performing strategies
    if all_results:
        print("\n🏆 BEST PERFORMING STRATEGIES")
        print("="*60)
        
        # Sort by total return
        best_results = sorted(all_results, key=lambda x: x['result'].total_return, reverse=True)
        
        for i, result_data in enumerate(best_results[:5]):  # Top 5
            result = result_data['result']
            print(f"{i+1}. {result_data['product']} - {result_data['strategy']} ({result_data['days']} days)")
            print(f"   Return: {result.total_return:.2%}, Trades: {result.total_trades}, Win Rate: {result.win_rate:.1%}")
            print(f"   Sharpe: {result.sharpe_ratio:.2f}, Max DD: {result.max_drawdown:.2%}")
            print()
    
    return all_results


async def run_single_backtest():
    """Run a single backtest with optimal parameters."""
    print("📊 SINGLE BACKTEST WITH REAL DATA")
    print("="*60)
    
    # Use optimal parameters based on testing
    strategy_params = {
        'short_window': 5,
        'long_window': 20
    }
    
    result, backtester = await run_backtest_with_period(
        days=7,
        strategy_params=strategy_params,
        product_id="BTC-USD"
    )
    
    if result:
        print_backtest_results(result)
        
        # Save detailed results
        trades_df = backtester.get_trades_df()
        equity_df = backtester.get_equity_curve_df()
        
        if not trades_df.empty:
            trades_file = f"backtest_trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            trades_df.to_csv(trades_file)
            print(f"💾 Saved trades to {trades_file}")
        
        if not equity_df.empty:
            equity_file = f"backtest_equity_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            equity_df.to_csv(equity_file)
            print(f"💾 Saved equity curve to {equity_file}")
        
        return True
    else:
        print("❌ Backtest failed!")
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Comprehensive backtesting with real data")
    parser.add_argument("--mode", choices=["single", "multiple"], default="single", 
                       help="Run single backtest or multiple strategy comparison")
    parser.add_argument("--product", default="BTC-USD", 
                       help="Trading pair to test (e.g., BTC-USD, ETH-USD)")
    parser.add_argument("--days", type=int, default=7, 
                       help="Number of days to backtest")
    
    args = parser.parse_args()
    
    if args.mode == "single":
        print("Running single backtest...")
        success = asyncio.run(run_single_backtest())
    else:
        print("Running comprehensive backtest comparison...")
        results = asyncio.run(run_multiple_backtests())
        success = len(results) > 0
    
    if success:
        print("\n✅ Backtesting completed successfully!")
    else:
        print("\n❌ Backtesting failed!")
        sys.exit(1)
