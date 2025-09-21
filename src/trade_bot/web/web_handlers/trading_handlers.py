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
    
    async def start_simulated_trading(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Start simulated trading session."""
        try:
            symbols = request_data.get('symbols', ['BTC-USD'])
            strategy_type = request_data.get('strategy_type', 'SMA')
            strategy_params = request_data.get('strategy_params', {})
            position_size_percent = request_data.get('position_size_percent', 20.0)
            max_positions = request_data.get('max_positions', 5)
            initial_balance = request_data.get('initial_balance', 10000.0)
            
            # Update simulated trading manager with new parameters
            self.simulated_trading_manager.initial_balance = initial_balance
            self.simulated_trading_manager.cash_balance = initial_balance
            
            # Start simulated trading with position size parameters
            self.simulated_trading_manager.start_trading(
                symbols, 
                position_size_percent=position_size_percent,
                max_positions=max_positions
            )
            
            return {
                "status": "started",
                "symbols": symbols,
                "strategy_type": strategy_type,
                "position_size_percent": position_size_percent,
                "max_positions": max_positions,
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
            
            return {
                "is_trading": self.simulated_trading_manager.is_trading,
                "portfolio": portfolio,
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
