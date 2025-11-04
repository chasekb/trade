from typing import List
"""ML-Enhanced Order Book trading strategy."""

import logging
import requests
import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base import BaseStrategy, TradeSignal
from ...core.config import TradingConfig

logger = logging.getLogger(__name__)


class MLEnhancedOrderBookStrategy(BaseStrategy):
    """ML-Enhanced Order Book trading strategy using machine learning predictions."""
    
    def __init__(self, config: TradingConfig, ml_server_url: str = "http://localhost:8002",
                 fallback_to_baseline: bool = True, confidence_threshold: float = 0.6,
                 **kwargs):
        """
        Initialize ML-enhanced order book strategy.
        
        Args:
            config: Trading configuration
            ml_server_url: URL of the ML model server
            fallback_to_baseline: Whether to fall back to baseline strategy if ML fails
            confidence_threshold: Minimum confidence threshold for ML predictions
        """
        super().__init__(config)
        
        self.ml_server_url = ml_server_url
        self.fallback_to_baseline = fallback_to_baseline
        self.confidence_threshold = confidence_threshold
        
        # Initialize baseline order book strategy for fallback
        if fallback_to_baseline:
            from .orderbook import OrderBookStrategy
            self.baseline_strategy = OrderBookStrategy(config, **kwargs)
        else:
            self.baseline_strategy = None
        
        # ML prediction tracking
        self.ml_predictions = []
        self.ml_accuracy = 0.0
        self.ml_requests = 0
        self.ml_failures = 0
        
        # Order book data (same as baseline)
        self.bids = []
        self.asks = []
        self.last_order_book_time = None
        
        # Position tracking
        self.entry_price = None
        self.stop_loss_price = None
        self.take_profit_price = None
        
        # Signal tracking
        self.signals_by_type = {
            'ml_buy': 0,
            'ml_sell': 0,
            'ml_hold': 0,
            'baseline_buy': 0,
            'baseline_sell': 0,
            'ml_fallback': 0,
            'ml_error': 0
        }
        
        logger.info(f"ML-Enhanced Order Book Strategy initialized with ML server: {ml_server_url}")
    
    def add_price(self, price: float, timestamp: datetime) -> None:
        """Add a new price point to the history."""
        self.price_history.append(price)
        
        # Keep only recent data
        if len(self.price_history) > 1000:
            self.price_history = self.price_history[-1000:]
        
        # Update baseline strategy if available
        if self.baseline_strategy:
            self.baseline_strategy.add_price(price, timestamp)
    
    def update_order_book(self, bids: List[List[float]], asks: List[List[float]], timestamp: datetime) -> None:
        """Update order book data."""
        self.bids = bids
        self.asks = asks
        self.last_order_book_time = timestamp
        
        # Keep only recent data
        if len(self.bids) > 100:
            self.bids = self.bids[-100:]
        if len(self.asks) > 100:
            self.asks = self.asks[-100:]
        
        # Update baseline strategy if available
        if self.baseline_strategy:
            self.baseline_strategy.update_order_book(bids, asks, timestamp)
    
    def _get_ml_prediction(self, current_price: float, timestamp: datetime) -> Optional[Dict[str, Any]]:
        """Get ML prediction from the model server."""
        try:
            # Calculate order book features
            features = self._calculate_order_book_features(current_price)
            
            # Prepare request
            request_data = {
                "symbol": self.config.product_id,
                "bid_ask_imbalance": features['bid_ask_imbalance'],
                "spread_percent": features['spread_percent'],
                "mid_price": features['mid_price'],
                "bid_volume": features['bid_volume'],
                "ask_volume": features['ask_volume'],
                "order_book_depth": features['order_book_depth'],
                "large_bid_wall": features['large_bid_wall'],
                "large_ask_wall": features['large_ask_wall'],
                "wall_size": features['wall_size'],
                "volume_weighted_price": features['volume_weighted_price'],
                "price_momentum": features['price_momentum'],
                "volatility": features['volatility'],
                "timestamp": int(timestamp.timestamp())
            }
            
            # Make request to ML server
            response = requests.post(
                f"{self.ml_server_url}/predict",
                json=request_data,
                timeout=5
            )
            
            self.ml_requests += 1
            
            if response.status_code == 200:
                prediction = response.json()
                logger.debug(f"ML prediction: {prediction}")
                return prediction
            else:
                logger.warning(f"ML server returned status {response.status_code}: {response.text}")
                self.ml_failures += 1
                return None
                
        except Exception as e:
            logger.error(f"Error getting ML prediction: {e}")
            self.ml_failures += 1
            return None
    
    def _calculate_order_book_features(self, current_price: float) -> Dict[str, Any]:
        """Calculate order book features for ML prediction."""
        features = {
            'bid_ask_imbalance': 0.0,
            'spread_percent': 0.0,
            'mid_price': current_price,
            'bid_volume': 0.0,
            'ask_volume': 0.0,
            'order_book_depth': 0,
            'large_bid_wall': False,
            'large_ask_wall': False,
            'wall_size': 0.0,
            'volume_weighted_price': current_price,
            'price_momentum': 0.0,
            'volatility': 0.0
        }
        
        if not self.bids or not self.asks:
            return features
        
        # Calculate bid-ask imbalance
        bid_volume = sum(bid[1] for bid in self.bids[:5] if len(bid) >= 2)
        ask_volume = sum(ask[1] for ask in self.asks[:5] if len(ask) >= 2)
        
        features['bid_volume'] = bid_volume
        features['ask_volume'] = ask_volume
        
        if ask_volume > 0:
            features['bid_ask_imbalance'] = bid_volume / ask_volume
        
        # Calculate spread
        best_bid = self.bids[0][0] if len(self.bids[0]) >= 1 else 0
        best_ask = self.asks[0][0] if len(self.asks[0]) >= 1 else 0
        
        if best_bid > 0 and best_ask > 0:
            features['spread_percent'] = (best_ask - best_bid) / best_bid * 100
            features['mid_price'] = (best_bid + best_ask) / 2
        
        # Calculate order book depth
        features['order_book_depth'] = len(self.bids) + len(self.asks)
        
        # Detect large walls
        for bid in self.bids[:10]:
            if len(bid) >= 2 and bid[1] > 1000:
                features['large_bid_wall'] = True
                features['wall_size'] = max(features['wall_size'], bid[1])
                break
        
        for ask in self.asks[:10]:
            if len(ask) >= 2 and ask[1] > 1000:
                features['large_ask_wall'] = True
                features['wall_size'] = max(features['wall_size'], ask[1])
                break
        
        # Calculate volume-weighted price
        total_volume = bid_volume + ask_volume
        if total_volume > 0:
            total_value = sum(bid[0] * bid[1] for bid in self.bids[:5] if len(bid) >= 2)
            total_value += sum(ask[0] * ask[1] for ask in self.asks[:5] if len(ask) >= 2)
            features['volume_weighted_price'] = total_value / total_volume
        
        # Calculate price momentum and volatility
        if len(self.price_history) >= 2:
            recent_prices = self.price_history[-20:] if len(self.price_history) >= 20 else self.price_history
            
            # Price momentum (percentage change over recent period)
            if len(recent_prices) >= 2:
                price_change = (recent_prices[-1] - recent_prices[0]) / recent_prices[0] * 100
                features['price_momentum'] = price_change
            
            # Volatility (standard deviation of price changes)
            if len(recent_prices) >= 3:
                price_changes = [(recent_prices[i] - recent_prices[i-1]) / recent_prices[i-1] 
                               for i in range(1, len(recent_prices))]
                import numpy as np
                features['volatility'] = float(np.std(price_changes)) * 100
        
        return features
    
    def generate_signal(self, current_price: float, timestamp: datetime, is_end_of_period: bool = False) -> Optional[TradeSignal]:
        """Generate trading signal using ML predictions."""
        if not self.bids or not self.asks:
            return None
        
        # Try to get ML prediction
        ml_prediction = self._get_ml_prediction(current_price, timestamp)
        
        if ml_prediction and ml_prediction.get('confidence', 0) >= self.confidence_threshold:
            # Use ML prediction
            action = ml_prediction.get('action', 'hold')
            confidence = ml_prediction.get('confidence', 0)
            signal_value = ml_prediction.get('signal_value', 0)
            reason = ml_prediction.get('reason', 'ML prediction')
            
            # Track ML prediction
            self.ml_predictions.append({
                'timestamp': timestamp,
                'action': action,
                'confidence': confidence,
                'signal_value': signal_value,
                'price': current_price
            })
            
            if action in ['buy', 'sell']:
                self.signals_by_type[f'ml_{action}'] += 1
                
                return TradeSignal(
                    action=action,
                    price=current_price,
                    quantity=self.calculate_position_size(current_price),
                    reason=f"{reason} (ML confidence: {confidence:.2f})",
                    timestamp=timestamp
                )
            else:
                self.signals_by_type['ml_hold'] += 1
                return None
        
        elif self.fallback_to_baseline and self.baseline_strategy:
            # Fall back to baseline strategy
            self.signals_by_type['ml_fallback'] += 1
            logger.debug("Falling back to baseline order book strategy")
            
            baseline_signal = self.baseline_strategy.generate_signal(current_price, timestamp, is_end_of_period)
            
            if baseline_signal:
                # Update signal type tracking
                self.signals_by_type[f'baseline_{baseline_signal.action}'] += 1
                
                # Modify reason to indicate fallback
                baseline_signal.reason = f"Baseline fallback: {baseline_signal.reason}"
            
            return baseline_signal
        
        else:
            # ML failed and no fallback
            self.signals_by_type['ml_error'] += 1
            logger.warning("ML prediction failed and no fallback strategy available")
            return None
    
    def get_strategy_name(self) -> str:
        """Get the name of this strategy."""
        return "ML-Enhanced Order Book"
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Get strategy information and statistics."""
        # Get baseline strategy info if available
        baseline_info = {}
        if self.baseline_strategy:
            baseline_info = self.baseline_strategy.get_strategy_info()
        
        # Calculate ML accuracy (simplified)
        total_predictions = len(self.ml_predictions)
        if total_predictions > 0:
            # This is a simplified accuracy calculation
            # In practice, you'd compare predictions with actual outcomes
            self.ml_accuracy = max(0, 1 - (self.ml_failures / self.ml_requests))
        
        return {
            'strategy_name': 'ML-Enhanced Order Book',
            'ml_server_url': self.ml_server_url,
            'fallback_to_baseline': self.fallback_to_baseline,
            'confidence_threshold': self.confidence_threshold,
            'ml_stats': {
                'total_requests': self.ml_requests,
                'total_failures': self.ml_failures,
                'success_rate': 1 - (self.ml_failures / max(1, self.ml_requests)),
                'accuracy': self.ml_accuracy,
                'total_predictions': total_predictions
            },
            'signals_by_type': self.signals_by_type.copy(),
            'total_signals': sum(self.signals_by_type.values()),
            'no_signal_count': self.no_signal_count,
            'baseline_strategy': baseline_info.get('strategy_name', 'None') if baseline_info else 'None'
        }
    
    def update_ml_accuracy(self, actual_outcome: str, predicted_action: str) -> None:
        """Update ML accuracy based on actual trading outcomes."""
        # This would be called after trades are executed to track accuracy
        # Implementation depends on how you track trade outcomes
        pass
