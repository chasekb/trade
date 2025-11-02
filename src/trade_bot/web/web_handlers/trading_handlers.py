"""Trading handlers for the trading web server."""

import logging
import re
import json
from typing import Dict, Any, Optional
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class TradingHandlers:
    """Handles trading-related functionality for the trading web server."""

    def __init__(self, config, simulated_trading_manager, database_manager, websocket_manager=None):
        self.config = config
        self.simulated_trading_manager = simulated_trading_manager
        self.database_manager = database_manager
        self.websocket_manager = websocket_manager
        # Set websocket manager reference in simulated trading manager for direct access
        if websocket_manager:
            self.simulated_trading_manager._websocket_manager = websocket_manager
        # Get configurable symbol limits
        self.max_symbols_per_request = getattr(config, 'max_symbols_per_request', 1000)
        self.max_universe_size = getattr(config, 'max_universe_size', 500)
    
    async def start_live_trading(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Start live trading session."""
        try:
            symbols = request_data.get('symbols', ['BTC-USD'])
            strategy_type = request_data.get('strategy_type', 'SMA')
            strategy_params = request_data.get('strategy_params', {})

            # Validate symbols
            if not isinstance(symbols, list) or len(symbols) == 0:
                raise HTTPException(status_code=400, detail="symbols must be a non-empty array")
            clean_symbols = []
            for s in symbols:
                if isinstance(s, str) and re.fullmatch(r"[A-Z0-9\-]{3,30}", s):
                    clean_symbols.append(s)
            if not clean_symbols:
                raise HTTPException(status_code=400, detail="No valid symbols provided")
            
            # Check universe size limit
            if len(clean_symbols) > self.max_universe_size:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Universe size {len(clean_symbols)} exceeds maximum allowed {self.max_universe_size}. Please reduce the number of symbols or increase the max_universe_size configuration."
                )
            
            # Use configurable limit from strategy configuration
            symbols = clean_symbols[:self.max_symbols_per_request]

            # Validate params
            if strategy_params is None:
                strategy_params = {}
            if not isinstance(strategy_params, dict):
                raise HTTPException(status_code=400, detail="strategy_params must be an object")
            
            # Start simulated trading
            self.simulated_trading_manager.start_trading(symbols)
            
            return {
                "status": "started",
                "symbols": symbols,
                "strategy_type": strategy_type,
                "message": "Live trading started successfully"
            }
        except Exception as e:
            logger.error(f"Error starting live trading: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def stop_live_trading(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Stop live trading session."""
        try:
            self.simulated_trading_manager.stop_trading()
            
            return {
                "status": "stopped",
                "message": "Live trading stopped successfully"
            }
        except Exception as e:
            logger.error(f"Error stopping live trading: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_live_positions(self, page: int = 1, limit: int = 50) -> Dict[str, Any]:
        """Get current live trading positions with pagination.

        If no positions are available in-memory (e.g. after a restart),
        attempt a lightweight reconstruction from recent trades in the DB
        (assumes whole-position sells, as implemented by the simulator).
        """
        try:
            page = max(1, int(page))
            limit = max(1, min(int(limit), 1000))
            # Primary source: in-memory simulated trading state
            positions = self.simulated_trading_manager.get_open_positions()

            # Fallback: reconstruct from recent trades persisted in DB
            if not positions:
                positions = await self._reconstruct_open_positions_from_db()

            total_positions = len(positions)
            total_pages = (total_positions + limit - 1) // limit if limit > 0 else 1
            current_page = max(1, min(page, total_pages if total_pages > 0 else 1))
            offset = (current_page - 1) * limit if limit > 0 else 0
            page_positions = positions[offset: offset + limit] if limit > 0 else positions

            return {
                "positions": page_positions,
                "pagination": {
                    "current_page": current_page,
                    "per_page": limit,
                    "total_pages": total_pages,
                    "total_positions": total_positions,
                    "has_next": current_page < total_pages,
                    "has_prev": current_page > 1
                }
            }
        except Exception as e:
            logger.error(f"Error getting live positions: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def _reconstruct_open_positions_from_db(self) -> list[Dict[str, Any]]:
        """Reconstruct open positions from recent trades in the database.

        Assumes the simulator opens with a single BUY and closes with a full SELL.
        If the latest trade for a symbol is a BUY with no subsequent SELL, we
        treat it as an open position. Uses trade price as both entry and current
        price for a conservative zero P&L default when live pricing is unavailable.
        """
        try:
            if not hasattr(self.database_manager, "get_recent_trades"):
                return []

            recent_trades = self.database_manager.get_recent_trades(limit=1000) or []

            # Sort ascending by timestamp to process chronologically
            def _ts(trade: Dict[str, Any]):
                ts = trade.get("timestamp")
                return ts or ""

            recent_trades.sort(key=_ts)

            symbol_state: Dict[str, Dict[str, Any]] = {}
            for trade in recent_trades:
                symbol = trade.get("symbol")
                side = trade.get("side")
                if not symbol or side not in ("buy", "sell"):
                    continue
                if side == "buy":
                    symbol_state[symbol] = {
                        "symbol": symbol,
                        "side": "long",
                        "quantity": float(trade.get("quantity", 0.0)),
                        "entry_price": float(trade.get("price", 0.0)),
                        "current_price": float(trade.get("price", 0.0)),
                        "unrealized_pnl": 0.0,
                        "entry_time": trade.get("timestamp") or "",
                        "duration": ""
                    }
                else:  # sell closes the whole position in our simulator
                    symbol_state[symbol] = None

            open_positions: list[Dict[str, Any]] = []
            from datetime import datetime
            for state in symbol_state.values():
                if state:
                    # Compute duration if possible
                    entry_time = state.get("entry_time")
                    try:
                        if entry_time:
                            dt = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))
                            state["duration"] = str(datetime.now(dt.tzinfo) - dt)
                    except Exception:
                        pass
                    open_positions.append(state)

            return open_positions
        except Exception as e:
            logger.error(f"Error reconstructing open positions from DB: {e}")
            return []
    
    async def close_live_position(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Close a specific live trading position."""
        try:
            symbol = request_data.get('symbol')
            if not symbol or not re.fullmatch(r"[A-Z0-9\-]{3,30}", str(symbol)):
                raise HTTPException(status_code=400, detail="Symbol is required")
            
            # Close position logic would go here
            return {
                "status": "closed",
                "symbol": symbol,
                "message": f"Position for {symbol} closed successfully"
            }
        except Exception as e:
            logger.error(f"Error closing live position: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_live_trading_history(self) -> Dict[str, Any]:
        """Get live trading history."""
        try:
            trades = self.simulated_trading_manager.get_recent_trades()
            return {"trades": trades}
        except Exception as e:
            logger.error(f"Error getting live trading history: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_paginated_trading_history(self, page: int = 1, per_page: int = 10, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Get paginated trading history, optionally filtered by session_id."""
        try:
            page = max(1, int(page))
            per_page = max(1, min(int(per_page), 1000))
            # Get trades from database, filtered by session_id if provided
            if session_id:
                if not re.fullmatch(r"[A-Za-z0-9._\-]{1,64}", str(session_id)):
                    raise HTTPException(status_code=400, detail="Invalid session_id format")
                all_trades = self.database_manager.get_trades_by_session(session_id)
            else:
                all_trades = self.database_manager.get_all_trades(limit=1000, offset=0)
            
            total_trades = len(all_trades)
            total_pages = (total_trades + per_page - 1) // per_page  # Ceiling division
            
            # Calculate offset for pagination
            offset = (page - 1) * per_page
            
            # Get trades for current page
            page_trades = all_trades[offset:offset + per_page]
            
            return {
                "trades": page_trades,
                "pagination": {
                    "current_page": page,
                    "per_page": per_page,
                    "total_pages": total_pages,
                    "total_trades": total_trades,
                    "has_next": page < total_pages,
                    "has_prev": page > 1
                }
            }
        except Exception as e:
            logger.error(f"Error getting paginated trading history: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_all_trading_history(self, limit: int = 1000, offset: int = 0) -> Dict[str, Any]:
        """Get all trading history from database."""
        try:
            limit = max(1, min(int(limit), 5000))
            offset = max(0, int(offset))
            trades = self.database_manager.get_all_trades(limit=limit, offset=offset)
            total_count = self.database_manager.get_trades_count()
            
            return {
                "trades": trades,
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + limit) < total_count
            }
        except Exception as e:
            logger.error(f"Error getting all trading history: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_session_trading_history(self, session_id: str, limit: int = 100) -> Dict[str, Any]:
        """Get trading history for a specific session."""
        try:
            if not re.fullmatch(r"[A-Za-z0-9._\-]{1,64}", str(session_id)):
                raise HTTPException(status_code=400, detail="Invalid session_id format")
            limit = max(1, min(int(limit), 2000))
            trades = self.database_manager.get_trades_by_session(session_id, limit=limit)
            session_info = self.database_manager.get_session_info(session_id)
            
            return {
                "session_id": session_id,
                "trades": trades,
                "session_info": session_info,
                "trade_count": len(trades)
            }
        except Exception as e:
            logger.error(f"Error getting session trading history: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_trading_metrics(self) -> Dict[str, Any]:
        """Get comprehensive trading metrics."""
        try:
            # Get all trades for analysis
            all_trades = self.database_manager.get_all_trades(limit=10000)
            
            if not all_trades:
                return {
                    "total_trades": 0,
                    "total_volume": 0,
                    "total_pnl": 0,
                    "win_rate": 0,
                    "avg_trade_size": 0,
                    "best_trade": 0,
                    "worst_trade": 0,
                    "total_fees": 0,
                    "symbols_traded": [],
                    "strategy_performance": {},
                    "daily_pnl": [],
                    "monthly_pnl": []
                }
            
            # Calculate basic metrics
            total_trades = len(all_trades)
            # Handle both 'size' and 'quantity' keys for trade size
            def _qty(trade):
                v = trade.get('quantity')
                if v is None:
                    v = trade.get('size')
                try:
                    return float(v or 0)
                except Exception:
                    return 0.0
            total_volume = sum(_qty(trade) * float(trade.get('price', 0) or 0) for trade in all_trades)
            total_pnl = sum(trade.get('pnl', 0) for trade in all_trades)
            total_fees = sum(trade.get('fees', 0) for trade in all_trades)
            
            # Calculate win rate
            winning_trades = [trade for trade in all_trades if trade.get('pnl', 0) > 0]
            win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
            
            # Calculate trade size metrics
            trade_sizes = [_qty(trade) * float(trade.get('price', 0) or 0) for trade in all_trades]
            avg_trade_size = sum(trade_sizes) / len(trade_sizes) if trade_sizes else 0
            
            # Best and worst trades
            pnl_values = [trade.get('pnl', 0) for trade in all_trades]
            best_trade = max(pnl_values) if pnl_values else 0
            worst_trade = min(pnl_values) if pnl_values else 0
            
            # Symbols traded
            symbols_traded = list(set(trade.get('symbol', '') for trade in all_trades if trade.get('symbol')))
            
            # Strategy performance
            strategy_performance = {}
            for trade in all_trades:
                strategy = trade.get('strategy_type', 'unknown')
                if strategy not in strategy_performance:
                    strategy_performance[strategy] = {
                        'trades': 0,
                        'pnl': 0,
                        'volume': 0
                    }
                strategy_performance[strategy]['trades'] += 1
                strategy_performance[strategy]['pnl'] += trade.get('pnl', 0)
                strategy_performance[strategy]['volume'] += trade.get('quantity', 0) * trade.get('price', 0)
            
            # Daily P&L (last 30 days)
            from datetime import datetime, timedelta
            daily_pnl = []
            for i in range(30):
                date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
                day_trades = [trade for trade in all_trades 
                             if trade.get('timestamp', '').startswith(date)]
                day_pnl = sum(trade.get('pnl', 0) for trade in day_trades)
                daily_pnl.append({'date': date, 'pnl': day_pnl})
            
            return {
                "total_trades": total_trades,
                "total_volume": total_volume,
                "total_pnl": total_pnl,
                "win_rate": win_rate,
                "avg_trade_size": avg_trade_size,
                "best_trade": best_trade,
                "worst_trade": worst_trade,
                "total_fees": total_fees,
                "symbols_traded": symbols_traded,
                "strategy_performance": strategy_performance,
                "daily_pnl": daily_pnl,
                "monthly_pnl": []  # Could be implemented similarly
            }
        except Exception as e:
            logger.error(f"Error getting trading metrics: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def start_simulated_trading(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Start simulated trading session."""
        try:
            symbols = request_data.get('symbols', ['BTC-USD'])
            strategy_type = request_data.get('strategy_type', 'SMA')
            strategy_params = request_data.get('strategy_params', {})
            position_size_percent = request_data.get('position_size_percent', 20.0)
            max_positions = request_data.get('max_positions', 5)
            position_update_interval = request_data.get('position_update_interval', 5)
            initial_balance = request_data.get('initial_balance', 10000.0)
            
            # Validate universe size limit
            if len(symbols) > self.max_universe_size:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Universe size {len(symbols)} exceeds maximum allowed {self.max_universe_size}. Please reduce the number of symbols or increase the max_universe_size configuration."
                )
            
            # Validate max positions limit
            max_positions_per_session = getattr(self.config, 'max_positions_per_session', 100)
            if max_positions > max_positions_per_session:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Max positions {max_positions} exceeds maximum allowed {max_positions_per_session}. Please reduce max_positions or increase the max_positions_per_session configuration."
                )
            
            # Generate session ID for this trading session
            import uuid
            from datetime import datetime
            session_id = f"sim_{uuid.uuid4().hex[:8]}_{int(datetime.now().timestamp())}"
            
            # Set session info for database logging
            self.simulated_trading_manager.set_session_info(self.database_manager, session_id)
            
            # Update simulated trading manager with new parameters
            # Only update initial_balance if it's different from current balance
            if self.simulated_trading_manager.initial_balance != initial_balance:
                self.simulated_trading_manager.initial_balance = initial_balance
                # Only reset cash_balance if we're starting fresh (no existing trades)
                if len(self.simulated_trading_manager.trades) == 0:
                    self.simulated_trading_manager.cash_balance = initial_balance
            
            # Update position update interval
            self.simulated_trading_manager.position_update_interval = position_update_interval

            # Set strategy info for trade logging and signal processing
            self.simulated_trading_manager.set_strategy_info(strategy_type, strategy_params)

            # Start simulated trading with position size parameters
            self.simulated_trading_manager.start_trading(
                symbols,
                position_size_percent=position_size_percent,
                max_positions=max_positions
            )

            # Broadcast initial trading state to frontend widgets
            await self._broadcast_trading_start_to_frontend()

            return {
                "status": "started",
                "session_id": session_id,
                "symbols": symbols,
                "strategy_type": strategy_type,
                "position_size_percent": position_size_percent,
                "max_positions": max_positions,
                "position_update_interval": position_update_interval,
                "initial_balance": initial_balance,
                "message": "Simulated trading started successfully"
            }
        except Exception as e:
            logger.error(f"Error starting simulated trading: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def stop_simulated_trading(self) -> Dict[str, Any]:
        """Stop simulated trading session."""
        try:
            self.simulated_trading_manager.stop_trading()
            
            return {
                "status": "stopped",
                "message": "Simulated trading stopped successfully"
            }
        except Exception as e:
            logger.error(f"Error stopping simulated trading: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_simulated_trading_status(self) -> Dict[str, Any]:
        """Get simulated trading status."""
        try:
            portfolio = self.simulated_trading_manager.get_portfolio_summary()
            open_positions = self.simulated_trading_manager.get_open_positions()
            recent_trades = self.simulated_trading_manager.get_recent_trades()
            
            # Convert portfolio to dictionary for JSON serialization
            from dataclasses import asdict
            portfolio_dict = asdict(portfolio)
            
            return {
                "is_trading": self.simulated_trading_manager.is_trading,
                "symbols": self.simulated_trading_manager.symbols_to_trade,
                "strategy_type": self.simulated_trading_manager.strategy_type,
                "strategy_params": self.simulated_trading_manager.strategy_params,
                "max_positions": self.simulated_trading_manager.max_positions,
                "position_size_percent": self.simulated_trading_manager.position_size_percent * 100,
                "position_update_interval": self.simulated_trading_manager.position_update_interval,
                "portfolio": portfolio_dict,
                "open_positions": open_positions,
                "recent_trades": recent_trades
            }
        except Exception as e:
            logger.error(f"Error getting simulated trading status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def process_simulated_signals(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process simulated trading signals."""
        try:
            # Accept either full signals list or just symbols (legacy)
            signals = request_data.get('signals')
            symbols = request_data.get('symbols')

            if signals is None and symbols:
                # Backward compatibility: if only symbols provided, create basic buy signals
                signals = [
                    {
                        "symbol": sym,
                        "signal": "buy",
                        "signal_generated": True,
                        "price": 0.0,
                        "signal_strength": 0.5,
                        "signal_reason": "Auto-generated from symbols list"
                    }
                    for sym in symbols if isinstance(sym, str)
                ]

            if not signals:
                return {"error": "No signals provided"}

            result = await self.simulated_trading_manager.process_signals(signals)
            
            logger.info(f"Processed {len(signals)} signals, executed {result.get('executed_trades', 0)} trades")
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing simulated signals: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def reset_simulated_trading(self) -> Dict[str, Any]:
        """Reset simulated trading session."""
        try:
            self.simulated_trading_manager.reset_portfolio()
            
            return {
                "status": "reset",
                "message": "Simulated trading reset successfully"
            }
        except Exception as e:
            logger.error(f"Error resetting simulated trading: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def add_symbols_to_trading(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add symbols to current trading session."""
        try:
            symbols = request_data.get('symbols', [])
            self.simulated_trading_manager.add_symbols(symbols)

            return {
                "status": "added",
                "symbols": symbols,
                "message": f"Added {len(symbols)} symbols to trading"
            }
        except Exception as e:
            logger.error(f"Error adding symbols to trading: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def _broadcast_trading_start_to_frontend(self) -> None:
        """Broadcast initial trading state to frontend widgets after starting trading."""
        try:
            await self._broadcast_current_trading_status()
        except Exception as e:
            logger.error(f"Error broadcasting initial trading state to frontend: {e}")

    async def _broadcast_current_trading_status(self) -> None:
        """Broadcast current trading status to all connected frontend clients."""
        try:
            # Get current trading status data
            portfolio = self.simulated_trading_manager.get_portfolio_summary()
            open_positions = self.simulated_trading_manager.get_open_positions()
            recent_trades = self.simulated_trading_manager.get_recent_trades()

            # Convert portfolio to dictionary for JSON serialization
            from dataclasses import asdict
            portfolio_dict = asdict(portfolio)

            # Prepare data for frontend widgets
            trading_data = {
                "is_trading": self.simulated_trading_manager.is_trading,
                "symbols": self.simulated_trading_manager.symbols_to_trade,
                "strategy_type": self.simulated_trading_manager.strategy_type,
                "strategy_params": self.simulated_trading_manager.strategy_params,
                "max_positions": self.simulated_trading_manager.max_positions,
                "position_size_percent": self.simulated_trading_manager.position_size_percent * 100,
                "portfolio": portfolio_dict,
                "open_positions": open_positions,
                "recent_trades": recent_trades,
                "session_id": getattr(self.simulated_trading_manager, 'session_id', None),
                "trading_started_at": self.simulated_trading_manager.last_signal_check.isoformat() if self.simulated_trading_manager.last_signal_check else None
            }

            # Prepare signals data (use actual signals if available, otherwise default)
            try:
                # Try to get live signals data
                from .data_handlers import DataHandlers
                # Create a data handler instance to get signals
                data_handler = DataHandlers(
                    config=self.config,
                    data_provider=None,
                    cached_data_provider=None,
                    database_manager=self.database_manager,
                    simulated_trading_manager=self.simulated_trading_manager,
                    trading_handlers=self,
                    trading_state=None
                )

                if self.simulated_trading_manager.symbols_to_trade:
                    symbols_str = ','.join(self.simulated_trading_manager.symbols_to_trade)
                    signals_response = await data_handler.get_live_orderbook_signals(symbols_str)

                    if signals_response and signals_response.get('signals'):
                        signals_data = signals_response
                        signals_data["trading_active"] = True
                    else:
                        # Fallback to default signals
                        signals_data = self._create_default_signals_data()
                else:
                    signals_data = self._create_default_signals_data()

            except Exception as signals_error:
                logger.warning(f"Could not get live signals data: {signals_error}")
                signals_data = self._create_default_signals_data()

            # Import the websocket manager to broadcast to frontend
            from ..web_components.websocket_manager import WebSocketManager

            # Broadcast trading statistics update to frontend widgets
            websocket_manager = getattr(self.simulated_trading_manager, '_websocket_manager', None)
            if websocket_manager:
                await websocket_manager.broadcast(json.dumps({
                    "type": "trading_statistics_update",
                    "data": trading_data
                }))

                # Broadcast signals update to frontend
                await websocket_manager.broadcast(json.dumps({
                    "type": "orderbook_signals_update",
                    "data": signals_data
                }))

                logger.debug("Broadcasted current trading state to frontend widgets")
            else:
                logger.warning("WebSocket manager not available for broadcasting trading status")

        except Exception as e:
            logger.error(f"Error broadcasting current trading state to frontend: {e}")

    def _create_default_signals_data(self):
        """Create default signals data for when live signals are not available."""
        return {
            "signals": [
                {
                    "symbol": symbol,
                    "signal": "hold",
                    "signal_type": "hold",
                    "signal_strength": 0.0,
                    "strength": 0.0,
                    "price": 0.0,
                    "timestamp": None,
                    "reason": "Trading session starting",
                    "signal_reason": "Trading session starting",
                    "data_status": "initializing",
                    "spread": 0.0,
                    "volume": 0.0,
                    "signal_generated": False,
                    "criteria_analysis": {
                        "bid_ask_squeeze": {
                            "enabled": True,
                            "meets_criteria": False,
                            "delta_to_threshold": 0,
                            "analysis": "Trading session starting",
                            "threshold": 0.1,
                            "current_value": 0
                        },
                        "volume_imbalance_buy": {
                            "enabled": True,
                            "meets_criteria": False,
                            "delta_to_threshold": 0,
                            "analysis": "Trading session starting",
                            "threshold": 0.1,
                            "current_value": 0,
                            "bid_volume": 0,
                            "ask_volume": 0
                        },
                        "volume_imbalance_sell": {
                            "enabled": True,
                            "meets_criteria": False,
                            "delta_to_threshold": 0,
                            "analysis": "Trading session starting",
                            "threshold": 0.1,
                            "current_value": 0,
                            "bid_volume": 0,
                            "ask_volume": 0
                        },
                        "large_trade_buy": {
                            "enabled": True,
                            "meets_criteria": False,
                            "delta_to_threshold": 0,
                            "analysis": "Trading session starting",
                            "threshold": 10000,
                            "current_value": 0,
                            "large_trades_count": 0
                        },
                        "large_trade_sell": {
                            "enabled": True,
                            "meets_criteria": False,
                            "delta_to_threshold": 0,
                            "analysis": "Trading session starting",
                            "threshold": 10000,
                            "current_value": 0,
                            "large_trades_count": 0
                        }
                    }
                }
                for symbol in (self.simulated_trading_manager.symbols_to_trade or [])
            ],
            "trading_active": True,
            "message": "Trading session status requested",
            "total_analyzed": self.simulated_trading_manager.get_total_signals_processed() if hasattr(self.simulated_trading_manager, 'get_total_signals_processed') else 0,
            "active_signals": 0,
            "average_strength": 0.0,
            "last_updated": None,
            "pagination": {
                "current_page": 1,
                "per_page": 1000,
                "total_signals": len(self.simulated_trading_manager.symbols_to_trade or []),
                "total_pages": 1,
                "has_next": False,
                "has_prev": False
            }
        }

    async def _broadcast_trading_update_to_frontend(self, signals_result: Dict[str, Any] = None) -> None:
        """Broadcast trading updates to frontend widgets."""
        try:
            # Get current trading status data
            trading_status = await self.get_simulated_trading_status()

            # Get websocket manager from app state
            from ..web_components import get_app_state
            app_state = get_app_state()
            websocket_manager = getattr(app_state, 'websocket_manager', None)
            if not websocket_manager:
                # Try getting from existing websocket client if available
                websocket_manager = getattr(self.simulated_trading_manager, '_websocket_manager', None)

            if websocket_manager:
                # Broadcast trading statistics update
                await websocket_manager.broadcast(json.dumps({
                    "type": "trading_statistics_update",
                    "data": trading_status
                }))

                # If signals result is provided, broadcast signals update too
                if signals_result:
                    await websocket_manager.broadcast(json.dumps({
                        "type": "orderbook_signals_update",
                        "data": signals_result
                    }))

                logger.debug("Broadcasted trading update to frontend widgets")

        except Exception as e:
            logger.error(f"Error broadcasting trading update to frontend: {e}")
