
import logging
import sys
import os

# Add src to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from trade_bot.ml.ml_optimizer import MLTradingOptimizer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def main():
    logger.info("Starting debug training...")
    
    # Initialize optimizer
    # Ensure we point to the correct database if needed, but defaults might work
    optimizer = MLTradingOptimizer()
    
    # Run batch training
    logger.info("Triggering batch training...")
    results = optimizer.train_ml_models(batch_training=True, batch_size=1000, days_back=30)
    
    logger.info(f"Training completed. Results: {results}")

if __name__ == "__main__":
    main()
