"""ML Model Server for real-time inference."""

import logging
import os
import sys
import json
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import numpy as np

# Add parent directories to Python path to enable importing trade_bot modules
# This is critical for unpickling models that were saved with absolute imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)  # Points to src/trade_bot
grandparent_dir = os.path.dirname(parent_dir)  # Points to src

# Add paths to enable both 'import trade_bot.ml.wrapper' and 'from trade_bot.ml import wrapper'
if grandparent_dir not in sys.path:
    sys.path.insert(0, grandparent_dir)

# Now import local modules
# Use relative imports to ensure we remain within the package context
try:
    from .ml_optimizer import MLTradingOptimizer
    from .wrapper import TradingModelWrapper, _reconstruct_wrapper
except ImportError:
    # Fallback for standalone execution
    from ml_optimizer import MLTradingOptimizer
    from wrapper import TradingModelWrapper, _reconstruct_wrapper

# CRITICAL: Create module aliases to support unpickling models saved with different import paths
# This allows models saved with "trade_bot.ml.wrapper" imports to work in this environment
import sys
current_module = sys.modules[__name__]  # Reference to the current 'server' module

# Import all ML modules to make them available
try:
    from . import wrapper
    from . import ml_optimizer
    from . import data_collector
    from . import feature_engineer
    from . import model_trainer
    from . import model_manager
    from . import vector_db_client
except ImportError:
    import wrapper
    import ml_optimizer
    import data_collector
    import feature_engineer
    import model_trainer
    import model_manager
    import vector_db_client

logger = logging.getLogger(__name__)

# Import Data Provider for fetching real-time stats
try:
    from ..data.data_provider import CoinbaseDataProvider
except ImportError:
    try:
        from trade_bot.data.data_provider import CoinbaseDataProvider
    except ImportError:
        # Fallback or mock if not available
        CoinbaseDataProvider = None
        logger.warning("CoinbaseDataProvider could not be imported. Real-time stats fetching disabled.")

# Ensure trade_bot package structure exists in sys.modules if not already present
if 'trade_bot' not in sys.modules:
    sys.modules['trade_bot'] = type(sys)('trade_bot')
if 'trade_bot.ml' not in sys.modules:
    sys.modules['trade_bot.ml'] = type(sys)('trade_bot.ml')

# Ensure modules are mapped to their full package paths
# This handles cases where they might have been loaded as top-level modules
sys.modules['trade_bot.ml.wrapper'] = wrapper
sys.modules['trade_bot.ml.ml_optimizer'] = ml_optimizer
sys.modules['trade_bot.ml.data_collector'] = data_collector
sys.modules['trade_bot.ml.feature_engineer'] = feature_engineer
sys.modules['trade_bot.ml.model_trainer'] = model_trainer
sys.modules['trade_bot.ml.model_manager'] = model_manager
sys.modules['trade_bot.ml.vector_db_client'] = vector_db_client

# Initialize FastAPI app
app = FastAPI(title="ML Trading Model Server", version="1.0.0")

# Global ML optimizer instance and state
ml_optimizer = None
training_status: str = "idle"  # "idle", "training", "success", "failed"
model_ready: bool = False

# Stats Cache
stats_cache: Dict[str, Dict[str, Any]] = {}
STATS_CACHE_TTL = 300  # 5 minutes

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
    # New meta-features
    volume_24h: Optional[float] = 0.0
    volume_30d: Optional[float] = 0.0
    high_24h: Optional[float] = 0.0
    low_24h: Optional[float] = 0.0

class PredictionResponse(BaseModel):
    action: str
    confidence: float
    signal_value: float
    reason: str
    similar_conditions: int
    timestamp: str
    win_probability: Optional[float] = 0.0
    expected_return_percentage: Optional[float] = 0.0
    analytics: Optional[Dict[str, Any]] = {}

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
        # Fetch 24h stats if missing
        volume_24h = request.volume_24h
        volume_30d = request.volume_30d
        high_24h = request.high_24h
        low_24h = request.low_24h

        if (volume_24h == 0.0 or high_24h == 0.0) and CoinbaseDataProvider:
            try:
                # Check cache
                cached = stats_cache.get(request.symbol)
                now = datetime.now().timestamp()
                
                if cached and (now - cached['timestamp'] < STATS_CACHE_TTL):
                    stats = cached['data']
                else:
                    # Fetch fresh
                    provider = CoinbaseDataProvider(request.symbol)
                    stats = await provider.get_product_stats()
                    # Also update cache
                    if stats:
                        stats_cache[request.symbol] = {
                            'timestamp': now,
                            'data': stats
                        }
                    # Don't need to close/cleanup provider as it uses aiohttp session created per request 
                    # or if it uses a shared session, we should check implementation.
                    # Looking at CoinbaseDataProvider, it creates a new session in methods unless configured otherwise.
                
                if stats:
                    if volume_24h == 0.0: volume_24h = stats.get('volume', 0.0)
                    if volume_30d == 0.0: volume_30d = stats.get('volume_30day', 0.0)
                    if high_24h == 0.0: high_24h = stats.get('high', 0.0)
                    if low_24h == 0.0: low_24h = stats.get('low', 0.0)
                    
            except Exception as e:
                logger.warning(f"Failed to fetch product stats for {request.symbol}: {e}")

        # Convert request to OrderBookFeatures
        # Use global import instead of local import which might fail
        features = data_collector.OrderBookFeatures(
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
            volatility=request.volatility,
            volume_24h=volume_24h,
            volume_30d=volume_30d,
            high_24h=high_24h,
            low_24h=low_24h
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

@app.post("/set_active")
async def set_active_model(model_name: str):
    """Set the active ML model."""
    global ml_optimizer, model_ready
    
    if ml_optimizer is None:
        raise HTTPException(status_code=503, detail="ML optimizer not initialized")
    
    try:
        logger.info(f"Setting active model to: {model_name}")
        
        # Run in thread to avoid blocking event loop
        # Reload registry first to ensure we see new models
        ml_optimizer.model_manager.load_model_registry()
        success = await asyncio.to_thread(ml_optimizer.model_manager.set_active_model, model_name)
        
        if success:
            # Update the optimizer's current model reference if needed
            model_ready = True
            
            return {
                "status": "success",
                "message": f"Active model set to {model_name}",
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=400, detail=f"Failed to set active model: {model_name}")
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Error setting active model: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

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
