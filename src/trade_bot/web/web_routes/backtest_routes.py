"""Backtest Routes for Trading Dashboard."""

from fastapi import APIRouter, HTTPException
from ..web_components import get_app_state
from ..models import BacktestRequest

# Create router
router = APIRouter()

# Helper function to check if handlers are ready
def check_handlers_ready(handlers_name: str, handlers):
    """Check if handlers are ready, raise HTTPException if not."""
    if handlers is None:
        raise HTTPException(status_code=503, detail=f"Server not ready - {handlers_name} not initialized")

@router.post("/api/backtest")
async def run_backtest(request: BacktestRequest):
    """Run a backtest with the specified parameters."""
    try:
        app_state = get_app_state()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("backtest_handlers", app_state.backtest_handlers)
    return await app_state.backtest_handlers.run_backtest(request.dict())

@router.post("/api/backtests/run")
async def run_backtests_alias(request: BacktestRequest):
    """Alias endpoint to run a backtest (parity with modular client)."""
    try:
        app_state = get_app_state()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("backtest_handlers", app_state.backtest_handlers)
    return await app_state.backtest_handlers.run_backtest(request.dict())

@router.get("/api/backtest/results")
async def get_backtest_results():
    """Get all backtest results."""
    try:
        app_state = get_app_state()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("backtest_handlers", app_state.backtest_handlers)
    return await app_state.backtest_handlers.get_backtest_results()

@router.get("/api/backtest/history")
async def get_backtest_history(limit: int = 10, offset: int = 0):
    """Get backtest history with pagination."""
    try:
        app_state = get_app_state()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("backtest_handlers", app_state.backtest_handlers)
    return await app_state.backtest_handlers.get_backtest_history(limit, offset)

@router.get("/api/backtest/{backtest_id}")
async def get_backtest(backtest_id: int):
    """Get a specific backtest by ID."""
    try:
        app_state = get_app_state()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("backtest_handlers", app_state.backtest_handlers)
    return await app_state.backtest_handlers.get_backtest(backtest_id)

@router.get("/api/backtest/stats")
async def get_backtest_stats():
    """Get backtest statistics."""
    try:
        app_state = get_app_state()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("backtest_handlers", app_state.backtest_handlers)
    return await app_state.backtest_handlers.get_backtest_stats()

@router.delete("/api/backtest/{backtest_id}")
async def delete_backtest(backtest_id: int):
    """Delete a backtest."""
    try:
        app_state = get_app_state()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("backtest_handlers", app_state.backtest_handlers)
    return await app_state.backtest_handlers.delete_backtest(backtest_id)

@router.get("/api/backtest/filters")
async def get_backtest_filters():
    """Get available backtest filters."""
    try:
        app_state = get_app_state()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("backtest_handlers", app_state.backtest_handlers)
    return await app_state.backtest_handlers.get_backtest_filters()
