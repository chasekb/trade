"""Trading signal data handler."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .base_data_handler import BaseDataHandler
from ..config import TradingConfig

logger = logging.getLogger(__name__)


class SignalHandler(BaseDataHandler):
    """Handles trading signal data collection and processing."""
    
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
        self.add_data(signal_record)
        logger.info(f"Signal generated: {signal_record}")
    
    def get_latest_signal(self) -> Optional[Dict[str, Any]]:
        """Get the latest signal."""
        return self.get_latest()
    
    def get_signals_by_action(self, action: str) -> List[Dict[str, Any]]:
        """Get signals by action (buy/sell/hold)."""
        return [item for item in self.data if item.get('action') == action]
    
    def get_signals_by_product(self, product_id: str) -> List[Dict[str, Any]]:
        """Get signals for a specific product."""
        return [item for item in self.data if item.get('product_id') == product_id]
    
    def get_buy_signals(self) -> List[Dict[str, Any]]:
        """Get all buy signals."""
        return self.get_signals_by_action('buy')
    
    def get_sell_signals(self) -> List[Dict[str, Any]]:
        """Get all sell signals."""
        return self.get_signals_by_action('sell')
    
    def get_hold_signals(self) -> List[Dict[str, Any]]:
        """Get all hold signals."""
        return self.get_signals_by_action('hold')
    
    def get_signal_frequency(self, action: str = None) -> int:
        """Get signal frequency for a specific action or all signals."""
        if action:
            return len(self.get_signals_by_action(action))
        return len(self.data)
    
    def get_average_quantity(self, action: str = None) -> float:
        """Get average quantity for signals."""
        data = self.get_signals_by_action(action) if action else self.data
        if not data:
            return 0.0
        
        quantities = [item.get('quantity', 0) for item in data]
        return sum(quantities) / len(quantities)
    
    def get_average_price(self, action: str = None) -> float:
        """Get average price for signals."""
        data = self.get_signals_by_action(action) if action else self.data
        if not data:
            return 0.0
        
        prices = [item.get('price', 0) for item in data]
        return sum(prices) / len(prices)
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get signal-specific summary statistics."""
        base_stats = super().get_summary_stats()
        
        if not self.data:
            return base_stats
        
        buy_signals = self.get_buy_signals()
        sell_signals = self.get_sell_signals()
        hold_signals = self.get_hold_signals()
        
        base_stats.update({
            'total_signals': len(self.data),
            'buy_signals': len(buy_signals),
            'sell_signals': len(sell_signals),
            'hold_signals': len(hold_signals),
            'average_quantity': self.get_average_quantity(),
            'average_price': self.get_average_price(),
            'average_buy_quantity': self.get_average_quantity('buy'),
            'average_sell_quantity': self.get_average_quantity('sell'),
            'average_buy_price': self.get_average_price('buy'),
            'average_sell_price': self.get_average_price('sell')
        })
        
        return base_stats
