"""Tests for ML Strategy implementation."""

import pytest
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.trade_bot.trading.strategies.ml_strategy import MLStrategy
from src.trade_bot.trading.strategies.ml_signal import MLSignalGenerator, MLSignalResult


class TestMLStrategy:
    """Test cases for ML Strategy."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.strategy = MLStrategy(
            name="Test ML Strategy",
            min_win_probability=0.6,
            min_expected_return=0.01,
            min_confidence=0.3
        )
        
        # Mock some price data
        self.strategy.prices = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110]
        self.strategy.symbol = "BTC-USD"
    
    def test_ml_strategy_initialization(self):
        """Test ML strategy initialization."""
        assert self.strategy.name == "Test ML Strategy"
        assert self.strategy.ml_enabled is True
        assert self.strategy.min_win_probability == 0.6
        assert self.strategy.min_expected_return == 0.01
        assert self.strategy.min_confidence == 0.3
        assert self.strategy.prediction_accuracy == 0.0
    
    def test_traditional_signal_generation(self):
        """Test traditional signal generation."""
        # Test with RSI oversold condition
        self.strategy.prices = [100, 99, 98, 97, 96, 95, 94, 93, 92, 91, 90, 89, 88, 87, 86]
        
        signal = self.strategy._get_traditional_signal(85.0)
        assert signal in ["buy", "sell", "hold"]
    
    def test_ml_signal_generation_without_model(self):
        """Test ML signal generation when no model is trained."""
        # Mock ML generator without trained model
        self.strategy.ml_generator.is_trained = False
        
        signal = self.strategy.generate_signal(100.0, datetime.now())
        assert signal in ["buy", "sell", "hold"]
    
    @patch('src.trade_bot.trading.strategies.ml_strategy.MLSignalGenerator')
    def test_ml_signal_generation_with_model(self, mock_ml_generator):
        """Test ML signal generation with trained model."""
        # Mock ML signal result
        mock_ml_result = MLSignalResult(
            win_probability=0.7,
            expected_return=0.02,
            confidence=0.8,
            features_used=["price", "volume"],
            model_version="1.0.0",
            prediction_timestamp=datetime.now()
        )
        
        # Mock ML generator
        mock_generator = Mock()
        mock_generator.is_trained = True
        mock_generator.generate_signal.return_value = mock_ml_result
        self.strategy.ml_generator = mock_generator
        
        signal = self.strategy.generate_signal(100.0, datetime.now())
        assert signal in ["buy", "sell", "hold"]
    
    def test_signal_combination_buy(self):
        """Test signal combination for buy signal."""
        # Mock ML signal that meets buy criteria
        mock_ml_signal = MLSignalResult(
            win_probability=0.7,  # > min_win_probability (0.6)
            expected_return=0.02,  # > min_expected_return (0.01)
            confidence=0.8,  # > min_confidence (0.3)
            features_used=["price", "volume"],
            model_version="1.0.0",
            prediction_timestamp=datetime.now()
        )
        
        traditional_signal = "buy"
        final_signal = self.strategy._combine_signals(traditional_signal, mock_ml_signal, 100.0)
        
        assert final_signal == "buy"
    
    def test_signal_combination_sell(self):
        """Test signal combination for sell signal."""
        # Mock ML signal that meets sell criteria
        mock_ml_signal = MLSignalResult(
            win_probability=0.3,  # < (1 - min_win_probability) (0.4)
            expected_return=-0.02,  # < -min_expected_return (-0.01)
            confidence=0.8,  # > min_confidence (0.3)
            features_used=["price", "volume"],
            model_version="1.0.0",
            prediction_timestamp=datetime.now()
        )
        
        traditional_signal = "sell"
        final_signal = self.strategy._combine_signals(traditional_signal, mock_ml_signal, 100.0)
        
        assert final_signal == "sell"
    
    def test_signal_combination_hold(self):
        """Test signal combination for hold signal."""
        # Mock ML signal that doesn't meet criteria
        mock_ml_signal = MLSignalResult(
            win_probability=0.5,  # < min_win_probability (0.6)
            expected_return=0.005,  # < min_expected_return (0.01)
            confidence=0.2,  # < min_confidence (0.3)
            features_used=["price", "volume"],
            model_version="1.0.0",
            prediction_timestamp=datetime.now()
        )
        
        traditional_signal = "hold"
        final_signal = self.strategy._combine_signals(traditional_signal, mock_ml_signal, 100.0)
        
        assert final_signal == "hold"
    
    def test_prediction_accuracy_update(self):
        """Test prediction accuracy update."""
        # Add some mock predictions
        self.strategy.ml_predictions = [
            {'timestamp': datetime.now(), 'prediction': None, 'price': 100, 'signal': 'buy'},
            {'timestamp': datetime.now(), 'prediction': None, 'price': 101, 'signal': 'sell'}
        ]
        
        # Update accuracy with correct prediction
        self.strategy.update_prediction_accuracy(0.05, "buy")  # Positive P&L, buy signal
        
        assert self.strategy.prediction_accuracy > 0
    
    def test_strategy_info(self):
        """Test strategy info retrieval."""
        info = self.strategy.get_strategy_info()
        
        assert 'ml_enabled' in info
        assert 'ml_model_info' in info
        assert 'prediction_accuracy' in info
        assert 'min_win_probability' in info
        assert info['ml_enabled'] is True
    
    def test_detailed_signal_analysis(self):
        """Test detailed signal analysis."""
        analysis = self.strategy.get_detailed_signal_analysis(100.0, datetime.now())
        
        assert 'final_signal' in analysis
        assert 'traditional_signal' in analysis
        assert 'ml_enabled' in analysis
        assert 'strategy_info' in analysis
        assert analysis['final_signal'] in ["buy", "sell", "hold"]


class TestMLSignalGenerator:
    """Test cases for ML Signal Generator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.generator = MLSignalGenerator()
    
    def test_ml_generator_initialization(self):
        """Test ML generator initialization."""
        assert self.generator.model is None
        assert self.generator.feature_scaler is None
        assert self.generator.feature_columns == []
        assert self.generator.is_trained is False
    
    def test_feature_extraction(self):
        """Test feature extraction from trade data."""
        trades = [
            {'pnl': 10.0, 'quantity': 1.0, 'price': 100.0, 'timestamp': '2023-01-01T00:00:00Z'},
            {'pnl': -5.0, 'quantity': 0.5, 'price': 101.0, 'timestamp': '2023-01-01T01:00:00Z'},
            {'pnl': 15.0, 'quantity': 1.5, 'price': 102.0, 'timestamp': '2023-01-01T02:00:00Z'}
        ]
        
        orderbook_data = {
            'bids': [['100.0', '1.0'], ['99.9', '2.0']],
            'asks': [['100.1', '1.0'], ['100.2', '2.0']]
        }
        
        features = self.generator._extract_features(trades, orderbook_data, 100.0, "BTC-USD")
        
        assert isinstance(features, dict)
        assert 'avg_pnl_5' in features
        assert 'win_rate_10' in features
        assert 'spread_abs' in features
        assert 'current_price' in features
    
    def test_trend_calculation(self):
        """Test trend calculation."""
        values = [1, 2, 3, 4, 5]
        trend = self.generator._calculate_trend(values)
        assert trend > 0  # Upward trend
        
        values = [5, 4, 3, 2, 1]
        trend = self.generator._calculate_trend(values)
        assert trend < 0  # Downward trend
    
    def test_volatility_calculation(self):
        """Test volatility calculation."""
        trades = [
            {'price': 100.0},
            {'price': 101.0},
            {'price': 99.0},
            {'price': 102.0},
            {'price': 98.0}
        ]
        
        volatility = self.generator._calculate_volatility(trades)
        assert volatility >= 0
    
    def test_generate_signal_without_model(self):
        """Test signal generation without trained model."""
        result = self.generator.generate_signal([], {}, 100.0, "BTC-USD")
        
        assert isinstance(result, MLSignalResult)
        assert result.win_probability == 0.5
        assert result.expected_return == 0.0
        assert result.confidence == 0.0
    
    def test_model_info(self):
        """Test model info retrieval."""
        info = self.generator.get_model_info()
        
        assert 'is_trained' in info
        assert 'model_version' in info
        assert 'feature_count' in info
        assert 'feature_columns' in info
        assert 'model_path' in info
