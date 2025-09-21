"""Cache manager for historical trading data."""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import logging

from .base_database import BaseDatabase

logger = logging.getLogger(__name__)


class CacheManager(BaseDatabase):
    """Manages caching of historical trading data."""
    
    def _create_tables(self, cursor):
        """Create cache-related tables."""
        # Historical candles table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historical_candles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                start_time INTEGER NOT NULL,
                end_time INTEGER NOT NULL,
                granularity INTEGER NOT NULL,
                data_hash TEXT NOT NULL,
                data_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                UNIQUE(product_id, start_time, end_time, granularity)
            )
        """)
        
        # Order book snapshots table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_book_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                data_hash TEXT NOT NULL,
                data_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                UNIQUE(product_id, timestamp)
            )
        """)
        
        # Trade history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trade_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                start_time INTEGER NOT NULL,
                end_time INTEGER NOT NULL,
                data_hash TEXT NOT NULL,
                data_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                UNIQUE(product_id, start_time, end_time)
            )
        """)
    
    def cache_historical_candles(self, product_id: str, start_time: int, end_time: int, 
                                granularity: int, data: List[Dict]) -> bool:
        """Cache historical candles data."""
        try:
            data_hash = self._calculate_hash(data)
            data_json = json.dumps(data)
            expires_at = self._get_expiration_time('historical_candles')
            
            query = """
                INSERT OR REPLACE INTO historical_candles 
                (product_id, start_time, end_time, granularity, data_hash, data_json, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            
            return self._execute_update(query, (
                product_id, start_time, end_time, granularity, 
                data_hash, data_json, expires_at
            ))
        except Exception as e:
            logger.error(f"Error caching historical candles: {e}")
            return False
    
    def get_historical_candles(self, product_id: str, start_time: int, end_time: int, 
                              granularity: int) -> Optional[List[Dict]]:
        """Get cached historical candles data."""
        try:
            query = """
                SELECT data_json, expires_at FROM historical_candles 
                WHERE product_id = ? AND start_time = ? AND end_time = ? AND granularity = ?
            """
            
            results = self._execute_query(query, (product_id, start_time, end_time, granularity))
            
            if results:
                data_json, expires_at = results[0]
                
                # Check if data has expired
                if expires_at and datetime.fromisoformat(expires_at) < datetime.now():
                    logger.info("Cached data has expired")
                    return None
                
                return json.loads(data_json)
            
            return None
        except Exception as e:
            logger.error(f"Error getting historical candles: {e}")
            return None
    
    def cache_order_book_snapshot(self, product_id: str, timestamp: int, data: Dict) -> bool:
        """Cache order book snapshot data."""
        try:
            data_hash = self._calculate_hash(data)
            data_json = json.dumps(data)
            expires_at = self._get_expiration_time('order_book_snapshots')
            
            query = """
                INSERT OR REPLACE INTO order_book_snapshots 
                (product_id, timestamp, data_hash, data_json, expires_at)
                VALUES (?, ?, ?, ?, ?)
            """
            
            return self._execute_update(query, (product_id, timestamp, data_hash, data_json, expires_at))
        except Exception as e:
            logger.error(f"Error caching order book snapshot: {e}")
            return False
    
    def get_order_book_snapshot(self, product_id: str, timestamp: int) -> Optional[Dict]:
        """Get cached order book snapshot data."""
        try:
            query = """
                SELECT data_json, expires_at FROM order_book_snapshots 
                WHERE product_id = ? AND timestamp = ?
            """
            
            results = self._execute_query(query, (product_id, timestamp))
            
            if results:
                data_json, expires_at = results[0]
                
                # Check if data has expired
                if expires_at and datetime.fromisoformat(expires_at) < datetime.now():
                    logger.info("Cached data has expired")
                    return None
                
                return json.loads(data_json)
            
            return None
        except Exception as e:
            logger.error(f"Error getting order book snapshot: {e}")
            return None
    
    def cache_trade_history(self, product_id: str, start_time: int, end_time: int, 
                           data: List[Dict]) -> bool:
        """Cache trade history data."""
        try:
            data_hash = self._calculate_hash(data)
            data_json = json.dumps(data)
            expires_at = self._get_expiration_time('trade_history')
            
            query = """
                INSERT OR REPLACE INTO trade_history 
                (product_id, start_time, end_time, data_hash, data_json, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            
            return self._execute_update(query, (product_id, start_time, end_time, data_hash, data_json, expires_at))
        except Exception as e:
            logger.error(f"Error caching trade history: {e}")
            return False
    
    def get_trade_history(self, product_id: str, start_time: int, end_time: int) -> Optional[List[Dict]]:
        """Get cached trade history data."""
        try:
            query = """
                SELECT data_json, expires_at FROM trade_history 
                WHERE product_id = ? AND start_time = ? AND end_time = ?
            """
            
            results = self._execute_query(query, (product_id, start_time, end_time))
            
            if results:
                data_json, expires_at = results[0]
                
                # Check if data has expired
                if expires_at and datetime.fromisoformat(expires_at) < datetime.now():
                    logger.info("Cached data has expired")
                    return None
                
                return json.loads(data_json)
            
            return None
        except Exception as e:
            logger.error(f"Error getting trade history: {e}")
            return None
    
    def cleanup_expired_data(self) -> int:
        """Clean up all expired cache data."""
        total_deleted = 0
        tables = ['historical_candles', 'order_book_snapshots', 'trade_history']
        
        for table in tables:
            deleted = super().cleanup_expired_data(table)
            total_deleted += deleted
            logger.info(f"Cleaned up {deleted} expired records from {table}")
        
        return total_deleted
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            stats = {}
            
            # Get counts for each table
            tables = ['historical_candles', 'order_book_snapshots', 'trade_history']
            for table in tables:
                query = f"SELECT COUNT(*) FROM {table}"
                results = self._execute_query(query)
                stats[f"{table}_count"] = results[0][0] if results else 0
                
                # Get total size
                query = f"SELECT SUM(LENGTH(data_json)) FROM {table}"
                results = self._execute_query(query)
                stats[f"{table}_size_bytes"] = results[0][0] if results and results[0][0] else 0
            
            # Get total cache size
            stats['total_size_bytes'] = sum(stats.get(f"{table}_size_bytes", 0) for table in tables)
            stats['total_records'] = sum(stats.get(f"{table}_count", 0) for table in tables)
            
            return stats
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}
    
    def clear_all_cache(self) -> bool:
        """Clear all cached data."""
        try:
            tables = ['historical_candles', 'order_book_snapshots', 'trade_history']
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                for table in tables:
                    cursor.execute(f"DELETE FROM {table}")
                conn.commit()
            
            logger.info("All cache data cleared")
            return True
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False
