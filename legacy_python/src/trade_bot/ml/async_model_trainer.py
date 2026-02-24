"""Asynchronous Model Trainer for continuous ML model updates."""

import logging
import threading
import time
from typing import Dict, Any, Optional
import numpy as np

from trade_bot.ml.data_collector import MLDataCollector
from trade_bot.ml.model_trainer import ModelTrainer
from trade_bot.ml.model_manager import ModelManager
from trade_bot.ml.feature_engineer import FeatureEngineer

logger = logging.getLogger(__name__)


class AsyncModelTrainer:
    """Manages asynchronous, continuous model training."""

    def __init__(self, data_collector: MLDataCollector, model_trainer: ModelTrainer,
                 model_manager: ModelManager, training_interval: int = 3600,
                 new_data_threshold: int = 100, ml_optimizer: Any = None):
        """
        Initialize the asynchronous model trainer.

        Args:
            data_collector: Instance of MLDataCollector for fetching new data.
            model_trainer: Instance of ModelTrainer for training models.
            model_manager: Instance of ModelManager for registering and deploying models.
            training_interval: Time in seconds between training checks.
            new_data_threshold: Minimum number of new samples to trigger training.
            ml_optimizer: Optional MLTradingOptimizer instance. If provided, it handles the full training pipeline.
        """
        self.data_collector = data_collector
        self.model_trainer = model_trainer
        self.model_manager = model_manager
        self.training_interval = training_interval
        self.new_data_threshold = new_data_threshold
        self.ml_optimizer = ml_optimizer
        self.feature_engineer = FeatureEngineer()
        self.is_running = False
        self.thread = None
        self.last_training_time = None
        self.status = "idle"

    def start(self):
        """Start the asynchronous training loop."""
        if self.is_running:
            logger.warning("AsyncModelTrainer is already running.")
            return

        self.is_running = True
        self.thread = threading.Thread(target=self._training_loop, daemon=True)
        self.thread.start()
        logger.info("AsyncModelTrainer started.")

    def stop(self):
        """Stop the asynchronous training loop."""
        if not self.is_running:
            logger.warning("AsyncModelTrainer is not running.")
            return

        self.is_running = False
        if self.thread:
            self.thread.join()
        logger.info("AsyncModelTrainer stopped.")

    def _training_loop(self):
        """The main training loop that runs in a separate thread."""
        while self.is_running:
            try:
                self._check_and_retrain_model()
            except Exception as e:
                logger.error(f"Error in training loop: {e}", exc_info=True)
            
            # Wait for the next training interval
            time.sleep(self.training_interval)

    def _check_and_retrain_model(self):
        """Check for new data and retrain the model if the threshold is met."""
        logger.info("Checking for new data to retrain model...")
        self.status = "checking_data"

        # Preferred method: Use MLTradingOptimizer if available
        # This ensures consistent feature engineering and handling between training and inference
        if self.ml_optimizer:
            try:
                # Continuous batch training logic
                # If no model exists, we want to start collecting data and training
                if not self.ml_optimizer.is_trained:
                     logger.info("No model loaded. Attempting to train from scratch/bootstrap...")

                self.status = "training"
                # train_ml_models with batch_training=True handles data collection (via generator) and training
                result = self.ml_optimizer.train_ml_models(
                    batch_training=True,
                    batch_size=1000,
                    days_back=30
                )
                
                # Check if training actually processed any data
                if not result or result.get('batches_processed', 0) == 0:
                    logger.info("Training yielded no results (insufficient data). Waiting for more data...")
                    self.status = "waiting_for_data"
                else:
                    logger.info(f"Continuous training completed successfully. Batches: {result.get('batches_processed')}")
                    self.status = "idle"
                    self.last_training_time = time.time()
            except Exception as e:
                logger.error(f"Error in continuous training via optimizer: {e}")
                self.status = "error"
            return

        # Fallback method: Use local components (Updated to use FeatureEngineer)
        days_back = 30 
        signals = self.data_collector.extract_order_book_signals(days_back=days_back)
        
        if not signals:
            logger.info("No signals found for retraining.")
            self.status = "waiting_for_data"
            return

        logger.info(f"Found {len(signals)} signals in the last {days_back} days. Proceeding with retraining.")
        self.status = "training"

        trades = self.data_collector.extract_trade_outcomes(days_back=days_back)
        
        # Use FeatureEngineer to create feature matrix correctly
        features_list = [s for s in signals] # data_collector returns list of OrderBookFeatures
        # We need to match signals with trades. create_feature_vectors does this matching.
        # But wait, create_training_labels does matching.
        
        # Let's reproduce what MLTradingOptimizer does:
        # 1. create_feature_vectors(signals, trades) -> returns list of features (but matched to trades? No, creates vectors FROM signals that happened before trades)
        feature_vectors = self.data_collector.create_feature_vectors(signals, trades)
        
        # 2. create_training_labels -> matches vectors to trade outcomes
        training_data = self.data_collector.create_training_labels(feature_vectors, trades)

        if not training_data:
            logger.warning("No training examples could be created from the new data.")
            self.status = "waiting_for_data"
            return
            
        # Unpack features and outcomes
        features, outcomes = zip(*training_data)
        
        # 3. Use FeatureEngineer to process
        try:
            # Create feature matrix
            X, y, _ = self.feature_engineer.create_feature_matrix(list(features), list(outcomes))
            
            if X.shape[0] == 0:
                logger.warning("Feature matrix is empty after engineering.")
                self.status = "waiting_for_data"
                return

            # Preprocess (Scale, Impute, etc.)
            X_processed, y_processed = self.feature_engineer.preprocess_pipeline(X, y, fit_transform=True)
            
            # Train models
            training_results = self.model_trainer.train_models(X_processed, y_processed)

            # Register and deploy
            if training_results and training_results.get('best_model'):
                best_model_name = training_results['best_model']
                model_path = f"data/models/{best_model_name}_{time.strftime('%Y%m%d_%H%M%S')}.pkl"
                self.model_trainer.save_model(self.model_trainer.best_model, model_path)

                version_id = self.model_manager.register_model(
                    model_name=best_model_name,
                    model_path=model_path,
                    performance_metrics=training_results['model_performance'][best_model_name]
                )

                if version_id:
                    self.model_manager.deploy_model(best_model_name, version_id)
                    logger.info(f"Successfully trained and deployed new model {best_model_name}:{version_id}")
            
            self.last_training_time = time.time()
            self.status = "idle"
            
        except Exception as e:
            logger.error(f"Error in training loop: {e}")
            self.status = "error"
