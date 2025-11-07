"""Feature Engineering for ML trading models."""

import logging
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.feature_selection import SelectKBest, f_regression
from sklearn.impute import SimpleImputer

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
                feature_vector = self._extract_features(features)
                features_list.append(feature_vector)
                
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
        
        # Generate feature names
        feature_names = self._generate_feature_names()
        
        logger.info(f"Created feature matrix: {X.shape[0]} samples, {X.shape[1]} features")
        return X, y, feature_names
    
    def _extract_features(self, features: Any) -> List[float]:
        """Extract numerical features from feature vector."""
        feature_list = []
        
        # Basic order book features
        feature_list.extend([
            features.bid_ask_imbalance,
            features.spread_percent,
            features.mid_price,
            features.bid_volume,
            features.ask_volume,
            features.order_book_depth,
            float(features.large_bid_wall),
            float(features.large_ask_wall),
            features.wall_size,
            features.volume_weighted_price,
            features.price_momentum,
            features.volatility
        ])
        
        # Derived features
        feature_list.extend([
            # Volume ratio
            features.bid_volume / (features.ask_volume + 1e-8),
            # Spread normalized by price
            features.spread_percent / (features.mid_price + 1e-8),
            # Wall size normalized by volume
            features.wall_size / (features.bid_volume + features.ask_volume + 1e-8),
            # Price momentum normalized
            features.price_momentum / (features.volatility + 1e-8),
            # Order book depth normalized
            features.order_book_depth / 100.0,  # Assuming max depth of 100
        ])
        
        # Technical indicators (simplified)
        feature_list.extend([
            # RSI-like momentum indicator
            self._calculate_rsi_like(features.price_momentum),
            # Bollinger-like volatility bands
            self._calculate_volatility_bands(features.volatility),
            # MACD-like trend indicator
            self._calculate_trend_indicator(features.price_momentum, features.volatility),
        ])
        
        return feature_list
    
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
    
    def _generate_feature_names(self) -> List[str]:
        """Generate feature names for interpretability."""
        base_features = [
            'bid_ask_imbalance',
            'spread_percent', 
            'mid_price',
            'bid_volume',
            'ask_volume',
            'order_book_depth',
            'large_bid_wall',
            'large_ask_wall',
            'wall_size',
            'volume_weighted_price',
            'price_momentum',
            'volatility'
        ]
        
        derived_features = [
            'volume_ratio',
            'spread_normalized',
            'wall_size_normalized',
            'momentum_normalized',
            'depth_normalized'
        ]
        
        technical_features = [
            'rsi_like',
            'volatility_bands',
            'trend_indicator'
        ]
        
        return base_features + derived_features + technical_features
    
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
    
    def fit_feature_selector(self, X: np.ndarray, y: np.ndarray, k: int = 20) -> None:
        """Fit feature selector to choose most important features."""
        self.feature_selector = SelectKBest(score_func=f_regression, k=k)
        self.feature_selector.fit(X, y)
        
        # Update feature names to selected features
        selected_indices = self.feature_selector.get_support(indices=True)
        self.feature_names = [self._generate_feature_names()[i] for i in selected_indices]
        
        logger.info(f"Selected {len(selected_indices)} most important features")
    
    def transform_features_selected(self, X: np.ndarray) -> np.ndarray:
        """Transform features using fitted selector."""
        if self.feature_selector is not None:
            return self.feature_selector.transform(X)
        return X
    
    def create_time_series_features(self, X: np.ndarray, window_size: int = 5) -> np.ndarray:
        """Create time series features by adding rolling statistics."""
        if X.shape[0] < window_size:
            return X
        
        # Calculate rolling statistics
        rolling_mean = pd.DataFrame(X).rolling(window=window_size, min_periods=1).mean().values
        rolling_std = pd.DataFrame(X).rolling(window=window_size, min_periods=1).std().values
        
        # Combine original features with rolling statistics
        X_enhanced = np.column_stack([
            X,
            rolling_mean,
            rolling_std
        ])
        
        logger.info(f"Enhanced features with time series: {X_enhanced.shape}")
        return X_enhanced
    
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
        if self.feature_selector is None:
            return {}
        
        scores = self.feature_selector.scores_
        feature_names = self._generate_feature_names()
        
        importance_dict = {}
        for i, score in enumerate(scores):
            if i < len(feature_names):
                importance_dict[feature_names[i]] = float(score)
        
        return importance_dict
    
    def preprocess_pipeline(self, X: np.ndarray, y: np.ndarray, 
                          fit_transform: bool = True) -> Tuple[np.ndarray, np.ndarray]:
        """Complete preprocessing pipeline."""
        logger.info("Starting preprocessing pipeline")
        
        # Step 1: Handle missing values
        if fit_transform:
            self.imputer = SimpleImputer(strategy='mean')
            X_imputed = self.imputer.fit_transform(X)
        else:
            X_imputed = self.imputer.transform(X)

        # Step 2: Feature scaling
        if fit_transform:
            self.fit_scaler(X_imputed)
        X_scaled = self.transform_features(X_imputed)
        
        # Step 3: Feature selection
        if fit_transform:
            self.fit_feature_selector(X_scaled, y)
        X_selected = self.transform_features_selected(X_scaled)
        
        # Step 4: Time series features
        X_ts = self.create_time_series_features(X_selected)
        
        # Step 5: Interaction features
        X_final = self.create_interaction_features(X_ts)
        
        logger.info(f"Preprocessing complete: {X_final.shape}")
        return X_final, y
