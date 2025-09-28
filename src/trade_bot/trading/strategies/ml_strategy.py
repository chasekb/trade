"""ML-Enhanced Trading Strategy.

This strategy combines traditional technical analysis with machine learning
predictions for improved trade decision making.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from .base import BaseStrategy, TradeSignal
from .ml_signal import MLSignalGenerator, MLSignalResult
from ...core.config import TradingConfig

logger = logging.getLogger(__name__)


class MLStrategy(BaseStrategy):
    """Trading strategy enhanced with machine learning predictions."""
    
    def __init__(self, config: TradingConfig, name: str = "ML Strategy", **kwargs):
        super().__init__(config)
        self.name = name
        
        # ML components
        self.ml_generator = MLSignalGenerator()
        self.ml_enabled = True
        
        # Strategy parameters
        self.min_win_probability = kwargs.get('min_win_probability', 0.6)
        self.min_expected_return = kwargs.get('min_expected_return', 0.01)  # 1%
        self.min_confidence = kwargs.get('min_confidence', 0.3)
        self.max_risk_per_trade = kwargs.get('max_risk_per_trade', 0.02)  # 2%
        
        # Traditional strategy parameters
        self.rsi_oversold = kwargs.get('rsi_oversold', 30)
        self.rsi_overbought = kwargs.get('rsi_overbought', 70)
        self.ma_short = kwargs.get('ma_short', 10)
        self.ma_long = kwargs.get('ma_long', 20)
        
        # Performance tracking
        self.ml_predictions = []
        self.prediction_accuracy = 0.0
        
        logger.info(f"ML Strategy initialized with ML enabled: {self.ml_enabled}")
    
    def get_strategy_name(self) -> str:
        """Get the name of this strategy."""
        return self.name
    
    def generate_signal(self, current_price: float, timestamp: datetime) -> Optional[TradeSignal]:
        """Generate trading signal using ML predictions and traditional analysis."""
        try:
            # Get traditional technical analysis
            traditional_signal = self._get_traditional_signal(current_price)
            
            # Get ML prediction if enabled
            ml_signal = None
            if self.ml_enabled and self.ml_generator.is_trained:
                ml_signal = self._get_ml_signal(current_price, timestamp)
            
            # Combine signals
            final_signal = self._combine_signals(traditional_signal, ml_signal, current_price)
            
            # Log prediction for accuracy tracking
            if ml_signal:
                self.ml_predictions.append({
                    'timestamp': timestamp,
                    'prediction': ml_signal,
                    'price': current_price,
                    'signal': final_signal
                })
            
            # Create TradeSignal object
            return TradeSignal(
                action=final_signal,
                price=current_price,
                quantity=0.0,  # Will be calculated by trading manager
                timestamp=timestamp,
                reason=f"ML Strategy: {final_signal}"
            )
            
        except Exception as e:
            logger.error(f"Error generating ML strategy signal: {e}")
            return TradeSignal(
                action="hold",
                price=current_price,
                quantity=0.0,
                timestamp=timestamp,
                reason=f"ML Strategy Error: {str(e)}"
            )
    
    def _get_traditional_signal(self, current_price: float) -> str:
        """Get traditional technical analysis signal."""
        try:
            if len(self.price_history) < self.ma_long:
                return "hold"
            
            # Calculate technical indicators
            rsi = self._calculate_rsi(self.price_history[-14:])
            ma_short = sum(self.price_history[-self.ma_short:]) / self.ma_short
            ma_long = sum(self.price_history[-self.ma_long:]) / self.ma_long
            
            # RSI signals
            rsi_signal = "hold"
            if rsi < self.rsi_oversold:
                rsi_signal = "buy"
            elif rsi > self.rsi_overbought:
                rsi_signal = "sell"
            
            # Moving average signals
            ma_signal = "hold"
            if ma_short > ma_long and self.prices[-1] > ma_short:
                ma_signal = "buy"
            elif ma_short < ma_long and self.prices[-1] < ma_short:
                ma_signal = "sell"
            
            # Combine traditional signals
            if rsi_signal == "buy" and ma_signal == "buy":
                return "buy"
            elif rsi_signal == "sell" and ma_signal == "sell":
                return "sell"
            else:
                return "hold"
                
        except Exception as e:
            logger.error(f"Error calculating traditional signal: {e}")
            return "hold"
    
    def _get_ml_signal(self, current_price: float, timestamp: datetime) -> Optional[MLSignalResult]:
        """Get ML prediction for current market conditions."""
        try:
            # Get recent trades and order book data
            recent_trades = self._get_recent_trades()
            orderbook_data = self._get_orderbook_data()
            
            # Generate ML signal
            ml_result = self.ml_generator.generate_signal(
                trades=recent_trades,
                orderbook_data=orderbook_data,
                current_price=current_price,
                symbol=self.symbol or "BTC-USD"
            )
            
            return ml_result
            
        except Exception as e:
            logger.error(f"Error getting ML signal: {e}")
            return None
    
    def _combine_signals(self, traditional_signal: str, ml_signal: Optional[MLSignalResult], 
                        current_price: float) -> str:
        """Combine traditional and ML signals for final decision."""
        try:
            # If no ML signal, use traditional only
            if not ml_signal:
                return traditional_signal
            
            # Check ML criteria
            ml_buy_criteria = (
                ml_signal.win_probability >= self.min_win_probability and
                ml_signal.expected_return >= self.min_expected_return and
                ml_signal.confidence >= self.min_confidence
            )
            
            ml_sell_criteria = (
                ml_signal.win_probability <= (1 - self.min_win_probability) and
                ml_signal.expected_return <= -self.min_expected_return and
                ml_signal.confidence >= self.min_confidence
            )
            
            # Combine signals
            if traditional_signal == "buy" and ml_buy_criteria:
                return "buy"
            elif traditional_signal == "sell" and ml_sell_criteria:
                return "sell"
            elif traditional_signal == "hold" and (ml_buy_criteria or ml_sell_criteria):
                # ML overrides traditional hold
                return "buy" if ml_buy_criteria else "sell"
            else:
                # Traditional signal takes precedence
                return traditional_signal
                
        except Exception as e:
            logger.error(f"Error combining signals: {e}")
            return traditional_signal
    
    def _get_recent_trades(self) -> List[Dict]:
        """Get recent trades for ML analysis."""
        # This would typically come from a trade history database
        # For now, return empty list - would be populated by the trading manager
        return []
    
    def _get_orderbook_data(self) -> Dict:
        """Get current order book data for ML analysis."""
        # This would typically come from the order book handler
        # For now, return empty dict - would be populated by the trading manager
        return {}
    
    def train_ml_model(self, training_data: List[Dict]) -> bool:
        """Train the ML model on historical data."""
        try:
            success = self.ml_generator.train_model(training_data)
            if success:
                logger.info("ML model trained successfully")
            else:
                logger.warning("ML model training failed")
            return success
        except Exception as e:
            logger.error(f"Error training ML model: {e}")
            return False
    
    def update_prediction_accuracy(self, actual_pnl: float, predicted_signal: str) -> None:
        """Update prediction accuracy based on actual trade results."""
        try:
            if not self.ml_predictions:
                return
            
            # Find the most recent prediction
            recent_prediction = self.ml_predictions[-1]
            
            # Determine if prediction was correct
            predicted_correct = False
            if predicted_signal == "buy" and actual_pnl > 0:
                predicted_correct = True
            elif predicted_signal == "sell" and actual_pnl < 0:
                predicted_correct = True
            elif predicted_signal == "hold" and abs(actual_pnl) < 0.001:  # Very small P&L
                predicted_correct = True
            
            # Update accuracy (simple moving average)
            if len(self.ml_predictions) > 0:
                current_accuracy = self.prediction_accuracy
                n_predictions = len(self.ml_predictions)
                self.prediction_accuracy = ((current_accuracy * (n_predictions - 1)) + predicted_correct) / n_predictions
            
            logger.debug(f"ML prediction accuracy updated: {self.prediction_accuracy:.3f}")
            
        except Exception as e:
            logger.error(f"Error updating prediction accuracy: {e}")
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Get comprehensive strategy information."""
        base_info = super().get_strategy_info()
        
        ml_info = {
            'ml_enabled': self.ml_enabled,
            'ml_model_info': self.ml_generator.get_model_info(),
            'prediction_accuracy': self.prediction_accuracy,
            'total_predictions': len(self.ml_predictions),
            'min_win_probability': self.min_win_probability,
            'min_expected_return': self.min_expected_return,
            'min_confidence': self.min_confidence
        }
        
        return {**base_info, **ml_info}
    
    def get_detailed_signal_analysis(self, current_price: float, timestamp: datetime) -> Dict[str, Any]:
        """Get detailed analysis of signal generation."""
        try:
            # Traditional analysis
            traditional_signal = self._get_traditional_signal(current_price)
            
            # ML analysis
            ml_signal = self._get_ml_signal(current_price, timestamp)
            
            # Final signal
            final_signal = self._combine_signals(traditional_signal, ml_signal, current_price)
            
            analysis = {
                'final_signal': final_signal,
                'traditional_signal': traditional_signal,
                'ml_enabled': self.ml_enabled,
                'ml_signal': None,
                'strategy_info': self.get_strategy_info()
            }
            
            if ml_signal:
                analysis['ml_signal'] = {
                    'win_probability': ml_signal.win_probability,
                    'expected_return': ml_signal.expected_return,
                    'confidence': ml_signal.confidence,
                    'features_used': ml_signal.features_used,
                    'model_version': ml_signal.model_version
                }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error getting detailed signal analysis: {e}")
            return {
                'final_signal': 'hold',
                'error': str(e),
                'strategy_info': self.get_strategy_info()
            }
