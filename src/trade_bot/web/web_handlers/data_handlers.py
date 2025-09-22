"""Data handlers for the trading web server."""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class DataHandlers:
    """Handles data-related functionality for the trading web server."""
    
    def __init__(self, config, data_provider, cached_data_provider, database_manager, simulated_trading_manager=None, trading_handlers=None):
        self.config = config
        self.data_provider = data_provider
        self.cached_data_provider = cached_data_provider
        self.database_manager = database_manager
        self.simulated_trading_manager = simulated_trading_manager
        self.trading_handlers = trading_handlers
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            stats = self.database_manager.get_cache_stats()
            return {"cache_stats": stats}
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_live_orderbook_signals(self, symbols: str = None, page: int = 1, per_page: int = 10) -> Dict[str, Any]:
        """Get live order book signals."""
        try:
            if not symbols:
                return {"error": "No symbols provided"}
            
            # Check if trading is active
            trading_active = False
            if self.simulated_trading_manager:
                trading_active = self.simulated_trading_manager.is_trading
            
            # Only return signals if trading is actually active
            if not trading_active:
                logger.info("Trading not active, returning empty signals")
                return {
                    "signals": [],
                    "trading_active": False,
                    "message": "Trading is not active. Configure your strategy and start trading to see live signals.",
                    "pagination": {
                        "current_page": page,
                        "per_page": per_page,
                        "total_signals": 0,
                        "total_pages": 0,
                        "has_next": False,
                        "has_prev": False
                    }
                }
            
            symbol_list = [s.strip() for s in symbols.split(',')]
            
            # Fetch real orderbook data from Coinbase API
            signals = []
            for symbol in symbol_list:
                try:
                    # Create a data provider instance for this symbol
                    from ...data.data_provider import CoinbaseDataProvider
                    symbol_provider = CoinbaseDataProvider(symbol)
                    
                    # Fetch live orderbook data (using level 2 for comprehensive signal analysis)
                    orderbook_data = await symbol_provider.get_order_book(level=2)
                    
                    if orderbook_data and orderbook_data.get('bids') and orderbook_data.get('asks'):
                        # Calculate orderbook metrics
                        best_bid = float(orderbook_data['bids'][0]['price']) if orderbook_data['bids'] else 0
                        best_ask = float(orderbook_data['asks'][0]['price']) if orderbook_data['asks'] else 0
                        current_price = (best_bid + best_ask) / 2 if best_bid and best_ask else 0
                        
                        # Calculate spread
                        spread = ((best_ask - best_bid) / current_price * 100) if current_price > 0 else 0
                        
                        # Calculate volume (sum of top 5 bids/asks)
                        bid_volume = sum(float(bid['size']) for bid in orderbook_data['bids'][:5])
                        ask_volume = sum(float(ask['size']) for ask in orderbook_data['asks'][:5])
                        total_volume = bid_volume + ask_volume
                        
                        # Calculate orderbook imbalance
                        volume_imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume) if (bid_volume + ask_volume) > 0 else 0
                        
                        # Determine signal based on orderbook analysis
                        if volume_imbalance > 0.1:  # More buy pressure
                            signal = "buy"
                            signal_strength = min(abs(volume_imbalance), 1.0)
                            signal_reason = f"Buy pressure detected (imbalance: {volume_imbalance:.2f})"
                        elif volume_imbalance < -0.1:  # More sell pressure
                            signal = "sell"
                            signal_strength = min(abs(volume_imbalance), 1.0)
                            signal_reason = f"Sell pressure detected (imbalance: {volume_imbalance:.2f})"
                        else:  # Balanced
                            signal = "hold"
                            signal_strength = 0.3
                            signal_reason = "Orderbook balanced"
                        
                        # Determine data status
                        data_status = "sufficient" if len(orderbook_data['bids']) >= 5 and len(orderbook_data['asks']) >= 5 else "insufficient"
                        
                        signals.append({
                            "symbol": symbol,
                            "signal": signal,
                            "signal_type": signal,
                            "signal_strength": signal_strength,
                            "strength": signal_strength,
                            "price": current_price,
                            "timestamp": orderbook_data.get('timestamp', '2024-01-01T00:00:00Z'),
                            "reason": signal_reason,
                            "signal_reason": signal_reason,
                            "data_status": data_status,
                            "spread": spread,
                            "volume": total_volume,
                            "signal_generated": signal != "hold" and signal_strength > 0.1,  # Only process strong signals
                            "criteria_analysis": {
                                "bid_ask_squeeze": {
                                    "analysis": f"Spread: {spread:.4f}%" if spread < 0.1 else "Wide spread detected"
                                },
                                "volume_imbalance_buy": {
                                    "analysis": f"Volume imbalance: {volume_imbalance:.2f} (bid: {bid_volume:.2f}, ask: {ask_volume:.2f})"
                                }
                            }
                        })
                        
                        logger.info(f"Generated live orderbook signal for {symbol}: {signal} (strength: {signal_strength:.2f})")
                    else:
                        # Fallback to placeholder if no data
                        logger.warning(f"No orderbook data available for {symbol}, using placeholder")
                        signals.append({
                            "symbol": symbol,
                            "signal": "hold",
                            "signal_type": "hold",
                            "signal_strength": 0.0,
                            "strength": 0.0,
                            "price": 0.0,
                            "timestamp": "2024-01-01T00:00:00Z",
                            "reason": "No orderbook data available",
                            "signal_reason": "No orderbook data available",
                            "data_status": "insufficient",
                            "spread": 0.0,
                            "volume": 0.0,
                            "signal_generated": False,  # No data available, don't process
                            "criteria_analysis": {
                                "bid_ask_squeeze": {
                                    "analysis": "No data available"
                                },
                                "volume_imbalance_buy": {
                                    "analysis": "No data available"
                                }
                            }
                        })
                        
                except Exception as e:
                    logger.error(f"Error fetching orderbook data for {symbol}: {e}")
                    # Fallback to placeholder on error
                    signals.append({
                        "symbol": symbol,
                        "signal": "hold",
                        "signal_type": "hold",
                        "signal_strength": 0.0,
                        "strength": 0.0,
                        "price": 0.0,
                        "timestamp": "2024-01-01T00:00:00Z",
                        "reason": f"Error fetching data: {str(e)}",
                        "signal_reason": f"Error fetching data: {str(e)}",
                        "data_status": "insufficient",
                        "spread": 0.0,
                        "volume": 0.0,
                        "signal_generated": False,  # Error occurred, don't process
                        "criteria_analysis": {
                            "bid_ask_squeeze": {
                                "analysis": "Error fetching data"
                            },
                            "volume_imbalance_buy": {
                                "analysis": "Error fetching data"
                            }
                        }
                    })
            
            # Sort signals by signal strength (descending)
            signals.sort(key=lambda x: x.get('signal_strength', 0), reverse=True)
            
            # Calculate pagination
            total_signals = len(signals)
            total_pages = (total_signals + per_page - 1) // per_page
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            paginated_signals = signals[start_idx:end_idx]
            
            # Calculate statistics
            active_signals = len([s for s in signals if s.get('signal_generated', False)])
            avg_strength = sum(s.get('signal_strength', 0) for s in signals) / len(signals) if signals else 0
            
            # Get cumulative total signals processed from simulated trading manager
            total_analyzed = 0
            if self.simulated_trading_manager and hasattr(self.simulated_trading_manager, 'get_total_signals_processed'):
                total_analyzed = self.simulated_trading_manager.get_total_signals_processed()
            
            return {
                "signals": paginated_signals,
                "trading_active": trading_active,
                "message": "Order book signals generated successfully",
                "total_analyzed": total_analyzed,
                "active_signals": active_signals,
                "average_strength": avg_strength,
                "last_updated": datetime.now().isoformat(),
                "pagination": {
                    "current_page": page,
                    "per_page": per_page,
                    "total_signals": total_signals,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1
                }
            }
        except Exception as e:
            logger.error(f"Error getting live orderbook signals: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_loading_status(self) -> Dict[str, Any]:
        """Get data loading status."""
        try:
            # Get loading status from simulated trading manager
            if self.simulated_trading_manager and hasattr(self.simulated_trading_manager, 'get_loading_status'):
                return await self.simulated_trading_manager.get_loading_status()
            
            # Fallback to static response if no trading manager
            return {
                "is_loading": False,
                "progress": 100,
                "loaded_symbols": 0,
                "total_symbols": 0,
                "message": "Data loading complete"
            }
        except Exception as e:
            logger.error(f"Error getting loading status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def load_remaining_symbols_async(self, remaining_symbols: list, 
                                         batch_size: int = 3) -> Dict[str, Any]:
        """Load remaining symbols asynchronously."""
        try:
            # This would typically load symbols in batches
            return {
                "status": "loading",
                "remaining_symbols": len(remaining_symbols),
                "batch_size": batch_size,
                "message": "Loading symbols in progress"
            }
        except Exception as e:
            logger.error(f"Error loading remaining symbols: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_trading_state(self) -> Dict[str, Any]:
        """Get current trading state."""
        try:
            # Get current trading status
            trading_status = await self.trading_handlers.get_simulated_trading_status()
            
            return {
                "is_trading": trading_status.get('is_trading', False),
                "active_strategy": trading_status.get('strategy_type'),
                "symbols": trading_status.get('symbols', []),
                "session_id": getattr(self.simulated_trading_manager, 'session_id', None)
            }
        except Exception as e:
            logger.error(f"Error getting trading state: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def save_current_trading_state(self, session_id: str) -> bool:
        """Save current trading state to database."""
        try:
            if not session_id:
                return False
                
            # Get current trading status
            trading_status = await self.trading_handlers.get_simulated_trading_status()
            
            # Prepare session data
            session_data = {
                'is_active': trading_status.get('is_trading', False),
                'trading_mode': 'simulated',
                'symbol_mode': 'universe' if len(trading_status.get('symbols', [])) > 1 else 'single',
                'strategy_type': trading_status.get('strategy_type'),
                'strategy_params': trading_status.get('strategy_params', {}),
                'symbols': trading_status.get('symbols', []),
                'universe_config': {},
                'portfolio_state': trading_status.get('portfolio', {}),
                'positions': trading_status.get('open_positions', []),
                'recent_trades': trading_status.get('recent_trades', [])
            }
            
            # Save to database
            success = self.database_manager.save_trading_session(session_id, session_data)
            
            if success:
                logger.debug(f"Auto-saved trading session {session_id}")
            
            return success
                
        except Exception as e:
            logger.error(f"Error auto-saving trading state: {e}")
            return False
    
    async def save_session_state(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save trading session state."""
        try:
            session_id = request_data.get('session_id')
            logger.info(f"Save session request received for session_id: {session_id}")
            
            if not session_id:
                raise HTTPException(status_code=400, detail="Session ID is required")
            
            # Get current trading status
            logger.info("Getting current trading status...")
            trading_status = await self.trading_handlers.get_simulated_trading_status()
            logger.info(f"Trading status retrieved: is_trading={trading_status.get('is_trading')}, total_trades={trading_status.get('portfolio', {}).get('total_trades')}")
            
            # Prepare session data
            session_data = {
                'is_active': trading_status.get('is_trading', False),
                'trading_mode': 'simulated',
                'symbol_mode': 'universe' if len(trading_status.get('symbols', [])) > 1 else 'single',
                'strategy_type': trading_status.get('strategy_type'),
                'strategy_params': trading_status.get('strategy_params', {}),
                'symbols': trading_status.get('symbols', []),
                'universe_config': {},
                'portfolio_state': trading_status.get('portfolio', {}),
                'positions': trading_status.get('open_positions', []),
                'recent_trades': trading_status.get('recent_trades', [])
            }
            
            # Save to database
            print(f"DEBUG: Attempting to save session {session_id} with data: {session_data}")
            logger.info(f"Attempting to save session {session_id} with data: {session_data}")
            try:
                # Test database connection first
                print("DEBUG: Testing database connection...")
                logger.info("Testing database connection...")
                test_result = self.database_manager.get_cache_stats()
                print(f"DEBUG: Database connection test result: {test_result}")
                logger.info(f"Database connection test result: {test_result}")
                
                success = self.database_manager.save_trading_session(session_id, session_data)
                print(f"DEBUG: Database save result: {success}")
                logger.info(f"Database save result: {success}")
                if not success:
                    print(f"DEBUG: Database save returned False for session {session_id}")
                    logger.error(f"Database save returned False for session {session_id}")
            except Exception as db_error:
                print(f"DEBUG: Database save exception: {db_error}")
                logger.error(f"Database save exception: {db_error}")
                import traceback
                print(f"DEBUG: Traceback: {traceback.format_exc()}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                return {"error": f"Database save failed: {str(db_error)}"}
            
            if success:
                logger.info(f"Saved trading session {session_id} with {len(session_data['positions'])} positions and {len(session_data['recent_trades'])} trades")
                return {
                    "status": "saved",
                    "session_id": session_id,
                    "message": "Session state saved successfully"
                }
            else:
                logger.error(f"Failed to save session {session_id}")
                return {"error": "Failed to save session state"}
                
        except Exception as e:
            logger.error(f"Error saving session state: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def restore_simulated_trading(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Restore simulated trading from saved state."""
        try:
            session_id = request_data.get('session_id')
            
            if not session_id:
                raise HTTPException(status_code=400, detail="Session ID is required")
            
            # Load session data from database
            session_data = self.database_manager.load_trading_session(session_id)
            if not session_data:
                raise HTTPException(status_code=404, detail="Session not found")
            
            # Extract trading parameters
            symbols = session_data.get('symbols', [])
            strategy_type = session_data.get('strategy_type', 'orderbook')
            strategy_params = session_data.get('strategy_params', {})
            portfolio_state = session_data.get('portfolio_state', {})
            positions = session_data.get('positions', [])
            recent_trades = session_data.get('recent_trades', [])
            
            # Restore simulated trading state
            self.simulated_trading_manager.restore_portfolio_state(
                portfolio_state=portfolio_state,
                positions=positions,
                trades=recent_trades,
                symbols=symbols
            )
            
            # Set session info for trade logging
            self.simulated_trading_manager.set_session_info(self.database_manager, session_id)
            
            # Set strategy info for trade logging
            self.simulated_trading_manager.set_strategy_info(strategy_type, strategy_params)
            
            # Start trading
            self.simulated_trading_manager.start_trading(symbols)
            
            # Get current portfolio summary
            portfolio = self.simulated_trading_manager.get_portfolio_summary()
            open_positions = self.simulated_trading_manager.get_open_positions()
            
            logger.info(f"Restored simulated trading for {len(symbols)} symbols with {len(open_positions)} positions")
            
            return {
                "status": "restored",
                "session_id": session_id,
                "symbols": symbols,
                "strategy_type": strategy_type,
                "portfolio": portfolio,
                "positions": open_positions,
                "recent_trades": recent_trades,
                "message": "Simulated trading restored successfully"
            }
        except Exception as e:
            logger.error(f"Error restoring simulated trading: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def load_session_state(self, session_id: str) -> Dict[str, Any]:
        """Load trading session state."""
        try:
            if not session_id:
                raise HTTPException(status_code=400, detail="Session ID is required")
            
            # Load session data from database
            session_data = self.database_manager.load_trading_session(session_id)
            if not session_data:
                return {
                    "session_id": session_id,
                    "state": {},
                    "message": "Session not found"
                }
            
            return {
                "session_id": session_id,
                "state": session_data,
                "message": "Session state loaded successfully"
            }
        except Exception as e:
            logger.error(f"Error loading session state: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def save_dashboard_state(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save dashboard UI state."""
        try:
            session_id = request_data.get('session_id')
            state_data = request_data.get('state', {})
            
            if not session_id:
                raise HTTPException(status_code=400, detail="Session ID is required")
            
            # Save dashboard state logic would go here
            return {
                "status": "saved",
                "session_id": session_id,
                "message": "Dashboard state saved successfully"
            }
        except Exception as e:
            logger.error(f"Error saving dashboard state: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def load_dashboard_state(self, session_id: str) -> Dict[str, Any]:
        """Load dashboard UI state."""
        try:
            if not session_id:
                raise HTTPException(status_code=400, detail="Session ID is required")
            
            # Load dashboard state logic would go here
            return {
                "session_id": session_id,
                "state": {},
                "message": "Dashboard state loaded successfully"
            }
        except Exception as e:
            logger.error(f"Error loading dashboard state: {e}")
            raise HTTPException(status_code=500, detail=str(e))
