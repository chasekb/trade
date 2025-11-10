from typing import List
"""ML Data Collector for extracting and preprocessing trading data."""

import logging
import sqlite3
import json
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import os

logger = logging.getLogger(__name__)

# Try to import PostgreSQL support
try:
    import psycopg
    PSYCOPG_AVAILABLE = True
except ImportError:
    PSYCOPG_AVAILABLE = False
    logger.warning("psycopg not available, PostgreSQL support disabled")


@dataclass
class OrderBookFeatures:
    """Order book feature vector."""
    timestamp: int
    symbol: str
    bid_ask_imbalance: float
    spread_percent: float
    mid_price: float
    bid_volume: float
    ask_volume: float
    order_book_depth: int
    large_bid_wall: bool
    large_ask_wall: bool
    wall_size: float
    volume_weighted_price: float
    price_momentum: float
    volatility: float
    # Features from previous ML analysis
    prev_win_probability: float = 0.0
    prev_expected_return: float = 0.0
    prev_confidence: float = 0.0


@dataclass
class TradeOutcome:
    """Trade outcome for ML training."""
    trade_id: str
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    fees: float
    duration_seconds: int
    signal_type: str
    signal_strength: float
    entry_timestamp: int
    exit_timestamp: int


class MLDataCollector:
    """Collects and preprocesses trading data for ML training."""
    
    def __init__(self, db_path: str = None):
        """
        Initialize ML data collector.
        
        Args:
            db_path: Database path (SQLite) or URL (PostgreSQL).
                    If None, uses DATABASE_URL env var or defaults to SQLite.
        """
        if db_path is None:
            db_path = os.getenv("DATABASE_URL", "data/databases/trading_cache.db")
        
        self.db_path = db_path
        self.is_postgres = db_path.startswith("postgresql://") or db_path.startswith("postgres://")
        
        if self.is_postgres and not PSYCOPG_AVAILABLE:
            raise ImportError("PostgreSQL support requires psycopg. Install with: pip install psycopg")
        
    def extract_order_book_signals(self, days_back: int = 30) -> List[Dict[str, Any]]:
        """Extract order book signals from database."""
        try:
            # Calculate timestamp threshold
            threshold_timestamp = int((datetime.now() - timedelta(days=days_back)).timestamp())
            
            if self.is_postgres:
                return self._extract_signals_from_postgres(threshold_timestamp)
            else:
                return self._extract_signals_from_sqlite(threshold_timestamp)
                
        except Exception as e:
            logger.error(f"Error extracting order book signals: {e}")
            return []
    
    def _extract_signals_from_postgres(self, threshold_timestamp: int) -> List[Dict[str, Any]]:
        """Extract signals from PostgreSQL database."""
        conn = psycopg.connect(self.db_path)
        cursor = conn.cursor()
        
        # PostgreSQL schema: signal_id, session_id, symbol, signal_type, strength, price, 
        #                    timestamp, signal_data (JSON), processed, created_at
        query = """
            SELECT signal_id, session_id, symbol, signal_type, strength, price, 
                   timestamp, signal_data
            FROM order_book_signals 
            WHERE timestamp >= %s
            ORDER BY timestamp ASC
        """
        
        cursor.execute(query, (threshold_timestamp,))
        results = cursor.fetchall()
        
        signals = []
        for row in results:
            # Parse signal_data JSON
            signal_data_json = json.loads(row[7]) if row[7] else {}
            
            # Extract fields from signal_data JSON (stored in criteria_analysis or directly)
            criteria_analysis = signal_data_json.get('criteria_analysis', {})
            volume_imbalance = criteria_analysis.get('volume_imbalance_buy', {})
            ml_analysis = signal_data_json.get('ml_analysis', {})
            
            signals.append({
                'signal_id': row[0],
                'session_id': row[1],
                'symbol': row[2],
                'signal_type': row[3],
                'strength': row[4],
                'price': row[5],
                'timestamp': row[6],
                'signal_data': signal_data_json,
                'ml_analysis': ml_analysis,
                'spread': signal_data_json.get('spread', 0.0),
                'imbalance': volume_imbalance.get('current_value', 0.0) if isinstance(volume_imbalance, dict) else 0.0,
                'mid_price': row[5],  # Use price as mid_price
                'best_bid': signal_data_json.get('best_bid', row[5] * 0.999),  # Estimate if not available
                'best_ask': signal_data_json.get('best_ask', row[5] * 1.001),  # Estimate if not available
                'order_book_depth': 2,  # Default depth
                'volume': signal_data_json.get('volume', 0.0),
                'total_signals': 1  # Not stored in PostgreSQL
            })
        
        conn.close()
        logger.info(f"Extracted {len(signals)} order book signals from PostgreSQL")
        return signals
    
    def _extract_signals_from_sqlite(self, threshold_timestamp: int) -> List[Dict[str, Any]]:
        """Extract signals from SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = """
            SELECT signal_id, session_id, symbol, signal_type, strength, price, 
                   timestamp, signal_data, spread, imbalance, mid_price, 
                   best_bid, best_ask, order_book_depth, volume, total_signals
            FROM order_book_signals 
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
        """
        
        cursor.execute(query, (threshold_timestamp,))
        results = cursor.fetchall()
        
        signals = []
        for row in results:
            signal_data = json.loads(row[7]) if row[7] else {}
            signals.append({
                'signal_id': row[0],
                'session_id': row[1],
                'symbol': row[2],
                'signal_type': row[3],
                'strength': row[4],
                'price': row[5],
                'timestamp': row[6],
                'signal_data': signal_data,
                'spread': row[8],
                'imbalance': row[9],
                'mid_price': row[10],
                'best_bid': row[11],
                'best_ask': row[12],
                'order_book_depth': row[13],
                'volume': row[14],
                'total_signals': row[15]
            })
        
        conn.close()
        logger.info(f"Extracted {len(signals)} order book signals from SQLite")
        return signals
    
    def extract_trade_outcomes(self, days_back: int = 30) -> List[Dict[str, Any]]:
        """Extract trade outcomes for ML training."""
        try:
            # Calculate timestamp threshold
            threshold_timestamp = int((datetime.now() - timedelta(days=days_back)).timestamp())
            
            if self.is_postgres:
                return self._extract_trades_from_postgres(threshold_timestamp)
            else:
                return self._extract_trades_from_sqlite(threshold_timestamp)
                
        except Exception as e:
            logger.error(f"Error extracting trade outcomes: {e}")
            return []
    
    def _extract_trades_from_postgres(self, threshold_timestamp: int) -> List[Dict[str, Any]]:
        """Extract trades from PostgreSQL database."""
        conn = psycopg.connect(self.db_path)
        cursor = conn.cursor()
        
        query = """
            SELECT trade_id, session_id, symbol, side, size, price, timestamp,
                   strategy_type, signal_reason, pnl, fees, created_at
            FROM individual_trades 
            WHERE timestamp >= %s
            ORDER BY timestamp ASC
        """
        
        cursor.execute(query, (threshold_timestamp,))
        results = cursor.fetchall()
        
        trades = []
        for row in results:
            trades.append({
                'trade_id': row[0],
                'session_id': row[1],
                'symbol': row[2],
                'side': row[3],
                'size': float(row[4]) if row[4] else 0.0,
                'price': float(row[5]),
                'timestamp': int(row[6]),
                'strategy_type': row[7],
                'signal_reason': row[8],
                'pnl': float(row[9]) if row[9] else 0.0,
                'fees': float(row[10]) if row[10] else 0.0,
                'created_at': row[11].isoformat() if row[11] else None
            })
        
        conn.close()
        logger.info(f"Extracted {len(trades)} trade outcomes from PostgreSQL")
        return trades
    
    def _extract_trades_from_sqlite(self, threshold_timestamp: int) -> List[Dict[str, Any]]:
        """Extract trades from SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = """
            SELECT trade_id, session_id, symbol, side, size, price, timestamp,
                   strategy_type, signal_reason, pnl, fees, created_at
            FROM individual_trades 
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
        """
        
        cursor.execute(query, (threshold_timestamp,))
        results = cursor.fetchall()
        
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
        
        conn.close()
        logger.info(f"Extracted {len(trades)} trade outcomes from SQLite")
        return trades
    
    def get_trades_by_pnl(self, limit: int = 10, sort_by: str = 'pnl') -> Dict[str, List[Dict[str, Any]]]:
        """Get top and bottom trades by PnL."""
        try:
            if self.is_postgres:
                return self._get_pnl_trades_from_postgres(limit, sort_by)
            else:
                return self._get_pnl_trades_from_sqlite(limit, sort_by)
        except Exception as e:
            logger.error(f"Error getting trades by PnL: {e}")
            return {"top_trades": [], "bottom_trades": []}

    def _get_pnl_trades_from_postgres(self, limit: int, sort_by: str) -> Dict[str, List[Dict[str, Any]]]:
        """Get top/bottom PnL trades from PostgreSQL."""
        conn = psycopg.connect(self.db_path)
        cursor = conn.cursor()

        order_by = 'pnl' if sort_by == 'pnl' else '(pnl / (price * size)) * 100'

        query_top = f"""
            SELECT trade_id, symbol, side, price, size, pnl, timestamp,
                   (pnl / (price * size)) * 100 as pnl_percent
            FROM individual_trades
            WHERE pnl IS NOT NULL AND price > 0 AND size > 0
            ORDER BY {order_by} DESC
            LIMIT %s
        """
        cursor.execute(query_top, (limit,))
        top_trades = cursor.fetchall()

        query_bottom = f"""
            SELECT trade_id, symbol, side, price, size, pnl, timestamp,
                   (pnl / (price * size)) * 100 as pnl_percent
            FROM individual_trades
            WHERE pnl IS NOT NULL AND price > 0 AND size > 0
            ORDER BY {order_by} ASC
            LIMIT %s
        """
        cursor.execute(query_bottom, (limit,))
        bottom_trades = cursor.fetchall()

        conn.close()
        
        return {
            "top_trades": [dict(zip([c.name for c in cursor.description], row)) for row in top_trades],
            "bottom_trades": [dict(zip([c.name for c in cursor.description], row)) for row in bottom_trades]
        }

    def _get_pnl_trades_from_sqlite(self, limit: int, sort_by: str) -> Dict[str, List[Dict[str, Any]]]:
        """Get top/bottom PnL trades from SQLite."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        order_by = 'pnl' if sort_by == 'pnl' else 'pnl_percent'

        query_top = f"""
            SELECT trade_id, symbol, side, price, size, pnl, timestamp,
                   (pnl / (price * size)) * 100 as pnl_percent
            FROM individual_trades
            WHERE pnl IS NOT NULL AND price > 0 AND size > 0
            ORDER BY {order_by} DESC
            LIMIT ?
        """
        cursor.execute(query_top, (limit,))
        top_trades = [dict(row) for row in cursor.fetchall()]

        query_bottom = f"""
            SELECT trade_id, symbol, side, price, size, pnl, timestamp,
                   (pnl / (price * size)) * 100 as pnl_percent
            FROM individual_trades
            WHERE pnl IS NOT NULL AND price > 0 AND size > 0
            ORDER BY {order_by} ASC
            LIMIT ?
        """
        cursor.execute(query_bottom, (limit,))
        bottom_trades = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return {"top_trades": top_trades, "bottom_trades": bottom_trades}
        
    def extract_order_book_snapshots(self, symbol: str, days_back: int = 7) -> List[Dict[str, Any]]:
        """Extract order book snapshots for feature engineering."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Calculate timestamp threshold
            threshold_timestamp = int((datetime.now() - timedelta(days=days_back)).timestamp())
            
            query = """
                SELECT product_id, timestamp, data_json, created_at
                FROM order_book_snapshots 
                WHERE product_id = ? AND timestamp >= ?
                ORDER BY timestamp ASC
            """
            
            cursor.execute(query, (symbol, threshold_timestamp))
            results = cursor.fetchall()
            
            snapshots = []
            for row in results:
                data_json = json.loads(row[2]) if row[2] else {}
                snapshots.append({
                    'product_id': row[0],
                    'timestamp': row[1],
                    'data_json': data_json,
                    'created_at': row[3]
                })
            
            conn.close()
            logger.info(f"Extracted {len(snapshots)} order book snapshots for {symbol}")
            return snapshots
            
        except Exception as e:
            logger.error(f"Error extracting order book snapshots: {e}")
            return []
    
    def create_feature_vectors(self, signals: List[Dict[str, Any]], 
                              trades: List[Dict[str, Any]]) -> List[OrderBookFeatures]:
        """Create feature vectors from signals and trades."""
        feature_vectors = []
        
        # Convert to DataFrames for easier processing
        signals_df = pd.DataFrame(signals)
        trades_df = pd.DataFrame(trades)
        
        if signals_df.empty:
            logger.warning("No signals available for feature vector creation")
            return feature_vectors
        
        # Group by symbol and timestamp for feature engineering
        for symbol in signals_df['symbol'].unique():
            symbol_signals = signals_df[signals_df['symbol'] == symbol].copy()
            symbol_trades = trades_df[trades_df['symbol'] == symbol].copy() if not trades_df.empty else pd.DataFrame()
            
            # Sort by timestamp and reset index for positional access
            symbol_signals = symbol_signals.sort_values('timestamp').reset_index(drop=True)
            
            for pos_idx, (df_idx, signal) in enumerate(symbol_signals.iterrows()):
                try:
                    # Get previous signal's ML analysis if available
                    prev_ml_analysis = {}
                    if pos_idx > 0:
                        prev_signal = symbol_signals.iloc[pos_idx - 1]
                        if 'ml_analysis' in prev_signal and prev_signal['ml_analysis']:
                            prev_ml_analysis = prev_signal['ml_analysis']

                    # Extract order book features
                    features = OrderBookFeatures(
                        timestamp=int(signal['timestamp']),
                        symbol=symbol,
                        bid_ask_imbalance=float(signal.get('imbalance', 0.0)),
                        spread_percent=float(signal.get('spread', 0.0)),
                        mid_price=float(signal.get('mid_price', signal['price'])),
                        bid_volume=self._calculate_bid_volume(signal),
                        ask_volume=self._calculate_ask_volume(signal),
                        order_book_depth=int(signal.get('order_book_depth', 0)),
                        large_bid_wall=self._detect_large_bid_wall(signal),
                        large_ask_wall=self._detect_large_ask_wall(signal),
                        wall_size=self._calculate_wall_size(signal),
                        volume_weighted_price=self._calculate_vwap(signal),
                        price_momentum=self._calculate_price_momentum(symbol_signals, signal),
                        volatility=self._calculate_volatility(symbol_signals, signal),
                        prev_win_probability=float(prev_ml_analysis.get('win_probability', 0.0) / 100.0), # Normalize to 0-1
                        prev_expected_return=float(prev_ml_analysis.get('expected_return', 0.0)),
                        prev_confidence=float(prev_ml_analysis.get('confidence', 0.0))
                    )
                    
                    feature_vectors.append(features)
                    
                except Exception as e:
                    logger.warning(f"Error creating feature vector for signal {signal['signal_id']}: {e}")
                    continue
        
        logger.info(f"Created {len(feature_vectors)} feature vectors")
        return feature_vectors
    
    def create_training_labels(self, feature_vectors: List[OrderBookFeatures], 
                              trades: List[Dict[str, Any]]) -> List[Tuple[OrderBookFeatures, TradeOutcome]]:
        """Create training labels by matching features with trade outcomes."""
        training_data = []
        
        # Convert trades to DataFrame for easier matching
        trades_df = pd.DataFrame(trades) if trades else pd.DataFrame()
        
        if trades_df.empty:
            logger.warning("No trades available for label creation")
            return training_data
        
        for features in feature_vectors:
            # Find trades that occurred within a time window after this signal
            time_window = 300  # 5 minutes
            matching_trades = trades_df[
                (trades_df['symbol'] == features.symbol) &
                (trades_df['timestamp'] >= features.timestamp) &
                (trades_df['timestamp'] <= features.timestamp + time_window)
            ]
            
            if not matching_trades.empty:
                # Use the first matching trade as the outcome
                trade = matching_trades.iloc[0]
                
                # Calculate trade outcome
                outcome = TradeOutcome(
                    trade_id=trade['trade_id'],
                    symbol=trade['symbol'],
                    side=trade['side'],
                    entry_price=float(trade['price']),
                    exit_price=float(trade['price']),  # Simplified - would need actual exit price
                    quantity=float(trade['size']),
                    pnl=float(trade['pnl']),
                    fees=float(trade['fees']),
                    duration_seconds=int(trade['timestamp']) - features.timestamp,
                    signal_type=features.symbol,  # Placeholder
                    signal_strength=features.bid_ask_imbalance,
                    entry_timestamp=features.timestamp,
                    exit_timestamp=int(trade['timestamp'])
                )
                
                training_data.append((features, outcome))
        
        logger.info(f"Created {len(training_data)} training examples")
        return training_data
    
    def _calculate_bid_volume(self, signal: pd.Series) -> float:
        """Calculate total bid volume from signal data."""
        try:
            signal_data = signal.get('signal_data', {})
            if isinstance(signal_data, str):
                signal_data = json.loads(signal_data)
            
            bids = signal_data.get('bids', [])
            if not bids:
                return 0.0
            
            return sum(float(bid[1]) for bid in bids[:5] if len(bid) >= 2)
        except Exception:
            return 0.0
    
    def _calculate_ask_volume(self, signal: pd.Series) -> float:
        """Calculate total ask volume from signal data."""
        try:
            signal_data = signal.get('signal_data', {})
            if isinstance(signal_data, str):
                signal_data = json.loads(signal_data)
            
            asks = signal_data.get('asks', [])
            if not asks:
                return 0.0
            
            return sum(float(ask[1]) for ask in asks[:5] if len(ask) >= 2)
        except Exception:
            return 0.0
    
    def _detect_large_bid_wall(self, signal: pd.Series) -> bool:
        """Detect if there's a large bid wall."""
        try:
            signal_data = signal.get('signal_data', {})
            if isinstance(signal_data, str):
                signal_data = json.loads(signal_data)
            
            bids = signal_data.get('bids', [])
            if not bids:
                return False
            
            # Check if any bid level has volume > 1000
            for bid in bids[:10]:
                if len(bid) >= 2 and float(bid[1]) > 1000:
                    return True
            
            return False
        except Exception:
            return False
    
    def _detect_large_ask_wall(self, signal: pd.Series) -> bool:
        """Detect if there's a large ask wall."""
        try:
            signal_data = signal.get('signal_data', {})
            if isinstance(signal_data, str):
                signal_data = json.loads(signal_data)
            
            asks = signal_data.get('asks', [])
            if not asks:
                return False
            
            # Check if any ask level has volume > 1000
            for ask in asks[:10]:
                if len(ask) >= 2 and float(ask[1]) > 1000:
                    return True
            
            return False
        except Exception:
            return False
    
    def _calculate_wall_size(self, signal: pd.Series) -> float:
        """Calculate the size of the largest wall."""
        try:
            signal_data = signal.get('signal_data', {})
            if isinstance(signal_data, str):
                signal_data = json.loads(signal_data)
            
            bids = signal_data.get('bids', [])
            asks = signal_data.get('asks', [])
            
            max_bid_volume = max((float(bid[1]) for bid in bids[:10] if len(bid) >= 2), default=0.0)
            max_ask_volume = max((float(ask[1]) for ask in asks[:10] if len(ask) >= 2), default=0.0)
            
            return max(max_bid_volume, max_ask_volume)
        except Exception:
            return 0.0
    
    def _calculate_vwap(self, signal: pd.Series) -> float:
        """Calculate volume-weighted average price."""
        try:
            signal_data = signal.get('signal_data', {})
            if isinstance(signal_data, str):
                signal_data = json.loads(signal_data)
            
            bids = signal_data.get('bids', [])
            asks = signal_data.get('asks', [])
            
            if not bids or not asks:
                return float(signal.get('mid_price', signal['price']))
            
            # Calculate VWAP from top 5 levels
            total_volume = 0
            total_value = 0
            
            for bid in bids[:5]:
                if len(bid) >= 2:
                    price, volume = float(bid[0]), float(bid[1])
                    total_value += price * volume
                    total_volume += volume
            
            for ask in asks[:5]:
                if len(ask) >= 2:
                    price, volume = float(ask[0]), float(ask[1])
                    total_value += price * volume
                    total_volume += volume
            
            return total_value / total_volume if total_volume > 0 else float(signal.get('mid_price', signal['price']))
        except Exception:
            return float(signal.get('mid_price', signal['price']))
    
    def _calculate_price_momentum(self, symbol_signals: pd.DataFrame, signal: pd.Series) -> float:
        """Calculate price momentum over recent signals."""
        try:
            # Get recent signals (last 10)
            recent_signals = symbol_signals[
                symbol_signals['timestamp'] <= signal['timestamp']
            ].tail(10)
            
            if len(recent_signals) < 2:
                return 0.0
            
            prices = recent_signals['price'].values
            if len(prices) < 2:
                return 0.0
            
            # Calculate momentum as price change percentage
            initial_price = prices[0] if prices[0] != 0 else 1e-9
            return ((prices[-1] - initial_price) / initial_price) * 100
        except Exception:
            return 0.0
    
    def _calculate_volatility(self, symbol_signals: pd.DataFrame, signal: pd.Series) -> float:
        """Calculate price volatility over recent signals."""
        try:
            # Get recent signals (last 20)
            recent_signals = symbol_signals[
                symbol_signals['timestamp'] <= signal['timestamp']
            ].tail(20)
            
            if len(recent_signals) < 2:
                return 0.0
            
            prices = recent_signals['price'].values
            if len(prices) < 2:
                return 0.0
            
            # Calculate volatility as standard deviation of price changes
            price_changes = np.diff(prices) / (prices[:-1] + 1e-9)  # Avoid division by zero
            return float(np.std(price_changes)) * 100
        except Exception:
            return 0.0
