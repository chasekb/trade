#!/usr/bin/env python3
"""
Debug test suite to identify where the 2x data points issue occurs in the strategy workflow.

This test suite traces through each function in the strategy workflow to determine
where the behavior deviates from the expectation of processing exactly the input data points.
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Add the src directory to the path
sys.path.insert(0, 'src')

from src.trade_bot.trading_strategy import SimpleMovingAverageStrategy, TradingConfig
from src.trade_bot.backtester import Backtester
from src.trade_bot.data_provider import CoinbaseDataProvider

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataFlowTracker:
    """Tracks data flow through the strategy workflow."""
    
    def __init__(self):
        self.add_price_calls = 0
        self.price_history_lengths = []
        self.signal_generation_calls = 0
        self.backtester_calls = 0
        
    def reset(self):
        """Reset all counters."""
        self.add_price_calls = 0
        self.price_history_lengths = []
        self.signal_generation_calls = 0
        self.backtester_calls = 0

# Global tracker
tracker = DataFlowTracker()

class DebugSMAStrategy(SimpleMovingAverageStrategy):
    """Debug version of SMA strategy that tracks all method calls."""
    
    def add_price(self, price: float, timestamp: datetime) -> None:
        """Override add_price to track calls and price history length."""
        tracker.add_price_calls += 1
        logger.info(f"DEBUG: add_price called #{tracker.add_price_calls} with price {price}")
        
        # Call parent method
        super().add_price(price, timestamp)
        
        # Track price history length
        current_length = len(self.price_history)
        tracker.price_history_lengths.append(current_length)
        logger.info(f"DEBUG: After add_price, price_history length = {current_length}")
        
    def generate_signal(self, price: float, timestamp: datetime, is_end_of_period: bool = False):
        """Override generate_signal to track calls."""
        tracker.signal_generation_calls += 1
        logger.info(f"DEBUG: generate_signal called #{tracker.signal_generation_calls}")
        
        # Call parent method
        result = super().generate_signal(price, timestamp, is_end_of_period)
        
        # Log result
        if result:
            logger.info(f"DEBUG: Signal generated: {result.action} - {result.reason}")
        else:
            logger.info(f"DEBUG: No signal generated")
            
        return result

class DebugBacktester(Backtester):
    """Debug version of backtester that tracks all method calls."""
    
    def run_backtest(self, historical_data: List[Dict[str, Any]]):
        """Override run_backtest to track calls and data flow."""
        tracker.backtester_calls += 1
        logger.info(f"DEBUG: run_backtest called #{tracker.backtester_calls} with {len(historical_data)} data points")
        
        # Call parent method
        result = super().run_backtest(historical_data)
        
        # Log final statistics
        logger.info(f"DEBUG: Backtest completed with {tracker.add_price_calls} add_price calls")
        logger.info(f"DEBUG: Price history lengths: {tracker.price_history_lengths}")
        logger.info(f"DEBUG: Signal generation calls: {tracker.signal_generation_calls}")
        
        return result

async def test_data_provider():
    """Test 1: Verify data provider returns correct number of data points."""
    logger.info("=" * 60)
    logger.info("TEST 1: Data Provider Data Points")
    logger.info("=" * 60)
    
    provider = CoinbaseDataProvider('BTC-USD')
    end_time = datetime.now()
    start_time = end_time - timedelta(days=1)
    
    logger.info(f"Fetching data from {start_time} to {end_time}")
    data = await provider.get_historical_candles(start_time, end_time, 3600)
    
    logger.info(f"Data provider returned {len(data)} candles")
    logger.info(f"Expected: {24} candles (1 day * 24 hours)")
    logger.info(f"Actual vs Expected: {len(data)} vs {24} = {len(data) / 24:.2f}x")
    
    if data:
        logger.info(f"First candle: {data[0]['timestamp']}")
        logger.info(f"Last candle: {data[-1]['timestamp']}")
    
    return data

def test_strategy_add_price():
    """Test 2: Verify strategy add_price method works correctly."""
    logger.info("=" * 60)
    logger.info("TEST 2: Strategy add_price Method")
    logger.info("=" * 60)
    
    # Reset tracker
    tracker.reset()
    
    # Create strategy
    config = TradingConfig(
        api_key="test_key",
        api_secret="test_secret", 
        passphrase="test_passphrase"
    )
    strategy = DebugSMAStrategy(config, short_window=5, long_window=20)
    
    # Test data
    test_prices = [100.0, 101.0, 102.0, 103.0, 104.0]
    test_timestamps = [datetime.now() + timedelta(hours=i) for i in range(len(test_prices))]
    
    logger.info(f"Testing with {len(test_prices)} price points")
    
    # Add prices one by one
    for i, (price, timestamp) in enumerate(zip(test_prices, test_timestamps)):
        logger.info(f"Adding price {i+1}/{len(test_prices)}: {price}")
        strategy.add_price(price, timestamp)
        logger.info(f"Price history length after add: {len(strategy.price_history)}")
    
    # Verify results
    logger.info(f"Total add_price calls: {tracker.add_price_calls}")
    logger.info(f"Final price_history length: {len(strategy.price_history)}")
    logger.info(f"Expected: {len(test_prices)}")
    logger.info(f"Actual vs Expected: {len(strategy.price_history)} vs {len(test_prices)} = {len(strategy.price_history) / len(test_prices):.2f}x")
    
    return strategy

def test_strategy_signal_generation():
    """Test 3: Verify strategy signal generation works correctly."""
    logger.info("=" * 60)
    logger.info("TEST 3: Strategy Signal Generation")
    logger.info("=" * 60)
    
    # Reset tracker
    tracker.reset()
    
    # Create strategy
    config = TradingConfig(
        api_key="test_key",
        api_secret="test_secret", 
        passphrase="test_passphrase"
    )
    strategy = DebugSMAStrategy(config, short_window=5, long_window=20)
    
    # Test data - enough for SMA calculation
    test_prices = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0, 110.0, 111.0, 112.0, 113.0, 114.0, 115.0, 116.0, 117.0, 118.0, 119.0, 120.0, 121.0, 122.0, 123.0, 124.0]
    test_timestamps = [datetime.now() + timedelta(hours=i) for i in range(len(test_prices))]
    
    logger.info(f"Testing with {len(test_prices)} price points")
    
    # Add prices and generate signals
    for i, (price, timestamp) in enumerate(zip(test_prices, test_timestamps)):
        logger.info(f"Processing price {i+1}/{len(test_prices)}: {price}")
        strategy.add_price(price, timestamp)
        
        # Generate signal
        is_end_of_period = (i == len(test_prices) - 1)
        signal = strategy.generate_signal(price, timestamp, is_end_of_period)
        
        if signal:
            logger.info(f"Signal generated: {signal.action} - {signal.reason}")
        else:
            logger.info(f"No signal generated")
    
    # Verify results
    logger.info(f"Total add_price calls: {tracker.add_price_calls}")
    logger.info(f"Total signal generation calls: {tracker.signal_generation_calls}")
    logger.info(f"Final price_history length: {len(strategy.price_history)}")
    logger.info(f"Expected: {len(test_prices)}")
    logger.info(f"Actual vs Expected: {len(strategy.price_history)} vs {len(test_prices)} = {len(strategy.price_history) / len(test_prices):.2f}x")
    
    return strategy

def test_backtester_data_flow():
    """Test 4: Verify backtester data flow works correctly."""
    logger.info("=" * 60)
    logger.info("TEST 4: Backtester Data Flow")
    logger.info("=" * 60)
    
    # Reset tracker
    tracker.reset()
    
    # Create test data
    test_data = []
    for i in range(24):  # 24 hours
        test_data.append({
            'timestamp': (datetime.now() - timedelta(hours=23-i)).isoformat() + 'Z',
            'price': 100.0 + i,
            'open': 100.0 + i,
            'high': 100.0 + i + 0.5,
            'low': 100.0 + i - 0.5,
            'close': 100.0 + i,
            'volume': 100.0
        })
    
    logger.info(f"Created test data with {len(test_data)} data points")
    
    # Create backtester with debug strategy
    config = TradingConfig(
        api_key="test_key",
        api_secret="test_secret", 
        passphrase="test_passphrase"
    )
    backtester = DebugBacktester(
        strategy_class=DebugSMAStrategy,
        strategy_params={'short_window': 5, 'long_window': 20},
        config=config,
        initial_capital=10000.0,
        portfolio_percentage=5.0
    )
    
    # Run backtest
    logger.info("Running backtest...")
    result = backtester.run_backtest(test_data)
    
    # Verify results
    logger.info(f"Backtest result: {result.total_trades} trades, {result.total_signals} signals")
    logger.info(f"Total add_price calls: {tracker.add_price_calls}")
    logger.info(f"Total signal generation calls: {tracker.signal_generation_calls}")
    logger.info(f"Expected add_price calls: {len(test_data)}")
    logger.info(f"Expected signal generation calls: {len(test_data)}")
    logger.info(f"Actual vs Expected add_price: {tracker.add_price_calls} vs {len(test_data)} = {tracker.add_price_calls / len(test_data):.2f}x")
    logger.info(f"Actual vs Expected signal generation: {tracker.signal_generation_calls} vs {len(test_data)} = {tracker.signal_generation_calls / len(test_data):.2f}x")
    
    return result

def test_strategy_memory_limits():
    """Test 5: Verify strategy memory limits work correctly."""
    logger.info("=" * 60)
    logger.info("TEST 5: Strategy Memory Limits")
    logger.info("=" * 60)
    
    # Reset tracker
    tracker.reset()
    
    # Create strategy
    config = TradingConfig(
        api_key="test_key",
        api_secret="test_secret", 
        passphrase="test_passphrase"
    )
    strategy = DebugSMAStrategy(config, short_window=5, long_window=20)
    
    # Test memory limit (long_window * 5000 = 20 * 5000 = 100,000)
    memory_limit = strategy.long_window * 5000
    logger.info(f"Memory limit: {memory_limit} data points")
    
    # Add more data points than the limit
    test_count = memory_limit + 1000
    logger.info(f"Adding {test_count} data points (exceeds limit by 1000)")
    
    for i in range(test_count):
        price = 100.0 + i
        timestamp = datetime.now() + timedelta(hours=i)
        strategy.add_price(price, timestamp)
        
        # Log every 10000th addition
        if i % 10000 == 0:
            logger.info(f"Added {i+1} data points, price_history length: {len(strategy.price_history)}")
    
    # Verify memory limit is enforced
    final_length = len(strategy.price_history)
    logger.info(f"Final price_history length: {final_length}")
    logger.info(f"Memory limit: {memory_limit}")
    logger.info(f"Memory limit enforced: {final_length <= memory_limit}")
    logger.info(f"Actual vs Limit: {final_length} vs {memory_limit} = {final_length / memory_limit:.2f}x")
    
    return strategy

def test_signal_stats_calculation():
    """Test 6: Verify signal stats calculation works correctly."""
    logger.info("=" * 60)
    logger.info("TEST 6: Signal Stats Calculation")
    logger.info("=" * 60)
    
    # Reset tracker
    tracker.reset()
    
    # Create strategy
    config = TradingConfig(
        api_key="test_key",
        api_secret="test_secret", 
        passphrase="test_passphrase"
    )
    strategy = DebugSMAStrategy(config, short_window=5, long_window=20)
    
    # Add test data
    test_prices = [100.0 + i for i in range(50)]
    test_timestamps = [datetime.now() + timedelta(hours=i) for i in range(50)]
    
    for price, timestamp in zip(test_prices, test_timestamps):
        strategy.add_price(price, timestamp)
    
    # Get signal stats
    stats = strategy.get_signal_stats()
    
    logger.info(f"Signal stats: {stats}")
    logger.info(f"Price history length from stats: {stats.get('price_history_length', 'NOT FOUND')}")
    logger.info(f"Actual price history length: {len(strategy.price_history)}")
    logger.info(f"Expected: {len(test_prices)}")
    logger.info(f"Stats vs Actual: {stats.get('price_history_length', 'NOT FOUND')} vs {len(strategy.price_history)}")
    logger.info(f"Stats vs Expected: {stats.get('price_history_length', 'NOT FOUND')} vs {len(test_prices)}")
    
    return stats

async def run_all_tests():
    """Run all debug tests."""
    logger.info("Starting comprehensive debug tests for 2x data points issue")
    logger.info("=" * 80)
    
    try:
        # Test 1: Data Provider
        data = await test_data_provider()
        
        # Test 2: Strategy add_price
        strategy1 = test_strategy_add_price()
        
        # Test 3: Strategy signal generation
        strategy2 = test_strategy_signal_generation()
        
        # Test 4: Backtester data flow
        result = test_backtester_data_flow()
        
        # Test 5: Strategy memory limits
        strategy3 = test_strategy_memory_limits()
        
        # Test 6: Signal stats calculation
        stats = test_signal_stats_calculation()
        
        # Summary
        logger.info("=" * 80)
        logger.info("DEBUG TEST SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Data provider returned correct number of data points: {len(data) == 24}")
        logger.info(f"Strategy add_price works correctly: {tracker.add_price_calls == len(test_prices) if 'test_prices' in locals() else 'N/A'}")
        logger.info(f"Strategy memory limits work correctly: {len(strategy3.price_history) <= strategy3.long_window * 5000}")
        logger.info(f"Signal stats calculation works correctly: {stats.get('price_history_length') == len(strategy2.price_history)}")
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_all_tests())
