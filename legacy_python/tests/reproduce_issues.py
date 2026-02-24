
import asyncio
import logging
from datetime import datetime
from unittest.mock import MagicMock, patch
import sys
import os

# Add src to path
sys.path.append(os.path.abspath("src"))

from trade_bot.trading.strategies.ml_enhanced_orderbook import MLEnhancedOrderBookStrategy
from trade_bot.trading.simulated_trading_manager import SimulatedTradingManager
from trade_bot.core.config import TradingConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_signal_strength_normalization():
    print("\n--- Testing Signal Strength Normalization ---")
    
    # Mock dependencies
    config = MagicMock(spec=TradingConfig)
    config.ml_server_host = "localhost"
    config.ml_server_port = 5000
    
    strategy = MLEnhancedOrderBookStrategy(config)
    
    # Mock ML prediction with confidence > 1.0 (e.g., 85.5)
    mock_prediction = {
        'action': 'buy',
        'confidence': 85.5,
        'signal_value': 1,
        'reason': 'Test Signal'
    }
    
    # Mock _get_ml_prediction to return our mock prediction
    strategy._get_ml_prediction = MagicMock(return_value=mock_prediction)
    strategy.calculate_position_size = MagicMock(return_value=1.0)
    
    # Mock bids and asks
    strategy.bids = [{'price': 49900, 'size': 1.0}]
    strategy.asks = [{'price': 50100, 'size': 1.0}]

    # Generate signal
    signal = strategy.generate_signal(
        current_price=50000.0,
        timestamp=datetime.now()
    )
    
    if signal:
        print(f"Original Confidence: {mock_prediction['confidence']}")
        print(f"Normalized Strength: {signal.strength}")
        
        if 0.0 <= signal.strength <= 1.0:
            print("✅ SUCCESS: Signal strength normalized correctly.")
        else:
            print("❌ FAILURE: Signal strength NOT normalized.")
    else:
        print("❌ FAILURE: No signal generated.")

async def test_trade_execution_logging():
    print("\n--- Testing Trade Execution Logging ---")
    
    # Mock dependencies
    config = MagicMock(spec=TradingConfig)
    db_manager = MagicMock()
    model_manager = MagicMock()
    
    manager = SimulatedTradingManager(
        initial_balance=10000.0,
        db_manager=db_manager,
        model_manager=model_manager,
        config=config
    )
    
    # 1. Test skipping buy due to existing position
    print("\nTest 1: Skipping buy due to existing position")
    manager.positions = {
        "BTC-USD": MagicMock(status='open')
    }
    
    with patch('trade_bot.trading.simulated_trading_manager.logger') as mock_logger:
        await manager._process_buy_signal(
            symbol="BTC-USD",
            price=50000.0,
            strength=0.8,
            signal={}
        )
        
        # Check if correct log message was called
        expected_msg = "Skipping buy for BTC-USD: Already have open position"
        if any(expected_msg in str(call) for call in mock_logger.info.call_args_list):
             print(f"✅ SUCCESS: Logged '{expected_msg}'")
        else:
             print(f"❌ FAILURE: Did not log '{expected_msg}'")

    # 2. Test skipping buy due to max positions
    print("\nTest 2: Skipping buy due to max positions")
    manager.positions = {
        "ETH-USD": MagicMock(status='open'),
        "SOL-USD": MagicMock(status='open'),
        "ADA-USD": MagicMock(status='open')
    }
    manager.max_positions = 3
    
    with patch('trade_bot.trading.simulated_trading_manager.logger') as mock_logger:
        await manager._process_buy_signal(
            symbol="BTC-USD",
            price=50000.0,
            strength=0.8,
            signal={}
        )
        
        expected_msg = "Skipping buy for BTC-USD: Max positions (3) reached"
        if any(expected_msg in str(call) for call in mock_logger.info.call_args_list):
             print(f"✅ SUCCESS: Logged '{expected_msg}'")
        else:
             print(f"❌ FAILURE: Did not log '{expected_msg}'")

if __name__ == "__main__":
    asyncio.run(test_signal_strength_normalization())
    asyncio.run(test_trade_execution_logging())
