"""Web server for trading dashboard with real-time data and backtesting."""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .config import TradingConfig
from .data_provider import CoinbaseDataProvider
from .backtester import Backtester
from .trading_strategy import SimpleMovingAverageStrategy, BollingerBandsStrategy
import math
from .websocket_client import WebSocketClient
from .data_handler import DataHandler

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter for REST API calls per Coinbase documentation."""
    
    def __init__(self, max_requests_per_hour: int = 10000):
        """
        Initialize rate limiter.
        
        Args:
            max_requests_per_hour: Maximum requests per hour (default: 10,000 per Coinbase docs)
        """
        self.max_requests_per_hour = max_requests_per_hour
        self.requests: List[float] = []
        self.lock = asyncio.Lock()
    
    async def is_allowed(self) -> bool:
        """
        Check if a request is allowed under rate limiting.
        
        Returns:
            True if request is allowed, False otherwise
        """
        async with self.lock:
            current_time = time.time()
            hour_ago = current_time - 3600  # 1 hour in seconds
            
            # Remove requests older than 1 hour
            self.requests = [req_time for req_time in self.requests if req_time > hour_ago]
            
            # Check if we're under the limit
            if len(self.requests) < self.max_requests_per_hour:
                self.requests.append(current_time)
                return True
            
            return False
    
    async def get_remaining_requests(self) -> int:
        """Get the number of remaining requests in the current hour."""
        async with self.lock:
            current_time = time.time()
            hour_ago = current_time - 3600
            
            # Remove requests older than 1 hour
            self.requests = [req_time for req_time in self.requests if req_time > hour_ago]
            
            return max(0, self.max_requests_per_hour - len(self.requests))
    
    async def get_reset_time(self) -> float:
        """Get the time when the rate limit resets (in seconds from now)."""
        if not self.requests:
            return 0.0
        
        # Find the oldest request still in the window
        current_time = time.time()
        hour_ago = current_time - 3600
        valid_requests = [req_time for req_time in self.requests if req_time > hour_ago]
        
        if not valid_requests:
            return 0.0
        
        oldest_request = min(valid_requests)
        return oldest_request + 3600 - current_time


# Global rate limiter instance
rate_limiter = RateLimiter()


async def check_rate_limit():
    """Check if the request is within rate limits."""
    if not await rate_limiter.is_allowed():
        remaining = await rate_limiter.get_remaining_requests()
        reset_time = await rate_limiter.get_reset_time()
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": "Too many requests",
                "remaining_requests": remaining,
                "reset_in_seconds": reset_time
            }
        )


# Initialize FastAPI app
app = FastAPI(title="Trading Dashboard", version="1.0.0")

# Setup templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Global variables for data storage
real_time_data: Dict[str, Dict] = {}
historical_data_cache: Dict[str, List[Dict]] = {}
backtest_results: Dict[str, Dict] = {}
websocket_clients: List[WebSocket] = []

# Configuration
config = TradingConfig.from_env()


def clean_for_json(data):
    """Clean data for JSON serialization by replacing NaN and infinite values."""
    if isinstance(data, dict):
        return {k: clean_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_for_json(item) for item in data]
    elif isinstance(data, float):
        if math.isnan(data) or math.isinf(data):
            return None
        return data
    else:
        return data


# Pydantic models for API requests
class SubscriptionRequest(BaseModel):
    channel: str
    product_id: str = None

class BacktestRequest(BaseModel):
    strategy_type: str = "sma"
    product_id: str = None
    days: int = 7
    granularity: int = 3600
    stop_loss: float = 5.0
    take_profit: float = 10.0
    initial_capital: float = 10000.0
    strategy_params: dict = {}
    # Legacy parameters for backward compatibility
    short_window: int = 5
    long_window: int = 20


class WebSocketManager:
    """Manages WebSocket connections for real-time data."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.websocket_client = None
    
    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send a message to a specific WebSocket."""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: str):
        """Broadcast a message to all connected WebSockets."""
        for connection in self.active_connections.copy():
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting to connection: {e}")
                self.disconnect(connection)
    
    async def start_real_time_data(self):
        """Start the real-time data feed with all subscription types."""
        if not self.websocket_client:
            self.websocket_client = WebSocketClient(config)
            self.data_handler = DataHandler(config)
            
            # Register message handlers for Coinbase channel names
            # Per documentation: https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/websocket/websocket-channels
            self.websocket_client.register_handler('ticker', self._handle_ticker_message)
            self.websocket_client.register_handler('ticker_batch', self._handle_ticker_message)
            self.websocket_client.register_handler('level2', self._handle_level2_message)
            self.websocket_client.register_handler('candles', self._handle_candles_message)
            self.websocket_client.register_handler('status', self._handle_status_message)
            self.websocket_client.register_handler('market_trades', self._handle_market_trades_message)
            self.websocket_client.register_handler('user', self._handle_user_message)
            
            # Start the websocket client (with error handling)
            asyncio.create_task(self._run_websocket_client())
            
            # Start the data collection task
            asyncio.create_task(self._collect_real_time_data())
    
    async def _run_websocket_client(self):
        """Run the websocket client in the background."""
        try:
            await self.websocket_client.connect()
            
            # Subscribe to heartbeats first to keep connection alive
            # Per Coinbase documentation: "Use heartbeats to keep all subscriptions open"
            await self.websocket_client.subscribe_to_channel('heartbeats', [])
            
            # Subscribe to data channels
            await self.websocket_client.subscribe_to_ticker(config.product_id)
            await self.websocket_client.subscribe_to_level2(config.product_id)
            await self.websocket_client.subscribe_to_candles(config.product_id)
            
            await self.websocket_client.listen()
        except Exception as e:
            logger.error(f"WebSocket client error: {e}")
    
    async def _handle_ticker_message(self, data):
        """Handle ticker messages per Coinbase documentation format."""
        # Per documentation: ticker messages have 'events' array with 'tickers' data
        events = data.get('events', [])
        for event in events:
            if 'tickers' in event:
                for ticker in event['tickers']:
                    self.data_handler.add_ticker_data(ticker)
    
    async def _handle_level2_message(self, data):
        """Handle level2 messages per Coinbase documentation format."""
        # Per documentation: level2 messages have 'events' array with 'updates' or 'snapshot' data
        events = data.get('events', [])
        for event in events:
            if event.get('type') in ['snapshot', 'update']:
                self.data_handler.add_level2_data(event)
    
    async def _handle_candles_message(self, data):
        """Handle candles/OHLCV messages per Coinbase documentation format."""
        # Per documentation: candles messages have 'events' array with 'candles' data
        events = data.get('events', [])
        for event in events:
            if 'candles' in event:
                for candle in event['candles']:
                    self.data_handler.add_candles_data(candle)
    
    async def _handle_status_message(self, data):
        """Handle product status messages per Coinbase documentation format."""
        # Per documentation: status messages have 'events' array with 'products' data
        events = data.get('events', [])
        for event in events:
            if 'products' in event:
                for product in event['products']:
                    self.data_handler.add_status_data(product)
    
    async def _handle_market_trades_message(self, data):
        """Handle market trades messages per Coinbase documentation format."""
        # Per documentation: market_trades messages have 'events' array with 'trades' data
        events = data.get('events', [])
        for event in events:
            if 'trades' in event:
                for trade in event['trades']:
                    self.data_handler.add_market_trades_data(trade)
    
    async def _handle_user_message(self, data):
        """Handle user messages per Coinbase documentation format."""
        # Per documentation: user messages have 'events' array with user-specific data
        events = data.get('events', [])
        for event in events:
            # Handle different types of user events (orders, positions, etc.)
            if 'orders' in event:
                for order in event['orders']:
                    self.data_handler.add_trade_data(order)
            elif 'positions' in event:
                for position in event['positions']:
                    self.data_handler.add_trade_data(position)
    
    async def _collect_real_time_data(self):
        """Collect real-time data and broadcast to clients."""
        while True:
            try:
                # Check if data handler is initialized
                if not self.data_handler:
                    await asyncio.sleep(1)
                    continue
                    
                # Get latest data from data handler for all types
                ticker_data = self.data_handler.get_latest_ticker()
                trade_data = self.data_handler.get_latest_trades()
                level2_data = self.data_handler.get_latest_level2()
                candles_data = self.data_handler.get_latest_candles()
                matches_data = self.data_handler.get_latest_matches()
                status_data = self.data_handler.get_latest_status()
                market_trades_data = self.data_handler.get_latest_market_trades()
                
                # Prepare comprehensive real-time data
                current_data = {
                    'ticker': ticker_data,
                    'trades': trade_data,
                    'level2': level2_data,
                    'candles': candles_data,
                    'matches': matches_data,
                    'status': status_data,
                    'market_trades': market_trades_data,
                    'timestamp': datetime.now().isoformat()
                }
                
                # Only broadcast if we have some data
                if any([ticker_data, trade_data, level2_data, candles_data, 
                       matches_data, status_data, market_trades_data]):
                    real_time_data[config.product_id] = current_data
                    
                    # Broadcast to all connected clients
                    await self.broadcast(json.dumps({
                        'type': 'real_time_data',
                        'data': current_data
                    }))
                
                await asyncio.sleep(1)  # Update every second
                
            except Exception as e:
                logger.error(f"Error in real-time data collection: {e}")
                await asyncio.sleep(5)


# Initialize WebSocket manager
manager = WebSocketManager()
realtime_data_enabled = True  # Global flag to control real-time data collection


@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    logger.info("Starting Trading Dashboard...")
    # Start real-time data collection if enabled
    if realtime_data_enabled:
        await manager.start_real_time_data()
    else:
        logger.info("Real-time data collection is disabled")


@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    """Serve the main dashboard page."""
    return templates.TemplateResponse("dashboard_enhanced.html", {
        "request": request,
        "product_id": config.product_id
    })


@app.get("/api/real-time-data")
async def get_real_time_data(product_id: str = None):
    """Get current real-time data."""
    await check_rate_limit()
    
    if not product_id:
        product_id = config.product_id
    
    return real_time_data.get(product_id, {})


@app.get("/api/historical-data")
async def get_historical_data(
    product_id: str = None,
    days: int = 7,
    granularity: int = 3600
):
    """Get historical data for a product."""
    await check_rate_limit()
    
    if not product_id:
        product_id = config.product_id
    
    cache_key = f"{product_id}_{days}_{granularity}"
    
    if cache_key not in historical_data_cache:
        data_provider = CoinbaseDataProvider(product_id)
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        historical_data = await data_provider.get_historical_candles(
            start_time=start_time,
            end_time=end_time,
            granularity=granularity
        )
        
        historical_data_cache[cache_key] = historical_data
    
    return historical_data_cache[cache_key]

@app.get("/api/symbols")
async def get_available_symbols():
    """Get list of available trading symbols."""
    await check_rate_limit()
    
    # Common cryptocurrency symbols available on Coinbase
    symbols = [
        {"symbol": "BTC-USD", "name": "Bitcoin", "base": "BTC", "quote": "USD"},
        {"symbol": "ETH-USD", "name": "Ethereum", "base": "ETH", "quote": "USD"},
        {"symbol": "ADA-USD", "name": "Cardano", "base": "ADA", "quote": "USD"},
        {"symbol": "SOL-USD", "name": "Solana", "base": "SOL", "quote": "USD"},
        {"symbol": "DOT-USD", "name": "Polkadot", "base": "DOT", "quote": "USD"},
        {"symbol": "MATIC-USD", "name": "Polygon", "base": "MATIC", "quote": "USD"},
        {"symbol": "AVAX-USD", "name": "Avalanche", "base": "AVAX", "quote": "USD"},
        {"symbol": "LINK-USD", "name": "Chainlink", "base": "LINK", "quote": "USD"},
        {"symbol": "UNI-USD", "name": "Uniswap", "base": "UNI", "quote": "USD"},
        {"symbol": "LTC-USD", "name": "Litecoin", "base": "LTC", "quote": "USD"},
        {"symbol": "BCH-USD", "name": "Bitcoin Cash", "base": "BCH", "quote": "USD"},
        {"symbol": "XRP-USD", "name": "Ripple", "base": "XRP", "quote": "USD"},
        {"symbol": "ATOM-USD", "name": "Cosmos", "base": "ATOM", "quote": "USD"},
        {"symbol": "ALGO-USD", "name": "Algorand", "base": "ALGO", "quote": "USD"},
        {"symbol": "FIL-USD", "name": "Filecoin", "base": "FIL", "quote": "USD"},
    ]
    
    return {"symbols": symbols}

@app.get("/api/candles")
async def get_candles_data(
    product_id: str = None,
    days: int = 7,
    granularity: int = 3600
):
    """Get candles data for a product with specified granularity."""
    await check_rate_limit()
    
    if not product_id:
        product_id = config.product_id
    
    cache_key = f"candles_{product_id}_{days}_{granularity}"
    
    if cache_key not in historical_data_cache:
        data_provider = CoinbaseDataProvider(product_id)
        end_time = datetime.now()
        
        # For recent data, try smaller chunks to avoid rate limits
        if days <= 1:
            # For 1 day or less, fetch directly
            start_time = end_time - timedelta(days=days)
            candles_data = await data_provider.get_historical_candles(
                start_time=start_time,
                end_time=end_time,
                granularity=granularity
            )
        else:
            # For longer periods, fetch in chunks to get more recent data
            candles_data = []
            
            # First, try to get the most recent 24 hours
            recent_start = end_time - timedelta(hours=24)
            recent_data = await data_provider.get_historical_candles(
                start_time=recent_start,
                end_time=end_time,
                granularity=granularity
            )
            candles_data.extend(recent_data)
            
            # Then get older data if we need more
            if len(candles_data) < 24:  # If we didn't get enough recent data
                older_start = end_time - timedelta(days=days)
                older_end = recent_start
                older_data = await data_provider.get_historical_candles(
                    start_time=older_start,
                    end_time=older_end,
                    granularity=granularity
                )
                candles_data.extend(older_data)
            
            # Sort by timestamp to ensure proper order
            candles_data.sort(key=lambda x: x['timestamp'])
        
        historical_data_cache[cache_key] = candles_data
    
    return historical_data_cache[cache_key]


@app.post("/api/run-backtest")
async def run_backtest(request: BacktestRequest):
    """Run a backtest and return results."""
    await check_rate_limit()
    
    product_id = request.product_id or config.product_id
    
    try:
        # Get historical data
        data_provider = CoinbaseDataProvider(product_id)
        end_time = datetime.now()
        start_time = end_time - timedelta(days=request.days)
        
        historical_data = await data_provider.get_historical_candles(
            start_time=start_time,
            end_time=end_time,
            granularity=request.granularity
        )
        
        if not historical_data:
            return {"error": "No historical data available"}
        
        # Convert candles data to backtester format
        backtest_data = []
        for candle in historical_data:
            backtest_data.append({
                'timestamp': candle['timestamp'],
                'price': candle['close'],  # Use close price for backtesting
                'open': candle['open'],
                'high': candle['high'],
                'low': candle['low'],
                'close': candle['close'],
                'volume': candle['volume']
            })
        
        # Select strategy class based on strategy_type
        strategy_class = SimpleMovingAverageStrategy  # Default
        if request.strategy_type == "ema":
            # For now, use SMA as EMA is not implemented
            strategy_class = SimpleMovingAverageStrategy
        elif request.strategy_type == "rsi":
            # For now, use SMA as RSI is not implemented
            strategy_class = SimpleMovingAverageStrategy
        elif request.strategy_type == "bollinger":
            strategy_class = BollingerBandsStrategy
        
        # Use strategy_params if provided, otherwise fall back to legacy parameters
        if request.strategy_params:
            strategy_params = request.strategy_params
        else:
            # Default parameters based on strategy type
            if request.strategy_type == "bollinger":
                strategy_params = {
                    'period': 20,
                    'std_dev': 2.0
                }
            else:
                strategy_params = {
                    'short_window': request.short_window,
                    'long_window': request.long_window
                }
        
        # Create backtester
        backtester = Backtester(
            config=config,
            strategy_class=strategy_class,
            strategy_params=strategy_params
        )
        
        # Run backtest
        result = await backtester.run_backtest(backtest_data)
        
        # Store results
        backtest_key = f"{product_id}_{request.strategy_type}_{request.days}_{request.granularity}_{hash(str(strategy_params))}"
        
        # Clean data for JSON serialization
        trades_data = clean_for_json(backtester.get_trades_df().to_dict('records'))
        equity_data = clean_for_json(backtester.get_equity_curve_df().to_dict('records'))
        result_data = clean_for_json(result.__dict__)  # Convert dataclass to dict
        
        backtest_results[backtest_key] = {
            'result': result_data,
            'trades_df': trades_data,
            'equity_df': equity_data,
            'timestamp': datetime.now().isoformat()
        }
        
        return {
            'success': True,
            'result': result_data,
            'trades': trades_data,
            'equity_curve': equity_data,
            'backtest_key': backtest_key
        }
        
    except Exception as e:
        logger.error(f"Backtest error: {e}")
        import traceback
        logger.error(f"Backtest traceback: {traceback.format_exc()}")
        return {"error": str(e), "details": traceback.format_exc()}


@app.get("/api/backtest-results")
async def get_backtest_results():
    """Get all backtest results."""
    return backtest_results


@app.get("/api/trading-metrics")
async def get_trading_metrics():
    """Get trading performance metrics."""
    if not real_time_data.get(config.product_id):
        return {"error": "No real-time data available"}
    
    # Calculate basic metrics from real-time data
    ticker = real_time_data[config.product_id].get('ticker', {})
    
    metrics = {
        'current_price': float(ticker.get('price', 0)),
        'price_change_24h': float(ticker.get('price_change_24h', 0)),
        'volume_24h': float(ticker.get('volume_24h', 0)),
        'timestamp': real_time_data[config.product_id].get('timestamp'),
        'total_backtests': len(backtest_results),
        'best_backtest': None
    }
    
    # Find best performing backtest
    if backtest_results:
        best_result = max(backtest_results.values(), 
                         key=lambda x: x['result'].total_return)
        metrics['best_backtest'] = {
            'total_return': best_result['result'].total_return,
            'win_rate': best_result['result'].win_rate,
            'total_trades': best_result['result'].total_trades,
            'timestamp': best_result['timestamp']
        }
    
    return metrics


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time data."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/api/subscriptions")
async def get_subscriptions():
    """Get current WebSocket subscription information."""
    await check_rate_limit()
    
    if manager.websocket_client:
        return await manager.websocket_client.get_subscription_info()
    return {"error": "WebSocket client not initialized"}

@app.get("/api/rate-limit")
async def get_rate_limit_status():
    """Get current rate limit status."""
    remaining_requests = await rate_limiter.get_remaining_requests()
    reset_time = await rate_limiter.get_reset_time()
    
    return {
        "limit_per_hour": 10000,
        "remaining_requests": remaining_requests,
        "reset_in_seconds": reset_time,
        "reset_in_minutes": round(reset_time / 60, 2) if reset_time > 0 else 0,
        "compliance": "Coinbase App API Rate Limiting - 10,000 requests per hour per API key"
    }


@app.get("/api/realtime-status")
async def get_realtime_status():
    """Get real-time data collection status."""
    return {
        "enabled": realtime_data_enabled,
        "websocket_connected": manager.websocket_client is not None and manager.websocket_client.connected if manager.websocket_client else False,
        "active_connections": len(manager.active_connections)
    }


@app.post("/api/toggle-realtime")
async def toggle_realtime_data():
    """Toggle real-time data collection on/off."""
    global realtime_data_enabled
    
    if realtime_data_enabled:
        # Stop real-time data collection
        realtime_data_enabled = False
        if manager.websocket_client:
            await manager.websocket_client.disconnect()
            manager.websocket_client = None
        logger.info("Real-time data collection stopped")
        return {"status": "stopped", "message": "Real-time data collection has been stopped"}
    else:
        # Start real-time data collection
        realtime_data_enabled = True
        await manager.start_real_time_data()
        logger.info("Real-time data collection started")
        return {"status": "started", "message": "Real-time data collection has been started"}

@app.post("/api/subscribe")
async def subscribe_to_channel(request: SubscriptionRequest):
    """Subscribe to a specific channel for a product."""
    if not manager.websocket_client:
        return {"error": "WebSocket client not initialized"}
    
    product_id = request.product_id or config.product_id
    
    try:
        await manager.websocket_client.subscribe_to_channel(request.channel, [product_id])
        return {"success": True, "channel": request.channel, "product_id": product_id}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/unsubscribe")
async def unsubscribe_from_channel(request: SubscriptionRequest):
    """Unsubscribe from a specific channel for a product."""
    if not manager.websocket_client:
        return {"error": "WebSocket client not initialized"}
    
    product_id = request.product_id or config.product_id
    
    try:
        await manager.websocket_client.unsubscribe_from_channel(request.channel, [product_id])
        return {"success": True, "channel": request.channel, "product_id": product_id}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/data-summary")
async def get_data_summary():
    """Get summary of all collected data."""
    if not manager.data_handler:
        return {"error": "Data handler not initialized"}
    
    return manager.data_handler.get_summary_stats()

@app.get("/api/available-channels")
async def get_available_channels():
    """Get list of available WebSocket channels."""
    return {
        "channels": WebSocketClient.AVAILABLE_CHANNELS,
        "description": "Available WebSocket subscription channels from Coinbase Advanced Trading API"
    }

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    await check_rate_limit()
    
    remaining_requests = await rate_limiter.get_remaining_requests()
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_connections": len(manager.active_connections),
        "cached_data_points": len(historical_data_cache),
        "backtest_results": len(backtest_results),
        "websocket_connected": manager.websocket_client is not None and manager.websocket_client.running,
        "data_handler_initialized": manager.data_handler is not None,
        "rate_limit": {
            "remaining_requests": remaining_requests,
            "limit_per_hour": 10000
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
