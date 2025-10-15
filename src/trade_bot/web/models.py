"""
Pydantic models for API requests and responses.
"""

from pydantic import BaseModel
from typing import Dict, Any, Optional, List


class SubscriptionRequest(BaseModel):
    """WebSocket subscription request."""
    channel: str
    product_id: Optional[str] = None


class BacktestRequest(BaseModel):
    """Backtest execution request."""
    strategy: str
    symbol: str
    start_date: str
    end_date: str
    strategy_params: Dict[str, Any] = {}


class BacktestHistoryItem(BaseModel):
    """Single backtest history item."""
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
    """Paginated backtest history response."""
    backtests: List[BacktestHistoryItem]
    total: int
    limit: int
    offset: int


class BacktestStatsResponse(BaseModel):
    """Backtest statistics response."""
    total_backtests: int
    successful_backtests: int
    average_return: float
    best_strategy: str


class TradingStartRequest(BaseModel):
    """Trading session start request."""
    strategy: str
    symbols: List[str]
    mode: str  # 'simulated' or 'live'
    strategy_params: Dict[str, Any] = {}


class PositionCloseRequest(BaseModel):
    """Request to close a trading position."""
    position_id: str
    symbol: Optional[str] = None


class SessionSaveRequest(BaseModel):
    """Request to save trading session state."""
    session_id: Optional[str] = None
    trading_state: Dict[str, Any]
    positions: List[Dict[str, Any]] = []


class DashboardStateRequest(BaseModel):
    """Request to save dashboard state."""
    session_id: str
    state: Dict[str, Any]

