"""ML API endpoints for web server."""

import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from datetime import datetime

from ..web_components.ml_dashboard import MLDashboardIntegration

logger = logging.getLogger(__name__)

# Create router for ML endpoints
ml_router = APIRouter(prefix="/api/ml", tags=["ml"])

# Initialize ML dashboard integration
ml_integration = MLDashboardIntegration()


@ml_router.get("/status")
async def get_ml_status():
    """Get ML system status."""
    try:
        status = ml_integration.get_ml_status()
        return status
    except Exception as e:
        logger.error(f"Error getting ML status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@ml_router.get("/performance")
async def get_ml_performance():
    """Get ML model performance metrics."""
    try:
        performance = ml_integration.get_ml_performance()
        return performance
    except Exception as e:
        logger.error(f"Error getting ML performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@ml_router.get("/features/importance")
async def get_feature_importance():
    """Get feature importance scores."""
    try:
        importance = ml_integration.get_feature_importance()
        return importance
    except Exception as e:
        logger.error(f"Error getting feature importance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@ml_router.post("/train")
async def trigger_model_training():
    """Trigger ML model training."""
    try:
        result = ml_integration.trigger_model_training()
        if 'error' in result:
            raise HTTPException(status_code=500, detail=result['error'])
        return result
    except Exception as e:
        logger.error(f"Error triggering model training: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@ml_router.post("/update")
async def trigger_model_update():
    """Trigger model update with new data."""
    try:
        result = ml_integration.trigger_model_update()
        if 'error' in result:
            raise HTTPException(status_code=500, detail=result['error'])
        return result
    except Exception as e:
        logger.error(f"Error triggering model update: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@ml_router.post("/rollback")
async def rollback_model():
    """Rollback to previous model version."""
    try:
        result = ml_integration.rollback_model()
        if 'error' in result:
            raise HTTPException(status_code=500, detail=result['error'])
        return result
    except Exception as e:
        logger.error(f"Error rolling back model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@ml_router.get("/dashboard")
async def get_ml_dashboard_data():
    """Get comprehensive ML data for dashboard."""
    try:
        dashboard_data = ml_integration.get_ml_dashboard_data()
        return dashboard_data
    except Exception as e:
        logger.error(f"Error getting ML dashboard data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@ml_router.get("/pnl-trades")
async def get_pnl_trades_data():
    """Get top and bottom trades by PnL."""
    try:
        pnl_data = ml_integration.get_pnl_tracking_data()
        return pnl_data
    except Exception as e:
        logger.error(f"Error getting PnL trades data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@ml_router.get("/models")
async def get_available_models():
    """Get a list of available ML models."""
    try:
        models = ml_integration.list_available_models()
        return models
    except Exception as e:
        logger.error(f"Error getting available models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@ml_router.post("/models/set_active")
async def set_active_model(model_name: str):
    """Set the active ML model."""
    try:
        result = ml_integration.set_active_model(model_name)
        if 'error' in result:
            raise HTTPException(status_code=400, detail=result['error'])
        return result
    except Exception as e:
        logger.error(f"Error setting active model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@ml_router.post("/prediction-comparison")
async def get_prediction_comparison(features: Dict[str, Any]):
    """Get a comparison of predictions from all models."""
    try:
        comparison = ml_integration.get_prediction_comparison(features)
        return comparison
    except Exception as e:
        logger.error(f"Error getting prediction comparison: {e}")
        raise HTTPException(status_code=500, detail=str(e))
