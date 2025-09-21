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
            
            # Trading session state table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trading_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    trading_mode TEXT NOT NULL,
                    symbol_mode TEXT NOT NULL,
                    strategy_type TEXT,
                    strategy_params TEXT,
                    symbols TEXT,
                    universe_config TEXT,
                    portfolio_state TEXT,
                    positions TEXT,
                    recent_trades TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Dashboard UI state table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dashboard_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    current_symbol TEXT,
                    current_timeframe TEXT,
                    chart_settings TEXT,
                    ui_preferences TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES trading_sessions (session_id)
                )
            """)
            
            # Individual trades table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS individual_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT UNIQUE NOT NULL,
                    session_id TEXT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    price REAL NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    reason TEXT,
                    pnl REAL DEFAULT 0.0,
                    fees REAL DEFAULT 0.0,
                    strategy_type TEXT,
                    strategy_params TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES trading_sessions (session_id)
                )
            """)
            
            # Order book signals table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS order_book_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_id TEXT UNIQUE NOT NULL,
                    session_id TEXT,
                    symbol TEXT NOT NULL,
                    price REAL NOT NULL,
                    signal TEXT NOT NULL,
                    signal_strength REAL NOT NULL,
                    signal_generated BOOLEAN NOT NULL,
                    signal_type TEXT,
                    signal_reason TEXT,
                    spread REAL,
                    imbalance REAL,
                    mid_price REAL,
                    best_bid REAL,
                    best_ask REAL,
                    order_book_depth INTEGER,
                    spread_trend TEXT,
                    imbalance_trend TEXT,
                    volume REAL,
                    total_signals INTEGER,
                    signal_rate REAL,
                    data_status TEXT,
                    timestamp TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES trading_sessions (session_id)
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
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_active ON trading_sessions(is_active)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_updated ON trading_sessions(updated_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_dashboard_session ON dashboard_state(session_id)")
            # Migration: Add strategy fields to existing individual_trades table
            try:
                cursor.execute("ALTER TABLE individual_trades ADD COLUMN strategy_type TEXT")
                logger.info("Added strategy_type column to individual_trades table")
            except sqlite3.OperationalError:
                # Column already exists
                pass
            
            try:
                cursor.execute("ALTER TABLE individual_trades ADD COLUMN strategy_params TEXT")
                logger.info("Added strategy_params column to individual_trades table")
            except sqlite3.OperationalError:
                # Column already exists
                pass
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_session ON individual_trades(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON individual_trades(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON individual_trades(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_strategy ON individual_trades(strategy_type)")
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_session ON order_book_signals(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_symbol ON order_book_signals(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON order_book_signals(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_signal ON order_book_signals(signal)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_generated ON order_book_signals(signal_generated)")
            
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
    
    # Session State Management Methods
    
    def save_trading_session(self, session_id: str, session_data: Dict[str, Any]) -> bool:
        """Save trading session state."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO trading_sessions 
                    (session_id, is_active, trading_mode, symbol_mode, strategy_type, 
                     strategy_params, symbols, universe_config, portfolio_state, 
                     positions, recent_trades, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    session_id,
                    session_data.get('is_active', False),
                    session_data.get('trading_mode', 'simulated'),
                    session_data.get('symbol_mode', 'single'),
                    session_data.get('strategy_type'),
                    json.dumps(session_data.get('strategy_params', {})),
                    json.dumps(session_data.get('symbols', [])),
                    json.dumps(session_data.get('universe_config', {})),
                    json.dumps(session_data.get('portfolio_state', {})),
                    json.dumps(session_data.get('positions', [])),
                    json.dumps(session_data.get('recent_trades', []))
                ))
                conn.commit()
            
            logger.debug(f"Saved trading session: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save trading session: {e}")
            return False
    
    def load_trading_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load trading session state."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT is_active, trading_mode, symbol_mode, strategy_type,
                           strategy_params, symbols, universe_config, portfolio_state,
                           positions, recent_trades, created_at, updated_at
                    FROM trading_sessions 
                    WHERE session_id = ?
                """, (session_id,))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                return {
                    'is_active': bool(row[0]),
                    'trading_mode': row[1],
                    'symbol_mode': row[2],
                    'strategy_type': row[3],
                    'strategy_params': json.loads(row[4]) if row[4] else {},
                    'symbols': json.loads(row[5]) if row[5] else [],
                    'universe_config': json.loads(row[6]) if row[6] else {},
                    'portfolio_state': json.loads(row[7]) if row[7] else {},
                    'positions': json.loads(row[8]) if row[8] else [],
                    'recent_trades': json.loads(row[9]) if row[9] else [],
                    'created_at': row[10],
                    'updated_at': row[11]
                }
                
        except Exception as e:
            logger.error(f"Failed to load trading session: {e}")
            return None
    
    def save_dashboard_state(self, session_id: str, state_data: Dict[str, Any]) -> bool:
        """Save dashboard UI state."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO dashboard_state 
                    (session_id, current_symbol, current_timeframe, chart_settings, 
                     ui_preferences, last_updated)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    session_id,
                    state_data.get('current_symbol'),
                    state_data.get('current_timeframe'),
                    json.dumps(state_data.get('chart_settings', {})),
                    json.dumps(state_data.get('ui_preferences', {}))
                ))
                conn.commit()
            
            logger.debug(f"Saved dashboard state: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save dashboard state: {e}")
            return False
    
    def load_dashboard_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load dashboard UI state."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT current_symbol, current_timeframe, chart_settings, 
                           ui_preferences, last_updated
                    FROM dashboard_state 
                    WHERE session_id = ?
                """, (session_id,))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                return {
                    'current_symbol': row[0],
                    'current_timeframe': row[1],
                    'chart_settings': json.loads(row[2]) if row[2] else {},
                    'ui_preferences': json.loads(row[3]) if row[3] else {},
                    'last_updated': row[4]
                }
                
        except Exception as e:
            logger.error(f"Failed to load dashboard state: {e}")
            return None
    
    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get all active trading sessions."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT session_id, trading_mode, symbol_mode, strategy_type,
                           updated_at, created_at
                    FROM trading_sessions 
                    WHERE is_active = 1
                    ORDER BY updated_at DESC
                """)
                
                sessions = []
                for row in cursor.fetchall():
                    sessions.append({
                        'session_id': row[0],
                        'trading_mode': row[1],
                        'symbol_mode': row[2],
                        'strategy_type': row[3],
                        'updated_at': row[4],
                        'created_at': row[5]
                    })
                
                return sessions
                
        except Exception as e:
            logger.error(f"Failed to get active sessions: {e}")
            return []
    
    def deactivate_session(self, session_id: str) -> bool:
        """Deactivate a trading session."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE trading_sessions 
                    SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                    WHERE session_id = ?
                """, (session_id,))
                conn.commit()
            
            logger.debug(f"Deactivated session: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to deactivate session: {e}")
            return False
    
    # Individual Trade Management Methods
    
    def save_trade(self, trade_data: Dict[str, Any]) -> bool:
        """Save an individual trade to the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Convert strategy_params to JSON string if it's a dict
                strategy_params = trade_data.get('strategy_params', {})
                if isinstance(strategy_params, dict):
                    strategy_params = json.dumps(strategy_params)
                
                cursor.execute("""
                    INSERT OR REPLACE INTO individual_trades 
                    (trade_id, session_id, symbol, side, quantity, price, 
                     timestamp, reason, pnl, fees, strategy_type, strategy_params)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade_data.get('trade_id'),
                    trade_data.get('session_id'),
                    trade_data.get('symbol'),
                    trade_data.get('side'),
                    trade_data.get('quantity'),
                    trade_data.get('price'),
                    trade_data.get('timestamp'),
                    trade_data.get('reason'),
                    trade_data.get('pnl', 0.0),
                    trade_data.get('fees', 0.0),
                    trade_data.get('strategy_type'),
                    strategy_params
                ))
                conn.commit()
            
            logger.debug(f"Saved trade: {trade_data.get('trade_id')} with strategy: {trade_data.get('strategy_type')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save trade: {e}")
            return False
    
    def get_trades_by_session(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get trades for a specific session."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT trade_id, symbol, side, quantity, price, timestamp, 
                           reason, pnl, fees, strategy_type, strategy_params, created_at
                    FROM individual_trades 
                    WHERE session_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (session_id, limit))
                
                trades = []
                for row in cursor.fetchall():
                    # Parse strategy_params JSON if it exists
                    strategy_params = row[10]
                    if strategy_params:
                        try:
                            strategy_params = json.loads(strategy_params)
                        except (json.JSONDecodeError, TypeError):
                            strategy_params = {}
                    else:
                        strategy_params = {}
                    
                    trades.append({
                        'trade_id': row[0],
                        'symbol': row[1],
                        'side': row[2],
                        'quantity': row[3],
                        'price': row[4],
                        'timestamp': row[5],
                        'reason': row[6],
                        'pnl': row[7],
                        'fees': row[8],
                        'strategy_type': row[9],
                        'strategy_params': strategy_params,
                        'created_at': row[11]
                    })
                
                return trades
                
        except Exception as e:
            logger.error(f"Failed to get trades by session: {e}")
            return []
    
    def get_trades_by_symbol(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get trades for a specific symbol."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT trade_id, session_id, symbol, side, quantity, price, 
                           timestamp, reason, pnl, fees, strategy_type, strategy_params, created_at
                    FROM individual_trades 
                    WHERE symbol = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (symbol, limit))
                
                trades = []
                for row in cursor.fetchall():
                    # Parse strategy_params JSON if it exists
                    strategy_params = row[11]
                    if strategy_params:
                        try:
                            strategy_params = json.loads(strategy_params)
                        except (json.JSONDecodeError, TypeError):
                            strategy_params = {}
                    else:
                        strategy_params = {}
                    
                    trades.append({
                        'trade_id': row[0],
                        'session_id': row[1],
                        'symbol': row[2],
                        'side': row[3],
                        'quantity': row[4],
                        'price': row[5],
                        'timestamp': row[6],
                        'reason': row[7],
                        'pnl': row[8],
                        'fees': row[9],
                        'strategy_type': row[10],
                        'strategy_params': strategy_params,
                        'created_at': row[12]
                    })
                
                return trades
                
        except Exception as e:
            logger.error(f"Failed to get trades by symbol: {e}")
            return []
    
    def get_recent_trades(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent trades across all sessions."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT trade_id, session_id, symbol, side, quantity, price, 
                           timestamp, reason, pnl, fees, strategy_type, strategy_params, created_at
                    FROM individual_trades 
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))
                
                trades = []
                for row in cursor.fetchall():
                    # Parse strategy_params JSON if it exists
                    strategy_params = row[11]
                    if strategy_params:
                        try:
                            strategy_params = json.loads(strategy_params)
                        except (json.JSONDecodeError, TypeError):
                            strategy_params = {}
                    else:
                        strategy_params = {}
                    
                    trades.append({
                        'trade_id': row[0],
                        'session_id': row[1],
                        'symbol': row[2],
                        'side': row[3],
                        'quantity': row[4],
                        'price': row[5],
                        'timestamp': row[6],
                        'reason': row[7],
                        'pnl': row[8],
                        'fees': row[9],
                        'strategy_type': row[10],
                        'strategy_params': strategy_params,
                        'created_at': row[12]
                    })
                
                return trades
                
        except Exception as e:
            logger.error(f"Failed to get recent trades: {e}")
            return []
    
    # Order Book Signals Management Methods
    
    def save_order_book_signal(self, signal_data: Dict[str, Any]) -> bool:
        """Save an order book signal to the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO order_book_signals 
                    (signal_id, session_id, symbol, price, signal, signal_strength, 
                     signal_generated, signal_type, signal_reason, spread, imbalance, 
                     mid_price, best_bid, best_ask, order_book_depth, spread_trend, 
                     imbalance_trend, volume, total_signals, signal_rate, data_status, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    signal_data.get('signal_id'),
                    signal_data.get('session_id'),
                    signal_data.get('symbol'),
                    signal_data.get('price'),
                    signal_data.get('signal'),
                    signal_data.get('signal_strength'),
                    signal_data.get('signal_generated'),
                    signal_data.get('signal_type'),
                    signal_data.get('signal_reason'),
                    signal_data.get('spread'),
                    signal_data.get('imbalance'),
                    signal_data.get('mid_price'),
                    signal_data.get('best_bid'),
                    signal_data.get('best_ask'),
                    signal_data.get('order_book_depth'),
                    signal_data.get('spread_trend'),
                    signal_data.get('imbalance_trend'),
                    signal_data.get('volume'),
                    signal_data.get('total_signals'),
                    signal_data.get('signal_rate'),
                    signal_data.get('data_status'),
                    signal_data.get('timestamp')
                ))
                conn.commit()
            
            logger.debug(f"Saved order book signal: {signal_data.get('signal_id')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save order book signal: {e}")
            return False
    
    def get_order_book_signals_paginated(self, session_id: str = None, symbol: str = None, 
                                       page: int = 1, per_page: int = 10) -> Dict[str, Any]:
        """Get paginated order book signals."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Build WHERE clause
                where_conditions = []
                params = []
                
                if session_id:
                    where_conditions.append("session_id = ?")
                    params.append(session_id)
                
                if symbol:
                    where_conditions.append("symbol = ?")
                    params.append(symbol)
                
                where_clause = " WHERE " + " AND ".join(where_conditions) if where_conditions else ""
                
                # Get total count
                count_query = f"SELECT COUNT(*) FROM order_book_signals{where_clause}"
                cursor.execute(count_query, params)
                total_signals = cursor.fetchone()[0]
                
                # Calculate pagination
                total_pages = (total_signals + per_page - 1) // per_page
                offset = (page - 1) * per_page
                
                # Get paginated results
                query = f"""
                    SELECT signal_id, session_id, symbol, price, signal, signal_strength,
                           signal_generated, signal_type, signal_reason, spread, imbalance,
                           mid_price, best_bid, best_ask, order_book_depth, spread_trend,
                           imbalance_trend, volume, total_signals, signal_rate, data_status,
                           timestamp, created_at
                    FROM order_book_signals{where_clause}
                    ORDER BY timestamp DESC
                    LIMIT ? OFFSET ?
                """
                cursor.execute(query, params + [per_page, offset])
                
                signals = []
                for row in cursor.fetchall():
                    signals.append({
                        'signal_id': row[0],
                        'session_id': row[1],
                        'symbol': row[2],
                        'price': row[3],
                        'signal': row[4],
                        'signal_strength': row[5],
                        'signal_generated': bool(row[6]),
                        'signal_type': row[7],
                        'signal_reason': row[8],
                        'spread': row[9],
                        'imbalance': row[10],
                        'mid_price': row[11],
                        'best_bid': row[12],
                        'best_ask': row[13],
                        'order_book_depth': row[14],
                        'spread_trend': row[15],
                        'imbalance_trend': row[16],
                        'volume': row[17],
                        'total_signals': row[18],
                        'signal_rate': row[19],
                        'data_status': row[20],
                        'timestamp': row[21],
                        'created_at': row[22]
                    })
                
                return {
                    'signals': signals,
                    'pagination': {
                        'current_page': page,
                        'per_page': per_page,
                        'total_signals': total_signals,
                        'total_pages': total_pages,
                        'has_next': page < total_pages,
                        'has_prev': page > 1
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to get paginated order book signals: {e}")
            return {
                'signals': [],
                'pagination': {
                    'current_page': 1,
                    'per_page': per_page,
                    'total_signals': 0,
                    'total_pages': 0,
                    'has_next': False,
                    'has_prev': False
                }
            }
    
    def get_trade_stats(self, session_id: str = None) -> Dict[str, Any]:
        """Get comprehensive trading statistics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Base query
                base_query = "FROM individual_trades"
                params = []
                
                if session_id:
                    base_query += " WHERE session_id = ?"
                    params.append(session_id)
                
                # Total trades
                cursor.execute(f"SELECT COUNT(*) {base_query}", params)
                total_trades = cursor.fetchone()[0]
                
                if total_trades == 0:
                    return {
                        'total_trades': 0,
                        'winning_trades': 0,
                        'losing_trades': 0,
                        'win_rate': 0.0,
                        'total_pnl': 0.0,
                        'total_fees': 0.0,
                        'net_pnl': 0.0,
                        'max_drawdown': 0.0,
                        'sharpe_ratio': 0.0,
                        'best_trade': 0.0,
                        'worst_trade': 0.0,
                        'avg_win': 0.0,
                        'avg_loss': 0.0,
                        'trades_today': 0,
                        'total_volume': 0.0
                    }
                
                # Get all trades for detailed analysis
                cursor.execute(f"SELECT pnl, fees, price, quantity, timestamp {base_query} ORDER BY timestamp", params)
                trades = cursor.fetchall()
                
                # Basic stats
                winning_trades = sum(1 for trade in trades if trade[0] > 0)
                losing_trades = total_trades - winning_trades
                win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
                
                # PnL and fees
                total_pnl = sum(trade[0] for trade in trades)
                total_fees = sum(trade[1] for trade in trades)
                net_pnl = total_pnl - total_fees
                
                # Best and worst trades
                pnls = [trade[0] for trade in trades]
                best_trade = max(pnls) if pnls else 0.0
                worst_trade = min(pnls) if pnls else 0.0
                
                # Average win and loss
                winning_pnls = [pnl for pnl in pnls if pnl > 0]
                losing_pnls = [pnl for pnl in pnls if pnl < 0]
                avg_win = sum(winning_pnls) / len(winning_pnls) if winning_pnls else 0.0
                avg_loss = sum(losing_pnls) / len(losing_pnls) if losing_pnls else 0.0
                
                # Total volume
                total_volume = sum(trade[2] * trade[3] for trade in trades)
                
                # Trades today
                today = datetime.now().date()
                trades_today = sum(1 for trade in trades if datetime.fromisoformat(trade[4].replace('Z', '+00:00')).date() == today)
                
                # Calculate max drawdown
                cumulative_pnl = 0
                peak = 0
                max_drawdown = 0.0
                
                for trade in trades:
                    cumulative_pnl += trade[0]
                    if cumulative_pnl > peak:
                        peak = cumulative_pnl
                    drawdown = peak - cumulative_pnl
                    if drawdown > max_drawdown:
                        max_drawdown = drawdown
                
                # Calculate Sharpe ratio (simplified)
                if len(pnls) > 1:
                    mean_return = sum(pnls) / len(pnls)
                    variance = sum((pnl - mean_return) ** 2 for pnl in pnls) / len(pnls)
                    std_dev = variance ** 0.5
                    sharpe_ratio = (mean_return / std_dev) if std_dev > 0 else 0.0
                else:
                    sharpe_ratio = 0.0
                
                return {
                    'total_trades': total_trades,
                    'winning_trades': winning_trades,
                    'losing_trades': losing_trades,
                    'win_rate': win_rate,
                    'total_pnl': total_pnl,
                    'total_fees': total_fees,
                    'net_pnl': net_pnl,
                    'max_drawdown': max_drawdown,
                    'sharpe_ratio': sharpe_ratio,
                    'best_trade': best_trade,
                    'worst_trade': worst_trade,
                    'avg_win': avg_win,
                    'avg_loss': avg_loss,
                    'trades_today': trades_today,
                    'total_volume': total_volume
                }
                
        except Exception as e:
            logger.error(f"Failed to get trade stats: {e}")
            return {}
    
    def get_all_trades(self, limit: int = 1000, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all trades with pagination."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT trade_id, session_id, symbol, side, quantity, price, 
                           timestamp, reason, pnl, fees, strategy_type, strategy_params, created_at
                    FROM individual_trades 
                    ORDER BY timestamp DESC 
                    LIMIT ? OFFSET ?
                """, (limit, offset))
                
                rows = cursor.fetchall()
                trades = []
                
                for row in rows:
                    # Parse strategy_params JSON
                    strategy_params = {}
                    if row[11]:
                        try:
                            strategy_params = json.loads(row[11])
                        except:
                            strategy_params = {}
                    
                    trades.append({
                        'trade_id': row[0],
                        'session_id': row[1],
                        'symbol': row[2],
                        'side': row[3],
                        'quantity': row[4],
                        'price': row[5],
                        'timestamp': row[6],
                        'reason': row[7],
                        'pnl': row[8],
                        'fees': row[9],
                        'strategy_type': row[10],
                        'strategy_params': strategy_params,
                        'created_at': row[12]
                    })
                
                return trades
                
        except Exception as e:
            logger.error(f"Failed to get all trades: {e}")
            return []
    
    def get_trades_count(self) -> int:
        """Get total count of trades."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM individual_trades")
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Failed to get trades count: {e}")
            return 0
    
    def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """Get session information."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT session_id, start_time, end_time, status, strategy_type, 
                           total_trades, total_pnl, total_volume, created_at
                    FROM trading_sessions 
                    WHERE session_id = ?
                """, (session_id,))
                
                row = cursor.fetchone()
                if row:
                    return {
                        'session_id': row[0],
                        'start_time': row[1],
                        'end_time': row[2],
                        'status': row[3],
                        'strategy_type': row[4],
                        'total_trades': row[5],
                        'total_pnl': row[6],
                        'total_volume': row[7],
                        'created_at': row[8]
                    }
                return {}
                
        except Exception as e:
            logger.error(f"Failed to get session info: {e}")
            return {}