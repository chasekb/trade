"""
Simulated Trading Manager for Live Order Book Signals.

This module handles simulated trading based on live order book signals,
including position tracking, portfolio management, and trade execution.
"""

import asyncio
import logging
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import asdict

from .trading_models import Position, Trade, Portfolio
from .strategies.ml_enhanced_orderbook import MLEnhancedOrderBookStrategy
from .strategies.orderbook import OrderBookStrategy
from trade_bot.ml.model_manager import ModelManager

logger = logging.getLogger(__name__)


class SimulatedTradingManager:
    """Manages simulated trading based on live order book signals."""
    
    def __init__(self, initial_balance: float = 10000.0, max_positions: int = 5, 
                 position_size_percent: float = 20.0, trading_fee: float = 0.001,
                 db_manager=None, session_id: str = None, model_manager: ModelManager = None, config=None):
        self.initial_balance = initial_balance
        self.config = config
        self.model_manager = model_manager
        self.max_positions = max_positions
        self.position_size_percent = position_size_percent / 100.0  # Convert to decimal
        self.trading_fee = trading_fee
        
        # Database and session
        self.db_manager = db_manager
        self.session_id = session_id
        
        # Portfolio state
        self.cash_balance = initial_balance
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.trade_counter = 0
        
        # Performance tracking
        self.peak_value = initial_balance
        self.max_drawdown = 0.0
        
        # Trading state
        self.is_trading = False
        self.symbols_to_trade: List[str] = []
        self.last_signal_check = None
        
        # Signal tracking
        self.total_signals_processed = 0
        # Statistics for signal-to-trade conversion analysis
        self.signal_to_trade_statistics = {
            'total_signals_above_threshold': 0,
            'successful_trades': 0,
            'filtered_signals': {
                'symbol_not_trading': 0,
                'hold_signal': 0,
                'already_have_position': 0,
                'max_positions_exceeded': 0,
                'insufficient_cash': 0,
                'insufficient_quantity': 0,
                'portfolio_restrictions': 0,
                'other_reasons': 0
            }
        }
        
        # Position price update rate limiting
        self.last_position_update = None
        self.position_update_interval = 5  # Update position prices every 5 seconds
        
        # Strategy information
        self.strategy_type = None
        self.strategy_params = {}
        self.strategy_instance = None
        
        logger.info(f"SimulatedTradingManager initialized with ${initial_balance:,.2f} balance")
    
    def set_session_info(self, db_manager, session_id: str) -> None:
        """Set database manager and session ID for trade logging."""
        self.db_manager = db_manager
        self.session_id = session_id

        # Create the session in the database if it doesn't exist
        try:
            session_data = {
                'is_active': True,
                'trading_mode': 'simulated',
                'symbol_mode': 'manual',
                'strategy_type': getattr(self, 'strategy_type', 'orderbook'),
                'strategy_params': getattr(self, 'strategy_params', {}),
                'symbols': getattr(self, 'symbols_to_trade', []),
                'universe_config': {},
                'portfolio_state': {
                    'cash_balance': self.cash_balance,
                    'total_value': self.cash_balance,
                    'max_drawdown': self.max_drawdown
                },
                'positions': {},
                'recent_trades': []
            }
            if self.db_manager:
                success = self.db_manager.save_trading_session(session_id, session_data)
                if success:
                    logger.info(f"Session created in database: {session_id}")
                else:
                    logger.warning(f"Failed to create session in database: {session_id}")
        except Exception as e:
            logger.error(f"Error creating session in database: {e}")

        logger.info(f"Session info set: {session_id}")
    
    def set_strategy_info(self, strategy_type: str, strategy_params: Dict[str, Any]) -> None:
        """Set strategy type and parameters for trade logging."""
        self.strategy_type = strategy_type
        self.strategy_params = strategy_params
        
        # Instantiate the strategy if config is available
        if self.config:
            try:
                if strategy_type == 'ml_enhanced_orderbook':
                    # Determine ML server URL from config or params
                    default_ml_url = "http://ml-server:8002"
                    if self.config:
                        host = getattr(self.config, 'ml_server_host', 'ml-server')
                        port = getattr(self.config, 'ml_server_port', 8002)
                        default_ml_url = f"http://{host}:{port}"
                    
                    self.strategy_instance = MLEnhancedOrderBookStrategy(
                        self.config,
                        ml_server_url=strategy_params.get('ml_server_url', default_ml_url),
                        fallback_to_baseline=strategy_params.get('fallback_to_baseline', True),
                        confidence_threshold=float(strategy_params.get('confidence_threshold', 0.6))
                    )
                    logger.info(f"Instantiated MLEnhancedOrderBookStrategy with ML server: {strategy_params.get('ml_server_url', default_ml_url)}")
                elif strategy_type == 'orderbook':
                    self.strategy_instance = OrderBookStrategy(self.config)
                    logger.info("Instantiated OrderBookStrategy")
                else:
                    self.strategy_instance = None
                    logger.warning(f"Unknown strategy type: {strategy_type}")
            except Exception as e:
                logger.error(f"Failed to instantiate strategy {strategy_type}: {e}")
                self.strategy_instance = None
        else:
            logger.warning("Config not available, cannot instantiate strategy")
            
        logger.info(f"Strategy info set: {strategy_type} with params: {strategy_params}")

    def generate_signal(self, symbol: str, current_price: float, timestamp: datetime, orderbook_data: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """Generate a signal using the active strategy."""
        if not self.strategy_instance:
            return None
            
        try:
            # Update strategy with latest order book data if available
            if orderbook_data:
                bids = [[float(b['price']), float(b['size'])] for b in orderbook_data.get('bids', [])]
                asks = [[float(a['price']), float(a['size'])] for a in orderbook_data.get('asks', [])]
                self.strategy_instance.update_order_book(bids, asks, timestamp)
            
            # Generate signal
            trade_signal = self.strategy_instance.generate_signal(current_price, timestamp)
            
            if trade_signal:
                # Convert TradeSignal to dictionary format expected by the system
                signal_dict = {
                    "symbol": symbol,
                    "signal": trade_signal.action,
                    "signal_type": trade_signal.action,
                    "signal_strength": getattr(trade_signal, 'strength', 0.5) if trade_signal.action != 'hold' else 0.0,
                    "strength": getattr(trade_signal, 'strength', 0.5) if trade_signal.action != 'hold' else 0.0,
                    "price": trade_signal.price,
                    "timestamp": trade_signal.timestamp.isoformat(),
                    "reason": trade_signal.reason,
                    "signal_reason": trade_signal.reason,
                    "signal_generated": trade_signal.action != 'hold'
                }
                
                # Add ML metadata if available
                if hasattr(self.strategy_instance, 'ml_predictions') and self.strategy_instance.ml_predictions:
                    last_prediction = self.strategy_instance.ml_predictions[-1]
                    # Check if this prediction corresponds to the current signal
                    if last_prediction['timestamp'] == timestamp:
                        signal_dict['win_probability'] = last_prediction.get('win_probability', 50.0)
                        signal_dict['expected_return'] = last_prediction.get('expected_return_percentage', 0.0)
                        signal_dict['model_confidence'] = last_prediction.get('confidence', 0.0)
                        
                        # Also add to ml_analysis structure for consistency
                        signal_dict['ml_analysis'] = {
                            "ml_enabled": True,
                            "win_probability": last_prediction.get('win_probability', 50.0),
                            "expected_return": last_prediction.get('expected_return_percentage', 0.0),
                            "confidence": last_prediction.get('confidence', 0.0),
                            "reason": trade_signal.reason,
                            "analytics": last_prediction.get('analytics', {})
                        }
                
                return signal_dict
            
            return None
            
        except Exception as e:
            logger.error(f"Error generating signal in strategy: {e}")
            return None

    def update_strategy_parameters(self, new_params: Dict[str, Any]) -> None:
        """Update strategy parameters during an active session."""
        if not self.is_trading:
            logger.warning("Cannot update strategy parameters: trading is not active.")
            return

        # Merge new parameters with existing ones
        self.strategy_params.update(new_params)
        logger.info(f"Updated strategy parameters: {self.strategy_params}")

        # If a websocket manager is available, notify it of the change
        websocket_manager = getattr(self, '_websocket_manager', None)
        if websocket_manager:
            try:
                asyncio.create_task(
                    websocket_manager.broadcast(json.dumps({
                        "type": "strategy_parameter_update",
                        "data": {"strategy_params": self.strategy_params}
                    }))
                )
                logger.info("Broadcasted strategy parameter update to WebSocket clients.")
            except Exception as e:
                logger.error(f"Failed to broadcast strategy parameter update: {e}")
    
    def restore_portfolio_state(self, portfolio_state: Dict[str, Any], positions: List[Dict[str, Any]], 
                               trades: List[Dict[str, Any]], symbols: List[str]) -> None:
        """Restore portfolio state from saved session data."""
        try:
            # Restore portfolio state
            self.cash_balance = portfolio_state.get('cash_balance', self.initial_balance)
            self.peak_value = portfolio_state.get('total_value', self.initial_balance)
            self.max_drawdown = portfolio_state.get('max_drawdown', 0.0)
            
            # Restore positions (respecting max positions limit)
            self.positions = {}
            open_positions_count = 0
            for pos_data in positions:
                if isinstance(pos_data, dict) and 'symbol' in pos_data:
                    # Convert entry_time string to datetime if needed
                    entry_time = pos_data.get('entry_time', '')
                    if isinstance(entry_time, str) and entry_time:
                        try:
                            entry_time = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Failed to parse entry_time '{entry_time}': {e}")
                            entry_time = datetime.now(timezone.utc)
                    elif not entry_time:
                        entry_time = datetime.now(timezone.utc)
                    
                    position = Position(
                        symbol=pos_data['symbol'],
                        side=pos_data.get('side', 'long'),
                        quantity=float(pos_data.get('quantity', 0.0)),
                        entry_price=float(pos_data.get('entry_price', 0.0)),
                        entry_time=entry_time,
                        current_price=float(pos_data.get('current_price', 0.0)),
                        unrealized_pnl=float(pos_data.get('unrealized_pnl', 0.0)),
                        status=pos_data.get('status', 'open')  # Restore position status
                    )
                    
                    # Only count open positions towards the limit
                    if position.status == 'open':
                        if open_positions_count >= self.max_positions:
                            logger.warning(f"Max positions limit ({self.max_positions}) reached, skipping restoration of {pos_data['symbol']}")
                            continue
                        open_positions_count += 1
                    
                    self.positions[position.symbol] = position
            
            # Restore trades
            self.trades = []
            for trade_data in trades:
                if isinstance(trade_data, dict) and 'symbol' in trade_data:
                    trade = Trade(
                        trade_id=trade_data.get('trade_id', ''),
                        symbol=trade_data['symbol'],
                        side=trade_data.get('side', 'buy'),
                        quantity=float(trade_data.get('quantity', 0.0)),
                        price=float(trade_data.get('price', 0.0)),
                        pnl=float(trade_data.get('pnl', 0.0)),
                        fees=float(trade_data.get('fees', 0.0)),
                        timestamp=trade_data.get('timestamp', ''),
                        reason=trade_data.get('reason', '')
                    )
                    self.trades.append(trade)
            
            # Restore symbols
            self.symbols_to_trade = symbols.copy()
            
            # Update trade counter
            self.trade_counter = len(self.trades)
            
            logger.info(f"Restored portfolio state: ${self.cash_balance:,.2f} cash, {len(self.positions)} positions, {len(self.trades)} trades")
            
        except Exception as e:
            logger.error(f"Error restoring portfolio state: {e}")
            self.reset_portfolio()
    
    def _save_trade_to_db(self, trade: Trade) -> None:
        """Save trade to database if db_manager is available."""
        if self.db_manager and self.session_id:
            try:
                trade_data = {
                    'trade_id': trade.trade_id,
                    'session_id': self.session_id,
                    'symbol': trade.symbol,
                    'side': trade.side,
                    'quantity': trade.quantity,
                    'size': trade.quantity,
                    'price': trade.price,
                    'timestamp': int(trade.timestamp.timestamp()),
                    'reason': trade.reason,
                    'pnl': trade.pnl,
                    'fees': trade.fees,
                    'strategy_type': self.strategy_type,
                    'strategy_params': self.strategy_params,
                    'trade_type': 'simulated',
                    'win_probability': trade.win_probability,
                    'expected_return': trade.expected_return,
                    'model_confidence': trade.model_confidence
                }
                self.db_manager.save_trade(trade_data)
            except Exception as e:
                logger.error(f"Failed to save trade to database: {e}")
    
    def start_trading(self, symbols: List[str], position_size_percent: float = None, max_positions: int = None) -> None:
        """Start simulated trading for specified symbols."""
        self.symbols_to_trade = symbols
        self.is_trading = True
        self.last_signal_check = datetime.now(timezone.utc)
        
        # Update position size and max positions if provided
        if position_size_percent is not None:
            self.position_size_percent = position_size_percent / 100.0  # Convert to decimal
            logger.info(f"Updated position size to {position_size_percent}%")
        
        if max_positions is not None:
            self.max_positions = max_positions
            logger.info(f"Updated max positions to {max_positions}")
        
        # Enforce max positions limit on existing positions
        self._enforce_max_positions_limit()
        
        logger.info(f"Started simulated trading for symbols: {symbols}")
    
    def stop_trading(self) -> None:
        """Stop simulated trading and close all positions."""
        self.is_trading = False
        
        # Close all open positions
        for symbol, position in list(self.positions.items()):
            if position.status == 'open':
                self._close_position(symbol, "Trading stopped")
        
        logger.info("Stopped simulated trading")
    
    def _enforce_max_positions_limit(self) -> None:
        """Enforce max positions limit by closing excess positions."""
        open_positions = [symbol for symbol, pos in self.positions.items() if pos.status == 'open']
        
        if len(open_positions) > self.max_positions:
            logger.warning(f"Found {len(open_positions)} open positions, but max is {self.max_positions}. Closing excess positions.")
            
            # Close excess positions (keep the most recent ones)
            excess_count = len(open_positions) - self.max_positions
            positions_to_close = open_positions[:excess_count]  # Close oldest positions first
            
            for symbol in positions_to_close:
                self._close_position(symbol, f"Max positions limit enforced (closing excess position)")
                logger.info(f"Closed excess position: {symbol}")
    
    def _update_all_position_prices(self) -> None:
        """Update all position prices with current market data."""
        try:
            # Rate limiting: only update if enough time has passed
            now = datetime.now(timezone.utc)
            if (self.last_position_update and 
                (now - self.last_position_update).total_seconds() < self.position_update_interval):
                return  # Skip update if too soon
            
            # Import here to avoid circular imports
            from ..data.data_provider import CoinbaseDataProvider
            
            async def update_prices():
                # Create a copy of positions to avoid dictionary changed size during iteration
                positions_copy = dict(self.positions)
                open_positions = [pos for pos in positions_copy.values() if pos.status == 'open']
                
                if not open_positions:
                    return  # No open positions to update
                
                logger.debug(f"Updating prices for {len(open_positions)} open positions using level 1 data")
                
                for symbol, position in positions_copy.items():
                    if position.status == 'open':
                        try:
                            # Create a data provider for this symbol
                            data_provider = CoinbaseDataProvider(symbol)
                            
                            # Get current orderbook data to extract current price
                            orderbook_data = await data_provider.get_order_book(level=1)
                            
                            if orderbook_data and 'bids' in orderbook_data and 'asks' in orderbook_data:
                                bids = orderbook_data['bids']
                                asks = orderbook_data['asks']
                                
                                if bids and asks:
                                    # Calculate current price as midpoint between best bid and ask
                                    best_bid = float(bids[0]['price']) if bids else 0
                                    best_ask = float(asks[0]['price']) if asks else 0
                                    current_price = (best_bid + best_ask) / 2
                                    
                                    if current_price > 0:
                                        position.update_price(current_price)
                                        logger.debug(f"Updated {symbol} price from {position.entry_price} to {current_price}")
                                    else:
                                        logger.warning(f"Invalid price for {symbol}: {current_price}")
                        except Exception as e:
                            logger.warning(f"Error updating price for {symbol}: {e}")
                            continue
            
            # Check if we're already in an event loop
            try:
                loop = asyncio.get_running_loop()
                # We're in an event loop, create a task
                loop.create_task(update_prices())
            except RuntimeError:
                # No event loop running, we can use asyncio.run()
                asyncio.run(update_prices())
            
            # Update the last update timestamp
            self.last_position_update = now
            
        except Exception as e:
            logger.error(f"Error updating position prices: {e}")
    
    def get_portfolio_summary(self) -> Portfolio:
        """Get current portfolio summary."""
        # Update all position prices with current market data
        self._update_all_position_prices()
        
        total_value = self.cash_balance
        unrealized_pnl = 0.0
        total_fees = sum(trade.fees for trade in self.trades)
        # Only count completed trades (SELL) for win metrics
        completed_trades = [t for t in self.trades if t.side == 'sell']
        winning_trades = sum(1 for trade in completed_trades if trade.pnl > 0)
        
        # Calculate total value including open positions
        total_positions_value = 0.0
        open_position_count = 0
        for position in self.positions.values():
            if position.status == 'open':
                pos_val = position.quantity * position.current_price
                total_positions_value += pos_val
                total_value += pos_val
                unrealized_pnl += position.unrealized_pnl
                open_position_count += 1
        
        # Realized PnL is the sum of SELL trade PnL (already net of fees in _execute_sell_trade)
        realized_pnl = sum(trade.pnl for trade in completed_trades)
        # Total PnL (gross) = realized + unrealized
        total_pnl = unrealized_pnl + realized_pnl
        net_pnl = total_pnl  # keep net_pnl explicit
        
        # Calculate win rate using only completed trades
        total_trades = len(completed_trades)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
        
        # Update peak value and max drawdown
        if total_value > self.peak_value:
            self.peak_value = total_value
        else:
            current_drawdown = (self.peak_value - total_value) / self.peak_value
            self.max_drawdown = max(self.max_drawdown, current_drawdown)
        
        return Portfolio(
            cash_balance=self.cash_balance,
            total_value=total_value,
            positions=self.positions.copy(),
            trades=self.trades.copy(),
            total_pnl=total_pnl,
            total_fees=total_fees,
            max_drawdown=self.max_drawdown,
            win_rate=win_rate,
            total_trades=total_trades,
            winning_trades=winning_trades,
            total_positions_value=total_positions_value,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=realized_pnl,
            net_pnl=net_pnl,
            position_count=open_position_count
        )
    
    def _should_process_signal(self, signal: Dict[str, Any]) -> bool:
        """
        Determine if a signal should be processed based on trading rules and filters.
        Updates signal_to_trade_statistics accordingly.
        """
        symbol = signal.get('symbol')
        signal_generated = signal.get('signal_generated', False)
        signal_action = signal.get('signal')
        model_confidence = signal.get('model_confidence', 0.0)
        confidence_threshold = self.strategy_params.get('confidence_threshold', 0.6)

        # Track signals above confidence threshold
        if signal_generated and model_confidence >= confidence_threshold:
            self.signal_to_trade_statistics['total_signals_above_threshold'] += 1

        # Filter: Symbol not in trading symbols
        if symbol not in self.symbols_to_trade:
            logger.info(f"Skipping {symbol} - not in trading symbols")
            if signal_generated and model_confidence >= confidence_threshold:
                self.signal_to_trade_statistics['filtered_signals']['symbol_not_trading'] += 1
            return False

        # Filter: Hold signal or not generated
        if not signal_generated or signal_action == 'hold':
            if signal_generated and model_confidence >= confidence_threshold and signal_action == 'hold':
                self.signal_to_trade_statistics['filtered_signals']['hold_signal'] += 1
            return False

        return True

    async def process_signals(self, signals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process live order book signals and execute trades."""
        if not self.is_trading:
            return {"status": "not_trading", "message": "Trading is not active"}
        
        # Enforce max positions limit before processing signals
        self._enforce_max_positions_limit()
        
        # Update total signals processed counter
        self.total_signals_processed += len(signals)
        
        # Check if we have signals for all symbols in the universe
        # Only if we have symbols configured AND prioritization is not 'none'
        prioritization = self.strategy_params.get('order_prioritization', 'signal_strength')
        
        if self.symbols_to_trade and prioritization != 'none':
            # Create a set of symbols present in the signals list
            received_symbols = set(s.get('symbol') for s in signals if s.get('symbol'))
            missing_symbols = [s for s in self.symbols_to_trade if s not in received_symbols]
            
            if missing_symbols:
                logger.info(f"Waiting for all signals. Missing: {len(missing_symbols)}/{len(self.symbols_to_trade)}. Present: {len(received_symbols)}")
                # Broadcast anyway so UI updates with what we have
                for signal in signals:
                    self._broadcast_signal(signal)
                return {
                    "status": "waiting", 
                    "message": f"Waiting for all signals ({len(received_symbols)}/{len(self.symbols_to_trade)})",
                    "executed_trades": 0,
                    "closed_positions": 0,
                    "trades": [],
                    "portfolio": self.get_portfolio_summary()
                }
        
        logger.info(f"Processing {len(signals)} signals. Total processed: {self.total_signals_processed}. Trading symbols: {self.symbols_to_trade}")
        
        executed_trades = []
        closed_positions = []
        
        # Filter for executable signals
        executable_signals = []
        for signal in signals:
            symbol = signal.get('symbol')
            # Broadcast signal immediately via WebSocket for real-time frontend updates
            self._broadcast_signal(signal)

            if self._should_process_signal(signal):
                executable_signals.append(signal)
        
        # Sort signals based on prioritization
        def get_sort_key(signal):
            if prioritization == 'win_probability':
                return float(signal.get('win_probability', 0.0))
            elif prioritization == 'expected_return':
                return float(signal.get('expected_return', 0.0))
            else: # signal_strength
                return float(signal.get('signal_strength', 0.0))

        # Sort descending if prioritization is not 'none'
        if executable_signals and prioritization != 'none':
            executable_signals.sort(key=get_sort_key, reverse=True)
            logger.info(f"Prioritizing {len(executable_signals)} signals by {prioritization}")
        elif prioritization == 'none':
            logger.info(f"Processing {len(executable_signals)} signals without prioritization (immediate execution)")

        # Execute trades
        for signal in executable_signals:
            symbol = signal.get('symbol')
            current_price = signal.get('price', 0.0)
            signal_action = signal.get('signal')
            signal_strength = signal.get('signal_strength', 0.0)
            
            # Update existing position price
            if symbol in self.positions and self.positions[symbol].status == 'open':
                self.positions[symbol].update_price(current_price)
            
            # Dispatch signal to appropriate handler
            if signal_action == 'buy':
                logger.info(f"Processing buy signal for {symbol} at ${current_price}")
                trade_result = await self._process_buy_signal(symbol, current_price, signal_strength, signal)
                if trade_result:
                    executed_trades.append(trade_result)
            
            elif signal_action == 'sell':
                logger.info(f"Processing sell signal for {symbol} at ${current_price}")
                trade_result = await self._process_sell_signal(symbol, current_price, signal_strength, signal)
                if trade_result:
                    executed_trades.append(trade_result)
                    if symbol in self.positions and self.positions[symbol].status == 'closed':
                        closed_positions.append(symbol)
        
        self.last_signal_check = datetime.now(timezone.utc)
        
        return {
            "status": "processed",
            "executed_trades": len(executed_trades),
            "closed_positions": len(closed_positions),
            "trades": executed_trades,
            "portfolio": self.get_portfolio_summary()
        }
    
    def _calculate_position_size(self, symbol: str, price: float, model_confidence: float, confidence_threshold: float) -> Optional[float]:
        """Calculate position size based on strategy parameters and available cash."""
        # Check if we already have a position
        if symbol in self.positions and self.positions[symbol].status == 'open':
            logger.info(f"Skipping buy for {symbol}: Already have open position")
            if model_confidence >= confidence_threshold:
                self.signal_to_trade_statistics['filtered_signals']['already_have_position'] += 1
            return None

        # Check if we have reached max positions
        open_positions = sum(1 for p in self.positions.values() if p.status == 'open')
        if open_positions >= self.max_positions:
            logger.info(f"Skipping buy for {symbol}: Max positions ({self.max_positions}) reached")
            if model_confidence >= confidence_threshold:
                self.signal_to_trade_statistics['filtered_signals']['max_positions_exceeded'] += 1
            return None
        
        # Get position sizing configuration
        position_size_mode = self.strategy_params.get('position_size_mode', 'percent')
        position_size_value = self.strategy_params.get('position_size_value')

        if position_size_value is None:
            position_size_value = self.position_size_percent * 100
        
        total_portfolio_value = self.cash_balance + sum(
            pos.quantity * pos.current_price for pos in self.positions.values() 
            if pos.status == 'open'
        )

        if position_size_mode == 'percent':
            position_value = total_portfolio_value * (float(position_size_value) / 100.0)
        elif position_size_mode == 'dollar':
            position_value = float(position_size_value)
        else:
            position_value = total_portfolio_value * self.position_size_percent

        quantity = position_value / price if price > 0 else 0

        if quantity < 0.001:
            logger.warning(f"Insufficient quantity for {symbol} position: {quantity:.6f} < 0.001")
            if model_confidence >= confidence_threshold:
                self.signal_to_trade_statistics['filtered_signals']['insufficient_quantity'] += 1
            return None
            
        return quantity

    async def _process_buy_signal(self, symbol: str, price: float, strength: float, signal: Dict) -> Optional[Dict]:
        """Process a buy signal."""
        model_confidence = signal.get('model_confidence', 0.0)
        confidence_threshold = self.strategy_params.get('confidence_threshold', 0.6)

        quantity = self._calculate_position_size(symbol, price, model_confidence, confidence_threshold)
        if quantity is None:
            return None

        # Calculate fees and cost
        fees = price * quantity * self.trading_fee
        total_cost = (price * quantity) + fees

        # Check cash availability
        if total_cost > self.cash_balance:
            max_quantity = (self.cash_balance * 0.99) / (price * (1 + self.trading_fee))
            if max_quantity < 0.001:
                logger.info(f"Skipping buy for {symbol}: Insufficient cash. Need ${total_cost:.2f}, have ${self.cash_balance:.2f}")
                if model_confidence >= confidence_threshold:
                    self.signal_to_trade_statistics['filtered_signals']['insufficient_cash'] += 1
                return None
            quantity = max_quantity
            fees = price * quantity * self.trading_fee
            total_cost = (price * quantity) + fees

        # Execute buy trade
        return await self._execute_buy_trade(symbol, price, quantity, fees, signal)
    
    async def _process_sell_signal(self, symbol: str, price: float, strength: float, signal: Dict) -> Optional[Dict]:
        """Process a sell signal."""
        if symbol not in self.positions or self.positions[symbol].status != 'open':
            logger.info(f"Skipping sell for {symbol}: No open position found")
            return None
        
        position = self.positions[symbol]
        return await self._execute_sell_trade(symbol, price, position.quantity, signal)
    
    async def _execute_buy_trade(self, symbol: str, price: float, quantity: float, fees: float, signal: Dict) -> Dict:
        """Execute a buy trade."""
        self.trade_counter += 1
        trade_id = f"sim_{self.trade_counter}_{symbol}_{int(datetime.now().timestamp())}"
        
        # Update cash balance
        self.cash_balance -= ((price * quantity) + fees)
        
        # Create position
        position = Position(
            symbol=symbol,
            side='long',
            quantity=quantity,
            entry_price=price,
            entry_time=datetime.now(timezone.utc),
            current_price=price,
            unrealized_pnl=0.0
        )
        self.positions[symbol] = position
        
        # Create trade record
        trade = Trade(
            trade_id=trade_id,
            symbol=symbol,
            side='buy',
            quantity=quantity,
            price=price,
            timestamp=datetime.now(timezone.utc),
            reason=signal.get('signal_reason', 'Order book signal'),
            fees=fees,
            win_probability=signal.get('win_probability'),
            expected_return=signal.get('expected_return'),
            model_confidence=signal.get('model_confidence')
        )
        self.trades.append(trade)
        
        # Save and broadcast
        self._save_trade_to_db(trade)
        self._broadcast_trading_update()

        if signal.get('model_confidence', 0.0) >= self.strategy_params.get('confidence_threshold', 0.6):
            self.signal_to_trade_statistics['successful_trades'] += 1

        logger.info(f"Executed BUY: {quantity:.6f} {symbol} at ${price:.2f} (fees: ${fees:.2f})")

        return {
            "trade_id": trade_id,
            "action": "buy",
            "symbol": symbol,
            "quantity": quantity,
            "price": price,
            "fees": fees,
            "reason": trade.reason
        }

    async def _execute_sell_trade(self, symbol: str, price: float, quantity: float, signal: Dict) -> Dict:
        """Execute a sell trade."""
        position = self.positions[symbol]

        # Calculate PnL
        pnl = (price - position.entry_price) * quantity
        fees = price * quantity * self.trading_fee
        net_pnl = pnl - fees

        # Update cash balance
        self.cash_balance += ((price * quantity) - fees)

        # Create trade record
        self.trade_counter += 1
        trade_id = f"sim_{self.trade_counter}_{symbol}_{int(datetime.now().timestamp())}"

        trade = Trade(
            trade_id=trade_id,
            symbol=symbol,
            side='sell',
            quantity=quantity,
            price=price,
            timestamp=datetime.now(timezone.utc),
            reason=signal.get('signal_reason', 'Order book signal'),
            pnl=net_pnl,
            fees=fees,
            win_probability=signal.get('win_probability'),
            expected_return=signal.get('expected_return'),
            model_confidence=signal.get('model_confidence')
        )
        self.trades.append(trade)

        # Save and broadcast
        self._save_trade_to_db(trade)
        self._broadcast_trading_update()

        # Close position
        self._close_position(symbol, "Sell signal executed")

        logger.info(f"Executed SELL: {quantity:.6f} {symbol} at ${price:.2f} (PnL: ${net_pnl:.2f}, fees: ${fees:.2f})")

        return {
            "trade_id": trade_id,
            "action": "sell",
            "symbol": symbol,
            "quantity": quantity,
            "price": price,
            "pnl": net_pnl,
            "fees": fees,
            "reason": trade.reason
        }
    
    def _close_position(self, symbol: str, reason: str) -> None:
        """Close a position."""
        if symbol in self.positions:
            self.positions[symbol].status = 'closed'
            logger.info(f"Closed position for {symbol}: {reason}")

    async def force_close_all_positions(self, reason: str = "Server shutdown") -> None:
        """Force close all open positions."""
        try:
            open_symbols = [sym for sym, pos in self.positions.items() if pos.status == 'open']
            for symbol in open_symbols:
                try:
                    position = self.positions.get(symbol)
                    if not position or position.status != 'open':
                        continue

                    exit_price = position.current_price or position.entry_price
                    await self._execute_sell_trade(symbol, exit_price, position.quantity, {'signal_reason': reason})
                except Exception as e:
                    logger.warning(f"Failed to force-close {symbol} on shutdown: {e}")
                    self._close_position(symbol, f"{reason} (fallback close)")
        except Exception as e:
            logger.error(f"Error during force_close_all_positions: {e}")
    
    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions."""
        open_positions = []
        for symbol, position in self.positions.items():
            if position.status == 'open':
                entry_time = position.entry_time
                if isinstance(entry_time, str):
                    try:
                        entry_time = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
                    except (ValueError, TypeError) as e:
                        entry_time = datetime.now(timezone.utc)
                
                open_positions.append({
                    "symbol": symbol,
                    "side": position.side,
                    "quantity": position.quantity,
                    "entry_price": position.entry_price,
                    "current_price": position.current_price,
                    "unrealized_pnl": position.unrealized_pnl,
                    "status": "open",
                    "entry_time": entry_time.isoformat(),
                    "duration": str(datetime.now(timezone.utc) - entry_time)
                })
        return open_positions
    
    def get_recent_trades(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent trades."""
        recent_trades = sorted(self.trades, key=lambda t: t.timestamp, reverse=True)[:limit]
        return [
            {
                "trade_id": trade.trade_id,
                "symbol": trade.symbol,
                "side": trade.side,
                "quantity": trade.quantity,
                "price": trade.price,
                "pnl": trade.pnl,
                "fees": trade.fees,
                "timestamp": trade.timestamp.isoformat() if hasattr(trade.timestamp, 'isoformat') else str(trade.timestamp),
                "reason": trade.reason
            }
            for trade in recent_trades
        ]
    
    def get_signal_to_trade_statistics(self) -> Dict[str, Any]:
        """Get detailed statistics on signal-to-trade conversion."""
        stats = self.signal_to_trade_statistics.copy()

        signals_above_threshold = stats['total_signals_above_threshold']
        successful_trades = stats['successful_trades']

        stats['conversion_rate'] = (successful_trades / signals_above_threshold * 100) if signals_above_threshold > 0 else 0.0
        stats['total_filtered_signals'] = sum(stats['filtered_signals'].values())

        stats['gap_analysis'] = {
            'signals_above_threshold': signals_above_threshold,
            'successful_trades': successful_trades,
            'gap_size': signals_above_threshold - successful_trades,
            'gap_percentage': ((signals_above_threshold - successful_trades) / max(1, signals_above_threshold)) * 100
        }

        stats['top_filtering_reasons'] = sorted(
            stats['filtered_signals'].items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:5]

        stats['last_updated'] = datetime.now(timezone.utc).isoformat()
        return stats

    def reset_portfolio(self) -> None:
        """Reset portfolio to initial state."""
        self.cash_balance = self.initial_balance
        self.positions.clear()
        self.trades.clear()
        self.trade_counter = 0
        self.peak_value = self.initial_balance
        self.max_drawdown = 0.0
        self.total_signals_processed = 0
        self.signal_to_trade_statistics = {
            'total_signals_above_threshold': 0,
            'successful_trades': 0,
            'filtered_signals': {k: 0 for k in self.signal_to_trade_statistics['filtered_signals']}
        }
        logger.info("Portfolio reset to initial state")
    
    def get_total_signals_processed(self) -> int:
        """Get total number of signals processed since trading started."""
        return self.total_signals_processed
    
    def add_symbols(self, new_symbols: List[str]) -> None:
        """Add new symbols to the trading list."""
        for symbol in new_symbols:
            if symbol not in self.symbols_to_trade:
                self.symbols_to_trade.append(symbol)
        logger.info(f"Updated trading symbols: {self.symbols_to_trade}")

    def _broadcast_signal(self, signal: Dict[str, Any]) -> None:
        """Broadcast individual order book signal to frontend via WebSocket."""
        if not self.is_trading:
            return

        try:
            websocket_manager = getattr(self, '_websocket_manager', None)
            if websocket_manager:
                # Prepare signal data for broadcasting in the same format as data_handlers
                signal_data = {
                    "signals": [signal],
                    "trading_active": True,
                    "message": f"Order book signal updated: {signal.get('symbol')}",
                    "last_updated": datetime.now(timezone.utc).isoformat()
                }

                async def broadcast_signal():
                    await websocket_manager.broadcast(json.dumps({
                        "type": "orderbook_signals_update",
                        "data": signal_data
                    }))
                    logger.info(f"📡 Broadcasted signal for {signal.get('symbol')} via WebSocket")

                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(broadcast_signal())
                except RuntimeError:
                    asyncio.run(broadcast_signal())
            else:
                logger.warning(f"⚠️ WebSocket manager not available for broadcasting signal {signal.get('symbol')}")
        except Exception as e:
            logger.error(f"Error broadcasting signal: {e}")


    def _broadcast_trading_update(self) -> None:
        """Broadcast trading update to frontend widgets."""
        if not self.is_trading:
            return

        try:
            portfolio = self.get_portfolio_summary()
            portfolio_dict = asdict(portfolio)
            portfolio_dict["positions"] = self.get_open_positions()
            portfolio_dict["trades"] = self.get_recent_trades()[:10]

            trading_data = {
                "is_trading": self.is_trading,
                "portfolio": portfolio_dict,
                "open_positions": portfolio_dict["positions"],
                "recent_trades": portfolio_dict["trades"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_signals_processed": self.get_total_signals_processed()
            }

            websocket_manager = getattr(self, '_websocket_manager', None)
            if websocket_manager:
                async def broadcast_update():
                    await websocket_manager.broadcast(json.dumps({
                        "type": "trading_statistics_update",
                        "data": trading_data
                    }))

                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(broadcast_update())
                except RuntimeError:
                    asyncio.run(broadcast_update())
        except Exception as e:
            logger.error(f"Error in trading update broadcast: {e}")
    
    async def get_loading_status(self) -> Dict[str, Any]:
        """Get current loading status for async symbol loading."""
        return {
            "loading_progress": {
                "status": "complete",
                "loaded": len(self.symbols_to_trade),
                "total": len(self.symbols_to_trade),
                "remaining": 0,
                "progress": 100
            },
            "current_symbols": self.symbols_to_trade,
            "is_loading": False
        }
