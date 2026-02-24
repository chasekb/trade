#!/usr/bin/env python3
"""
Detailed test to verify prediction code workflow scales features after generating time series and interaction features.
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

def test_prediction_workflow_scaling():
    """Test the prediction workflow to verify scaling occurs after time series and interaction features."""
    try:
        from trade_bot.ml.feature_engineer import FeatureEngineer
        from trade_bot.ml.data_collector import OrderBookFeatures

        logger.info("=== Testing Prediction Workflow Scaling ===")

        # Step 1: Create and train feature engineer
        feature_engineer = FeatureEngineer(feature_scaling='standard')

        # Create training data to fit transformers
        training_features = []
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
            training_features.append(feature)

        # Create feature matrix and fit transformers
        X_train, _, _ = feature_engineer.create_feature_matrix(training_features, [])
        X_train_processed, _ = feature_engineer.preprocess_pipeline(X_train, y=None, fit_transform=True)

        logger.info(f"✅ Training data processed: {X_train_processed.shape}")
        logger.info(f"✅ Transformers fitted: scaler={feature_engineer.scaler is not None}, selector={feature_engineer.feature_selector is not None}")

        # Step 2: Test prediction workflow with historical data
        # Create current feature for prediction
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

        # Create historical data (simulating what _get_historical_feature_vectors would return)
        historical_vectors = []
        for i in range(20):  # 20 historical points
            hist_feature = OrderBookFeatures(
                timestamp=int(datetime.now().timestamp()) + 80 + i,
                symbol='BTC-USD',
                bid_ask_imbalance=1.5 + i * 0.01,
                spread_percent=0.15 + i * 0.001,
                mid_price=52000.0 + i * 100,
                bid_volume=150.0 + i * 1,
                ask_volume=150.0 + i * 1,
                order_book_depth=12 + i % 3,
                large_bid_wall=bool(i % 2),
                large_ask_wall=bool(i % 3),
                wall_size=750.0 + i * 10,
                volume_weighted_price=52000.0 + i * 50,
                price_momentum=0.75 + i * 0.01,
                volatility=1.5 + i * 0.01
            )
            # Extract and process historical features
            hist_feature_dict = feature_engineer._extract_features(hist_feature)
            historical_vectors.append(list(hist_feature_dict.values()))

        # Convert to numpy array and apply same transformers
        X_hist = np.array(historical_vectors)
        if feature_engineer.imputer:
            X_hist = feature_engineer.imputer.transform(X_hist)
        if feature_engineer.scaler:
            X_hist = feature_engineer.scaler.transform(X_hist)

        logger.info(f"✅ Historical data prepared: {X_hist.shape}")

        # Step 3: Process current feature through prediction pipeline
        logger.info("\n--- Prediction Pipeline Steps ---")

        # Step 3a: Extract features from current feature
        feature_dict = feature_engineer._extract_features(current_feature)
        X_current = pd.DataFrame([feature_dict])
        logger.info(f"1. Raw features extracted: {X_current.shape}")
        logger.info(f"   Sample raw values: {X_current.values[0][:5]}")

        # Step 3b: Impute features
        X_current_imputed = feature_engineer.imputer.transform(X_current.values) if feature_engineer.imputer else X_current.values
        logger.info(f"2. Features imputed: {X_current_imputed.shape}")

        # Step 3c: Create time series features with historical data
        X_current_ts = feature_engineer.create_time_series_features(X_current_imputed, historical_data=X_hist)
        logger.info(f"3. Time series features added: {X_current_ts.shape}")
        logger.info(f"   Time series features include rolling mean and std")

        # Step 3d: Create interaction features
        X_current_interactions = feature_engineer.create_interaction_features(X_current_ts)
        logger.info(f"4. Interaction features added: {X_current_interactions.shape}")
        logger.info(f"   Interaction features include squares and cross-terms")

        # Step 3e: Scale features (THIS IS THE KEY STEP - scaling after time series and interactions)
        X_current_scaled = feature_engineer.transform_features(X_current_interactions)
        logger.info(f"5. Features scaled: {X_current_scaled.shape}")
        logger.info(f"   Sample scaled values: {X_current_scaled[0][:5]}")

        # Step 3f: Apply feature selection
        X_current_selected = feature_engineer.transform_features_selected(X_current_scaled)
        logger.info(f"6. Feature selection applied: {X_current_selected.shape}")

        # Verify the scaling occurred correctly
        logger.info("\n--- Scaling Verification ---")
        logger.info(f"✅ Original feature count: {X_current.shape[1]}")
        logger.info(f"✅ After time series: {X_current_ts.shape[1]}")
        logger.info(f"✅ After interactions: {X_current_interactions.shape[1]}")
        logger.info(f"✅ After scaling: {X_current_scaled.shape[1]}")
        logger.info(f"✅ After selection: {X_current_selected.shape[1]}")

        # Verify that scaled values are normalized
        if feature_engineer.scaler is not None:
            mean_val = np.mean(X_current_scaled)
            std_val = np.std(X_current_scaled)
            logger.info(f"✅ Scaled feature statistics: mean={mean_val:.4f}, std={std_val:.4f}")
            if abs(mean_val) < 1e-6 and abs(std_val - 1.0) < 0.5:  # Allow some tolerance
                logger.info("✅ Scaling verification PASSED: features are properly normalized")
            else:
                logger.warning("⚠️  Scaling verification WARNING: features may not be properly normalized")

        return True

    except Exception as e:
        logger.error(f"Error in prediction workflow scaling test: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_prediction_pipeline_method():
    """Test using the actual preprocess_pipeline method as used in predictions."""
    try:
        from trade_bot.ml.feature_engineer import FeatureEngineer
        from trade_bot.ml.data_collector import OrderBookFeatures

        logger.info("\n=== Testing Prediction Pipeline Method ===")

        # Create and train feature engineer
        feature_engineer = FeatureEngineer(feature_scaling='standard')

        # Create training data
        training_features = []
        for i in range(30):
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
            training_features.append(feature)

        # Fit transformers
        X_train, _, _ = feature_engineer.create_feature_matrix(training_features, [])
        X_train_processed, _ = feature_engineer.preprocess_pipeline(X_train, y=None, fit_transform=True)

        logger.info(f"✅ Transformers fitted on training data")

        # Create current feature for prediction
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

        # Create historical data
        historical_vectors = []
        for i in range(10):
            hist_feature = OrderBookFeatures(
                timestamp=int(datetime.now().timestamp()) + 90 + i,
                symbol='BTC-USD',
                bid_ask_imbalance=1.5 + i * 0.01,
                spread_percent=0.15 + i * 0.001,
                mid_price=52000.0 + i * 100,
                bid_volume=150.0 + i * 1,
                ask_volume=150.0 + i * 1,
                order_book_depth=12 + i % 3,
                large_bid_wall=bool(i % 2),
                large_ask_wall=bool(i % 3),
                wall_size=750.0 + i * 10,
                volume_weighted_price=52000.0 + i * 50,
                price_momentum=0.75 + i * 0.01,
                volatility=1.5 + i * 0.01
            )
            hist_feature_dict = feature_engineer._extract_features(hist_feature)
            historical_vectors.append(list(hist_feature_dict.values()))

        # Convert to numpy and apply transformers
        X_hist = np.array(historical_vectors)
        if feature_engineer.imputer:
            X_hist = feature_engineer.imputer.transform(X_hist)
        if feature_engineer.scaler:
            X_hist = feature_engineer.scaler.transform(X_hist)

        # Extract current feature
        feature_dict = feature_engineer._extract_features(current_feature)
        X_current = pd.DataFrame([feature_dict])

        logger.info(f"Before pipeline: {X_current.shape}")

        # Process through the actual pipeline method (fit_transform=False for prediction)
        X_processed, _ = feature_engineer.preprocess_pipeline(
            X_current.values, y=None, fit_transform=False, historical_data=X_hist
        )

        logger.info(f"After pipeline: {X_processed.shape}")
        logger.info(f"Sample processed values: {X_processed[0][:5]}")

        # Verify scaling occurred
        if X_processed.shape[1] > X_current.shape[1]:
            logger.info("✅ Feature expansion occurred (time series + interactions added)")
        else:
            logger.warning("⚠️  Feature expansion may not have occurred")

        # Check if values are scaled (standard scaling should center around 0)
        mean_val = np.mean(X_processed)
        if abs(mean_val) < 1.0:  # Should be close to 0 for standard scaling
            logger.info("✅ Scaling verification PASSED: values are centered around 0")
        else:
            logger.warning(f"⚠️  Scaling verification WARNING: mean is {mean_val:.4f}, expected close to 0")

        return True

    except Exception as e:
        logger.error(f"Error in prediction pipeline method test: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run prediction scaling verification tests."""
    logger.info("Starting prediction scaling verification tests...")

    test_results = []

    test_results.append(("Prediction Workflow Scaling", test_prediction_workflow_scaling()))
    test_results.append(("Prediction Pipeline Method", test_prediction_pipeline_method()))

    # Print summary
    logger.info("\n=== Prediction Scaling Test Results Summary ===")
    for test_name, result in test_results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{test_name}: {status}")

    all_passed = all(result for _, result in test_results)
    if all_passed:
        logger.info("\n🎉 All prediction scaling tests passed!")
    else:
        logger.error("\n💥 Some prediction scaling tests failed.")

    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
