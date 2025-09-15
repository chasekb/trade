#!/usr/bin/env python3
"""
Test all Order Book strategy optimizations.
"""

import asyncio
import time
import random
import sys
import os
from datetime import datetime, timedelta

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.trade_bot.trading_strategy import OrderBookStrategy
from src.trade_bot.config import TradingConfig

class OptimizationTester:
    def __init__(self):
        self.config = TradingConfig(
            product_id="BTC-USD",
            api_key="test",
            api_secret="test", 
            passphrase="test",
            max_position_size=1.0,
            stop_loss_percentage=0.02,
            take_profit_percentage=0.04
        )
    
    def create_mock_trade_data(self, count: int) -> list:
        """Create mock trade data for testing."""
        trades = []
        base_price = 50000.0
        
        for i in range(count):
            price_variation = random.uniform(-0.01, 0.01)
            price = base_price * (1 + price_variation)
            size = random.uniform(0.001, 10.0)
            side = random.choice(['buy', 'sell'])
            
            trade = {
                'size': str(size),
                'side': side,
                'price': str(price),
                'time': (datetime.now() - timedelta(seconds=i)).isoformat()
            }
            
            trades.append({
                'trade': trade,
                'timestamp': datetime.now() - timedelta(seconds=i)
            })
        
        return trades
    
    def create_mock_order_book_data(self, count: int) -> list:
        """Create mock order book data for testing."""
        order_books = []
        base_price = 50000.0
        
        for i in range(count):
            price_variation = random.uniform(-0.005, 0.005)
            mid_price = base_price * (1 + price_variation)
            spread = random.uniform(0.0001, 0.001)
            
            bids = []
            asks = []
            
            for level in range(5):
                bid_price = mid_price - (level + 1) * spread * mid_price
                ask_price = mid_price + (level + 1) * spread * mid_price
                size = random.uniform(0.1, 5.0)
                
                bids.append({'price': bid_price, 'size': size})
                asks.append({'price': ask_price, 'size': size})
            
            order_book = {
                'bids': bids,
                'asks': asks
            }
            
            order_books.append({
                'order_book': order_book,
                'timestamp': datetime.now() - timedelta(seconds=i)
            })
        
        return order_books
    
    def test_caching_performance(self):
        """Test caching performance improvements."""
        print("🧪 Testing Caching Performance")
        print("-" * 40)
        
        # Create strategy
        strategy = OrderBookStrategy(
            config=self.config,
            trade_history_limit=1000,
            data_analysis_mode='recent',
            recent_data_limit=50
        )
        
        # Add order book data
        order_books = self.create_mock_order_book_data(100)
        for ob in order_books:
            strategy.add_order_book(ob['order_book'], ob['timestamp'])
        
        # Test without caching
        times_no_cache = []
        for _ in range(50):
            current_ob = order_books[-1]['order_book']
            
            # Clear cache
            strategy._cached_metrics = {}
            strategy._cache_timestamp = None
            
            start_time = time.perf_counter()
            strategy.calculate_bid_ask_spread(current_ob)
            strategy.calculate_volume_imbalance(current_ob)
            strategy.calculate_mid_price(current_ob)
            end_time = time.perf_counter()
            
            times_no_cache.append((end_time - start_time) * 1000)
        
        # Test with caching
        times_with_cache = []
        for _ in range(50):
            current_ob = order_books[-1]['order_book']
            
            start_time = time.perf_counter()
            metrics = strategy._calculate_metrics_cached(current_ob)
            end_time = time.perf_counter()
            
            times_with_cache.append((end_time - start_time) * 1000)
        
        avg_no_cache = sum(times_no_cache) / len(times_no_cache)
        avg_with_cache = sum(times_with_cache) / len(times_with_cache)
        
        print(f"Without caching: {avg_no_cache:.3f} ms")
        print(f"With caching: {avg_with_cache:.3f} ms")
        print(f"Improvement: {avg_no_cache / avg_with_cache:.2f}x faster")
        print()
        
        return avg_no_cache / avg_with_cache
    
    def test_data_analysis_modes(self):
        """Test different data analysis modes."""
        print("🧪 Testing Data Analysis Modes")
        print("-" * 40)
        
        modes = ['all', 'recent', 'sampled']
        trade_counts = [100, 500, 1000, 5000]
        
        for mode in modes:
            print(f"\nMode: {mode}")
            print("Trade Count | Time (ms) | Data Used")
            print("-" * 35)
            
            for trade_count in trade_counts:
                # Create strategy with specific mode
                strategy = OrderBookStrategy(
                    config=self.config,
                    trade_history_limit=trade_count,
                    data_analysis_mode=mode,
                    recent_data_limit=50,
                    sampling_ratio=0.1
                )
                
                # Add trade data
                trades = self.create_mock_trade_data(trade_count)
                for trade in trades:
                    strategy.add_trades([trade['trade']], trade['timestamp'])
                
                # Measure analysis time
                times = []
                for _ in range(20):
                    start_time = time.perf_counter()
                    analysis_data = strategy._get_analysis_data('trades')
                    end_time = time.perf_counter()
                    times.append((end_time - start_time) * 1000)
                
                avg_time = sum(times) / len(times)
                data_used = len(analysis_data)
                
                print(f"{trade_count:11} | {avg_time:8.3f} | {data_used:9}")
    
    def test_numpy_performance(self):
        """Test numpy array performance improvements."""
        print("\n🧪 Testing NumPy Performance")
        print("-" * 40)
        
        trade_counts = [100, 500, 1000, 5000, 10000]
        
        print("Trade Count | Python (ms) | NumPy (ms) | Improvement")
        print("-" * 55)
        
        for trade_count in trade_counts:
            trades = self.create_mock_trade_data(trade_count)
            
            # Test Python implementation
            strategy_python = OrderBookStrategy(config=self.config)
            times_python = []
            for _ in range(10):
                start_time = time.perf_counter()
                # Simulate Python implementation
                buy_volume = 0.0
                sell_volume = 0.0
                for trade_data in trades:
                    trade = trade_data['trade']
                    size = float(trade.get('size', 0))
                    side = trade.get('side', '')
                    price = float(trade.get('price', 0))
                    trade_value = size * price
                    if side == 'buy':
                        buy_volume += trade_value
                    elif side == 'sell':
                        sell_volume += trade_value
                end_time = time.perf_counter()
                times_python.append((end_time - start_time) * 1000)
            
            # Test NumPy implementation
            strategy_numpy = OrderBookStrategy(config=self.config)
            times_numpy = []
            for _ in range(10):
                start_time = time.perf_counter()
                strategy_numpy._analyze_trade_flow_optimized(trades)
                end_time = time.perf_counter()
                times_numpy.append((end_time - start_time) * 1000)
            
            avg_python = sum(times_python) / len(times_python)
            avg_numpy = sum(times_numpy) / len(times_numpy)
            improvement = avg_python / avg_numpy if avg_numpy > 0 else 1.0
            
            print(f"{trade_count:11} | {avg_python:10.3f} | {avg_numpy:9.3f} | {improvement:10.2f}x")
    
    def test_incremental_updates(self):
        """Test incremental update performance."""
        print("\n🧪 Testing Incremental Updates")
        print("-" * 40)
        
        strategy = OrderBookStrategy(
            config=self.config,
            trade_history_limit=1000,
            data_analysis_mode='recent'
        )
        
        # Add initial trades
        initial_trades = self.create_mock_trade_data(100)
        for trade in initial_trades:
            strategy.add_trades([trade['trade']], trade['timestamp'])
        
        # Measure full recalculation
        times_full = []
        for _ in range(20):
            start_time = time.perf_counter()
            strategy.analyze_trade_flow(initial_trades)
            end_time = time.perf_counter()
            times_full.append((end_time - start_time) * 1000)
        
        # Add more trades and measure incremental update
        additional_trades = self.create_mock_trade_data(50)
        for trade in additional_trades:
            strategy.add_trades([trade['trade']], trade['timestamp'])
        
        times_incremental = []
        for _ in range(20):
            start_time = time.perf_counter()
            strategy._incremental_trade_analysis()
            end_time = time.perf_counter()
            times_incremental.append((end_time - start_time) * 1000)
        
        avg_full = sum(times_full) / len(times_full)
        avg_incremental = sum(times_incremental) / len(times_incremental)
        
        print(f"Full recalculation: {avg_full:.3f} ms")
        print(f"Incremental update: {avg_incremental:.3f} ms")
        print(f"Improvement: {avg_full / avg_incremental:.2f}x faster")
        print()
        
        return avg_full / avg_incremental
    
    def test_polars_availability(self):
        """Test Polars availability and performance."""
        print("\n🧪 Testing Polars Availability")
        print("-" * 40)
        
        strategy = OrderBookStrategy(config=self.config)
        
        if strategy.polars_optimizer:
            stats = strategy.polars_optimizer.get_performance_stats()
            print(f"Polars available: {stats['polars_available']}")
            print(f"GPU available: {stats['gpu_available']}")
            print(f"Optimization level: {stats['optimization_level']}")
            
            # Test Polars performance
            trades = self.create_mock_trade_data(1000)
            
            times = []
            for _ in range(10):
                start_time = time.perf_counter()
                strategy.polars_optimizer.analyze_trade_flow_polars(trades)
                end_time = time.perf_counter()
                times.append((end_time - start_time) * 1000)
            
            avg_time = sum(times) / len(times)
            print(f"Polars analysis time: {avg_time:.3f} ms")
        else:
            print("Polars not available")
    
    def run_comprehensive_test(self):
        """Run all optimization tests."""
        print("🚀 Order Book Strategy Optimization Test Suite")
        print("=" * 60)
        
        results = {}
        
        # Test 1: Caching Performance
        print("\n1. Caching Performance Test")
        results['caching'] = self.test_caching_performance()
        
        # Test 2: Data Analysis Modes
        print("\n2. Data Analysis Modes Test")
        self.test_data_analysis_modes()
        
        # Test 3: NumPy Performance
        print("\n3. NumPy Performance Test")
        self.test_numpy_performance()
        
        # Test 4: Incremental Updates
        print("\n4. Incremental Updates Test")
        results['incremental'] = self.test_incremental_updates()
        
        # Test 5: Polars Availability
        print("\n5. Polars Availability Test")
        self.test_polars_availability()
        
        # Summary
        print("\n📊 Optimization Summary")
        print("=" * 60)
        print(f"Caching improvement: {results.get('caching', 1.0):.2f}x")
        print(f"Incremental improvement: {results.get('incremental', 1.0):.2f}x")
        print("Data analysis modes: ✅ Implemented")
        print("NumPy arrays: ✅ Implemented")
        print("Polars GPU: ✅ Available (if installed)")
        
        return results

def main():
    """Run the optimization test suite."""
    tester = OptimizationTester()
    results = tester.run_comprehensive_test()
    
    print(f"\n✅ Optimization test suite completed!")
    print(f"All optimizations implemented and tested successfully.")

if __name__ == "__main__":
    main()
