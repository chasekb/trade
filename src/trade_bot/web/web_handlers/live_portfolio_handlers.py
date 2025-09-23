"""
Live portfolio handlers for the trading web server.

This module handles live trading portfolio data from Coinbase API.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import HTTPException

from ...data.coinbase_portfolio_handler import CoinbasePortfolioHandler

logger = logging.getLogger(__name__)

class LivePortfolioHandlers:
    """Handles live trading portfolio functionality."""
    
    def __init__(self, config, coinbase_portfolio_handler: CoinbasePortfolioHandler = None):
        self.config = config
        self.coinbase_portfolio_handler = coinbase_portfolio_handler or CoinbasePortfolioHandler(
            api_key=getattr(config, 'api_key', None),
            api_secret=getattr(config, 'api_secret', None),
            passphrase=getattr(config, 'passphrase', None)
        )
        self.last_portfolio_update = None
        self.cached_portfolio = None
    
    async def get_live_portfolio_status(self) -> Dict[str, Any]:
        """Get live portfolio status from Coinbase API."""
        try:
            # Check if we have cached data that's still fresh (less than 30 seconds old)
            if (self.cached_portfolio and self.last_portfolio_update and 
                (datetime.now() - self.last_portfolio_update).seconds < 30):
                logger.debug("Using cached portfolio data")
                return self.cached_portfolio
            
            # Fetch fresh portfolio data from Coinbase API
            portfolio = await self.coinbase_portfolio_handler.get_portfolio_summary()
            
            # Convert to dictionary
            portfolio_dict = self.coinbase_portfolio_handler.portfolio_to_dict(portfolio)
            
            # Add additional computed fields
            portfolio_dict.update({
                "is_live_trading": True,
                "data_source": "coinbase_api" if self.coinbase_portfolio_handler.has_credentials else "mock_data",
                "total_accounts": len(portfolio.accounts),
                "usd_accounts": len([acc for acc in portfolio.accounts if acc.currency == "USD"]),
                "crypto_accounts": len([acc for acc in portfolio.accounts if acc.currency != "USD"])
            })
            
            # Cache the result
            self.cached_portfolio = portfolio_dict
            self.last_portfolio_update = datetime.now()
            
            logger.info(f"Live portfolio status retrieved: ${portfolio.total_balance_usd:.2f} USD, {portfolio.total_balance_btc:.8f} BTC")
            return portfolio_dict
            
        except Exception as e:
            logger.error(f"Error getting live portfolio status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_account_details(self, account_uuid: str = None) -> Dict[str, Any]:
        """Get detailed account information."""
        try:
            accounts = await self.coinbase_portfolio_handler.get_accounts()
            
            if account_uuid:
                # Return specific account
                account = next((acc for acc in accounts if acc.uuid == account_uuid), None)
                if not account:
                    raise HTTPException(status_code=404, detail="Account not found")
                
                return {
                    "account": {
                        "uuid": account.uuid,
                        "name": account.name,
                        "currency": account.currency,
                        "available_balance": account.available_balance,
                        "hold": account.hold,
                        "total_balance": account.total_balance
                    },
                    "is_live_trading": True,
                    "data_source": "coinbase_api" if self.coinbase_portfolio_handler.has_credentials else "mock_data"
                }
            else:
                # Return all accounts
                return {
                    "accounts": [
                        {
                            "uuid": account.uuid,
                            "name": account.name,
                            "currency": account.currency,
                            "available_balance": account.available_balance,
                            "hold": account.hold,
                            "total_balance": account.total_balance
                        }
                        for account in accounts
                    ],
                    "total_accounts": len(accounts),
                    "is_live_trading": True,
                    "data_source": "coinbase_api" if self.coinbase_portfolio_handler.has_credentials else "mock_data"
                }
                
        except Exception as e:
            logger.error(f"Error getting account details: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_portfolio_summary_for_frontend(self) -> Dict[str, Any]:
        """Get portfolio summary formatted for frontend display."""
        try:
            portfolio_data = await self.get_live_portfolio_status()
            
            # Format for frontend compatibility
            frontend_data = {
                "portfolio": {
                    "cash_balance": portfolio_data.get("total_balance_usd", 0.0),
                    "total_value": portfolio_data.get("total_balance_usd", 0.0),
                    "total_pnl": 0.0,  # Would need historical data to calculate
                    "total_fees": 0.0,  # Would need trade history
                    "max_drawdown": 0.0,  # Would need historical data
                    "win_rate": 0.0,  # Would need trade history
                    "total_trades": 0,  # Would need trade history
                    "winning_trades": 0,  # Would need trade history
                    "btc_balance": portfolio_data.get("total_balance_btc", 0.0),
                    "total_accounts": portfolio_data.get("total_accounts", 0),
                    "data_source": portfolio_data.get("data_source", "unknown")
                },
                "accounts": portfolio_data.get("accounts", []),
                "is_live_trading": True,
                "last_updated": portfolio_data.get("last_updated"),
                "error": portfolio_data.get("error")
            }
            
            return frontend_data
            
        except Exception as e:
            logger.error(f"Error formatting portfolio for frontend: {e}")
            raise HTTPException(status_code=500, detail=str(e))
