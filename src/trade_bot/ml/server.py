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

# Global ML optimizer instance and state
ml_optimizer = None
training_status: str = "idle"  # "idle", "training", "success", "failed"
model_ready: bool = False

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
    vector_db_stats: Optional[Dict[str, Any]] = None

async def load_model_background():
    """Initialize ML optimizer and load model in the background."""
    global ml_optimizer, model_ready
    
    try:
        logger.info("Initializing ML Trading Optimizer in background")
        
        # Initialize ML optimizer
        temp_optimizer = MLTradingOptimizer(
            db_url=os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/trading_db"),
            models_dir=os.getenv("MODELS_DIR", "data/models"),
            vector_db_host=os.getenv("QDRANT_HOST", "localhost"),
            vector_db_port=int(os.getenv("QDRANT_PORT", "6333"))
        )
        
        # Initialize vector database
        if not temp_optimizer.initialize_vector_database():
            logger.warning("Failed to initialize vector database")
        
        # Load the registry
        temp_optimizer.model_manager.load_model_registry()
        
        # Assign to global variable after basic initialization
        ml_optimizer = temp_optimizer
        
        # Now, load the active model
        active_model_name = None
        config_path = os.path.abspath("data/ml_config.json")
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
                active_model_name = config.get("active_model")
        except (FileNotFoundError, json.JSONDecodeError):
            logger.info(f"No active model configured in {config_path}.")
        
        if active_model_name:
            logger.info(f"Attempting to deploy configured model '{active_model_name}' in background.")
            # Run the blocking model loading in a separate thread
            success = await asyncio.to_thread(ml_optimizer.model_manager.set_active_model, active_model_name)
            if success:
                model_ready = True
                logger.info(f"Model '{active_model_name}' deployed successfully. Server is ready for predictions.")
            else:
                logger.warning(f"Failed to deploy configured model '{active_model_name}'.")
        else:
            logger.info("No active model configured. Server will wait for model selection.")
            model_ready = True # Ready for tasks that don't require a model

        logger.info("ML Trading Optimizer background initialization finished.")
        
    except Exception as e:
        logger.error(f"Error initializing ML optimizer in background: {e}")

@app.on_event("startup")
async def startup_event():
    """Schedule background initialization of the ML optimizer."""
    logger.info("Scheduling ML optimizer initialization.")
    asyncio.create_task(load_model_background())

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    # Return healthy status immediately without any logging to ensure fast response
    # for container health checks. Logging can be slow and cause timeouts.
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/predict", response_model=PredictionResponse)
async def predict_trading_signal(request: PredictionRequest):
    """Predict optimal trading signal."""
    global ml_optimizer, model_ready
    logger.info(f"Prediction requested for {request.symbol}")

    if ml_optimizer is None:
        logger.error("ML optimizer not initialized")
        raise HTTPException(status_code=503, detail="ML optimizer not initialized")

    if not model_ready:
        logger.warning("Prediction requested, but model is not ready yet.")
        raise HTTPException(status_code=503, detail="Model is loading, please try again later.")

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

        # Check if model is trained and deployed
        if not ml_optimizer.is_trained or ml_optimizer.model_manager.current_model is None:
            logger.warning("Prediction requested, but no model is deployed.")
            return PredictionResponse(
                action="hold",
                confidence=0.0,
                signal_value=0.0,
                reason="Model not trained or deployed",
                similar_conditions=0,
                timestamp=datetime.now().isoformat()
            )

        # Get prediction
        prediction = ml_optimizer.predict_trading_signal(features)
        logger.info(f"Prediction for {request.symbol}: {prediction}")
        return PredictionResponse(**prediction)

    except Exception as e:
        logger.error(f"Error making prediction for {request.symbol}: {e}")
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
    logger.info("Status requested")

    if ml_optimizer is None:
        logger.error("ML optimizer not initialized")
        raise HTTPException(status_code=503, detail="ML optimizer not initialized")

    try:
        # Always reload the model registry to get the latest state
        ml_optimizer.model_manager.load_model_registry()

        # Check for a configured active model
        active_model_name = None
        config_path = os.path.abspath("data/ml_config.json")
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
                active_model_name = config.get("active_model")
        except (FileNotFoundError, json.JSONDecodeError):
            pass  # No config file, that's fine

        # If a model is configured, ensure it's the one that's deployed
        current_model_info = ml_optimizer.model_manager.get_current_model()
        current_model_id = None
        if current_model_info and 'model_name' in current_model_info and 'version_id' in current_model_info:
            current_model_id = f"{current_model_info['model_name']}:{current_model_info['version_id']}"

        if active_model_name and active_model_name != current_model_id:
            logger.info(f"Configuration changed. Setting new active model: {active_model_name}")
            ml_optimizer.model_manager.set_active_model(active_model_name)

        is_trained = ml_optimizer.is_trained
        if is_trained:
            status = ml_optimizer.get_system_status()
            logger.info(f"Current status: {status}")
            return ModelStatusResponse(**status)

        if training_status == "idle":
            logger.info("No trained model found. Starting background training.")
            background_tasks.add_task(train_model_background)
            training_status = "training"
            return ModelStatusResponse(
                is_trained=False,
                last_training_time=None,
                current_model={"status": "training_started"},
                model_performance={},
                vector_db_status=ml_optimizer.vector_db_client.get_collection_info()
            )
        else:
            return ModelStatusResponse(
                is_trained=False,
                last_training_time=None,
                current_model={"status": f"training_{training_status}"},
                model_performance={},
                vector_db_status=ml_optimizer.vector_db_client.get_collection_info()
            )
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
