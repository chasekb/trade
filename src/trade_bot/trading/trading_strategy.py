"""Trading strategy implementation - Legacy compatibility module."""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from ..core.config import TradingConfig
from .strategies import (
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

logger = logging.getLogger(__name__)

# Re-export all strategy classes for backward compatibility
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
    'OrderBookStrategy'
]