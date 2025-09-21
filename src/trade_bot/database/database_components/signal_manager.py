"""Signal manager for order book signals."""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
import logging

from .base_database import BaseDatabase

logger = logging.getLogger(__name__)


class SignalManager(BaseDatabase):
    """Manages order book signals and trading signals."""
    
    def _create_tables(self, cursor):
        """Create signal-related tables."""
        # Order book signals table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_book_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id TEXT UNIQUE NOT NULL,
                session_id TEXT,
                symbol TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                strength REAL NOT NULL,
                price REAL NOT NULL,
                timestamp INTEGER NOT NULL,
                signal_data TEXT,
                processed BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES trading_sessions (session_id)
            )
        """)
    
    def save_order_book_signal(self, signal_data: Dict[str, Any]) -> bool:
        """Save order book signal."""
        try:
            query = """
                INSERT OR REPLACE INTO order_book_signals 
                (signal_id, session_id, symbol, signal_type, strength, price, 
                 timestamp, signal_data, processed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            return self._execute_update(query, (
                signal_data.get('signal_id'),
                signal_data.get('session_id'),
                signal_data.get('symbol'),
                signal_data.get('signal_type'),
                signal_data.get('strength', 0.0),
                signal_data.get('price', 0.0),
                signal_data.get('timestamp'),
                json.dumps(signal_data.get('signal_data', {})),
                signal_data.get('processed', False)
            ))
        except Exception as e:
            logger.error(f"Error saving order book signal: {e}")
            return False
    
    def get_order_book_signals_paginated(self, session_id: str = None, symbol: str = None, 
                                        limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """Get order book signals with pagination."""
        try:
            # Build query conditions
            conditions = []
            params = []
            
            if session_id:
                conditions.append("session_id = ?")
                params.append(session_id)
            
            if symbol:
                conditions.append("symbol = ?")
                params.append(symbol)
            
            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            
            # Get total count
            count_query = f"SELECT COUNT(*) FROM order_book_signals {where_clause}"
            count_results = self._execute_query(count_query, tuple(params))
            total_count = count_results[0][0] if count_results else 0
            
            # Get signals
            signals_query = f"""
                SELECT signal_id, session_id, symbol, signal_type, strength, price, 
                       timestamp, signal_data, processed, created_at
                FROM order_book_signals 
                {where_clause}
                ORDER BY timestamp DESC 
                LIMIT ? OFFSET ?
            """
            
            params.extend([limit, offset])
            results = self._execute_query(signals_query, tuple(params))
            
            signals = []
            for row in results:
                signals.append({
                    'signal_id': row[0],
                    'session_id': row[1],
                    'symbol': row[2],
                    'signal_type': row[3],
                    'strength': row[4],
                    'price': row[5],
                    'timestamp': row[6],
                    'signal_data': json.loads(row[7]) if row[7] else {},
                    'processed': bool(row[8]),
                    'created_at': row[9]
                })
            
            return {
                'signals': signals,
                'total_count': total_count,
                'limit': limit,
                'offset': offset,
                'has_more': (offset + limit) < total_count
            }
        except Exception as e:
            logger.error(f"Error getting order book signals: {e}")
            return {'signals': [], 'total_count': 0, 'limit': limit, 'offset': offset, 'has_more': False}
    
    def get_signals_by_symbol(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get signals for a specific symbol."""
        try:
            query = """
                SELECT signal_id, session_id, symbol, signal_type, strength, price, 
                       timestamp, signal_data, processed, created_at
                FROM order_book_signals 
                WHERE symbol = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            """
            
            results = self._execute_query(query, (symbol, limit))
            signals = []
            
            for row in results:
                signals.append({
                    'signal_id': row[0],
                    'session_id': row[1],
                    'symbol': row[2],
                    'signal_type': row[3],
                    'strength': row[4],
                    'price': row[5],
                    'timestamp': row[6],
                    'signal_data': json.loads(row[7]) if row[7] else {},
                    'processed': bool(row[8]),
                    'created_at': row[9]
                })
            
            return signals
        except Exception as e:
            logger.error(f"Error getting signals by symbol: {e}")
            return []
    
    def mark_signal_processed(self, signal_id: str) -> bool:
        """Mark a signal as processed."""
        try:
            query = """
                UPDATE order_book_signals 
                SET processed = 1 
                WHERE signal_id = ?
            """
            
            return self._execute_update(query, (signal_id,))
        except Exception as e:
            logger.error(f"Error marking signal as processed: {e}")
            return False
    
    def get_unprocessed_signals(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get unprocessed signals."""
        try:
            query = """
                SELECT signal_id, session_id, symbol, signal_type, strength, price, 
                       timestamp, signal_data, created_at
                FROM order_book_signals 
                WHERE processed = 0 
                ORDER BY timestamp ASC 
                LIMIT ?
            """
            
            results = self._execute_query(query, (limit,))
            signals = []
            
            for row in results:
                signals.append({
                    'signal_id': row[0],
                    'session_id': row[1],
                    'symbol': row[2],
                    'signal_type': row[3],
                    'strength': row[4],
                    'price': row[5],
                    'timestamp': row[6],
                    'signal_data': json.loads(row[7]) if row[7] else {},
                    'created_at': row[8]
                })
            
            return signals
        except Exception as e:
            logger.error(f"Error getting unprocessed signals: {e}")
            return []
    
    def get_signal_stats(self, session_id: str = None) -> Dict[str, Any]:
        """Get signal statistics."""
        try:
            stats = {}
            
            # Base query
            base_query = "SELECT COUNT(*), AVG(strength), MIN(strength), MAX(strength) FROM order_book_signals"
            params = []
            
            if session_id:
                base_query += " WHERE session_id = ?"
                params.append(session_id)
            
            # Get overall stats
            results = self._execute_query(base_query, tuple(params))
            if results:
                count, avg_strength, min_strength, max_strength = results[0]
                stats.update({
                    'total_signals': count or 0,
                    'average_strength': avg_strength or 0.0,
                    'min_strength': min_strength or 0.0,
                    'max_strength': max_strength or 0.0
                })
            
            # Get processed/unprocessed counts
            processed_query = base_query.replace("COUNT(*), AVG(strength), MIN(strength), MAX(strength)", 
                                               "COUNT(*)")
            processed_query += " AND processed = 1" if session_id else " WHERE processed = 1"
            
            results = self._execute_query(processed_query, tuple(params))
            if results:
                stats['processed_signals'] = results[0][0] or 0
            
            unprocessed_query = base_query.replace("COUNT(*), AVG(strength), MIN(strength), MAX(strength)", 
                                                 "COUNT(*)")
            unprocessed_query += " AND processed = 0" if session_id else " WHERE processed = 0"
            
            results = self._execute_query(unprocessed_query, tuple(params))
            if results:
                stats['unprocessed_signals'] = results[0][0] or 0
            
            return stats
        except Exception as e:
            logger.error(f"Error getting signal stats: {e}")
            return {}
