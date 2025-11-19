
import unittest
from unittest.mock import MagicMock, patch
import numpy as np
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from trade_bot.ml.model_trainer import TradingModelWrapper, ModelTrainer
from trade_bot.ml.ml_optimizer import MLTradingOptimizer
from trade_bot.ml.data_collector import OrderBookFeatures

class TestMLRefinement(unittest.TestCase):
    def test_trading_model_wrapper(self):
        """Test TradingModelWrapper delegates correctly."""
        regressor = MagicMock()
        classifier = MagicMock()
        
        regressor.predict.return_value = np.array([0.5])
        classifier.predict_proba.return_value = np.array([[0.2, 0.8]])
        
        wrapper = TradingModelWrapper(regressor, classifier)
        
        # Test predict (regressor)
        X = np.array([[1, 2, 3]])
        pred = wrapper.predict(X)
        regressor.predict.assert_called_with(X)
        self.assertEqual(pred[0], 0.5)
        
        # Test predict_proba (classifier)
        prob = wrapper.predict_proba(X)
        classifier.predict_proba.assert_called_with(X)
        self.assertEqual(prob[0][1], 0.8)
        
    def test_model_trainer_classifiers(self):
        """Test ModelTrainer can train classifiers."""
        trainer = ModelTrainer()
        
        # Create dummy data
        X = np.random.rand(100, 5)
        y = np.random.randint(0, 2, 100)
        
        results = trainer.train_classifiers(X, y, test_size=0.2)
        
        self.assertIn('classifier_performance', results)
        self.assertIn('best_classifier', results)
        self.assertIsNotNone(trainer.best_classifier)
        
    @patch('trade_bot.ml.ml_optimizer.ModelManager')
    @patch('trade_bot.ml.ml_optimizer.VectorDBClient')
    @patch('trade_bot.ml.ml_optimizer.MLDataCollector')
    @patch('trade_bot.ml.ml_optimizer.FeatureEngineer')
    def test_optimizer_prediction_logic(self, MockFE, MockDC, MockVDB, MockMM):
        """Test MLTradingOptimizer uses wrapper for prediction."""
        optimizer = MLTradingOptimizer()
        
        # Mock feature engineer
        optimizer.feature_engineer.preprocess_pipeline.return_value = (np.array([[1, 2]]), None)
        optimizer.feature_engineer._extract_features.return_value = {'f1': 1, 'f2': 2}
        
        # Mock model manager to return wrapper
        regressor = MagicMock()
        classifier = MagicMock()
        regressor.predict.return_value = np.array([0.5]) # Signal value
        classifier.predict_proba.return_value = np.array([[0.3, 0.7]]) # 70% win prob
        
        wrapper = TradingModelWrapper(regressor, classifier)
        
        # Mock get_current_model to return the wrapper
        optimizer.model_manager.get_current_model.return_value = wrapper
        
        # Mock predict to return regressor output (as it calls wrapper.predict)
        optimizer.model_manager.predict.return_value = np.array([0.5])
        
        # Create dummy features
        features = OrderBookFeatures(
            timestamp=1234567890, symbol="BTC-USD", bid_ask_imbalance=0.1, spread_percent=0.01,
            mid_price=100.0, bid_volume=10.0, ask_volume=10.0, order_book_depth=10,
            large_bid_wall=False, large_ask_wall=False, wall_size=0.0, volume_weighted_price=100.0,
            price_momentum=0.0, volatility=0.0
        )
        
        # Run prediction
        result = optimizer.predict_trading_signal(features)
        
        # Verify results
        self.assertEqual(result['signal_value'], 0.5)
        self.assertEqual(result['win_probability'], 70.0) # Should be 0.7 * 100
        
        # Verify fallback logic (if classifier is missing)
        wrapper_no_clf = TradingModelWrapper(regressor, None)
        optimizer.model_manager.get_current_model.return_value = wrapper_no_clf
        
        result_fallback = optimizer.predict_trading_signal(features)
        
        # Heuristic: min(max(0.5 * 1000, 10), 90) = 90 (capped)
        # 0.5 * 1000 = 500. max(500, 10) = 500. min(500, 90) = 90.
        self.assertEqual(result_fallback['win_probability'], 90.0)

if __name__ == '__main__':
    unittest.main()
