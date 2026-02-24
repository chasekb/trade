from typing import List
"""Order Book trading strategy."""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base import BaseStrategy, TradeSignal
from ...core.config import TradingConfig

logger = logging.getLogger(__name__)


class OrderBookStrategy(BaseStrategy):
    """Order Book trading strategy based on order book analysis."""
    
    def __init__(self, config: TradingConfig, min_volume_ratio: float = 2.0, 
                 max_spread_percent: float = 0.1, enable_stop_loss: bool = True, 
                 enable_take_profit: bool = True, order_book_level: int = 2,
                 trade_history_limit: int = 1000, bid_ask_spread_threshold: float = 0.001,
                 volume_imbalance_threshold: float = 0.6, large_trade_threshold: float = 10000.0,
                 data_analysis_mode: str = "recent", recent_data_limit: int = 50,
                 sampling_ratio: float = 0.1):
        super().__init__(config)
        self.min_volume_ratio = min_volume_ratio
        self.max_spread_percent = max_spread_percent
        self.enable_stop_loss = enable_stop_loss
        self.enable_take_profit = enable_take_profit
        
        # Additional parameters for order book analysis
        self.order_book_level = order_book_level
        self.trade_history_limit = trade_history_limit
        self.bid_ask_spread_threshold = bid_ask_spread_threshold
        self.volume_imbalance_threshold = volume_imbalance_threshold
        self.large_trade_threshold = large_trade_threshold
        self.data_analysis_mode = data_analysis_mode
        self.recent_data_limit = recent_data_limit
        self.sampling_ratio = sampling_ratio
        
        # Order book data
        self.bids = []
        self.asks = []
        self.last_order_book_time = None
        
        # Position tracking
        self.entry_price = None
        self.stop_loss_price = None
        self.take_profit_price = None
        
        # Initialize signal tracking
        self.signals_by_type = {
            'order_book_imbalance_buy': 0,
            'order_book_imbalance_sell': 0,
            'large_bid_wall': 0,
            'large_ask_wall': 0,
            'spread_compression': 0,
            'spread_expansion': 0,
            'stop_loss': 0,
            'take_profit': 0
        }
        
    def add_price(self, price: float, timestamp: datetime) -> None:
        """Add a new price point to the history."""
        self.price_history.append(price)
        
        # Keep only recent data to avoid memory issues
        if len(self.price_history) > 1000:
            self.price_history = self.price_history[-1000:]
    
    def update_order_book(self, bids: List[List[float]], asks: List[List[float]], timestamp: datetime) -> None:
        """Update order book data."""
        self.bids = bids
        self.asks = asks
        self.last_order_book_time = timestamp
        
        # Keep only recent data
        if len(self.bids) > 100:
            self.bids = self.bids[-100:]
        if len(self.asks) > 100:
            self.asks = self.asks[-100:]
    
    def calculate_bid_ask_imbalance(self) -> Optional[float]:
        """Calculate bid-ask volume imbalance."""
        if not self.bids or not self.asks:
            return None
        
        # Calculate total bid volume (top 5 levels)
        bid_volume = sum(bid[1] for bid in self.bids[:5] if len(bid) >= 2)
        
        # Calculate total ask volume (top 5 levels)
        ask_volume = sum(ask[1] for ask in self.asks[:5] if len(ask) >= 2)
        
        if ask_volume == 0:
            return None
        
        return bid_volume / ask_volume
    
    def calculate_spread(self) -> Optional[float]:
        """Calculate bid-ask spread."""
        if not self.bids or not self.asks:
            return None
        
        best_bid = self.bids[0][0] if len(self.bids[0]) >= 1 else 0
        best_ask = self.asks[0][0] if len(self.asks[0]) >= 1 else 0
        
        if best_bid == 0 or best_ask == 0:
            return None
        
        return (best_ask - best_bid) / best_bid * 100
    
    def detect_large_walls(self) -> Dict[str, Any]:
        """Detect large bid/ask walls."""
        walls = {'bid_wall': None, 'ask_wall': None}
        
        if not self.bids or not self.asks:
            return walls
        
        # Check for large bid wall (large volume at a single price level)
        for bid in self.bids[:10]:  # Check top 10 bid levels
            if len(bid) >= 2:
                price, volume = bid[0], bid[1]
                if volume > 1000:  # Large volume threshold
                    walls['bid_wall'] = {'price': price, 'volume': volume}
                    break
        
        # Check for large ask wall (large volume at a single price level)
        for ask in self.asks[:10]:  # Check top 10 ask levels
            if len(ask) >= 2:
                price, volume = ask[0], bid[1]
                if volume > 1000:  # Large volume threshold
                    walls['ask_wall'] = {'price': price, 'volume': volume}
                    break
        
        return walls
    
    def generate_signal(self, current_price: float, timestamp: datetime, is_end_of_period: bool = False) -> Optional[TradeSignal]:
        """Generate trading signal based on order book analysis."""
        if not self.bids or not self.asks:
            return None
        
        # Calculate order book metrics
        imbalance = self.calculate_bid_ask_imbalance()
        spread = self.calculate_spread()
        walls = self.detect_large_walls()
        
        if imbalance is None or spread is None:
            return None
        
        # Check for bid-ask imbalance signals
        if imbalance > self.min_volume_ratio:
            # Calculate strength based on how much imbalance exceeds threshold
            # Normalize to 0.0-1.0 range
            excess = imbalance - self.min_volume_ratio
            strength = min(excess / self.min_volume_ratio, 1.0)
            
            self.signals_by_type['order_book_imbalance_buy'] += 1
            return TradeSignal(
                action='buy',
                price=current_price,
                quantity=self.calculate_position_size(current_price),
                reason=f'Order book imbalance: {imbalance:.2f} (bids > asks)',
                timestamp=timestamp,
                strength=strength
            )
        elif imbalance < (1 / self.min_volume_ratio):
            # Calculate strength based on how much imbalance exceeds threshold (inverse)
            # Normalize to 0.0-1.0 range
            ratio = 1 / imbalance
            excess = ratio - self.min_volume_ratio
            strength = min(excess / self.min_volume_ratio, 1.0)
            
            self.signals_by_type['order_book_imbalance_sell'] += 1
            return TradeSignal(
                action='sell',
                price=current_price,
                quantity=self.calculate_position_size(current_price),
                reason=f'Order book imbalance: {imbalance:.2f} (asks > bids)',
                timestamp=timestamp,
                strength=strength
            )
        
        # Check for large walls
        if walls['bid_wall']:
            # Calculate strength based on wall size relative to threshold
            # Normalize to 0.0-1.0 range
            wall_size = walls['bid_wall']['volume']
            strength = min(wall_size / self.large_trade_threshold, 1.0)
            
            self.signals_by_type['large_bid_wall'] += 1
            return TradeSignal(
                action='buy',
                price=current_price,
                quantity=self.calculate_position_size(current_price),
                reason=f'Large bid wall detected: {walls["bid_wall"]["volume"]} at ${walls["bid_wall"]["price"]:.2f}',
                timestamp=timestamp,
                strength=strength
            )
        
        if walls['ask_wall']:
            # Calculate strength based on wall size relative to threshold
            # Normalize to 0.0-1.0 range
            wall_size = walls['ask_wall']['volume']
            strength = min(wall_size / self.large_trade_threshold, 1.0)
            
            self.signals_by_type['large_ask_wall'] += 1
            return TradeSignal(
                action='sell',
                price=current_price,
                quantity=self.calculate_position_size(current_price),
                reason=f'Large ask wall detected: {walls["ask_wall"]["volume"]} at ${walls["ask_wall"]["price"]:.2f}',
                timestamp=timestamp,
                strength=strength
            )
        
        # Check for spread compression (potential breakout)
        if spread < self.max_spread_percent:
            self.signals_by_type['spread_compression'] += 1
            # Could generate a signal here, but for now just track it
        else:
            self.signals_by_type['spread_expansion'] += 1
        
        return None
    
    def get_strategy_name(self) -> str:
        """Get the name of this strategy."""
        return "Order Book"
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Get strategy information and statistics."""
        imbalance = self.calculate_bid_ask_imbalance()
        spread = self.calculate_spread()
        walls = self.detect_large_walls()
        
        return {
            'strategy_name': 'Order Book',
            'parameters': {
                'min_volume_ratio': self.min_volume_ratio,
                'max_spread_percent': self.max_spread_percent,
                'enable_stop_loss': self.enable_stop_loss,
                'enable_take_profit': self.enable_take_profit,
                'order_book_level': self.order_book_level,
                'trade_history_limit': self.trade_history_limit,
                'bid_ask_spread_threshold': self.bid_ask_spread_threshold,
                'volume_imbalance_threshold': self.volume_imbalance_threshold,
                'large_trade_threshold': self.large_trade_threshold,
                'data_analysis_mode': self.data_analysis_mode,
                'recent_data_limit': self.recent_data_limit,
                'sampling_ratio': self.sampling_ratio
            },
            'current_values': {
                'bid_ask_imbalance': imbalance,
                'spread_percent': spread,
                'large_walls': walls,
                'bid_levels': len(self.bids),
                'ask_levels': len(self.asks)
            },
            'signals_by_type': self.signals_by_type.copy(),
            'total_signals': sum(self.signals_by_type.values()),
            'no_signal_count': self.no_signal_count
        }
