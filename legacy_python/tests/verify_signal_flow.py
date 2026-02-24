
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
import sys
import os

# Add src to path
# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))


from trade_bot.trading.strategies.ml_enhanced_orderbook import MLEnhancedOrderBookStrategy
from trade_bot.trading.simulated_trading_manager import SimulatedTradingManager
from trade_bot.core.config import TradingConfig

class TestMLSignalFlow(unittest.TestCase):
    def setUp(self):
        self.config = MagicMock(spec=TradingConfig)
        self.config.product_id = "BTC-USD"
        
    def test_signal_propagation(self):
        # 1. Setup Strategy with mocked ML response
        strategy = MLEnhancedOrderBookStrategy(self.config, fallback_to_baseline=False)
        
        # Mock _get_ml_prediction to return a specific prediction with win_probability
        mock_prediction = {
            'action': 'buy',
            'confidence': 0.85,
            'signal_value': 0.75,
            'win_probability': 78.5,
            'expected_return_percentage': 1.25,
            'reason': 'Test ML Signal'
        }
        strategy._get_ml_prediction = MagicMock(return_value=mock_prediction)
        
        # Mock order book data so generate_signal proceeds
        strategy.bids = [[50000, 1.0]]
        strategy.asks = [[50100, 1.0]]
        
        # 2. Generate Signal
        timestamp = datetime.now(timezone.utc)
        signal = strategy.generate_signal(50050.0, timestamp)
        
        # Verify strategy stored the prediction data correctly
        self.assertEqual(len(strategy.ml_predictions), 1)
        stored_prediction = strategy.ml_predictions[0]
        self.assertEqual(stored_prediction['win_probability'], 78.5)
        self.assertEqual(stored_prediction['expected_return_percentage'], 1.25)
        
        # 3. Setup Manager and process signal
        manager = SimulatedTradingManager(initial_balance=10000.0, config=self.config)
        manager.strategy_instance = strategy
        
        # Manually call generate_signal on manager (which calls strategy)
        # We need to mock strategy.generate_signal to return the signal we just got, 
        # BUT we also need the side effect of storing the prediction which we already did.
        # So we can just use the real strategy instance we set up.
        
        # However, manager.generate_signal calls strategy.generate_signal again.
        # Let's just call manager.generate_signal and let it call the mocked _get_ml_prediction
        
        # Pass valid order book data so the strategy has data to work with
        orderbook_data = {
            'bids': [{'price': 50000, 'size': 1.0}],
            'asks': [{'price': 50100, 'size': 1.0}]
        }
        manager_signal_dict = manager.generate_signal("BTC-USD", 50050.0, timestamp, orderbook_data)

        
        # 4. Verify Manager Output
        print(f"Manager Signal Dict: {manager_signal_dict}")
        
        self.assertIsNotNone(manager_signal_dict)
        self.assertEqual(manager_signal_dict['win_probability'], 78.5)
        self.assertEqual(manager_signal_dict['expected_return'], 1.25)
        self.assertEqual(manager_signal_dict['model_confidence'], 0.85)
        
        # Verify it didn't use the old incorrect mapping
        # Old mapping: win_prob = confidence * 100 = 85.0
        self.assertNotEqual(manager_signal_dict['win_probability'], 85.0)
        
        print("SUCCESS: Signal flow verified correctly!")

if __name__ == '__main__':
    unittest.main()
