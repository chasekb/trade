"""New modular database manager using component architecture."""

import logging
from typing import List, Dict, Optional, Any

from .database_components import CacheManager, SessionManager, TradeManager, SignalManager

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Modular database manager using component architecture."""
    
    def __init__(self, db_path: str = "trading_cache.db"):
        self.db_path = db_path
        self.cache_manager = CacheManager(db_path)
        self.session_manager = SessionManager(db_path)
        self.trade_manager = TradeManager(db_path)
        self.signal_manager = SignalManager(db_path)
        logger.info("Database initialized successfully")
    
    # Cache Manager Methods
    def cache_historical_candles(self, product_id: str, start_time: int, end_time: int, 
                                granularity: int, data: List[Dict]) -> bool:
        """Cache historical candles data."""
        return self.cache_manager.cache_historical_candles(product_id, start_time, end_time, granularity, data)
    
    def get_historical_candles(self, product_id: str, start_time: int, end_time: int, 
                              granularity: int) -> Optional[List[Dict]]:
        """Get cached historical candles data."""
        return self.cache_manager.get_historical_candles(product_id, start_time, end_time, granularity)
    
    def cache_order_book_snapshot(self, product_id: str, timestamp: int, data: Dict) -> bool:
        """Cache order book snapshot data."""
        return self.cache_manager.cache_order_book_snapshot(product_id, timestamp, data)
    
    def get_order_book_snapshot(self, product_id: str, timestamp: int) -> Optional[Dict]:
        """Get cached order book snapshot data."""
        return self.cache_manager.get_order_book_snapshot(product_id, timestamp)
    
    def cache_trade_history(self, product_id: str, start_time: int, end_time: int, 
                           data: List[Dict]) -> bool:
        """Cache trade history data."""
        return self.cache_manager.cache_trade_history(product_id, start_time, end_time, data)
    
    def get_trade_history(self, product_id: str, start_time: int, end_time: int) -> Optional[List[Dict]]:
        """Get cached trade history data."""
        return self.cache_manager.get_trade_history(product_id, start_time, end_time)
    
    def cleanup_expired_data(self) -> int:
        """Clean up all expired cache data."""
        return self.cache_manager.cleanup_expired_data()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache_manager.get_cache_stats()
    
    def clear_all_cache(self) -> bool:
        """Clear all cached data."""
        return self.cache_manager.clear_all_cache()
    
    # Session Manager Methods
    def save_trading_session(self, session_id: str, session_data: Dict[str, Any]) -> bool:
        """Save trading session state."""
        return self.session_manager.save_trading_session(session_id, session_data)
    
    def load_trading_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load trading session state."""
        return self.session_manager.load_trading_session(session_id)
    
    def save_dashboard_state(self, session_id: str, state_data: Dict[str, Any]) -> bool:
        """Save dashboard UI state."""
        return self.session_manager.save_dashboard_state(session_id, state_data)
    
    def load_dashboard_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load dashboard UI state."""
        return self.session_manager.load_dashboard_state(session_id)
    
    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get all active trading sessions."""
        return self.session_manager.get_active_sessions()
    
    def deactivate_session(self, session_id: str) -> bool:
        """Deactivate a trading session."""
        return self.session_manager.deactivate_session(session_id)
    
    # Trade Manager Methods
    def save_trade(self, trade_data: Dict[str, Any]) -> bool:
        """Save individual trade record."""
        return self.trade_manager.save_trade(trade_data)
    
    def get_trades_by_session(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get trades for a specific session."""
        return self.trade_manager.get_trades_by_session(session_id, limit)
    
    def get_trades_by_symbol(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get trades for a specific symbol."""
        return self.trade_manager.get_trades_by_symbol(symbol, limit)
    
    def get_recent_trades(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get most recent trades across all sessions."""
        return self.trade_manager.get_recent_trades(limit)
    
    def get_trade_stats(self, session_id: str = None) -> Dict[str, Any]:
        """Get trade statistics."""
        return self.trade_manager.get_trade_stats(session_id)
    
    # Signal Manager Methods
    def save_order_book_signal(self, signal_data: Dict[str, Any]) -> bool:
        """Save order book signal."""
        return self.signal_manager.save_order_book_signal(signal_data)
    
    def get_order_book_signals_paginated(self, session_id: str = None, symbol: str = None, 
                                        limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """Get order book signals with pagination."""
        return self.signal_manager.get_order_book_signals_paginated(session_id, symbol, limit, offset)
    
    def get_signals_by_symbol(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get signals for a specific symbol."""
        return self.signal_manager.get_signals_by_symbol(symbol, limit)
    
    def mark_signal_processed(self, signal_id: str) -> bool:
        """Mark a signal as processed."""
        return self.signal_manager.mark_signal_processed(signal_id)
    
    def get_unprocessed_signals(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get unprocessed signals."""
        return self.signal_manager.get_unprocessed_signals(limit)
    
    def get_signal_stats(self, session_id: str = None) -> Dict[str, Any]:
        """Get signal statistics."""
        return self.signal_manager.get_signal_stats(session_id)
