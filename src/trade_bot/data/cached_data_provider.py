"""
Cached data provider that uses database caching for improved performance.
"""

import asyncio
import aiohttp
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import time

from ..data.data_provider import CoinbaseDataProvider
from ..database.database_manager import DatabaseManager

logger = logging.getLogger(__name__)

class CachedDataProvider(CoinbaseDataProvider):
    """Data provider with database caching for improved performance."""
    
    def __init__(self, config, db_path: str = "data/databases/trading_cache.db"):
        super().__init__(config)
        self.db_manager = DatabaseManager(db_path)
        self.cache_hits = 0
        self.cache_misses = 0
        self.api_calls = 0
    
    def get_cache_stats(self) -> Dict[str, any]:
        """Get cache performance statistics."""
        db_stats = self.db_manager.get_cache_stats()
        return {
            **db_stats,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'api_calls': self.api_calls,
            'hit_rate': self.cache_hits / (self.cache_hits + self.cache_misses) if (self.cache_hits + self.cache_misses) > 0 else 0
        }
    
    async def get_historical_candles(self, start_time, end_time, granularity: int = 60) -> List[Dict]:
        """Get historical candles with caching."""
        # Convert datetime objects to timestamps for caching
        from datetime import datetime
        if isinstance(start_time, datetime):
            start_timestamp = int(start_time.timestamp())
        else:
            start_timestamp = int(start_time)
            
        if isinstance(end_time, datetime):
            end_timestamp = int(end_time.timestamp())
        else:
            end_timestamp = int(end_time)
        
        # Try to get from cache first
        cached_data = self.db_manager.get_historical_candles(
            self.product_id, start_timestamp, end_timestamp, granularity
        )
        
        if cached_data is not None:
            self.cache_hits += 1
            logger.debug(f"Cache HIT for candles: {self.product_id} ({start_timestamp}-{end_timestamp})")
            return cached_data
        
        # Cache miss - fetch from API
        self.cache_misses += 1
        self.api_calls += 1
        logger.debug(f"Cache MISS for candles: {self.product_id} ({start_timestamp}-{end_timestamp})")
        
        # Fetch from parent class (API)
        data = await super().get_historical_candles(start_time, end_time, granularity)
        
        # Cache the result
        if data:
            self.db_manager.cache_historical_candles(
                self.product_id, start_timestamp, end_timestamp, granularity, data
            )
            logger.debug(f"Cached {len(data)} candles for {self.product_id}")
        
        return data
    
    async def get_order_book(self, product_id: str) -> Optional[Dict]:
        """Get order book with caching."""
        # For order book, we use current timestamp as key
        current_timestamp = int(time.time())
        
        # Try to get from cache first
        cached_data = self.db_manager.get_order_book_snapshot(product_id, current_timestamp)
        
        if cached_data is not None:
            self.cache_hits += 1
            logger.debug(f"Cache HIT for order book: {product_id}")
            return cached_data
        
        # Cache miss - fetch from API
        self.cache_misses += 1
        self.api_calls += 1
        logger.debug(f"Cache MISS for order book: {product_id}")
        
        # Fetch from parent class (API)
        data = await super().get_order_book(product_id)
        
        # Cache the result
        if data:
            self.db_manager.cache_order_book_snapshot(product_id, current_timestamp, data)
            logger.debug(f"Cached order book snapshot for {product_id}")
        
        return data
    
    async def get_recent_trades(self, product_id: str, limit: int = 100) -> List[Dict]:
        """Get recent trades with caching."""
        # For trades, we use a time window as key
        end_time = int(time.time())
        start_time = end_time - 3600  # 1 hour window
        
        # Try to get from cache first
        cached_data = self.db_manager.get_trade_history(product_id, start_time, end_time)
        
        if cached_data is not None:
            self.cache_hits += 1
            logger.debug(f"Cache HIT for trades: {product_id}")
            # Limit the results to requested limit
            return cached_data[:limit]
        
        # Cache miss - fetch from API
        self.cache_misses += 1
        self.api_calls += 1
        logger.debug(f"Cache MISS for trades: {product_id}")
        
        # Fetch from parent class (API)
        data = await super().get_recent_trades(limit)
        
        # Cache the result
        if data:
            self.db_manager.cache_trade_history(product_id, start_time, end_time, data)
            logger.debug(f"Cached {len(data)} trades for {product_id}")
        
        return data
    
    async def cleanup_expired_cache(self) -> int:
        """Clean up expired cache entries."""
        return self.db_manager.cleanup_expired_data()
    
    def clear_cache(self) -> bool:
        """Clear all cached data."""
        return self.db_manager.clear_all_cache()
    
    def reset_stats(self):
        """Reset cache statistics."""
        self.cache_hits = 0
        self.cache_misses = 0
        self.api_calls = 0
