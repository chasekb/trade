"""Trade execution for live trading."""

import logging
from typing import Dict, Any
from coinbase.rest import RESTClient

from ...core.config import TradingConfig
from ...data.data_components.trade_handler import TradeHandler

logger = logging.getLogger(__name__)

class LiveTradeExecutor:
    """Handles trade execution for live trading."""

    def __init__(self, config: TradingConfig, trade_handler: TradeHandler):
        self.config = config
        self.trade_handler = trade_handler
        self.rest_client = RESTClient(
            api_key=config.api_key,
            api_secret=config.api_secret,
        )

    async def execute_trade(self, signal: Dict[str, Any]) -> None:
        """Execute a trade using the REST API."""
        try:
            order = None
            if signal['action'] == 'buy':
                order = self.rest_client.market_order_buy(
                    product_id=signal['product_id'],
                    quote_size=str(signal['quantity'] * signal['price'])
                )
            elif signal['action'] == 'sell':
                order = self.rest_client.market_order_sell(
                    product_id=signal['product_id'],
                    base_size=str(signal['quantity'])
                )
            else:
                logger.warning(f"Unknown signal action: {signal['action']}")
                return

            # Attempt to fetch fee
            fee = 0.0
            order_id = order.get('order_id') if order else None
            status = order.get('status', '') if order else 'unknown'
            
            if order_id:
                try:
                    import asyncio
                    # Poll for fill to get accurate fee
                    for _ in range(5): # Try up to 5 times (5 seconds)
                        await asyncio.sleep(1) 
                        order_details_response = self.rest_client.get_order(order_id)
                        # Response structure: {'order': { ... }}
                        if order_details_response and 'order' in order_details_response:
                            order_info = order_details_response['order']
                            status = order_info.get('status', status)
                            fee = float(order_info.get('total_fees', 0.0))
                            if status == 'FILLED':
                                break
                except Exception as fee_err:
                    logger.warning(f"Failed to retrieve fee for order {order_id}: {fee_err}")

            trade_data = {
                'trade_id': order_id or '',
                'product_id': signal['product_id'],
                'side': signal['action'],
                'price': signal['price'],
                'size': signal['quantity'],
                'value': signal['price'] * signal['quantity'],
                'fee': fee,
                'status': status,
                'order_id': order_id or ''
            }
            self.trade_handler.add_trade_data(trade_data)

        except Exception as e:
            logger.error(f"Error executing trade: {e}")
