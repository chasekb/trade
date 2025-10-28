"""Data Routes for Trading Dashboard."""

import logging
from fastapi import APIRouter, HTTPException

from ..web_components import app_state
from ...ml.vector_database_service import get_vector_db_service

# Create router
router = APIRouter()
logger = logging.getLogger(__name__)

# Helper function to check if handlers are ready
def check_handlers_ready(handlers_name: str, handlers):
    """Check if handlers are ready, raise HTTPException if not."""
    if handlers is None:
        raise HTTPException(status_code=503, detail=f"Server not ready - {handlers_name} not initialized")

# Data cache and statistics routes
@router.get("/api/data/cache-stats")
async def get_cache_stats():
    """Get cache statistics."""
    check_handlers_ready("data_handlers", app_state.data_handlers)
    return await app_state.data_handlers.get_cache_stats()

@router.get("/api/data/orderbook-signals")
async def get_live_orderbook_signals(symbols: str = None, page: int = 1, per_page: int = 50):
    """Get live order book signals."""
    check_handlers_ready("data_handlers", app_state.data_handlers)
    return await app_state.data_handlers.get_live_orderbook_signals(symbols, page, per_page)

@router.get("/api/orderbook/live-signals")
async def get_orderbook_live_signals(symbols: str = None, page: int = 1, per_page: int = 50):
    """Get live order book signals (alternative endpoint)."""
    check_handlers_ready("data_handlers", app_state.data_handlers)
    return await app_state.data_handlers.get_live_orderbook_signals(symbols, page, per_page)

@router.get("/api/data/loading-status")
async def get_loading_status():
    """Get data loading status."""
    check_handlers_ready("data_handlers", app_state.data_handlers)
    return await app_state.data_handlers.get_loading_status()

@router.post("/api/data/load-symbols")
async def load_remaining_symbols_async(request: dict):
    """Load remaining symbols asynchronously."""
    check_handlers_ready("data_handlers", app_state.data_handlers)
    remaining_symbols = request.get('remaining_symbols', [])
    batch_size = request.get('batch_size', 3)
    return await app_state.data_handlers.load_remaining_symbols_async(remaining_symbols, batch_size)

# Trading state and session routes
@router.get("/api/data/trading-state")
async def get_trading_state():
    """Get current trading state."""
    check_handlers_ready("data_handlers", app_state.data_handlers)
    return await app_state.data_handlers.get_trading_state()

@router.post("/api/data/save-session")
async def save_session_state(request: dict):
    """Save trading session state."""
    logger.info("save_session_state endpoint called")
    check_handlers_ready("data_handlers", app_state.data_handlers)
    logger.debug("data_handlers is ready, calling save_session_state")
    result = await app_state.data_handlers.save_session_state(request)
    logger.info("save_session_state completed successfully")
    return result

@router.post("/api/data/restore-trading")
async def restore_simulated_trading(request: dict):
    """Restore simulated trading from saved state."""
    check_handlers_ready("data_handlers", app_state.data_handlers)
    return await app_state.data_handlers.restore_simulated_trading(request)

@router.get("/api/data/load-session/{session_id}")
async def load_session_state(session_id: str):
    """Load trading session state."""
    check_handlers_ready("data_handlers", app_state.data_handlers)
    return await app_state.data_handlers.load_session_state(session_id)

@router.post("/api/data/save-dashboard")
async def save_dashboard_state(request: dict):
    """Save dashboard UI state."""
    check_handlers_ready("data_handlers", app_state.data_handlers)
    return await app_state.data_handlers.save_dashboard_state(request)

@router.get("/api/data/load-dashboard/{session_id}")
async def load_dashboard_state(session_id: str):
    """Load dashboard UI state."""
    check_handlers_ready("data_handlers", app_state.data_handlers)
    return await app_state.data_handlers.load_dashboard_state(session_id)

# Metrics routes
@router.get("/api/metrics/trading")
async def get_trading_metrics():
    """Get trading performance metrics."""
    check_handlers_ready("dashboard_handlers", app_state.dashboard_handlers)
    return await app_state.dashboard_handlers.get_trading_metrics()

@router.get("/api/metrics/data-summary")
async def get_data_summary():
    """Get data summary statistics."""
    check_handlers_ready("dashboard_handlers", app_state.dashboard_handlers)
    return await app_state.dashboard_handlers.get_data_summary()

# Active session routes
@router.get("/api/session/active")
async def get_active_session():
    """Get active session."""
    check_handlers_ready("data_handlers", app_state.data_handlers)
    return await app_state.data_handlers.get_trading_state()

@router.post("/api/session/save")
async def save_session(request: dict):
    """Save trading session (alternative endpoint)."""
    check_handlers_ready("data_handlers", app_state.data_handlers)
    return await app_state.data_handlers.save_session_state(request)

@router.post("/api/session/save-dashboard")
async def save_dashboard_session(request: dict):
    """Save dashboard session (alternative endpoint)."""
    check_handlers_ready("data_handlers", app_state.data_handlers)
    return await app_state.data_handlers.save_dashboard_state(request)

# Candles routes
@router.get("/api/candles")
async def get_candles(product_id: str, granularity: int, days: int = 7):
    """Get candle data."""
    check_handlers_ready("dashboard_handlers", app_state.dashboard_handlers)
    from datetime import datetime, timedelta
    # Use fixed historical date range since system date is in 2025
    end_time = datetime(2024, 12, 31)
    start_time = end_time - timedelta(days=days)
    return await app_state.dashboard_handlers.get_candles_data(
        product_id,
        start_time.isoformat(),
        end_time.isoformat(),
        granularity
    )
