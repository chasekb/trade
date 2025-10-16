"""Trade manager for individual trade records."""

import sqlite3
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
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT UNIQUE NOT NULL,
                session_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                size REAL,
                price REAL NOT NULL,
                timestamp INTEGER NOT NULL,
                strategy_type TEXT,
                signal_reason TEXT,
                pnl REAL,
                fees REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES trading_sessions (session_id)
            )
        """)
        # Migration: ensure 'size' column exists; backfill from legacy 'quantity' when present
        try:
            cursor.execute("PRAGMA table_info(individual_trades)")
            columns = [row[1] for row in cursor.fetchall()]
            # Add missing columns used by queries
            if 'size' not in columns:
                cursor.execute("ALTER TABLE individual_trades ADD COLUMN size REAL")
            if 'signal_reason' not in columns:
                cursor.execute("ALTER TABLE individual_trades ADD COLUMN signal_reason TEXT")
            if 'strategy_type' not in columns:
                cursor.execute("ALTER TABLE individual_trades ADD COLUMN strategy_type TEXT")
            if 'pnl' not in columns:
                cursor.execute("ALTER TABLE individual_trades ADD COLUMN pnl REAL")
            if 'fees' not in columns:
                cursor.execute("ALTER TABLE individual_trades ADD COLUMN fees REAL")
            if 'created_at' not in columns:
                cursor.execute("ALTER TABLE individual_trades ADD COLUMN created_at TIMESTAMP")
            # Backfill size from quantity if legacy column exists and size is NULL
            cursor.execute("PRAGMA table_info(individual_trades)")
            columns2 = [row[1] for row in cursor.fetchall()]
            if 'quantity' in columns2:
                cursor.execute("UPDATE individual_trades SET size = COALESCE(size, quantity)")
        except Exception as e:
            logger.warning(f"TradeManager migration check failed: {e}")
    
    def save_trade(self, trade_data: Dict[str, Any]) -> bool:
        """Save individual trade record."""
        try:
            query = """
                INSERT OR REPLACE INTO individual_trades 
                (trade_id, session_id, symbol, side, size, price, timestamp, 
                 strategy_type, signal_reason, pnl, fees)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            return self._execute_update(query, (
                trade_data.get('trade_id'),
                trade_data.get('session_id'),
                trade_data.get('symbol'),
                trade_data.get('side'),
                trade_data.get('size', 0.0),
                trade_data.get('price', 0.0),
                trade_data.get('timestamp'),
                trade_data.get('strategy_type'),
                trade_data.get('signal_reason'),
                trade_data.get('pnl', 0.0),
                trade_data.get('fees', 0.0)
            ))
        except Exception as e:
            logger.error(f"Error saving trade: {e}")
            return False
    
    def get_trades_by_session(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get trades for a specific session."""
        try:
            query = """
                SELECT trade_id, symbol, side, size, price, timestamp, 
                       strategy_type, signal_reason, pnl, fees, created_at
                FROM individual_trades 
                WHERE session_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
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
                    'created_at': row[10]
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
                       strategy_type, signal_reason, pnl, fees, created_at
                FROM individual_trades 
                WHERE symbol = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
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
                    'created_at': row[11]
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
                       strategy_type, signal_reason, pnl, fees, created_at
                FROM individual_trades 
                ORDER BY timestamp DESC 
                LIMIT ?
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
                    'created_at': row[11]
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
                       strategy_type, signal_reason, pnl, fees, created_at
                FROM individual_trades
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
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
                    'created_at': row[11]
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
                base_query += " WHERE session_id = ?"
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
