"""
Database manager for caching trading data.
"""

import sqlite3
import json
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages SQLite database for caching trading data."""
    
    def __init__(self, db_path: str = "trading_cache.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
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
            
            # Create indexes for better performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_candles_product_time ON historical_candles(product_id, start_time, end_time)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_candles_granularity ON historical_candles(granularity)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_candles_expires ON historical_candles(expires_at)")
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_orderbook_product_time ON order_book_snapshots(product_id, timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_orderbook_expires ON order_book_snapshots(expires_at)")
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_product_time ON trade_history(product_id, start_time, end_time)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_expires ON trade_history(expires_at)")
            
            conn.commit()
            logger.info("Database initialized successfully")
    
    def _calculate_hash(self, data: Any) -> str:
        """Calculate hash for data integrity checking."""
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.md5(data_str.encode()).hexdigest()
    
    def _get_expiration_time(self, data_type: str) -> datetime:
        """Get expiration time based on data type."""
        now = datetime.now()
        if data_type == "candles":
            return now + timedelta(hours=1)  # Historical data changes less frequently
        elif data_type == "orderbook":
            return now + timedelta(minutes=5)  # Order book changes frequently
        elif data_type == "trades":
            return now + timedelta(minutes=10)  # Trade history changes moderately
        else:
            return now + timedelta(hours=1)
    
    def cache_historical_candles(self, product_id: str, start_time: int, end_time: int, 
                                granularity: int, data: List[Dict]) -> bool:
        """Cache historical candles data."""
        try:
            data_hash = self._calculate_hash(data)
            expires_at = self._get_expiration_time("candles")
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO historical_candles 
                    (product_id, start_time, end_time, granularity, data_hash, data_json, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (product_id, start_time, end_time, granularity, data_hash, 
                      json.dumps(data), expires_at))
                conn.commit()
            
            logger.debug(f"Cached {len(data)} candles for {product_id} ({start_time}-{end_time})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache historical candles: {e}")
            return False
    
    def get_historical_candles(self, product_id: str, start_time: int, end_time: int, 
                              granularity: int) -> Optional[List[Dict]]:
        """Retrieve cached historical candles data."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT data_json, expires_at FROM historical_candles
                    WHERE product_id = ? AND start_time = ? AND end_time = ? AND granularity = ?
                    AND expires_at > CURRENT_TIMESTAMP
                """, (product_id, start_time, end_time, granularity))
                
                result = cursor.fetchone()
                if result:
                    data_json, expires_at = result
                    data = json.loads(data_json)
                    logger.debug(f"Retrieved {len(data)} cached candles for {product_id}")
                    return data
                else:
                    logger.debug(f"No valid cached candles found for {product_id}")
                    return None
                    
        except Exception as e:
            logger.error(f"Failed to retrieve cached historical candles: {e}")
            return None
    
    def cache_order_book_snapshot(self, product_id: str, timestamp: int, data: Dict) -> bool:
        """Cache order book snapshot."""
        try:
            data_hash = self._calculate_hash(data)
            expires_at = self._get_expiration_time("orderbook")
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO order_book_snapshots 
                    (product_id, timestamp, data_hash, data_json, expires_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (product_id, timestamp, data_hash, json.dumps(data), expires_at))
                conn.commit()
            
            logger.debug(f"Cached order book snapshot for {product_id} at {timestamp}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache order book snapshot: {e}")
            return False
    
    def get_order_book_snapshot(self, product_id: str, timestamp: int) -> Optional[Dict]:
        """Retrieve cached order book snapshot."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT data_json, expires_at FROM order_book_snapshots
                    WHERE product_id = ? AND timestamp = ?
                    AND expires_at > CURRENT_TIMESTAMP
                """, (product_id, timestamp))
                
                result = cursor.fetchone()
                if result:
                    data_json, expires_at = result
                    data = json.loads(data_json)
                    logger.debug(f"Retrieved cached order book snapshot for {product_id}")
                    return data
                else:
                    logger.debug(f"No valid cached order book snapshot found for {product_id}")
                    return None
                    
        except Exception as e:
            logger.error(f"Failed to retrieve cached order book snapshot: {e}")
            return None
    
    def cache_trade_history(self, product_id: str, start_time: int, end_time: int, 
                           data: List[Dict]) -> bool:
        """Cache trade history data."""
        try:
            data_hash = self._calculate_hash(data)
            expires_at = self._get_expiration_time("trades")
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO trade_history 
                    (product_id, start_time, end_time, data_hash, data_json, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (product_id, start_time, end_time, data_hash, 
                      json.dumps(data), expires_at))
                conn.commit()
            
            logger.debug(f"Cached {len(data)} trades for {product_id} ({start_time}-{end_time})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache trade history: {e}")
            return False
    
    def get_trade_history(self, product_id: str, start_time: int, end_time: int) -> Optional[List[Dict]]:
        """Retrieve cached trade history data."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT data_json, expires_at FROM trade_history
                    WHERE product_id = ? AND start_time = ? AND end_time = ?
                    AND expires_at > CURRENT_TIMESTAMP
                """, (product_id, start_time, end_time))
                
                result = cursor.fetchone()
                if result:
                    data_json, expires_at = result
                    data = json.loads(data_json)
                    logger.debug(f"Retrieved {len(data)} cached trades for {product_id}")
                    return data
                else:
                    logger.debug(f"No valid cached trade history found for {product_id}")
                    return None
                    
        except Exception as e:
            logger.error(f"Failed to retrieve cached trade history: {e}")
            return None
    
    def cleanup_expired_data(self) -> int:
        """Remove expired data from cache."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Count expired records
                cursor.execute("SELECT COUNT(*) FROM historical_candles WHERE expires_at <= CURRENT_TIMESTAMP")
                expired_candles = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM order_book_snapshots WHERE expires_at <= CURRENT_TIMESTAMP")
                expired_orderbook = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM trade_history WHERE expires_at <= CURRENT_TIMESTAMP")
                expired_trades = cursor.fetchone()[0]
                
                # Delete expired records
                cursor.execute("DELETE FROM historical_candles WHERE expires_at <= CURRENT_TIMESTAMP")
                cursor.execute("DELETE FROM order_book_snapshots WHERE expires_at <= CURRENT_TIMESTAMP")
                cursor.execute("DELETE FROM trade_history WHERE expires_at <= CURRENT_TIMESTAMP")
                
                conn.commit()
                
                total_expired = expired_candles + expired_orderbook + expired_trades
                logger.info(f"Cleaned up {total_expired} expired records")
                return total_expired
                
        except Exception as e:
            logger.error(f"Failed to cleanup expired data: {e}")
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                stats = {}
                
                # Historical candles stats
                cursor.execute("SELECT COUNT(*) FROM historical_candles")
                stats['candles_count'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM historical_candles WHERE expires_at > CURRENT_TIMESTAMP")
                stats['candles_valid'] = cursor.fetchone()[0]
                
                # Order book stats
                cursor.execute("SELECT COUNT(*) FROM order_book_snapshots")
                stats['orderbook_count'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM order_book_snapshots WHERE expires_at > CURRENT_TIMESTAMP")
                stats['orderbook_valid'] = cursor.fetchone()[0]
                
                # Trade history stats
                cursor.execute("SELECT COUNT(*) FROM trade_history")
                stats['trades_count'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM trade_history WHERE expires_at > CURRENT_TIMESTAMP")
                stats['trades_valid'] = cursor.fetchone()[0]
                
                # Database size
                cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
                stats['db_size_bytes'] = cursor.fetchone()[0]
                
                return stats
                
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {}
    
    def clear_all_cache(self) -> bool:
        """Clear all cached data."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM historical_candles")
                cursor.execute("DELETE FROM order_book_snapshots")
                cursor.execute("DELETE FROM trade_history")
                conn.commit()
            
            logger.info("Cleared all cached data")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return False
