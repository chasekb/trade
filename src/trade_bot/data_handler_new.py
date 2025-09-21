"""New modular data handler using component architecture."""

import logging
from typing import Dict, Any, List, Optional

from .config import TradingConfig
from .data_components import (
    TickerHandler, TradeHandler, SignalHandler, OrderBookHandler, 
    CSVExporter, APIClient
)

logger = logging.getLogger(__name__)


class DataHandler:
    """Modular data handler using component architecture."""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        
        # Initialize component handlers
        self.ticker_handler = TickerHandler(config)
        self.trade_handler = TradeHandler(config)
        self.signal_handler = SignalHandler(config)
        self.orderbook_handler = OrderBookHandler(config)
        self.csv_exporter = CSVExporter(config)
        self.api_client = APIClient(config)
        
        logger.info("DataHandler initialized successfully")
    
    # Ticker Handler Methods
    def add_ticker_data(self, data: Dict[str, Any]) -> None:
        """Add ticker data point."""
        self.ticker_handler.add_ticker_data(data)
    
    def get_latest_ticker(self) -> Optional[Dict[str, Any]]:
        """Get the latest ticker data."""
        return self.ticker_handler.get_latest_ticker()
    
    def get_ticker_by_product(self, product_id: str) -> List[Dict[str, Any]]:
        """Get ticker data for a specific product."""
        return self.ticker_handler.get_ticker_by_product(product_id)
    
    def get_price_history(self, product_id: str = None) -> List[float]:
        """Get price history for a product."""
        return self.ticker_handler.get_price_history(product_id)
    
    def get_volume_history(self, product_id: str = None) -> List[float]:
        """Get volume history for a product."""
        return self.ticker_handler.get_volume_history(product_id)
    
    # Trade Handler Methods
    def add_trade_data(self, trade_info: Dict[str, Any]) -> None:
        """Add trade execution data."""
        self.trade_handler.add_trade_data(trade_info)
    
    def get_latest_trades(self) -> List[Dict[str, Any]]:
        """Get the latest trade data."""
        return self.trade_handler.get_latest_trades()
    
    def get_trades_by_product(self, product_id: str) -> List[Dict[str, Any]]:
        """Get trades for a specific product."""
        return self.trade_handler.get_trades_by_product(product_id)
    
    def get_trades_by_side(self, side: str) -> List[Dict[str, Any]]:
        """Get trades by side (buy/sell)."""
        return self.trade_handler.get_trades_by_side(side)
    
    def get_total_volume(self, product_id: str = None) -> float:
        """Get total volume traded."""
        return self.trade_handler.get_total_volume(product_id)
    
    def get_total_value(self, product_id: str = None) -> float:
        """Get total value traded."""
        return self.trade_handler.get_total_value(product_id)
    
    def get_total_fees(self, product_id: str = None) -> float:
        """Get total fees paid."""
        return self.trade_handler.get_total_fees(product_id)
    
    def get_average_price(self, product_id: str = None) -> float:
        """Get average trade price."""
        return self.trade_handler.get_average_price(product_id)
    
    # Signal Handler Methods
    def add_signal_data(self, signal: Dict[str, Any]) -> None:
        """Add trading signal data."""
        self.signal_handler.add_signal_data(signal)
    
    def get_latest_signal(self) -> Optional[Dict[str, Any]]:
        """Get the latest signal."""
        return self.signal_handler.get_latest_signal()
    
    def get_signals_by_action(self, action: str) -> List[Dict[str, Any]]:
        """Get signals by action (buy/sell/hold)."""
        return self.signal_handler.get_signals_by_action(action)
    
    def get_signals_by_product(self, product_id: str) -> List[Dict[str, Any]]:
        """Get signals for a specific product."""
        return self.signal_handler.get_signals_by_product(product_id)
    
    def get_buy_signals(self) -> List[Dict[str, Any]]:
        """Get all buy signals."""
        return self.signal_handler.get_buy_signals()
    
    def get_sell_signals(self) -> List[Dict[str, Any]]:
        """Get all sell signals."""
        return self.signal_handler.get_sell_signals()
    
    def get_hold_signals(self) -> List[Dict[str, Any]]:
        """Get all hold signals."""
        return self.signal_handler.get_hold_signals()
    
    def get_signal_frequency(self, action: str = None) -> int:
        """Get signal frequency for a specific action or all signals."""
        return self.signal_handler.get_signal_frequency(action)
    
    def get_average_quantity(self, action: str = None) -> float:
        """Get average quantity for signals."""
        return self.signal_handler.get_average_quantity(action)
    
    def get_average_signal_price(self, action: str = None) -> float:
        """Get average price for signals."""
        return self.signal_handler.get_average_price(action)
    
    # Order Book Handler Methods
    def add_level2_data(self, data: Dict[str, Any]) -> None:
        """Add level2 order book data."""
        self.orderbook_handler.add_level2_data(data)
    
    def add_candles_data(self, data: Dict[str, Any]) -> None:
        """Add candles/OHLCV data."""
        self.orderbook_handler.add_candles_data(data)
    
    def add_matches_data(self, data: Dict[str, Any]) -> None:
        """Add matches data."""
        self.orderbook_handler.add_matches_data(data)
    
    def add_status_data(self, data: Dict[str, Any]) -> None:
        """Add product status data."""
        self.orderbook_handler.add_status_data(data)
    
    def add_market_trades_data(self, data: Dict[str, Any]) -> None:
        """Add market trades data."""
        self.orderbook_handler.add_market_trades_data(data)
    
    def get_latest_level2(self) -> Optional[Dict[str, Any]]:
        """Get the latest level2 data."""
        return self.orderbook_handler.get_latest_level2()
    
    def get_latest_candles(self) -> Optional[Dict[str, Any]]:
        """Get the latest candle data."""
        return self.orderbook_handler.get_latest_candles()
    
    def get_latest_matches(self) -> Optional[Dict[str, Any]]:
        """Get the latest match data."""
        return self.orderbook_handler.get_latest_matches()
    
    def get_latest_status(self) -> Optional[Dict[str, Any]]:
        """Get the latest status data."""
        return self.orderbook_handler.get_latest_status()
    
    def get_latest_market_trades(self) -> Optional[Dict[str, Any]]:
        """Get the latest market trade data."""
        return self.orderbook_handler.get_latest_market_trades()
    
    def get_best_bid_ask(self, product_id: str = None) -> Dict[str, float]:
        """Get best bid and ask prices."""
        return self.orderbook_handler.get_best_bid_ask(product_id)
    
    def get_volume_profile(self, product_id: str = None) -> Dict[str, float]:
        """Get volume profile from order book data."""
        return self.orderbook_handler.get_volume_profile(product_id)
    
    # CSV Export Methods
    def save_ticker_data(self) -> str:
        """Save ticker data to CSV."""
        data = self.ticker_handler.get_all_data()
        return self.csv_exporter.export_ticker_data(data)
    
    def save_trade_data(self) -> str:
        """Save trade data to CSV."""
        data = self.trade_handler.get_all_data()
        return self.csv_exporter.export_trade_data(data)
    
    def save_signal_data(self) -> str:
        """Save signal data to CSV."""
        data = self.signal_handler.get_all_data()
        return self.csv_exporter.export_signal_data(data)
    
    def save_level2_data(self) -> str:
        """Save level2 data to CSV."""
        data = self.orderbook_handler.get_all_data()
        return self.csv_exporter.export_level2_data(data)
    
    def save_candles_data(self) -> str:
        """Save candles data to CSV."""
        data = self.orderbook_handler.get_all_data()
        return self.csv_exporter.export_candles_data(data)
    
    def save_matches_data(self) -> str:
        """Save matches data to CSV."""
        data = self.orderbook_handler.get_all_data()
        return self.csv_exporter.export_matches_data(data)
    
    def save_status_data(self) -> str:
        """Save status data to CSV."""
        data = self.orderbook_handler.get_all_data()
        return self.csv_exporter.export_status_data(data)
    
    def save_market_trades_data(self) -> str:
        """Save market trades data to CSV."""
        data = self.orderbook_handler.get_all_data()
        return self.csv_exporter.export_market_trades_data(data)
    
    def save_all_data(self) -> Dict[str, str]:
        """Save all data to CSV files."""
        data_handlers = {
            'ticker': self.ticker_handler,
            'trade': self.trade_handler,
            'signal': self.signal_handler,
            'level2': self.orderbook_handler,
            'candles': self.orderbook_handler,
            'matches': self.orderbook_handler,
            'status': self.orderbook_handler,
            'market_trades': self.orderbook_handler
        }
        return self.csv_exporter.export_all_data(data_handlers)
    
    # Summary Methods
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get comprehensive summary statistics."""
        return {
            'ticker': self.ticker_handler.get_summary_stats(),
            'trade': self.trade_handler.get_summary_stats(),
            'signal': self.signal_handler.get_summary_stats(),
            'orderbook': self.orderbook_handler.get_summary_stats()
        }
