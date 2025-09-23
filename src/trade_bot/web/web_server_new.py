"""New modular web server using component architecture."""

import os
import asyncio
import logging
from fastapi import FastAPI, Request, WebSocket, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Dict, Any, Optional

from ..core.config import TradingConfig
from ..data.data_provider import CoinbaseDataProvider
from ..data.cached_data_provider import CachedDataProvider
from ..data.product_fetcher import ProductFetcher
from ..database.database_manager import DatabaseManager
from ..trading.simulated_trading_manager import SimulatedTradingManager
from ..data.websocket_client import WebSocketClient
from ..data.data_handler import DataHandler
from ..web.web_components import RateLimiter, WebSocketManager
from ..web.web_handlers import (
    APIHandlers, DashboardHandlers, BacktestHandlers, 
    TradingHandlers, WebSocketHandlers, DataHandlers
)
from ..web.web_handlers.live_portfolio_handlers import LivePortfolioHandlers

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models
class SubscriptionRequest(BaseModel):
    channel: str
    product_id: Optional[str] = None

class BacktestRequest(BaseModel):
    strategy: str
    symbol: str
    start_date: str
    end_date: str
    strategy_params: Dict[str, Any] = {}

class BacktestHistoryItem(BaseModel):
    backtest_id: int
    strategy: str
    symbol: str
    start_date: str
    end_date: str
    total_trades: int
    win_rate: float
    total_return: float
    created_at: str

class BacktestHistoryResponse(BaseModel):
    backtests: list[BacktestHistoryItem]
    total: int
    limit: int
    offset: int

class BacktestStatsResponse(BaseModel):
    total_backtests: int
    successful_backtests: int
    average_return: float
    best_strategy: str

# Global rate limiter instance
rate_limiter = RateLimiter()

# Global WebSocket manager (will be initialized in startup)
websocket_manager = None

# Global trading state
trading_state = {
    "is_trading": False,
    "active_strategy": None,
    "symbols": [],
    "session_id": None
}

# Global data handler
data_handler = None

# Global simulated trading manager
simulated_trading_manager = None

# Global database manager
database_manager = None

# Global WebSocket client
websocket_client = None

# Global handlers
api_handlers = None
dashboard_handlers = None
backtest_handlers = None
trading_handlers = None
websocket_handlers = None
data_handlers = None
live_portfolio_handlers = None

# FastAPI app
app = FastAPI(title="Trading Dashboard API", version="1.0.0")

# Helper function to check if handlers are ready
def check_handlers_ready(handlers_name: str, handlers):
    """Check if handlers are ready, raise HTTPException if not."""
    if handlers is None:
        raise HTTPException(status_code=503, detail=f"Server not ready - {handlers_name} not initialized")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    global data_handler, simulated_trading_manager, database_manager, websocket_client
    global api_handlers, dashboard_handlers, backtest_handlers, trading_handlers
    global websocket_handlers, data_handlers, websocket_manager, live_portfolio_handlers
    
    try:
        # Initialize configuration
        config = TradingConfig(
            api_key=os.getenv('COINBASE_API_KEY', ''),
            api_secret=os.getenv('COINBASE_API_SECRET', ''),
            passphrase=os.getenv('COINBASE_PASSPHRASE', '')
        )
        
        # Initialize core components
        data_provider = CoinbaseDataProvider(config)
        cached_data_provider = CachedDataProvider(config)
        product_fetcher = ProductFetcher()
        database_manager = DatabaseManager()
        simulated_trading_manager = SimulatedTradingManager(
            initial_balance=10000.0,
            db_manager=database_manager
        )
        data_handler = DataHandler(config)
        websocket_client = WebSocketClient(config)
        websocket_manager = WebSocketManager(config)
        
        # Initialize handlers
        api_handlers = APIHandlers(config, data_provider, cached_data_provider, product_fetcher, database_manager, simulated_trading_manager)
        dashboard_handlers = DashboardHandlers(config, templates)
        backtest_handlers = BacktestHandlers(config, database_manager)
        trading_handlers = TradingHandlers(config, simulated_trading_manager, database_manager)
        websocket_handlers = WebSocketHandlers(websocket_manager)
        data_handlers = DataHandlers(config, data_provider, cached_data_provider, database_manager, simulated_trading_manager, trading_handlers, trading_state)
        live_portfolio_handlers = LivePortfolioHandlers(config)
        logger.info(f"✅ Live portfolio handlers initialized: {live_portfolio_handlers is not None}")
        
        # Start WebSocket client
        # Note: WebSocket client will be started when needed
        
        logger.info("🚀 Trading Dashboard started successfully!")
        logger.info("📊 Dashboard available at: http://localhost:8001")
        logger.info("🔌 WebSocket endpoint: ws://localhost:8001/ws")
        logger.info("📈 API documentation: http://localhost:8001/docs")
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise

# API Routes
@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    """Serve the main dashboard page."""
    check_handlers_ready("dashboard_handlers", dashboard_handlers)
    return await dashboard_handlers.get_dashboard(request)

@app.get("/favicon.ico")
async def favicon():
    """Serve favicon."""
    from fastapi.responses import Response
    return Response(content="", media_type="image/x-icon")

@app.get("/api/real-time-data")
async def get_real_time_data(product_id: str = None):
    """Get real-time market data."""
    check_handlers_ready("dashboard_handlers", dashboard_handlers)
    check_handlers_ready("dashboard_handlers", dashboard_handlers)
    return await dashboard_handlers.get_real_time_data(product_id)

@app.get("/api/historical-data")
async def get_historical_data(product_id: str, start_time: str = None, end_time: str = None, granularity: int = 3600, days: int = 7):
    """Get historical market data."""
    check_handlers_ready("dashboard_handlers", dashboard_handlers)
    
    # If start_time and end_time are not provided, calculate from days
    if start_time is None or end_time is None:
        from datetime import datetime, timedelta
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        start_time = start_time.isoformat()
        end_time = end_time.isoformat()
    
    return await dashboard_handlers.get_historical_data(product_id, start_time, end_time, granularity)

@app.get("/api/symbols")
async def get_available_symbols():
    """Get available trading symbols."""
    check_handlers_ready("api_handlers", api_handlers)
    return await api_handlers.get_available_symbols()

@app.get("/api/products")
async def get_available_products():
    """Get available products for trading."""
    check_handlers_ready("api_handlers", api_handlers)
    return await api_handlers.get_available_products()

@app.get("/api/channels")
async def get_available_channels():
    """Get available WebSocket channels."""
    check_handlers_ready("api_handlers", api_handlers)
    return await api_handlers.get_available_channels()

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    check_handlers_ready("api_handlers", api_handlers)
    return await api_handlers.health_check()

# Backtest Routes
@app.post("/api/backtest")
async def run_backtest(request: BacktestRequest):
    """Run a backtest with the specified parameters."""
    check_handlers_ready("backtest_handlers", backtest_handlers)
    return await backtest_handlers.run_backtest(request.dict())

@app.get("/api/backtest/results")
async def get_backtest_results():
    """Get all backtest results."""
    check_handlers_ready("backtest_handlers", backtest_handlers)
    return await backtest_handlers.get_backtest_results()

@app.get("/api/backtest/history")
async def get_backtest_history(limit: int = 10, offset: int = 0):
    """Get backtest history with pagination."""
    check_handlers_ready("backtest_handlers", backtest_handlers)
    return await backtest_handlers.get_backtest_history(limit, offset)

@app.get("/api/backtest/{backtest_id}")
async def get_backtest(backtest_id: int):
    """Get a specific backtest by ID."""
    check_handlers_ready("backtest_handlers", backtest_handlers)
    return await backtest_handlers.get_backtest(backtest_id)

@app.get("/api/backtest/stats")
async def get_backtest_stats():
    """Get backtest statistics."""
    check_handlers_ready("backtest_handlers", backtest_handlers)
    return await backtest_handlers.get_backtest_stats()

@app.delete("/api/backtest/{backtest_id}")
async def delete_backtest(backtest_id: int):
    """Delete a backtest."""
    check_handlers_ready("backtest_handlers", backtest_handlers)
    return await backtest_handlers.delete_backtest(backtest_id)

@app.get("/api/backtest/filters")
async def get_backtest_filters():
    """Get available backtest filters."""
    check_handlers_ready("backtest_handlers", backtest_handlers)
    return await backtest_handlers.get_backtest_filters()

# Trading Routes
@app.post("/api/trading/live/start")
async def start_live_trading(request: dict):
    """Start live trading session."""
    check_handlers_ready("trading_handlers", trading_handlers)
    return await trading_handlers.start_live_trading(request)

@app.post("/api/trading/live/stop")
async def stop_live_trading(request: dict):
    """Stop live trading session."""
    check_handlers_ready("trading_handlers", trading_handlers)
    return await trading_handlers.stop_live_trading(request)

@app.get("/api/trading/live/positions")
async def get_live_positions():
    """Get current live trading positions."""
    check_handlers_ready("trading_handlers", trading_handlers)
    return await trading_handlers.get_live_positions()

@app.post("/api/trading/live/close-position")
async def close_live_position(request: dict):
    """Close a specific live trading position."""
    check_handlers_ready("trading_handlers", trading_handlers)
    return await trading_handlers.close_live_position(request)

@app.get("/api/trading/live/history")
async def get_live_trading_history():
    """Get live trading history."""
    check_handlers_ready("trading_handlers", trading_handlers)
    return await trading_handlers.get_live_trading_history()

@app.post("/api/trading/simulated/start")
async def start_simulated_trading(request: dict):
    """Start simulated trading session."""
    check_handlers_ready("trading_handlers", trading_handlers)
    return await trading_handlers.start_simulated_trading(request)

@app.post("/api/async-trading/start")
async def start_async_trading(request: dict):
    """Start async trading session with progressive symbol loading."""
    check_handlers_ready("trading_handlers", trading_handlers)
    
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
        
        # Update global trading state
        trading_state["is_trading"] = True
        trading_state["active_strategy"] = strategy_type
        trading_state["symbols"] = initial_symbols
        trading_state["session_id"] = session_id
        trading_state["loading_progress"] = {
            "status": "loading",
            "loaded": len(initial_symbols),
            "total": len(symbols),
            "remaining": len(remaining_symbols),
            "progress": int((len(initial_symbols) / len(symbols)) * 100) if symbols else 100
        }
        
        # Start simulated trading with initial symbols
        await trading_handlers.start_simulated_trading({
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
            "loading_progress": trading_state["loading_progress"],
            "trading_active": True
        }
        
    except Exception as e:
        logger.error(f"Error starting async trading: {e}")
        return {"error": str(e)}

@app.get("/api/async-trading/loading-status")
async def get_async_trading_loading_status():
    """Get async trading loading status (alternative endpoint)."""
    try:
        return {
            "loading_progress": trading_state.get("loading_progress", {
                "status": "complete",
                "loaded": 0,
                "total": 0,
                "remaining": 0,
                "progress": 100
            }),
            "current_symbols": trading_state.get("symbols", []),
            "is_loading": trading_state.get("loading_progress", {}).get("status") == "loading"
        }
    except Exception as e:
        logger.error(f"Error getting loading status: {e}")
        return {"error": str(e)}

@app.get("/api/data/load-universe")
async def load_universe_data(symbols: str = None):
    """Load data for universe of symbols."""
    check_handlers_ready("data_handlers", data_handlers)
    if symbols:
        symbol_list = symbols.split(',')
        return await data_handlers.load_remaining_symbols_async(symbol_list, 3)
    else:
        return {"status": "error", "message": "No symbols provided"}

@app.get("/api/data/load-symbols")
async def load_symbols_data(symbols: str = None):
    """Load data for symbols (alternative endpoint)."""
    check_handlers_ready("data_handlers", data_handlers)
    if symbols:
        symbol_list = symbols.split(',')
        return await data_handlers.load_remaining_symbols_async(symbol_list, 3)
    else:
        return {"status": "error", "message": "No symbols provided"}

@app.post("/api/trading/simulated/stop")
async def stop_simulated_trading():
    """Stop simulated trading session."""
    check_handlers_ready("trading_handlers", trading_handlers)
    return await trading_handlers.stop_simulated_trading()

@app.get("/api/trading/simulated/status")
async def get_simulated_trading_status():
    """Get simulated trading status."""
    check_handlers_ready("trading_handlers", trading_handlers)
    return await trading_handlers.get_simulated_trading_status()

@app.get("/api/simulated-trading/status")
async def get_simulated_trading_status_alt():
    """Alternative endpoint for simulated trading status."""
    check_handlers_ready("trading_handlers", trading_handlers)
    return await trading_handlers.get_simulated_trading_status()

@app.post("/api/trading/simulated/process-signals")
async def process_simulated_signals(request: dict):
    """Process simulated trading signals."""
    check_handlers_ready("trading_handlers", trading_handlers)
    return await trading_handlers.process_simulated_signals(request)

@app.post("/api/trading/simulated/reset")
async def reset_simulated_trading():
    """Reset simulated trading session."""
    check_handlers_ready("trading_handlers", trading_handlers)
    return await trading_handlers.reset_simulated_trading()

@app.post("/api/trading/simulated/add-symbols")
async def add_symbols_to_trading(request: dict):
    """Add symbols to current trading session."""
    check_handlers_ready("trading_handlers", trading_handlers)
    return await trading_handlers.add_symbols_to_trading(request)

# WebSocket Routes
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket connections."""
    if websocket_handlers is None:
        await websocket.close(code=1011, reason="Server not ready")
        return
    await websocket_handlers.websocket_endpoint(websocket)

@app.get("/api/websocket/subscriptions")
async def get_subscriptions():
    """Get current WebSocket subscriptions."""
    if websocket_handlers is None:
        raise HTTPException(status_code=503, detail="Server not ready")
    check_handlers_ready("websocket_handlers", websocket_handlers)
    return await websocket_handlers.get_subscriptions()

@app.post("/api/websocket/subscribe")
async def subscribe_to_channel(request: SubscriptionRequest):
    """Subscribe to a WebSocket channel."""
    check_handlers_ready("websocket_handlers", websocket_handlers)
    check_handlers_ready("websocket_handlers", websocket_handlers)
    return await websocket_handlers.subscribe_to_channel(request.dict())

@app.post("/api/websocket/unsubscribe")
async def unsubscribe_from_channel(request: SubscriptionRequest):
    """Unsubscribe from a WebSocket channel."""
    check_handlers_ready("websocket_handlers", websocket_handlers)
    check_handlers_ready("websocket_handlers", websocket_handlers)
    return await websocket_handlers.unsubscribe_from_channel(request.dict())

@app.get("/api/websocket/status")
async def get_realtime_status():
    """Get real-time data status."""
    check_handlers_ready("websocket_handlers", websocket_handlers)
    check_handlers_ready("websocket_handlers", websocket_handlers)
    return await websocket_handlers.get_realtime_status()

@app.post("/api/websocket/toggle")
async def toggle_realtime_data():
    """Toggle real-time data streaming."""
    check_handlers_ready("websocket_handlers", websocket_handlers)
    check_handlers_ready("websocket_handlers", websocket_handlers)
    return await websocket_handlers.toggle_realtime_data()

# Data Routes
@app.get("/api/data/cache-stats")
async def get_cache_stats():
    """Get cache statistics."""
    check_handlers_ready("data_handlers", data_handlers)
    return await data_handlers.get_cache_stats()

@app.get("/api/data/orderbook-signals")
async def get_live_orderbook_signals(symbols: str = None, page: int = 1, per_page: int = 10):
    """Get live order book signals."""
    check_handlers_ready("data_handlers", data_handlers)
    return await data_handlers.get_live_orderbook_signals(symbols, page, per_page)

@app.get("/api/orderbook/live-signals")
async def get_orderbook_live_signals(symbols: str = None, page: int = 1, per_page: int = 10):
    """Get live order book signals (alternative endpoint)."""
    check_handlers_ready("data_handlers", data_handlers)
    return await data_handlers.get_live_orderbook_signals(symbols, page, per_page)

@app.get("/api/data/loading-status")
async def get_loading_status():
    """Get data loading status."""
    check_handlers_ready("data_handlers", data_handlers)
    return await data_handlers.get_loading_status()

@app.post("/api/data/load-symbols")
async def load_remaining_symbols_async(request: dict):
    """Load remaining symbols asynchronously."""
    remaining_symbols = request.get('remaining_symbols', [])
    batch_size = request.get('batch_size', 3)
    check_handlers_ready("data_handlers", data_handlers)
    return await data_handlers.load_remaining_symbols_async(remaining_symbols, batch_size)

@app.get("/api/data/trading-state")
async def get_trading_state():
    """Get current trading state."""
    check_handlers_ready("data_handlers", data_handlers)
    return await data_handlers.get_trading_state()

@app.post("/api/data/save-session")
async def save_session_state(request: dict):
    """Save trading session state."""
    print(f"DEBUG: save_session_state endpoint called with request: {request}")
    check_handlers_ready("data_handlers", data_handlers)
    print(f"DEBUG: data_handlers is ready, calling save_session_state")
    result = await data_handlers.save_session_state(request)
    print(f"DEBUG: save_session_state result: {result}")
    return result

@app.post("/api/data/restore-trading")
async def restore_simulated_trading(request: dict):
    """Restore simulated trading from saved state."""
    check_handlers_ready("data_handlers", data_handlers)
    return await data_handlers.restore_simulated_trading(request)

@app.get("/api/data/load-session/{session_id}")
async def load_session_state(session_id: str):
    """Load trading session state."""
    check_handlers_ready("data_handlers", data_handlers)
    return await data_handlers.load_session_state(session_id)

@app.post("/api/data/save-dashboard")
async def save_dashboard_state(request: dict):
    """Save dashboard UI state."""
    check_handlers_ready("data_handlers", data_handlers)
    return await data_handlers.save_dashboard_state(request)

@app.get("/api/data/load-dashboard/{session_id}")
async def load_dashboard_state(session_id: str):
    """Load dashboard UI state."""
    check_handlers_ready("data_handlers", data_handlers)
    return await data_handlers.load_dashboard_state(session_id)

# Metrics Routes
@app.get("/api/metrics/trading")
async def get_trading_metrics():
    """Get trading performance metrics."""
    check_handlers_ready("dashboard_handlers", dashboard_handlers)
    return await dashboard_handlers.get_trading_metrics()

@app.get("/api/metrics/data-summary")
async def get_data_summary():
    """Get data summary statistics."""
    check_handlers_ready("dashboard_handlers", dashboard_handlers)
    return await dashboard_handlers.get_data_summary()

@app.get("/api/data-summary")
async def get_data_summary_alt():
    """Alternative endpoint for data summary statistics."""
    check_handlers_ready("dashboard_handlers", dashboard_handlers)
    return await dashboard_handlers.get_data_summary()

# Additional missing endpoints
@app.get("/api/subscriptions")
async def get_subscriptions_alt():
    """Alternative endpoint for subscriptions."""
    check_handlers_ready("websocket_handlers", websocket_handlers)
    check_handlers_ready("websocket_handlers", websocket_handlers)
    return await websocket_handlers.get_subscriptions()

@app.get("/api/realtime-status")
async def get_realtime_status_alt():
    """Alternative endpoint for realtime status."""
    check_handlers_ready("websocket_handlers", websocket_handlers)
    check_handlers_ready("websocket_handlers", websocket_handlers)
    return await websocket_handlers.get_realtime_status()

@app.get("/api/trades/stats")
async def get_trades_stats():
    """Get trading statistics."""
    check_handlers_ready("trading_handlers", trading_handlers)
    check_handlers_ready("trading_handlers", trading_handlers)
    return await trading_handlers.get_simulated_trading_status()

@app.get("/api/trades/paginated")
async def get_trades_paginated(page: int = 1, per_page: int = 10, session_id: str = None):
    """Get paginated trades."""
    check_handlers_ready("trading_handlers", trading_handlers)
    check_handlers_ready("trading_handlers", trading_handlers)
    return await trading_handlers.get_live_trading_history()

@app.get("/api/session/active")
async def get_active_session():
    """Get active session."""
    check_handlers_ready("data_handlers", data_handlers)
    return await data_handlers.get_trading_state()

@app.post("/api/session/save")
async def save_session(request: dict):
    """Save trading session (alternative endpoint)."""
    check_handlers_ready("data_handlers", data_handlers)
    return await data_handlers.save_session_state(request)

@app.post("/api/session/save-dashboard")
async def save_dashboard_session(request: dict):
    """Save dashboard session (alternative endpoint)."""
    check_handlers_ready("data_handlers", data_handlers)
    return await data_handlers.save_dashboard_state(request)

@app.get("/api/trades/session/{session_id}")
async def get_session_trades(session_id: str):
    """Get trades for a specific session."""
    check_handlers_ready("trading_handlers", trading_handlers)
    return await trading_handlers.get_session_trading_history(session_id)

@app.get("/api/trading/history/all")
async def get_all_trading_history(limit: int = 1000, offset: int = 0):
    """Get all trading history from database."""
    check_handlers_ready("trading_handlers", trading_handlers)
    return await trading_handlers.get_all_trading_history(limit=limit, offset=offset)

@app.get("/api/trading/metrics")
async def get_trading_metrics():
    """Get comprehensive trading metrics."""
    check_handlers_ready("trading_handlers", trading_handlers)
    return await trading_handlers.get_trading_metrics()

# Live Portfolio Endpoints
@app.get("/api/live-portfolio/status")
async def get_live_portfolio_status():
    """Get live portfolio status from Coinbase API."""
    check_handlers_ready("live_portfolio_handlers", live_portfolio_handlers)
    return await live_portfolio_handlers.get_live_portfolio_status()

@app.get("/api/live-portfolio/summary")
async def get_live_portfolio_summary():
    """Get live portfolio summary formatted for frontend."""
    check_handlers_ready("live_portfolio_handlers", live_portfolio_handlers)
    return await live_portfolio_handlers.get_portfolio_summary_for_frontend()

@app.get("/api/live-portfolio/accounts")
async def get_live_portfolio_accounts(account_uuid: str = None):
    """Get live portfolio account details."""
    check_handlers_ready("live_portfolio_handlers", live_portfolio_handlers)
    return await live_portfolio_handlers.get_account_details(account_uuid)

@app.get("/api/candles")
async def get_candles(product_id: str, granularity: int, days: int = 7):
    """Get candle data."""
    check_handlers_ready("dashboard_handlers", dashboard_handlers)
    from datetime import datetime, timedelta
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    check_handlers_ready("dashboard_handlers", dashboard_handlers)
    return await dashboard_handlers.get_candles_data(
        product_id, 
        start_time.isoformat(), 
        end_time.isoformat(), 
        granularity
    )

async def load_remaining_symbols_background(remaining_symbols: list, batch_size: int = 3):
    """Background task to load remaining symbols progressively."""
    try:
        logger.info(f"Starting background loading of {len(remaining_symbols)} symbols")
        
        # Process symbols in batches
        for i in range(0, len(remaining_symbols), batch_size):
            batch = remaining_symbols[i:i + batch_size]
            
            # Add batch to trading
            await trading_handlers.add_symbols_to_trading({"symbols": batch})
            
            # Update trading state
            current_symbols = trading_state.get("symbols", [])
            trading_state["symbols"] = current_symbols + batch
            
            # Update loading progress
            loaded_count = len(trading_state["symbols"])
            total_count = trading_state["loading_progress"]["total"]
            remaining_count = len(remaining_symbols) - (i + len(batch))
            
            trading_state["loading_progress"] = {
                "status": "loading" if remaining_count > 0 else "complete",
                "loaded": loaded_count,
                "total": total_count,
                "remaining": remaining_count,
                "progress": int((loaded_count / total_count) * 100) if total_count > 0 else 100
            }
            
            # Wait between batches to avoid overwhelming the system
            await asyncio.sleep(2.0)
            
            logger.info(f"Loaded batch {i//batch_size + 1}: {batch}")
        
        # Mark loading as complete
        trading_state["loading_progress"]["status"] = "complete"
        
        logger.info("Background symbol loading completed")
        
    except Exception as e:
        logger.error(f"Error in background symbol loading: {e}")
        trading_state["loading_progress"]["status"] = "error"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "trade_bot.web_server_new:app",
        host="0.0.0.0",
        port=8001,
        log_level="info",
        reload=True
    )
