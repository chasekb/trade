"""
Database module for persistent storage of backtest results.
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class BacktestDatabase:
    """Database manager for backtest results storage."""
    
    def __init__(self, db_path: str = "backtests.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create backtests table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS backtests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        strategy_type TEXT NOT NULL,
                        strategy_params TEXT NOT NULL,
                        backtest_params TEXT NOT NULL,
                        results TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes for better performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_backtests_timestamp 
                    ON backtests(timestamp)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_backtests_symbol 
                    ON backtests(symbol)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_backtests_strategy 
                    ON backtests(strategy_type)
                """)
                
                conn.commit()
                logger.info("Database initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def save_backtest(self, 
                     symbol: str,
                     strategy_type: str,
                     strategy_params: Dict[str, Any],
                     backtest_params: Dict[str, Any],
                     results: Dict[str, Any]) -> int:
        """Save a backtest result to the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Generate timestamp for this backtest
                timestamp = datetime.now().isoformat()
                
                cursor.execute("""
                    INSERT INTO backtests 
                    (timestamp, symbol, strategy_type, strategy_params, backtest_params, results)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    timestamp,
                    symbol,
                    strategy_type,
                    json.dumps(strategy_params),
                    json.dumps(backtest_params),
                    json.dumps(results)
                ))
                
                backtest_id = cursor.lastrowid
                conn.commit()
                
                logger.info(f"Saved backtest {backtest_id} for {symbol} with {strategy_type} strategy")
                return backtest_id
                
        except Exception as e:
            logger.error(f"Failed to save backtest: {e}")
            raise
    
    def get_backtest(self, backtest_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a specific backtest by ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, timestamp, symbol, strategy_type, strategy_params, 
                           backtest_params, results, created_at
                    FROM backtests 
                    WHERE id = ?
                """, (backtest_id,))
                
                row = cursor.fetchone()
                if row:
                    return {
                        'id': row[0],
                        'timestamp': row[1],
                        'symbol': row[2],
                        'strategy_type': row[3],
                        'strategy_params': json.loads(row[4]),
                        'backtest_params': json.loads(row[5]),
                        'results': json.loads(row[6]),
                        'created_at': row[7]
                    }
                return None
                
        except Exception as e:
            logger.error(f"Failed to retrieve backtest {backtest_id}: {e}")
            return None
    
    def get_backtest_history(self, 
                           limit: int = 50,
                           offset: int = 0,
                           symbol: Optional[str] = None,
                           strategy_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve backtest history with optional filtering."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Build query with optional filters
                query = """
                    SELECT id, timestamp, symbol, strategy_type, strategy_params, 
                           backtest_params, results, created_at
                    FROM backtests
                """
                params = []
                conditions = []
                
                if symbol:
                    conditions.append("symbol = ?")
                    params.append(symbol)
                
                if strategy_type:
                    conditions.append("strategy_type = ?")
                    params.append(strategy_type)
                
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
                
                query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                backtests = []
                for row in rows:
                    backtests.append({
                        'id': row[0],
                        'timestamp': row[1],
                        'symbol': row[2],
                        'strategy_type': row[3],
                        'strategy_params': json.loads(row[4]),
                        'backtest_params': json.loads(row[5]),
                        'results': json.loads(row[6]),
                        'created_at': row[7]
                    })
                
                return backtests
                
        except Exception as e:
            logger.error(f"Failed to retrieve backtest history: {e}")
            return []
    
    def get_backtest_stats(self) -> Dict[str, Any]:
        """Get statistics about stored backtests."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Total backtests
                cursor.execute("SELECT COUNT(*) FROM backtests")
                total_backtests = cursor.fetchone()[0]
                
                # Backtests by strategy
                cursor.execute("""
                    SELECT strategy_type, COUNT(*) 
                    FROM backtests 
                    GROUP BY strategy_type
                """)
                strategy_counts = dict(cursor.fetchall())
                
                # Backtests by symbol
                cursor.execute("""
                    SELECT symbol, COUNT(*) 
                    FROM backtests 
                    GROUP BY symbol
                """)
                symbol_counts = dict(cursor.fetchall())
                
                # Recent backtests (last 7 days)
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM backtests 
                    WHERE created_at >= datetime('now', '-7 days')
                """)
                recent_backtests = cursor.fetchone()[0]
                
                return {
                    'total_backtests': total_backtests,
                    'strategy_counts': strategy_counts,
                    'symbol_counts': symbol_counts,
                    'recent_backtests': recent_backtests
                }
                
        except Exception as e:
            logger.error(f"Failed to get backtest stats: {e}")
            return {
                'total_backtests': 0,
                'strategy_counts': {},
                'symbol_counts': {},
                'recent_backtests': 0
            }
    
    def delete_backtest(self, backtest_id: int) -> bool:
        """Delete a backtest by ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("DELETE FROM backtests WHERE id = ?", (backtest_id,))
                deleted = cursor.rowcount > 0
                conn.commit()
                
                if deleted:
                    logger.info(f"Deleted backtest {backtest_id}")
                else:
                    logger.warning(f"Backtest {backtest_id} not found")
                
                return deleted
                
        except Exception as e:
            logger.error(f"Failed to delete backtest {backtest_id}: {e}")
            return False
    
    def clear_old_backtests(self, days: int = 30) -> int:
        """Clear backtests older than specified days."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    DELETE FROM backtests 
                    WHERE created_at < datetime('now', '-{} days')
                """.format(days))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                logger.info(f"Cleared {deleted_count} backtests older than {days} days")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Failed to clear old backtests: {e}")
            return 0
