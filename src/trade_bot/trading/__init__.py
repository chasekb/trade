"""Trading domain - Strategies and trading logic."""

from .trading_strategy import (
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
    OrderBookStrategy
)
from .simulated_trading_manager import SimulatedTradingManager
from .live_signal_scheduler import (
    BoundedQuoteScheduler, ExchangeBudget, IntentLedger, SchedulerConfig,
)

__all__ = [
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
    'BoundedQuoteScheduler',
    'ExchangeBudget',
    'IntentLedger',
    'SchedulerConfig'
]
