#!/usr/bin/env python3
"""
Test Order Book strategy with more realistic market conditions.
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

class RealisticOrderBookTester:
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
    
    def create_realistic_scenarios(self) -> dict:
        """Create different realistic market scenarios."""
        scenarios = {}
        base_price = 50000.0
        
        # Scenario 1: Normal market conditions
        scenarios['normal'] = self._create_normal_market(base_price)
        
        # Scenario 2: High volatility with imbalances
        scenarios['volatile'] = self._create_volatile_market(base_price)
        
        # Scenario 3: Low liquidity with wide spreads
        scenarios['low_liquidity'] = self._create_low_liquidity_market(base_price)
        
        # Scenario 4: High volume with large trades
        scenarios['high_volume'] = self._create_high_volume_market(base_price)
        
        return scenarios
    
    def _create_normal_market(self, base_price: float) -> tuple:
        """Create normal market conditions."""
        order_books = []
        trades = []
        
        for i in range(50):
            price = base_price + random.uniform(-500, 500)
            spread = price * 0.0005  # 0.05% spread
            
            # Normal order book
            bids = []
            asks = []
            for level in range(5):
                bid_price = price - (level + 1) * spread
                ask_price = price + (level + 1) * spread
                bid_volume = random.uniform(0.5, 2.0)
                ask_volume = random.uniform(0.5, 2.0)
                
                bids.append({'price': bid_price, 'size': bid_volume})
                asks.append({'price': ask_price, 'size': ask_volume})
            
            order_books.append({
                'order_book': {'bids': bids, 'asks': asks},
                'timestamp': datetime.now() - timedelta(seconds=i)
            })
            
            # Normal trades
            for _ in range(random.randint(1, 3)):
                trade_size = random.uniform(0.01, 0.5)
                trade_price = price + random.uniform(-spread/2, spread/2)
                side = random.choice(['buy', 'sell'])
                
                trades.append({
                    'trade': {
                        'size': str(trade_size),
                        'side': side,
                        'price': str(trade_price),
                        'time': (datetime.now() - timedelta(seconds=i)).isoformat()
                    },
                    'timestamp': datetime.now() - timedelta(seconds=i)
                })
        
        return order_books, trades
    
    def _create_volatile_market(self, base_price: float) -> tuple:
        """Create volatile market with imbalances."""
        order_books = []
        trades = []
        
        for i in range(50):
            price = base_price + random.uniform(-2000, 2000)
            spread = price * random.uniform(0.0002, 0.002)  # Variable spread
            
            # Create imbalances
            bids = []
            asks = []
            for level in range(5):
                bid_price = price - (level + 1) * spread
                ask_price = price + (level + 1) * spread
                
                # Create volume imbalances
                if i % 10 < 3:  # 30% of the time, strong buy pressure
                    bid_volume = random.uniform(2.0, 5.0)
                    ask_volume = random.uniform(0.1, 1.0)
                elif i % 10 < 6:  # 30% of the time, strong sell pressure
                    bid_volume = random.uniform(0.1, 1.0)
                    ask_volume = random.uniform(2.0, 5.0)
                else:  # 40% of the time, balanced
                    bid_volume = random.uniform(0.5, 2.0)
                    ask_volume = random.uniform(0.5, 2.0)
                
                bids.append({'price': bid_price, 'size': bid_volume})
                asks.append({'price': ask_price, 'size': ask_volume})
            
            order_books.append({
                'order_book': {'bids': bids, 'asks': asks},
                'timestamp': datetime.now() - timedelta(seconds=i)
            })
            
            # Volatile trades
            for _ in range(random.randint(2, 8)):
                trade_size = random.uniform(0.01, 2.0)
                trade_price = price + random.uniform(-spread, spread)
                side = random.choice(['buy', 'sell'])
                
                trades.append({
                    'trade': {
                        'size': str(trade_size),
                        'side': side,
                        'price': str(trade_price),
                        'time': (datetime.now() - timedelta(seconds=i)).isoformat()
                    },
                    'timestamp': datetime.now() - timedelta(seconds=i)
                })
        
        return order_books, trades
    
    def _create_low_liquidity_market(self, base_price: float) -> tuple:
        """Create low liquidity market with wide spreads."""
        order_books = []
        trades = []
        
        for i in range(50):
            price = base_price + random.uniform(-1000, 1000)
            spread = price * random.uniform(0.001, 0.01)  # Wide spreads
            
            # Sparse order book
            bids = []
            asks = []
            for level in range(3):  # Fewer levels
                bid_price = price - (level + 1) * spread
                ask_price = price + (level + 1) * spread
                bid_volume = random.uniform(0.01, 0.5)  # Low volume
                ask_volume = random.uniform(0.01, 0.5)
                
                bids.append({'price': bid_price, 'size': bid_volume})
                asks.append({'price': ask_price, 'size': ask_volume})
            
            order_books.append({
                'order_book': {'bids': bids, 'asks': asks},
                'timestamp': datetime.now() - timedelta(seconds=i)
            })
            
            # Few trades
            for _ in range(random.randint(0, 2)):
                trade_size = random.uniform(0.001, 0.1)
                trade_price = price + random.uniform(-spread/2, spread/2)
                side = random.choice(['buy', 'sell'])
                
                trades.append({
                    'trade': {
                        'size': str(trade_size),
                        'side': side,
                        'price': str(trade_price),
                        'time': (datetime.now() - timedelta(seconds=i)).isoformat()
                    },
                    'timestamp': datetime.now() - timedelta(seconds=i)
                })
        
        return order_books, trades
    
    def _create_high_volume_market(self, base_price: float) -> tuple:
        """Create high volume market with large trades."""
        order_books = []
        trades = []
        
        for i in range(50):
            price = base_price + random.uniform(-800, 800)
            spread = price * 0.0003  # Tight spread
            
            # Deep order book
            bids = []
            asks = []
            for level in range(8):  # More levels
                bid_price = price - (level + 1) * spread
                ask_price = price + (level + 1) * spread
                bid_volume = random.uniform(1.0, 10.0)  # High volume
                ask_volume = random.uniform(1.0, 10.0)
                
                bids.append({'price': bid_price, 'size': bid_volume})
                asks.append({'price': ask_price, 'size': ask_volume})
            
            order_books.append({
                'order_book': {'bids': bids, 'asks': asks},
                'timestamp': datetime.now() - timedelta(seconds=i)
            })
            
            # High volume trades with some large ones
            for _ in range(random.randint(5, 15)):
                if random.random() < 0.2:  # 20% large trades
                    trade_size = random.uniform(5.0, 20.0)
                else:
                    trade_size = random.uniform(0.1, 3.0)
                
                trade_price = price + random.uniform(-spread/2, spread/2)
                side = random.choice(['buy', 'sell'])
                
                trades.append({
                    'trade': {
                        'size': str(trade_size),
                        'side': side,
                        'price': str(trade_price),
                        'time': (datetime.now() - timedelta(seconds=i)).isoformat()
                    },
                    'timestamp': datetime.now() - timedelta(seconds=i)
                })
        
        return order_books, trades
    
    def test_parameter_sensitivity(self, scenario_name: str, order_books: list, trades: list):
        """Test how different parameters affect signal generation."""
        print(f"\n🧪 Testing {scenario_name} Market")
        print("-" * 50)
        
        # Test different parameter sets
        parameter_sets = {
            "Very Conservative": {
                "volume_imbalance_threshold": 0.8,
                "bid_ask_spread_threshold": 0.0005,
                "large_trade_threshold": 20000.0
            },
            "Conservative": {
                "volume_imbalance_threshold": 0.6,
                "bid_ask_spread_threshold": 0.001,
                "large_trade_threshold": 10000.0
            },
            "Moderate": {
                "volume_imbalance_threshold": 0.4,
                "bid_ask_spread_threshold": 0.002,
                "large_trade_threshold": 5000.0
            },
            "Aggressive": {
                "volume_imbalance_threshold": 0.3,
                "bid_ask_spread_threshold": 0.005,
                "large_trade_threshold": 2000.0
            },
            "Very Aggressive": {
                "volume_imbalance_threshold": 0.2,
                "bid_ask_spread_threshold": 0.01,
                "large_trade_threshold": 1000.0
            }
        }
        
        results = {}
        
        for param_name, params in parameter_sets.items():
            # Create strategy with these parameters
            strategy = OrderBookStrategy(
                config=self.config,
                order_book_level=2,
                trade_history_limit=100,
                **params
            )
            
            # Add data
            for ob in order_books:
                strategy.add_order_book(ob['order_book'], ob['timestamp'])
            
            for trade in trades:
                strategy.add_trades([trade['trade']], trade['timestamp'])
            
            # Test signal generation
            signals = []
            for i in range(20):
                current_price = 50000.0 + random.uniform(-1000, 1000)
                signal = strategy.generate_signal(
                    current_price=current_price,
                    timestamp=datetime.now()
                )
                
                if signal and signal.action != 'hold':
                    signals.append(signal)
            
            total_signals = len(signals)
            buy_signals = len([s for s in signals if s.action == 'buy'])
            sell_signals = len([s for s in signals if s.action == 'sell'])
            
            results[param_name] = {
                'total_signals': total_signals,
                'buy_signals': buy_signals,
                'sell_signals': sell_signals,
                'signal_rate': total_signals/20
            }
            
            print(f"{param_name:<20}: {total_signals:2d} signals ({total_signals/20:.1%}) - Buy: {buy_signals}, Sell: {sell_signals}")
        
        return results
    
    def run_comprehensive_test(self):
        """Run comprehensive parameter sensitivity test."""
        print("🚀 Order Book Strategy Parameter Sensitivity Test")
        print("=" * 70)
        
        scenarios = self.create_realistic_scenarios()
        all_results = {}
        
        for scenario_name, (order_books, trades) in scenarios.items():
            all_results[scenario_name] = self.test_parameter_sensitivity(
                scenario_name, order_books, trades
            )
        
        # Summary
        print("\n📊 Parameter Sensitivity Summary")
        print("=" * 70)
        print(f"{'Scenario':<15} {'Very Cons':<10} {'Cons':<6} {'Mod':<6} {'Agg':<6} {'Very Agg':<10}")
        print("-" * 70)
        
        for scenario_name, results in all_results.items():
            row = f"{scenario_name:<15}"
            for param_name in ["Very Conservative", "Conservative", "Moderate", "Aggressive", "Very Aggressive"]:
                if param_name in results:
                    signals = results[param_name]['total_signals']
                    row += f" {signals:<10}" if len(str(signals)) > 6 else f" {signals:<6}"
            print(row)
        
        # Recommendations
        print("\n💡 Recommendations for More Signals:")
        print("-" * 50)
        print("1. Use 'Moderate' or 'Aggressive' parameters for more signals")
        print("2. Lower volume_imbalance_threshold to 0.3-0.4")
        print("3. Increase bid_ask_spread_threshold to 0.002-0.005")
        print("4. Lower large_trade_threshold to $2,000-$5,000")
        print("5. Test with different market conditions")
        
        return all_results

def main():
    """Run the comprehensive test."""
    tester = RealisticOrderBookTester()
    results = tester.run_comprehensive_test()
    
    print(f"\n✅ Comprehensive parameter test completed!")

if __name__ == "__main__":
    main()
