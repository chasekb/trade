"""Feature Engineering for ML trading models."""

import logging
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.feature_selection import SelectKBest, f_regression
from sklearn.decomposition import PCA
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
        self.pca = None
        self.feature_selector = None
        self.feature_names = []
        self.imputer = None
        
        # Removed feature weighting state
        
    # Removed update_error_signal and _apply_learned_weights as per refactoring for PCA

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
        
        # Log-transform volume and count features
        bid_volume_log = np.log1p(features.bid_volume)
        ask_volume_log = np.log1p(features.ask_volume)
        wall_size_log = np.log1p(features.wall_size)
        depth_log = np.log1p(features.order_book_depth)

        # Log-transform prices (for later return calculation)
        mid_price_log = np.log(features.mid_price) if features.mid_price > 0 else 0.0
        vwap_log = np.log(features.volume_weighted_price) if features.volume_weighted_price > 0 else 0.0
        
        # Basic order book features
        feature_dict = {
            'bid_ask_imbalance': features.bid_ask_imbalance,
            'spread_percent': features.spread_percent,
            'mid_price_log': mid_price_log,
            'bid_volume_log': bid_volume_log,
            'ask_volume_log': ask_volume_log,
            'order_book_depth_log': depth_log,
            'large_bid_wall': float(features.large_bid_wall),
            'large_ask_wall': float(features.large_ask_wall),
            'wall_size_log': wall_size_log,
            'volume_weighted_price_log': vwap_log,
            'price_momentum': features.price_momentum,
            'volatility': features.volatility
        }
        
        # Derived features
        feature_dict.update({
            'volume_ratio': bid_volume_log / (ask_volume_log + 1e-8),
            'spread_normalized': features.spread_percent / (features.mid_price + 1e-8), # Keep spread relative to price? Or assume spread_percent is already relative? Usually spread_percent is (ask-bid)/bid, so it's scale invariant.
            'wall_size_ratio': wall_size_log / (bid_volume_log + ask_volume_log + 1e-8),
            'momentum_normalized': features.price_momentum / (features.volatility + 1e-8)
        })

        # Meta-Features Integration
        # Encoding symbol using liquidity, volatility, and price position
        if hasattr(features, 'volume_24h'):
            feature_dict['liquidity_short'] = np.log1p(features.volume_24h)
        else:
             feature_dict['liquidity_short'] = 0.0

        if hasattr(features, 'volume_30d'):
            feature_dict['liquidity_long'] = np.log1p(features.volume_30d)
        else:
            feature_dict['liquidity_long'] = 0.0
            
        if hasattr(features, 'high_24h') and hasattr(features, 'low_24h') and features.low_24h > 0:
            feature_dict['volatility_24h'] = (features.high_24h - features.low_24h) / features.low_24h
        else:
            feature_dict['volatility_24h'] = 0.0

        if hasattr(features, 'high_24h') and hasattr(features, 'low_24h') and features.low_24h < features.high_24h:
             # ((last - low) / (high - low))
             feature_dict['price_position_24h'] = (features.mid_price - features.low_24h) / (features.high_24h - features.low_24h)
        else:
             feature_dict['price_position_24h'] = 0.5 # Middle
        
        # Technical indicators (using log prices where appropriate)
        feature_dict.update({
            'rsi_like': self._calculate_rsi_like(features.price_momentum),
            'volatility_bands': self._calculate_volatility_bands(features.volatility),
            'trend_indicator': self._calculate_trend_indicator(features.price_momentum, features.volatility),
            'macd_like': mid_price_log - vwap_log, # Log difference is approx percentage difference
            'bollinger_bands_like': self._calculate_bollinger_bands_like(features.mid_price, features.volatility),
            'atr_like': self._calculate_atr_like(features.volatility)
        })
        
        # Clean up NaNs and infinities
        for key, value in feature_dict.items():
            feature_dict[key] = float(np.nan_to_num(value, nan=0.0, posinf=1e9, neginf=-1e9))
            
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
        return risk_adjusted_return
    
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
        # Force StandardScaler as per requirements, or stick to config if compatible
        if self.feature_scaling == 'minmax':
             logger.warning("Switching to StandardScaler for scale invariance requirement")
             self.feature_scaling = 'standard'

        if self.feature_scaling == 'standard':
            self.scaler = StandardScaler()
        else:
            self.scaler = StandardScaler() # Default to StandardScaler
        
        if self.scaler is not None:
            # Initialize random sample weights
            rng = np.random.RandomState(42)
            sample_weight = rng.uniform(0.1, 1.0, size=X.shape[0])
            
            self.scaler.fit(X, sample_weight=sample_weight)
            logger.info(f"Fitted {self.feature_scaling} scaler with random sample weights")

    def fit_pca(self, X: np.ndarray, n_components: float = 0.95) -> None:
        """Fit PCA to reduce dimensionality while preserving variance."""
        self.pca = PCA(n_components=n_components)
        self.pca.fit(X)
        logger.info(f"Fitted PCA: {self.pca.n_components_} components explain {n_components*100}% variance")

    def transform_pca(self, X: np.ndarray) -> np.ndarray:
        """Transform features using fitted PCA."""
        if self.pca is not None:
            return self.pca.transform(X)
        return X
    
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

        # Generate feature names based on the actual input shape
        # If we have base feature names and the input shape matches expected expansion, use them
        if hasattr(self, 'feature_names') and len(self.feature_names) > 0:
            base_count = len(self.feature_names)
            expected_expanded_count = base_count * 3  # base + mean + std

            if X.shape[1] == expected_expanded_count:
                # We have time series features but no interactions (this is the standard case)
                base_names = self.feature_names
                ts_mean_names = [f"{name}_mean" for name in base_names]
                ts_std_names = [f"{name}_std" for name in base_names]
                extended_feature_names = base_names + ts_mean_names + ts_std_names
            elif X.shape[1] > expected_expanded_count:
                # We have both time series and interaction features
                base_names = self.feature_names
                ts_mean_names = [f"{name}_mean" for name in base_names]
                ts_std_names = [f"{name}_std" for name in base_names]

                # Add interaction feature names
                interaction_names = []
                key_features_indices = list(range(min(5, len(base_names))))
                for i in key_features_indices:
                    for j in range(i, len(key_features_indices)):
                        if i == j:
                            interaction_names.append(f"{base_names[i]}_sq")
                        else:
                            interaction_names.append(f"{base_names[i]}_x_{base_names[j]}")

                extended_feature_names = base_names + ts_mean_names + ts_std_names + interaction_names
            else:
                # Fallback: use generic names if we can't determine the structure
                extended_feature_names = [f"feature_{i}" for i in range(X.shape[1])]
        else:
            # No base feature names available, use generic names
            extended_feature_names = [f"feature_{i}" for i in range(X.shape[1])]

        # Ensure the generated names match the number of features
        if len(extended_feature_names) != X.shape[1]:
            logger.warning(f"Mismatch in feature names ({len(extended_feature_names)}) and feature count ({X.shape[1]}). Using generic names.")
            extended_feature_names = [f"feature_{i}" for i in range(X.shape[1])]

        self.feature_names = [extended_feature_names[i] for i in selected_indices]

        logger.info(f"Selected {len(self.feature_names)} most important features from {X.shape[1]} total features")

    def partial_fit(self, X: np.ndarray, y: Optional[np.ndarray] = None) -> None:
        """Incrementally fit transformers on a batch of data."""
        logger.info(f"Partial fit: input shape {X.shape}")

        # Step 1: Handle missing values
        if self.imputer is None:
            self.imputer = SimpleImputer(strategy='mean')
            self.imputer.fit(X)
            logger.info(f"Fitted imputer on shape {X.shape}")
        else:
            # For incremental learning, we need to fit on the expanded features
            # Skip refitting imputer for now to keep it stable
            pass

        X_imputed = self.imputer.transform(X)
        logger.info(f"After imputation: {X_imputed.shape}")

        # Step 2: Time series features (must be created before scaling for incremental)
        X_ts, _ = self.create_time_series_features_incremental(X_imputed, previous_window=None)
        logger.info(f"After time series: {X_ts.shape}")

        # Step 3: Interaction features (MUST be created before scaling to match main pipeline)
        # This was the missing step causing the dimension mismatch!
        X_interactions = self.create_interaction_features(X_ts)
        logger.info(f"After interactions: {X_interactions.shape}")

        # Step 4: Feature scaling (fit on expanded features for incremental)
        if self.scaler is None:
            self.scaler = StandardScaler()
            logger.info(f"Created new scaler for shape {X_interactions.shape}")

        if self.scaler is not None and hasattr(self.scaler, 'partial_fit'):
            # Use random sample weights for partial updates
            rng = np.random.RandomState(None)
            sample_weight = rng.uniform(0.1, 1.0, size=X_interactions.shape[0])

            self.scaler.partial_fit(X_interactions, sample_weight=sample_weight)
            logger.info(f"Partial fitted scaler on shape {X_interactions.shape}")
        elif self.scaler is not None:
            # If partial_fit not available, fit on the expanded features
            rng = np.random.RandomState(42)
            sample_weight = rng.uniform(0.1, 1.0, size=X_interactions.shape[0])
            self.scaler.fit(X_interactions, sample_weight=sample_weight)
            logger.info(f"Fitted scaler on expanded shape {X_interactions.shape}")

        # Step 5: PCA (incremental not fully supported for standard PCA, so we just check if it exists or fit on batch if very necessary but standard PCA doesn't partial_fit)
        # We will assume PCA is pre-fitted or we skip update. If we want to support incremental PCA update, we need IncrementalPCA.
        # For now, we skip fitting PCA in incremental mode if it's standard PCA.
        # If this is the first batch and fit=True, we should fit PCA.
        if self.pca is None:
             self.fit_pca(X_interactions if self.scaler is None else self.scaler.transform(X_interactions), n_components=0.95)
             logger.info("Fitted PCA on initial batch in incremental pipeline")

        # Step 6: Feature selection (fit on expanded features for incremental)
        # Note: SelectKBest doesn't support partial_fit well usually, but we can refit or skip.
        # We'll skip update for now to avoid dimension mismatch if PCA changed.
        pass

    
    def transform_features_selected(self, X: np.ndarray) -> np.ndarray:
        """Transform features using fitted selector."""
        if self.feature_selector is not None:
            return self.feature_selector.transform(X)
        return X
    
    def create_time_series_features(self, X: np.ndarray, window_size: int = 5, historical_data: Optional[np.ndarray] = None) -> np.ndarray:
        """Create time series features by adding rolling statistics on Log Returns for prices."""
        
        # Identify price columns to compute returns (indices of columns ending with '_log')
        # We rely on feature names if available, otherwise apply to all or heuristics
        # Since X doesn't have names here, we need to rely on the fact that we process 'mid_price_log' and 'volume_weighted_price_log'
        # which are indices 2 and 9 in _extract_features dict (Python < 3.7 dict order is insertion, >= 3.7 is preserved)
        # However, to be robust, we should calculate log returns for ALL features as 'changes' are often more stationary.
        # BUT, the prompt specifies "Price: Convert raw prices ... to Log Returns ... for time-series analysis."
        # And "Volume/Count: Apply np.log1p".
        # Let's compute rolling stats on the *input* X. Since X already contains Log Prices and Log Volumes,
        # Rolling Mean of Log Price is not Log Return.
        # We need to transform X to Returns first for price columns.
        
        # Strategy: Create a new matrix for rolling stats calculation.
        # For price-like columns (log prices), compute diff (log return).
        # For others, keep as is? Or diff them too? 
        # Usually, rolling mean/std of LEVELS (even log levels) is not scale invariant if the level shifts.
        # Rolling mean/std of CHANGES (returns) is scale invariant.
        # So I will apply diff() to ALL columns to get changes, and calculate rolling stats on CHANGES.
        # This aligns with "Scale-Invariance".
        
        # For a single prediction, use provided historical data
        if X.shape[0] == 1:
            if historical_data is not None and historical_data.size > 0:
                combined_data = np.vstack([historical_data, X])
            else:
                combined_data = X
            
            # Compute changes (diff)
            # diff[i] = data[i] - data[i-1]
            df = pd.DataFrame(combined_data)
            diff_df = df.diff().fillna(0) # First row becomes 0 or NaN
            
            # Calculate rolling statistics on the DIFF data (Returns/Changes)
            rolling_stats_df = diff_df.rolling(window=window_size, min_periods=1)
            rolling_mean = rolling_stats_df.mean().values
            rolling_std = rolling_stats_df.std().fillna(0).values
            
            # Extract the stats for the latest data point
            latest_rolling_mean = rolling_mean[-1, :].reshape(1, -1)
            latest_rolling_std = rolling_std[-1, :].reshape(1, -1)

            # Combine original features (Levels) with rolling stats of Changes
            X_enhanced = np.column_stack([X, latest_rolling_mean, latest_rolling_std])

        # For batch processing
        else:
            df = pd.DataFrame(X)
            diff_df = df.diff().fillna(0)
            
            rolling_mean = diff_df.rolling(window=window_size, min_periods=1).mean().values
            rolling_std = diff_df.rolling(window=window_size, min_periods=1).std().fillna(0).values
            
            X_enhanced = np.column_stack([X, rolling_mean, rolling_std])

        logger.info(f"Enhanced features with time series (rolling stats on changes): {X_enhanced.shape}")
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

        # Step 4: PCA (After scaling, before selection)
        if fit_transform:
            self.fit_pca(X_scaled, n_components=0.95)
        X_pca = self.transform_pca(X_scaled)

        # Step 5: Feature selection
        if fit_transform and y is not None:
            self.fit_feature_selector(X_pca, y)
        X_selected = self.transform_features_selected(X_pca)

        X_final = X_selected

        logger.info(f"Preprocessing complete: {X_final.shape} (original: {X.shape[1]}, after TS: {X_ts.shape[1]}, after interactions: {X_interactions.shape[1]}, after scaling: {X_scaled.shape[1]}, after selection: {X_selected.shape[1]})")
        return X_final, y

    def preprocess_pipeline_incremental(self, X: np.ndarray, y: Optional[np.ndarray] = None, 
                                      fit: bool = False,
                                      previous_window: Optional[np.ndarray] = None) -> Tuple[np.ndarray, Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Incremental preprocessing pipeline.
        Returns (X_processed, y_processed, next_window).
        """
        logger.info(f"Incremental pipeline: input shape {X.shape}, fit={fit}")

        # Step 1: Handle missing values
        if fit:
            self.partial_fit(X, y)
            
        if self.imputer:
            X_imputed = self.imputer.transform(X)
        else:
            X_imputed = X # Should not happen if fit called or loaded

        logger.info(f"After imputation: {X_imputed.shape}")

        # Step 2: Time series features (on unscaled data for incremental)
        # Note: For incremental learning, we create features first then scale
        X_ts, next_window = self.create_time_series_features_incremental(X_imputed, previous_window=previous_window)
        logger.info(f"After time series: {X_ts.shape}")

        # Step 3: Interaction features (on unscaled data for incremental)
        # MUST create interactions BEFORE scaling to match main pipeline
        X_interactions = self.create_interaction_features(X_ts)
        logger.info(f"After interactions: {X_interactions.shape}")

        # Step 4: Feature scaling (AFTER creating interactions to match main pipeline)
        # This ensures we have the same feature expansion as the main training pipeline
        if self.scaler:
            X_scaled = self.scaler.transform(X_interactions)
            logger.info(f"After scaling: {X_scaled.shape}")
        else:
            X_scaled = X_interactions
            logger.info(f"No scaler available, using unscaled: {X_scaled.shape}")

        # Step 5: PCA
        X_pca = self.transform_pca(X_scaled)
        logger.info(f"After PCA: {X_pca.shape}")

        # Step 6: Feature selection
        if self.feature_selector:
            X_selected = self.feature_selector.transform(X_pca)
            logger.info(f"After selection: {X_selected.shape}")
        else:
            X_selected = X_pca
            logger.info(f"Feature selection disabled during online/incremental training: {X_selected.shape}")

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
        if self.pca:
            joblib.dump(self.pca, os.path.join(directory, 'pca.pkl'))
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
        pca_path = os.path.join(directory, 'pca.pkl')
        if os.path.exists(pca_path):
            self.pca = joblib.load(pca_path)
        selector_path = os.path.join(directory, 'feature_selector.pkl')
        if os.path.exists(selector_path):
            self.feature_selector = joblib.load(selector_path)
            
        logger.info(f"Loaded transformers from {directory}")
