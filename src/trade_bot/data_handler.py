"""Data handling and CSV output functionality."""

import csv
import logging
from typing import Dict, Any, List
from datetime import datetime
import os
import pandas as pd

from .config import TradingConfig


logger = logging.getLogger(__name__)


class DataHandler:
    """Handles data storage and CSV output."""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.ticker_data: List[Dict[str, Any]] = []
        self.trade_data: List[Dict[str, Any]] = []
        self.signal_data: List[Dict[str, Any]] = []
        
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
    
    def save_all_data(self) -> Dict[str, str]:
        """Save all data to CSV files."""
        files = {}
        
        if self.ticker_data:
            files['ticker'] = self.save_ticker_data()
        if self.trade_data:
            files['trades'] = self.save_trade_data()
        if self.signal_data:
            files['signals'] = self.save_signal_data()
            
        return files
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics."""
        stats = {
            'ticker_records': len(self.ticker_data),
            'trade_records': len(self.trade_data),
            'signal_records': len(self.signal_data)
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
