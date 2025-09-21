"""CSV export functionality for data handlers."""

import csv
import logging
from typing import Dict, Any, List
from datetime import datetime
import os

from ..config import TradingConfig

logger = logging.getLogger(__name__)


class CSVExporter:
    """Handles CSV export for various data types."""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.output_dir = config.output_dir
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
    
    def export_ticker_data(self, data: List[Dict[str, Any]]) -> str:
        """Export ticker data to CSV."""
        if not data:
            return ""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ticker_data_{timestamp}.csv"
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = data[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
            
            logger.info(f"Ticker data exported to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error exporting ticker data: {e}")
            return ""
    
    def export_trade_data(self, data: List[Dict[str, Any]]) -> str:
        """Export trade data to CSV."""
        if not data:
            return ""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"trade_data_{timestamp}.csv"
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = data[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
            
            logger.info(f"Trade data exported to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error exporting trade data: {e}")
            return ""
    
    def export_signal_data(self, data: List[Dict[str, Any]]) -> str:
        """Export signal data to CSV."""
        if not data:
            return ""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"signal_data_{timestamp}.csv"
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = data[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
            
            logger.info(f"Signal data exported to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error exporting signal data: {e}")
            return ""
    
    def export_level2_data(self, data: List[Dict[str, Any]]) -> str:
        """Export level2 data to CSV."""
        if not data:
            return ""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"level2_data_{timestamp}.csv"
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = data[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
            
            logger.info(f"Level2 data exported to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error exporting level2 data: {e}")
            return ""
    
    def export_candles_data(self, data: List[Dict[str, Any]]) -> str:
        """Export candles data to CSV."""
        if not data:
            return ""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"candles_data_{timestamp}.csv"
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = data[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
            
            logger.info(f"Candles data exported to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error exporting candles data: {e}")
            return ""
    
    def export_matches_data(self, data: List[Dict[str, Any]]) -> str:
        """Export matches data to CSV."""
        if not data:
            return ""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"matches_data_{timestamp}.csv"
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = data[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
            
            logger.info(f"Matches data exported to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error exporting matches data: {e}")
            return ""
    
    def export_status_data(self, data: List[Dict[str, Any]]) -> str:
        """Export status data to CSV."""
        if not data:
            return ""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"status_data_{timestamp}.csv"
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = data[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
            
            logger.info(f"Status data exported to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error exporting status data: {e}")
            return ""
    
    def export_market_trades_data(self, data: List[Dict[str, Any]]) -> str:
        """Export market trades data to CSV."""
        if not data:
            return ""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"market_trades_data_{timestamp}.csv"
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = data[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
            
            logger.info(f"Market trades data exported to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error exporting market trades data: {e}")
            return ""
    
    def export_all_data(self, data_handlers: Dict[str, Any]) -> Dict[str, str]:
        """Export all data types to CSV files."""
        results = {}
        
        for handler_name, handler in data_handlers.items():
            if hasattr(handler, 'get_all_data'):
                data = handler.get_all_data()
                if data:
                    if handler_name == 'ticker':
                        results[handler_name] = self.export_ticker_data(data)
                    elif handler_name == 'trade':
                        results[handler_name] = self.export_trade_data(data)
                    elif handler_name == 'signal':
                        results[handler_name] = self.export_signal_data(data)
                    elif handler_name == 'level2':
                        results[handler_name] = self.export_level2_data(data)
                    elif handler_name == 'candles':
                        results[handler_name] = self.export_candles_data(data)
                    elif handler_name == 'matches':
                        results[handler_name] = self.export_matches_data(data)
                    elif handler_name == 'status':
                        results[handler_name] = self.export_status_data(data)
                    elif handler_name == 'market_trades':
                        results[handler_name] = self.export_market_trades_data(data)
        
        return results
