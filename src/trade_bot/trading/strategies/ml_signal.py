"""Machine Learning Signal for Trade Prediction.

This module implements a machine learning-based signal generator that learns
from historical trade data to predict win probability and return size.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import json
import pickle
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MLSignalResult:
    """Result of ML signal prediction."""
    win_probability: float
    expected_return: float
    confidence: float
    features_used: List[str]
    model_version: str
    prediction_timestamp: datetime


class MLSignalGenerator:
    """Machine Learning Signal Generator for Trade Prediction."""
    
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or "models/ml_trading_model.pkl"
        self.model = None
        self.feature_scaler = None
        self.feature_columns = []
        self.model_version = "1.0.0"
        self.is_trained = False
        
        # Feature engineering parameters
        self.lookback_periods = [5, 10, 20, 50]  # Different time windows for features
        self.volume_percentiles = [25, 50, 75, 90]  # Volume analysis percentiles
        
        # Load existing model if available
        self._load_model()
    
    def _load_model(self) -> None:
        """Load existing model from disk."""
        try:
            model_file = Path(self.model_path)
            if model_file.exists():
                with open(model_file, 'rb') as f:
                    model_data = pickle.load(f)
                    self.model = model_data.get('model')
                    self.feature_scaler = model_data.get('scaler')
                    self.feature_columns = model_data.get('feature_columns', [])
                    self.model_version = model_data.get('version', '1.0.0')
                    self.is_trained = True
                    logger.info(f"Loaded ML model version {self.model_version}")
            else:
                logger.info("No existing model found, will train new model")
        except Exception as e:
            logger.error(f"Error loading ML model: {e}")
            self.is_trained = False
    
    def _save_model(self) -> None:
        """Save trained model to disk."""
        try:
            model_file = Path(self.model_path)
            model_file.parent.mkdir(parents=True, exist_ok=True)
            
            model_data = {
                'model': self.model,
                'scaler': self.feature_scaler,
                'feature_columns': self.feature_columns,
                'version': self.model_version,
                'trained_at': datetime.now().isoformat()
            }
            
            with open(model_file, 'wb') as f:
                pickle.dump(model_data, f)
            
            logger.info(f"Saved ML model to {self.model_path}")
        except Exception as e:
            logger.error(f"Error saving ML model: {e}")
    
    def _extract_features(self, trades: List[Dict], orderbook_data: Dict, 
                         current_price: float, symbol: str) -> Dict[str, float]:
        """Extract features for ML prediction."""
        features = {}
        
        # Basic trade features
        if trades:
            recent_trades = trades[-50:]  # Last 50 trades
            trade_pnls = [t.get('pnl', 0) for t in recent_trades]
            trade_volumes = [t.get('quantity', 0) * t.get('price', 0) for t in recent_trades]
            
            # P&L features
            features['avg_pnl_5'] = np.mean(trade_pnls[-5:]) if len(trade_pnls) >= 5 else 0
            features['avg_pnl_10'] = np.mean(trade_pnls[-10:]) if len(trade_pnls) >= 10 else 0
            features['std_pnl_10'] = np.std(trade_pnls[-10:]) if len(trade_pnls) >= 10 else 0
            features['win_rate_10'] = sum(1 for pnl in trade_pnls[-10:] if pnl > 0) / min(10, len(trade_pnls))
            features['max_win_10'] = max(trade_pnls[-10:]) if trade_pnls else 0
            features['max_loss_10'] = min(trade_pnls[-10:]) if trade_pnls else 0
            
            # Volume features
            features['avg_volume_5'] = np.mean(trade_volumes[-5:]) if len(trade_volumes) >= 5 else 0
            features['volume_trend'] = self._calculate_trend(trade_volumes[-10:]) if len(trade_volumes) >= 10 else 0
            
            # Trade frequency
            features['trades_per_hour'] = len(recent_trades) / max(1, self._get_time_hours(recent_trades))
        else:
            # Default values for new symbols
            features.update({
                'avg_pnl_5': 0, 'avg_pnl_10': 0, 'std_pnl_10': 0,
                'win_rate_10': 0, 'max_win_10': 0, 'max_loss_10': 0,
                'avg_volume_5': 0, 'volume_trend': 0, 'trades_per_hour': 0
            })
        
        # Order book features
        if orderbook_data:
            bids = orderbook_data.get('bids', [])
            asks = orderbook_data.get('asks', [])
            
            if bids and asks:
                best_bid = float(bids[0][0]) if bids else current_price
                best_ask = float(asks[0][0]) if asks else current_price
                
                # Spread features
                spread = best_ask - best_bid
                features['spread_abs'] = spread
                features['spread_pct'] = (spread / current_price) * 100 if current_price > 0 else 0
                
                # Order book depth
                features['bid_depth'] = sum(float(bid[1]) for bid in bids[:5])
                features['ask_depth'] = sum(float(ask[1]) for ask in asks[:5])
                features['depth_imbalance'] = (features['bid_depth'] - features['ask_depth']) / max(features['bid_depth'] + features['ask_depth'], 1)
                
                # Price levels
                features['price_levels_bid'] = len(bids)
                features['price_levels_ask'] = len(asks)
            else:
                features.update({
                    'spread_abs': 0, 'spread_pct': 0, 'bid_depth': 0, 'ask_depth': 0,
                    'depth_imbalance': 0, 'price_levels_bid': 0, 'price_levels_ask': 0
                })
        else:
            features.update({
                'spread_abs': 0, 'spread_pct': 0, 'bid_depth': 0, 'ask_depth': 0,
                'depth_imbalance': 0, 'price_levels_bid': 0, 'price_levels_ask': 0
            })
        
        # Market features
        features['current_price'] = current_price
        features['symbol_volatility'] = self._calculate_volatility(trades[-20:]) if len(trades) >= 20 else 0
        
        # Time-based features
        now = datetime.now()
        features['hour_of_day'] = now.hour
        features['day_of_week'] = now.weekday()
        features['is_weekend'] = 1 if now.weekday() >= 5 else 0
        
        return features
    
    def _calculate_trend(self, values: List[float]) -> float:
        """Calculate trend slope using linear regression."""
        if len(values) < 2:
            return 0
        
        x = np.arange(len(values))
        y = np.array(values)
        
        # Simple linear regression
        n = len(x)
        slope = (n * np.sum(x * y) - np.sum(x) * np.sum(y)) / (n * np.sum(x**2) - np.sum(x)**2)
        return slope
    
    def _get_time_hours(self, trades: List[Dict]) -> float:
        """Get time span in hours for trades."""
        if len(trades) < 2:
            return 1
        
        try:
            first_time = datetime.fromisoformat(trades[0].get('timestamp', '').replace('Z', '+00:00'))
            last_time = datetime.fromisoformat(trades[-1].get('timestamp', '').replace('Z', '+00:00'))
            return (last_time - first_time).total_seconds() / 3600
        except (ValueError, TypeError, KeyError, IndexError) as e:
            logger.warning(f"Failed to calculate time range from trades: {e}")
            return 1
    
    def _calculate_volatility(self, trades: List[Dict]) -> float:
        """Calculate price volatility from recent trades."""
        if len(trades) < 2:
            return 0
        
        prices = [t.get('price', 0) for t in trades if t.get('price', 0) > 0]
        if len(prices) < 2:
            return 0
        
        returns = np.diff(np.log(prices))
        return np.std(returns) * np.sqrt(24)  # Annualized volatility
    
    def train_model(self, training_data: List[Dict]) -> bool:
        """Train the ML model on historical trade data."""
        try:
            from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
            from sklearn.preprocessing import StandardScaler
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import accuracy_score, mean_squared_error
            
            logger.info(f"Training ML model on {len(training_data)} trades")
            
            # Prepare training data
            X = []
            y_win = []
            y_return = []
            
            for trade in training_data:
                # Extract features (simplified for training)
                features = self._extract_features(
                    training_data[:training_data.index(trade) + 1],
                    {},  # No orderbook data in training
                    trade.get('price', 0),
                    trade.get('symbol', '')
                )
                
                # Prepare feature vector
                feature_vector = list(features.values())
                X.append(feature_vector)
                
                # Target variables
                pnl = trade.get('pnl', 0)
                y_win.append(1 if pnl > 0 else 0)
                y_return.append(pnl)
            
            if len(X) < 10:
                logger.warning("Insufficient training data")
                return False
            
            X = np.array(X)
            y_win = np.array(y_win)
            y_return = np.array(y_return)
            
            # Store feature columns
            self.feature_columns = list(features.keys())
            
            # Split data
            X_train, X_test, y_win_train, y_win_test = train_test_split(
                X, y_win, test_size=0.2, random_state=42
            )
            _, _, y_return_train, y_return_test = train_test_split(
                X, y_return, test_size=0.2, random_state=42
            )
            
            # Scale features
            self.feature_scaler = StandardScaler()
            X_train_scaled = self.feature_scaler.fit_transform(X_train)
            X_test_scaled = self.feature_scaler.transform(X_test)
            
            # Train win probability classifier
            win_classifier = RandomForestClassifier(n_estimators=100, random_state=42)
            win_classifier.fit(X_train_scaled, y_win_train)
            
            # Train return size regressor
            return_regressor = RandomForestRegressor(n_estimators=100, random_state=42)
            return_regressor.fit(X_train_scaled, y_return_train)
            
            # Evaluate models
            win_pred = win_classifier.predict(X_test_scaled)
            return_pred = return_regressor.predict(X_test_scaled)
            
            win_accuracy = accuracy_score(y_win_test, win_pred)
            return_mse = mean_squared_error(y_return_test, return_pred)
            
            logger.info(f"Win prediction accuracy: {win_accuracy:.3f}")
            logger.info(f"Return prediction MSE: {return_mse:.3f}")
            
            # Store models
            self.model = {
                'win_classifier': win_classifier,
                'return_regressor': return_regressor
            }
            
            self.is_trained = True
            self._save_model()
            
            return True
            
        except Exception as e:
            logger.error(f"Error training ML model: {e}")
            return False
    
    def generate_signal(self, trades: List[Dict], orderbook_data: Dict, 
                       current_price: float, symbol: str) -> MLSignalResult:
        """Generate ML-based trading signal."""
        try:
            if not self.is_trained or not self.model:
                return MLSignalResult(
                    win_probability=0.5,
                    expected_return=0.0,
                    confidence=0.0,
                    features_used=[],
                    model_version=self.model_version,
                    prediction_timestamp=datetime.now()
                )
            
            # Extract features
            features = self._extract_features(trades, orderbook_data, current_price, symbol)
            feature_vector = np.array([list(features.values())]).reshape(1, -1)
            
            # Scale features
            if self.feature_scaler:
                feature_vector = self.feature_scaler.transform(feature_vector)
            
            # Make predictions
            win_classifier = self.model['win_classifier']
            return_regressor = self.model['return_regressor']
            
            win_probability = win_classifier.predict_proba(feature_vector)[0][1]
            expected_return = return_regressor.predict(feature_vector)[0]
            
            # Calculate confidence based on feature quality
            confidence = min(1.0, len(trades) / 50.0)  # More trades = higher confidence
            
            return MLSignalResult(
                win_probability=float(win_probability),
                expected_return=float(expected_return),
                confidence=float(confidence),
                features_used=list(features.keys()),
                model_version=self.model_version,
                prediction_timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error generating ML signal: {e}")
            return MLSignalResult(
                win_probability=0.5,
                expected_return=0.0,
                confidence=0.0,
                features_used=[],
                model_version=self.model_version,
                prediction_timestamp=datetime.now()
            )
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model."""
        return {
            'is_trained': self.is_trained,
            'model_version': self.model_version,
            'feature_count': len(self.feature_columns),
            'feature_columns': self.feature_columns,
            'model_path': self.model_path
        }
