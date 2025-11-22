from typing import List
"""ML Trading Optimization System - Main Integration."""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import os
import glob
import json

# Support both relative imports (when used as module) and absolute imports (when run standalone)
try:
    from .data_collector import MLDataCollector, OrderBookFeatures, TradeOutcome
    from .feature_engineer import FeatureEngineer
    from .model_trainer import ModelTrainer, TradingModelWrapper
    from .model_manager import ModelManager
    from .vector_db_client import VectorDBClient
except ImportError:
    # Fallback to absolute imports when running as standalone script
    from data_collector import MLDataCollector, OrderBookFeatures, TradeOutcome
    from feature_engineer import FeatureEngineer
    from model_trainer import ModelTrainer, TradingModelWrapper
    from model_manager import ModelManager
    from vector_db_client import VectorDBClient

logger = logging.getLogger(__name__)


class MLTradingOptimizer:
    """Main ML trading optimization system."""
    
    def __init__(self, db_url: str = None,
                 models_dir: str = "data/models",
                 transformers_dir: str = "data/transformers",
                 vector_db_host: str = "localhost",
                 vector_db_port: int = 6333):
        """
        Initialize ML trading optimizer.

        Args:
            db_url: PostgreSQL database URL
            models_dir: Directory for model storage
            transformers_dir: Directory for transformer storage
            vector_db_host: Vector database host
            vector_db_port: Vector database port
        """
        self.db_url = db_url
        self.models_dir = models_dir
        self.transformers_dir = transformers_dir

        # Initialize components
        self.data_collector = MLDataCollector(db_url)
        self.feature_engineer = FeatureEngineer()
        self.model_trainer = ModelTrainer()
        self.model_manager = ModelManager(models_dir)
        self.vector_db_client = VectorDBClient(vector_db_host, vector_db_port)
        
        # Training state
        self.last_training_time = None

        # Load transformers on initialization
        self.load_transformers()

    @property
    def is_trained(self) -> bool:
        """Check if a model is currently loaded in the model manager."""
        if self.model_manager.current_model is not None:
            return True
        
        # Also try to load the active model from config if not already loaded
        try:
            config_path = "data/ml_config.json"
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    active_model = config.get("active_model")
                    if active_model:
                        success = self.model_manager.set_active_model(active_model)
                        return success
        except Exception as e:
            logger.warning(f"Failed to auto-load active model: {e}")
            
        return False
        
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
        
        # Save the fitted transformers
        self.feature_engineer.save_transformers(self.transformers_dir)
        
        # Train models
        # Train models
        self.model_trainer.model_type = model_type
        training_results = self.model_trainer.train_models(X_processed, y_processed)
        
        # Train classifiers
        y_class = np.array([outcome.is_win for outcome in outcomes])
        classifier_results = self.model_trainer.train_classifiers(X_processed, y_class)
        
        training_results['classifier_performance'] = classifier_results['classifier_performance']
        training_results['best_classifier'] = classifier_results['best_classifier']
        training_results['best_classifier_score'] = classifier_results['best_score']
        
        # Store feature vectors in vector database
        self._store_feature_vectors_in_db(features, X_processed)
        
        # Register and deploy the best model
        # Register and deploy the best model
        if training_results and training_results.get('best_model') and training_results.get('best_score') is not None:
            best_model_name = max(training_results['model_performance'].keys(), 
                                key=lambda k: training_results['model_performance'][k]['score'])
            
            # Create wrapper with best regressor and best classifier
            best_regressor = self.model_trainer.models[best_model_name]
            best_classifier = None
            if training_results.get('best_classifier'):
                best_classifier = self.model_trainer.classifiers[training_results['best_classifier']]
                
            model_wrapper = TradingModelWrapper(best_regressor, best_classifier)
            
            # Save the wrapper model
            wrapper_filename = f"trading_optimizer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
            wrapper_path = os.path.join(self.models_dir, wrapper_filename)
            
            # Use model_trainer's save_model to save the wrapper (it handles directory creation)
            # We manually save it here to ensure it's the wrapper that gets saved
            import joblib
            joblib.dump(model_wrapper, wrapper_path)
            
            # Create metadata for the wrapper
            wrapper_metadata = {
                'model_type': 'combined_wrapper',
                'regressor': best_model_name,
                'classifier': training_results.get('best_classifier'),
                'regressor_score': training_results['best_score'],
                'classifier_score': training_results.get('best_classifier_score'),
                'timestamp': datetime.now().isoformat()
            }
            
            metadata_path = wrapper_path.replace('.pkl', '_metadata.json')
            with open(metadata_path, 'w') as f:
                json.dump(wrapper_metadata, f, indent=2)
                
            # Register the wrapper model
            version_id = self.model_manager.register_model(
                model_name="trading_optimizer",
                model_path=wrapper_path,
                performance_metrics={
                    'regressor': training_results['model_performance'][best_model_name],
                    'classifier': training_results.get('classifier_performance', {}).get(training_results.get('best_classifier'), {})
                },
                metadata=wrapper_metadata
            )
            
            if version_id:
                # Deploy the registered model
                if self.model_manager.deploy_model("trading_optimizer", version_id):
                    logger.info(f"Registered and deployed trading optimizer (Regressor: {best_model_name}, Classifier: {training_results.get('best_classifier')})")
                else:
                    logger.warning("Failed to deploy registered model")
            else:
                logger.warning("Failed to register best model")
        
        self.last_training_time = datetime.now()
        
        logger.info("ML model training completed")
        return training_results
    
    def predict_trading_signal(self, current_features: OrderBookFeatures) -> Dict[str, Any]:
        """Predict optimal trading signal using ML model."""
        if not self.is_trained:
            logger.warning("No trained model available")
            return {
                'action': 'hold',
                'confidence': 0.0,
                'signal_value': 0.0,
                'reason': 'No trained model',
                'similar_conditions': 0,
                'timestamp': datetime.now().isoformat()
            }
        
        try:
            # Extract features into a dictionary
            feature_dict = self.feature_engineer._extract_features(current_features)
            
            # Convert to DataFrame for consistent processing
            X = pd.DataFrame([feature_dict])

            # Fetch historical data for time-series features
            historical_data = self.vector_db_client.get_historical_patterns(current_features.symbol, days_back=1)
            
            historical_vectors = []
            if historical_data:
                # Sort by timestamp to ensure correct order
                sorted_data = sorted(historical_data, key=lambda p: p['payload']['timestamp'])
                historical_vectors = [p['vector'] for p in sorted_data]

            # Preprocess features using the same pipeline as training
            X_processed, _ = self.feature_engineer.preprocess_pipeline(
                X.values, y=None, fit_transform=False, historical_data=np.array(historical_vectors)
            )
            
            # Make prediction
            prediction = self.model_manager.predict(X_processed)
            
            if prediction is None:
                return {
                    'action': 'hold',
                    'confidence': 0.0,
                    'signal_value': 0.0,
                    'reason': 'Prediction failed',
                    'similar_conditions': 0,
                    'timestamp': datetime.now().isoformat()
                }
            
            # Convert prediction to trading signal
            signal_value = prediction[0]
            confidence = abs(signal_value)

            # Win probability represents the ML model's estimated probability of a successful trade
            # Get the probability from the model's classifier
            win_probability = 50.0
            
            # Log input features for debugging
            logger.info(f"Predicting for {current_features.symbol} with features: {feature_dict}")

            # Get the current model object (TradingModelWrapper) to access predict_proba
            current_model = self.model_manager.get_current_model()
            if current_model is not None and hasattr(current_model, 'predict_proba'):
                try:
                    # Get probability predictions from the classifier (probability of class 1 = win)
                    prob = current_model.predict_proba(X_processed)
                    if prob is not None and len(prob[0]) > 1:
                        raw_prob = float(prob[0][1] * 100)
                        # Clip probability to avoid unrealistic certainty
                        win_probability = max(5.0, min(95.0, raw_prob))
                        logger.info(f"Classifier raw probability: {raw_prob:.2f}%, clipped: {win_probability:.2f}%")
                except Exception as e:
                    logger.warning(f"Error getting win probability from classifier: {e}")
                    # Fallback: use regressor signal to estimate probability
                    try:
                        # Use a sigmoid function that doesn't saturate too quickly
                        # signal_value typically ranges -1 to 1. 
                        # A value of 0.5 should give high confidence but not 100%
                        win_probability = 100 / (1 + np.exp(-3 * signal_value))
                        logger.info(f"Fallback probability from signal {signal_value:.4f}: {win_probability:.2f}%")
                    except Exception:
                        win_probability = 50.0
            else:
                # Fallback: use regressor signal to estimate probability
                try:
                    win_probability = 100 / (1 + np.exp(-3 * signal_value))
                    logger.info(f"Fallback probability (no classifier) from signal {signal_value:.4f}: {win_probability:.2f}%")
                except Exception:
                    win_probability = 50.0

            if signal_value > 0.1:
                action = 'buy'
                # Calculate expected return as percentage based on signal strength
                expected_return_percentage = signal_value
            elif signal_value < -0.1:
                action = 'sell'
                # Calculate expected return as percentage based on signal strength
                expected_return_percentage = signal_value
            else:
                action = 'hold'
                expected_return_percentage = signal_value
                # For hold, win probability is neutral (around 50%) but slightly biased by signal
                try:
                    win_probability = 100 / (1 + np.exp(-1 * signal_value)) # Reduce sensitivity for hold
                except Exception:
                    win_probability = 50.0
            
            # Cap win probability at 99% to avoid unrealistic 100% values
            win_probability = min(win_probability, 99.0)
            
            logger.info(f"Final Prediction: Action={action}, Signal={signal_value:.4f}, WinProb={win_probability:.2f}%, ExpRet={expected_return_percentage:.4f}%")

            return {
                'action': action,
                'confidence': float(confidence),  # ML model confidence in signal (used for signal strength)
                'win_probability': float(win_probability),  # Probability of success (separate from confidence)
                'signal_value': float(signal_value),
                'expected_return_percentage': float(expected_return_percentage),
                'reason': f'ML prediction: {signal_value:.3f}',
                'similar_conditions': len(historical_vectors),  # Number of similar historical patterns found
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error predicting trading signal: {e}")
            return {
                'action': 'hold',
                'confidence': 0.0,
                'signal_value': 0.0,
                'reason': f'Error: {str(e)}',
                'similar_conditions': 0,
                'timestamp': datetime.now().isoformat()
            }
    
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

    def list_available_models(self) -> List[Dict[str, Any]]:
        """List all available models."""
        return self.model_manager.list_models()

    def set_active_model(self, model_name: str) -> bool:
        """Set the active model for predictions."""
        return self.model_manager.set_active_model(model_name)

    def get_prediction_comparison(self, features: OrderBookFeatures) -> Dict[str, Any]:
        """Get predictions from all models for comparison."""
        predictions = {}
        for model_info in self.model_manager.list_models():
            model_name = model_info['model_name']
            self.model_manager.set_active_model(model_name)
            prediction = self.predict_trading_signal(features)
            predictions[model_name] = prediction
        return predictions
    
    def get_top_pnl_trades(self, limit: int = 10, sort_by: str = 'pnl') -> Dict[str, List[Dict[str, Any]]]:
        """Get top and bottom trades by PnL."""
        return self.data_collector.get_trades_by_pnl(limit, sort_by)
        
    def _store_feature_vectors_in_db(self, features: List[OrderBookFeatures], 
                                    processed_features: np.ndarray) -> None:
        """Store feature vectors in vector database."""
        try:
            vectors = []
            metadata_list = []
            
            for i, feature in enumerate(features):
                if i < processed_features.shape[0]:
                    vector = processed_features[i]
                    # Extract all features for metadata storage
                    feature_dict = self.feature_engineer._extract_features(feature)
                    
                    # Convert all values to native Python types for JSON serialization
                    serializable_features = {k: v.item() if isinstance(v, np.generic) else v for k, v in feature_dict.items()}
                    
                    metadata = {
                        'symbol': feature.symbol,
                        'timestamp': feature.timestamp,
                        **serializable_features
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
            # A sample feature vector is created to determine the correct vector size
            sample_features, _ = self.collect_and_preprocess_data(days_back=1)
            if not sample_features:
                # Fallback to a default size if no data is available
                vector_size = 20
            else:
                # Create dummy outcomes with default values
                dummy_outcomes = [
                    TradeOutcome(
                        trade_id="", symbol="", side="", entry_price=0.0, exit_price=0.0,
                        quantity=0.0, pnl=0.0, fees=0.0, duration_seconds=0,
                        signal_type="", signal_strength=0.0, entry_timestamp=0, exit_timestamp=0
                    )
                ] * len(sample_features)
                X, _, _ = self.feature_engineer.create_feature_matrix(sample_features, dummy_outcomes)
                X_processed, _ = self.feature_engineer.preprocess_pipeline(X, y=np.zeros(len(X)), fit_transform=True)
                vector_size = X_processed.shape[1]

            if self.vector_db_client.check_collection_exists():
                info = self.vector_db_client.get_collection_info()
                if info['result']['config']['params']['vectors']['size'] != vector_size:
                    logger.warning(f"Vector DB dimension mismatch. Deleting and recreating collection.")
                    self.vector_db_client.delete_collection()
                    return self.vector_db_client.create_collection(vector_size)
            else:
                return self.vector_db_client.create_collection(vector_size)
            
            return True
            
        except Exception as e:
            logger.error(f"Error initializing vector database: {e}")
            return False
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status."""
        current_model = self.model_manager.get_current_model()

        # Skip vector DB status calls that might hang - just check if collection exists
        vector_db_status = {"exists": self.vector_db_client.check_collection_exists()}

        return {
            'is_trained': self.is_trained,
            'last_training_time': self.last_training_time.isoformat() if self.last_training_time else None,
            'current_model': {
                'model_name': current_model.get('model_name'),
                'version_id': current_model.get('version_id'),
                'deployed_at': current_model.get('deployed_at'),
            } if current_model else None,
            'model_performance': self.get_model_performance(),
            'vector_db_status': vector_db_status,
            'vector_db_stats': None  # Skip stats to avoid hanging
        }

    def load_transformers(self) -> None:
        """Load transformers from disk."""
        try:
            self.feature_engineer.load_transformers(self.transformers_dir)
            if self.feature_engineer.scaler and self.feature_engineer.feature_selector:
                logger.info("Transformers loaded, ML Optimizer is ready for predictions.")
        except Exception as e:
            logger.error(f"Error loading transformers: {e}")
