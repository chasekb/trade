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
    'SimulatedTradingManager'
]
