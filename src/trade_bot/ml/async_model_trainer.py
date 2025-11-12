"""Asynchronous Model Trainer for continuous ML model updates."""

import logging
import threading
import time
from typing import Dict, Any, Optional

from trade_bot.ml.data_collector import MLDataCollector
from trade_bot.ml.model_trainer import ModelTrainer
from trade_bot.ml.model_manager import ModelManager

logger = logging.getLogger(__name__)


class AsyncModelTrainer:
    """Manages asynchronous, continuous model training."""

    def __init__(self, data_collector: MLDataCollector, model_trainer: ModelTrainer,
                 model_manager: ModelManager, training_interval: int = 3600,
                 new_data_threshold: int = 100):
        """
        Initialize the asynchronous model trainer.

        Args:
            data_collector: Instance of MLDataCollector for fetching new data.
            model_trainer: Instance of ModelTrainer for training models.
            model_manager: Instance of ModelManager for registering and deploying models.
            training_interval: Time in seconds between training checks.
            new_data_threshold: Minimum number of new samples to trigger training.
        """
        self.data_collector = data_collector
        self.model_trainer = model_trainer
        self.model_manager = model_manager
        self.training_interval = training_interval
        self.new_data_threshold = new_data_threshold
        self.is_running = False
        self.thread = None
        self.last_training_time = None

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

        # Fetch a rolling window of data for retraining (e.g., last 30 days)
        days_back = 30 
        signals = self.data_collector.extract_order_book_signals(days_back=days_back)
        
        if not signals:
            logger.info("No signals found for retraining.")
            return

        logger.info(f"Found {len(signals)} signals in the last {days_back} days. Proceeding with retraining.")

        # Create feature vectors and labels
        trades = self.data_collector.extract_trade_outcomes(days_back=days_back)
        training_data = self.data_collector.create_training_labels(
            self.data_collector.create_feature_vectors(signals, trades),
            trades
        )

        if not training_data:
            logger.warning("No training examples could be created from the new data.")
            return

        # Prepare data for training
        X_list = [list(d[0].__dict__.values())[2:] for d in training_data] # Exclude timestamp and symbol
        y_list = [d[1].pnl for d in training_data]
        
        if not X_list or not y_list:
            logger.warning("Feature vectors or labels are empty. Skipping training.")
            return

        X = np.array(X_list)
        y = np.array(y_list)

        # Train the model
        training_results = self.model_trainer.train_models(X, y)

        # Register and deploy the new model
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
