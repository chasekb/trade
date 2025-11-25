"""Training Manager for orchestrating ML model training."""

import logging
import json
import os
from trade_bot.ml.data_collector import MLDataCollector
from trade_bot.ml.model_trainer import ModelTrainer
from trade_bot.ml.model_manager import ModelManager
from trade_bot.ml.async_model_trainer import AsyncModelTrainer

logger = logging.getLogger(__name__)


class TrainingManager:
    """Orchestrates the continuous training of ML models."""

    def __init__(self, db_path: str, models_dir: str, config_path: str = "data/ml_config.json"):
        """
        Initialize the TrainingManager.

        Args:
            db_path: Path to the database.
            models_dir: Directory to store models.
            config_path: Path to the ML configuration file.
        """
        self.config_path = config_path
        self.config = self._load_config()
        
        self.data_collector = MLDataCollector(db_path=db_path)
        self.model_trainer = ModelTrainer(model_type='ensemble')
        self.model_manager = ModelManager(models_dir=models_dir)
        self.async_trainer = AsyncModelTrainer(
            data_collector=self.data_collector,
            model_trainer=self.model_trainer,
            model_manager=self.model_manager,
            training_interval=self.config.get("training_interval", 3600),
            new_data_threshold=self.config.get("new_data_threshold", 100)
        )

    def _load_config(self) -> dict:
        """Load the ML configuration from a JSON file."""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return {
            "continuous_training_enabled": True,
            "training_interval": 3600,
            "new_data_threshold": 100,
            "batch_training_enabled": True,
            "batch_size": 1000
        }


    def _save_config(self):
        """Save the current configuration to the JSON file."""
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)

    def update_config(self, new_config: dict):
        """Update and save the ML configuration."""
        self.config.update(new_config)
        self._save_config()
        self.reload_config()

    def reload_config(self):
        """Reload the configuration and apply changes."""
        self.config = self._load_config()
        self.async_trainer.training_interval = self.config.get("training_interval", 3600)
        self.async_trainer.new_data_threshold = self.config.get("new_data_threshold", 100)
        
        if self.config.get("continuous_training_enabled"):
            if not self.async_trainer.is_running:
                self.start_continuous_training()
        else:
            if self.async_trainer.is_running:
                self.stop_continuous_training()

    def start_continuous_training(self):
        """Start the continuous training process if enabled in config."""
        if self.config.get("continuous_training_enabled"):
            logger.info("Starting continuous model training.")
            self.async_trainer.start()
        else:
            logger.info("Continuous model training is disabled in the configuration.")

    def stop_continuous_training(self):
        """Stop the continuous training process."""
        logger.info("Stopping continuous model training.")
        self.async_trainer.stop()

    def get_training_status(self) -> dict:
        """Get the status of the training manager."""
        return {
            "is_running": self.async_trainer.is_running,
            "last_training_time": self.async_trainer.last_training_time
        }
