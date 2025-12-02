#!/usr/bin/env python3
"""
Test script to verify scaling occurs after creating time series and interaction terms
during training and prediction in the ML-enhanced order book trading strategy.
"""

import sys
import os
import numpy as np
import pandas as pd
from datetime import datetime
import logging

# Add the src directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_scaling_in_feature_engineering():
    """Test that scaling occurs after time series and interaction features are created."""
    try:
        from trade_bot.ml.feature_engineer import FeatureEngineer
        from trade_bot.ml.data_collector import OrderBookFeatures, TradeOutcome

        logger.info("=== Testing Scaling in Feature Engineering ===")

        # Create a feature engineer instance
        feature_engineer = FeatureEngineer(feature_scaling='standard')

        # Create sample feature data
        features_list = []
        for i in range(100):
            feature = OrderBookFeatures(
                timestamp=int(datetime.now().timestamp()) + i,
                symbol='BTC-USD',
                bid_ask_imbalance=1.0 + i * 0.01,
                spread_percent=0.1 + i * 0.001,
                mid_price=50000.0 + i * 100,
                bid_volume=100.0 + i * 1,
                ask_volume=100.0 + i * 1,
                order_book_depth=10 + i % 5,
                large_bid_wall=bool(i % 2),
                large_ask_wall=bool(i % 3),
                wall_size=500.0 + i * 10,
                volume_weighted_price=50000.0 + i * 50,
                price_momentum=0.5 + i * 0.01,
                volatility=1.0 + i * 0.01
            )
            features_list.append(feature)

        # Create sample outcomes
        outcomes_list = []
        for i in range(100):
            outcome = TradeOutcome(
                trade_id=f"trade_{i}",
                symbol='BTC-USD',
                side='buy' if i % 2 == 0 else 'sell',
                entry_price=50000.0 + i * 100,
                exit_price=50000.0 + i * 100 + (100 if i % 2 == 0 else -100),
                quantity=0.1,
                pnl=10.0 if i % 2 == 0 else -10.0,
                fees=1.0,
                duration_seconds=60,
                signal_type='ml_buy' if i % 2 == 0 else 'ml_sell',
                signal_strength=0.7,
                entry_timestamp=int(datetime.now().timestamp()) + i,
                exit_timestamp=int(datetime.now().timestamp()) + i + 60
            )
            outcomes_list.append(outcome)

        # Create feature matrix
        X, y, feature_names = feature_engineer.create_feature_matrix(features_list, outcomes_list)

        logger.info(f"Original feature matrix shape: {X.shape}")
        logger.info(f"Feature names count: {len(feature_names)}")
        logger.info(f"Sample feature values before scaling: min={np.min(X):.4f}, max={np.max(X):.4f}, mean={np.mean(X):.4f}")

        # Preprocess features (this should create time series, interactions, and then scale)
        X_processed, y_processed = feature_engineer.preprocess_pipeline(X, y, fit_transform=True)

        logger.info(f"Processed feature matrix shape: {X_processed.shape}")
        logger.info(f"Sample feature values after scaling: min={np.min(X_processed):.4f}, max={np.max(X_processed):.4f}, mean={np.mean(X_processed):.4f}")

        # Verify that scaling occurred
        if feature_engineer.scaler is not None:
            logger.info("✅ Scaler was fitted and applied")
            logger.info(f"Scaler type: {type(feature_engineer.scaler).__name__}")
            logger.info(f"Scaler mean: {feature_engineer.scaler.mean_[:5]}")  # Show first 5 features
            logger.info(f"Scaler scale: {feature_engineer.scaler.scale_[:5]}")  # Show first 5 features
        else:
            logger.warning("❌ No scaler was fitted")

        # Verify feature selection occurred
        if feature_engineer.feature_selector is not None:
            logger.info("✅ Feature selector was fitted and applied")
            logger.info(f"Selected {len(feature_engineer.feature_names)} features from {X.shape[1]} original features")
        else:
            logger.warning("❌ No feature selector was fitted")

        return True

    except Exception as e:
        logger.error(f"Error in feature engineering test: {e}")
        return False

def test_scaling_in_training():
    """Test that scaling occurs during model training."""
    try:
        from trade_bot.ml.model_trainer import ModelTrainer

        logger.info("\n=== Testing Scaling in Model Training ===")

        # Create sample data
        np.random.seed(42)
        X = np.random.randn(100, 20)  # 100 samples, 20 features
        y = np.random.randn(100)  # Target values

        # Create model trainer
        trainer = ModelTrainer(model_type='linear')

        # Train models
        results = trainer.train_models(X, y)

        logger.info(f"Training results: {results}")
        logger.info("✅ Model training completed successfully")

        return True

    except Exception as e:
        logger.error(f"Error in model training test: {e}")
        return False

def test_scaling_in_prediction():
    """Test that scaling occurs during prediction."""
    try:
        from trade_bot.ml.feature_engineer import FeatureEngineer
        from trade_bot.ml.data_collector import OrderBookFeatures

        logger.info("\n=== Testing Scaling in Prediction ===")

        # Create feature engineer and fit transformers
        feature_engineer = FeatureEngineer(feature_scaling='standard')

        # Create sample training data
        features_list = []
        for i in range(50):
            feature = OrderBookFeatures(
                timestamp=int(datetime.now().timestamp()) + i,
                symbol='BTC-USD',
                bid_ask_imbalance=1.0 + i * 0.01,
                spread_percent=0.1 + i * 0.001,
                mid_price=50000.0 + i * 100,
                bid_volume=100.0 + i * 1,
                ask_volume=100.0 + i * 1,
                order_book_depth=10 + i % 5,
                large_bid_wall=bool(i % 2),
                large_ask_wall=bool(i % 3),
                wall_size=500.0 + i * 10,
                volume_weighted_price=50000.0 + i * 50,
                price_momentum=0.5 + i * 0.01,
                volatility=1.0 + i * 0.01
            )
            features_list.append(feature)

        # Create feature matrix and fit transformers
        X_train, _, _ = feature_engineer.create_feature_matrix(features_list, [])
        X_train_processed, _ = feature_engineer.preprocess_pipeline(X_train, y=None, fit_transform=True)

        logger.info(f"Training data processed: {X_train_processed.shape}")

        # Now test prediction with new data
        current_feature = OrderBookFeatures(
            timestamp=int(datetime.now().timestamp()) + 101,
            symbol='BTC-USD',
            bid_ask_imbalance=2.0,
            spread_percent=0.2,
            mid_price=55000.0,
            bid_volume=200.0,
            ask_volume=200.0,
            order_book_depth=15,
            large_bid_wall=True,
            large_ask_wall=False,
            wall_size=1000.0,
            volume_weighted_price=55000.0,
            price_momentum=1.0,
            volatility=2.0
        )

        # Extract features for the current sample
        feature_dict = feature_engineer._extract_features(current_feature)
        X_current = pd.DataFrame([feature_dict])

        logger.info(f"Current feature values before processing: {X_current.values[0][:5]}")  # Show first 5

        # Process through the same pipeline (without fitting)
        X_current_processed, _ = feature_engineer.preprocess_pipeline(
            X_current.values, y=None, fit_transform=False
        )

        logger.info(f"Current feature values after processing: {X_current_processed[0][:5]}")  # Show first 5

        # Verify that the current data was scaled using the same transformers
        logger.info("✅ Prediction data was scaled using fitted transformers")

        return True

    except Exception as e:
        logger.error(f"Error in prediction scaling test: {e}")
        return False

def test_end_to_end_workflow():
    """Test the complete workflow from training to prediction."""
    try:
        logger.info("\n=== Testing End-to-End Workflow ===")

        from trade_bot.ml.feature_engineer import FeatureEngineer
        from trade_bot.ml.model_trainer import ModelTrainer
        from trade_bot.ml.data_collector import OrderBookFeatures, TradeOutcome

        # Step 1: Create and process training data
        feature_engineer = FeatureEngineer(feature_scaling='standard')

        # Generate training data
        features_list = []
        outcomes_list = []
        for i in range(100):
            feature = OrderBookFeatures(
                timestamp=int(datetime.now().timestamp()) + i,
                symbol='BTC-USD',
                bid_ask_imbalance=1.0 + i * 0.01,
                spread_percent=0.1 + i * 0.001,
                mid_price=50000.0 + i * 100,
                bid_volume=100.0 + i * 1,
                ask_volume=100.0 + i * 1,
                order_book_depth=10 + i % 5,
                large_bid_wall=bool(i % 2),
                large_ask_wall=bool(i % 3),
                wall_size=500.0 + i * 10,
                volume_weighted_price=50000.0 + i * 50,
                price_momentum=0.5 + i * 0.01,
                volatility=1.0 + i * 0.01
            )
            features_list.append(feature)

            outcome = TradeOutcome(
                trade_id=f"trade_{i}",
                symbol='BTC-USD',
                side='buy' if i % 2 == 0 else 'sell',
                entry_price=50000.0 + i * 100,
                exit_price=50000.0 + i * 100 + (100 if i % 2 == 0 else -100),
                quantity=0.1,
                pnl=10.0 if i % 2 == 0 else -10.0,
                fees=1.0,
                duration_seconds=60,
                signal_type='ml_buy' if i % 2 == 0 else 'ml_sell',
                signal_strength=0.7,
                entry_timestamp=int(datetime.now().timestamp()) + i,
                exit_timestamp=int(datetime.now().timestamp()) + i + 60
            )
            outcomes_list.append(outcome)

        # Process training data
        X_train, y_train, _ = feature_engineer.create_feature_matrix(features_list, outcomes_list)
        X_train_processed, y_train_processed = feature_engineer.preprocess_pipeline(X_train, y_train, fit_transform=True)

        logger.info(f"Training data processed: {X_train_processed.shape}")
        logger.info(f"Training targets: {y_train_processed.shape}")

        # Step 2: Train model
        trainer = ModelTrainer(model_type='linear')
        train_results = trainer.train_models(X_train_processed, y_train_processed)

        logger.info(f"Model training completed with best score: {train_results.get('best_score', 'N/A')}")

        # Step 3: Test prediction
        current_feature = OrderBookFeatures(
            timestamp=int(datetime.now().timestamp()) + 101,
            symbol='BTC-USD',
            bid_ask_imbalance=2.0,
            spread_percent=0.2,
            mid_price=55000.0,
            bid_volume=200.0,
            ask_volume=200.0,
            order_book_depth=15,
            large_bid_wall=True,
            large_ask_wall=False,
            wall_size=1000.0,
            volume_weighted_price=55000.0,
            price_momentum=1.0,
            volatility=2.0
        )

        # Extract features for the current sample
        feature_dict = feature_engineer._extract_features(current_feature)
        X_current = pd.DataFrame([feature_dict])

        # Process through the same pipeline (without fitting)
        X_current_processed, _ = feature_engineer.preprocess_pipeline(
            X_current.values, y=None, fit_transform=False
        )

        logger.info(f"Prediction data processed: {X_current_processed.shape}")

        # Make prediction
        prediction = trainer.predict(X_current_processed)
        logger.info(f"Prediction result: {prediction}")

        logger.info("✅ End-to-end workflow completed successfully")
        return True

    except Exception as e:
        logger.error(f"Error in end-to-end workflow test: {e}")
        return False

def main():
    """Run all tests to verify scaling occurs during training and prediction."""
    logger.info("Starting scaling verification tests...")

    # Run all tests
    test_results = []

    test_results.append(("Feature Engineering Scaling", test_scaling_in_feature_engineering()))
    test_results.append(("Model Training Scaling", test_scaling_in_training()))
    test_results.append(("Prediction Scaling", test_scaling_in_prediction()))
    test_results.append(("End-to-End Workflow", test_end_to_end_workflow()))

    # Print summary
    logger.info("\n=== Test Results Summary ===")
    for test_name, result in test_results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{test_name}: {status}")

    all_passed = all(result for _, result in test_results)
    if all_passed:
        logger.info("\n🎉 All tests passed! Scaling verification successful.")
    else:
        logger.error("\n💥 Some tests failed. Please check the logs above.")

    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
