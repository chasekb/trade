"""Trade manager for individual trade records."""

import psycopg
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
import logging

from .base_database import BaseDatabase

logger = logging.getLogger(__name__)


class TradeManager(BaseDatabase):
    """Manages individual trade records."""
    
    def _create_tables(self, cursor):
        """Create trade-related tables."""
        # Individual trades table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS individual_trades (
                id SERIAL PRIMARY KEY,
                trade_id VARCHAR(255) UNIQUE NOT NULL,
                session_id VARCHAR(255) NOT NULL,
                symbol VARCHAR(255) NOT NULL,
                side VARCHAR(10) NOT NULL,
                size REAL,
                price REAL NOT NULL,
                timestamp BIGINT NOT NULL,
                strategy_type VARCHAR(50),
                signal_reason TEXT,
                pnl REAL,
                fees REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                win_probability REAL,
                expected_return REAL,
                model_confidence REAL,
                FOREIGN KEY (session_id) REFERENCES trading_sessions (session_id)
            )
        """)
        
        # Add columns if they don't exist (migration for existing tables)
        try:
            cursor.execute("ALTER TABLE individual_trades ADD COLUMN IF NOT EXISTS win_probability REAL")
            cursor.execute("ALTER TABLE individual_trades ADD COLUMN IF NOT EXISTS expected_return REAL")
            cursor.execute("ALTER TABLE individual_trades ADD COLUMN IF NOT EXISTS model_confidence REAL")
        except Exception as e:
            logger.warning(f"Migration warning for individual_trades: {e}")
    
    def save_trade(self, trade_data: Dict[str, Any]) -> bool:
        """Save individual trade record."""
        try:
            query = """
                INSERT INTO individual_trades
                (trade_id, session_id, symbol, side, size, price, timestamp,
                 strategy_type, signal_reason, pnl, fees, win_probability, expected_return, model_confidence)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (trade_id)
                DO UPDATE SET session_id = EXCLUDED.session_id,
                              symbol = EXCLUDED.symbol,
                              side = EXCLUDED.side,
                              size = EXCLUDED.size,
                              price = EXCLUDED.price,
                              timestamp = EXCLUDED.timestamp,
                              strategy_type = EXCLUDED.strategy_type,
                              signal_reason = EXCLUDED.signal_reason,
                              pnl = EXCLUDED.pnl,
                              fees = EXCLUDED.fees,
                              win_probability = EXCLUDED.win_probability,
                              expected_return = EXCLUDED.expected_return,
                              model_confidence = EXCLUDED.model_confidence
            """

            params = (
                trade_data.get('trade_id'),
                trade_data.get('session_id'),
                trade_data.get('symbol'),
                trade_data.get('side'),
                float(trade_data.get('size', trade_data.get('quantity', 0.0)) or 0.0),
                float(trade_data.get('price', 0.0) or 0.0),
                trade_data.get('timestamp'),
                trade_data.get('strategy_type'),
                trade_data.get('signal_reason'),
                float(trade_data.get('pnl', 0.0) or 0.0),
                float(trade_data.get('fees', 0.0) or 0.0),
                trade_data.get('win_probability'),
                trade_data.get('expected_return'),
                trade_data.get('model_confidence')
            )

            return self._execute_update(query, params)
        except Exception as e:
            logger.error(f"Error saving trade: {e}")
            return False
    
    def get_trades_by_session(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get trades for a specific session."""
        try:
            query = """
                SELECT trade_id, symbol, side, size, price, timestamp,
                       strategy_type, signal_reason, pnl, fees, created_at,
                       win_probability, expected_return, model_confidence
                FROM individual_trades
                WHERE session_id = %s
                ORDER BY timestamp DESC
                LIMIT %s
            """

            results = self._execute_query(query, (session_id, limit))
            trades = []

            for row in results:
                trades.append({
                    'trade_id': row[0],
                    'symbol': row[1],
                    'side': row[2],
                    'size': row[3],
                    'price': row[4],
                    'timestamp': row[5],
                    'strategy_type': row[6],
                    'signal_reason': row[7],
                    'pnl': row[8],
                    'fees': row[9],
                    'created_at': row[10],
                    'win_probability': row[11],
                    'expected_return': row[12],
                    'model_confidence': row[13]
                })

            return trades
        except Exception as e:
            logger.error(f"Error getting trades by session: {e}")
            return []

    def get_trades_by_symbol(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get trades for a specific symbol."""
        try:
            query = """
                SELECT trade_id, session_id, symbol, side, size, price, timestamp,
                       strategy_type, signal_reason, pnl, fees, created_at,
                       win_probability, expected_return, model_confidence
                FROM individual_trades
                WHERE symbol = %s
                ORDER BY timestamp DESC
                LIMIT %s
            """

            results = self._execute_query(query, (symbol, limit))
            trades = []

            for row in results:
                trades.append({
                    'trade_id': row[0],
                    'session_id': row[1],
                    'symbol': row[2],
                    'side': row[3],
                    'size': row[4],
                    'price': row[5],
                    'timestamp': row[6],
                    'strategy_type': row[7],
                    'signal_reason': row[8],
                    'pnl': row[9],
                    'fees': row[10],
                    'created_at': row[11],
                    'win_probability': row[12],
                    'expected_return': row[13],
                    'model_confidence': row[14]
                })

            return trades
        except Exception as e:
            logger.error(f"Error getting trades by symbol: {e}")
            return []

    def get_recent_trades(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get most recent trades across all sessions."""
        try:
            query = """
                SELECT trade_id, session_id, symbol, side, size, price, timestamp,
                       strategy_type, signal_reason, pnl, fees, created_at,
                       win_probability, expected_return, model_confidence
                FROM individual_trades
                ORDER BY timestamp DESC
                LIMIT %s
            """

            results = self._execute_query(query, (limit,))
            trades = []

            for row in results:
                trades.append({
                    'trade_id': row[0],
                    'session_id': row[1],
                    'symbol': row[2],
                    'side': row[3],
                    'size': row[4],
                    'price': row[5],
                    'timestamp': row[6],
                    'strategy_type': row[7],
                    'signal_reason': row[8],
                    'pnl': row[9],
                    'fees': row[10],
                    'created_at': row[11],
                    'win_probability': row[12],
                    'expected_return': row[13],
                    'model_confidence': row[14]
                })

            return trades
        except Exception as e:
            logger.error(f"Error getting recent trades: {e}")
            return []

    def get_all_trades(self, limit: int = 1000, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all trades across all sessions with pagination."""
        try:
            query = """
                SELECT trade_id, session_id, symbol, side, size, price, timestamp,
                       strategy_type, signal_reason, pnl, fees, created_at,
                       win_probability, expected_return, model_confidence
                FROM individual_trades
                ORDER BY timestamp DESC
                LIMIT %s OFFSET %s
            """
            results = self._execute_query(query, (limit, offset))
            trades: List[Dict[str, Any]] = []
            for row in results:
                trades.append({
                    'trade_id': row[0],
                    'session_id': row[1],
                    'symbol': row[2],
                    'side': row[3],
                    'size': row[4],
                    'price': row[5],
                    'timestamp': row[6],
                    'strategy_type': row[7],
                    'signal_reason': row[8],
                    'pnl': row[9],
                    'fees': row[10],
                    'created_at': row[11],
                    'win_probability': row[12],
                    'expected_return': row[13],
                    'model_confidence': row[14]
                })
            return trades
        except Exception as e:
            logger.error(f"Error getting all trades: {e}")
            return []

    def get_trades_count(self) -> int:
        """Get total number of trades across all sessions."""
        try:
            query = "SELECT COUNT(*) FROM individual_trades"
            results = self._execute_query(query)
            if results:
                return int(results[0][0] or 0)
            return 0
        except Exception as e:
            logger.error(f"Error getting trades count: {e}")
            return 0

    def get_trade_stats(self, session_id: str = None) -> Dict[str, Any]:
        """Get trade statistics."""
        try:
            stats = {}

            # Base query
            base_query = "SELECT COUNT(*), SUM(pnl), SUM(fees), AVG(pnl) FROM individual_trades"
            params = []

            if session_id:
                base_query += " WHERE session_id = %s"
                params.append(session_id)

            # Get overall stats
            results = self._execute_query(base_query, tuple(params))
            if results:
                count, total_pnl, total_fees, avg_pnl = results[0]
                stats.update({
                    'total_trades': count or 0,
                    'total_pnl': total_pnl or 0.0,
                    'total_fees': total_fees or 0.0,
                    'average_pnl': avg_pnl or 0.0
                })

            # Get winning/losing trades
            win_query = base_query.replace("COUNT(*), SUM(pnl), SUM(fees), AVG(pnl)",
                                         "COUNT(*)")
            win_query += " AND pnl > 0" if session_id else " WHERE pnl > 0"

            results = self._execute_query(win_query, tuple(params))
            if results:
                stats['winning_trades'] = results[0][0] or 0

            lose_query = base_query.replace("COUNT(*), SUM(pnl), SUM(fees), AVG(pnl)",
                                          "COUNT(*)")
            lose_query += " AND pnl < 0" if session_id else " WHERE pnl < 0"

            results = self._execute_query(lose_query, tuple(params))
            if results:
                stats['losing_trades'] = results[0][0] or 0

            # Calculate win rate
            total_trades = stats.get('total_trades', 0)
            if total_trades > 0:
                stats['win_rate'] = (stats.get('winning_trades', 0) / total_trades) * 100
            else:
                stats['win_rate'] = 0.0

            return stats
        except Exception as e:
            logger.error(f"Error getting trade stats: {e}")
            return {}
