#!/usr/bin/env python3
"""ML Model Training Script for Trading Optimization."""

import logging
import sys
import os
import argparse
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trade_bot.ml.ml_optimizer import MLTradingOptimizer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'outputs/ml_training_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def main():
    """Main training function."""
    parser = argparse.ArgumentParser(description='Train ML models for trading optimization')
    parser.add_argument('--days-back', type=int, default=30, 
                       help='Number of days of historical data to use for training')
    parser.add_argument('--model-type', type=str, default='ensemble',
                       choices=['ensemble', 'rf', 'gb', 'nn', 'linear'],
                       help='Type of ML model to train')
    parser.add_argument('--db-path', type=str, default='data/databases/trading_cache.db',
                       help='Path to trading database')
    parser.add_argument('--models-dir', type=str, default='data/models',
                       help='Directory to store trained models')
    parser.add_argument('--vector-db-host', type=str, default='localhost',
                       help='Vector database host')
    parser.add_argument('--vector-db-port', type=int, default=6333,
                       help='Vector database port')
    parser.add_argument('--min-samples', type=int, default=100,
                       help='Minimum number of training samples required')
    
    args = parser.parse_args()
    
    logger.info("Starting ML model training")
    logger.info(f"Configuration: {vars(args)}")
    
    try:
        # Initialize ML optimizer
        ml_optimizer = MLTradingOptimizer(
            db_path=args.db_path,
            models_dir=args.models_dir,
            vector_db_host=args.vector_db_host,
            vector_db_port=args.vector_db_port
        )
        
        # Initialize vector database
        logger.info("Initializing vector database")
        if not ml_optimizer.initialize_vector_database():
            logger.warning("Failed to initialize vector database, continuing without it")
        
        # Collect and preprocess data
        logger.info(f"Collecting data from last {args.days_back} days")
        features, outcomes = ml_optimizer.collect_and_preprocess_data(args.days_back)
        
        if not features:
            logger.error("No features collected from database")
            return 1
        
        if not outcomes:
            logger.error("No trade outcomes collected from database")
            return 1
        
        logger.info(f"Collected {len(features)} features and {len(outcomes)} outcomes")
        
        # Check minimum samples requirement
        if len(features) < args.min_samples:
            logger.error(f"Insufficient training data: {len(features)} < {args.min_samples}")
            return 1
        
        # Train ML models
        logger.info(f"Training {args.model_type} models")
        training_results = ml_optimizer.train_ml_models(features, outcomes, args.model_type)
        
        if not training_results:
            logger.error("Model training failed")
            return 1
        
        # Log training results
        logger.info("Training completed successfully")
        logger.info(f"Model performance: {training_results.get('model_performance', {})}")
        logger.info(f"Best model score: {training_results.get('best_score', 'N/A')}")
        
        # Get system status
        status = ml_optimizer.get_system_status()
        logger.info(f"System status: {status}")
        
        # Get feature importance
        importance = ml_optimizer.get_feature_importance()
        if importance:
            logger.info("Top 10 most important features:")
            sorted_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)
            for i, (feature, score) in enumerate(sorted_features[:10]):
                logger.info(f"  {i+1}. {feature}: {score:.4f}")
        
        logger.info("ML model training completed successfully")
        return 0
        
    except Exception as e:
        logger.error(f"Error during training: {e}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
