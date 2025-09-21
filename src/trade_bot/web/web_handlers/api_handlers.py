"""API handlers for the trading web server."""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class APIHandlers:
    """Handles API-related functionality for the trading web server."""
    
    def __init__(self, config, data_provider, cached_data_provider, product_fetcher, 
                 database_manager, simulated_trading_manager):
        self.config = config
        self.data_provider = data_provider
        self.cached_data_provider = cached_data_provider
        self.product_fetcher = product_fetcher
        self.database_manager = database_manager
        self.simulated_trading_manager = simulated_trading_manager
    
    async def get_available_symbols(self) -> Dict[str, Any]:
        """Get available trading symbols."""
        try:
            symbols_response = await self.product_fetcher.get_available_products()
            if not symbols_response or 'symbols' not in symbols_response:
                return {"error": "No symbols available"}
            
            symbols = []
            for symbol in symbols_response['symbols']:
                if symbol.get('status') == 'online' and symbol.get('type') == 'spot':
                    symbols.append({
                        'symbol': symbol['symbol'],
                        'base_currency': symbol['base_currency'],
                        'quote_currency': symbol['quote_currency'],
                        'display_name': symbol['display_name'],
                        'status': symbol['status']
                    })
            
            return {"symbols": symbols}
        except Exception as e:
            logger.error(f"Error getting available symbols: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_available_products(self) -> Dict[str, Any]:
        """Get available products for trading."""
        try:
            products = await self.product_fetcher.fetch_all_products()
            categories = self.product_fetcher.get_products_by_category()
            return {
                "status": "success",
                "products": products,
                "categories": categories
            }
        except Exception as e:
            logger.error(f"Error getting available products: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_available_channels(self) -> Dict[str, Any]:
        """Get available WebSocket channels."""
        channels = [
            {"name": "ticker", "description": "Real-time price updates"},
            {"name": "level2", "description": "Order book updates"},
            {"name": "candles", "description": "OHLCV candle data"},
            {"name": "matches", "description": "Trade executions"},
            {"name": "status", "description": "Product status updates"},
            {"name": "market_trades", "description": "Market trade data"}
        ]
        return {"channels": channels}
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check endpoint."""
        try:
            # Check database connection
            db_status = "healthy"
            try:
                await self.database_manager.get_cache_stats()
            except Exception:
                db_status = "unhealthy"
            
            # Check data provider
            data_status = "healthy"
            try:
                # Simple check - could be more comprehensive
                pass
            except Exception:
                data_status = "unhealthy"
            
            return {
                "status": "healthy" if db_status == "healthy" and data_status == "healthy" else "degraded",
                "database": db_status,
                "data_provider": data_status,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
