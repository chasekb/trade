"""Data handling and CSV output functionality with support for all WebSocket data types."""

import csv
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import os
import pandas as pd

from .config import TradingConfig


logger = logging.getLogger(__name__)


class DataHandler:
    """Handles data storage and CSV output for all WebSocket data types."""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.ticker_data: List[Dict[str, Any]] = []
        self.trade_data: List[Dict[str, Any]] = []
        self.signal_data: List[Dict[str, Any]] = []
        self.level2_data: List[Dict[str, Any]] = []
        self.candles_data: List[Dict[str, Any]] = []
        self.matches_data: List[Dict[str, Any]] = []
        self.status_data: List[Dict[str, Any]] = []
        self.market_trades_data: List[Dict[str, Any]] = []
        
        # Ensure output directory exists
        os.makedirs(config.output_dir, exist_ok=True)
    
    def add_ticker_data(self, data: Dict[str, Any]) -> None:
        """Add ticker data point."""
        ticker_record = {
            'timestamp': datetime.now().isoformat(),
            'product_id': data.get('product_id', ''),
            'price': float(data.get('price', 0)),
            'volume_24h': float(data.get('volume_24h', 0)),
            'volume_30d': float(data.get('volume_30d', 0)),
            'best_bid': float(data.get('best_bid', 0)),
            'best_ask': float(data.get('best_ask', 0)),
            'side': data.get('side', ''),
            'time': data.get('time', ''),
            'trade_id': data.get('trade_id', ''),
            'last_size': float(data.get('last_size', 0))
        }
        self.ticker_data.append(ticker_record)
        logger.debug(f"Added ticker data: {ticker_record}")
    
    def add_trade_data(self, trade_info: Dict[str, Any]) -> None:
        """Add trade execution data."""
        trade_record = {
            'timestamp': datetime.now().isoformat(),
            'trade_id': trade_info.get('trade_id', ''),
            'product_id': trade_info.get('product_id', ''),
            'side': trade_info.get('side', ''),
            'price': float(trade_info.get('price', 0)),
            'size': float(trade_info.get('size', 0)),
            'value': float(trade_info.get('value', 0)),
            'fee': float(trade_info.get('fee', 0)),
            'status': trade_info.get('status', ''),
            'order_id': trade_info.get('order_id', '')
        }
        self.trade_data.append(trade_record)
        logger.info(f"Trade executed: {trade_record}")
    
    def add_signal_data(self, signal: Dict[str, Any]) -> None:
        """Add trading signal data."""
        signal_record = {
            'timestamp': signal.get('timestamp', datetime.now().isoformat()),
            'action': signal.get('action', ''),
            'price': float(signal.get('price', 0)),
            'quantity': float(signal.get('quantity', 0)),
            'reason': signal.get('reason', ''),
            'product_id': signal.get('product_id', '')
        }
        self.signal_data.append(signal_record)
        logger.info(f"Signal generated: {signal_record}")
    
    def add_level2_data(self, data: Dict[str, Any]) -> None:
        """Add level2 order book data."""
        level2_record = {
            'timestamp': datetime.now().isoformat(),
            'product_id': data.get('product_id', ''),
            'time': data.get('time', ''),
            'changes': data.get('changes', []),
            'sequence': data.get('sequence', 0)
        }
        self.level2_data.append(level2_record)
        logger.debug(f"Added level2 data: {level2_record}")
    
    def add_candles_data(self, data: Dict[str, Any]) -> None:
        """Add candlestick/OHLCV data."""
        candles_record = {
            'timestamp': datetime.now().isoformat(),
            'product_id': data.get('product_id', ''),
            'time': data.get('time', ''),
            'candles': data.get('candles', []),
            'granularity': data.get('granularity', 0)
        }
        self.candles_data.append(candles_record)
        logger.debug(f"Added candles data: {candles_record}")
    
    def add_matches_data(self, data: Dict[str, Any]) -> None:
        """Add trade matches data."""
        matches_record = {
            'timestamp': datetime.now().isoformat(),
            'product_id': data.get('product_id', ''),
            'time': data.get('time', ''),
            'matches': data.get('matches', []),
            'sequence': data.get('sequence', 0)
        }
        self.matches_data.append(matches_record)
        logger.debug(f"Added matches data: {matches_record}")
    
    def add_status_data(self, data: Dict[str, Any]) -> None:
        """Add product status data."""
        status_record = {
            'timestamp': datetime.now().isoformat(),
            'product_id': data.get('product_id', ''),
            'time': data.get('time', ''),
            'status': data.get('status', ''),
            'message': data.get('message', '')
        }
        self.status_data.append(status_record)
        logger.info(f"Status update: {status_record}")
    
    def add_market_trades_data(self, data: Dict[str, Any]) -> None:
        """Add market trades data."""
        market_trades_record = {
            'timestamp': datetime.now().isoformat(),
            'product_id': data.get('product_id', ''),
            'time': data.get('time', ''),
            'trades': data.get('trades', []),
            'sequence': data.get('sequence', 0)
        }
        self.market_trades_data.append(market_trades_record)
        logger.debug(f"Added market trades data: {market_trades_record}")
    
    def get_latest_ticker(self) -> Optional[Dict[str, Any]]:
        """Get the latest ticker data."""
        return self.ticker_data[-1] if self.ticker_data else None
    
    def get_latest_trades(self) -> List[Dict[str, Any]]:
        """Get the latest trade data."""
        return self.trade_data[-10:] if self.trade_data else []
    
    def get_latest_level2(self) -> Optional[Dict[str, Any]]:
        """Get the latest level2 data."""
        return self.level2_data[-1] if self.level2_data else None
    
    def get_latest_candles(self) -> Optional[Dict[str, Any]]:
        """Get the latest candles data."""
        return self.candles_data[-1] if self.candles_data else None
    
    def get_latest_matches(self) -> Optional[Dict[str, Any]]:
        """Get the latest matches data."""
        return self.matches_data[-1] if self.matches_data else None
    
    def get_latest_status(self) -> Optional[Dict[str, Any]]:
        """Get the latest status data."""
        return self.status_data[-1] if self.status_data else None
    
    def get_latest_market_trades(self) -> Optional[Dict[str, Any]]:
        """Get the latest market trades data."""
        return self.market_trades_data[-1] if self.market_trades_data else None
    
    def save_ticker_data(self) -> str:
        """Save ticker data to CSV."""
        if not self.ticker_data:
            return ""
            
        filename = os.path.join(
            self.config.output_dir, 
            f"ticker_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        df = pd.DataFrame(self.ticker_data)
        df.to_csv(filename, index=False)
        logger.info(f"Saved {len(self.ticker_data)} ticker records to {filename}")
        return filename
    
    def save_trade_data(self) -> str:
        """Save trade data to CSV."""
        if not self.trade_data:
            return ""
            
        filename = os.path.join(
            self.config.output_dir, 
            f"trade_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        df = pd.DataFrame(self.trade_data)
        df.to_csv(filename, index=False)
        logger.info(f"Saved {len(self.trade_data)} trade records to {filename}")
        return filename
    
    def save_signal_data(self) -> str:
        """Save signal data to CSV."""
        if not self.signal_data:
            return ""
            
        filename = os.path.join(
            self.config.output_dir, 
            f"signal_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        df = pd.DataFrame(self.signal_data)
        df.to_csv(filename, index=False)
        logger.info(f"Saved {len(self.signal_data)} signal records to {filename}")
        return filename
    
    def save_level2_data(self) -> str:
        """Save level2 data to CSV."""
        if not self.level2_data:
            return ""
            
        filename = os.path.join(
            self.config.output_dir, 
            f"level2_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        df = pd.DataFrame(self.level2_data)
        df.to_csv(filename, index=False)
        logger.info(f"Saved {len(self.level2_data)} level2 records to {filename}")
        return filename
    
    def save_candles_data(self) -> str:
        """Save candles data to CSV."""
        if not self.candles_data:
            return ""
            
        filename = os.path.join(
            self.config.output_dir, 
            f"candles_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        df = pd.DataFrame(self.candles_data)
        df.to_csv(filename, index=False)
        logger.info(f"Saved {len(self.candles_data)} candles records to {filename}")
        return filename
    
    def save_matches_data(self) -> str:
        """Save matches data to CSV."""
        if not self.matches_data:
            return ""
            
        filename = os.path.join(
            self.config.output_dir, 
            f"matches_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        df = pd.DataFrame(self.matches_data)
        df.to_csv(filename, index=False)
        logger.info(f"Saved {len(self.matches_data)} matches records to {filename}")
        return filename
    
    def save_status_data(self) -> str:
        """Save status data to CSV."""
        if not self.status_data:
            return ""
            
        filename = os.path.join(
            self.config.output_dir, 
            f"status_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        df = pd.DataFrame(self.status_data)
        df.to_csv(filename, index=False)
        logger.info(f"Saved {len(self.status_data)} status records to {filename}")
        return filename
    
    def save_market_trades_data(self) -> str:
        """Save market trades data to CSV."""
        if not self.market_trades_data:
            return ""
            
        filename = os.path.join(
            self.config.output_dir, 
            f"market_trades_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        df = pd.DataFrame(self.market_trades_data)
        df.to_csv(filename, index=False)
        logger.info(f"Saved {len(self.market_trades_data)} market trades records to {filename}")
        return filename
    
    def save_all_data(self) -> Dict[str, str]:
        """Save all data to CSV files."""
        files = {}
        
        if self.ticker_data:
            files['ticker'] = self.save_ticker_data()
        if self.trade_data:
            files['trades'] = self.save_trade_data()
        if self.signal_data:
            files['signals'] = self.save_signal_data()
        if self.level2_data:
            files['level2'] = self.save_level2_data()
        if self.candles_data:
            files['candles'] = self.save_candles_data()
        if self.matches_data:
            files['matches'] = self.save_matches_data()
        if self.status_data:
            files['status'] = self.save_status_data()
        if self.market_trades_data:
            files['market_trades'] = self.save_market_trades_data()
            
        return files
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics for all data types."""
        stats = {
            'ticker_records': len(self.ticker_data),
            'trade_records': len(self.trade_data),
            'signal_records': len(self.signal_data),
            'level2_records': len(self.level2_data),
            'candles_records': len(self.candles_data),
            'matches_records': len(self.matches_data),
            'status_records': len(self.status_data),
            'market_trades_records': len(self.market_trades_data)
        }
        
        if self.trade_data:
            df = pd.DataFrame(self.trade_data)
            stats['total_trades'] = len(df)
            stats['total_volume'] = df['size'].sum()
            stats['total_value'] = df['value'].sum()
            stats['total_fees'] = df['fee'].sum()
            
            if 'price' in df.columns:
                stats['avg_price'] = df['price'].mean()
                stats['min_price'] = df['price'].min()
                stats['max_price'] = df['price'].max()
        
        return stats
