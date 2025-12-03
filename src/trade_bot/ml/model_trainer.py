"""Model Trainer for ML trading optimization."""

import logging
import numpy as np
import pandas as pd
import joblib
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import os

from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, RandomForestClassifier
from sklearn.linear_model import LinearRegression, Ridge, LogisticRegression, SGDRegressor, SGDClassifier
from sklearn.neural_network import MLPRegressor
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error, accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from sklearn.pipeline import Pipeline

logger = logging.getLogger(__name__)


try:
    from .wrapper import TradingModelWrapper
except ImportError:
    from wrapper import TradingModelWrapper


class ModelTrainer:
    """Trains ML models for trading optimization."""
    
    def __init__(self, model_type: str = 'ensemble', random_state: int = 42):
        """
        Initialize model trainer.
        
        Args:
            model_type: Type of model to train ('ensemble', 'rf', 'gb', 'nn', 'linear')
            random_state: Random state for reproducibility
        """
        self.model_type = model_type
        self.random_state = random_state
        self.models = {}
        self.model_performance = {}
        self.best_model = None
        self.best_score = -np.inf
        self.classifiers = {}
        self.classifier_performance = {}
        self.best_classifier = None
        self.best_classifier_score = -np.inf
        
    def train_models(self, X: np.ndarray, y: np.ndarray, 
                    test_size: float = 0.2) -> Dict[str, Any]:
        """Train multiple models and select the best one."""
        logger.info(f"Training {self.model_type} models with {X.shape[0]} samples")
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=self.random_state
        )
        
        # Train different model types
        if self.model_type == 'ensemble':
            self._train_ensemble_models(X_train, y_train, X_test, y_test)
        elif self.model_type == 'rf':
            self._train_random_forest(X_train, y_train, X_test, y_test)
        elif self.model_type == 'gb':
            self._train_gradient_boosting(X_train, y_train, X_test, y_test)
        elif self.model_type == 'nn':
            self._train_neural_network(X_train, y_train, X_test, y_test)
        elif self.model_type == 'linear':
            self._train_linear_models(X_train, y_train, X_test, y_test)
        
        # Select best model
        self._select_best_model()

        best_model_name = None
        if self.model_performance:
            best_model_name = max(self.model_performance.keys(),
                                key=lambda k: self.model_performance[k]['score'])
        
        return {
            'model_performance': self.model_performance,
            'best_model': best_model_name,
            'best_score': self.best_score,
            'test_size': test_size,
            'training_samples': X_train.shape[0],
            'test_samples': X_test.shape[0]
        }
    
    def train_incremental(self, data_generator, model_type: str = 'sgd', 
                         test_size: float = 0.2) -> Dict[str, Any]:
        """Train models incrementally using a data generator."""
        logger.info(f"Starting incremental training with model type: {model_type}")
        
        # Initialize model based on type
        if model_type == 'sgd':
            # Use adaptive learning rate to prevent exploding gradients
            model = SGDRegressor(loss='squared_error', penalty='l2', alpha=0.0001, 
                               learning_rate='adaptive', eta0=0.001, n_iter_no_change=5,
                               shuffle=False,
                               random_state=self.random_state)
            model_name = 'sgd_regressor'
        elif model_type == 'nn':
            model = MLPRegressor(hidden_layer_sizes=(100, 50), activation='relu', 
                               solver='adam', alpha=0.0001, batch_size=200, 
                               learning_rate='adaptive', max_iter=1, warm_start=True, 
                               random_state=self.random_state)
            model_name = 'neural_network_incremental'
        else:
            logger.warning(f"Model type {model_type} does not support incremental learning. Defaulting to SGD.")
            model = SGDRegressor(random_state=self.random_state)
            model_name = 'sgd_regressor'
            
        # Initialize classifier for win probability
        classifier = SGDClassifier(loss='log_loss', penalty='l2', alpha=0.0001, 
                                 learning_rate='optimal', random_state=self.random_state)
        classifier_name = 'sgd_classifier'
        
        total_feature_vectors = 0
        total_used_samples = 0
        batch_count = 0
        
        # Keep track of performance on the fly (using a rolling window of test data from batches)
        rolling_mse = []
        rolling_accuracy = []
        
        # Minimum samples required for train/test split
        MIN_SAMPLES_FOR_SPLIT = 5
        
        for batch_data in data_generator:
            # Handle different generator yield formats (X, y) or (X, y, processed_targets)
            if len(batch_data) == 3:
                X_batch, y_batch, processed_targets = batch_data
            else:
                X_batch, y_batch = batch_data
                processed_targets = None

            if len(X_batch) == 0:
                continue
                
            # Convert to numpy arrays
            X_batch = np.array(X_batch)
            total_feature_vectors += len(X_batch)
            
            # Check for NaNs or Infs in input data
            if np.isnan(X_batch).any() or np.isinf(X_batch).any():
                logger.warning(f"Batch {batch_count + 1} contains NaNs or Infs in features. Skipping.")
                continue
            
            # Target for regressor - use processed targets if available (normalized), otherwise raw PnL
            if processed_targets is not None:
                y_batch_reg = np.array(processed_targets)
            else:
                y_batch_reg = np.array([y.pnl for y in y_batch])
                
            y_batch_cls = np.array([y.is_win for y in y_batch]) # Target for classifier
            
            # Check for NaNs or Infs in targets
            if np.isnan(y_batch_reg).any() or np.isinf(y_batch_reg).any():
                logger.warning(f"Batch {batch_count + 1} contains NaNs or Infs in targets. Skipping.")
                continue

            # Log batch statistics for troubleshooting
            if batch_count % 10 == 0:
                logger.info(f"Batch {batch_count + 1} Stats - "
                          f"X: min={np.min(X_batch):.4f}, max={np.max(X_batch):.4f}, mean={np.mean(X_batch):.4f}, std={np.std(X_batch):.4f} | "
                          f"y: min={np.min(y_batch_reg):.4f}, max={np.max(y_batch_reg):.4f}, mean={np.mean(y_batch_reg):.4f}, std={np.std(y_batch_reg):.4f}")
            
            try:
                # Check if batch is large enough for train/test split
                if len(X_batch) >= MIN_SAMPLES_FOR_SPLIT:
                    # Split batch for validation
                    X_train, X_test, y_train_reg, y_test_reg, y_train_cls, y_test_cls = train_test_split(
                        X_batch, y_batch_reg, y_batch_cls, test_size=test_size, random_state=self.random_state
                    )
                    
                    # Partial fit regressor
                    model.partial_fit(X_train, y_train_reg)
                    
                    # Partial fit classifier (needs classes for first call)
                    classes = np.array([False, True])
                    classifier.partial_fit(X_train, y_train_cls, classes=classes)
                    
                    # Evaluate on test split only if variance exists
                    # Zero variance in targets makes R² undefined
                    if np.std(y_test_reg) > 1e-6:  # Check for non-zero variance
                        reg_score = model.score(X_test, y_test_reg)
                        
                        # Handle NaN scores
                        if np.isnan(reg_score):
                            logger.warning(f"Batch {batch_count + 1} produced NaN regression score.")
                            reg_score = 0.0
                            
                        rolling_mse.append(reg_score)
                    else:
                        # Skip score for zero-variance targets
                        logger.debug(f"Batch {batch_count + 1} has zero target variance, skipping R² evaluation")
                    
                    cls_score = classifier.score(X_test, y_test_cls)
                    rolling_accuracy.append(cls_score)
                else:
                    # Batch too small for split - use entire batch for training without validation
                    logger.info(f"Batch {batch_count + 1} has only {len(X_batch)} samples - using entire batch for training without validation")
                    
                    # Partial fit regressor with entire batch
                    model.partial_fit(X_batch, y_batch_reg)
                    
                    # Partial fit classifier with entire batch
                    classes = np.array([False, True])
                    classifier.partial_fit(X_batch, y_batch_cls, classes=classes)
            except Exception as e:
                logger.error(f"Error training on batch {batch_count + 1}: {e}")
                continue
            
            total_used_samples += len(X_batch)
            batch_count += 1
            
            if batch_count % 10 == 0:
                avg_reg = np.mean(rolling_mse[-10:]) if rolling_mse else 0.0
                avg_cls = np.mean(rolling_accuracy[-10:]) if rolling_accuracy else 0.0
                logger.info(f"Processed {batch_count} batches. "
                          f"Total Vectors: {total_feature_vectors}, Used Samples: {total_used_samples}. "
                          f"Avg Reg Score: {avg_reg:.4f}, "
                          f"Avg Cls Score: {avg_cls:.4f}")
        
        # Store models
        self.models[model_name] = model
        self.classifiers[classifier_name] = classifier
        
        # Calculate final average scores
        avg_reg_score = np.mean(rolling_mse) if rolling_mse else 0.0
        avg_cls_score = np.mean(rolling_accuracy) if rolling_accuracy else 0.0
        
        # Final sanity check for NaN
        if np.isnan(avg_reg_score):
            avg_reg_score = 0.0
            
        self.model_performance[model_name] = {'score': avg_reg_score, 'type': 'incremental'}
        self.classifier_performance[classifier_name] = {'accuracy': avg_cls_score, 'type': 'incremental'}
        
        # Set best models
        self.best_model = model
        self.best_score = avg_reg_score
        self.best_classifier = classifier
        self.best_classifier_score = avg_cls_score
        
        # Save models
        self.save_model(model, f"data/models/{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl",
                       performance_metrics=self.model_performance, score=avg_reg_score)
        
        self.save_model(classifier, f"data/models/{classifier_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl",
                       performance_metrics=self.classifier_performance, score=avg_cls_score)
        
        logger.info(f"Incremental training complete. "
                  f"Total Vectors: {total_feature_vectors}, Used Samples: {total_used_samples}, Batches: {batch_count}. "
                  f"Final Reg Score: {avg_reg_score:.4f}, Final Cls Score: {avg_cls_score:.4f}")
        
        return {
            'model_performance': self.model_performance,
            'classifier_performance': self.classifier_performance,
            'best_model': model_name,
            'best_classifier': classifier_name,
            'best_score': self.best_score,
            'best_classifier_score': self.best_classifier_score,
            'total_feature_vectors': total_feature_vectors,
            'total_used_samples': total_used_samples,
            'batches_processed': batch_count
        }

    
    def train_classifiers(self, X: np.ndarray, y: np.ndarray, 
                         test_size: float = 0.2) -> Dict[str, Any]:
        """Train classifier models for win probability."""
        logger.info(f"Training classifiers with {X.shape[0]} samples")
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=self.random_state, stratify=y
        )
        
        # Logistic Regression
        lr_model = LogisticRegression(random_state=self.random_state, max_iter=1000)
        lr_model.fit(X_train, y_train)
        lr_score = self._evaluate_classifier(lr_model, X_test, y_test)
        self.classifiers['logistic_regression'] = lr_model
        self.classifier_performance['logistic_regression'] = lr_score
        self.save_model(lr_model, f"data/models/win_classifier_logreg_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl",
                       performance_metrics=self.classifier_performance, score=lr_score['roc_auc'])
        
        # Random Forest Classifier
        rf_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=8,
            random_state=self.random_state
        )
        rf_model.fit(X_train, y_train)
        rf_score = self._evaluate_classifier(rf_model, X_test, y_test)
        self.classifiers['random_forest_classifier'] = rf_model
        self.classifier_performance['random_forest_classifier'] = rf_score
        self.save_model(rf_model, f"data/models/win_classifier_rf_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl",
                       performance_metrics=self.classifier_performance, score=rf_score['roc_auc'])
        
        # Select best classifier
        if self.classifier_performance:
            best_clf_name = max(self.classifier_performance.keys(),
                                key=lambda k: self.classifier_performance[k]['roc_auc'])
            self.best_classifier = self.classifiers[best_clf_name]
            self.best_classifier_score = self.classifier_performance[best_clf_name]['roc_auc']
            logger.info(f"Best classifier: {best_clf_name} with ROC AUC: {self.best_classifier_score}")
            
        return {
            'classifier_performance': self.classifier_performance,
            'best_classifier': best_clf_name if self.classifier_performance else None,
            'best_score': self.best_classifier_score
        }

    def _evaluate_classifier(self, model: Any, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, float]:
        """Evaluate classifier performance."""
        y_pred = model.predict(X_test)
        y_prob = model.predict_proba(X_test)[:, 1]
        
        return {
            'accuracy': float(accuracy_score(y_test, y_pred)),
            'precision': float(precision_score(y_test, y_pred, zero_division=0)),
            'recall': float(recall_score(y_test, y_pred, zero_division=0)),
            'f1': float(f1_score(y_test, y_pred, zero_division=0)),
            'roc_auc': float(roc_auc_score(y_test, y_prob))
        }

    def predict_proba(self, X: np.ndarray) -> Optional[np.ndarray]:
        """Make probability predictions using the best classifier."""
        if self.best_classifier is None:
            return None
        return self.best_classifier.predict_proba(X)
    
    def _train_ensemble_models(self, X_train: np.ndarray, y_train: np.ndarray,
                              X_test: np.ndarray, y_test: np.ndarray) -> None:
        """Train ensemble of different model types."""
        
        # Random Forest
        rf_model = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=self.random_state
        )
        rf_model.fit(X_train, y_train)
        rf_score = self._evaluate_model(rf_model, X_test, y_test)
        self.models['random_forest'] = rf_model
        self.model_performance['random_forest'] = rf_score
        self.save_model(rf_model, f"data/models/random_forest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl")

        # Gradient Boosting
        gb_model = GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=6,
            random_state=self.random_state
        )
        gb_model.fit(X_train, y_train)
        gb_score = self._evaluate_model(gb_model, X_test, y_test)
        self.models['gradient_boosting'] = gb_model
        self.model_performance['gradient_boosting'] = gb_score
        self.save_model(gb_model, f"data/models/gradient_boosting_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl")

        # Neural Network
        nn_model = MLPRegressor(
            hidden_layer_sizes=(100, 50),
            activation='relu',
            solver='adam',
            alpha=0.001,
            learning_rate='adaptive',
            max_iter=1000,
            random_state=self.random_state
        )
        nn_model.fit(X_train, y_train)
        nn_score = self._evaluate_model(nn_model, X_test, y_test)
        self.models['neural_network'] = nn_model
        self.model_performance['neural_network'] = nn_score
        self.save_model(nn_model, f"data/models/neural_network_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl")

        # Ridge Regression
        ridge_model = Ridge(alpha=1.0, random_state=self.random_state)
        ridge_model.fit(X_train, y_train)
        ridge_score = self._evaluate_model(ridge_model, X_test, y_test)
        self.models['ridge'] = ridge_model
        self.model_performance['ridge'] = ridge_score
        self.save_model(ridge_model, f"data/models/ridge_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl")
        
        logger.info(f"Ensemble training complete. Scores: {self.model_performance}")
    
    def _train_random_forest(self, X_train: np.ndarray, y_train: np.ndarray,
                            X_test: np.ndarray, y_test: np.ndarray) -> None:
        """Train Random Forest with hyperparameter tuning."""
        
        # Define parameter grid
        param_grid = {
            'n_estimators': [50, 100, 200],
            'max_depth': [5, 10, 15, None],
            'min_samples_split': [2, 5, 10],
            'min_samples_leaf': [1, 2, 4]
        }
        
        # Grid search
        rf = RandomForestRegressor(random_state=self.random_state)
        grid_search = GridSearchCV(
            rf, param_grid, cv=5, scoring='neg_mean_squared_error', n_jobs=-1
        )
        grid_search.fit(X_train, y_train)
        
        # Train final model with best parameters
        best_rf = grid_search.best_estimator_
        score = self._evaluate_model(best_rf, X_test, y_test)
        
        self.models['random_forest'] = best_rf
        self.model_performance['random_forest'] = score
        
        logger.info(f"Random Forest training complete. Score: {score}")
    
    def _train_gradient_boosting(self, X_train: np.ndarray, y_train: np.ndarray,
                                X_test: np.ndarray, y_test: np.ndarray) -> None:
        """Train Gradient Boosting with hyperparameter tuning."""
        
        # Define parameter grid
        param_grid = {
            'n_estimators': [50, 100, 200],
            'learning_rate': [0.01, 0.1, 0.2],
            'max_depth': [3, 6, 9],
            'subsample': [0.8, 0.9, 1.0]
        }
        
        # Grid search
        gb = GradientBoostingRegressor(random_state=self.random_state)
        grid_search = GridSearchCV(
            gb, param_grid, cv=5, scoring='neg_mean_squared_error', n_jobs=-1
        )
        grid_search.fit(X_train, y_train)
        
        # Train final model with best parameters
        best_gb = grid_search.best_estimator_
        score = self._evaluate_model(best_gb, X_test, y_test)
        
        self.models['gradient_boosting'] = best_gb
        self.model_performance['gradient_boosting'] = score
        
        logger.info(f"Gradient Boosting training complete. Score: {score}")
    
    def _train_neural_network(self, X_train: np.ndarray, y_train: np.ndarray,
                             X_test: np.ndarray, y_test: np.ndarray) -> None:
        """Train Neural Network with hyperparameter tuning."""
        
        # Define parameter grid
        param_grid = {
            'hidden_layer_sizes': [(50,), (100,), (100, 50), (100, 50, 25)],
            'activation': ['relu', 'tanh'],
            'alpha': [0.0001, 0.001, 0.01],
            'learning_rate': ['constant', 'adaptive']
        }
        
        # Grid search
        nn = MLPRegressor(random_state=self.random_state, max_iter=1000)
        grid_search = GridSearchCV(
            nn, param_grid, cv=5, scoring='neg_mean_squared_error', n_jobs=-1
        )
        grid_search.fit(X_train, y_train)
        
        # Train final model with best parameters
        best_nn = grid_search.best_estimator_
        score = self._evaluate_model(best_nn, X_test, y_test)
        
        self.models['neural_network'] = best_nn
        self.model_performance['neural_network'] = score
        
        logger.info(f"Neural Network training complete. Score: {score}")
    
    def _train_linear_models(self, X_train: np.ndarray, y_train: np.ndarray,
                            X_test: np.ndarray, y_test: np.ndarray) -> None:
        """Train linear models."""
        
        # Linear Regression
        lr_model = LinearRegression()
        lr_model.fit(X_train, y_train)
        lr_score = self._evaluate_model(lr_model, X_test, y_test)
        self.models['linear_regression'] = lr_model
        self.model_performance['linear_regression'] = lr_score
        
        # Ridge Regression
        ridge_model = Ridge(alpha=1.0, random_state=self.random_state)
        ridge_model.fit(X_train, y_train)
        ridge_score = self._evaluate_model(ridge_model, X_test, y_test)
        self.models['ridge'] = ridge_model
        self.model_performance['ridge'] = ridge_score
        
        logger.info(f"Linear models training complete. Scores: {self.model_performance}")
    
    def _evaluate_model(self, model: Any, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, float]:
        """Evaluate model performance."""
        y_pred = model.predict(X_test)
        
        mse = mean_squared_error(y_test, y_pred)
        rmse = np.sqrt(mse)
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        
        # Calculate trading-specific metrics
        profit_factor = self._calculate_profit_factor(y_test, y_pred)
        sharpe_ratio = self._calculate_sharpe_ratio(y_test, y_pred)
        
        return {
            'mse': float(mse),
            'rmse': float(rmse),
            'mae': float(mae),
            'r2': float(r2),
            'profit_factor': float(profit_factor),
            'sharpe_ratio': float(sharpe_ratio),
            'score': float(r2)
        }
    
    def _calculate_profit_factor(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """Calculate profit factor for trading performance."""
        # Use predictions as trading signals
        signals = np.sign(y_pred)
        returns = signals * y_true
        
        profits = returns[returns > 0].sum()
        losses = abs(returns[returns < 0].sum())
        
        return profits / losses if losses > 0 else float('inf')
    
    def _calculate_sharpe_ratio(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """Calculate Sharpe ratio for trading performance."""
        # Use predictions as trading signals
        signals = np.sign(y_pred)
        returns = signals * y_true
        
        if len(returns) == 0 or np.std(returns) == 0:
            return 0.0
        
        return np.mean(returns) / np.std(returns) * np.sqrt(252)  # Annualized
    
    def _select_best_model(self) -> None:
        """Select the best performing model."""
        if not self.model_performance:
            logger.warning("No models trained yet")
            return
        
        best_model_name = max(self.model_performance.keys(), 
                            key=lambda k: self.model_performance[k]['score'])
        
        self.best_model = self.models[best_model_name]
        self.best_score = self.model_performance[best_model_name]['score']
        
        logger.info(f"Best model: {best_model_name} with score: {self.best_score}")
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Make predictions using the best model."""
        if self.best_model is None:
            raise ValueError("No model trained yet")
        
        return self.best_model.predict(X)
    
    def get_feature_importance(self) -> Optional[np.ndarray]:
        """Get feature importance from the best model."""
        if self.best_model is None:
            return None
        
        if hasattr(self.best_model, 'feature_importances_'):
            return self.best_model.feature_importances_
        elif hasattr(self.best_model, 'coef_'):
            return np.abs(self.best_model.coef_)
        else:
            return None
    
    def save_model(self, model: Any, filepath: str, performance_metrics: Dict = None, score: float = None) -> bool:
        """Save a model to disk."""
        if model is None:
            logger.error("No model to save")
            return False
        
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Save model
            joblib.dump(model, filepath)
            
            # Save metadata
            metadata = {
                'model_type': self.model_type,
                'model_performance': performance_metrics if performance_metrics is not None else self.model_performance,
                'best_score': score if score is not None else self.best_score,
                'timestamp': datetime.now().isoformat(),
                'random_state': self.random_state
            }
            
            metadata_path = filepath.replace('.pkl', '_metadata.json')
            import json
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Model saved to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving model: {e}")
            return False
    
    def load_model(self, filepath: str) -> bool:
        """Load a saved model."""
        try:
            self.best_model = joblib.load(filepath)
            
            # Load metadata
            metadata_path = filepath.replace('.pkl', '_metadata.json')
            if os.path.exists(metadata_path):
                import json
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                    self.model_performance = metadata.get('model_performance', {})
                    self.best_score = metadata.get('best_score', 0.0)
                    self.model_type = metadata.get('model_type', 'unknown')
            
            logger.info(f"Model loaded from {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return False
    
    def cross_validate(self, X: np.ndarray, y: np.ndarray, cv: int = 5) -> Dict[str, Any]:
        """Perform cross-validation on the best model."""
        if self.best_model is None:
            raise ValueError("No model trained yet")
        
        # Perform cross-validation
        cv_scores = cross_val_score(self.best_model, X, y, cv=cv, scoring='r2')
        
        return {
            'cv_scores': cv_scores.tolist(),
            'mean_cv_score': cv_scores.mean(),
            'std_cv_score': cv_scores.std(),
            'cv_folds': cv
        }
