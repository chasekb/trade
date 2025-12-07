"""New modular web server using component architecture."""

import os
import asyncio
import logging
from fastapi import FastAPI, Request, WebSocket, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
import time

from ..core.config import TradingConfig
from ..data.data_provider import CoinbaseDataProvider
from ..data.cached_data_provider import CachedDataProvider
from ..data.product_fetcher import ProductFetcher
from ..database.database_manager import DatabaseManager
from ..trading.simulated_trading_manager import SimulatedTradingManager
from ..ml.training_manager import TrainingManager
from ..data.websocket_client import WebSocketClient
from ..data.data_handler import DataHandler
from ..web.web_components import RateLimiter, WebSocketManager, ApplicationState, set_app_state, get_app_state
from ..web.web_handlers import (
    APIHandlers, BacktestHandlers,
    TradingHandlers, WebSocketHandlers, DataHandlers
)
from ..web.web_handlers.live_portfolio_handlers import LivePortfolioHandlers
from ..web.web_handlers.ml_handler import ml_router
from ..web.web_routes import (
    api_routes, backtest_routes, trading_routes,
    websocket_routes, data_routes, live_portfolio_routes, ml_routes
)
from ..ml.vector_database_service import get_vector_db_service

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global rate limiter instance
rate_limiter = RateLimiter()

# Global application state manager - will be set during startup

# Moved to ApplicationState class

# FastAPI app with performance optimizations
app = FastAPI(
    title="Trading Dashboard API", 
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add CORS middleware for better performance
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include ML router
app.include_router(ml_router)

# Include route modules
app.include_router(api_routes.router)
app.include_router(backtest_routes.router)
app.include_router(trading_routes.router)
app.include_router(websocket_routes.router)
app.include_router(data_routes.router)
app.include_router(live_portfolio_routes.router)
app.include_router(ml_routes.router)

# Helper function to check if handlers are ready
def check_handlers_ready(handlers_name: str, handlers):
    """Check if handlers are ready, raise HTTPException if not."""
    if handlers is None:
        raise HTTPException(status_code=503, detail=f"Server not ready - {handlers_name} not initialized")

@app.get("/health")
async def health_check():
    """Health check endpoint for Docker health monitoring."""
    return {"status": "healthy", "service": "trading-bot-backend"}

@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    try:
        # Create application state instance
        app_state_local = ApplicationState()

        # Initialize configuration
        config = TradingConfig.from_env()

        # Initialize vector database and ML services (fault-tolerant)
        logger.info("🚀 Initializing vector database and ML services...")
        vector_db_service = get_vector_db_service()
        app_state_local.vector_db_service = vector_db_service

        try:
            from ..ml.ml_optimizer import MLTradingOptimizer
            ml_optimizer = MLTradingOptimizer(
                db_url=os.getenv('DATABASE_URL'),
                models_dir="data/models",
                vector_db_host=os.getenv('QDRANT_HOST', 'localhost'),
                vector_db_port=int(os.getenv('QDRANT_PORT', '6333'))
            )
            app_state_local.ml_optimizer = ml_optimizer
            logger.info("✅ ML optimizer initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize ML optimizer: {e}")
            app_state_local.ml_optimizer = None

        # Initialize core components
        data_provider = CoinbaseDataProvider(config, config)
        cached_data_provider = CachedDataProvider(config, db_url=os.getenv('DATABASE_URL'))
        product_fetcher = ProductFetcher()
        database_manager = DatabaseManager()

        # Initialize TrainingManager and ModelManager
        training_manager = TrainingManager(
            db_path=os.getenv("DATABASE_URL", "data/databases/trading_cache.db"),
            models_dir="data/models",
            ml_optimizer=app_state_local.ml_optimizer
        )
        app_state_local.training_manager = training_manager
        model_manager = training_manager.model_manager
        app_state_local.model_manager = model_manager

        simulated_trading_manager = SimulatedTradingManager(
            initial_balance=10000.0,
            db_manager=database_manager,
            model_manager=model_manager,
            config=config
        )
        data_handler = DataHandler(config)
        websocket_client = WebSocketClient(config)
        websocket_manager = WebSocketManager(config)

        # Store components in application state
        app_state_local.data_handler = data_handler
        app_state_local.simulated_trading_manager = simulated_trading_manager
        app_state_local.database_manager = database_manager
        app_state_local.websocket_client = websocket_client
        app_state_local.websocket_manager = websocket_manager

        # Connect WebSocketManager to trading state and components
        websocket_manager.set_trading_state({
            "is_active": app_state_local.trading_state.is_trading,
            "strategy_type": app_state_local.trading_state.active_strategy,
            "symbols": app_state_local.trading_state.symbols
        })
        websocket_manager.set_simulated_trading(simulated_trading_manager)

        # Initialize handlers
        api_handlers = APIHandlers(config, data_provider, cached_data_provider, product_fetcher, database_manager, simulated_trading_manager)
        backtest_handlers = BacktestHandlers(config, database_manager)
        data_handlers = DataHandlers(config, data_provider, cached_data_provider, database_manager, simulated_trading_manager, None, app_state_local.trading_state)
        trading_handlers = TradingHandlers(config, simulated_trading_manager, database_manager, websocket_manager, data_handlers)
        
        # Set websocket manager reference in data handlers after both are created
        data_handlers.websocket_manager = websocket_manager
        data_handlers.trading_handlers = trading_handlers

        app_state_local.websocket_handlers = WebSocketHandlers(websocket_manager)
        app_state_local.data_handlers = data_handlers
        app_state_local.live_portfolio_handlers = LivePortfolioHandlers(config)

        # Store handlers in application state
        app_state_local.api_handlers = api_handlers
        app_state_local.backtest_handlers = backtest_handlers
        app_state_local.trading_handlers = trading_handlers

        logger.info(f"✅ Live portfolio handlers initialized: {app_state_local.live_portfolio_handlers is not None}")

        # ML services are handled by the ML handler routes and vector database integration
        if app_state_local.ml_optimizer:
            logger.info("✅ ML optimizer and vector database services available")

        # Mark application as initialized
        app_state_local.set_initialized(True)

        # Set the global app_state reference BEFORE starting WebSocket connections
        # This prevents "Service unavailable - application not initialized" errors
        set_app_state(app_state_local)

        # Start WebSocket client and real-time data processing
        # Note: WebSocket client and background processing will be started when needed
        try:
            # Start the real-time data processing which includes background trading signal processing
            await websocket_manager.start_real_time_data()
            logger.info("✅ WebSocket manager real-time data processing started")
        except Exception as e:
            logger.error(f"❌ Failed to start WebSocket manager real-time data processing: {e}")
            # Don't fail startup, just log the error

        # Start continuous model training
        try:
            training_manager.start_continuous_training()
            logger.info("✅ Continuous model training started")
        except Exception as e:
            logger.error(f"❌ Failed to start continuous model training: {e}")

        port = int(os.getenv("PORT", "8000"))
        logger.info("🚀 Trading API Backend started successfully!")
        logger.info(f"� API endpoints available at: http://localhost:{port}")
        logger.info(f"🔌 WebSocket endpoint: ws://localhost:{port}/ws")
        logger.info(f"📈 API documentation: http://localhost:{port}/docs")

    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Gracefully close simulated positions and stop services on server shutdown."""
    try:
        # Get application state to perform cleanup
        app_state_instance = get_app_state()
        if app_state_instance:
            await app_state_instance.cleanup()
        logger.info("👋 Trading API Backend shutdown complete")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
