from typing import List
"""Ticker data handler."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .base_data_handler import BaseDataHandler
from ...core.config import TradingConfig

logger = logging.getLogger(__name__)


class TickerHandler(BaseDataHandler):
    """Handles ticker data collection and processing."""
    
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
        self.add_data(ticker_record)
        logger.debug(f"Added ticker data: {ticker_record}")
    
    def get_latest_ticker(self) -> Optional[Dict[str, Any]]:
        """Get the latest ticker data."""
        return self.get_latest()
    
    def get_ticker_by_product(self, product_id: str) -> List[Dict[str, Any]]:
        """Get ticker data for a specific product."""
        return [item for item in self.data if item.get('product_id') == product_id]
    
    def get_price_history(self, product_id: str = None) -> List[float]:
        """Get price history for a product."""
        data = self.get_ticker_by_product(product_id) if product_id else self.data
        return [item.get('price', 0) for item in data if 'price' in item]
    
    def get_volume_history(self, product_id: str = None) -> List[float]:
        """Get volume history for a product."""
        data = self.get_ticker_by_product(product_id) if product_id else self.data
        return [item.get('volume_24h', 0) for item in data if 'volume_24h' in item]
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get ticker-specific summary statistics."""
        base_stats = super().get_summary_stats()
        
        if not self.data:
            return base_stats
        
        prices = self.get_price_history()
        volumes = self.get_volume_history()
        
        if prices:
            base_stats.update({
                'current_price': prices[-1] if prices else 0,
                'min_price': min(prices),
                'max_price': max(prices),
                'price_change': prices[-1] - prices[0] if len(prices) > 1 else 0,
                'price_change_pct': ((prices[-1] - prices[0]) / prices[0] * 100) if len(prices) > 1 and prices[0] != 0 else 0
            })
        
        if volumes:
            base_stats.update({
                'avg_volume_24h': sum(volumes) / len(volumes),
                'max_volume_24h': max(volumes),
                'min_volume_24h': min(volumes)
            })
        
        return base_stats
