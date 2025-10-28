"""Backtest Routes for Trading Dashboard."""

from fastapi import APIRouter, HTTPException
from ..models import BacktestRequest
from ..web_components import app_state

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
    check_handlers_ready("backtest_handlers", app_state.backtest_handlers)
    return await app_state.backtest_handlers.run_backtest(request.dict())

@router.post("/api/backtests/run")
async def run_backtests_alias(request: BacktestRequest):
    """Alias endpoint to run a backtest (parity with modular client)."""
    check_handlers_ready("backtest_handlers", app_state.backtest_handlers)
    return await app_state.backtest_handlers.run_backtest(request.dict())

@router.get("/api/backtest/results")
async def get_backtest_results():
    """Get all backtest results."""
    check_handlers_ready("backtest_handlers", app_state.backtest_handlers)
    return await app_state.backtest_handlers.get_backtest_results()

@router.get("/api/backtest/history")
async def get_backtest_history(limit: int = 10, offset: int = 0):
    """Get backtest history with pagination."""
    check_handlers_ready("backtest_handlers", app_state.backtest_handlers)
    return await app_state.backtest_handlers.get_backtest_history(limit, offset)

@router.get("/api/backtest/{backtest_id}")
async def get_backtest(backtest_id: int):
    """Get a specific backtest by ID."""
    check_handlers_ready("backtest_handlers", app_state.backtest_handlers)
    return await app_state.backtest_handlers.get_backtest(backtest_id)

@router.get("/api/backtest/stats")
async def get_backtest_stats():
    """Get backtest statistics."""
    check_handlers_ready("backtest_handlers", app_state.backtest_handlers)
    return await app_state.backtest_handlers.get_backtest_stats()

@router.delete("/api/backtest/{backtest_id}")
async def delete_backtest(backtest_id: int):
    """Delete a backtest."""
    check_handlers_ready("backtest_handlers", app_state.backtest_handlers)
    return await app_state.backtest_handlers.delete_backtest(backtest_id)

@router.get("/api/backtest/filters")
async def get_backtest_filters():
    """Get available backtest filters."""
    check_handlers_ready("backtest_handlers", app_state.backtest_handlers)
    return await app_state.backtest_handlers.get_backtest_filters()
