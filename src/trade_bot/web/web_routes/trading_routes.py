"""Trading Routes for Trading Dashboard."""

import asyncio
import logging
from fastapi import APIRouter, HTTPException

from ..web_components import app_state

# Create router
router = APIRouter()
logger = logging.getLogger(__name__)

# Helper function to check if handlers are ready
def check_handlers_ready(handlers_name: str, handlers):
    """Check if handlers are ready, raise HTTPException if not."""
    if handlers is None:
        raise HTTPException(status_code=503, detail=f"Server not ready - {handlers_name} not initialized")

# Live Trading Routes
@router.post("/api/trading/live/start")
async def start_live_trading(request: dict):
    """Start live trading session."""
    if app_state is None:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.start_live_trading(request)

@router.post("/api/trading/live/stop")
async def stop_live_trading(request: dict):
    """Stop live trading session."""
    if app_state is None:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.stop_live_trading(request)

@router.get("/api/trading/live/positions")
async def get_live_positions(page: int = 1, limit: int = 50):
    """Get current live trading positions (paginated)."""
    if app_state is None:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.get_live_positions(page=page, limit=limit)

@router.post("/api/trading/live/close-position")
async def close_live_position(request: dict):
    """Close a specific live trading position."""
    if app_state is None:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.close_live_position(request)

@router.get("/api/trading/live/history")
async def get_live_trading_history():
    """Get live trading history."""
    if app_state is None:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.get_live_trading_history()

# Simulated Trading Routes
@router.post("/api/trading/simulated/start")
async def start_simulated_trading(request: dict):
    """Start simulated trading session."""
    if app_state is None:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.start_simulated_trading(request)

@router.post("/api/async-trading/start")
async def start_async_trading(request: dict):
    """Start async trading session with progressive symbol loading."""
    if app_state is None:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)

    try:
        # Extract trading parameters
        symbols = request.get('symbols', ['BTC-USD', 'ETH-USD'])
        strategy_type = request.get('strategy_type', 'orderbook')
        strategy_params = request.get('strategy_params', {})
        initial_balance = request.get('initial_balance', 10000.0)
        max_positions = request.get('max_positions', 5)
        position_size_percent = request.get('position_size_percent', 20.0)
        position_update_interval = request.get('position_update_interval', 5)
        session_id = request.get('session_id')
        immediate_start = request.get('immediate_start', True)
        batch_size = request.get('batch_size', 3)

        # Create session ID if not provided
        if not session_id:
            import time
            session_id = f"async_trading_{int(time.time())}"

        # Start with first batch of symbols for immediate trading
        initial_symbols = symbols[:batch_size] if len(symbols) > batch_size else symbols
        remaining_symbols = symbols[batch_size:] if len(symbols) > batch_size else []

        # Update trading state via application state
        app_state.trading_state.is_trading = True
        app_state.trading_state.active_strategy = strategy_type
        app_state.trading_state.symbols = initial_symbols
        app_state.trading_state.session_id = session_id
        app_state.update_loading_progress(
            loaded=len(initial_symbols),
            total=len(symbols),
            status="loading"
        )

        # Start simulated trading with initial symbols
        await app_state.trading_handlers.start_simulated_trading({
            'symbols': initial_symbols,
            'strategy_type': strategy_type,
            'strategy_params': strategy_params,
            'position_size_percent': position_size_percent,
            'max_positions': max_positions,
            'position_update_interval': position_update_interval,
            'initial_balance': initial_balance
        })

        # Start background symbol loading if there are remaining symbols
        if remaining_symbols and immediate_start:
            import asyncio
            asyncio.create_task(load_remaining_symbols_background(remaining_symbols, batch_size))

        return {
            "status": "started",
            "session_id": session_id,
            "initial_symbols": initial_symbols,
            "remaining_symbols": remaining_symbols,
            "total_symbols": len(symbols),
            "loading_progress": app_state.trading_state.loading_progress,
            "trading_active": True
        }

    except Exception as e:
        logger.error(f"Error starting async trading: {e}")
        return {"error": str(e)}

@router.get("/api/async-trading/loading-status")
async def get_async_trading_loading_status():
    """Get async trading loading status (alternative endpoint)."""
    if app_state is None:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    try:
        return {
            "loading_progress": app_state.trading_state.loading_progress,
            "current_symbols": app_state.trading_state.symbols,
            "is_loading": app_state.trading_state.loading_progress.get("status") == "loading"
        }
    except Exception as e:
        logger.error(f"Error getting loading status: {e}")
        return {"error": str(e)}

@router.get("/api/data/load-universe")
async def load_universe_data(symbols: str = None):
    """Load data for universe of symbols."""
    if app_state is None:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("data_handlers", app_state.data_handlers)
    if symbols:
        symbol_list = symbols.split(',')
        return await app_state.data_handlers.load_remaining_symbols_async(symbol_list, 3)
    else:
        return {"status": "error", "message": "No symbols provided"}

@router.get("/api/data/load-symbols")
async def load_symbols_data(symbols: str = None):
    """Load data for symbols (alternative endpoint)."""
    if app_state is None:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("data_handlers", app_state.data_handlers)
    if symbols:
        symbol_list = symbols.split(',')
        return await app_state.data_handlers.load_remaining_symbols_async(symbol_list, 3)
    else:
        return {"status": "error", "message": "No symbols provided"}

@router.post("/api/trading/simulated/stop")
async def stop_simulated_trading():
    """Stop simulated trading session."""
    if app_state is None:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.stop_simulated_trading()

@router.get("/api/trading/simulated/status")
async def get_simulated_trading_status():
    """Get simulated trading status."""
    if app_state is None:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.get_simulated_trading_status()

@router.get("/api/simulated-trading/status")
async def get_simulated_trading_status_alt():
    """Alternative endpoint for simulated trading status."""
    if app_state is None:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.get_simulated_trading_status()

@router.post("/api/trading/simulated/process-signals")
async def process_simulated_signals(request: dict):
    """Process simulated trading signals."""
    if app_state is None:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.process_simulated_signals(request)

@router.post("/api/trading/simulated/reset")
async def reset_simulated_trading():
    """Reset simulated trading session."""
    if app_state is None:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.reset_simulated_trading()

@router.post("/api/trading/simulated/add-symbols")
async def add_symbols_to_trading(request: dict):
    """Add symbols to current trading session."""
    if app_state is None:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.add_symbols_to_trading(request)

# Trading Statistics Routes
@router.get("/api/trades/stats")
async def get_trades_stats():
    """Get trading statistics."""
    if app_state is None:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.get_simulated_trading_status()

@router.get("/api/trades/paginated")
async def get_trades_paginated(page: int = 1, per_page: int = 10, session_id: str = None):
    """Get paginated trades."""
    if app_state is None:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.get_paginated_trading_history(page=page, per_page=per_page, session_id=session_id)

@router.get("/api/trades/session/{session_id}")
async def get_session_trades(session_id: str):
    """Get trades for a specific session."""
    if app_state is None:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.get_session_trading_history(session_id)

@router.get("/api/trading/history/all")
async def get_all_trading_history(limit: int = 1000, offset: int = 0):
    """Get all trading history from database."""
    if app_state is None:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.get_all_trading_history(limit=limit, offset=offset)

@router.get("/api/trading/metrics")
async def get_trading_metrics():
    """Get comprehensive trading metrics."""
    if app_state is None:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.get_trading_metrics()

async def load_remaining_symbols_background(remaining_symbols: list, batch_size: int = 3):
    """Background task to load remaining symbols progressively."""
    try:
        logger.info(f"Starting background loading of {len(remaining_symbols)} symbols")

        # Process symbols in batches
        for i in range(0, len(remaining_symbols), batch_size):
            batch = remaining_symbols[i:i + batch_size]

            try:
                # Check if app_state is available before proceeding
                if app_state is None:
                    logger.error("App state not available in background loading")
                    return

                # Add batch to trading
                await app_state.trading_handlers.add_symbols_to_trading({"symbols": batch})

                # Update trading state
                current_symbols = app_state.trading_state.get("symbols", [])
                app_state.trading_state["symbols"] = current_symbols + batch

                # Update loading progress
                loaded_count = len(app_state.trading_state["symbols"])
                total_count = app_state.trading_state["loading_progress"]["total"]
                remaining_count = len(remaining_symbols) - (i + len(batch))

                app_state.trading_state["loading_progress"] = {
                    "status": "loading" if remaining_count > 0 else "complete",
                    "loaded": loaded_count,
                    "total": total_count,
                    "remaining": remaining_count,
                    "progress": int((loaded_count / total_count) * 100) if total_count > 0 else 100
                }

                # Wait between batches to avoid overwhelming the system
                await asyncio.sleep(2.0)

                logger.info(f"Loaded batch {i//batch_size + 1}: {batch}")

            except Exception as batch_error:
                logger.error(f"Error loading batch {i//batch_size + 1}: {batch_error}")
                # Mark progress as error and continue with next batch
                if app_state and app_state.trading_state:
                    app_state.trading_state["loading_progress"]["status"] = "error"
                continue

        # Mark loading as complete
        if app_state and app_state.trading_state:
            app_state.trading_state["loading_progress"]["status"] = "complete"

        logger.info("Background symbol loading completed")

    except Exception as e:
        logger.error(f"Error in background symbol loading: {e}")
        if app_state and app_state.trading_state:
            app_state.trading_state["loading_progress"]["status"] = "error"
