"""Trading Bot - Modular trading system with domain-driven architecture."""

# Lazy imports to avoid dependency issues
def __getattr__(name):
    """Lazy import for better performance and dependency management."""
    if name == 'TradingConfig':
        from .core.config import TradingConfig
        return TradingConfig
    elif name == 'TradingBot':
        from .core.trading_bot import TradingBot
        return TradingBot
    elif name == 'UniverseSelector':
        from .core.universe_selector import UniverseSelector
        return UniverseSelector
    elif name in ['TradeSignal', 'BaseStrategy', 'SimpleMovingAverageStrategy', 
                  'BollingerBandsStrategy', 'RSIStrategy', 'EMAStrategy', 
                  'MACDStrategy', 'StochasticStrategy', 'DCAStrategy', 
                  'BuyAndHoldStrategy', 'ATRStrategy', 'FibonacciRetracementStrategy', 
                  'OrderBookStrategy', 'SimulatedTradingManager']:
        from .trading import (
            TradeSignal, BaseStrategy,
            SimpleMovingAverageStrategy,
            BollingerBandsStrategy,
            RSIStrategy,
            EMAStrategy,
            MACDStrategy,
            StochasticStrategy,
            DCAStrategy,
            BuyAndHoldStrategy,
            ATRStrategy,
            FibonacciRetracementStrategy,
            OrderBookStrategy,
            SimulatedTradingManager
        )
        return locals()[name]
    elif name in ['CoinbaseDataProvider', 'CachedDataProvider', 'DataHandler', 
                  'NewDataHandler', 'ProductFetcher', 'WebSocketClient', 'PolarsOptimizer']:
        from .data import (
            CoinbaseDataProvider,
            CachedDataProvider,
            DataHandler,
            NewDataHandler,
            ProductFetcher,
            WebSocketClient,
            PolarsOptimizer
        )
        return locals()[name]
    elif name == 'Backtester':
        from .backtest import Backtester
        return Backtester
    elif name in ['web_app', 'new_web_app', 'RateLimiter', 'WebSocketManager',
                  'APIHandlers', 'DashboardHandlers', 'BacktestHandlers',
                  'TradingHandlers', 'WebSocketHandlers', 'DataHandlers']:
        from .web import (
            web_app,
            new_web_app,
            RateLimiter,
            WebSocketManager,
            APIHandlers,
            DashboardHandlers,
            BacktestHandlers,
            TradingHandlers,
            WebSocketHandlers,
            DataHandlers
        )
        return locals()[name]
    elif name in ['BacktestDatabase', 'DatabaseManager', 'NewDatabaseManager']:
        from .database import (
            BacktestDatabase,
            DatabaseManager,
            NewDatabaseManager
        )
        return locals()[name]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = [
    # Core
    'TradingConfig',
    'TradingBot',
    'UniverseSelector',
    
    # Trading
    'TradeSignal',
    'BaseStrategy',
    'SimpleMovingAverageStrategy',
    'BollingerBandsStrategy',
    'RSIStrategy',
    'EMAStrategy',
    'MACDStrategy',
    'StochasticStrategy',
    'DCAStrategy',
    'BuyAndHoldStrategy',
    'ATRStrategy',
    'FibonacciRetracementStrategy',
    'OrderBookStrategy',
    'SimulatedTradingManager',
    
    # Data
    'CoinbaseDataProvider',
    'CachedDataProvider',
    'DataHandler',
    'NewDataHandler',
    'ProductFetcher',
    'WebSocketClient',
    'PolarsOptimizer',
    
    # Backtest
    'Backtester',
    
    # Web
    'web_app',
    'new_web_app',
    'RateLimiter',
    'WebSocketManager',
    'APIHandlers',
    'DashboardHandlers',
    'BacktestHandlers',
    'TradingHandlers',
    'WebSocketHandlers',
    'DataHandlers',
    
    # Database
    'BacktestDatabase',
    'DatabaseManager',
    'NewDatabaseManager'
]