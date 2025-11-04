from typing import List
"""ML Trading Optimization System - Main Integration."""

import logging
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import os

from .data_collector import MLDataCollector, OrderBookFeatures, TradeOutcome
from .feature_engineer import FeatureEngineer
from .model_trainer import ModelTrainer
from .model_manager import ModelManager
from .vector_db_client import VectorDBClient

logger = logging.getLogger(__name__)


class MLTradingOptimizer:
    """Main ML trading optimization system."""
    
    def __init__(self, db_path: str = "data/databases/trading_cache.db",
                 models_dir: str = "data/models",
                 vector_db_host: str = "localhost",
                 vector_db_port: int = 6333):
        """
        Initialize ML trading optimizer.
        
        Args:
            db_path: Path to trading database
            models_dir: Directory for model storage
            vector_db_host: Vector database host
            vector_db_port: Vector database port
        """
        self.db_path = db_path
        self.models_dir = models_dir
        
        # Initialize components
        self.data_collector = MLDataCollector(db_path)
        self.feature_engineer = FeatureEngineer()
        self.model_trainer = ModelTrainer()
        self.model_manager = ModelManager(models_dir)
        self.vector_db_client = VectorDBClient(vector_db_host, vector_db_port)
        
        # Training state
        self.is_trained = False
        self.last_training_time = None
        
    def collect_and_preprocess_data(self, days_back: int = 30) -> Tuple[List[OrderBookFeatures], List[TradeOutcome]]:
        """Collect and preprocess trading data for ML training."""
        logger.info(f"Collecting data from last {days_back} days")
        
        # Extract raw data
        signals = self.data_collector.extract_order_book_signals(days_back)
        trades = self.data_collector.extract_trade_outcomes(days_back)
        
        if not signals:
            logger.warning("No signals found for training")
            return [], []
        
        if not trades:
            logger.warning("No trades found for training")
            return [], []
        
        # Create feature vectors
        feature_vectors = self.data_collector.create_feature_vectors(signals, trades)
        
        if not feature_vectors:
            logger.warning("No feature vectors created")
            return [], []
        
        # Create training labels
        training_data = self.data_collector.create_training_labels(feature_vectors, trades)
        
        if not training_data:
            logger.warning("No training data created")
            return [], []
        
        # Separate features and outcomes
        features, outcomes = zip(*training_data)
        
        logger.info(f"Collected {len(features)} feature vectors and {len(outcomes)} trade outcomes")
        return list(features), list(outcomes)
    
    def train_ml_models(self, features: List[OrderBookFeatures], 
                        outcomes: List[TradeOutcome],
                        model_type: str = 'ensemble') -> Dict[str, Any]:
        """Train ML models on the collected data."""
        logger.info("Starting ML model training")
        
        # Create feature matrix
        X, y, feature_names = self.feature_engineer.create_feature_matrix(features, outcomes)
        
        if X.shape[0] == 0:
            logger.error("No valid training data")
            return {}
        
        # Preprocess features
        X_processed, y_processed = self.feature_engineer.preprocess_pipeline(X, y, fit_transform=True)
        
        # Train models
        self.model_trainer.model_type = model_type
        training_results = self.model_trainer.train_models(X_processed, y_processed)
        
        # Store feature vectors in vector database
        self._store_feature_vectors_in_db(features, X_processed)
        
        # Register the best model
        if self.model_trainer.best_model is not None:
            model_path = os.path.join(self.models_dir, f"best_model_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl")
            if self.model_trainer.save_model(model_path):
                version_id = self.model_manager.register_model(
                    model_name="trading_optimizer",
                    model_path=model_path,
                    performance_metrics=training_results['model_performance'].get('best_model', {}),
                    metadata={
                        'feature_names': feature_names,
                        'training_samples': X_processed.shape[0],
                        'feature_count': X_processed.shape[1],
                        'model_type': model_type
                    }
                )
                
                if version_id:
                    # Deploy the new model
                    self.model_manager.deploy_model("trading_optimizer", version_id)
                    self.is_trained = True
                    self.last_training_time = datetime.now()
        
        logger.info("ML model training completed")
        return training_results
    
    def predict_trading_signal(self, current_features: OrderBookFeatures) -> Dict[str, Any]:
        """Predict optimal trading signal using ML model."""
        if not self.is_trained:
            logger.warning("No trained model available")
            return {'action': 'hold', 'confidence': 0.0, 'reason': 'No trained model'}
        
        try:
            # Extract features
            feature_vector = self.feature_engineer._extract_features(current_features)
            X = np.array([feature_vector])
            
            # Preprocess features (using fitted scaler and selector)
            X_scaled = self.feature_engineer.transform_features(X)
            X_selected = self.feature_engineer.transform_features_selected(X_scaled)
            X_ts = self.feature_engineer.create_time_series_features(X_selected)
            X_final = self.feature_engineer.create_interaction_features(X_ts)
            
            # Make prediction
            prediction = self.model_manager.predict(X_final)
            
            if prediction is None:
                return {'action': 'hold', 'confidence': 0.0, 'reason': 'Prediction failed'}
            
            # Convert prediction to trading signal
            signal_value = prediction[0]
            confidence = abs(signal_value)
            
            if signal_value > 0.1:
                action = 'buy'
            elif signal_value < -0.1:
                action = 'sell'
            else:
                action = 'hold'
            
            # Find similar market conditions
            similar_conditions = self.vector_db_client.find_similar_market_conditions(
                X_final[0], current_features.symbol, limit=3
            )
            
            return {
                'action': action,
                'confidence': float(confidence),
                'signal_value': float(signal_value),
                'reason': f'ML prediction: {signal_value:.3f}',
                'similar_conditions': len(similar_conditions),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error predicting trading signal: {e}")
            return {'action': 'hold', 'confidence': 0.0, 'reason': f'Error: {str(e)}'}
    
    def update_model_with_new_data(self, new_features: List[OrderBookFeatures],
                                  new_outcomes: List[TradeOutcome]) -> bool:
        """Update the model with new trading data (streaming learning)."""
        try:
            if not new_features or not new_outcomes:
                logger.warning("No new data provided for model update")
                return False
            
            logger.info(f"Updating model with {len(new_features)} new samples")
            
            # Create feature matrix for new data
            X_new, y_new, _ = self.feature_engineer.create_feature_matrix(new_features, new_outcomes)
            
            if X_new.shape[0] == 0:
                logger.warning("No valid new data for model update")
                return False
            
            # Preprocess new features (using existing scaler and selector)
            X_new_processed = self.feature_engineer.transform_features(X_new)
            X_new_selected = self.feature_engineer.transform_features_selected(X_new_processed)
            X_new_ts = self.feature_engineer.create_time_series_features(X_new_selected)
            X_new_final = self.feature_engineer.create_interaction_features(X_new_ts)
            
            # Store new feature vectors
            self._store_feature_vectors_in_db(new_features, X_new_final)
            
            # For now, we'll retrain the model with all data
            # In a production system, you might implement incremental learning
            logger.info("Retraining model with updated dataset")
            
            # Collect all historical data
            all_features, all_outcomes = self.collect_and_preprocess_data(days_back=90)
            
            if all_features and all_outcomes:
                # Retrain the model
                training_results = self.train_ml_models(all_features, all_outcomes)
                
                if training_results:
                    logger.info("Model updated successfully")
                    return True
            
            logger.warning("Failed to update model")
            return False
            
        except Exception as e:
            logger.error(f"Error updating model: {e}")
            return False
    
    def get_model_performance(self) -> Dict[str, Any]:
        """Get current model performance metrics."""
        return self.model_manager.get_model_performance("trading_optimizer")
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance from the current model."""
        return self.feature_engineer.get_feature_importance()
    
    def rollback_model(self) -> bool:
        """Rollback to the previous model version."""
        return self.model_manager.rollback_model("trading_optimizer")
    
    def _store_feature_vectors_in_db(self, features: List[OrderBookFeatures], 
                                    processed_features: np.ndarray) -> None:
        """Store feature vectors in vector database."""
        try:
            vectors = []
            metadata_list = []
            
            for i, feature in enumerate(features):
                if i < processed_features.shape[0]:
                    vector = processed_features[i]
                    metadata = {
                        'symbol': feature.symbol,
                        'timestamp': feature.timestamp,
                        'bid_ask_imbalance': feature.bid_ask_imbalance,
                        'spread_percent': feature.spread_percent,
                        'mid_price': feature.mid_price,
                        'volatility': feature.volatility,
                        'price_momentum': feature.price_momentum
                    }
                    
                    vectors.append(vector)
                    metadata_list.append(metadata)
            
            if vectors:
                self.vector_db_client.upsert_vectors(vectors, metadata_list)
                logger.info(f"Stored {len(vectors)} feature vectors in vector database")
                
        except Exception as e:
            logger.error(f"Error storing feature vectors: {e}")
    
    def initialize_vector_database(self) -> bool:
        """Initialize vector database for feature storage."""
        try:
            # Create collection if it doesn't exist
            if not self.vector_db_client.check_collection_exists():
                return self.vector_db_client.create_collection(vector_size=128)
            
            return True
            
        except Exception as e:
            logger.error(f"Error initializing vector database: {e}")
            return False
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status."""
        return {
            'is_trained': self.is_trained,
            'last_training_time': self.last_training_time.isoformat() if self.last_training_time else None,
            'current_model': self.model_manager.get_current_model(),
            'model_performance': self.get_model_performance(),
            'vector_db_status': self.vector_db_client.get_collection_info(),
            'vector_db_stats': self.vector_db_client.get_collection_stats()
        }
