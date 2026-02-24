#!/usr/bin/env python3
"""
Test signal calculation performance for Order Book strategy.
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

class SignalPerformanceTester:
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
            # Simulate realistic trade data
            price_variation = random.uniform(-0.01, 0.01)  # ±1% price variation
            price = base_price * (1 + price_variation)
            size = random.uniform(0.001, 10.0)  # 0.001 to 10 BTC
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
            # Simulate realistic order book
            price_variation = random.uniform(-0.005, 0.005)  # ±0.5% price variation
            mid_price = base_price * (1 + price_variation)
            spread = random.uniform(0.0001, 0.001)  # 0.01% to 0.1% spread
            
            bids = []
            asks = []
            
            # Create 5 levels of bids and asks
            for level in range(5):
                bid_price = mid_price - (level + 1) * spread * mid_price
                ask_price = mid_price + (level + 1) * spread * mid_price
                size = random.uniform(0.1, 5.0)
                
                bids.append({'price': bid_price, 'size': size})  # Keep as float
                asks.append({'price': ask_price, 'size': size})  # Keep as float
            
            order_book = {
                'bids': bids,
                'asks': asks
            }
            
            order_books.append({
                'order_book': order_book,
                'timestamp': datetime.now() - timedelta(seconds=i)
            })
        
        return order_books
    
    def test_signal_performance(self, trade_count: int, order_book_count: int, iterations: int = 100):
        """Test signal calculation performance with different data sizes."""
        print(f"Testing signal performance with {trade_count} trades, {order_book_count} order books")
        print(f"Running {iterations} iterations...")
        
        # Create strategy
        strategy = OrderBookStrategy(
            config=self.config,
            trade_history_limit=trade_count,
            large_trade_threshold=1000.0
        )
        
        # Add mock data
        trades = self.create_mock_trade_data(trade_count)
        order_books = self.create_mock_order_book_data(order_book_count)
        
        for trade in trades:
            strategy.add_trades([trade['trade']], trade['timestamp'])
        
        for ob in order_books:
            strategy.add_order_book(ob['order_book'], ob['timestamp'])
        
        # Add some price history
        for i in range(100):
            price = 50000.0 + random.uniform(-1000, 1000)
            timestamp = datetime.now() - timedelta(seconds=i)
            strategy.add_price(price, timestamp)
        
        # Measure signal calculation time
        times = []
        
        for i in range(iterations):
            current_price = 50000.0 + random.uniform(-1000, 1000)
            timestamp = datetime.now()
            
            start_time = time.perf_counter()
            signal = strategy.generate_signal(current_price, timestamp)
            end_time = time.perf_counter()
            
            calculation_time = (end_time - start_time) * 1000  # Convert to milliseconds
            times.append(calculation_time)
        
        # Calculate statistics
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        median_time = sorted(times)[len(times) // 2]
        
        print(f"  Average time: {avg_time:.3f} ms")
        print(f"  Min time: {min_time:.3f} ms")
        print(f"  Max time: {max_time:.3f} ms")
        print(f"  Median time: {median_time:.3f} ms")
        print(f"  Total signals generated: {strategy.signal_count}")
        print()
        
        return {
            'trade_count': trade_count,
            'order_book_count': order_book_count,
            'iterations': iterations,
            'avg_time_ms': avg_time,
            'min_time_ms': min_time,
            'max_time_ms': max_time,
            'median_time_ms': median_time,
            'signal_count': strategy.signal_count
        }
    
    def run_comparison_test(self):
        """Run comparison test between current and optimized limits."""
        print("🚀 Order Book Strategy Signal Performance Test")
        print("=" * 60)
        
        # Test configurations
        test_configs = [
            # Current implementation
            {'trades': 100, 'order_books': 10, 'name': 'Current (100 trades)'},
            {'trades': 1000, 'order_books': 100, 'name': 'Optimized (1000 trades)'},
            {'trades': 10000, 'order_books': 1000, 'name': 'Extended (10000 trades)'},
            {'trades': 100, 'order_books': 100, 'name': 'Current + More Order Books'},
            {'trades': 1000, 'order_books': 10, 'name': 'Optimized Trades Only'},
        ]
        
        results = []
        
        for config in test_configs:
            print(f"\n📊 Testing: {config['name']}")
            print("-" * 40)
            
            result = self.test_signal_performance(
                trade_count=config['trades'],
                order_book_count=config['order_books'],
                iterations=50  # Reduced for faster testing
            )
            result['name'] = config['name']
            results.append(result)
        
        # Analyze results
        print("\n📈 Performance Analysis")
        print("=" * 60)
        
        current_result = next(r for r in results if 'Current (100 trades)' in r['name'])
        optimized_result = next(r for r in results if 'Optimized (1000 trades)' in r['name'])
        
        print(f"Current Implementation (100 trades):")
        print(f"  Average time: {current_result['avg_time_ms']:.3f} ms")
        print(f"  Signal count: {current_result['signal_count']}")
        
        print(f"\nOptimized Implementation (1000 trades):")
        print(f"  Average time: {optimized_result['avg_time_ms']:.3f} ms")
        print(f"  Signal count: {optimized_result['signal_count']}")
        
        # Calculate performance impact
        time_increase = optimized_result['avg_time_ms'] / current_result['avg_time_ms']
        print(f"\nPerformance Impact:")
        print(f"  Time increase: {time_increase:.2f}x")
        print(f"  Additional time: {optimized_result['avg_time_ms'] - current_result['avg_time_ms']:.3f} ms")
        
        # Calculate throughput
        current_throughput = 1000 / current_result['avg_time_ms']  # signals per second
        optimized_throughput = 1000 / optimized_result['avg_time_ms']
        
        print(f"\nThroughput:")
        print(f"  Current: {current_throughput:.1f} signals/second")
        print(f"  Optimized: {optimized_throughput:.1f} signals/second")
        
        # Memory usage estimation
        current_memory = 100 * 200  # 100 trades * ~200 bytes per trade
        optimized_memory = 1000 * 200  # 1000 trades * ~200 bytes per trade
        
        print(f"\nMemory Usage (estimated):")
        print(f"  Current: {current_memory / 1024:.1f} KB")
        print(f"  Optimized: {optimized_memory / 1024:.1f} KB")
        print(f"  Memory increase: {optimized_memory / current_memory:.1f}x")
        
        return results

def main():
    """Run the performance test."""
    tester = SignalPerformanceTester()
    results = tester.run_comparison_test()
    
    print(f"\n✅ Performance test completed!")
    print(f"Tested {len(results)} configurations")

if __name__ == "__main__":
    main()
