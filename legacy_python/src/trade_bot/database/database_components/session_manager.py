"""Session manager for trading sessions and dashboard state."""

import psycopg
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
import logging

from .base_database import BaseDatabase

logger = logging.getLogger(__name__)


class SessionManager(BaseDatabase):
    """Manages trading sessions and dashboard state."""
    
    def _create_tables(self, cursor):
        """Create session-related tables."""
        # Trading session state table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trading_sessions (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(255) UNIQUE NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                trading_mode VARCHAR(50) NOT NULL,
                symbol_mode VARCHAR(50) NOT NULL,
                strategy_type VARCHAR(50),
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
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(255) NOT NULL,
                current_symbol VARCHAR(255),
                current_timeframe VARCHAR(50),
                chart_settings TEXT,
                ui_preferences TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES trading_sessions (session_id)
            )
        """)
    
    def save_trading_session(self, session_id: str, session_data: Dict[str, Any]) -> bool:
        """Save trading session state."""
        try:
            query = """
                INSERT INTO trading_sessions
                (session_id, is_active, trading_mode, symbol_mode, strategy_type,
                 strategy_params, symbols, universe_config, portfolio_state,
                 positions, recent_trades, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (session_id)
                DO UPDATE SET is_active = EXCLUDED.is_active,
                              trading_mode = EXCLUDED.trading_mode,
                              symbol_mode = EXCLUDED.symbol_mode,
                              strategy_type = EXCLUDED.strategy_type,
                              strategy_params = EXCLUDED.strategy_params,
                              symbols = EXCLUDED.symbols,
                              universe_config = EXCLUDED.universe_config,
                              portfolio_state = EXCLUDED.portfolio_state,
                              positions = EXCLUDED.positions,
                              recent_trades = EXCLUDED.recent_trades,
                              updated_at = EXCLUDED.updated_at
            """

            return self._execute_update(query, (
                session_id,
                session_data.get('is_active', True),
                session_data.get('trading_mode', ''),
                session_data.get('symbol_mode', ''),
                session_data.get('strategy_type'),
                json.dumps(session_data.get('strategy_params', {})),
                json.dumps(session_data.get('symbols', [])),
                json.dumps(session_data.get('universe_config', {})),
                json.dumps(session_data.get('portfolio_state', {})),
                json.dumps(session_data.get('positions', {})),
                json.dumps(session_data.get('recent_trades', [])),
                datetime.now()
            ))
        except Exception as e:
            logger.error(f"Error saving trading session: {e}")
            return False

    def load_trading_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load trading session state."""
        try:
            query = """
                SELECT is_active, trading_mode, symbol_mode, strategy_type,
                       strategy_params, symbols, universe_config, portfolio_state,
                       positions, recent_trades, created_at, updated_at
                FROM trading_sessions WHERE session_id = %s
            """

            results = self._execute_query(query, (session_id,))

            if results:
                row = results[0]
                return {
                    'session_id': session_id,
                    'is_active': bool(row[0]),
                    'trading_mode': row[1],
                    'symbol_mode': row[2],
                    'strategy_type': row[3],
                    'strategy_params': json.loads(row[4]) if row[4] else {},
                    'symbols': json.loads(row[5]) if row[5] else [],
                    'universe_config': json.loads(row[6]) if row[6] else {},
                    'portfolio_state': json.loads(row[7]) if row[7] else {},
                    'positions': json.loads(row[8]) if row[8] else {},
                    'recent_trades': json.loads(row[9]) if row[9] else [],
                    'created_at': row[10],
                    'updated_at': row[11]
                }

            return None
        except Exception as e:
            logger.error(f"Error loading trading session: {e}")
            return None

    def save_dashboard_state(self, session_id: str, state_data: Dict[str, Any]) -> bool:
        """Save dashboard UI state."""
        try:
            query = """
                INSERT INTO dashboard_state
                (session_id, current_symbol, current_timeframe, chart_settings,
                 ui_preferences, last_updated)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (session_id)
                DO UPDATE SET current_symbol = EXCLUDED.current_symbol,
                              current_timeframe = EXCLUDED.current_timeframe,
                              chart_settings = EXCLUDED.chart_settings,
                              ui_preferences = EXCLUDED.ui_preferences,
                              last_updated = EXCLUDED.last_updated
            """

            return self._execute_update(query, (
                session_id,
                state_data.get('current_symbol'),
                state_data.get('current_timeframe'),
                json.dumps(state_data.get('chart_settings', {})),
                json.dumps(state_data.get('ui_preferences', {})),
                datetime.now()
            ))
        except Exception as e:
            logger.error(f"Error saving dashboard state: {e}")
            return False

    def load_dashboard_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load dashboard UI state."""
        try:
            query = """
                SELECT current_symbol, current_timeframe, chart_settings,
                       ui_preferences, last_updated
                FROM dashboard_state WHERE session_id = %s
            """

            results = self._execute_query(query, (session_id,))

            if results:
                row = results[0]
                return {
                    'session_id': session_id,
                    'current_symbol': row[0],
                    'current_timeframe': row[1],
                    'chart_settings': json.loads(row[2]) if row[2] else {},
                    'ui_preferences': json.loads(row[3]) if row[3] else {},
                    'last_updated': row[4]
                }

            return None
        except Exception as e:
            logger.error(f"Error loading dashboard state: {e}")
            return None

    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get all active trading sessions."""
        try:
            query = """
                SELECT session_id, trading_mode, symbol_mode, strategy_type,
                       created_at, updated_at
                FROM trading_sessions
                WHERE is_active = TRUE
                ORDER BY updated_at DESC
            """

            results = self._execute_query(query)
            sessions = []

            for row in results:
                sessions.append({
                    'session_id': row[0],
                    'trading_mode': row[1],
                    'symbol_mode': row[2],
                    'strategy_type': row[3],
                    'created_at': row[4],
                    'updated_at': row[5]
                })

            return sessions
        except Exception as e:
            logger.error(f"Error getting active sessions: {e}")
            return []

    def deactivate_session(self, session_id: str) -> bool:
        """Deactivate a trading session."""
        try:
            query = """
                UPDATE trading_sessions
                SET is_active = FALSE, updated_at = %s
                WHERE session_id = %s
            """

            return self._execute_update(query, (datetime.now(), session_id))
        except Exception as e:
            logger.error(f"Error deactivating session: {e}")
            return False
