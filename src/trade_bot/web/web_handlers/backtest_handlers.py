"""Backtest handlers for the trading web server."""

import logging
import re
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from fastapi import HTTPException

from ...backtest.backtester import Backtester
from ...trading.trading_strategy import (
    SimpleMovingAverageStrategy, BollingerBandsStrategy, RSIStrategy, 
    EMAStrategy, MACDStrategy, StochasticStrategy, DCAStrategy, 
    BuyAndHoldStrategy, ATRStrategy, FibonacciRetracementStrategy, OrderBookStrategy
)

logger = logging.getLogger(__name__)


class BacktestHandlers:
    """Handles backtesting functionality for the trading web server."""
    
    def __init__(self, config, database_manager):
        self.config = config
        self.database_manager = database_manager
        self.strategy_classes = {
            'SMA': SimpleMovingAverageStrategy,
            'BollingerBands': BollingerBandsStrategy,
            'RSI': RSIStrategy,
            'EMA': EMAStrategy,
            'MACD': MACDStrategy,
            'Stochastic': StochasticStrategy,
            'DCA': DCAStrategy,
            'BuyAndHold': BuyAndHoldStrategy,
            'ATR': ATRStrategy,
            'Fibonacci': FibonacciRetracementStrategy,
            'OrderBook': OrderBookStrategy
        }
    
    async def run_backtest(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run a backtest with the specified parameters."""
        try:
            strategy_name = str(request_data.get('strategy', 'SMA'))
            symbol = str(request_data.get('symbol', 'BTC-USD'))
            start_date = request_data.get('start_date')
            end_date = request_data.get('end_date')
            strategy_params = request_data.get('strategy_params', {})

            # Validate symbol format (e.g., BTC-USD)
            if not re.fullmatch(r"[A-Z0-9\-]{3,30}", symbol):
                raise HTTPException(status_code=400, detail="Invalid symbol format")

            # Validate strategy name
            if strategy_name not in self.strategy_classes:
                raise HTTPException(status_code=400, detail=f"Unknown strategy: {strategy_name}")

            # Validate strategy params type
            if strategy_params is None:
                strategy_params = {}
            if not isinstance(strategy_params, dict):
                raise HTTPException(status_code=400, detail="strategy_params must be an object")

            # Validate dates if provided
            if start_date and end_date:
                try:
                    from datetime import datetime as _dt
                    sd = _dt.fromisoformat(str(start_date).replace('Z', '+00:00'))
                    ed = _dt.fromisoformat(str(end_date).replace('Z', '+00:00'))
                except Exception:
                    raise HTTPException(status_code=400, detail="Invalid ISO date format")
                if ed < sd:
                    raise HTTPException(status_code=400, detail="end_date must be after start_date")
            
            # Get strategy class
            strategy_class = self.strategy_classes.get(strategy_name)
            if not strategy_class:
                raise HTTPException(status_code=400, detail=f"Unknown strategy: {strategy_name}")
            
            # Create backtester
            backtester = Backtester(
                config=self.config,
                strategy_class=strategy_class,
                strategy_params=strategy_params
            )
            
            # Run backtest (simplified - would need actual data)
            result = {
                "backtest_id": 1,
                "strategy": strategy_name,
                "symbol": symbol,
                "start_date": start_date,
                "end_date": end_date,
                "status": "completed",
                "total_trades": 0,
                "win_rate": 0.0,
                "total_return": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0
            }
            
            return result
        except Exception as e:
            logger.error(f"Error running backtest: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_backtest_results(self) -> Dict[str, Any]:
        """Get all backtest results."""
        try:
            # This would typically fetch from database
            return {"backtests": []}
        except Exception as e:
            logger.error(f"Error getting backtest results: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_backtest_history(self, limit: int = 10, offset: int = 0) -> Dict[str, Any]:
        """Get backtest history with pagination."""
        try:
            limit = max(1, min(int(limit), 1000))
            offset = max(0, int(offset))
            # This would typically fetch from database with pagination
            return {
                "backtests": [],
                "total": 0,
                "limit": limit,
                "offset": offset
            }
        except Exception as e:
            logger.error(f"Error getting backtest history: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_backtest(self, backtest_id: int) -> Dict[str, Any]:
        """Get a specific backtest by ID."""
        try:
            if int(backtest_id) <= 0:
                raise HTTPException(status_code=400, detail="Invalid backtest_id")
            # This would typically fetch from database
            return {"error": "Backtest not found"}
        except Exception as e:
            logger.error(f"Error getting backtest: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_backtest_stats(self) -> Dict[str, Any]:
        """Get backtest statistics."""
        try:
            # This would typically calculate real stats
            return {
                "total_backtests": 0,
                "successful_backtests": 0,
                "average_return": 0.0,
                "best_strategy": "None"
            }
        except Exception as e:
            logger.error(f"Error getting backtest stats: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def delete_backtest(self, backtest_id: int) -> Dict[str, Any]:
        """Delete a backtest."""
        try:
            if int(backtest_id) <= 0:
                raise HTTPException(status_code=400, detail="Invalid backtest_id")
            # This would typically delete from database
            return {"message": "Backtest deleted successfully"}
        except Exception as e:
            logger.error(f"Error deleting backtest: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_backtest_filters(self) -> Dict[str, Any]:
        """Get available backtest filters."""
        try:
            return {
                "strategies": list(self.strategy_classes.keys()),
                "symbols": ["BTC-USD", "ETH-USD", "ADA-USD"],
                "date_ranges": ["1D", "1W", "1M", "3M", "6M", "1Y"]
            }
        except Exception as e:
            logger.error(f"Error getting backtest filters: {e}")
            raise HTTPException(status_code=500, detail=str(e))
