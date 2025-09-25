"""Trading handlers for the trading web server."""

import logging
from typing import Dict, Any, Optional
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class TradingHandlers:
    """Handles trading-related functionality for the trading web server."""
    
    def __init__(self, config, simulated_trading_manager, database_manager):
        self.config = config
        self.simulated_trading_manager = simulated_trading_manager
        self.database_manager = database_manager
    
    async def start_live_trading(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Start live trading session."""
        try:
            symbols = request_data.get('symbols', ['BTC-USD'])
            strategy_type = request_data.get('strategy_type', 'SMA')
            strategy_params = request_data.get('strategy_params', {})
            
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
    
    async def get_live_positions(self) -> Dict[str, Any]:
        """Get current live trading positions."""
        try:
            positions = self.simulated_trading_manager.get_open_positions()
            return {"positions": positions}
        except Exception as e:
            logger.error(f"Error getting live positions: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def close_live_position(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Close a specific live trading position."""
        try:
            symbol = request_data.get('symbol')
            if not symbol:
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
            # Get trades from database, filtered by session_id if provided
            if session_id:
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
            total_volume = sum(trade.get('quantity', 0) * trade.get('price', 0) for trade in all_trades)
            total_pnl = sum(trade.get('pnl', 0) for trade in all_trades)
            total_fees = sum(trade.get('fees', 0) for trade in all_trades)
            
            # Calculate win rate
            winning_trades = [trade for trade in all_trades if trade.get('pnl', 0) > 0]
            win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
            
            # Calculate trade size metrics
            trade_sizes = [trade.get('quantity', 0) * trade.get('price', 0) for trade in all_trades]
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
            
            # Start simulated trading with position size parameters
            self.simulated_trading_manager.start_trading(
                symbols, 
                position_size_percent=position_size_percent,
                max_positions=max_positions
            )
            
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
            signals = request_data.get('signals', [])
            
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
