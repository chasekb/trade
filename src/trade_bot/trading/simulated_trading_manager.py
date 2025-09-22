"""
Simulated Trading Manager for Live Order Book Signals.

This module handles simulated trading based on live order book signals,
including position tracking, portfolio management, and trade execution.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import json

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents a trading position."""
    symbol: str
    side: str  # 'long' or 'short'
    quantity: float
    entry_price: float
    entry_time: datetime
    current_price: float
    unrealized_pnl: float
    realized_pnl: float = 0.0
    status: str = 'open'  # 'open', 'closed'
    
    def update_price(self, new_price: float) -> None:
        """Update current price and calculate unrealized PnL."""
        self.current_price = new_price
        if self.side == 'long':
            self.unrealized_pnl = (new_price - self.entry_price) * self.quantity
        else:  # short
            self.unrealized_pnl = (self.entry_price - new_price) * self.quantity


@dataclass
class Trade:
    """Represents a completed trade."""
    trade_id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: float
    price: float
    timestamp: datetime
    reason: str
    pnl: float = 0.0
    fees: float = 0.0


@dataclass
class Portfolio:
    """Represents the trading portfolio."""
    cash_balance: float
    total_value: float
    positions: Dict[str, Position]
    trades: List[Trade]
    total_pnl: float
    total_fees: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    winning_trades: int


class SimulatedTradingManager:
    """Manages simulated trading based on live order book signals."""
    
    def __init__(self, initial_balance: float = 10000.0, max_positions: int = 5, 
                 position_size_percent: float = 20.0, trading_fee: float = 0.001,
                 db_manager=None, session_id: str = None):
        self.initial_balance = initial_balance
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
        
        # Strategy information
        self.strategy_type = None
        self.strategy_params = {}
        
        logger.info(f"SimulatedTradingManager initialized with ${initial_balance:,.2f} balance")
    
    def set_session_info(self, db_manager, session_id: str) -> None:
        """Set database manager and session ID for trade logging."""
        self.db_manager = db_manager
        self.session_id = session_id
        logger.info(f"Session info set: {session_id}")
    
    def set_strategy_info(self, strategy_type: str, strategy_params: Dict[str, Any]) -> None:
        """Set strategy type and parameters for trade logging."""
        self.strategy_type = strategy_type
        self.strategy_params = strategy_params
        logger.info(f"Strategy info set: {strategy_type} with params: {strategy_params}")
    
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
                    # Check if we've reached max positions limit
                    if open_positions_count >= self.max_positions:
                        logger.warning(f"Max positions limit ({self.max_positions}) reached, skipping restoration of {pos_data['symbol']}")
                        continue
                    
                    # Convert entry_time string to datetime if needed
                    entry_time = pos_data.get('entry_time', '')
                    if isinstance(entry_time, str) and entry_time:
                        try:
                            from datetime import datetime
                            entry_time = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
                        except:
                            entry_time = datetime.now()
                    elif not entry_time:
                        entry_time = datetime.now()
                    
                    position = Position(
                        symbol=pos_data['symbol'],
                        side=pos_data.get('side', 'long'),
                        quantity=float(pos_data.get('quantity', 0.0)),
                        entry_price=float(pos_data.get('entry_price', 0.0)),
                        entry_time=entry_time,
                        current_price=float(pos_data.get('current_price', 0.0)),
                        unrealized_pnl=float(pos_data.get('unrealized_pnl', 0.0))
                    )
                    self.positions[position.symbol] = position
                    open_positions_count += 1
            
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
            logger.info(f"Portfolio state details: {portfolio_state}")
            logger.info(f"Positions details: {positions}")
            logger.info(f"Trades details: {trades}")
            
            # Debug: Check if the restoration actually worked
            logger.info(f"After restoration - cash_balance: {self.cash_balance}, positions: {len(self.positions)}, trades: {len(self.trades)}")
            
        except Exception as e:
            logger.error(f"Error restoring portfolio state: {e}")
            # Reset to initial state if restoration fails
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
                    'price': trade.price,
                    'timestamp': trade.timestamp.isoformat(),
                    'reason': trade.reason,
                    'pnl': trade.pnl,
                    'fees': trade.fees,
                    'strategy_type': self.strategy_type,
                    'strategy_params': self.strategy_params
                }
                self.db_manager.save_trade(trade_data)
            except Exception as e:
                logger.error(f"Failed to save trade to database: {e}")
    
    def start_trading(self, symbols: List[str], position_size_percent: float = None, max_positions: int = None) -> None:
        """Start simulated trading for specified symbols."""
        self.symbols_to_trade = symbols
        self.is_trading = True
        self.last_signal_check = datetime.now()
        
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
            # Import here to avoid circular imports
            from ..data.data_provider import CoinbaseDataProvider
            import asyncio
            
            async def update_prices():
                # Create a copy of positions to avoid dictionary changed size during iteration
                positions_copy = dict(self.positions)
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
                                else:
                                    logger.warning(f"No bid/ask data for {symbol}")
                            else:
                                logger.warning(f"Could not get orderbook data for {symbol}")
                        except Exception as e:
                            logger.warning(f"Error updating price for {symbol}: {e}")
                            # Keep the existing price if we can't get current data
                            continue
            
            # Check if we're already in an event loop
            try:
                loop = asyncio.get_running_loop()
                # We're in an event loop, create a task
                loop.create_task(update_prices())
            except RuntimeError:
                # No event loop running, we can use asyncio.run()
                asyncio.run(update_prices())
        except Exception as e:
            logger.error(f"Error updating position prices: {e}")
    
    def get_portfolio_summary(self) -> Portfolio:
        """Get current portfolio summary."""
        # Update all position prices with current market data
        self._update_all_position_prices()
        
        total_value = self.cash_balance
        total_pnl = 0.0
        total_fees = sum(trade.fees for trade in self.trades)
        winning_trades = sum(1 for trade in self.trades if trade.pnl > 0)
        
        # Calculate total value including open positions
        for position in self.positions.values():
            if position.status == 'open':
                total_value += position.quantity * position.current_price
                total_pnl += position.unrealized_pnl
        
        # Calculate win rate
        total_trades = len(self.trades)
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
            winning_trades=winning_trades
        )
    
    async def process_signals(self, signals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process live order book signals and execute trades."""
        if not self.is_trading:
            return {"status": "not_trading", "message": "Trading is not active"}
        
        # Enforce max positions limit before processing signals
        self._enforce_max_positions_limit()
        
        # Update total signals processed counter
        self.total_signals_processed += len(signals)
        
        logger.info(f"Processing {len(signals)} signals. Total processed: {self.total_signals_processed}. Trading symbols: {self.symbols_to_trade}")
        
        executed_trades = []
        closed_positions = []
        
        for signal in signals:
            symbol = signal.get('symbol')
            logger.info(f"Processing signal for {symbol}: {signal.get('signal')} (generated: {signal.get('signal_generated')})")
            
            if symbol not in self.symbols_to_trade:
                logger.info(f"Skipping {symbol} - not in trading symbols")
                continue
            
            signal_action = signal.get('signal')
            signal_generated = signal.get('signal_generated', False)
            current_price = signal.get('price', 0.0)
            signal_strength = signal.get('signal_strength', 0.0)
            
            if not signal_generated or signal_action == 'hold':
                continue
            
            # Update existing position price
            if symbol in self.positions and self.positions[symbol].status == 'open':
                self.positions[symbol].update_price(current_price)
            
            # Process buy signals
            if signal_action == 'buy':
                logger.info(f"Processing buy signal for {symbol} at ${current_price}")
                trade_result = await self._process_buy_signal(symbol, current_price, signal_strength, signal)
                if trade_result:
                    executed_trades.append(trade_result)
                    logger.info(f"Executed buy trade for {symbol}: {trade_result}")
                else:
                    logger.info(f"Failed to execute buy trade for {symbol}")
            
            # Process sell signals
            elif signal_action == 'sell':
                logger.info(f"Processing sell signal for {symbol} at ${current_price}")
                trade_result = await self._process_sell_signal(symbol, current_price, signal_strength, signal)
                if trade_result:
                    executed_trades.append(trade_result)
                    logger.info(f"Executed sell trade for {symbol}: {trade_result}")
                    if symbol in self.positions and self.positions[symbol].status == 'closed':
                        closed_positions.append(symbol)
                else:
                    logger.info(f"Failed to execute sell trade for {symbol}")
        
        self.last_signal_check = datetime.now()
        
        return {
            "status": "processed",
            "executed_trades": len(executed_trades),
            "closed_positions": len(closed_positions),
            "trades": executed_trades,
            "portfolio": self.get_portfolio_summary()
        }
    
    async def _process_buy_signal(self, symbol: str, price: float, strength: float, signal: Dict) -> Optional[Dict]:
        """Process a buy signal."""
        # Check if we already have a position
        if symbol in self.positions and self.positions[symbol].status == 'open':
            logger.debug(f"Already have open position for {symbol}, skipping buy signal")
            return None
        
        # Check if we have reached max positions
        open_positions = sum(1 for p in self.positions.values() if p.status == 'open')
        if open_positions >= self.max_positions:
            logger.debug(f"Max positions ({self.max_positions}) reached, skipping buy signal for {symbol}")
            return None
        
        # Calculate position size based on total portfolio value
        # This ensures each position represents a fixed percentage of the total portfolio
        total_portfolio_value = self.cash_balance + sum(
            pos.quantity * pos.current_price for pos in self.positions.values() 
            if pos.status == 'open'
        )
        position_value = total_portfolio_value * self.position_size_percent
        quantity = position_value / price
        
        if quantity < 0.001:  # Minimum quantity threshold
            logger.debug(f"Insufficient cash for {symbol} position")
            return None
        
        # Calculate fees
        fees = price * quantity * self.trading_fee
        total_cost = (price * quantity) + fees
        
        # Check if we have enough cash for this position
        if total_cost > self.cash_balance:
            # If we don't have enough cash, reduce the quantity to fit within available cash
            max_quantity = (self.cash_balance * 0.99) / (price * (1 + self.trading_fee))  # 99% to account for fees
            if max_quantity < 0.001:
                logger.debug(f"Insufficient cash for {symbol} position: need ${total_cost:.2f}, have ${self.cash_balance:.2f}")
                return None
            quantity = max_quantity
            fees = price * quantity * self.trading_fee
            total_cost = (price * quantity) + fees
        
        # Execute buy trade
        return await self._execute_buy_trade(symbol, price, quantity, fees, signal)
    
    async def _process_sell_signal(self, symbol: str, price: float, strength: float, signal: Dict) -> Optional[Dict]:
        """Process a sell signal."""
        if symbol not in self.positions or self.positions[symbol].status != 'open':
            logger.debug(f"No open position for {symbol}, skipping sell signal")
            return None
        
        position = self.positions[symbol]
        return await self._execute_sell_trade(symbol, price, position.quantity, signal)
    
    async def _execute_buy_trade(self, symbol: str, price: float, quantity: float, fees: float, signal: Dict) -> Dict:
        """Execute a buy trade."""
        self.trade_counter += 1
        trade_id = f"sim_{self.trade_counter}_{symbol}_{int(datetime.now().timestamp())}"
        
        # Update cash balance
        total_cost = (price * quantity) + fees
        self.cash_balance -= total_cost
        
        # Create position
        position = Position(
            symbol=symbol,
            side='long',
            quantity=quantity,
            entry_price=price,
            entry_time=datetime.now(),
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
            timestamp=datetime.now(),
            reason=signal.get('signal_reason', 'Order book signal'),
            fees=fees
        )
        self.trades.append(trade)
        
        # Save trade to database
        self._save_trade_to_db(trade)
        
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
        proceeds = (price * quantity) - fees
        self.cash_balance += proceeds
        
        # Create trade record
        self.trade_counter += 1
        trade_id = f"sim_{self.trade_counter}_{symbol}_{int(datetime.now().timestamp())}"
        
        trade = Trade(
            trade_id=trade_id,
            symbol=symbol,
            side='sell',
            quantity=quantity,
            price=price,
            timestamp=datetime.now(),
            reason=signal.get('signal_reason', 'Order book signal'),
            pnl=net_pnl,
            fees=fees
        )
        self.trades.append(trade)
        
        # Save trade to database
        self._save_trade_to_db(trade)
        
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
    
    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions."""
        open_positions = []
        for symbol, position in self.positions.items():
            if position.status == 'open':
                # Handle entry_time conversion
                entry_time = position.entry_time
                if isinstance(entry_time, str):
                    try:
                        entry_time = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
                    except:
                        entry_time = datetime.now()
                
                open_positions.append({
                    "symbol": symbol,
                    "side": position.side,
                    "quantity": position.quantity,
                    "entry_price": position.entry_price,
                    "current_price": position.current_price,
                    "unrealized_pnl": position.unrealized_pnl,
                    "entry_time": entry_time.isoformat(),
                    "duration": str(datetime.now() - entry_time)
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
    
    def reset_portfolio(self) -> None:
        """Reset portfolio to initial state."""
        self.cash_balance = self.initial_balance
        self.positions.clear()
        self.trades.clear()
        self.trade_counter = 0
        self.peak_value = self.initial_balance
        self.max_drawdown = 0.0
        self.total_signals_processed = 0
        logger.info("Portfolio reset to initial state")
    
    def get_total_signals_processed(self) -> int:
        """Get total number of signals processed since trading started."""
        return self.total_signals_processed
    
    def add_symbols(self, new_symbols: List[str]) -> None:
        """Add new symbols to the trading list."""
        for symbol in new_symbols:
            if symbol not in self.symbols_to_trade:
                self.symbols_to_trade.append(symbol)
                logger.info(f"Added symbol to trading: {symbol}")
        
        logger.info(f"Updated trading symbols: {self.symbols_to_trade}")
    
    async def get_loading_status(self) -> Dict[str, Any]:
        """Get current loading status for async symbol loading."""
        try:
            # This would typically track loading progress from async operations
            # For now, return a basic status indicating loading is complete
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
        except Exception as e:
            logger.error(f"Error getting loading status: {e}")
            return {
                "loading_progress": {
                    "status": "error",
                    "loaded": 0,
                    "total": 0,
                    "remaining": 0,
                    "progress": 0
                },
                "current_symbols": [],
                "is_loading": False
            }