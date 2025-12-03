"""ML Trading Optimization System - Main Integration."""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import os
import glob
import json
import asyncio
import concurrent.futures

logger = logging.getLogger(__name__)

# Support both relative imports (when used as module) and absolute imports (when run standalone)
try:
    from .data_collector import MLDataCollector, OrderBookFeatures, TradeOutcome
    from .feature_engineer import FeatureEngineer
    from .model_trainer import ModelTrainer
    from .wrapper import TradingModelWrapper
    from .model_manager import ModelManager
    from .vector_db_client import VectorDBClient
    try:
        from trade_bot.data.data_provider import CoinbaseDataProvider
    except ImportError:
        from ..data.data_provider import CoinbaseDataProvider
except ImportError as e:
    logger.warning(f"ImportError in MLTradingOptimizer: {e}")
    # Fallback to absolute imports when running as standalone script
    try:
        from data_collector import MLDataCollector, OrderBookFeatures, TradeOutcome
        from feature_engineer import FeatureEngineer
        from model_trainer import ModelTrainer
        from wrapper import TradingModelWrapper
        from model_manager import ModelManager
        from vector_db_client import VectorDBClient
    except ImportError:
        pass
    # Mock/Placeholder for standalone run if data provider not available
    CoinbaseDataProvider = None


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
    
    def train_ml_models(self, features: List[OrderBookFeatures] = None, 
                        outcomes: List[TradeOutcome] = None,
                        model_type: str = 'ensemble',
                        batch_training: bool = False,
                        batch_size: int = 1000,
                        days_back: int = 30) -> Dict[str, Any]:
        """Train ML models on the collected data."""
        logger.info(f"Starting ML model training (Batching: {batch_training})")

        if batch_training:
            return self._train_batch_models(model_type, batch_size, days_back)

        if features is None or outcomes is None:
            # If not provided and not batch training, collect all data
            features, outcomes = self.collect_and_preprocess_data(days_back)

        # Create feature matrix
        X, y, feature_names = self.feature_engineer.create_feature_matrix(features, outcomes)

        if X.shape[0] == 0:
            logger.error("No valid training data")
            return {}

        # Preprocess features - create new transformers for this training session
        # Clear existing transformers to ensure fresh fitting for this model
        self.feature_engineer = FeatureEngineer()  # Create fresh feature engineer
        X_processed, y_processed = self.feature_engineer.preprocess_pipeline(X, y, fit_transform=True)

        # Save the fitted transformers with model-specific naming
        model_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        model_transformers_dir = os.path.join(self.transformers_dir, f"transformers_{model_timestamp}")
        self.feature_engineer.save_transformers(model_transformers_dir)
        
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
            
            # Ensure models directory exists
            os.makedirs(self.models_dir, exist_ok=True)
            
            # Save the model with comprehensive error handling
            import joblib
            model_saved_successfully = False
            
            try:
                joblib.dump(model_wrapper, wrapper_path)
                
                # Verify the file was created and has content
                if os.path.exists(wrapper_path) and os.path.getsize(wrapper_path) > 0:
                    model_saved_successfully = True
                    logger.info(f"Model saved successfully to {wrapper_path} ({os.path.getsize(wrapper_path)} bytes)")
                else:
                    logger.error(f"Model file was not created or is empty: {wrapper_path}")
                    
            except Exception as e:
                logger.error(f"Error saving model to {wrapper_path}: {e}")
                # Clean up partial file if it exists
                if os.path.exists(wrapper_path):
                    try:
                        os.remove(wrapper_path)
                        logger.info(f"Cleaned up partial model file: {wrapper_path}")
                    except Exception as cleanup_error:
                        logger.warning(f"Failed to clean up partial model file: {cleanup_error}")
            
            # Only create metadata if model was saved successfully
            if model_saved_successfully:
                try:
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
                    
                    # Verify metadata was written
                    if os.path.exists(metadata_path) and os.path.getsize(metadata_path) > 0:
                        logger.info(f"Metadata saved successfully to {metadata_path}")
                    else:
                        logger.warning(f"Metadata file was not created or is empty: {metadata_path}")
                        
                except Exception as e:
                    logger.error(f"Error saving metadata to {metadata_path}: {e}")
                    # Don't fail the entire training if just metadata fails
            else:
                logger.error("Skipping metadata creation because model save failed")
                
            # Only register the model if it was saved successfully
            if model_saved_successfully:
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
            else:
                logger.error("Skipping model registration because model save failed")
        
        self.last_training_time = datetime.now()
        
        logger.info("ML model training completed")
        return training_results

    def _train_batch_models(self, model_type: str, batch_size: int, days_back: int) -> Dict[str, Any]:
        """Train models using batch processing."""
        # Reset feature engineer for new training to avoid scaler dimension mismatches
        # This ensures we start with a fresh scaler that adapts to the current feature set dimensions
        self.feature_engineer = FeatureEngineer()

        # Create generator that yields processed batches
        data_generator = self._create_batch_generator(batch_size, days_back)
        
        # Train incrementally
        # For batch training, we typically use SGD or Neural Networks
        if model_type not in ['sgd', 'nn']:
            logger.warning(f"Model type {model_type} not optimal for batch training. Switching to 'sgd'.")
            model_type = 'sgd'
            
        training_results = self.model_trainer.train_incremental(
            data_generator, 
            model_type=model_type,
            feature_engineer=self.feature_engineer
        )
        
        # Save transformers after training (they are updated incrementally)
        self.feature_engineer.save_transformers(self.transformers_dir)
        
        # Register and deploy (similar logic to standard training)
        if training_results and training_results.get('best_model'):
            best_model_name = training_results['best_model']
            
            # Create wrapper
            best_regressor = self.model_trainer.models[best_model_name]
            best_classifier = self.model_trainer.classifiers.get(training_results.get('best_classifier'))
            
            model_wrapper = TradingModelWrapper(best_regressor, best_classifier)
            
            # Save wrapper
            wrapper_filename = f"trading_optimizer_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
            wrapper_path = os.path.join(self.models_dir, wrapper_filename)
            os.makedirs(self.models_dir, exist_ok=True)
            
            import joblib
            joblib.dump(model_wrapper, wrapper_path)
            
            # Register
            version_id = self.model_manager.register_model(
                model_name="trading_optimizer",
                model_path=wrapper_path,
                performance_metrics=training_results,
                metadata={'training_mode': 'batch', 'batch_size': batch_size}
            )
            
            if version_id:
                self.model_manager.deploy_model("trading_optimizer", version_id)
        
        self.last_training_time = datetime.now()
        return training_results

    def _create_batch_generator(self, batch_size: int, days_back: int):
        """Create a generator that yields (X_processed, outcomes, targets) batches."""
        raw_batch_generator = self.data_collector.yield_training_batches(batch_size, days_back)
        
        previous_window = None
        first_batch = True
        
        for features, outcomes in raw_batch_generator:
            # Create feature matrix
            X, y, _ = self.feature_engineer.create_feature_matrix(features, outcomes)
            
            if X.shape[0] == 0:
                continue
                
            # Preprocess incrementally
            # We fit on the first batch, then just transform (or partial fit if implemented fully)
            # In our FeatureEngineer.preprocess_pipeline_incremental, 'fit' argument controls partial_fit
            # We should probably fit on every batch for scaler/imputer to adapt, 
            # but usually we want to fit on a representative sample or adapt slowly.
            # Let's fit on every batch for now as our partial_fit implementation handles it safely.
            X_processed, _, next_window = self.feature_engineer.preprocess_pipeline_incremental(
                X, y, fit=True, previous_window=previous_window
            )
            
            previous_window = next_window
            
            # Store vectors in DB (optional, might be slow for large datasets)
            # self._store_feature_vectors_in_db(features, X_processed)
            
            # Yield X_processed, outcomes (for classifier), and y (processed targets for regressor)
            yield X_processed, outcomes, y

    
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
            # Use raw historical data from Coinbase API to calculate correct rolling stats
            # This ensures we don't mix processed vectors (from vector DB) with raw vectors (current)
            historical_vectors = self._get_historical_feature_vectors(current_features.symbol, current_features)
            
            # Preprocess features using the same pipeline as training
            # Pass historical vectors (raw/scaled) so create_time_series_features can calculate rolling stats correctly
            X_processed, _ = self.feature_engineer.preprocess_pipeline(
                X.values, y=None, fit_transform=False, historical_data=historical_vectors
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
                        win_probability = raw_prob
                        logger.info(f"Classifier raw probability: {raw_prob:.2f}%")
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
            
            # No clipping as requested - trust the model output based on stabilized inputs
            
            logger.info(f"Final Prediction: Action={action}, Signal={signal_value:.4f}, WinProb={win_probability:.2f}%, ExpRet={expected_return_percentage:.4f}%")

            # Calculate number of historical points used
            num_history = len(historical_vectors) if historical_vectors is not None else 0

            return {
                'action': action,
                'confidence': float(win_probability / 100.0),  # Use win probability as confidence (0-1 range)
                'win_probability': float(win_probability),  # Probability of success (separate from confidence)
                'signal_value': float(signal_value),
                'expected_return_percentage': float(expected_return_percentage),
                'reason': f'ML prediction: {signal_value:.3f}',
                'similar_conditions': num_history,  # Number of similar historical patterns found
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
            
            # Ensure transformers are loaded
            self.load_transformers()

            # Preprocess new features (correct order: Impute -> TS -> Interactions -> Scale -> Select)
            
            # 1. Impute
            if self.feature_engineer.imputer:
                X_new_imputed = self.feature_engineer.imputer.transform(X_new)
            else:
                X_new_imputed = X_new
                
            # 2. Time Series
            # Note: We ideally need historical data for accurate rolling stats, 
            # but for storage we'll calculate based on the batch
            X_new_ts = self.feature_engineer.create_time_series_features(X_new_imputed)
            
            # 3. Interactions
            X_new_interactions = self.feature_engineer.create_interaction_features(X_new_ts)
            
            # 4. Scale
            if self.feature_engineer.scaler:
                X_new_scaled = self.feature_engineer.transform_features(X_new_interactions)
            else:
                X_new_scaled = X_new_interactions
                
            # 5. Select
            X_new_final = self.feature_engineer.transform_features_selected(X_new_scaled)
            
            # Save transformers
            self.feature_engineer.save_transformers(self.transformers_dir)
            
            # Store new feature vectors
            self._store_feature_vectors_in_db(new_features, X_new_final)
            
            # Use batch training for continuous updates to handle large datasets efficiently
            logger.info("Retraining model with updated dataset using batch training")
            
            # Use batch training (days_back=90 or configurable)
            # This will pick up the new data from the database
            training_results = self.train_ml_models(
                batch_training=True,
                batch_size=1000,
                days_back=90
            )
            
            if training_results:
                logger.info("Model updated successfully via batch training")
                return True
            
            logger.warning("Failed to update model")
            return False
            
        except Exception as e:
            logger.error(f"Error updating model: {e}")
            return False
    
    def get_model_performance(self) -> Dict[str, Any]:
        """Get current model performance metrics."""
        return self.model_manager.get_model_performance("trading_optimizer")
    
    def _get_historical_feature_vectors(self, symbol: str, current_features: Optional[OrderBookFeatures] = None) -> Optional[np.ndarray]:
        """Fetch raw historical data from Coinbase and convert to feature vectors."""
        try:
            if CoinbaseDataProvider is None:
                logger.warning("CoinbaseDataProvider not available")
                return None

            # Helper to run async method synchronously
            async def fetch_history():
                provider = CoinbaseDataProvider(symbol)
                # Fetch recent trades to reconstruct price history
                trades = await provider.get_recent_trades(limit=50)
                await provider.close() if hasattr(provider, 'close') else None
                return trades

            # Run in a separate thread to avoid "loop is running" errors
            # and to allow using asyncio.run() which creates a new loop
            try:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    trades = executor.submit(asyncio.run, fetch_history()).result()
            except Exception as e:
                logger.warning(f"Failed to run async fetch in thread: {e}")
                # Fallback to direct run if threading fails (unlikely) or if asyncio.run fails
                try:
                    trades = asyncio.run(fetch_history())
                except Exception as e2:
                    logger.warning(f"Direct asyncio run also failed: {e2}")
                    return None
            
            if not trades:
                return None

            # Convert trades to OrderBookFeatures (approximation)
            hist_features = []
            
            # Sort trades by timestamp ascending
            trades.sort(key=lambda x: x['timestamp'])
            
            # Create features from trades
            # We only have price info, so we fill others with defaults or 0
            # This gives us valid Price Momentum and Volatility rolling stats, 
            # while Imbalance stats will decay towards 0 (neutral)
            
            # Extract defaults from current_features if available to avoid artificial jumps
            default_imbalance = current_features.bid_ask_imbalance if current_features else 0.0
            default_spread = current_features.spread_percent if current_features else 0.0
            default_bid_vol = current_features.bid_volume if current_features else 0.0
            default_ask_vol = current_features.ask_volume if current_features else 0.0
            default_depth = current_features.order_book_depth if current_features else 0
            default_wall_size = current_features.wall_size if current_features else 0.0
            
            for i in range(len(trades)):
                trade = trades[i]
                price = float(trade['price'])
                
                # Calculate simple momentum/volatility based on window of previous trades
                price_momentum = 0.0
                volatility = 0.0
                
                if i >= 10:
                    window = [float(t['price']) for t in trades[i-10:i+1]]
                    if window[0] != 0:
                        price_momentum = ((window[-1] - window[0]) / window[0]) * 100
                    
                    changes = np.diff(window) / (np.array(window[:-1]) + 1e-9)
                    volatility = np.std(changes) * 100

                # Create feature object
                # Use current values for missing historical data to avoid artificial jumps in rolling stats
                feat = OrderBookFeatures(
                    timestamp=int(datetime.fromisoformat(trade['timestamp'].replace('Z', '+00:00')).timestamp()),
                    symbol=symbol,
                    bid_ask_imbalance=default_imbalance,
                    spread_percent=default_spread,
                    mid_price=price,
                    bid_volume=default_bid_vol,
                    ask_volume=default_ask_vol,
                    order_book_depth=default_depth,
                    large_bid_wall=False,
                    large_ask_wall=False,
                    wall_size=default_wall_size,
                    volume_weighted_price=price, # Use price as best guess for historical VWAP
                    price_momentum=price_momentum,
                    volatility=volatility
                )
                
                # Extract raw features (this applies log transforms etc.)
                feature_dict = self.feature_engineer._extract_features(feat)
                hist_features.append(list(feature_dict.values()))

            if not hist_features:
                return None
                
            X_hist = np.array(hist_features)
            
            # We must apply Imputer to history to match X_imputed (raw features)
            # DO NOT apply Scaler here, as Scaler expects expanded features (TS + Interactions)
            # which are created in preprocess_pipeline using this history
            if self.feature_engineer.imputer:
                X_hist = self.feature_engineer.imputer.transform(X_hist)
                
            return X_hist

        except Exception as e:
            logger.warning(f"Failed to fetch historical features from Coinbase: {e}")
            return None

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
        success = self.model_manager.set_active_model(model_name)
        if success:
            # Load the transformers associated with this model
            # Extract timestamp from model name to find corresponding transformers
            # Model names follow pattern: trading_optimizer_YYYYMMDD_HHMMSS.pkl
            # Transformer directories follow pattern: transformers_YYYYMMDD_HHMMSS/
            if model_name.startswith("trading_optimizer_") and model_name.endswith(".pkl"):
                timestamp_part = model_name[len("trading_optimizer_"):-len(".pkl")]
                transformer_dir = os.path.join(self.transformers_dir, f"transformers_{timestamp_part}")
                if os.path.exists(transformer_dir):
                    # Create new feature engineer and load the model-specific transformers
                    self.feature_engineer = FeatureEngineer()
                    self.feature_engineer.load_transformers(transformer_dir)
                    logger.info(f"Loaded transformers for model {model_name} from {transformer_dir}")
                else:
                    logger.warning(f"No transformers found for model {model_name} at {transformer_dir}")
        return success

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

    def delete_model(self, model_name: str) -> bool:
        """Delete a specific model and its associated artifacts."""
        try:
            # First try the new versioned structure
            if self.model_manager.unregister_model(model_name):
                # Delete versioned directory
                model_dir = os.path.join(self.models_dir, model_name)
                if os.path.exists(model_dir):
                    import shutil
                    shutil.rmtree(model_dir)
                    logger.info(f"Deleted versioned model directory: {model_dir}")
                return True

            # Fallback to old flat file structure
            # Extract timestamp from model name to find corresponding transformers
            if model_name.startswith("trading_optimizer_") and model_name.endswith(".pkl"):
                timestamp_part = model_name[len("trading_optimizer_"):-len(".pkl")]
                transformer_dir = os.path.join(self.transformers_dir, f"transformers_{timestamp_part}")

                # Delete model file
                model_path = os.path.join(self.models_dir, model_name)
                if os.path.exists(model_path):
                    os.remove(model_path)
                    logger.info(f"Deleted model file: {model_path}")

                # Delete metadata file
                metadata_path = model_path.replace('.pkl', '_metadata.json')
                if os.path.exists(metadata_path):
                    os.remove(metadata_path)
                    logger.info(f"Deleted metadata file: {metadata_path}")

                # Delete associated transformers
                if os.path.exists(transformer_dir):
                    import shutil
                    shutil.rmtree(transformer_dir)
                    logger.info(f"Deleted transformer directory: {transformer_dir}")

                # Unregister from model manager (even if it wasn't found in versioned, it might be in legacy if loaded)
                self.model_manager.unregister_model(model_name)
                logger.info(f"Unregistered model: {model_name}")

                return True
            else:
                # Try simple directory deletion if it matches model name
                model_dir = os.path.join(self.models_dir, model_name)
                if os.path.exists(model_dir) and os.path.isdir(model_dir):
                     import shutil
                     shutil.rmtree(model_dir)
                     logger.info(f"Deleted model directory: {model_dir}")
                     self.model_manager.unregister_model(model_name)
                     return True
                
                logger.warning(f"Could not delete model: {model_name}")
                return False
        except Exception as e:
            logger.error(f"Error deleting model {model_name}: {e}")
            return False

    def delete_all_models(self) -> bool:
        """Delete all models and their associated artifacts."""
        try:
            success = True
            
            # Delete from model registry
            all_models = self.list_available_models()
            for model in all_models:
                model_name = model.get('model_name')
                if model_name:
                     # We use delete_model but allow it to fail (e.g. if file missing)
                     # as long as we clear the registry
                     try:
                        self.delete_model(model_name)
                     except Exception as e:
                        logger.warning(f"Error deleting registered model {model_name}: {e}")

            # Legacy cleanup: Get all model files
            # This catches files that were not in the registry
            model_files = glob.glob(os.path.join(self.models_dir, "trading_optimizer_*.pkl"))
            for model_file in model_files:
                model_name = os.path.basename(model_file)
                # Only try to delete if file still exists
                if os.path.exists(model_file):
                    if not self.delete_model(model_name):
                        # Only mark as failure if file exists and we couldn't delete it
                        if os.path.exists(model_file):
                            success = False
                            logger.error(f"Failed to delete legacy model file: {model_file}")

            # Also delete any remaining transformer directories
            transformer_dirs = glob.glob(os.path.join(self.transformers_dir, "transformers_*"))
            for transformer_dir in transformer_dirs:
                try:
                    import shutil
                    shutil.rmtree(transformer_dir)
                    logger.info(f"Deleted transformer directory: {transformer_dir}")
                except Exception as e:
                    logger.error(f"Error deleting transformer directory {transformer_dir}: {e}")
                    success = False

            if success:
                logger.info("All models and associated artifacts deleted successfully")
            else:
                logger.warning("Some models or artifacts could not be deleted")

            return success
        except Exception as e:
            logger.error(f"Error deleting all models: {e}")
            return False
        
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
        current_model_info = self.model_manager.get_current_model_info()

        # Skip vector DB status calls that might hang - just check if collection exists
        vector_db_status = {"exists": self.vector_db_client.check_collection_exists()}

        return {
            'is_trained': self.is_trained,
            'last_training_time': self.last_training_time.isoformat() if self.last_training_time else None,
            'current_model': {
                'model_name': current_model_info.get('model_name'),
                'version_id': current_model_info.get('version_id'),
                'deployed_at': current_model_info.get('deployed_at'),
            } if current_model_info else None,
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
