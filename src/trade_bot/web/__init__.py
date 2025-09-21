"""Web domain - Web server and handlers."""

from .web_server import app as web_app
from .web_server_new import app as new_web_app
from .web_components import RateLimiter, WebSocketManager
from .web_handlers import (
    APIHandlers,
    DashboardHandlers,
    BacktestHandlers,
    TradingHandlers,
    WebSocketHandlers,
    DataHandlers
)

__all__ = [
    'web_app',
    'new_web_app',
    'RateLimiter',
    'WebSocketManager',
    'APIHandlers',
    'DashboardHandlers',
    'BacktestHandlers',
    'TradingHandlers',
    'WebSocketHandlers',
    'DataHandlers'
]
