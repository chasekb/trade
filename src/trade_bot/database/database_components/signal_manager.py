"""Signal manager for order book signals."""

import psycopg
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
                id SERIAL PRIMARY KEY,
                signal_id VARCHAR(255) UNIQUE NOT NULL,
                session_id VARCHAR(255),
                symbol VARCHAR(255) NOT NULL,
                signal_type VARCHAR(50) NOT NULL,
                strength REAL NOT NULL,
                price REAL NOT NULL,
                timestamp BIGINT NOT NULL,
                signal_data TEXT,
                processed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                win_probability REAL,
                expected_return REAL,
                FOREIGN KEY (session_id) REFERENCES trading_sessions (session_id)
            )
        """)
        
        # Add columns if they don't exist (migration for existing tables)
        try:
            cursor.execute("ALTER TABLE order_book_signals ADD COLUMN IF NOT EXISTS win_probability REAL")
            cursor.execute("ALTER TABLE order_book_signals ADD COLUMN IF NOT EXISTS expected_return REAL")
        except Exception as e:
            logger.warning(f"Migration warning for order_book_signals: {e}")
    
    def save_order_book_signal(self, signal_data: Dict[str, Any]) -> bool:
        """Save order book signal."""
        try:
            query = """
                INSERT INTO order_book_signals
                (signal_id, session_id, symbol, signal_type, strength, price,
                 timestamp, signal_data, processed, win_probability, expected_return)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (signal_id)
                DO UPDATE SET session_id = EXCLUDED.session_id,
                              symbol = EXCLUDED.symbol,
                              signal_type = EXCLUDED.signal_type,
                              strength = EXCLUDED.strength,
                              price = EXCLUDED.price,
                              timestamp = EXCLUDED.timestamp,
                              signal_data = EXCLUDED.signal_data,
                              processed = EXCLUDED.processed,
                              win_probability = EXCLUDED.win_probability,
                              expected_return = EXCLUDED.expected_return
            """

            # Extract ML metrics from signal_data if available
            ml_analysis = signal_data.get('signal_data', {}).get('ml_analysis', {})
            win_prob = signal_data.get('win_probability')
            if win_prob is None and ml_analysis:
                win_prob = ml_analysis.get('win_probability')
                
            exp_return = signal_data.get('expected_return')
            if exp_return is None and ml_analysis:
                exp_return = ml_analysis.get('expected_return')

            return self._execute_update(query, (
                signal_data.get('signal_id'),
                signal_data.get('session_id'),
                signal_data.get('symbol'),
                signal_data.get('signal_type'),
                signal_data.get('strength', 0.0),
                signal_data.get('price', 0.0),
                signal_data.get('timestamp'),
                json.dumps(signal_data.get('signal_data', {})),
                signal_data.get('processed', False),
                win_prob,
                exp_return
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
                conditions.append("session_id = %s")
                params.append(session_id)

            if symbol:
                conditions.append("symbol = %s")
                params.append(symbol)

            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

            # Get total count - use parameterized query
            count_query = "SELECT COUNT(*) FROM order_book_signals " + where_clause
            count_results = self._execute_query(count_query, tuple(params))
            total_count = count_results[0][0] if count_results else 0

            # Get signals - use parameterized query
            signals_query = """
                SELECT signal_id, session_id, symbol, signal_type, strength, price,
                       timestamp, signal_data, processed, created_at, win_probability, expected_return
                FROM order_book_signals
                """ + where_clause + """
                ORDER BY timestamp DESC
                LIMIT %s OFFSET %s
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
                    'created_at': row[9],
                    'win_probability': row[10],
                    'expected_return': row[11]
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
                       timestamp, signal_data, processed, created_at, win_probability, expected_return
                FROM order_book_signals
                WHERE symbol = %s
                ORDER BY timestamp DESC
                LIMIT %s
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
                    'created_at': row[9],
                    'win_probability': row[10],
                    'expected_return': row[11]
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
                SET processed = TRUE
                WHERE signal_id = %s
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
                WHERE processed = FALSE
                ORDER BY timestamp ASC
                LIMIT %s
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
                base_query += " WHERE session_id = %s"
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
            processed_query += " AND processed = TRUE" if session_id else " WHERE processed = TRUE"

            results = self._execute_query(processed_query, tuple(params))
            if results:
                stats['processed_signals'] = results[0][0] or 0

            unprocessed_query = base_query.replace("COUNT(*), AVG(strength), MIN(strength), MAX(strength)",
                                                 "COUNT(*)")
            unprocessed_query += " AND processed = FALSE" if session_id else " WHERE processed = FALSE"

            results = self._execute_query(unprocessed_query, tuple(params))
            if results:
                stats['unprocessed_signals'] = results[0][0] or 0

            return stats
        except Exception as e:
            logger.error(f"Error getting signal stats: {e}")
            return {}
