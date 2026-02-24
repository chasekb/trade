#!/usr/bin/env python3
"""
Test your specific Order Book strategy parameters.
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.trade_bot.trading_strategy import OrderBookStrategy
from src.trade_bot.config import TradingConfig

def test_your_parameters():
    """Test your specific parameter configuration."""
    
    # Your custom parameters - MODIFY THESE
    your_parameters = {
        "order_book_level": 2,
        "trade_history_limit": 1000,
        "bid_ask_spread_threshold": 0.002,        # Try 0.001, 0.002, 0.005
        "volume_imbalance_threshold": 0.4,        # Try 0.6, 0.4, 0.3
        "large_trade_threshold": 5000.0,          # Try 10000, 5000, 2000
        "data_analysis_mode": "recent",           # Try "recent", "all"
        "recent_data_limit": 100,                 # Try 50, 100, 200
        "sampling_ratio": 0.1
    }
    
    print("🧪 Testing Your Order Book Strategy Parameters")
    print("=" * 60)
    print("Parameters:")
    for key, value in your_parameters.items():
        print(f"  {key}: {value}")
    print()
    
    # Create config
    config = TradingConfig(
        product_id="BTC-USD",
        api_key="test",
        api_secret="test", 
        passphrase="test",
        max_position_size=1.0,
        stop_loss_percentage=0.02,
        take_profit_percentage=0.04
    )
    
    # Create strategy
    strategy = OrderBookStrategy(config, **your_parameters)
    
    # Create realistic test data
    print("Creating test market data...")
    
    # Add some order book data with imbalances
    for i in range(20):
        base_price = 50000.0 + (i * 100)
        spread = base_price * 0.001  # 0.1% spread
        
        # Create order book with varying imbalances
        bids = []
        asks = []
        
        for level in range(5):
            bid_price = base_price - (level + 1) * spread
            ask_price = base_price + (level + 1) * spread
            
            # Create imbalances every few iterations
            if i % 5 < 2:  # 40% of the time, create buy pressure
                bid_volume = 3.0 + (level * 0.5)
                ask_volume = 0.5 + (level * 0.1)
            elif i % 5 < 4:  # 40% of the time, create sell pressure
                bid_volume = 0.5 + (level * 0.1)
                ask_volume = 3.0 + (level * 0.5)
            else:  # 20% of the time, balanced
                bid_volume = 1.0 + (level * 0.2)
                ask_volume = 1.0 + (level * 0.2)
            
            bids.append({'price': bid_price, 'size': bid_volume})
            asks.append({'price': ask_price, 'size': ask_volume})
        
        order_book = {'bids': bids, 'asks': asks}
        strategy.add_order_book(order_book, datetime.now() - timedelta(seconds=i))
    
    # Add some trade data with large trades
    for i in range(30):
        base_price = 50000.0 + (i * 50)
        
        # Create some large trades
        if i % 7 < 2:  # 28% of the time, create large trades
            trade_size = 15.0  # Large trade
        else:
            trade_size = 1.0   # Normal trade
        
        trade = {
            'size': str(trade_size),
            'side': 'buy' if i % 2 == 0 else 'sell',
            'price': str(base_price),
            'time': (datetime.now() - timedelta(seconds=i)).isoformat()
        }
        
        strategy.add_trades([trade], datetime.now() - timedelta(seconds=i))
    
    # Test signal generation
    print("Testing signal generation...")
    signals = []
    
    for i in range(50):
        current_price = 50000.0 + (i * 20)
        signal = strategy.generate_signal(
            current_price=current_price,
            timestamp=datetime.now()
        )
        
        if signal and signal.action != 'hold':
            signals.append(signal)
            print(f"Signal {len(signals)}: {signal.action.upper()} - {signal.reason}")
    
    # Results
    total_signals = len(signals)
    buy_signals = len([s for s in signals if s.action == 'buy'])
    sell_signals = len([s for s in signals if s.action == 'sell'])
    
    print(f"\n📊 Results:")
    print(f"Total signals generated: {total_signals}")
    print(f"Buy signals: {buy_signals}")
    print(f"Sell signals: {sell_signals}")
    print(f"Signal rate: {total_signals/50:.1%}")
    
    if total_signals == 0:
        print("\n❌ No signals generated. Try more aggressive parameters:")
        print("   - Lower volume_imbalance_threshold to 0.3")
        print("   - Increase bid_ask_spread_threshold to 0.005")
        print("   - Lower large_trade_threshold to 2000")
    elif total_signals < 10:
        print("\n⚠️  Few signals generated. Consider moderate parameters:")
        print("   - Lower volume_imbalance_threshold to 0.4")
        print("   - Increase bid_ask_spread_threshold to 0.002")
        print("   - Lower large_trade_threshold to 5000")
    else:
        print(f"\n✅ Good signal generation! ({total_signals} signals)")
    
    return total_signals

if __name__ == "__main__":
    test_your_parameters()
