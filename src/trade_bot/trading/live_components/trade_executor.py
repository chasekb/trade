"""Trade execution for live trading."""

import logging
from typing import Dict, Any
from coinbase.rest import RESTClient

from ...core.config import TradingConfig
from ...data.data_components.trade_handler import TradeHandler
from ..diagnostics import StrategyDiagnostics

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
        self.gate_decisions = {"allowed": 0, "blocked": 0}

    async def execute_trade(self, signal: Dict[str, Any]) -> None:
        """Execute a trade using the REST API."""
        try:
            diagnostics = StrategyDiagnostics.from_signal(
                signal, fee_rate=self.config.trading_fee_percentage
            )
            gate = diagnostics.for_action(
                signal.get('action', ''),
                min_confidence=float(signal.get('min_confidence', 0.0)),
                min_expected_return=float(signal.get('min_expected_return', 0.0)),
            )
            if not gate['allowed']:
                self.gate_decisions['blocked'] += 1
                logger.warning(
                    "Live execution blocked by diagnostics: action=%s reasons=%s diagnostics=%s",
                    signal.get('action'), gate['reasons'], diagnostics.as_dict(),
                )
                return
            self.gate_decisions['allowed'] += 1
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

        except Exception as e:
            logger.error(f"Error executing trade: {e}")
