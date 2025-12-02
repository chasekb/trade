"""Feature Engineering for ML trading models."""

import logging
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.feature_selection import SelectKBest, f_regression
from sklearn.impute import SimpleImputer
import joblib
import os

logger = logging.getLogger(__name__)


@dataclass
class ProcessedFeatures:
    """Processed feature vector for ML training."""
    features: np.ndarray
    feature_names: List[str]
    target: float
    metadata: Dict[str, Any]


class FeatureEngineer:
    """Engineers features from raw trading data for ML models."""
    
    def __init__(self, feature_scaling: str = 'standard'):
        """
        Initialize feature engineer.
        
        Args:
            feature_scaling: Type of scaling to apply ('standard', 'minmax', 'none')
        """
        self.feature_scaling = feature_scaling
        self.scaler = None
        self.feature_selector = None
        self.feature_names = []
        self.imputer = None
        
    def create_feature_matrix(self, feature_vectors: List[Any], 
                             trade_outcomes: List[Any]) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """Create feature matrix and targets from raw data."""
        if not feature_vectors or not trade_outcomes:
            logger.warning("No feature vectors or trade outcomes provided")
            return np.array([]), np.array([]), []
        
        # Extract features and targets
        features_list = []
        targets = []
        
        for features, outcome in zip(feature_vectors, trade_outcomes):
            try:
                # Create feature vector
                feature_dict = self._extract_features(features)
                features_list.append(list(feature_dict.values()))
                
                # Create target (normalized P&L considering fees)
                target = self._calculate_target(outcome)
                targets.append(target)
                
            except Exception as e:
                logger.warning(f"Error processing feature vector: {e}")
                continue
        
        if not features_list:
            logger.warning("No valid feature vectors created")
            return np.array([]), np.array([]), []
        
        # Convert to numpy arrays
        X = np.array(features_list)
        y = np.array(targets)
        
        # Generate feature names from the first feature vector
        feature_names = self._generate_feature_names(feature_vectors[0])
        self.feature_names = feature_names
        
        logger.info(f"Created feature matrix: {X.shape[0]} samples, {X.shape[1]} features")
        return X, y, feature_names
    
    def _extract_features(self, features: Any) -> Dict[str, float]:
        """Extract numerical features from feature vector."""
        
        # Basic order book features
        feature_dict = {
            'bid_ask_imbalance': features.bid_ask_imbalance,
            'spread_percent': features.spread_percent,
            'mid_price': features.mid_price,
            'bid_volume': features.bid_volume,
            'ask_volume': features.ask_volume,
            'order_book_depth': features.order_book_depth,
            'large_bid_wall': float(features.large_bid_wall),
            'large_ask_wall': float(features.large_ask_wall),
            'wall_size': features.wall_size,
            'volume_weighted_price': features.volume_weighted_price,
            'price_momentum': features.price_momentum,
            'volatility': features.volatility
        }
        
        # Derived features
        feature_dict.update({
            'volume_ratio': np.log(features.bid_volume + 1) - np.log(features.ask_volume + 1),
            'spread_normalized': features.spread_percent / (features.mid_price + 1e-8),
            'wall_size_normalized': features.wall_size / (features.bid_volume + features.ask_volume + 1e-8),
            'momentum_normalized': features.price_momentum / (features.volatility + 1e-8),
            'depth_normalized': features.order_book_depth / 100.0
        })
        
        # Technical indicators
        feature_dict.update({
            'rsi_like': self._calculate_rsi_like(features.price_momentum),
            'volatility_bands': self._calculate_volatility_bands(features.volatility),
            'trend_indicator': self._calculate_trend_indicator(features.price_momentum, features.volatility),
            'macd_like': self._calculate_macd_like(features.mid_price, features.volume_weighted_price),
            'bollinger_bands_like': self._calculate_bollinger_bands_like(features.mid_price, features.volatility),
            'atr_like': self._calculate_atr_like(features.volatility)
        })
        
        # Clean up NaNs and infinities
        for key, value in feature_dict.items():
            feature_dict[key] = np.nan_to_num(value, nan=0.0, posinf=1e9, neginf=-1e9)
            
        return feature_dict
    
    def _calculate_target(self, outcome: Any) -> float:
        """Calculate target variable for ML training."""
        # Normalized P&L considering fees and risk
        gross_pnl = outcome.pnl
        fees = outcome.fees
        net_pnl = gross_pnl - fees
        
        # Risk-adjusted return
        if outcome.quantity > 0:
            risk_adjusted_return = net_pnl / (outcome.quantity * outcome.entry_price)
        else:
            risk_adjusted_return = 0.0
        
        # Scale to reasonable range for ML training
        return np.clip(risk_adjusted_return * 100, -10.0, 10.0)
    
    def _generate_feature_names(self, features: Any) -> List[str]:
        """Generate feature names from a sample feature object."""
        feature_dict = self._extract_features(features)
        return list(feature_dict.keys())
    
    def _calculate_rsi_like(self, momentum: float) -> float:
        """Calculate RSI-like momentum indicator."""
        # Simplified RSI calculation
        return np.tanh(momentum / 5.0)  # Normalize to [-1, 1]
    
    def _calculate_volatility_bands(self, volatility: float) -> float:
        """Calculate volatility-based bands."""
        # Normalize volatility to [0, 1] range
        return np.clip(volatility / 10.0, 0.0, 1.0)
    
    def _calculate_trend_indicator(self, momentum: float, volatility: float) -> float:
        """Calculate MACD-like trend indicator."""
        # Combine momentum and volatility for trend strength
        trend_strength = momentum / (volatility + 1e-8)
        return np.tanh(trend_strength / 2.0)  # Normalize to [-1, 1]

    def _calculate_macd_like(self, mid_price: float, vw_price: float) -> float:
        """Calculate an approximated MACD."""
        # Use the difference between mid-price and VWAP as a proxy for the MACD line
        macd_line = mid_price - vw_price
        # Normalize to a reasonable range
        return np.tanh(macd_line / (mid_price * 0.01)) if mid_price else 0.0

    def _calculate_bollinger_bands_like(self, mid_price: float, volatility: float) -> float:
        """Calculate approximated Bollinger Bands."""
        # Use volatility to create bands around the mid-price
        upper_band = mid_price + (2 * volatility)
        lower_band = mid_price - (2 * volatility)
        # Return the width of the bands as a percentage of the mid-price
        return (upper_band - lower_band) / mid_price if mid_price else 0.0

    def _calculate_atr_like(self, volatility: float) -> float:
        """Calculate an approximated Average True Range."""
        # Use the current volatility as a proxy for ATR
        return volatility
    
    def fit_scaler(self, X: np.ndarray) -> None:
        """Fit feature scaler on training data."""
        if self.feature_scaling == 'standard':
            self.scaler = StandardScaler()
        elif self.feature_scaling == 'minmax':
            self.scaler = MinMaxScaler()
        else:
            self.scaler = None
        
        if self.scaler is not None:
            self.scaler.fit(X)
            logger.info(f"Fitted {self.feature_scaling} scaler")
    
    def transform_features(self, X: np.ndarray) -> np.ndarray:
        """Transform features using fitted scaler."""
        if self.scaler is not None:
            return self.scaler.transform(X)
        return X
    
    def impute_features(self, X: np.ndarray) -> np.ndarray:
        """Impute missing values using fitted imputer."""
        if self.imputer is not None:
            return self.imputer.transform(X)
        return X
    
    def fit_feature_selector(self, X: np.ndarray, y: np.ndarray, k: int = 128) -> None:
        """Fit feature selector to choose most important features."""
        if k > X.shape[1]:
            logger.warning(f"k={k} is greater than the number of features {X.shape[1]}. Adjusting k to {X.shape[1]}.")
            k = X.shape[1]
        
        self.feature_selector = SelectKBest(score_func=f_regression, k=k)
        self.feature_selector.fit(X, y)
        
        # Update feature names to selected features
        selected_indices = self.feature_selector.get_support(indices=True)
        
        # Generate new names for the expanded features
        base_names = self.feature_names
        
        # Names for time series features
        ts_mean_names = [f"{name}_mean" for name in base_names]
        ts_std_names = [f"{name}_std" for name in base_names]
        
        # Names for interaction features
        interaction_names = []
        key_features_indices = list(range(min(5, len(base_names))))
        
        for i in key_features_indices:
            for j in range(i, len(key_features_indices)):
                if i == j:
                    interaction_names.append(f"{base_names[i]}_sq")
                else:
                    interaction_names.append(f"{base_names[i]}_x_{base_names[j]}")

        # Combine all feature names in the correct order
        extended_feature_names = base_names + ts_mean_names + ts_std_names + interaction_names
        
        # Ensure the generated names match the number of features
        if len(extended_feature_names) != X.shape[1]:
            logger.warning(f"Mismatch in feature names ({len(extended_feature_names)}) and feature count ({X.shape[1]}). Using generic names.")
            extended_feature_names = [f"feature_{i}" for i in range(X.shape[1])]

        self.feature_names = [extended_feature_names[i] for i in selected_indices]
        
        logger.info(f"Selected {len(self.feature_names)} most important features")

    def partial_fit(self, X: np.ndarray, y: Optional[np.ndarray] = None) -> None:
        """Incrementally fit transformers on a batch of data."""
        # Step 1: Handle missing values
        if self.imputer is None:
            self.imputer = SimpleImputer(strategy='mean')
            # SimpleImputer doesn't support partial_fit in all versions/configurations easily 
            # without knowing all stats, but for 'mean', we can use fit on the first batch 
            # and then transform. True partial_fit for imputer is tricky.
            # However, for 'mean', we can just fit on the batch if we assume batches are representative.
            # Better approach for streaming: Use a pre-defined constant or robust scaling that handles NaNs.
            # For now, we'll fit on the current batch if not fitted.
            self.imputer.fit(X)
        else:
            # Re-fitting on new batch might shift means slightly, but standard SimpleImputer 
            # doesn't have partial_fit. We'll stick with the initial fit or refit if needed.
            # Ideally we'd use an incremental imputer, but for now let's assume the first batch 
            # gives a good enough mean, or we just refit (which is wrong for global mean).
            # Let's skip refitting imputer for now to keep it stable.
            pass

        X_imputed = self.imputer.transform(X)

        # Step 2: Feature scaling
        if self.scaler is None:
            if self.feature_scaling == 'standard':
                self.scaler = StandardScaler()
            elif self.feature_scaling == 'minmax':
                self.scaler = MinMaxScaler()
        
        if self.scaler is not None and hasattr(self.scaler, 'partial_fit'):
            self.scaler.partial_fit(X_imputed)
        
        # Step 3: Feature selection
        # SelectKBest does not support partial_fit. We will skip feature selection updates 
        # during incremental learning and rely on the initial selection or a separate selection phase.
        if self.feature_selector is None and y is not None:
             # If this is the first batch, we can try to fit it
             self.fit_feature_selector(X_imputed, y)

    
    def transform_features_selected(self, X: np.ndarray) -> np.ndarray:
        """Transform features using fitted selector."""
        if self.feature_selector is not None:
            return self.feature_selector.transform(X)
        return X
    
    def create_time_series_features(self, X: np.ndarray, window_size: int = 5, historical_data: Optional[np.ndarray] = None) -> np.ndarray:
        """Create time series features by adding rolling statistics."""
        
        # For a single prediction, use provided historical data
        if X.shape[0] == 1:
            # If historical data is available, combine it with the current sample
            if historical_data is not None and historical_data.size > 0:
                combined_data = np.vstack([historical_data, X])
            else:
                # If no history, use only the current sample
                combined_data = X

            # Calculate rolling statistics on the combined data
            rolling_stats_df = pd.DataFrame(combined_data).rolling(window=window_size, min_periods=1)
            rolling_mean = rolling_stats_df.mean().values
            rolling_std = rolling_stats_df.std().fillna(0).values
            
            # Extract the stats for the latest data point
            latest_rolling_mean = rolling_mean[-1, :].reshape(1, -1)
            latest_rolling_std = rolling_std[-1, :].reshape(1, -1)

            # Combine original features with the latest rolling statistics
            X_enhanced = np.column_stack([X, latest_rolling_mean, latest_rolling_std])

        # For batch processing (training), calculate rolling stats directly
        else:
            rolling_mean = pd.DataFrame(X).rolling(window=window_size, min_periods=1).mean().values
            rolling_std = pd.DataFrame(X).rolling(window=window_size, min_periods=1).std().fillna(0).values
            X_enhanced = np.column_stack([X, rolling_mean, rolling_std])

        logger.info(f"Enhanced features with time series: {X_enhanced.shape}")
        return X_enhanced

    def create_time_series_features_incremental(self, X: np.ndarray, window_size: int = 5, 
                                              previous_window: Optional[np.ndarray] = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        Create time series features for a batch, using previous window for continuity.
        Returns (enhanced_features, last_window_of_this_batch).
        """
        # Combine with previous window if available
        if previous_window is not None and previous_window.size > 0:
            combined_data = np.vstack([previous_window, X])
            start_idx = len(previous_window)
        else:
            combined_data = X
            start_idx = 0
            
        # Calculate rolling stats
        rolling_mean = pd.DataFrame(combined_data).rolling(window=window_size, min_periods=1).mean().values
        rolling_std = pd.DataFrame(combined_data).rolling(window=window_size, min_periods=1).std().fillna(0).values
        
        # Slice back to the original batch size
        batch_rolling_mean = rolling_mean[start_idx:]
        batch_rolling_std = rolling_std[start_idx:]
        
        X_enhanced = np.column_stack([X, batch_rolling_mean, batch_rolling_std])
        
        # Save the last window for the next batch
        last_window = combined_data[-window_size:] if len(combined_data) >= window_size else combined_data
        
        return X_enhanced, last_window

    
    def create_interaction_features(self, X: np.ndarray) -> np.ndarray:
        """Create interaction features between important variables."""
        if X.shape[1] < 2:
            return X
        
        # Select key features for interactions (first 5 features)
        key_features = X[:, :5]
        
        # Create polynomial features (degree 2)
        interaction_features = []
        
        for i in range(key_features.shape[1]):
            for j in range(i, key_features.shape[1]):
                if i == j:
                    # Square terms
                    interaction_features.append(key_features[:, i] ** 2)
                else:
                    # Interaction terms
                    interaction_features.append(key_features[:, i] * key_features[:, j])
        
        # Combine original features with interactions
        X_interactions = np.column_stack([X] + interaction_features)
        
        logger.info(f"Enhanced features with interactions: {X_interactions.shape}")
        return X_interactions
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance scores."""
        if self.feature_selector is None or not hasattr(self.feature_selector, 'scores_'):
            return {}
        
        scores = self.feature_selector.scores_
        
        importance_dict = {}
        for i, score in enumerate(scores):
            if i < len(self.feature_names):
                importance_dict[self.feature_names[i]] = float(score)
        
        # Sort by importance
        sorted_importance = sorted(importance_dict.items(), key=lambda item: item[1], reverse=True)
        return dict(sorted_importance)
    
    def preprocess_pipeline(self, X: np.ndarray, y: Optional[np.ndarray], 
                          fit_transform: bool = True, 
                          historical_data: Optional[np.ndarray] = None) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """Complete preprocessing pipeline."""
        logger.info("Starting preprocessing pipeline")
        
        # Step 1: Handle missing values
        if fit_transform:
            self.imputer = SimpleImputer(strategy='mean')
            X_imputed = self.imputer.fit_transform(X)
        else:
            X_imputed = self.imputer.transform(X)

        # Step 2: Time series and interaction features (on unscaled data)
        # Note: We create these first, then scale everything together
        X_ts = self.create_time_series_features(X_imputed, historical_data=historical_data)
        X_interactions = self.create_interaction_features(X_ts)
        
        # Step 3: Feature scaling (AFTER creating interactions)
        # This ensures polynomial features are also normalized
        if fit_transform:
            self.fit_scaler(X_interactions)
        X_scaled = self.transform_features(X_interactions)

        # Step 4: Feature selection
        if fit_transform and y is not None:
            self.fit_feature_selector(X_scaled, y)
        X_selected = self.transform_features_selected(X_scaled)
        
        X_final = X_selected
        
        logger.info(f"Preprocessing complete: {X_final.shape}")
        return X_final, y

    def preprocess_pipeline_incremental(self, X: np.ndarray, y: Optional[np.ndarray] = None, 
                                      fit: bool = False,
                                      previous_window: Optional[np.ndarray] = None) -> Tuple[np.ndarray, Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Incremental preprocessing pipeline.
        Returns (X_processed, y_processed, next_window).
        """
        # Step 1: Handle missing values
        if fit:
            self.partial_fit(X, y)
            
        if self.imputer:
            X_imputed = self.imputer.transform(X)
        else:
            X_imputed = X # Should not happen if fit called or loaded

        # Step 2: Time series and interaction features (on unscaled data for incremental)
        # Note: For incremental learning, we create features first then scale
        X_ts, next_window = self.create_time_series_features_incremental(X_imputed, previous_window=previous_window)
        X_interactions = self.create_interaction_features(X_ts)
        
        # Step 3: Feature scaling (AFTER creating interactions)
        if self.scaler:
            X_scaled = self.scaler.transform(X_interactions)
        else:
            X_scaled = X_interactions

        # Step 4: Feature selection
        if self.feature_selector:
            X_selected = self.feature_selector.transform(X_scaled)
        else:
            X_selected = X_scaled
        
        # Log feature statistics for troubleshooting
        if X_selected.shape[0] > 0:
             logger.info(f"Processed Features Stats - "
                       f"min={np.min(X_selected):.4f}, max={np.max(X_selected):.4f}, "
                       f"mean={np.mean(X_selected):.4f}, std={np.std(X_selected):.4f}")

        return X_selected, y, next_window


    def save_transformers(self, directory: str) -> None:
        """Save fitted transformers to disk."""
        os.makedirs(directory, exist_ok=True)
        if self.imputer:
            joblib.dump(self.imputer, os.path.join(directory, 'imputer.pkl'))
        if self.scaler:
            joblib.dump(self.scaler, os.path.join(directory, 'scaler.pkl'))
        if self.feature_selector:
            joblib.dump(self.feature_selector, os.path.join(directory, 'feature_selector.pkl'))
        logger.info(f"Saved transformers to {directory}")

    def load_transformers(self, directory: str) -> None:
        """Load fitted transformers from disk."""
        imputer_path = os.path.join(directory, 'imputer.pkl')
        if os.path.exists(imputer_path):
            self.imputer = joblib.load(imputer_path)
        scaler_path = os.path.join(directory, 'scaler.pkl')
        if os.path.exists(scaler_path):
            self.scaler = joblib.load(scaler_path)
        selector_path = os.path.join(directory, 'feature_selector.pkl')
        if os.path.exists(selector_path):
            self.feature_selector = joblib.load(selector_path)
        logger.info(f"Loaded transformers from {directory}")
