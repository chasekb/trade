"""Order book data handler."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .base_data_handler import BaseDataHandler
from ...core.config import TradingConfig

logger = logging.getLogger(__name__)


class OrderBookHandler(BaseDataHandler):
    """Handles order book data collection and processing."""
    
    def add_level2_data(self, data: Dict[str, Any]) -> None:
        """Add level2 order book data."""
        level2_record = {
            'timestamp': datetime.now().isoformat(),
            'product_id': data.get('product_id', ''),
            'type': data.get('type', ''),
            'bids': data.get('bids', []),
            'asks': data.get('asks', []),
            'time': data.get('time', '')
        }
        self.add_data(level2_record)
        logger.debug(f"Added level2 data: {level2_record}")
    
    def add_candles_data(self, data: Dict[str, Any]) -> None:
        """Add candles/OHLCV data."""
        candle_record = {
            'timestamp': datetime.now().isoformat(),
            'product_id': data.get('product_id', ''),
            'start': data.get('start', ''),
            'end': data.get('end', ''),
            'low': float(data.get('low', 0)),
            'high': float(data.get('high', 0)),
            'open': float(data.get('open', 0)),
            'close': float(data.get('close', 0)),
            'volume': float(data.get('volume', 0))
        }
        self.add_data(candle_record)
        logger.debug(f"Added candle data: {candle_record}")
    
    def add_matches_data(self, data: Dict[str, Any]) -> None:
        """Add matches data."""
        match_record = {
            'timestamp': datetime.now().isoformat(),
            'product_id': data.get('product_id', ''),
            'trade_id': data.get('trade_id', ''),
            'side': data.get('side', ''),
            'price': float(data.get('price', 0)),
            'size': float(data.get('size', 0)),
            'time': data.get('time', '')
        }
        self.add_data(match_record)
        logger.debug(f"Added match data: {match_record}")
    
    def add_status_data(self, data: Dict[str, Any]) -> None:
        """Add product status data."""
        status_record = {
            'timestamp': datetime.now().isoformat(),
            'product_id': data.get('product_id', ''),
            'status': data.get('status', ''),
            'time': data.get('time', '')
        }
        self.add_data(status_record)
        logger.debug(f"Added status data: {status_record}")
    
    def add_market_trades_data(self, data: Dict[str, Any]) -> None:
        """Add market trades data."""
        trade_record = {
            'timestamp': datetime.now().isoformat(),
            'product_id': data.get('product_id', ''),
            'trade_id': data.get('trade_id', ''),
            'side': data.get('side', ''),
            'price': float(data.get('price', 0)),
            'size': float(data.get('size', 0)),
            'time': data.get('time', '')
        }
        self.add_data(trade_record)
        logger.debug(f"Added market trade data: {trade_record}")
    
    def get_latest_level2(self) -> Optional[Dict[str, Any]]:
        """Get the latest level2 data."""
        return self.get_latest()
    
    def get_latest_candles(self) -> Optional[Dict[str, Any]]:
        """Get the latest candle data."""
        return self.get_latest()
    
    def get_latest_matches(self) -> Optional[Dict[str, Any]]:
        """Get the latest match data."""
        return self.get_latest()
    
    def get_latest_status(self) -> Optional[Dict[str, Any]]:
        """Get the latest status data."""
        return self.get_latest()
    
    def get_latest_market_trades(self) -> Optional[Dict[str, Any]]:
        """Get the latest market trade data."""
        return self.get_latest()
    
    def get_best_bid_ask(self, product_id: str = None) -> Dict[str, float]:
        """Get best bid and ask prices."""
        data = [item for item in self.data if item.get('product_id') == product_id] if product_id else self.data
        
        best_bid = 0.0
        best_ask = float('inf')
        
        for item in data:
            if 'bids' in item and item['bids']:
                for bid in item['bids']:
                    if len(bid) >= 2:
                        best_bid = max(best_bid, float(bid[0]))
            
            if 'asks' in item and item['asks']:
                for ask in item['asks']:
                    if len(ask) >= 2:
                        best_ask = min(best_ask, float(ask[0]))
        
        return {
            'best_bid': best_bid if best_bid > 0 else 0.0,
            'best_ask': best_ask if best_ask != float('inf') else 0.0,
            'spread': best_ask - best_bid if best_ask != float('inf') and best_bid > 0 else 0.0
        }
    
    def get_volume_profile(self, product_id: str = None) -> Dict[str, float]:
        """Get volume profile from order book data."""
        data = [item for item in self.data if item.get('product_id') == product_id] if product_id else self.data
        
        total_bid_volume = 0.0
        total_ask_volume = 0.0
        
        for item in data:
            if 'bids' in item:
                for bid in item['bids']:
                    if len(bid) >= 2:
                        total_bid_volume += float(bid[1])
            
            if 'asks' in item:
                for ask in item['asks']:
                    if len(ask) >= 2:
                        total_ask_volume += float(ask[1])
        
        return {
            'total_bid_volume': total_bid_volume,
            'total_ask_volume': total_ask_volume,
            'volume_imbalance': total_bid_volume - total_ask_volume
        }
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get order book-specific summary statistics."""
        base_stats = super().get_summary_stats()
        
        if not self.data:
            return base_stats
        
        best_bid_ask = self.get_best_bid_ask()
        volume_profile = self.get_volume_profile()
        
        base_stats.update({
            'best_bid': best_bid_ask['best_bid'],
            'best_ask': best_bid_ask['best_ask'],
            'spread': best_bid_ask['spread'],
            'total_bid_volume': volume_profile['total_bid_volume'],
            'total_ask_volume': volume_profile['total_ask_volume'],
            'volume_imbalance': volume_profile['volume_imbalance']
        })
        
        return base_stats
