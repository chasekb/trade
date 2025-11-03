"""Trading Routes for Trading Dashboard."""

import asyncio
import logging
from fastapi import APIRouter, HTTPException

from ..web_components import get_app_state

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
    try:
        app_state = get_app_state()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.start_live_trading(request)

@router.post("/api/trading/live/stop")
async def stop_live_trading(request: dict):
    """Stop live trading session."""
    try:
        app_state = get_app_state()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.stop_live_trading(request)

@router.get("/api/trading/live/positions")
async def get_live_positions(page: int = 1, limit: int = 50):
    """Get current live trading positions (paginated)."""
    try:
        app_state = get_app_state()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.get_live_positions(page=page, limit=limit)

@router.post("/api/trading/live/close-position")
async def close_live_position(request: dict):
    """Close a specific live trading position."""
    try:
        app_state = get_app_state()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.close_live_position(request)

@router.get("/api/trading/live/history")
async def get_live_trading_history():
    """Get live trading history."""
    try:
        app_state = get_app_state()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.get_live_trading_history()

# Simulated Trading Routes
@router.post("/api/trading/simulated/start")
async def start_simulated_trading(request: dict):
    """Start simulated trading session."""
    try:
        app_state = get_app_state()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.start_simulated_trading(request)

@router.post("/api/async-trading/start")
async def start_async_trading(request: dict):
    """Start async trading session with progressive symbol loading."""
    try:
        app_state = get_app_state()
    except RuntimeError:
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
            "is_active": True
        }

    except Exception as e:
        logger.error(f"Error starting async trading: {e}")
        return {"error": str(e)}

@router.get("/api/async-trading/loading-status")
async def get_async_trading_loading_status():
    """Get async trading loading status (alternative endpoint)."""
    try:
        app_state = get_app_state()
    except RuntimeError:
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
    try:
        app_state = get_app_state()
    except RuntimeError:
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
    try:
        app_state = get_app_state()
    except RuntimeError:
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
    try:
        app_state = get_app_state()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.stop_simulated_trading()

@router.get("/api/trading/simulated/status")
async def get_simulated_trading_status():
    """Get simulated trading status."""
    try:
        app_state = get_app_state()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.get_simulated_trading_status()

@router.get("/api/simulated-trading/status")
async def get_simulated_trading_status_alt():
    """Alternative endpoint for simulated trading status."""
    try:
        app_state = get_app_state()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.get_simulated_trading_status()

@router.post("/api/trading/simulated/process-signals")
async def process_simulated_signals(request: dict):
    """Process simulated trading signals."""
    try:
        app_state = get_app_state()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.process_simulated_signals(request)

@router.post("/api/trading/simulated/reset")
async def reset_simulated_trading():
    """Reset simulated trading session."""
    try:
        app_state = get_app_state()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.reset_simulated_trading()

@router.post("/api/trading/simulated/add-symbols")
async def add_symbols_to_trading(request: dict):
    """Add symbols to current trading session."""
    try:
        app_state = get_app_state()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.add_symbols_to_trading(request)

# Trading Statistics Routes
@router.get("/api/trades/stats")
async def get_trades_stats():
    """Get trading statistics."""
    try:
        app_state = get_app_state()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.get_simulated_trading_status()

@router.get("/api/trades/paginated")
async def get_trades_paginated(page: int = 1, per_page: int = 10, session_id: str = None):
    """Get paginated trades."""
    try:
        app_state = get_app_state()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.get_paginated_trading_history(page=page, per_page=per_page, session_id=session_id)

@router.get("/api/trades/session/{session_id}")
async def get_session_trades(session_id: str):
    """Get trades for a specific session."""
    try:
        app_state = get_app_state()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.get_session_trading_history(session_id)

@router.get("/api/trading/history/all")
async def get_all_trading_history(limit: int = 1000, offset: int = 0):
    """Get all trading history from database."""
    try:
        app_state = get_app_state()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.get_all_trading_history(limit=limit, offset=offset)

@router.get("/api/trading/metrics")
async def get_trading_metrics():
    """Get comprehensive trading metrics."""
    try:
        app_state = get_app_state()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service unavailable - application not initialized")
    check_handlers_ready("trading_handlers", app_state.trading_handlers)
    return await app_state.trading_handlers.get_trading_metrics()

async def load_remaining_symbols_background(remaining_symbols: list, batch_size: int = 3):
    """Background task to load remaining symbols progressively with improved error handling and recovery."""
    try:
        logger.info(f"Starting background loading of {len(remaining_symbols)} symbols")

        # Get app_state for background task
        app_state = get_app_state()
        if app_state is None:
            logger.error("App state not available in background loading")
            return

        # Initialize error tracking and retry logic
        consecutive_failures = 0
        max_consecutive_failures = 3
        retry_delay = 5.0  # Start with 5 seconds
        max_retry_delay = 60.0  # Max 1 minute

        # Process symbols in batches with improved error handling
        for i in range(0, len(remaining_symbols), batch_size):
            batch = remaining_symbols[i:i + batch_size]
            batch_number = i // batch_size + 1
            total_batches = (len(remaining_symbols) + batch_size - 1) // batch_size

            # Retry logic for each batch
            batch_success = False
            batch_retry_count = 0
            max_batch_retries = 3

            while not batch_success and batch_retry_count < max_batch_retries:
                try:
                    # Check if app_state is still available
                    current_app_state = get_app_state()
                    if current_app_state is None:
                        logger.error("App state became unavailable during background loading")
                        return

                    # Check if trading is still active
                    if not current_app_state.trading_state.is_trading:
                        logger.warning("Trading is no longer active, stopping background loading")
                        return

                    logger.info(f"Processing batch {batch_number}/{total_batches}: {batch} (attempt {batch_retry_count + 1})")

                    # Add batch to trading with timeout protection
                    try:
                        # Add timeout to prevent hanging
                        await asyncio.wait_for(
                            current_app_state.trading_handlers.add_symbols_to_trading({"symbols": batch}),
                            timeout=30.0  # 30 second timeout per batch
                        )
                        batch_success = True
                        consecutive_failures = 0  # Reset on success
                    except asyncio.TimeoutError:
                        logger.warning(f"Batch {batch_number} timed out after 30 seconds")
                        batch_retry_count += 1
                        continue

                    # Update trading state - append new symbols to existing ones
                    current_symbols = current_app_state.trading_state.symbols if hasattr(current_app_state.trading_state, 'symbols') else []
                    current_app_state.trading_state.symbols = current_symbols + batch

                    # Update loading progress
                    loaded_count = len(current_app_state.trading_state.symbols)
                    total_count = current_app_state.trading_state.loading_progress.get("total", 0) if hasattr(current_app_state.trading_state, 'loading_progress') else 0
                    remaining_count = len(remaining_symbols) - (i + len(batch))

                    current_app_state.update_loading_progress(
                        loaded=loaded_count,
                        total=total_count,
                        status="loading" if remaining_count > 0 else "complete"
                    )

                    # Wait between batches to avoid overwhelming the system
                    if batch_number < total_batches:  # Don't wait after last batch
                        await asyncio.sleep(2.0)

                    logger.info(f"Successfully loaded batch {batch_number}/{total_batches}: {batch}")

                except asyncio.TimeoutError:
                    logger.error(f"Batch {batch_number} failed due to timeout")
                    batch_retry_count += 1
                    consecutive_failures += 1

                except Exception as batch_error:
                    logger.error(f"Error loading batch {batch_number} (attempt {batch_retry_count + 1}): {batch_error}")
                    batch_retry_count += 1
                    consecutive_failures += 1

                    # Log detailed error information
                    if "timeout" in str(batch_error).lower():
                        logger.warning(f"Batch {batch_number} timeout - may indicate API rate limiting")
                    elif "connection" in str(batch_error).lower():
                        logger.warning(f"Batch {batch_number} connection error - may indicate network issues")
                    elif "rate" in str(batch_error).lower():
                        logger.warning(f"Batch {batch_number} rate limited - increasing delay")

                # Implement exponential backoff for retries
                if not batch_success and batch_retry_count < max_batch_retries:
                    # Calculate delay with exponential backoff and jitter
                    base_delay = retry_delay * (2 ** batch_retry_count)
                    jitter = random.uniform(0.5, 1.5)
                    delay = min(base_delay + jitter, max_retry_delay)
                    
                    logger.info(f"Retrying batch {batch_number} in {delay:.2f} seconds")
                    await asyncio.sleep(delay)

            # Handle batch failure after all retries
            if not batch_success:
                logger.error(f"Batch {batch_number} failed after {max_batch_retries} attempts")
                
                # Update progress to error state but continue with next batch
                try:
                    error_app_state = get_app_state()
                    if error_app_state and error_app_state.trading_state:
                        current_symbols = error_app_state.trading_state.symbols if hasattr(error_app_state.trading_state, 'symbols') else []
                        total_count = error_app_state.trading_state.loading_progress.get("total", 0) if hasattr(error_app_state.trading_state, 'loading_progress') else 0
                        
                        error_app_state.update_loading_progress(
                            loaded=len(current_symbols),
                            total=total_count,
                            status="error" if consecutive_failures >= max_consecutive_failures else "loading"
                        )
                except Exception as error_update_e:
                    logger.warning(f"Failed to update error status for batch {batch_number}: {error_update_e}")

                # Implement circuit breaker: if too many consecutive failures, stop processing
                if consecutive_failures >= max_consecutive_failures:
                    logger.error(f"Circuit breaker activated: {consecutive_failures} consecutive batch failures, stopping background loading")
                    try:
                        circuit_app_state = get_app_state()
                        if circuit_app_state and circuit_app_state.trading_state:
                            current_symbols = circuit_app_state.trading_state.symbols if hasattr(circuit_app_state.trading_state, 'symbols') else []
                            total_count = circuit_app_state.trading_state.loading_progress.get("total", 0) if hasattr(circuit_app_state.trading_state, 'loading_progress') else 0
                            
                            circuit_app_state.update_loading_progress(
                                loaded=len(current_symbols),
                                total=total_count,
                                status="error"
                            )
                    except Exception as circuit_error:
                        logger.error(f"Failed to update circuit breaker status: {circuit_error}")
                    return

        # Mark loading as complete or final status
        try:
            final_app_state = get_app_state()
            if final_app_state and final_app_state.trading_state:
                current_symbols = final_app_state.trading_state.symbols if hasattr(final_app_state.trading_state, 'symbols') else []
                total_count = final_app_state.trading_state.loading_progress.get("total", 0) if hasattr(final_app_state.trading_state, 'loading_progress') else 0
                
                final_status = "complete" if len(current_symbols) >= total_count else "partial"
                logger.info(f"Background symbol loading completed with status: {final_status} ({len(current_symbols)}/{total_count} symbols loaded)")
                
                final_app_state.update_loading_progress(
                    loaded=len(current_symbols),
                    total=total_count,
                    status=final_status
                )
        except Exception as final_error:
            logger.error(f"Failed to update final loading status: {final_error}")

    except Exception as e:
        logger.error(f"Critical error in background symbol loading: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Try to update error status one final time
        try:
            error_app_state = get_app_state()
            if error_app_state and error_app_state.trading_state:
                current_symbols = error_app_state.trading_state.symbols if hasattr(error_app_state.trading_state, 'symbols') else []
                total_count = error_app_state.trading_state.loading_progress.get("total", 0) if hasattr(error_app_state.trading_state, 'loading_progress') else 0
                
                error_app_state.update_loading_progress(
                    loaded=len(current_symbols),
                    total=total_count,
                    status="error"
                )
        except Exception as inner_e:
            logger.error(f"Failed to update critical error status: {inner_e}")
