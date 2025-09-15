#!/usr/bin/env python3
"""
Test different Order Book strategy parameter configurations to increase signal generation.
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

class OrderBookParameterTester:
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
    
    def create_realistic_market_data(self, count: int) -> tuple:
        """Create realistic market data for testing."""
        # Create order book data
        order_books = []
        trades = []
        base_price = 50000.0
        
        for i in range(count):
            # Price movement
            price_variation = random.uniform(-0.02, 0.02)
            current_price = base_price * (1 + price_variation)
            
            # Create order book with varying spreads
            spread_variation = random.uniform(0.0001, 0.002)  # 0.01% to 0.2%
            spread = current_price * spread_variation
            
            bids = []
            asks = []
            
            for level in range(5):
                bid_price = current_price - (level + 1) * spread
                ask_price = current_price + (level + 1) * spread
                
                # Vary volume to create imbalances
                bid_volume = random.uniform(0.1, 2.0)
                ask_volume = random.uniform(0.1, 2.0)
                
                # Sometimes create significant imbalances
                if random.random() < 0.3:  # 30% chance of imbalance
                    if random.random() < 0.5:
                        bid_volume *= 3  # Strong buy pressure
                    else:
                        ask_volume *= 3  # Strong sell pressure
                
                bids.append({'price': bid_price, 'size': bid_volume})
                asks.append({'price': ask_price, 'size': ask_volume})
            
            order_book = {
                'bids': bids,
                'asks': asks
            }
            
            order_books.append({
                'order_book': order_book,
                'timestamp': datetime.now() - timedelta(seconds=i)
            })
            
            # Create trade data
            for _ in range(random.randint(1, 5)):
                trade_size = random.uniform(0.001, 2.0)
                trade_price = current_price + random.uniform(-spread/2, spread/2)
                side = random.choice(['buy', 'sell'])
                
                # Sometimes create large trades
                if random.random() < 0.1:  # 10% chance of large trade
                    trade_size *= 10
                
                trade = {
                    'size': str(trade_size),
                    'side': side,
                    'price': str(trade_price),
                    'time': (datetime.now() - timedelta(seconds=i)).isoformat()
                }
                
                trades.append({
                    'trade': trade,
                    'timestamp': datetime.now() - timedelta(seconds=i)
                })
        
        return order_books, trades
    
    def test_parameter_configuration(self, config_name: str, strategy_params: dict) -> dict:
        """Test a specific parameter configuration."""
        print(f"\n🧪 Testing {config_name}")
        print("-" * 50)
        
        # Create strategy with given parameters
        strategy = OrderBookStrategy(
            config=self.config,
            **strategy_params
        )
        
        # Generate market data
        order_books, trades = self.create_realistic_market_data(100)
        
        # Add data to strategy
        for ob in order_books:
            strategy.add_order_book(ob['order_book'], ob['timestamp'])
        
        for trade in trades:
            strategy.add_trades([trade['trade']], trade['timestamp'])
        
        # Test signal generation
        signals = []
        for i in range(50):  # Test 50 iterations
            current_price = 50000.0 + random.uniform(-1000, 1000)
            signal = strategy.generate_signal(
                current_price=current_price,
                timestamp=datetime.now()
            )
            
            if signal and signal.action != 'hold':
                signals.append(signal)
        
        # Calculate statistics
        total_signals = len(signals)
        buy_signals = len([s for s in signals if s.action == 'buy'])
        sell_signals = len([s for s in signals if s.action == 'sell'])
        
        print(f"Total signals generated: {total_signals}")
        print(f"Buy signals: {buy_signals}")
        print(f"Sell signals: {sell_signals}")
        print(f"Signal rate: {total_signals/50:.2%}")
        
        # Show signal types
        signal_types = {}
        for signal in signals:
            reason = signal.reason.split(':')[0] if ':' in signal.reason else signal.reason
            signal_types[reason] = signal_types.get(reason, 0) + 1
        
        print("Signal types:")
        for signal_type, count in signal_types.items():
            print(f"  {signal_type}: {count}")
        
        return {
            'total_signals': total_signals,
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'signal_rate': total_signals/50,
            'signal_types': signal_types
        }
    
    def run_parameter_comparison(self):
        """Compare different parameter configurations."""
        print("🚀 Order Book Strategy Parameter Tuning Test")
        print("=" * 60)
        
        # Define different configurations
        configurations = {
            "Conservative (Current)": {
                "order_book_level": 2,
                "trade_history_limit": 100,
                "bid_ask_spread_threshold": 0.001,
                "volume_imbalance_threshold": 0.6,
                "large_trade_threshold": 10000.0,
                "data_analysis_mode": "recent",
                "recent_data_limit": 50
            },
            "Moderate": {
                "order_book_level": 2,
                "trade_history_limit": 200,
                "bid_ask_spread_threshold": 0.002,
                "volume_imbalance_threshold": 0.4,
                "large_trade_threshold": 5000.0,
                "data_analysis_mode": "recent",
                "recent_data_limit": 100
            },
            "Aggressive": {
                "order_book_level": 2,
                "trade_history_limit": 500,
                "bid_ask_spread_threshold": 0.005,
                "volume_imbalance_threshold": 0.3,
                "large_trade_threshold": 2000.0,
                "data_analysis_mode": "all",
                "recent_data_limit": 200
            },
            "Very Aggressive": {
                "order_book_level": 2,
                "trade_history_limit": 1000,
                "bid_ask_spread_threshold": 0.01,
                "volume_imbalance_threshold": 0.2,
                "large_trade_threshold": 1000.0,
                "data_analysis_mode": "all",
                "recent_data_limit": 500
            }
        }
        
        results = {}
        
        for config_name, params in configurations.items():
            results[config_name] = self.test_parameter_configuration(config_name, params)
        
        # Summary comparison
        print("\n📊 Parameter Configuration Comparison")
        print("=" * 60)
        print(f"{'Configuration':<20} {'Signals':<8} {'Rate':<8} {'Buy':<6} {'Sell':<6}")
        print("-" * 60)
        
        for config_name, result in results.items():
            print(f"{config_name:<20} {result['total_signals']:<8} {result['signal_rate']:<8.2%} {result['buy_signals']:<6} {result['sell_signals']:<6}")
        
        # Recommendations
        print("\n💡 Recommendations for More Signals:")
        print("-" * 40)
        print("1. Lower volume_imbalance_threshold (0.3-0.4)")
        print("2. Increase bid_ask_spread_threshold (0.002-0.005)")
        print("3. Lower large_trade_threshold ($2,000-$5,000)")
        print("4. Use data_analysis_mode: 'all' for more data")
        print("5. Increase recent_data_limit (100-200)")
        
        return results

def main():
    """Run the parameter tuning test."""
    tester = OrderBookParameterTester()
    results = tester.run_parameter_comparison()
    
    print(f"\n✅ Parameter tuning test completed!")
    print(f"Tested {len(results)} different configurations.")

if __name__ == "__main__":
    main()
