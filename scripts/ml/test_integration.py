#!/usr/bin/env python3
"""ML Integration Test Script for Trading Optimization."""

import logging
import sys
import os
import requests
import time
import json
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trade_bot.ml.ml_optimizer import MLTradingOptimizer
from trade_bot.ml.data_collector import OrderBookFeatures

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'outputs/ml_integration_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def test_vector_database_connection():
    """Test vector database connection."""
    logger.info("Testing vector database connection...")
    
    try:
        # Test Qdrant connection
        response = requests.get("http://localhost:6333/health", timeout=5)
        if response.status_code == 200:
            logger.info("✅ Qdrant Vector Database connection successful")
        else:
            logger.error(f"❌ Qdrant connection failed: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Qdrant connection failed: {e}")
        return False
    
    try:
        # Test Redis connection
        import redis
        r = redis.Redis(host='localhost', port=6380, decode_responses=True)
        r.ping()
        logger.info("✅ Redis Cache connection successful")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        return False
    
    return True


def test_ml_model_server():
    """Test ML model server."""
    logger.info("Testing ML model server...")
    
    try:
        # Test health endpoint
        response = requests.get("http://localhost:8002/health", timeout=5)
        if response.status_code == 200:
            logger.info("✅ ML Model Server health check successful")
        else:
            logger.error(f"❌ ML Model Server health check failed: {response.status_code}")
            return False
        
        # Test status endpoint
        response = requests.get("http://localhost:8002/status", timeout=5)
        if response.status_code == 200:
            status = response.json()
            logger.info(f"✅ ML Model Server status: {status}")
        else:
            logger.error(f"❌ ML Model Server status check failed: {response.status_code}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ ML Model Server test failed: {e}")
        return False


def test_ml_prediction():
    """Test ML prediction functionality."""
    logger.info("Testing ML prediction...")
    
    try:
        # Create sample order book features
        sample_features = {
            "symbol": "BTC-USD",
            "bid_ask_imbalance": 1.2,
            "spread_percent": 0.05,
            "mid_price": 50000.0,
            "bid_volume": 1000.0,
            "ask_volume": 800.0,
            "order_book_depth": 50,
            "large_bid_wall": False,
            "large_ask_wall": True,
            "wall_size": 5000.0,
            "volume_weighted_price": 50010.0,
            "price_momentum": 0.5,
            "volatility": 2.0,
            "timestamp": int(datetime.now().timestamp())
        }
        
        # Make prediction request
        response = requests.post(
            "http://localhost:8002/predict",
            json=sample_features,
            timeout=10
        )
        
        if response.status_code == 200:
            prediction = response.json()
            logger.info(f"✅ ML prediction successful: {prediction}")
            return True
        else:
            logger.error(f"❌ ML prediction failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ ML prediction test failed: {e}")
        return False


def test_ml_training():
    """Test ML model training."""
    logger.info("Testing ML model training...")
    
    try:
        # Initialize ML optimizer
        ml_optimizer = MLTradingOptimizer(
            db_path="data/databases/trading_cache.db",
            models_dir="data/models",
            vector_db_host="localhost",
            vector_db_port=6333
        )
        
        # Collect training data
        logger.info("Collecting training data...")
        features, outcomes = ml_optimizer.collect_and_preprocess_data(days_back=7)
        
        if not features or not outcomes:
            logger.warning("No training data available, skipping training test")
            return True
        
        logger.info(f"Collected {len(features)} features and {len(outcomes)} outcomes")
        
        # Train models
        logger.info("Training ML models...")
        training_results = ml_optimizer.train_ml_models(features, outcomes, model_type='ensemble')
        
        if training_results:
            logger.info("✅ ML model training successful")
            logger.info(f"Training results: {training_results}")
            return True
        else:
            logger.error("❌ ML model training failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ ML training test failed: {e}")
        return False


def test_ml_enhanced_strategy():
    """Test ML-enhanced order book strategy."""
    logger.info("Testing ML-enhanced order book strategy...")
    
    try:
        from trade_bot.trading.strategies.ml_enhanced_orderbook import MLEnhancedOrderBookStrategy
        from trade_bot.core.config import TradingConfig
        
        # Create trading config
        config = TradingConfig()
        config.product_id = "BTC-USD"
        
        # Initialize strategy
        strategy = MLEnhancedOrderBookStrategy(
            config=config,
            ml_server_url="http://localhost:8002",
            fallback_to_baseline=True,
            confidence_threshold=0.6
        )
        
        # Test order book update
        bids = [[50000.0, 100.0], [49999.0, 200.0], [49998.0, 150.0]]
        asks = [[50001.0, 120.0], [50002.0, 180.0], [50003.0, 160.0]]
        
        strategy.update_order_book(bids, asks, datetime.now())
        
        # Test signal generation
        signal = strategy.generate_signal(50000.5, datetime.now())
        
        if signal:
            logger.info(f"✅ ML-enhanced strategy signal: {signal.action} - {signal.reason}")
        else:
            logger.info("✅ ML-enhanced strategy: No signal generated (hold)")
        
        # Get strategy info
        info = strategy.get_strategy_info()
        logger.info(f"Strategy info: {info}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ ML-enhanced strategy test failed: {e}")
        return False


def main():
    """Main test function."""
    logger.info("Starting ML Integration Tests")
    
    tests = [
        ("Vector Database Connection", test_vector_database_connection),
        ("ML Model Server", test_ml_model_server),
        ("ML Prediction", test_ml_prediction),
        ("ML Training", test_ml_training),
        ("ML-Enhanced Strategy", test_ml_enhanced_strategy)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"Running test: {test_name}")
        logger.info(f"{'='*50}")
        
        try:
            result = test_func()
            results[test_name] = result
            
            if result:
                logger.info(f"✅ {test_name} PASSED")
            else:
                logger.error(f"❌ {test_name} FAILED")
                
        except Exception as e:
            logger.error(f"❌ {test_name} FAILED with exception: {e}")
            results[test_name] = False
        
        time.sleep(1)  # Brief pause between tests
    
    # Summary
    logger.info(f"\n{'='*50}")
    logger.info("TEST SUMMARY")
    logger.info(f"{'='*50}")
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{test_name}: {status}")
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All ML integration tests passed!")
        return 0
    else:
        logger.error(f"⚠️ {total - passed} tests failed")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
