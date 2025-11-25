
import unittest
import numpy as np
import pandas as pd
from unittest.mock import MagicMock, patch
from datetime import datetime

from trade_bot.ml.data_collector import MLDataCollector, OrderBookFeatures, TradeOutcome
from trade_bot.ml.feature_engineer import FeatureEngineer
from trade_bot.ml.model_trainer import ModelTrainer
from trade_bot.ml.ml_optimizer import MLTradingOptimizer

class TestBatchTraining(unittest.TestCase):
    
    def setUp(self):
        self.feature_engineer = FeatureEngineer()
        self.model_trainer = ModelTrainer()
        
    def test_incremental_feature_engineering(self):
        # Create dummy data
        X_batch1 = np.random.rand(10, 5)
        X_batch2 = np.random.rand(10, 5)
        
        # Test first batch
        X_proc1, _, next_window = self.feature_engineer.preprocess_pipeline_incremental(
            X_batch1, fit=True
        )
        self.assertEqual(X_proc1.shape[0], 10)
        self.assertIsNotNone(next_window)
        
        # Test second batch with window
        X_proc2, _, _ = self.feature_engineer.preprocess_pipeline_incremental(
            X_batch2, fit=True, previous_window=next_window
        )
        self.assertEqual(X_proc2.shape[0], 10)
        
        # Check if scaler was fitted
        self.assertIsNotNone(self.feature_engineer.scaler)
        
    def test_incremental_model_training(self):
        # Create dummy generator
        def data_generator():
            for _ in range(3):
                X = np.random.rand(20, 10)
                # Create outcomes with pnl and is_win
                outcomes = []
                for i in range(20):
                    outcome = MagicMock()
                    outcome.pnl = float(np.random.randn())
                    outcome.is_win = outcome.pnl > 0
                    outcomes.append(outcome)
                yield X, outcomes
                
        results = self.model_trainer.train_incremental(data_generator(), model_type='sgd')
        
        self.assertIn('model_performance', results)
        self.assertIn('sgd_regressor', results['model_performance'])
        self.assertIn('sgd_classifier', results['classifier_performance'])
        self.assertEqual(results['batches_processed'], 3)
        self.assertEqual(results['total_samples'], 60)
        
    @patch('trade_bot.ml.data_collector.MLDataCollector.yield_training_batches')
    def test_optimizer_batch_flow(self, mock_yield_batches):
        # Mock data collector generator
        def mock_gen(batch_size, days_back):
            for _ in range(2):
                features = [OrderBookFeatures(
                    timestamp=1000, symbol='BTC-USD', bid_ask_imbalance=0.1, spread_percent=0.01,
                    mid_price=100.0, bid_volume=10.0, ask_volume=10.0, order_book_depth=10,
                    large_bid_wall=False, large_ask_wall=False, wall_size=0.0, 
                    volume_weighted_price=100.0, price_momentum=0.0, volatility=0.0
                )] * 5
                
                outcomes = [TradeOutcome(
                    trade_id='1', symbol='BTC-USD', side='buy', entry_price=100.0, exit_price=101.0,
                    quantity=1.0, pnl=1.0, fees=0.1, duration_seconds=60, signal_type='test',
                    signal_strength=0.5, entry_timestamp=1000, exit_timestamp=1060, is_win=True
                )] * 5
                
                yield features, outcomes
                
        mock_yield_batches.side_effect = mock_gen
        
        optimizer = MLTradingOptimizer(db_url="sqlite:///:memory:")
        # Mock components to avoid real DB/File IO where possible
        optimizer.model_manager = MagicMock()
        optimizer.model_manager.register_model.return_value = "v1"
        
        results = optimizer.train_ml_models(batch_training=True, batch_size=5)
        
        self.assertIn('model_performance', results)
        self.assertTrue(mock_yield_batches.called)

if __name__ == '__main__':
    unittest.main()
