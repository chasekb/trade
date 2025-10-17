"""ML Trading Dashboard Integration."""

import logging
import requests
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class MLDashboardIntegration:
    """Integration between ML system and web dashboard."""
    
    def __init__(self, ml_server_url: str = "http://localhost:8002"):
        """
        Initialize ML dashboard integration.
        
        Args:
            ml_server_url: URL of the ML model server
        """
        self.ml_server_url = ml_server_url
        
    def get_ml_status(self) -> Dict[str, Any]:
        """Get ML system status for dashboard."""
        try:
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
            response = requests.post(f"{self.ml_server_url}/rollback", timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                return {'error': f'Rollback failed with status {response.status_code}'}
        except Exception as e:
            logger.error(f"Error rolling back model: {e}")
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
