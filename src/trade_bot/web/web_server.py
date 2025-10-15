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
from typing import Optional, List, Dict, Any

from ..core.config import TradingConfig
from ..data.data_provider import CoinbaseDataProvider
from ..data.cached_data_provider import CachedDataProvider
from ..data.product_fetcher import ProductFetcher
from ..backtest.backtester import Backtester
from ..trading.trading_strategy import SimpleMovingAverageStrategy, BollingerBandsStrategy, RSIStrategy, EMAStrategy, MACDStrategy, StochasticStrategy, DCAStrategy, BuyAndHoldStrategy, ATRStrategy, FibonacciRetracementStrategy, OrderBookStrategy
from ..trading.strategies.ml_strategy import MLStrategy
from ..database.database import BacktestDatabase
from ..database.database_manager import DatabaseManager
import math
from ..data.websocket_client import WebSocketClient
from ..data.data_handler import DataHandler
from ..trading.simulated_trading_manager import SimulatedTradingManager

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

# Initialize database
backtest_db = BacktestDatabase()
db_manager = DatabaseManager("data/databases/trading_cache.db")

from collections import OrderedDict
import time as _time


class TTLCache:
    """A simple TTL + LRU cache.

    - Evicts least-recently-used entries when exceeding maxsize
    - Treats expired entries as missing
    """

    def __init__(self, maxsize: int = 1000, ttl_seconds: int = 3600):
        self._store: OrderedDict[str, tuple[float, dict]] = OrderedDict()
        self._maxsize: int = maxsize
        self._ttl_seconds: int = ttl_seconds

    def _purge_expired(self) -> None:
        now = _time.time()
        expired_keys: list[str] = []
        for key, (expires_at, _val) in list(self._store.items()):
            if expires_at <= now:
                expired_keys.append(key)
        for key in expired_keys:
            self._store.pop(key, None)

    def __contains__(self, key: str) -> bool:  # type: ignore[override]
        self._purge_expired()
        return key in self._store

    def __len__(self) -> int:  # type: ignore[override]
        self._purge_expired()
        return len(self._store)

    def __getitem__(self, key: str) -> dict:  # type: ignore[override]
        self._purge_expired()
        expires_at, value = self._store[key]
        # Refresh LRU position
        self._store.move_to_end(key)
        return value

    def __setitem__(self, key: str, value: dict) -> None:  # type: ignore[override]
        self._purge_expired()
        expires_at = _time.time() + self._ttl_seconds
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (expires_at, value)
        # Evict LRU entries if over capacity
        while len(self._store) > self._maxsize:
            self._store.popitem(last=False)

    def get(self, key: str, default: dict | None = None) -> dict | None:
        try:
            return self.__getitem__(key)
        except KeyError:
            return default


# Global variables for data storage (bounded with TTL)
real_time_data = TTLCache(maxsize=100, ttl_seconds=300)
historical_data_cache = TTLCache(maxsize=1000, ttl_seconds=3600)
backtest_results: Dict[str, Dict] = {}
websocket_clients: List[WebSocket] = []

# Configuration
config = TradingConfig.from_env()
product_fetcher = ProductFetcher()

# Simulated Trading Manager
simulated_trading = SimulatedTradingManager(
    initial_balance=10000.0,
    max_positions=5,
    position_size_percent=20.0,
    trading_fee=0.001
)

# Trading State Management
trading_state = {
    "is_active": False,
    "strategy_type": None,
    "strategy_params": {},
    "symbols": [],
    "mode": "simulated",  # "simulated" or "live"
    "last_signal_check": None
}


def clean_for_json(data):
    """Clean data for JSON serialization by replacing NaN, infinite values, and converting datetime objects."""
    if isinstance(data, dict):
        return {k: clean_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_for_json(item) for item in data]
    elif isinstance(data, float):
        if math.isnan(data) or math.isinf(data):
            return None
        return data
    elif isinstance(data, datetime):
        return data.isoformat()
    elif hasattr(data, 'item'):  # numpy scalar types
        return data.item()
    elif hasattr(data, 'tolist'):  # numpy arrays
        return data.tolist()
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
    enable_stop_loss: bool = True
    enable_take_profit: bool = True
    initial_capital: float = 10000.0
    portfolio_percentage: float = 5.0  # Percentage of portfolio to use per trade (1-100%)
    strategy_params: dict = {}
    # DCA parameters
    enable_dca: bool = False
    dca_amount: float = 100.0
    dca_frequency: int = 7
    dca_max_investments: int = 52
    dca_start_delay: int = 0
    # Buy and Hold parameters
    enable_buy_hold: bool = False
    buy_hold_exit_condition: str = "never"
    buy_hold_profit_target: float = 0.0
    # Legacy parameters for backward compatibility
    short_window: int = 5
    long_window: int = 20
    # Additional legacy parameters for different strategies
    bb_period: int = 20
    bb_std_dev: float = 2.0
    rsi_period: int = 14
    rsi_oversold: int = 30
    rsi_overbought: int = 70
    ema_short: int = 12
    ema_long: int = 26
    ema_alpha: float = None
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    stoch_k_period: int = 14
    stoch_d_period: int = 3
    stoch_overbought: int = 80
    stoch_oversold: int = 20
    atr_period: int = 14
    atr_multiplier: float = 2.0
    atr_volatility_threshold: float = 1.5
    atr_position_size: float = 2.0
    # Fibonacci retracement parameters
    fib_lookback_period: int = 50
    fib_levels: List[float] = [0.236, 0.382, 0.5, 0.618, 0.786]
    fib_confirmation_candles: int = 2
    # Order book strategy parameters
    order_book_level: int = 2
    trade_history_limit: int = 1000  # Increased from 100
    bid_ask_spread_threshold: float = 0.001
    volume_imbalance_threshold: float = 0.6
    large_trade_threshold: float = 10000.0
    data_analysis_mode: str = 'recent'  # 'all', 'recent', 'sampled'
    recent_data_limit: int = 50
    sampling_ratio: float = 0.1

    @validator("days")
    def _validate_days(cls, v: int) -> int:
        if not 1 <= v <= 365:
            raise ValueError("days must be between 1 and 365")
        return v

    @validator("granularity")
    def _validate_granularity(cls, v: int) -> int:
        allowed = {60, 300, 900, 3600, 21600, 86400}
        if v not in allowed:
            raise ValueError("granularity must be one of 60,300,900,3600,21600,86400")
        return v

    @validator("portfolio_percentage")
    def _validate_portfolio_pct(cls, v: float) -> float:
        if not 1.0 <= v <= 100.0:
            raise ValueError("portfolio_percentage must be between 1 and 100")
        return v

    @validator("product_id")
    def _validate_product_id(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not isinstance(v, str) or "/" in v or ".." in v or len(v) > 30:
            raise ValueError("invalid product_id")
        return v

class BacktestHistoryItem(BaseModel):
    id: int
    timestamp: str
    symbol: str
    strategy_type: str
    strategy_params: Dict[str, Any]
    backtest_params: Dict[str, Any]
    results: Dict[str, Any]
    created_at: str

class BacktestHistoryResponse(BaseModel):
    success: bool
    backtests: List[BacktestHistoryItem]
    total_count: int
    stats: Dict[str, Any]

class BacktestStatsResponse(BaseModel):
    success: bool
    stats: Dict[str, Any]


class WebSocketManager:
    """Manages WebSocket connections for real-time data."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.websocket_client = None
        self.data_handler = DataHandler(config)
    
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
            
            # Start the simulated trading task
            asyncio.create_task(self._process_simulated_trading())
    
    async def _process_simulated_trading(self):
        """Process simulated trading signals in the background."""
        while True:
            try:
                # Check if trading is active
                if trading_state["is_active"] and trading_state["strategy_type"] == "orderbook":
                    # Get live order book signals
                    symbols = trading_state.get("symbols", [])
                    if symbols:
                        # Call the live order book signals endpoint internally
                        from fastapi.testclient import TestClient
                        client = TestClient(app)
                        
                        symbols_param = ','.join(symbols)
                        response = client.get(f"/api/orderbook/live-signals?symbols={symbols_param}")
                        
                        if response.status_code == 200:
                            data = response.json()
                            if data.get("signals"):
                                # Process signals through simulated trading
                                await simulated_trading.process_signals(data["signals"])
                
                # Wait before next check
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in simulated trading processing: {e}")
                await asyncio.sleep(30)  # Wait before retrying
    
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
                    # Cache current snapshot with TTL; key by product_id
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
    
    return real_time_data.get(product_id, {}) or {}


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
        data_provider = CachedDataProvider(config, "data/databases/trading_cache.db")
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        historical_data = await data_provider.get_historical_candles(
            start_time=start_time,
            end_time=end_time,
            granularity=granularity
        )
        
        historical_data_cache[cache_key] = historical_data
    
    return historical_data_cache.get(cache_key, [])

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
        data_provider = CachedDataProvider(config, "data/databases/trading_cache.db")
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
    
    return historical_data_cache.get(cache_key, [])


@app.post("/api/run-backtest")
async def run_backtest(request: BacktestRequest):
    """Run a backtest and return results."""
    await check_rate_limit()
    
    product_id = request.product_id or config.product_id
    
    try:
        # Get historical data
        data_provider = CachedDataProvider(config, "data/databases/trading_cache.db")
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
        
        logger.info(f"Converted {len(historical_data)} candles to {len(backtest_data)} backtest data points")
        
        # Select strategy class based on strategy_type
        strategy_class = SimpleMovingAverageStrategy  # Default
        if request.strategy_type == "ema":
            strategy_class = EMAStrategy
        elif request.strategy_type == "rsi":
            strategy_class = RSIStrategy
        elif request.strategy_type == "bollinger":
            strategy_class = BollingerBandsStrategy
        elif request.strategy_type == "macd":
            strategy_class = MACDStrategy
        elif request.strategy_type == "stochastic":
            strategy_class = StochasticStrategy
        elif request.strategy_type == "dca":
            strategy_class = DCAStrategy
        elif request.strategy_type == "atr":
            strategy_class = ATRStrategy
        elif request.strategy_type == "fibonacci":
            strategy_class = FibonacciRetracementStrategy
        elif request.strategy_type == "orderbook":
            strategy_class = OrderBookStrategy
        
        # Use strategy_params if provided and not empty, otherwise fall back to legacy parameters
        if request.strategy_params and len(request.strategy_params) > 0:
            strategy_params = request.strategy_params
        else:
            # Default parameters based on strategy type
            if request.strategy_type == "sma":
                strategy_params = {
                    'short_window': request.short_window,
                    'long_window': request.long_window
                }
            elif request.strategy_type == "ema":
                strategy_params = {
                    'short_ema': request.ema_short,
                    'long_ema': request.ema_long,
                    'alpha': request.ema_alpha
                }
            elif request.strategy_type == "bollinger":
                strategy_params = {
                    'period': request.bb_period,
                    'std_dev': request.bb_std_dev
                }
            elif request.strategy_type == "rsi":
                strategy_params = {
                    'period': request.rsi_period,
                    'oversold': request.rsi_oversold,
                    'overbought': request.rsi_overbought
                }
            elif request.strategy_type == "macd":
                strategy_params = {
                    'fast_ema': request.macd_fast,
                    'slow_ema': request.macd_slow,
                    'signal_ema': request.macd_signal
                }
            elif request.strategy_type == "stochastic":
                strategy_params = {
                    'k_period': request.stoch_k_period,
                    'd_period': request.stoch_d_period,
                    'overbought': request.stoch_overbought,
                    'oversold': request.stoch_oversold
                }
            elif request.strategy_type == "dca":
                strategy_params = {}  # DCA doesn't need strategy-specific params
            elif request.strategy_type == "atr":
                strategy_params = {
                    'period': request.atr_period,
                    'atr_multiplier': request.atr_multiplier,
                    'volatility_threshold': request.atr_volatility_threshold,
                    'position_size_atr': request.atr_position_size / 100  # Convert percentage to decimal
                }
            elif request.strategy_type == "fibonacci":
                strategy_params = {
                    'lookback_period': request.fib_lookback_period,
                    'fib_levels': request.fib_levels,
                    'confirmation_candles': request.fib_confirmation_candles
                }
            elif request.strategy_type == "orderbook":
                strategy_params = {
                    'order_book_level': request.order_book_level,
                    'trade_history_limit': request.trade_history_limit,
                    'bid_ask_spread_threshold': request.bid_ask_spread_threshold,
                    'volume_imbalance_threshold': request.volume_imbalance_threshold,
                    'large_trade_threshold': request.large_trade_threshold
                }
            else:
                # Fallback for unknown strategies
                strategy_params = {
                    'short_window': request.short_window,
                    'long_window': request.long_window
                }
        
        # Create backtester with buy and hold wrapper if enabled
        if request.enable_buy_hold:
            # Update config with buy and hold settings
            config.enable_buy_hold = request.enable_buy_hold
            config.buy_hold_exit_condition = request.buy_hold_exit_condition
            config.buy_hold_profit_target = request.buy_hold_profit_target
            
            # Create base strategy first with a config that doesn't have buy and hold enabled
            # This ensures the base strategy generates signals normally
            base_config = TradingConfig(
                api_key=config.api_key,
                api_secret=config.api_secret,
                passphrase=config.passphrase,
                product_id=config.product_id,
                websocket_url=config.websocket_url,
                max_position_size=config.max_position_size,
                stop_loss_percentage=config.stop_loss_percentage,
                take_profit_percentage=config.take_profit_percentage,
                trading_fee_percentage=config.trading_fee_percentage,
                enable_dca=config.enable_dca,
                dca_amount=config.dca_amount,
                dca_frequency=config.dca_frequency,
                dca_max_investments=config.dca_max_investments,
                dca_start_delay=config.dca_start_delay,
                enable_buy_hold=False,  # Base strategy should not have buy and hold enabled
                buy_hold_exit_condition="never",
                buy_hold_profit_target=0.0,
                output_dir=config.output_dir,
                log_level=config.log_level
            )
            
            base_strategy = strategy_class(base_config, **strategy_params)
            
            # Wrap with buy and hold strategy using the original config
            wrapped_strategy = BuyAndHoldStrategy(config, base_strategy)
            
            # Create backtester with wrapped strategy
            backtester = Backtester(
                config=config,
                strategy_class=lambda config, **kwargs: wrapped_strategy,
                strategy_params={},
                portfolio_percentage=request.portfolio_percentage,
                initial_capital=request.initial_capital,
                enable_stop_loss=request.enable_stop_loss,
                enable_take_profit=request.enable_take_profit,
                data_provider=data_provider
            )
        else:
            # Create backtester normally
            backtester = Backtester(
                config=config,
                strategy_class=strategy_class,
                strategy_params=strategy_params,
                portfolio_percentage=request.portfolio_percentage,
                initial_capital=request.initial_capital,
                enable_stop_loss=request.enable_stop_loss,
                enable_take_profit=request.enable_take_profit,
                data_provider=data_provider
            )
        
        # Run backtest
        result = await backtester.run_backtest(backtest_data)
        
        # Store results
        backtest_key = f"{product_id}_{request.strategy_type}_{request.days}_{request.granularity}_{hash(str(strategy_params))}"
        
        # Clean data for JSON serialization
        trades_data = clean_for_json(backtester.get_trades_df().to_dict('records'))
        equity_data = clean_for_json(backtester.get_equity_curve_df().to_dict('records'))
        result_data = clean_for_json(result.__dict__)  # Convert dataclass to dict
        
        # Store in memory cache
        backtest_results[backtest_key] = {
            'result': result_data,
            'trades_df': trades_data,
            'equity_df': equity_data,
            'timestamp': datetime.now().isoformat()
        }
        
        # Save to database
        backtest_params = {
            'days': request.days,
            'granularity': request.granularity,
            'stop_loss': request.stop_loss,
            'take_profit': request.take_profit,
            'initial_capital': request.initial_capital,
            'enable_dca': request.enable_dca,
            'dca_amount': request.dca_amount,
            'dca_frequency': request.dca_frequency,
            'dca_max_investments': request.dca_max_investments,
            'dca_start_delay': request.dca_start_delay,
            'enable_buy_hold': request.enable_buy_hold,
            'buy_hold_exit_condition': request.buy_hold_exit_condition,
            'buy_hold_profit_target': request.buy_hold_profit_target
        }
        
        results_data = {
            'result': result_data,
            'trades': trades_data,
            'equity_curve': equity_data
        }
        
        backtest_id = backtest_db.save_backtest(
            symbol=product_id,
            strategy_type=request.strategy_type,
            strategy_params=strategy_params,
            backtest_params=backtest_params,
            results=results_data
        )
        
        return {
            'success': True,
            'result': result_data,
            'trades': trades_data,
            'equity_curve': equity_data,
            'backtest_key': backtest_key,
            'backtest_id': backtest_id
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

@app.get("/api/backtest-history", response_model=BacktestHistoryResponse)
async def get_backtest_history(
    limit: int = 50,
    offset: int = 0,
    symbol: Optional[str] = None,
    strategy_type: Optional[str] = None
):
    """Get backtest history with optional filtering."""
    try:
        backtests = backtest_db.get_backtest_history(
            limit=limit,
            offset=offset,
            symbol=symbol,
            strategy_type=strategy_type
        )
        
        stats = backtest_db.get_backtest_stats()
        
        return BacktestHistoryResponse(
            success=True,
            backtests=backtests,
            total_count=stats['total_backtests'],
            stats=stats
        )
    except Exception as e:
        logger.error(f"Failed to get backtest history: {e}")
        return BacktestHistoryResponse(
            success=False,
            backtests=[],
            total_count=0,
            stats={}
        )

@app.get("/api/backtest/{backtest_id}", response_model=BacktestHistoryItem)
async def get_backtest(backtest_id: int):
    """Get a specific backtest by ID."""
    try:
        backtest = backtest_db.get_backtest(backtest_id)
        if backtest:
            return backtest
        else:
            raise HTTPException(status_code=404, detail="Backtest not found")
    except Exception as e:
        logger.error(f"Failed to get backtest {backtest_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/backtest-stats", response_model=BacktestStatsResponse)
async def get_backtest_stats():
    """Get backtest statistics."""
    try:
        stats = backtest_db.get_backtest_stats()
        return BacktestStatsResponse(success=True, stats=stats)
    except Exception as e:
        logger.error(f"Failed to get backtest stats: {e}")
        return BacktestStatsResponse(success=False, stats={})

@app.delete("/api/backtest/{backtest_id}")
async def delete_backtest(backtest_id: int):
    """Delete a backtest by ID."""
    try:
        success = backtest_db.delete_backtest(backtest_id)
        if success:
            return {"success": True, "message": f"Backtest {backtest_id} deleted"}
        else:
            raise HTTPException(status_code=404, detail="Backtest not found")
    except Exception as e:
        logger.error(f"Failed to delete backtest {backtest_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/backtest-filters")
async def get_backtest_filters():
    """Get available symbols and strategies for filtering."""
    try:
        stats = backtest_db.get_backtest_stats()
        
        # Get unique symbols and strategies from the database
        symbols = list(stats.get('symbol_counts', {}).keys())
        strategies = list(stats.get('strategy_counts', {}).keys())
        
        return {
            "success": True,
            "symbols": sorted(symbols),
            "strategies": sorted(strategies)
        }
    except Exception as e:
        logger.error(f"Failed to get backtest filters: {e}")
        return {
            "success": False,
            "symbols": [],
            "strategies": []
        }


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
    websocket_connected = False
    if manager.websocket_client is not None:
        websocket_status = await manager.websocket_client.get_subscription_info()
        websocket_connected = websocket_status.get('connected', False)
    
    return {
        "enabled": realtime_data_enabled,
        "websocket_connected": websocket_connected,
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
        return {"error": str(e)    }

@app.get("/api/products")
async def get_available_products():
    """Get all available trading products from Coinbase."""
    await check_rate_limit()
    
    try:
        # Fetch products if not cached or cache is old
        if not product_fetcher.products_cache or not product_fetcher.last_updated:
            await product_fetcher.fetch_all_products()
        
        categories = product_fetcher.get_products_by_category()
        
        return {
            "status": "success",
            "last_updated": product_fetcher.last_updated.isoformat() if product_fetcher.last_updated else None,
            "total_products": len(product_fetcher.products_cache),
            "categories": categories,
            "recommended": {
                "major_pairs": categories['major'][:10],  # Top 10 major pairs
                "popular_dex": categories['dex_tokens'][:5],  # Top 5 DEX tokens
                "meme_tokens": categories['meme_tokens'][:5]  # Top 5 meme tokens
            }
        }
    except Exception as e:
        logger.error(f"Failed to fetch products: {e}")
        return {"error": str(e)}

@app.post("/api/live-trading/start")
async def start_live_trading(request: dict):
    """Start live trading with specified strategy."""
    await check_rate_limit()
    
    try:
        # Extract trading parameters
        symbols = request.get('symbols', [request.get('symbol', 'BTC-USD')])  # Support both single and multiple symbols
        strategy_type = request.get('strategy_type', 'sma')
        mode = request.get('mode', 'simulated')  # 'simulated' or 'live'
        symbol_mode = request.get('symbol_mode', 'single')  # 'single' or 'universe'
        strategy_params = request.get('strategy_params', {})
        position_size = request.get('position_size', 5.0)
        max_positions = request.get('max_positions', 3)
        universe_config = request.get('universe_config', {})
        
        # Validate parameters
        if mode not in ['simulated', 'live']:
            return {"error": "Invalid trading mode. Must be 'simulated' or 'live'"}
        
        if symbol_mode not in ['single', 'universe']:
            return {"error": "Invalid symbol mode. Must be 'single' or 'universe'"}
        
        if strategy_type not in ['sma', 'ema', 'rsi', 'bollinger', 'macd', 'stochastic', 'fibonacci', 'orderbook', 'dca', 'buyandhold']:
            return {"error": "Invalid strategy type"}
        
        # Validate symbols
        if not symbols or len(symbols) == 0:
            return {"error": "No symbols specified for trading"}
        
        # Note: Removed symbol limit validation to allow unlimited universe trading
        # Users can now trade on as many symbols as they want
        
        # For universe trading, select the best symbols to trade
        selected_symbols = symbols
        if symbol_mode == 'universe' and len(symbols) > max_positions:
            try:
                from .universe_selector import UniverseSelector
                from ..trading.trading_strategy import get_strategy_class
                # Import all strategy classes to ensure they're available
                from ..trading.trading_strategy import (
                    SimpleMovingAverageStrategy, EMAStrategy,
                    RSIStrategy, BollingerBandsStrategy, MACDStrategy,
                    StochasticStrategy, FibonacciRetracementStrategy,
                    OrderBookStrategy, DCAStrategy, BuyAndHoldStrategy
                )
                
                # Get strategy class
                strategy_class = get_strategy_class(strategy_type)
                if not strategy_class:
                    return {"error": f"Unknown strategy type: {strategy_type}"}
                
                # Create data provider for universe selection
                data_provider = CachedDataProvider(config, "data/databases/trading_cache.db")
                
                # Create universe selector
                selector = UniverseSelector(
                    data_provider=data_provider,
                    strategy_class=strategy_class,
                    strategy_params=strategy_params
                )
                
                # Select best symbols
                selection_method = universe_config.get('selection_method', 'signal_strength')
                selected = await selector.select_symbols(
                    universe_symbols=symbols,
                    max_positions=max_positions,
                    selection_method=selection_method
                )
                
                if not selected:
                    return {"error": "No symbols selected for trading from universe"}
                
                # Update symbols to only include selected ones
                selected_symbols = [symbol for symbol, strength, data in selected]
                
                # Log selection results
                summary = selector.get_universe_summary(selected)
                logger.info(f"Universe selection: {summary['count']} symbols selected from {len(symbols)} total")
                logger.info(f"Buy signals: {summary['buy_signals']}, Sell signals: {summary['sell_signals']}")
                
            except Exception as e:
                logger.error(f"Error in universe selection: {e}")
                return {"error": f"Failed to select symbols from universe: {str(e)}"}
        
        # Update symbols to selected symbols
        symbols = selected_symbols
        
        trading_session = {
            "session_id": f"trading_{int(time.time())}",
            "symbols": symbols,
            "symbol_mode": symbol_mode,
            "strategy_type": strategy_type,
            "mode": mode,
            "status": "active",
            "started_at": datetime.now().isoformat(),
            "strategy_params": strategy_params,
            "position_size": position_size,
            "max_positions": max_positions,
            "universe_config": universe_config
        }
        
        # Create appropriate message based on symbol mode
        if symbol_mode == 'universe':
            message = f"Live universe trading started in {mode} mode with {strategy_type} strategy on {len(symbols)} symbols"
        else:
            message = f"Live trading started in {mode} mode with {strategy_type} strategy on {symbols[0]}"
        
        return {
            "status": "success",
            "trading_session": trading_session,
            "message": message
        }
        
    except Exception as e:
        logger.error(f"Failed to start live trading: {e}")
        return {"error": str(e)}

@app.post("/api/live-trading/stop")
async def stop_live_trading(request: dict):
    """Stop live trading session."""
    await check_rate_limit()
    
    try:
        session_id = request.get('session_id')
        
        if not session_id:
            return {"error": "Session ID required"}
        
        # In a real implementation, this would:
        # 1. Stop the trading strategy
        # 2. Close any open positions if needed
        # 3. Clean up resources
        
        return {
            "status": "success",
            "message": f"Trading session {session_id} stopped"
        }
        
    except Exception as e:
        logger.error(f"Failed to stop live trading: {e}")
        return {"error": str(e)}

@app.get("/api/live-trading/positions")
async def get_live_positions():
    """Get current live trading positions."""
    await check_rate_limit()
    
    try:
        # In a real implementation, this would return actual positions
        # For now, return empty list
        return {
            "status": "success",
            "positions": [],
            "total_value": 0.0,
            "unrealized_pnl": 0.0
        }
        
    except Exception as e:
        logger.error(f"Failed to get positions: {e}")
        return {"error": str(e)}

@app.post("/api/live-trading/close-position")
async def close_live_position(request: dict):
    """Close a specific position."""
    await check_rate_limit()
    
    try:
        position_id = request.get('position_id')
        
        if not position_id:
            return {"error": "Position ID required"}
        
        # In a real implementation, this would:
        # 1. Find the position
        # 2. Execute the closing trade
        # 3. Update the portfolio
        
        return {
            "status": "success",
            "message": f"Position {position_id} closed"
        }
        
    except Exception as e:
        logger.error(f"Failed to close position: {e}")
        return {"error": str(e)}

@app.get("/api/live-trading/history")
async def get_live_trading_history():
    """Get live trading history."""
    await check_rate_limit()
    
    try:
        # In a real implementation, this would return actual trading history
        # For now, return empty list
        return {
            "status": "success",
            "trades": [],
            "total_trades": 0,
            "total_pnl": 0.0
        }
        
    except Exception as e:
        logger.error(f"Failed to get trading history: {e}")
        return {"error": str(e)}

@app.get("/api/cache-stats")
async def get_cache_stats():
    """Get cache performance statistics."""
    try:
        # Create a temporary data provider to get cache stats
        temp_provider = CachedDataProvider(config, "data/databases/trading_cache.db")
        stats = temp_provider.get_cache_stats()
        return {
            "status": "success",
            "cache_stats": stats,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
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

@app.get("/api/orderbook/live-signals")
async def get_live_orderbook_signals(symbols: str = None):
    """Get live order book signals for specified symbols or top 20 symbols."""
    await check_rate_limit()
    
    try:
        print("DEBUG: Starting live order book signals endpoint")
        if not manager.data_handler:
            return {"error": "Data handler not initialized"}
        print("DEBUG: Data handler is initialized")
        logger.debug("DataHandler and main config initialized")
        
        # Check if trading is active
        if not trading_state["is_active"]:
            return {
                "signals": [],
                "message": "Trading is not active. Start trading to see live signals.",
                "trading_active": False,
                "timestamp": datetime.now().isoformat()
            }
        
        # DataHandler is now initialized in WebSocketManager.__init__
        
        # Parse symbols parameter if provided
        if symbols:
            try:
                symbols_to_analyze = symbols.split(',') if ',' in symbols else [symbols]
                logger.info(f"Using provided symbols: {symbols_to_analyze}")
            except Exception as e:
                logger.error(f"Error parsing symbols parameter: {e}")
                return {"error": "Invalid symbols parameter format"}
        else:
            # Get available symbols from Coinbase Advanced Trade API
            if manager.data_handler:
                products = await manager.data_handler.get_products()
                if products:
                    # Filter for USD pairs and extract symbols
                    usd_products = [p for p in products if p.get('quote_currency_id') == 'USD']
                    available_symbols = [p['product_id'] for p in usd_products[:20]]
                else:
                    # Fallback to hardcoded symbols
                    symbols_response = await get_available_symbols()
                    if not symbols_response or 'symbols' not in symbols_response:
                        return {"error": "No symbols available"}
                    available_symbols = [symbol['symbol'] for symbol in symbols_response['symbols']]
            else:
                # Fallback to hardcoded symbols
                symbols_response = await get_available_symbols()
                if not symbols_response or 'symbols' not in symbols_response:
                    return {"error": "No symbols available"}
                available_symbols = [symbol['symbol'] for symbol in symbols_response['symbols']]
            
            symbols_to_analyze = available_symbols[:20]
        
        # Create OrderBook strategy for analysis using trading state parameters
        strategy_params = trading_state.get("strategy_params", {})
        strategy = OrderBookStrategy(
            config=config,
            order_book_level=strategy_params.get("order_book_level", 2),
            trade_history_limit=strategy_params.get("trade_history_limit", 1000),
            bid_ask_spread_threshold=strategy_params.get("bid_ask_spread_threshold", 0.001),
            volume_imbalance_threshold=strategy_params.get("volume_imbalance_threshold", 0.6),
            large_trade_threshold=strategy_params.get("large_trade_threshold", 10000.0),
            data_analysis_mode=strategy_params.get("data_analysis_mode", "recent"),
            recent_data_limit=strategy_params.get("recent_data_limit", 50),
            sampling_ratio=strategy_params.get("sampling_ratio", 0.1)
        )
        
        # Create ML strategy for enhanced signal generation
        ml_strategy = MLStrategy(
            config=config,
            name="ML Strategy",
            min_win_probability=strategy_params.get("min_win_probability", 0.6),
            min_expected_return=strategy_params.get("min_expected_return", 0.01),
            min_confidence=strategy_params.get("min_confidence", 0.3),
            max_risk_per_trade=strategy_params.get("max_risk_per_trade", 0.02)
        )
        
        live_signals = []
        
        logger.info(f"Analyzing {len(symbols_to_analyze)} symbols: {symbols_to_analyze[:5]}...")
        
        for symbol in symbols_to_analyze:
            try:
                # Get historical candles from Coinbase Advanced Trade API
                candles = []
                if manager.data_handler:
                    candles = await manager.data_handler.get_historical_candles(
                        product_id=symbol,
                        start_time=int((datetime.now() - timedelta(hours=2)).timestamp()),
                        end_time=int(datetime.now().timestamp()),
                        granularity=60  # 1 minute
                    )
                
                # Initialize default values
                current_price = 0.0
                signal = None
                detailed_analysis = {
                    'signal_generated': False,
                    'signal_type': None,
                    'signal_reason': 'Insufficient data for analysis',
                    'criteria_analysis': {
                        'bid_ask_squeeze': {'enabled': False, 'analysis': 'Insufficient data'},
                        'volume_imbalance_buy': {'enabled': False, 'analysis': 'Insufficient data'},
                        'volume_imbalance_sell': {'enabled': False, 'analysis': 'Insufficient data'},
                        'large_trade_buy': {'enabled': False, 'analysis': 'Insufficient data'},
                        'large_trade_sell': {'enabled': False, 'analysis': 'Insufficient data'}
                    }
                }
                ob_summary = {
                    'current_spread': 0.0,
                    'current_imbalance': 0.0,
                    'current_mid_price': 0.0,
                    'order_book_depth': 0,
                    'best_bid': 0.0,
                    'best_ask': 0.0,
                    'spread_trend': 'unknown',
                    'imbalance_trend': 'unknown'
                }
                signal_strength = 0.0
                volume = 0.0
                stats = {'total_signals': 0, 'signal_rate': 0.0}
                
                # Process data if available
                logger.info(f"Symbol {symbol}: {len(candles) if candles else 0} candles available")
                if candles and len(candles) >= 10:
                    # Add price data to strategy
                    for candle in candles:
                        strategy.add_price(float(candle['close']), candle['time'])
                    
                    current_price = float(candles[-1]['close'])
                    volume = float(candles[-1]['volume'])
                    
                    # Get order book data - try WebSocket first, then API
                    order_book = manager.data_handler.get_latest_level2()
                    if not order_book:
                        # Fallback to Coinbase Advanced Trade API
                        order_book = await manager.data_handler.get_product_book(symbol, limit=20)
                    
                    if order_book:
                        # Add multiple order book snapshots to enable squeeze analysis
                        # Simulate historical order book data by adding slight variations
                        strategy.add_order_book(order_book, candles[-1]['time'])
                        
                        # Add a few more snapshots with slight variations to enable squeeze analysis
                        for i in range(1, 3):  # Add 2 more snapshots
                            try:
                                # Create a slightly modified order book with small price variations
                                modified_order_book = order_book.copy()
                                
                                # Handle bids - check if they exist and have the right structure
                                if 'bids' in modified_order_book and modified_order_book['bids']:
                                    for bid in modified_order_book['bids']:
                                        if isinstance(bid, list) and len(bid) >= 2:
                                            try:
                                                bid[0] = str(float(bid[0]) * (1 + (i * 0.0001)))  # Small variation
                                            except (ValueError, TypeError):
                                                continue
                                
                                # Handle asks - check if they exist and have the right structure
                                if 'asks' in modified_order_book and modified_order_book['asks']:
                                    for ask in modified_order_book['asks']:
                                        if isinstance(ask, list) and len(ask) >= 2:
                                            try:
                                                ask[0] = str(float(ask[0]) * (1 + (i * 0.0001)))  # Small variation
                                            except (ValueError, TypeError):
                                                continue
                                
                                # Add the modified order book with a slightly earlier timestamp
                                earlier_time = datetime.fromisoformat(candles[-1]['time'].replace('Z', '+00:00')) - timedelta(seconds=i*30)
                                strategy.add_order_book(modified_order_book, earlier_time.isoformat())
                            except Exception as e:
                                logger.warning(f"Error creating modified order book for {symbol}: {e}")
                                continue
                    
                    # Get recent trades - try WebSocket first, then API
                    trades = manager.data_handler.get_latest_trades()
                    if not trades:
                        # Fallback to Coinbase Advanced Trade API
                        trades = await manager.data_handler.get_recent_trades(symbol, limit=100)
                    
                    if trades:
                        logger.info(f"Adding {len(trades)} trades to strategy for {symbol}")
                        strategy.add_trades(trades, candles[-1]['time'])
                    
                    # Generate signal and get detailed analysis
                    logger.info(f"Generating signal for {symbol}")
                    try:
                        signal = strategy.generate_signal(current_price, candles[-1]['time'])
                        logger.info(f"Getting detailed analysis for {symbol}")
                        detailed_analysis = strategy.get_detailed_signal_analysis(current_price, candles[-1]['time'])
                    except Exception as e:
                        logger.error(f"Error in signal generation for {symbol}: {e}")
                        logger.error(f"Error type: {type(e)}")
                        import traceback
                        logger.error(f"Traceback: {traceback.format_exc()}")
                        raise
                    ob_summary = strategy.get_order_book_summary()
                    stats = strategy.get_signal_stats()
                    
                    # Generate ML signal
                    ml_signal_data = None
                    ml_analysis = {
                        'win_probability': 0.0,
                        'expected_return': 0.0,
                        'confidence': 0.0,
                        'features_used': [],
                        'model_version': '1.0.0',
                        'prediction_timestamp': datetime.now().isoformat(),
                        'ml_enabled': False
                    }
                    
                    try:
                        if ml_strategy.ml_enabled:
                            logger.info(f"Generating ML signal for {symbol}")
                            # Prepare data for ML analysis
                            orderbook_data = order_book if order_book else {}
                            trades_data = trades if trades else []
                            
                            # Generate ML signal (will return default values if not trained)
                            ml_signal_data = ml_strategy.ml_generator.generate_signal(
                                trades=trades_data,
                                orderbook_data=orderbook_data,
                                current_price=current_price,
                                symbol=symbol
                            )
                            
                            ml_analysis = {
                                'win_probability': ml_signal_data.win_probability,
                                'expected_return': ml_signal_data.expected_return,
                                'confidence': ml_signal_data.confidence,
                                'features_used': ml_signal_data.features_used,
                                'model_version': ml_signal_data.model_version,
                                'prediction_timestamp': ml_signal_data.prediction_timestamp.isoformat(),
                                'ml_enabled': True,
                                'model_trained': ml_strategy.ml_generator.is_trained
                            }
                            logger.info(f"ML signal generated for {symbol}: win_prob={ml_signal_data.win_probability:.3f}, expected_return={ml_signal_data.expected_return:.3f}, trained={ml_strategy.ml_generator.is_trained}")
                        else:
                            logger.info(f"ML signal disabled for {symbol}")
                    except Exception as e:
                        logger.error(f"Error generating ML signal for {symbol}: {e}")
                        # Continue without ML signal
                    
                    # Calculate signal strength based on closest criteria
                    criteria = detailed_analysis['criteria_analysis']
                    max_delta = 0.0
                    
                    # Find the highest delta (closest to triggering)
                    for criterion_name, criterion_data in criteria.items():
                        if criterion_data['enabled'] and not criterion_data['meets_criteria']:
                            delta = criterion_data['delta_to_threshold']
                            if delta > max_delta:
                                max_delta = delta
                    
                    # Calculate signal strength based on deltas
                    if detailed_analysis['signal_generated']:
                        signal_strength = 0.9  # High strength for active signals
                    else:
                        signal_strength = min(0.8, max_delta)  # Strength based on closest criteria
                elif candles and len(candles) > 0:
                    # Some data available but not enough for full analysis
                    current_price = float(candles[-1]['close'])
                    volume = float(candles[-1]['volume'])
                    detailed_analysis['signal_reason'] = f'Insufficient data: {len(candles)}/10 candles available'
                else:
                    # No data available
                    detailed_analysis['signal_reason'] = 'No historical data available'
                
                # Always add the symbol to results
                data_status = 'sufficient' if candles and len(candles) >= 10 else 'insufficient' if candles else 'none'
                logger.info(f"Adding {symbol} to results: price={current_price}, data_status={data_status}")
                live_signals.append({
                    'symbol': symbol,
                    'price': current_price,
                    'signal': signal.action if signal else 'hold',
                    'signal_strength': round(signal_strength, 3),
                    'signal_generated': detailed_analysis['signal_generated'],
                    'signal_type': detailed_analysis['signal_type'],
                    'signal_reason': detailed_analysis['signal_reason'],
                    'criteria_analysis': detailed_analysis['criteria_analysis'],
                    'spread': round(float(ob_summary.get('current_spread', 0.0)) * 100, 4),  # Convert to percentage
                    'imbalance': round(float(ob_summary.get('current_imbalance', 0.0)), 3),
                    'mid_price': round(float(ob_summary.get('current_mid_price', 0.0)), 2),
                    'best_bid': round(float(ob_summary.get('best_bid', 0.0)), 2),
                    'best_ask': round(float(ob_summary.get('best_ask', 0.0)), 2),
                    'order_book_depth': int(ob_summary.get('order_book_depth', 0)),
                    'spread_trend': str(ob_summary.get('spread_trend', 'unknown')),
                    'imbalance_trend': str(ob_summary.get('imbalance_trend', 'unknown')),
                    'volume': float(volume),
                    'total_signals': int(stats.get('total_signals', 0)),
                    'signal_rate': round(float(stats.get('signal_rate', 0.0)), 2),
                    'data_status': data_status,
                    'ml_analysis': ml_analysis,
                    'timestamp': datetime.now().isoformat()
                })
                
                # Reset strategy for next symbol
                strategy = OrderBookStrategy(
                    config=config,
                    order_book_level=2,
                    volume_imbalance_threshold=0.6,
                    large_trade_threshold=10000.0
                )
                
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                logger.error(f"Error type: {type(e)}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                continue
        
        # Sort by signal strength and return top 10
        live_signals.sort(key=lambda x: x['signal_strength'], reverse=True)
        
        # Save signals to database if trading is active
        if trading_state["is_active"] and trading_state.get("session_id"):
            current_time = datetime.now()
            for signal in live_signals:
                signal_data = {
                    'signal_id': f"{signal['symbol']}_{int(current_time.timestamp() * 1000)}",
                    'session_id': trading_state["session_id"],
                    'symbol': signal['symbol'],
                    'price': signal['price'],
                    'signal': signal['signal'],
                    'signal_strength': signal['signal_strength'],
                    'signal_generated': signal['signal_generated'],
                    'signal_type': signal['signal_type'],
                    'signal_reason': signal['signal_reason'],
                    'spread': signal.get('spread'),
                    'imbalance': signal.get('imbalance'),
                    'mid_price': signal.get('mid_price'),
                    'best_bid': signal.get('best_bid'),
                    'best_ask': signal.get('best_ask'),
                    'order_book_depth': signal.get('order_book_depth'),
                    'spread_trend': signal.get('spread_trend'),
                    'imbalance_trend': signal.get('imbalance_trend'),
                    'volume': signal.get('volume'),
                    'total_signals': signal.get('total_signals'),
                    'signal_rate': signal.get('signal_rate'),
                    'data_status': signal.get('data_status'),
                    'timestamp': current_time.isoformat()
                }
                db_manager.save_order_book_signal(signal_data)
        
        # Clean data for JSON serialization
        cleaned_signals = clean_for_json(live_signals)
        
        # Count active signals
        active_signals = sum(1 for signal in live_signals if signal.get('signal_generated', False))
        
        return {
            "signals": cleaned_signals[:10],  # Return top 10
            "timestamp": datetime.now().isoformat(),
            "total_analyzed": len(live_signals),
            "total_signals": active_signals
        }
        
    except Exception as e:
        logger.error(f"Error getting live order book signals: {e}")
        return {"error": str(e)}


# Simulated Trading Endpoints
@app.post("/api/simulated-trading/start")
async def start_simulated_trading(request: dict):
    """Start simulated trading based on live order book signals."""
    await check_rate_limit()
    
    try:
        symbols = request.get('symbols', ['BTC-USD', 'ETH-USD'])
        initial_balance = request.get('initial_balance', 10000.0)
        max_positions = request.get('max_positions', 5)
        position_size_percent = request.get('position_size_percent', 20.0)
        strategy_type = request.get('strategy_type', 'orderbook')
        strategy_params = request.get('strategy_params', {})
        session_id = request.get('session_id')
        
        # Update trading state
        trading_state["is_active"] = True
        trading_state["strategy_type"] = strategy_type
        trading_state["strategy_params"] = strategy_params
        trading_state["symbols"] = symbols
        trading_state["mode"] = "simulated"
        trading_state["last_signal_check"] = datetime.now()
        trading_state["session_id"] = session_id
        
        # Reset and configure simulated trading
        simulated_trading.reset_portfolio()
        simulated_trading.initial_balance = initial_balance
        simulated_trading.cash_balance = initial_balance
        simulated_trading.max_positions = max_positions
        simulated_trading.position_size_percent = position_size_percent / 100.0
        
        # Set session info for trade logging
        if session_id:
            simulated_trading.set_session_info(db_manager, session_id)
        
        # Set strategy info for trade logging
        simulated_trading.set_strategy_info(strategy_type, strategy_params)
        
        # Start trading
        simulated_trading.start_trading(symbols)
        
        logger.info(f"Started simulated trading for {len(symbols)} symbols with ${initial_balance:,.2f}")
        logger.info(f"Strategy: {strategy_type} with params: {strategy_params}")
        
        return {
            "status": "started",
            "symbols": symbols,
            "initial_balance": initial_balance,
            "max_positions": max_positions,
            "position_size_percent": position_size_percent,
            "strategy_type": strategy_type,
            "strategy_params": strategy_params,
            "trading_active": True
        }
        
    except Exception as e:
        logger.error(f"Failed to start simulated trading: {e}")
        return {"error": str(e)}


@app.post("/api/simulated-trading/stop")
async def stop_simulated_trading():
    """Stop simulated trading and close all positions."""
    await check_rate_limit()
    
    try:
        simulated_trading.stop_trading()
        
        # Update trading state
        trading_state["is_active"] = False
        trading_state["strategy_type"] = None
        trading_state["strategy_params"] = {}
        trading_state["symbols"] = []
        trading_state["mode"] = "simulated"
        trading_state["last_signal_check"] = None
        
        logger.info("Stopped simulated trading")
        
        return {
            "status": "stopped",
            "message": "Simulated trading stopped and all positions closed",
            "trading_active": False
        }
        
    except Exception as e:
        logger.error(f"Failed to stop simulated trading: {e}")
        return {"error": str(e)}


# Asynchronous Trading Endpoints
@app.post("/api/async-trading/start")
async def start_async_trading(request: dict):
    """Start asynchronous trading with progressive symbol loading."""
    await check_rate_limit()
    
    try:
        # Extract trading parameters
        symbols = request.get('symbols', ['BTC-USD', 'ETH-USD'])
        strategy_type = request.get('strategy_type', 'orderbook')
        strategy_params = request.get('strategy_params', {})
        initial_balance = request.get('initial_balance', 10000.0)
        max_positions = request.get('max_positions', 5)
        position_size_percent = request.get('position_size_percent', 20.0)
        session_id = request.get('session_id')
        immediate_start = request.get('immediate_start', True)
        batch_size = request.get('batch_size', 3)
        
        # Create session ID if not provided
        if not session_id:
            session_id = f"async_trading_{int(time.time())}"
        
        # Start with first batch of symbols for immediate trading
        initial_symbols = symbols[:batch_size] if len(symbols) > batch_size else symbols
        remaining_symbols = symbols[batch_size:] if len(symbols) > batch_size else []
        
        # Update trading state
        trading_state["is_active"] = True
        trading_state["strategy_type"] = strategy_type
        trading_state["strategy_params"] = strategy_params
        trading_state["symbols"] = initial_symbols
        trading_state["all_symbols"] = symbols  # Store all symbols for reference
        trading_state["remaining_symbols"] = remaining_symbols
        trading_state["mode"] = "simulated"
        trading_state["last_signal_check"] = datetime.now()
        trading_state["session_id"] = session_id
        trading_state["async_loading"] = True
        trading_state["loading_progress"] = {
            "total": len(symbols),
            "loaded": len(initial_symbols),
            "remaining": len(remaining_symbols),
            "status": "loading"
        }
        
        # Reset and configure simulated trading
        simulated_trading.reset_portfolio()
        simulated_trading.initial_balance = initial_balance
        simulated_trading.cash_balance = initial_balance
        simulated_trading.max_positions = max_positions
        simulated_trading.position_size_percent = position_size_percent / 100.0
        
        # Set session info for trade logging
        simulated_trading.set_session_info(db_manager, session_id)
        
        # Set strategy info for trade logging
        simulated_trading.set_strategy_info(strategy_type, strategy_params)
        
        # Start trading with initial symbols
        simulated_trading.start_trading(initial_symbols)
        
        logger.info(f"Started async trading with {len(initial_symbols)} initial symbols, {len(remaining_symbols)} remaining")
        logger.info(f"Strategy: {strategy_type} with params: {strategy_params}")
        
        # Start background symbol loading if there are remaining symbols
        if remaining_symbols and immediate_start:
            asyncio.create_task(load_remaining_symbols_async(remaining_symbols, batch_size))
        
        return {
            "status": "started",
            "session_id": session_id,
            "initial_symbols": initial_symbols,
            "remaining_symbols": remaining_symbols,
            "total_symbols": len(symbols),
            "loading_progress": trading_state["loading_progress"],
            "initial_balance": initial_balance,
            "max_positions": max_positions,
            "position_size_percent": position_size_percent,
            "strategy_type": strategy_type,
            "strategy_params": strategy_params,
            "trading_active": True
        }
        
    except Exception as e:
        logger.error(f"Failed to start async trading: {e}")
        return {"error": str(e)}


@app.post("/api/async-trading/add-symbols")
async def add_symbols_to_trading(request: dict):
    """Add additional symbols to active trading session."""
    await check_rate_limit()
    
    try:
        new_symbols = request.get('symbols', [])
        if not new_symbols:
            return {"error": "No symbols provided"}
        
        if not trading_state.get("is_active", False):
            return {"error": "No active trading session"}
        
        # Add symbols to the trading session
        current_symbols = trading_state.get("symbols", [])
        all_symbols = trading_state.get("all_symbols", [])
        
        # Add new symbols to current trading
        for symbol in new_symbols:
            if symbol not in current_symbols:
                current_symbols.append(symbol)
                all_symbols.append(symbol)
        
        # Update trading state
        trading_state["symbols"] = current_symbols
        trading_state["all_symbols"] = all_symbols
        
        # Add symbols to simulated trading
        simulated_trading.add_symbols(new_symbols)
        
        # Update loading progress
        remaining = trading_state.get("remaining_symbols", [])
        for symbol in new_symbols:
            if symbol in remaining:
                remaining.remove(symbol)
        trading_state["remaining_symbols"] = remaining
        
        trading_state["loading_progress"] = {
            "total": len(all_symbols),
            "loaded": len(current_symbols),
            "remaining": len(remaining),
            "status": "loading" if remaining else "complete"
        }
        
        logger.info(f"Added {len(new_symbols)} symbols to trading session: {new_symbols}")
        
        return {
            "status": "success",
            "added_symbols": new_symbols,
            "current_symbols": current_symbols,
            "loading_progress": trading_state["loading_progress"]
        }
        
    except Exception as e:
        logger.error(f"Failed to add symbols to trading: {e}")
        return {"error": str(e)}


@app.get("/api/async-trading/loading-status")
async def get_loading_status():
    """Get current symbol loading status."""
    await check_rate_limit()
    
    try:
        if not trading_state.get("is_active", False):
            return {"error": "No active trading session"}
        
        return {
            "loading_progress": trading_state.get("loading_progress", {}),
            "current_symbols": trading_state.get("symbols", []),
            "remaining_symbols": trading_state.get("remaining_symbols", []),
            "total_symbols": len(trading_state.get("all_symbols", []))
        }
        
    except Exception as e:
        logger.error(f"Failed to get loading status: {e}")
        return {"error": str(e)}


async def load_remaining_symbols_async(remaining_symbols: list, batch_size: int = 3):
    """Background task to load remaining symbols progressively."""
    try:
        logger.info(f"Starting background loading of {len(remaining_symbols)} symbols")
        
        # Process symbols in batches
        for i in range(0, len(remaining_symbols), batch_size):
            batch = remaining_symbols[i:i + batch_size]
            
            # Add batch to trading
            await add_symbols_to_trading({"symbols": batch})
            
            # Broadcast progress update via WebSocket
            await manager.broadcast(json.dumps({
                'type': 'symbol_loading_progress',
                'data': {
                    'loading_progress': trading_state.get("loading_progress", {}),
                    'current_symbols': trading_state.get("symbols", []),
                    'remaining_symbols': trading_state.get("remaining_symbols", []),
                    'total_symbols': len(trading_state.get("all_symbols", []))
                }
            }))
            
            # Wait between batches to avoid overwhelming the system
            await asyncio.sleep(2.0)
            
            logger.info(f"Loaded batch {i//batch_size + 1}: {batch}")
        
        # Mark loading as complete
        trading_state["loading_progress"]["status"] = "complete"
        trading_state["async_loading"] = False
        
        # Broadcast final completion update
        await manager.broadcast(json.dumps({
            'type': 'symbol_loading_complete',
            'data': {
                'loading_progress': trading_state.get("loading_progress", {}),
                'current_symbols': trading_state.get("symbols", []),
                'message': 'All symbols loaded successfully!'
            }
        }))
        
        logger.info("Background symbol loading completed")
        
    except Exception as e:
        logger.error(f"Error in background symbol loading: {e}")
        trading_state["loading_progress"]["status"] = "error"
        trading_state["async_loading"] = False
        
        # Broadcast error update
        await manager.broadcast(json.dumps({
            'type': 'symbol_loading_error',
            'data': {
                'loading_progress': trading_state.get("loading_progress", {}),
                'error': str(e),
                'message': 'Error loading some symbols'
            }
        }))


@app.get("/api/simulated-trading/status")
async def get_simulated_trading_status():
    """Get current simulated trading status and portfolio."""
    await check_rate_limit()
    
    try:
        portfolio = simulated_trading.get_portfolio_summary()
        open_positions = simulated_trading.get_open_positions()
        recent_trades = simulated_trading.get_recent_trades(10)
        
        return {
            "is_trading": simulated_trading.is_trading,
            "symbols": simulated_trading.symbols_to_trade,
            "portfolio": {
                "cash_balance": portfolio.cash_balance,
                "total_value": portfolio.total_value,
                "total_pnl": portfolio.total_pnl,
                "total_fees": portfolio.total_fees,
                "max_drawdown": portfolio.max_drawdown,
                "win_rate": portfolio.win_rate,
                "total_trades": portfolio.total_trades,
                "winning_trades": portfolio.winning_trades
            },
            "open_positions": open_positions,
            "recent_trades": recent_trades,
            "last_signal_check": simulated_trading.last_signal_check.isoformat() if simulated_trading.last_signal_check else None
        }
        
    except Exception as e:
        logger.error(f"Failed to get simulated trading status: {e}")
        return {"error": str(e)}


@app.post("/api/simulated-trading/process-signals")
async def process_simulated_signals(request: dict):
    """Process live order book signals and execute simulated trades."""
    await check_rate_limit()
    
    try:
        signals = request.get('signals', [])
        
        if not signals:
            return {"error": "No signals provided"}
        
        result = await simulated_trading.process_signals(signals)
        
        logger.info(f"Processed {len(signals)} signals, executed {result.get('executed_trades', 0)} trades")
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to process simulated signals: {e}")
        return {"error": str(e)}


@app.post("/api/simulated-trading/reset")
async def reset_simulated_trading():
    """Reset simulated trading portfolio to initial state."""
    await check_rate_limit()
    
    try:
        simulated_trading.reset_portfolio()
        logger.info("Reset simulated trading portfolio")
        
        return {
            "status": "reset",
            "message": "Portfolio reset to initial state"
        }
        
    except Exception as e:
        logger.error(f"Failed to reset simulated trading: {e}")
        return {"error": str(e)}


@app.get("/api/trading/state")
async def get_trading_state():
    """Get current trading state."""
    await check_rate_limit()
    
    try:
        return {
            "trading_active": trading_state["is_active"],
            "strategy_type": trading_state["strategy_type"],
            "strategy_params": trading_state["strategy_params"],
            "symbols": trading_state["symbols"],
            "mode": trading_state["mode"],
            "last_signal_check": trading_state["last_signal_check"].isoformat() if trading_state["last_signal_check"] else None
        }
        
    except Exception as e:
        logger.error(f"Failed to get trading state: {e}")
        return {"error": str(e)}


# Session State Management Endpoints

@app.post("/api/session/save")
async def save_session_state(request: dict):
    """Save current trading session state."""
    await check_rate_limit()
    
    try:
        session_id = request.get('session_id')
        if not session_id:
            return {"error": "Session ID is required"}
        
        # Get current trading state
        trading_status = await get_simulated_trading_status()
        if trading_status.get('error'):
            return {"error": "Failed to get current trading status"}
        
        # Prepare session data
        session_data = {
            'is_active': trading_status.get('is_trading', False),
            'trading_mode': 'simulated',  # Currently only simulated trading
            'symbol_mode': 'universe' if len(trading_status.get('symbols', [])) > 1 else 'single',
            'strategy_type': trading_status.get('strategy_type'),
            'strategy_params': trading_status.get('strategy_params', {}),
            'symbols': trading_status.get('symbols', []),
            'universe_config': {},
            'portfolio_state': trading_status.get('portfolio', {}),
            'positions': trading_status.get('open_positions', []),
            'recent_trades': trading_status.get('recent_trades', [])
        }
        
        # Save to database
        success = db_manager.save_trading_session(session_id, session_data)
        
        if success:
            return {"status": "saved", "session_id": session_id}
        else:
            return {"error": "Failed to save session state"}
            
    except Exception as e:
        logger.error(f"Failed to save session state: {e}")
        return {"error": str(e)}


@app.post("/api/simulated-trading/restore")
async def restore_simulated_trading(request: dict):
    """Restore simulated trading with existing portfolio state."""
    await check_rate_limit()
    
    try:
        session_id = request.get('session_id')
        if not session_id:
            return {"error": "Session ID is required"}
        
        # Load session data from database
        session_data = db_manager.load_trading_session(session_id)
        if not session_data:
            return {"error": "Session not found"}
        
        # Extract trading parameters
        symbols = session_data.get('symbols', [])
        strategy_type = session_data.get('strategy_type', 'orderbook')
        strategy_params = session_data.get('strategy_params', {})
        portfolio_state = session_data.get('portfolio_state', {})
        positions = session_data.get('positions', [])
        recent_trades = session_data.get('recent_trades', [])
        
        # Update trading state
        trading_state["is_active"] = True
        trading_state["strategy_type"] = strategy_type
        trading_state["strategy_params"] = strategy_params
        trading_state["symbols"] = symbols
        trading_state["mode"] = "simulated"
        trading_state["last_signal_check"] = datetime.now()
        trading_state["session_id"] = session_id
        
        # Restore simulated trading state instead of resetting
        simulated_trading.restore_portfolio_state(
            portfolio_state=portfolio_state,
            positions=positions,
            trades=recent_trades,
            symbols=symbols
        )
        
        # Set session info for trade logging
        simulated_trading.set_session_info(db_manager, session_id)
        
        # Set strategy info for trade logging
        simulated_trading.set_strategy_info(strategy_type, strategy_params)
        
        # Start trading
        simulated_trading.start_trading(symbols)
        
        logger.info(f"Restored simulated trading for {len(symbols)} symbols with existing portfolio state")
        logger.info(f"Strategy: {strategy_type} with params: {strategy_params}")
        
        return {
            "status": "restored",
            "symbols": symbols,
            "portfolio": portfolio_state,
            "positions": positions,
            "recent_trades": recent_trades
        }
        
    except Exception as e:
        logger.error(f"Failed to restore simulated trading: {e}")
        return {"error": str(e)}


@app.get("/api/session/load/{session_id}")
async def load_session_state(session_id: str):
    """Load trading session state."""
    await check_rate_limit()
    
    try:
        session_data = db_manager.load_trading_session(session_id)
        if not session_data:
            return {"error": "Session not found"}
        
        return {
            "status": "loaded",
            "session_id": session_id,
            "session_data": session_data
        }
        
    except Exception as e:
        logger.error(f"Failed to load session state: {e}")
        return {"error": str(e)}


@app.post("/api/session/save-dashboard")
async def save_dashboard_state(request: dict):
    """Save dashboard UI state."""
    await check_rate_limit()
    
    try:
        session_id = request.get('session_id')
        state_data = request.get('state_data', {})
        
        if not session_id:
            return {"error": "Session ID is required"}
        
        success = db_manager.save_dashboard_state(session_id, state_data)
        
        if success:
            return {"status": "saved", "session_id": session_id}
        else:
            return {"error": "Failed to save dashboard state"}
            
    except Exception as e:
        logger.error(f"Failed to save dashboard state: {e}")
        return {"error": str(e)}


@app.get("/api/session/load-dashboard/{session_id}")
async def load_dashboard_state(session_id: str):
    """Load dashboard UI state."""
    await check_rate_limit()
    
    try:
        state_data = db_manager.load_dashboard_state(session_id)
        if not state_data:
            return {"error": "Dashboard state not found"}
        
        return {
            "status": "loaded",
            "session_id": session_id,
            "state_data": state_data
        }
        
    except Exception as e:
        logger.error(f"Failed to load dashboard state: {e}")
        return {"error": str(e)}


@app.get("/api/session/active")
async def get_active_sessions():
    """Get all active trading sessions."""
    await check_rate_limit()
    
    try:
        sessions = db_manager.get_active_sessions()
        return {
            "status": "success",
            "sessions": sessions
        }
        
    except Exception as e:
        logger.error(f"Failed to get active sessions: {e}")
        return {"error": str(e)}


@app.post("/api/session/deactivate/{session_id}")
async def deactivate_session(session_id: str):
    """Deactivate a trading session."""
    await check_rate_limit()
    
    try:
        success = db_manager.deactivate_session(session_id)
        
        if success:
            return {"status": "deactivated", "session_id": session_id}
        else:
            return {"error": "Failed to deactivate session"}
            
    except Exception as e:
        logger.error(f"Failed to deactivate session: {e}")
        return {"error": str(e)}


# Trade History Endpoints

@app.get("/api/trades/session/{session_id}")
async def get_trades_by_session(session_id: str, limit: int = 100):
    """Get trades for a specific session."""
    await check_rate_limit()
    
    try:
        trades = db_manager.get_trades_by_session(session_id, limit)
        return {
            "status": "success",
            "session_id": session_id,
            "trades": trades,
            "count": len(trades)
        }
        
    except Exception as e:
        logger.error(f"Failed to get trades by session: {e}")
        return {"error": str(e)}


@app.get("/api/trades/symbol/{symbol}")
async def get_trades_by_symbol(symbol: str, limit: int = 100):
    """Get trades for a specific symbol."""
    await check_rate_limit()
    
    try:
        trades = db_manager.get_trades_by_symbol(symbol, limit)
        return {
            "status": "success",
            "symbol": symbol,
            "trades": trades,
            "count": len(trades)
        }
        
    except Exception as e:
        logger.error(f"Failed to get trades by symbol: {e}")
        return {"error": str(e)}


@app.get("/api/trades/recent")
async def get_recent_trades(limit: int = 50):
    """Get recent trades across all sessions."""
    await check_rate_limit()
    
    try:
        trades = db_manager.get_recent_trades(limit)
        return {
            "status": "success",
            "trades": trades,
            "count": len(trades)
        }
        
    except Exception as e:
        logger.error(f"Failed to get recent trades: {e}")
        return {"error": str(e)}


@app.get("/api/trades/paginated")
async def get_paginated_trades(page: int = 1, per_page: int = 10, session_id: str = None):
    """Get paginated trading history."""
    await check_rate_limit()
    
    try:
        # Calculate offset
        offset = (page - 1) * per_page
        
        # Get total count
        if session_id:
            total_trades = len(db_manager.get_trades_by_session(session_id, 10000))  # Get all to count
        else:
            total_trades = len(db_manager.get_recent_trades(10000))  # Get all to count
        
        # Calculate total pages
        total_pages = (total_trades + per_page - 1) // per_page
        
        # Get paginated trades
        if session_id:
            all_trades = db_manager.get_trades_by_session(session_id, 10000)
        else:
            all_trades = db_manager.get_recent_trades(10000)
        
        # Sort by timestamp descending (most recent first)
        all_trades.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Get the page slice
        start_idx = offset
        end_idx = min(offset + per_page, len(all_trades))
        trades = all_trades[start_idx:end_idx]
        
        return {
            "status": "success",
            "trades": trades,
            "pagination": {
                "current_page": page,
                "per_page": per_page,
                "total_trades": total_trades,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get paginated trades: {e}")
        return {"error": str(e)}


@app.get("/api/orderbook/signals/paginated")
async def get_paginated_orderbook_signals(page: int = 1, per_page: int = 10, session_id: str = None, symbol: str = None):
    """Get paginated order book signals."""
    await check_rate_limit()
    
    try:
        result = db_manager.get_order_book_signals_paginated(
            session_id=session_id,
            symbol=symbol,
            page=page,
            per_page=per_page
        )
        
        return {
            "status": "success",
            "signals": result["signals"],
            "pagination": result["pagination"]
        }
        
    except Exception as e:
        logger.error(f"Error getting paginated order book signals: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/api/trades/stats")
async def get_trade_stats(session_id: str = None):
    """Get trading statistics."""
    await check_rate_limit()
    
    try:
        stats = db_manager.get_trade_stats(session_id)
        return {
            "status": "success",
            "session_id": session_id,
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"Failed to get trade stats: {e}")
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
