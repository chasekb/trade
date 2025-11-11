from typing import List
"""Model Manager for ML model versioning and deployment."""

import logging
import os
import json
import shutil
from typing import Dict, List, Any, Optional
from datetime import datetime
import joblib
import numpy as np

logger = logging.getLogger(__name__)


class ModelManager:
    """Manages ML model versions, deployment, and rollback."""
    
    def __init__(self, models_dir: str = "data/models"):
        """
        Initialize model manager.
        
        Args:
            models_dir: Directory to store model files
        """
        self.models_dir = models_dir
        self.current_model = None
        self.model_versions = {}
        self.performance_history = {}
        
        # Create models directory if it doesn't exist
        os.makedirs(models_dir, exist_ok=True)
        
        # Load existing model information
        self.load_model_registry()
    
    def register_model(self, model_name: str, model_path: str, 
                      performance_metrics: Dict[str, Any],
                      metadata: Dict[str, Any] = None) -> str:
        """Register a new model version."""
        try:
            # Generate version ID
            version_id = self._generate_version_id()
            
            # Create version directory
            version_dir = os.path.join(self.models_dir, model_name, version_id)
            os.makedirs(version_dir, exist_ok=True)
            
            # Copy model file
            model_filename = f"{model_name}_{version_id}.pkl"
            model_filepath = os.path.join(version_dir, model_filename)
            shutil.copy2(model_path, model_filepath)
            
            # Save metadata
            model_metadata = {
                'version_id': version_id,
                'model_name': model_name,
                'model_path': model_filepath,
                'performance_metrics': performance_metrics,
                'metadata': metadata or {},
                'created_at': datetime.now().isoformat(),
                'status': 'registered'
            }
            
            metadata_filepath = os.path.join(version_dir, 'metadata.json')
            with open(metadata_filepath, 'w') as f:
                json.dump(model_metadata, f, indent=2)
            
            # Update registry
            if model_name not in self.model_versions:
                self.model_versions[model_name] = []
            
            self.model_versions[model_name].append(model_metadata)
            
            # Save registry
            self._save_model_registry()
            
            logger.info(f"Registered model {model_name} version {version_id}")
            return version_id
            
        except Exception as e:
            logger.error(f"Error registering model: {e}")
            return None
    
    def set_active_model(self, model_name: str) -> bool:
        """Set the active model by name, supporting versioned models."""
        try:
            if ':' in model_name:
                name, version_id = model_name.split(':', 1)
                logger.info(f"Setting active model to {name} version {version_id}")
                return self.deploy_model(name, version_id)
            else:
                logger.warning(f"Setting active model using fallback for non-versioned model: {model_name}")
                # Fallback for non-versioned models - this path may be deprecated
                model_path = os.path.join(self.models_dir, f"{model_name}.pkl")

                if not os.path.exists(model_path):
                    logger.error(f"Model file not found for {model_name} at {model_path}")
                    return False

                # Load the model
                model = joblib.load(model_path)

                # Set as current model
                self.current_model = {
                    'model': model,
                    'model_name': model_name,
                    'deployed_at': datetime.now().isoformat(),
                }
                logger.info(f"Set active model to {model_name}")
                return True
        except Exception as e:
            logger.error(f"Error setting active model: {e}")
            return False

    def deploy_model(self, model_name: str, version_id: str = None) -> bool:
        """Deploy a model version as the current model."""
        try:
            if version_id is None:
                # Deploy the latest version
                if model_name not in self.model_versions:
                    logger.error(f"No versions found for model {model_name}")
                    return False
                
                version_id = self.model_versions[model_name][-1]['version_id']
            
            # Find the model version
            model_version = self._find_model_version(model_name, version_id)
            if not model_version:
                logger.error(f"Model version {model_name}:{version_id} not found")
                return False
            
            # Load the model
            model = joblib.load(model_version['model_path'])
            
            # Set as current model
            self.current_model = {
                'model': model,
                'version_id': version_id,
                'model_name': model_name,
                'deployed_at': datetime.now().isoformat(),
                'performance_metrics': model_version['performance_metrics']
            }
            
            # Update status
            model_version['status'] = 'deployed'
            model_version['deployed_at'] = datetime.now().isoformat()
            
            # Save registry
            self._save_model_registry()
            
            logger.info(f"Deployed model {model_name} version {version_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deploying model: {e}")
            return False
    
    def rollback_model(self, model_name: str, version_id: str = None) -> bool:
        """Rollback to a previous model version."""
        try:
            if version_id is None:
                # Rollback to the previous version
                if model_name not in self.model_versions:
                    logger.error(f"No versions found for model {model_name}")
                    return False
                
                versions = self.model_versions[model_name]
                if len(versions) < 2:
                    logger.error(f"No previous version to rollback to for {model_name}")
                    return False
                
                # Find the last deployed version that's not the current one
                deployed_versions = [v for v in versions if v['status'] == 'deployed']
                if len(deployed_versions) < 2:
                    logger.error(f"No previous deployed version found for {model_name}")
                    return False
                
                version_id = deployed_versions[-2]['version_id']
            
            # Deploy the specified version
            return self.deploy_model(model_name, version_id)
            
        except Exception as e:
            logger.error(f"Error rolling back model: {e}")
            return False
    
    def get_model_performance(self, model_name: str = None) -> Dict[str, Any]:
        """Get performance metrics for models."""
        if model_name:
            if model_name not in self.model_versions:
                return {}
            
            versions = self.model_versions[model_name]
            return {
                'model_name': model_name,
                'versions': len(versions),
                'latest_performance': versions[-1]['performance_metrics'] if versions else {},
                'performance_history': [v['performance_metrics'] for v in versions]
            }
        else:
            # Return performance for all models
            performance = {}
            for name, versions in self.model_versions.items():
                performance[name] = {
                    'versions': len(versions),
                    'latest_performance': versions[-1]['performance_metrics'] if versions else {},
                    'performance_history': [v['performance_metrics'] for v in versions]
                }
            return performance
    
    def list_models(self) -> List[Dict[str, Any]]:
        """List all registered models."""
        models = []
        for model_name in os.listdir(self.models_dir):
            model_dir = os.path.join(self.models_dir, model_name)
            if os.path.isdir(model_dir):
                for version_id in os.listdir(model_dir):
                    version_dir = os.path.join(model_dir, version_id)
                    metadata_path = os.path.join(version_dir, 'metadata.json')
                    if os.path.exists(metadata_path):
                        with open(metadata_path, 'r') as f:
                            metadata = json.load(f)
                            models.append({
                                'model_id': f"{model_name}:{version_id}",
                                'model_name': model_name,
                                'version_id': version_id,
                                'trained_at': metadata.get('created_at'),
                            })
        return models
    
    def get_current_model(self) -> Optional[Dict[str, Any]]:
        """Get information about the currently deployed model."""
        return self.current_model
    
    def predict(self, X: np.ndarray) -> Optional[np.ndarray]:
        """Make predictions using the current model."""
        if self.current_model is None:
            logger.error("No model currently deployed")
            return None
        
        try:
            model = self.current_model['model']
            return model.predict(X)
        except Exception as e:
            logger.error(f"Error making prediction: {e}")
            return None
    
    def evaluate_model_performance(self, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, Any]:
        """Evaluate the current model's performance."""
        if self.current_model is None:
            logger.error("No model currently deployed")
            return {}
        
        try:
            model = self.current_model['model']
            y_pred = model.predict(X_test)
            
            # Calculate metrics
            mse = np.mean((y_test - y_pred) ** 2)
            rmse = np.sqrt(mse)
            mae = np.mean(np.abs(y_test - y_pred))
            r2 = 1 - (np.sum((y_test - y_pred) ** 2) / np.sum((y_test - np.mean(y_test)) ** 2))
            
            # Calculate trading-specific metrics
            profit_factor = self._calculate_profit_factor(y_test, y_pred)
            sharpe_ratio = self._calculate_sharpe_ratio(y_test, y_pred)
            
            performance = {
                'mse': float(mse),
                'rmse': float(rmse),
                'mae': float(mae),
                'r2': float(r2),
                'profit_factor': float(profit_factor),
                'sharpe_ratio': float(sharpe_ratio),
                'evaluation_timestamp': datetime.now().isoformat()
            }
            
            # Update performance history
            model_name = self.current_model['model_name']
            version_id = self.current_model['version_id']
            
            if model_name not in self.performance_history:
                self.performance_history[model_name] = {}
            
            self.performance_history[model_name][version_id] = performance
            
            return performance
            
        except Exception as e:
            logger.error(f"Error evaluating model performance: {e}")
            return {}
    
    def _calculate_profit_factor(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """Calculate profit factor for trading performance."""
        signals = np.sign(y_pred)
        returns = signals * y_true
        
        profits = returns[returns > 0].sum()
        losses = abs(returns[returns < 0].sum())
        
        return profits / losses if losses > 0 else float('inf')
    
    def _calculate_sharpe_ratio(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """Calculate Sharpe ratio for trading performance."""
        signals = np.sign(y_pred)
        returns = signals * y_true
        
        if len(returns) == 0 or np.std(returns) == 0:
            return 0.0
        
        return np.mean(returns) / np.std(returns) * np.sqrt(252)  # Annualized
    
    def _generate_version_id(self) -> str:
        """Generate a unique version ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"v{timestamp}"
    
    def _find_model_version(self, model_name: str, version_id: str) -> Optional[Dict[str, Any]]:
        """Find a specific model version."""
        if model_name not in self.model_versions:
            return None
        
        for version in self.model_versions[model_name]:
            if version['version_id'] == version_id:
                return version
        
        return None
    
    def load_model_registry(self) -> None:
        """Load model registry from disk."""
        registry_path = os.path.join(self.models_dir, 'model_registry.json')
        
        if os.path.exists(registry_path):
            try:
                with open(registry_path, 'r') as f:
                    registry = json.load(f)
                    self.model_versions = registry.get('model_versions', {})
                    self.performance_history = registry.get('performance_history', {})
            except Exception as e:
                logger.warning(f"Error loading model registry: {e}")
                self.model_versions = {}
                self.performance_history = {}
        else:
            self.model_versions = {}
            self.performance_history = {}
    
    def _save_model_registry(self) -> None:
        """Save model registry to disk."""
        registry_path = os.path.join(self.models_dir, 'model_registry.json')
        
        try:
            registry = {
                'model_versions': self.model_versions,
                'performance_history': self.performance_history,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(registry_path, 'w') as f:
                json.dump(registry, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving model registry: {e}")
    
    def cleanup_old_versions(self, model_name: str, keep_versions: int = 5) -> bool:
        """Clean up old model versions, keeping only the most recent ones."""
        try:
            if model_name not in self.model_versions:
                logger.warning(f"No versions found for model {model_name}")
                return True
            
            versions = self.model_versions[model_name]
            
            if len(versions) <= keep_versions:
                logger.info(f"Model {model_name} has {len(versions)} versions, no cleanup needed")
                return True
            
            # Sort by creation time and keep only the most recent
            versions.sort(key=lambda x: x['created_at'])
            versions_to_keep = versions[-keep_versions:]
            versions_to_remove = versions[:-keep_versions]
            
            # Remove old versions
            for version in versions_to_remove:
                version_dir = os.path.dirname(version['model_path'])
                if os.path.exists(version_dir):
                    shutil.rmtree(version_dir)
                    logger.info(f"Removed old version {version['version_id']}")
            
            # Update registry
            self.model_versions[model_name] = versions_to_keep
            self._save_model_registry()
            
            logger.info(f"Cleaned up {len(versions_to_remove)} old versions for {model_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error cleaning up old versions: {e}")
            return False
