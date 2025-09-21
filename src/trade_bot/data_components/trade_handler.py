"""Trade data handler."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .base_data_handler import BaseDataHandler
from ..config import TradingConfig

logger = logging.getLogger(__name__)


class TradeHandler(BaseDataHandler):
    """Handles trade execution data collection and processing."""
    
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
        self.add_data(trade_record)
        logger.info(f"Trade executed: {trade_record}")
    
    def get_latest_trades(self) -> List[Dict[str, Any]]:
        """Get the latest trade data."""
        return self.get_all_data()
    
    def get_trades_by_product(self, product_id: str) -> List[Dict[str, Any]]:
        """Get trades for a specific product."""
        return [item for item in self.data if item.get('product_id') == product_id]
    
    def get_trades_by_side(self, side: str) -> List[Dict[str, Any]]:
        """Get trades by side (buy/sell)."""
        return [item for item in self.data if item.get('side') == side]
    
    def get_total_volume(self, product_id: str = None) -> float:
        """Get total volume traded."""
        data = self.get_trades_by_product(product_id) if product_id else self.data
        return sum(item.get('size', 0) for item in data)
    
    def get_total_value(self, product_id: str = None) -> float:
        """Get total value traded."""
        data = self.get_trades_by_product(product_id) if product_id else self.data
        return sum(item.get('value', 0) for item in data)
    
    def get_total_fees(self, product_id: str = None) -> float:
        """Get total fees paid."""
        data = self.get_trades_by_product(product_id) if product_id else self.data
        return sum(item.get('fee', 0) for item in data)
    
    def get_average_price(self, product_id: str = None) -> float:
        """Get average trade price."""
        data = self.get_trades_by_product(product_id) if product_id else self.data
        if not data:
            return 0.0
        
        total_value = sum(item.get('value', 0) for item in data)
        total_size = sum(item.get('size', 0) for item in data)
        
        return total_value / total_size if total_size > 0 else 0.0
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get trade-specific summary statistics."""
        base_stats = super().get_summary_stats()
        
        if not self.data:
            return base_stats
        
        buy_trades = self.get_trades_by_side('buy')
        sell_trades = self.get_trades_by_side('sell')
        
        base_stats.update({
            'total_trades': len(self.data),
            'buy_trades': len(buy_trades),
            'sell_trades': len(sell_trades),
            'total_volume': self.get_total_volume(),
            'total_value': self.get_total_value(),
            'total_fees': self.get_total_fees(),
            'average_price': self.get_average_price()
        })
        
        return base_stats
