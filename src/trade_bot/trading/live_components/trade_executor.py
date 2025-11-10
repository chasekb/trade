"""Trade execution for live trading."""

import logging
from typing import Dict, Any
from coinbase.rest import RESTClient
from coinbase.rest.api_error import ApiError

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
            if signal['action'] == 'buy':
                order = self.rest_client.market_order_buy(
                    product_id=signal['product_id'],
                    quote_size=signal['quantity'] * signal['price']
                )
            elif signal['action'] == 'sell':
                order = self.rest_client.market_order_sell(
                    product_id=signal['product_id'],
                    base_size=signal['quantity']
                )
            else:
                logger.warning(f"Unknown signal action: {signal['action']}")
                return

            trade_data = {
                'trade_id': order.get('order_id', ''),
                'product_id': signal['product_id'],
                'side': signal['action'],
                'price': signal['price'],
                'size': signal['quantity'],
                'value': signal['price'] * signal['quantity'],
                'fee': 0.0,  # Would be calculated from order response
                'status': order.get('status', ''),
                'order_id': order.get('order_id', '')
            }
            self.trade_handler.add_trade_data(trade_data)

        except ApiError as e:
            logger.error(f"API error executing trade: {e}")
        except Exception as e:
            logger.error(f"Error executing trade: {e}")
