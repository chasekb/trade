"""Main trading bot implementation."""

import asyncio
import logging
from typing import Dict, Any
from datetime import datetime
import json

from coinbase.rest import RESTClient

from ..core.config import TradingConfig
from ..data.websocket_client import WebSocketClient
from ..trading.trading_strategy import SimpleMovingAverageStrategy, TradeSignal
from ..data.data_handler import DataHandler


logger = logging.getLogger(__name__)


class TradingBot:
    """Main trading bot class."""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.config.validate()
        
        # Initialize components
        self.rest_client = RESTClient(
            api_key=config.api_key,
            api_secret=config.api_secret,
            api_passphrase=config.passphrase
        )
        
        self.websocket_client = WebSocketClient(config)
        self.strategy = SimpleMovingAverageStrategy(config)
        self.data_handler = DataHandler(config)
        
        # Register message handlers
        self.websocket_client.register_handler("ticker", self._handle_ticker)
        self.websocket_client.register_handler("l2update", self._handle_level2)
        
        # Bot state
        self.running = False
        self.current_price = 0.0
        
    async def _handle_ticker(self, data: Dict[str, Any]) -> None:
        """Handle ticker updates."""
        try:
            if 'price' in data:
                self.current_price = float(data['price'])
                self.data_handler.add_ticker_data(data)
                
                # Generate trading signal
                signal = self.strategy.generate_signal(
                    self.current_price, 
                    datetime.now()
                )
                
                if signal:
                    await self._process_signal(signal)
                    
        except Exception as e:
            logger.error(f"Error handling ticker data: {e}")
    
    async def _handle_level2(self, data: Dict[str, Any]) -> None:
        """Handle level2 order book updates."""
        try:
            logger.debug(f"Level2 update: {data}")
            # Could implement order book analysis here
        except Exception as e:
            logger.error(f"Error handling level2 data: {e}")
    
    async def _process_signal(self, signal: TradeSignal) -> None:
        """Process a trading signal."""
        try:
            # Log the signal
            signal_data = {
                'timestamp': signal.timestamp.isoformat(),
                'action': signal.action,
                'price': signal.price,
                'quantity': signal.quantity,
                'reason': signal.reason,
                'product_id': self.config.product_id
            }
            self.data_handler.add_signal_data(signal_data)
            
            # In a real implementation, you would execute the trade here
            # For now, we'll just log it and update the strategy position
            logger.info(f"Processing signal: {signal.action} {signal.quantity} at {signal.price}")
            
            # Update strategy position (simulated)
            self.strategy.update_position(signal)
            
            # In a real bot, you would call the REST API to place orders
            await self._execute_trade(signal)
            
        except Exception as e:
            logger.error(f"Error processing signal: {e}")
    
    async def _execute_trade(self, signal: TradeSignal) -> None:
        """Execute a trade using the REST API."""
        try:
            # Delegate to trade executor if available
            if self.trade_executor:
                signal_dict = {
                    'action': signal.action,
                    'product_id': self.config.product_id,
                    'quantity': signal.quantity,
                    'price': signal.price
                }
                await self.trade_executor.execute_trade(signal_dict)
                return

            # Fallback internal implementation
            if signal.action == 'buy':
                order = self.rest_client.market_order_buy(
                    product_id=self.config.product_id,
                    quote_size=signal.quantity * signal.price
                )
            elif signal.action == 'sell':
                order = self.rest_client.market_order_sell(
                    product_id=self.config.product_id,
                    base_size=signal.quantity
                )
            else:
                logger.warning(f"Unknown signal action: {signal.action}")
                return
            
            # Log the trade
            trade_data = {
                'trade_id': order.get('order_id', ''),
                'product_id': self.config.product_id,
                'side': signal.action,
                'price': signal.price,
                'size': signal.quantity,
                'value': signal.price * signal.quantity,
                'fee': 0.0,  # Would be calculated from order response
                'status': order.get('status', ''),
                'order_id': order.get('order_id', '')
            }
            self.data_handler.add_trade_data(trade_data)
            
        except Exception as e:
            logger.error(f"Error executing trade: {e}")
    
    async def start(self) -> None:
        """Start the trading bot."""
        logger.info("Starting trading bot...")
        self.running = True
        
        try:
            # Start WebSocket client
            await self.websocket_client.run()
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        except Exception as e:
            logger.error(f"Error in trading bot: {e}")
        finally:
            await self.stop()
    
    async def stop(self) -> None:
        """Stop the trading bot."""
        logger.info("Stopping trading bot...")
        self.running = False
        
        # Save all data
        files = self.data_handler.save_all_data()
        logger.info(f"Saved data files: {files}")
        
        # Get final statistics
        stats = self.data_handler.get_summary_stats()
        logger.info(f"Final statistics: {stats}")
        
        # Disconnect WebSocket
        await self.websocket_client.disconnect()
    
    def get_status(self) -> Dict[str, Any]:
        """Get current bot status."""
        position_info = self.strategy.get_position_info()
        stats = self.data_handler.get_summary_stats()
        
        return {
            'running': self.running,
            'current_price': self.current_price,
            'position': position_info,
            'statistics': stats
        }
