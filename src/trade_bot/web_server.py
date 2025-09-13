"""Web server for trading dashboard with real-time data and backtesting."""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import TradingConfig
from .data_provider import CoinbaseDataProvider
from .backtester import Backtester
from .trading_strategy import SimpleMovingAverageStrategy
from .websocket_client import WebSocketClient
from .data_handler import DataHandler

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        """Start the real-time data feed."""
        if not self.websocket_client:
            self.websocket_client = WebSocketClient(config)
            self.data_handler = DataHandler(config)
            
            # Register message handlers
            self.websocket_client.register_handler('ticker', self._handle_ticker_message)
            self.websocket_client.register_handler('l2update', self._handle_l2update_message)
            
            # Start the websocket client
            asyncio.create_task(self._run_websocket_client())
            
            # Start the data collection task
            asyncio.create_task(self._collect_real_time_data())
    
    async def _run_websocket_client(self):
        """Run the websocket client in the background."""
        try:
            await self.websocket_client.connect()
            await self.websocket_client.subscribe_to_ticker(config.product_id)
            await self.websocket_client.subscribe_to_level2(config.product_id)
            await self.websocket_client.listen()
        except Exception as e:
            logger.error(f"WebSocket client error: {e}")
    
    async def _handle_ticker_message(self, data):
        """Handle ticker messages."""
        if 'ticker' in data:
            self.data_handler.add_ticker_data(data['ticker'])
    
    async def _handle_l2update_message(self, data):
        """Handle level2 update messages."""
        if 'changes' in data:
            self.data_handler.add_level2_data(data)
    
    async def _collect_real_time_data(self):
        """Collect real-time data and broadcast to clients."""
        while True:
            try:
                # Get latest data from data handler
                ticker_data = self.data_handler.get_latest_ticker()
                trade_data = self.data_handler.get_latest_trades()
                
                if ticker_data:
                    real_time_data[config.product_id] = {
                        'ticker': ticker_data,
                        'trades': trade_data,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    # Broadcast to all connected clients
                    await self.broadcast(json.dumps({
                        'type': 'real_time_data',
                        'data': real_time_data[config.product_id]
                    }))
                
                await asyncio.sleep(1)  # Update every second
                
            except Exception as e:
                logger.error(f"Error in real-time data collection: {e}")
                await asyncio.sleep(5)


# Initialize WebSocket manager
manager = WebSocketManager()


@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    logger.info("Starting Trading Dashboard...")
    # Start real-time data collection
    await manager.start_real_time_data()


@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    """Serve the main dashboard page."""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "product_id": config.product_id
    })


@app.get("/api/real-time-data")
async def get_real_time_data():
    """Get current real-time data."""
    return real_time_data.get(config.product_id, {})


@app.get("/api/historical-data")
async def get_historical_data(
    product_id: str = None,
    days: int = 7,
    granularity: int = 3600
):
    """Get historical data for a product."""
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


@app.post("/api/run-backtest")
async def run_backtest(
    product_id: str = None,
    days: int = 7,
    short_window: int = 5,
    long_window: int = 20
):
    """Run a backtest and return results."""
    if not product_id:
        product_id = config.product_id
    
    try:
        # Get historical data
        data_provider = CoinbaseDataProvider(product_id)
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        historical_data = await data_provider.get_historical_candles(
            start_time=start_time,
            end_time=end_time,
            granularity=3600
        )
        
        if not historical_data:
            return {"error": "No historical data available"}
        
        # Create backtester
        backtester = Backtester(
            config=config,
            strategy_class=SimpleMovingAverageStrategy,
            strategy_params={
                'short_window': short_window,
                'long_window': long_window
            }
        )
        
        # Run backtest
        result = await backtester.run_backtest(historical_data)
        
        # Store results
        backtest_key = f"{product_id}_{days}_{short_window}_{long_window}"
        backtest_results[backtest_key] = {
            'result': result,
            'trades_df': backtester.get_trades_df().to_dict('records'),
            'equity_df': backtester.get_equity_curve_df().to_dict('records'),
            'timestamp': datetime.now().isoformat()
        }
        
        return {
            'success': True,
            'result': result,
            'trades': backtester.get_trades_df().to_dict('records'),
            'equity_curve': backtester.get_equity_curve_df().to_dict('records')
        }
        
    except Exception as e:
        logger.error(f"Backtest error: {e}")
        return {"error": str(e)}


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


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_connections": len(manager.active_connections),
        "cached_data_points": len(historical_data_cache),
        "backtest_results": len(backtest_results)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
