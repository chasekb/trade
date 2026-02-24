
import logging
import sys
import os
import numpy as np
from datetime import datetime

# Add src to path
# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))


from trade_bot.ml.ml_optimizer import MLTradingOptimizer
from trade_bot.ml.data_collector import OrderBookFeatures, TradeOutcome
from trade_bot.ml.model_trainer import TradingModelWrapper

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_training():
    logger.info("Starting verification...")
    
    # Initialize optimizer
    optimizer = MLTradingOptimizer(db_url="sqlite:///data/databases/trading_cache.db")
    
    # Mock data collection to return dummy data if DB is empty
    # But let's try to use the real method first, maybe there is data
    features, outcomes = optimizer.collect_and_preprocess_data(days_back=90)
    
    if len(features) < 100:
        logger.warning("Not enough data in DB. Generating dummy data for verification.")
        # Generate dummy data
        features = []
        outcomes = []
        for i in range(200):
            features.append(OrderBookFeatures(
                timestamp=int(datetime.now().timestamp()) - i*60,
                symbol="BTC-USD",
                bid_ask_imbalance=np.random.random() - 0.5,
                spread_percent=0.01,
                mid_price=50000 + np.random.random()*1000,
                bid_volume=1.0,
                ask_volume=1.0,
                order_book_depth=10,
                large_bid_wall=False,
                large_ask_wall=False,
                wall_size=0.0,
                volume_weighted_price=50000.0,
                price_momentum=0.0,
                volatility=0.0
            ))
            outcomes.append(TradeOutcome(
                trade_id=f"trade_{i}",
                symbol="BTC-USD",
                side="buy",
                entry_price=50000.0,
                exit_price=50100.0 if i % 2 == 0 else 49900.0,
                quantity=0.1,
                pnl=10.0 if i % 2 == 0 else -10.0,
                fees=0.5,
                duration_seconds=60,
                signal_type="test",
                signal_strength=0.5,
                entry_timestamp=int(datetime.now().timestamp()) - i*60,
                exit_timestamp=int(datetime.now().timestamp()) - i*60 + 60,
                is_win=i % 2 == 0
            ))
            
    logger.info(f"Training with {len(features)} samples")
    
    # Train models
    results = optimizer.train_ml_models(features, outcomes)
    
    if not results:
        logger.error("Training failed")
        return
        
    logger.info("Training completed")
    logger.info(f"Best model: {results.get('best_model')}")
    logger.info(f"Best classifier: {results.get('best_classifier')}")
    
    # Verify the active model is a wrapper
    current_model = optimizer.model_manager.get_current_model()
    logger.info(f"Current model type: {type(current_model)}")
    
    if isinstance(current_model, TradingModelWrapper):
        logger.info("SUCCESS: Current model is a TradingModelWrapper")
        
        # Test prediction
        dummy_feature = features[0]
        prediction = optimizer.predict_trading_signal(dummy_feature)
        logger.info(f"Prediction: {prediction}")
        
        if 'win_probability' in prediction:
            logger.info(f"Win Probability: {prediction['win_probability']}%")
            if prediction['win_probability'] != 50.0 and prediction['win_probability'] != 81.76:
                 logger.info("SUCCESS: Win probability seems to be from classifier (not default/fallback)")
            else:
                 logger.warning("Win probability might be fallback (check logs)")
    else:
        logger.error("FAILURE: Current model is NOT a TradingModelWrapper")

if __name__ == "__main__":
    verify_training()
