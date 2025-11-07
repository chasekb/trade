"""ML Model Server for real-time inference."""

import logging
import os
import json
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import numpy as np

from ml_optimizer import MLTradingOptimizer

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="ML Trading Model Server", version="1.0.0")

# Global ML optimizer instance
ml_optimizer = None
training_status: str = "idle"  # "idle", "training", "success", "failed"

# Request/Response models
class PredictionRequest(BaseModel):
    symbol: str
    bid_ask_imbalance: float
    spread_percent: float
    mid_price: float
    bid_volume: float
    ask_volume: float
    order_book_depth: int
    large_bid_wall: bool
    large_ask_wall: bool
    wall_size: float
    volume_weighted_price: float
    price_momentum: float
    volatility: float
    timestamp: int

class PredictionResponse(BaseModel):
    action: str
    confidence: float
    signal_value: float
    reason: str
    similar_conditions: int
    timestamp: str

class ModelStatusResponse(BaseModel):
    is_trained: bool
    last_training_time: Optional[str]
    current_model: Optional[Dict[str, Any]]
    model_performance: Dict[str, Any]
    vector_db_status: Optional[Dict[str, Any]]

@app.on_event("startup")
async def startup_event():
    """Initialize ML optimizer on startup."""
    global ml_optimizer
    
    try:
        logger.info("Initializing ML Trading Optimizer")
        
        # Initialize ML optimizer
        ml_optimizer = MLTradingOptimizer(
            db_url=os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/trading_db"),
            models_dir=os.getenv("MODELS_DIR", "data/models"),
            vector_db_host=os.getenv("QDRANT_HOST", "localhost"),
            vector_db_port=int(os.getenv("QDRANT_PORT", "6333"))
        )
        
        # Initialize vector database
        if not ml_optimizer.initialize_vector_database():
            logger.warning("Failed to initialize vector database")
        
        # Try to load existing model
        models = ml_optimizer.model_manager.list_models()
        if models:
            latest_model = models[0]  # Assuming first is latest
            ml_optimizer.model_manager.deploy_model("trading_optimizer")
            ml_optimizer.is_trained = True
            logger.info("Loaded existing trained model")
        else:
            logger.info("No existing model found, will train on first request")
        
        logger.info("ML Trading Optimizer initialized successfully")
        
    except Exception as e:
        logger.error(f"Error initializing ML optimizer: {e}")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/predict", response_model=PredictionResponse)
async def predict_trading_signal(request: PredictionRequest):
    """Predict optimal trading signal."""
    global ml_optimizer

    if ml_optimizer is None:
        raise HTTPException(status_code=503, detail="ML optimizer not initialized")

    try:
        # Convert request to OrderBookFeatures
        from data_collector import OrderBookFeatures

        features = OrderBookFeatures(
            timestamp=request.timestamp,
            symbol=request.symbol,
            bid_ask_imbalance=request.bid_ask_imbalance,
            spread_percent=request.spread_percent,
            mid_price=request.mid_price,
            bid_volume=request.bid_volume,
            ask_volume=request.ask_volume,
            order_book_depth=request.order_book_depth,
            large_bid_wall=request.large_bid_wall,
            large_ask_wall=request.large_ask_wall,
            wall_size=request.wall_size,
            volume_weighted_price=request.volume_weighted_price,
            price_momentum=request.price_momentum,
            volatility=request.volatility
        )

        # Check if model is trained, if not, try to train one
        if not ml_optimizer.is_trained:
            logger.info("No trained model available, attempting to train a model...")
            try:
                # Collect and train a model
                features_data, outcomes = ml_optimizer.collect_and_preprocess_data(days_back=30)
                if features_data and outcomes:
                    training_results = ml_optimizer.train_ml_models(features_data, outcomes)
                    if training_results and ml_optimizer.is_trained:
                        logger.info("Model trained successfully")
                    else:
                        logger.warning("Failed to train model, returning hold signal")
                        return PredictionResponse(
                            action="hold",
                            confidence=0.0,
                            signal_value=0.0,
                            reason="No training data available",
                            similar_conditions=0,
                            timestamp=datetime.now().isoformat()
                        )
                else:
                    logger.warning("No training data available, returning hold signal")
                    return PredictionResponse(
                        action="hold",
                        confidence=0.0,
                        signal_value=0.0,
                        reason="No training data available",
                        similar_conditions=0,
                        timestamp=datetime.now().isoformat()
                    )
            except Exception as train_error:
                logger.error(f"Error training model: {train_error}")
                return PredictionResponse(
                    action="hold",
                    confidence=0.0,
                    signal_value=0.0,
                    reason=f"Model training failed: {str(train_error)}",
                    similar_conditions=0,
                    timestamp=datetime.now().isoformat()
                )

        # Get prediction
        prediction = ml_optimizer.predict_trading_signal(features)

        # Ensure all required fields are present
        complete_prediction = {
            'action': prediction.get('action', 'hold'),
            'confidence': prediction.get('confidence', 0.0),
            'signal_value': prediction.get('signal_value', 0.0),
            'reason': prediction.get('reason', 'ML prediction'),
            'similar_conditions': prediction.get('similar_conditions', 0),
            'timestamp': prediction.get('timestamp', datetime.now().isoformat())
        }

        return PredictionResponse(**complete_prediction)

    except Exception as e:
        logger.error(f"Error making prediction: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def train_model_background():
    """Train model in the background."""
    global ml_optimizer, training_status
    
    logger.info("Starting background model training")
    training_status = "training"
    
    try:
        features, outcomes = ml_optimizer.collect_and_preprocess_data(days_back=30)
        
        if not features or not outcomes:
            logger.warning("Insufficient training data available for background training")
            training_status = "failed"
            return

        training_results = ml_optimizer.train_ml_models(features, outcomes)
        
        if training_results and training_results.get('model_performance'):
            ml_optimizer.is_trained = True
            ml_optimizer.last_training_time = datetime.now()
            training_status = "success"
            logger.info("Background model training completed successfully")
        else:
            training_status = "failed"
            logger.warning("Background model training failed")
            
    except Exception as e:
        logger.error(f"Error during background model training: {e}")
        training_status = "failed"


@app.get("/status", response_model=ModelStatusResponse)
async def get_model_status(background_tasks: BackgroundTasks):
    """Get current model status."""
    global ml_optimizer, training_status
    
    if ml_optimizer is None:
        raise HTTPException(status_code=503, detail="ML optimizer not initialized")
    
    try:
        is_trained = ml_optimizer.model_manager.get_current_model() is not None
        
        if is_trained:
            if training_status != "success":
                training_status = "success"
            status = ml_optimizer.get_system_status()
            return ModelStatusResponse(**status)

        if training_status == "idle":
            logger.info("No trained model found. Starting background training.")
            background_tasks.add_task(train_model_background)
            return ModelStatusResponse(
                is_trained=False,
                last_training_time=None,
                current_model={"status": "training_started"},
                model_performance={},
                vector_db_status=ml_optimizer.vector_db_client.get_collection_info()
            )
        elif training_status == "training":
            return ModelStatusResponse(
                is_trained=False,
                last_training_time=None,
                current_model={"status": "training_in_progress"},
                model_performance={},
                vector_db_status=ml_optimizer.vector_db_client.get_collection_info()
            )
        elif training_status == "failed":
             return ModelStatusResponse(
                is_trained=False,
                last_training_time=None,
                current_model={"status": "training_failed"},
                model_performance={},
                vector_db_status=ml_optimizer.vector_db_client.get_collection_info()
            )
        
        # Fallback for any other state, including "success" before is_trained is reflected
        status = {
            'is_trained': False,
            'last_training_time': None,
            'current_model': None,
            'model_performance': {},
            'vector_db_status': ml_optimizer.vector_db_client.get_collection_info()
        }
        return ModelStatusResponse(**status)
        
    except Exception as e:
        logger.error(f"Error getting model status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/train")
async def train_model():
    """Train or retrain the ML model."""
    global ml_optimizer
    
    if ml_optimizer is None:
        raise HTTPException(status_code=503, detail="ML optimizer not initialized")
    
    try:
        logger.info("Starting model training")
        
        # Check if we have sufficient data before attempting training
        features, outcomes = ml_optimizer.collect_and_preprocess_data(days_back=30)
        
        if not features or not outcomes:
            logger.warning("Insufficient training data available")
            return {
                "status": "insufficient_data",
                "message": "Not enough historical data to train model",
                "timestamp": datetime.now().isoformat()
            }
        
        # Train models
        training_results = ml_optimizer.train_ml_models(features, outcomes)
        
        # Mark as trained if successful
        if training_results and training_results.get('model_performance'):
            ml_optimizer.is_trained = True
            ml_optimizer.last_training_time = datetime.now()
            logger.info("Model training completed successfully")
        
        return {
            "status": "success",
            "training_results": training_results,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error training model: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/update")
async def update_model():
    """Update model with new data."""
    global ml_optimizer
    
    if ml_optimizer is None:
        raise HTTPException(status_code=503, detail="ML optimizer not initialized")
    
    try:
        logger.info("Updating model with new data")
        
        # Collect recent data
        features, outcomes = ml_optimizer.collect_and_preprocess_data(days_back=7)
        
        if not features or not outcomes:
            raise HTTPException(status_code=400, detail="No new data available")
        
        # Update model
        success = ml_optimizer.update_model_with_new_data(features, outcomes)
        
        if success:
            return {
                "status": "success",
                "message": "Model updated successfully",
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="Model update failed")
        
    except Exception as e:
        logger.error(f"Error updating model: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/rollback")
async def rollback_model():
    """Rollback to previous model version."""
    global ml_optimizer
    
    if ml_optimizer is None:
        raise HTTPException(status_code=503, detail="ML optimizer not initialized")
    
    try:
        success = ml_optimizer.rollback_model()
        
        if success:
            return {
                "status": "success",
                "message": "Model rolled back successfully",
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="Model rollback failed")
        
    except Exception as e:
        logger.error(f"Error rolling back model: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/performance")
async def get_model_performance():
    """Get model performance metrics."""
    global ml_optimizer
    
    if ml_optimizer is None:
        raise HTTPException(status_code=503, detail="ML optimizer not initialized")
    
    try:
        performance = ml_optimizer.get_model_performance()
        return performance
        
    except Exception as e:
        logger.error(f"Error getting model performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/features/importance")
async def get_feature_importance():
    """Get feature importance scores."""
    global ml_optimizer
    
    if ml_optimizer is None:
        raise HTTPException(status_code=503, detail="ML optimizer not initialized")
    
    try:
        importance = ml_optimizer.get_feature_importance()
        return importance
        
    except Exception as e:
        logger.error(f"Error getting feature importance: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run server
    uvicorn.run(
        app,
        host=os.getenv("ML_SERVER_HOST", "0.0.0.0"),
        port=int(os.getenv("ML_SERVER_PORT", "8002")),
        log_level="info"
    )
