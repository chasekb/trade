"""ML Trading Dashboard Integration."""

import logging
import requests
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


import os

class MLDashboardIntegration:
    """Integration between ML system and web dashboard."""
    
    def __init__(self, ml_server_url: str = None):
        """
        Initialize ML dashboard integration.
        
        Args:
            ml_server_url: URL of the ML model server (fallback for external ML server)
        """
        if ml_server_url is None:
            ml_server_url = os.getenv("ML_SERVER_URL", "http://localhost:8002")
        self.ml_server_url = ml_server_url
        self.ml_optimizer = None
    
    def set_ml_optimizer(self, ml_optimizer):
        """Set the ML optimizer instance."""
        self.ml_optimizer = ml_optimizer
        
    def get_ml_status(self) -> Dict[str, Any]:
        """Get ML system status for dashboard."""
        try:
            # Try to use local ML optimizer first
            if self.ml_optimizer:
                return self.ml_optimizer.get_system_status()
            
            # Fallback to HTTP request to external ML server
            response = requests.get(f"{self.ml_server_url}/status", timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    'is_trained': False,
                    'error': f'ML server returned status {response.status_code}'
                }
        except Exception as e:
            logger.error(f"Error getting ML status: {e}")
            return {
                'is_trained': False,
                'error': str(e)
            }
    
    def get_ml_performance(self) -> Dict[str, Any]:
        """Get ML model performance metrics."""
        try:
            # Try to use local ML optimizer first
            if self.ml_optimizer:
                return self.ml_optimizer.get_model_performance()
            
            # Fallback to HTTP request to external ML server
            response = requests.get(f"{self.ml_server_url}/performance", timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                return {'error': f'ML server returned status {response.status_code}'}
        except Exception as e:
            logger.error(f"Error getting ML performance: {e}")
            return {'error': str(e)}
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance scores."""
        try:
            # Try to use local ML optimizer first
            if self.ml_optimizer:
                return self.ml_optimizer.get_feature_importance()
            
            # Fallback to HTTP request to external ML server
            response = requests.get(f"{self.ml_server_url}/features/importance", timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                return {}
        except Exception as e:
            logger.error(f"Error getting feature importance: {e}")
            return {}
    
    def trigger_model_training(self) -> Dict[str, Any]:
        """Trigger model training."""
        try:
            # Try to use local ML optimizer first
            if self.ml_optimizer:
                # Collect and preprocess data
                features, outcomes = self.ml_optimizer.collect_and_preprocess_data(days_back=30)
                if not features or not outcomes:
                    return {'error': 'Insufficient training data'}
                
                # Train models
                training_results = self.ml_optimizer.train_ml_models(features, outcomes)
                return {
                    'status': 'success',
                    'training_results': training_results,
                    'timestamp': datetime.now().isoformat()
                }
            
            # Fallback to HTTP request to external ML server
            response = requests.post(f"{self.ml_server_url}/train", timeout=60)
            if response.status_code == 200:
                return response.json()
            else:
                return {'error': f'Training failed with status {response.status_code}'}
        except Exception as e:
            logger.error(f"Error triggering model training: {e}")
            return {'error': str(e)}
    
    def trigger_model_update(self) -> Dict[str, Any]:
        """Trigger model update with new data."""
        try:
            # Try to use local ML optimizer first
            if self.ml_optimizer:
                # Collect recent data
                features, outcomes = self.ml_optimizer.collect_and_preprocess_data(days_back=7)
                if not features or not outcomes:
                    return {'error': 'No new data available'}
                
                # Update model
                success = self.ml_optimizer.update_model_with_new_data(features, outcomes)
                if success:
                    return {
                        'status': 'success',
                        'message': 'Model updated successfully',
                        'timestamp': datetime.now().isoformat()
                    }
                else:
                    return {'error': 'Model update failed'}
            
            # Fallback to HTTP request to external ML server
            response = requests.post(f"{self.ml_server_url}/update", timeout=30)
            if response.status_code == 200:
                return response.json()
            else:
                return {'error': f'Update failed with status {response.status_code}'}
        except Exception as e:
            logger.error(f"Error triggering model update: {e}")
            return {'error': str(e)}
    
    def rollback_model(self) -> Dict[str, Any]:
        """Rollback to previous model version."""
        try:
            # Try to use local ML optimizer first
            if self.ml_optimizer:
                success = self.ml_optimizer.rollback_model()
                if success:
                    return {
                        'status': 'success',
                        'message': 'Model rolled back successfully',
                        'timestamp': datetime.now().isoformat()
                    }
                else:
                    return {'error': 'Model rollback failed'}
            
            # Fallback to HTTP request to external ML server
            response = requests.post(f"{self.ml_server_url}/rollback", timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                return {'error': f'Rollback failed with status {response.status_code}'}
        except Exception as e:
            logger.error(f"Error rolling back model: {e}")
            return {'error': str(e)}
            
    def get_pnl_tracking_data(self, sort_by: str = 'pnl') -> Dict[str, Any]:
        """Get PnL tracking data for dashboard."""
        try:
            if self.ml_optimizer:
                return self.ml_optimizer.get_top_pnl_trades(sort_by=sort_by)
            else:
                return {'error': 'ML optimizer not available'}
        except Exception as e:
            logger.error(f"Error getting PnL tracking data: {e}")
            return {'error': str(e)}

    def list_available_models(self) -> Dict[str, Any]:
        """List available models for dashboard."""
        try:
            if self.ml_optimizer:
                return {"models": self.ml_optimizer.list_available_models()}
            else:
                return {'error': 'ML optimizer not available'}
        except Exception as e:
            logger.error(f"Error listing available models: {e}")
            return {'error': str(e)}

    def set_active_model(self, model_name: str) -> Dict[str, Any]:
        """Set the active model for predictions."""
        try:
            if self.ml_optimizer:
                success = self.ml_optimizer.set_active_model(model_name)
                if success:
                    return {'status': 'success', 'message': f'Model {model_name} activated'}
                else:
                    return {'error': f'Failed to activate model {model_name}'}
            else:
                return {'error': 'ML optimizer not available'}
        except Exception as e:
            logger.error(f"Error setting active model: {e}")
            return {'error': str(e)}

    def get_prediction_comparison(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Get prediction comparison from all models."""
        try:
            if self.ml_optimizer:
                # The features are passed in as a dictionary, so we need to convert them to an OrderBookFeatures object
                from ..ml.data_collector import OrderBookFeatures
                feature_obj = OrderBookFeatures(**features)
                return self.ml_optimizer.get_prediction_comparison(feature_obj)
            else:
                return {'error': 'ML optimizer not available'}
        except Exception as e:
            logger.error(f"Error getting prediction comparison: {e}")
            return {'error': str(e)}
    
    def get_ml_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive ML data for dashboard."""
        try:
            # Get all ML data
            status = self.get_ml_status()
            performance = self.get_ml_performance()
            feature_importance = self.get_feature_importance()
            
            # Combine data
            dashboard_data = {
                'status': status,
                'performance': performance,
                'feature_importance': feature_importance,
                'timestamp': datetime.now().isoformat(),
                'ml_server_url': self.ml_server_url
            }
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Error getting ML dashboard data: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
