"""Core domain - Configuration and base classes."""

# Lazy imports to avoid dependency issues
def __getattr__(name):
    """Lazy import for better performance and dependency management."""
    if name == 'TradingConfig':
        from .config import TradingConfig
        return TradingConfig
    elif name == 'TradingBot':
        from .trading_bot import TradingBot
        return TradingBot
    elif name == 'UniverseSelector':
        from .universe_selector import UniverseSelector
        return UniverseSelector
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = [
    'TradingConfig',
    'TradingBot', 
    'UniverseSelector'
]
