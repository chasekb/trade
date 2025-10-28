"""Web handlers package."""

from .api_handlers import APIHandlers
from .dashboard_handlers import DashboardHandlers
from .backtest_handlers import BacktestHandlers
from .trading_handlers import TradingHandlers
from .websocket_handlers import WebSocketHandlers
from .data_handlers import DataHandlers
from .live_portfolio_handlers import LivePortfolioHandlers

__all__ = [
    'APIHandlers',
    'DashboardHandlers',
    'BacktestHandlers',
    'TradingHandlers',
    'WebSocketHandlers',
    'DataHandlers',
    'LivePortfolioHandlers'
]
