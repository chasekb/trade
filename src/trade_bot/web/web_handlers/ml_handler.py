"""ML API endpoints for web server."""

import json
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from datetime import datetime
import os
import requests

from ...ml.ml_optimizer import MLTradingOptimizer
from ..web_components import get_app_state

logger = logging.getLogger(__name__)

# Create router for ML endpoints
ml_router = APIRouter(prefix="/api/ml", tags=["ml"])

def _get_ml_optimizer() -> MLTradingOptimizer:
    """Get the shared MLTradingOptimizer instance from the app state."""
    try:
        app_state = get_app_state()
        if app_state and app_state.ml_optimizer:
            return app_state.ml_optimizer
    except RuntimeError:
        # App state not initialized yet
        pass
    raise HTTPException(status_code=503, detail="ML service not available")


@ml_router.get("/status")
async def get_ml_status():
    """Get ML system status."""
    try:
        app_state = get_app_state()
        if not app_state or not app_state.model_manager:
            raise HTTPException(status_code=503, detail="Model manager not available")

        model_manager = app_state.model_manager
        current_model_info = model_manager.get_current_model_info()
        
        is_trained = current_model_info is not None
        
        status = {
            "is_trained": is_trained,
            "current_model": current_model_info,
            "last_training_time": app_state.training_manager.async_trainer.last_training_time if app_state.training_manager else None,
            "is_training": app_state.training_manager.async_trainer.is_running if app_state.training_manager else False
        }
        return status
    except Exception as e:
        logger.error(f"Error getting ML status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@ml_router.get("/performance")
async def get_ml_performance():
    """Get ML model performance metrics."""
    try:
        optimizer = _get_ml_optimizer()
        return optimizer.get_model_performance()
    except Exception as e:
        logger.error(f"Error getting ML performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@ml_router.get("/features/importance")
async def get_feature_importance():
    """Get feature importance scores."""
    try:
        optimizer = _get_ml_optimizer()
        return optimizer.get_feature_importance()
    except Exception as e:
        logger.error(f"Error getting feature importance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@ml_router.post("/train")
async def trigger_model_training():
    """Trigger ML model training asynchronously."""
    try:
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        import functools

        optimizer = _get_ml_optimizer()

        # Run training in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor(max_workers=1)
        loop.run_in_executor(executor, train_model_background, optimizer)

        return {"status": "training_started", "message": "Model training started in background"}
    except Exception as e:
        logger.error(f"Error starting model training: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def train_model_background(optimizer):
    """Background task to train ML model."""
    try:
        logger.info("Starting background ML model training")
        features, outcomes = optimizer.collect_and_preprocess_data(days_back=30)
        if not features or not outcomes:
            logger.error("Insufficient data for training")
            return

        result = optimizer.train_ml_models(features, outcomes)
        logger.info(f"Background ML training completed: {result}")
    except Exception as e:
        logger.error(f"Error in background ML training: {e}")

@ml_router.get("/train/status")
async def get_training_status():
    """Get ML training status."""
    try:
        optimizer = _get_ml_optimizer()
        # For now, just return if a model is trained
        # In a production system, you'd track training progress
        is_trained = optimizer.is_trained
        return {
            "is_training": False,  # We don't track ongoing training status yet
            "is_trained": is_trained,
            "last_training_time": optimizer.last_training_time.isoformat() if optimizer.last_training_time else None
        }
    except Exception as e:
        logger.error(f"Error getting training status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@ml_router.post("/rollback")
async def rollback_model():
    """Rollback to previous model version."""
    try:
        optimizer = _get_ml_optimizer()
        success = optimizer.rollback_model()
        if not success:
            raise HTTPException(status_code=500, detail="Model rollback failed")
        return {"status": "success", "message": "Model rolled back successfully"}
    except Exception as e:
        logger.error(f"Error rolling back model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@ml_router.get("/dashboard")
async def get_ml_dashboard_data():
    """Get comprehensive ML data for dashboard."""
    try:
        optimizer = _get_ml_optimizer()
        status = optimizer.get_system_status()
        
        # Get performance and feature importance
        performance = status.get('model_performance', {})
        feature_importance = optimizer.get_feature_importance()

        # Flatten performance metrics for frontend
        flat_performance = {}
        
        # Handle nested structure (regressor/classifier) if present
        if 'latest_performance' in performance:
            # It's from model manager history
            perf_data = performance['latest_performance']
        else:
            # It's direct from current model
            perf_data = performance

        # Extract regressor metrics
        if 'regressor' in perf_data:
            flat_performance.update(perf_data['regressor'])
        else:
            # Maybe it's already flat or just regressor
            flat_performance.update(perf_data)
            
        # Extract classifier metrics and map to win_rate
        if 'classifier' in perf_data:
            classifier_metrics = perf_data['classifier']
            if 'accuracy' in classifier_metrics:
                flat_performance['win_rate'] = classifier_metrics['accuracy']
            # Add other classifier metrics if needed
            flat_performance.update({k: v for k, v in classifier_metrics.items() if k not in flat_performance})
            
        return {
            'status': status,
            'performance': flat_performance,
            'feature_importance': feature_importance,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting ML dashboard data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@ml_router.get("/pnl-trades")
async def get_pnl_trades_data(sort_by: str = 'pnl'):
    """Get top and bottom trades by PnL."""
    try:
        optimizer = _get_ml_optimizer()
        return optimizer.get_top_pnl_trades(sort_by=sort_by)
    except Exception as e:
        logger.error(f"Error getting PnL trades data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@ml_router.get("/models")
async def get_available_models():
    """Get a list of available ML models."""
    try:
        optimizer = _get_ml_optimizer()
        return optimizer.list_available_models()
    except Exception as e:
        logger.error(f"Error getting available models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@ml_router.get("/config")
async def get_ml_config():
    """Get the ML configuration."""
    try:
        app_state = get_app_state()
        if not app_state or not app_state.training_manager:
            raise HTTPException(status_code=503, detail="Training manager not available")
        return app_state.training_manager.config
    except Exception as e:
        logger.error(f"Error getting ML config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@ml_router.post("/config")
async def update_ml_config(new_config: Dict[str, Any]):
    """Update the ML configuration."""
    try:
        app_state = get_app_state()
        if not app_state or not app_state.training_manager:
            raise HTTPException(status_code=503, detail="Training manager not available")
        
        training_manager = app_state.training_manager
        training_manager.update_config(new_config)
        
        return {"status": "success", "message": "ML configuration updated successfully"}
    except Exception as e:
        logger.error(f"Error updating ML config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@ml_router.post("/models/set_active")
async def set_active_model(model_name: str):
    """Set the active ML model."""
    try:
        optimizer = _get_ml_optimizer()
        success = optimizer.set_active_model(model_name)
        if not success:
            raise HTTPException(status_code=400, detail=f"Failed to set active model: {model_name}")

        # Persist the active model choice
        try:
            with open("data/ml_config.json", "w") as f:
                json.dump({"active_model": model_name}, f)
        except Exception as e:
            logger.error(f"Error saving active model to config: {e}")
            # Don't fail the request, but log the error

        # Notify ML Server to update its active model
        try:
            ml_server_host = os.getenv("ML_SERVER_HOST", "ml-server") # Default to service name in docker
            ml_server_port = os.getenv("ML_SERVER_PORT", "8002")
            url = f"http://{ml_server_host}:{ml_server_port}/set_active"
            
            # Use params for query parameters in FastAPI
            response = requests.post(url, params={"model_name": model_name}, timeout=5)
            
            if response.status_code == 200:
                logger.info(f"Successfully notified ML server to set active model to {model_name}")
            else:
                logger.warning(f"ML server returned status {response.status_code} when setting active model")
                
        except Exception as e:
            logger.warning(f"Failed to notify ML server: {e}")

        return {"status": "success", "message": f"Active model set to {model_name}"}
    except Exception as e:
        logger.error(f"Error setting active model: {e}")
        raise HTTPException(status_code=500, detail=str(e))
