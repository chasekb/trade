"""Base database class with common functionality."""

import sqlite3
import json
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)


class BaseDatabase:
    """Base database class with common functionality."""
    
    def __init__(self, db_path: str = "trading_cache.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            self._create_tables(cursor)
            conn.commit()
    
    def _create_tables(self, cursor):
        """Create database tables. Override in subclasses."""
        pass
    
    def _calculate_hash(self, data: Any) -> str:
        """Calculate hash for data to detect changes."""
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.md5(data_str.encode()).hexdigest()
    
    def _get_expiration_time(self, data_type: str) -> datetime:
        """Get expiration time for different data types."""
        now = datetime.now()
        expiration_hours = {
            'historical_candles': 24,  # 24 hours
            'order_book_snapshots': 1,  # 1 hour
            'trade_history': 168,  # 1 week
            'trading_sessions': 720,  # 30 days
            'dashboard_state': 24,  # 24 hours
        }
        hours = expiration_hours.get(data_type, 24)
        return now + timedelta(hours=hours)
    
    def _execute_query(self, query: str, params: tuple = ()) -> list:
        """Execute a query and return results."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Database query error: {e}")
            return []
    
    def _execute_update(self, query: str, params: tuple = ()) -> bool:
        """Execute an update query."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Database update error: {e}")
            return False
    
    def cleanup_expired_data(self, table_name: str) -> int:
        """Clean up expired data from a specific table."""
        query = f"""
            DELETE FROM {table_name} 
            WHERE expires_at IS NOT NULL AND expires_at < ?
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(query, (datetime.now(),))
                deleted_count = cursor.rowcount
                conn.commit()
                return deleted_count
        except Exception as e:
            logger.error(f"Error cleaning up expired data from {table_name}: {e}")
            return 0
