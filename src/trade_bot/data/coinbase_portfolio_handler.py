"""
Coinbase Advanced Trade API portfolio data handler.

This module handles fetching and processing portfolio data from Coinbase Advanced Trade API
for live trading mode.
"""

import asyncio
import logging
import time
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from coinbase.rest import RESTClient

logger = logging.getLogger(__name__)

@dataclass
class CoinbaseAccount:
    """Represents a Coinbase account."""
    uuid: str
    name: str
    currency: str
    available_balance: float
    hold: float
    total_balance: float
    available_balance_obj: Dict[str, str] = None
    hold_obj: Dict[str, str] = None
    
    def __post_init__(self):
        if self.available_balance_obj is None:
            self.available_balance_obj = {"value": str(self.available_balance), "currency": self.currency}
        if self.hold_obj is None:
            self.hold_obj = {"value": str(self.hold), "currency": self.currency}

@dataclass
class CoinbasePortfolio:
    """Represents Coinbase portfolio data."""
    total_balance_usd: float
    total_balance_btc: float
    accounts: List[CoinbaseAccount]
    last_updated: datetime
    error: Optional[str] = None

class CoinbasePortfolioHandler:
    """Handles Coinbase Advanced Trade API portfolio data using official REST client."""
    
    def __init__(self, api_key: str = None, api_secret: str = None):
        self.api_key = api_key
        self.api_secret = api_secret
        
        # Check if credentials are available
        self.has_credentials = all([api_key, api_secret])
        
        if self.has_credentials:
            logger.info("Coinbase portfolio handler initialized with REST client credentials")
            # Validate API key format
            if not self.api_key.startswith('organizations/'):
                logger.warning("API key should be in format 'organizations/{org_id}/apiKeys/{key_id}'")
            if not self.api_secret.startswith('-----BEGIN EC PRIVATE KEY-----'):
                logger.warning("Private key should be in PEM format with proper headers")
            
            # Initialize REST client
            try:
                self.rest_client = RESTClient(api_key=api_key, api_secret=api_secret, verbose=True)
                logger.info("REST client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize REST client: {e}")
                self.rest_client = None
        else:
            logger.warning("Coinbase portfolio handler initialized without credentials - will use mock data")
            self.rest_client = None
    
    async def get_accounts(self) -> List[CoinbaseAccount]:
        """Get all Coinbase accounts using REST client."""
        if not self.has_credentials or not self.rest_client:
            logger.warning("No credentials or REST client available")
            return []
        
        try:
            # Use the official REST client
            accounts_response = self.rest_client.get_accounts()
            
            accounts = []
            for account_data in accounts_response.accounts:
                # Use the raw REST response structure directly
                available_balance_obj = account_data.available_balance if isinstance(account_data.available_balance, dict) else {"value": "0", "currency": account_data.currency}
                hold_obj = account_data.hold if isinstance(account_data.hold, dict) else {"value": "0", "currency": account_data.currency}
                
                # Calculate numeric values for compatibility
                available_balance_value = float(available_balance_obj['value']) if 'value' in available_balance_obj else 0.0
                hold_balance_value = float(hold_obj['value']) if 'value' in hold_obj else 0.0
                total_balance = available_balance_value + hold_balance_value
                
                account = CoinbaseAccount(
                    uuid=account_data.uuid,
                    name=account_data.name,
                    currency=account_data.currency,
                    available_balance=available_balance_value,
                    hold=hold_balance_value,
                    total_balance=total_balance,
                    available_balance_obj=available_balance_obj,
                    hold_obj=hold_obj
                )
                accounts.append(account)
            
            logger.info(f"Retrieved {len(accounts)} Coinbase accounts using REST client")
            return accounts
            
        except Exception as e:
            logger.error(f"Error getting Coinbase accounts: {e}")
            return []
    
    async def get_portfolio_summary(self) -> CoinbasePortfolio:
        """Get comprehensive portfolio summary from Coinbase."""
        try:
            if not self.has_credentials or not self.rest_client:
                logger.error("No Coinbase API credentials available for live trading")
                return CoinbasePortfolio(
                    total_balance_usd=0.0,
                    total_balance_btc=0.0,
                    accounts=[],
                    last_updated=datetime.now(),
                    error="No Coinbase API credentials configured. Please configure API credentials for live trading."
                )
            
            # Get all accounts using REST client
            accounts = await self.get_accounts()
            
            if not accounts:
                return CoinbasePortfolio(
                    total_balance_usd=0.0,
                    total_balance_btc=0.0,
                    accounts=[],
                    last_updated=datetime.now(),
                    error="No accounts found or API error"
                )
            
            # Calculate total balances
            total_usd = 0.0
            total_btc = 0.0
            
            for account in accounts:
                if account.currency == 'USD':
                    total_usd += account.total_balance
                elif account.currency == 'BTC':
                    total_btc += account.total_balance
                elif account.currency != 'USD' and account.currency != 'BTC':
                    # For other currencies, we'd need to convert to USD/BTC
                    # For now, just add the raw balance
                    total_usd += account.total_balance * 0.01  # Placeholder conversion
            
            portfolio = CoinbasePortfolio(
                total_balance_usd=total_usd,
                total_balance_btc=total_btc,
                accounts=accounts,
                last_updated=datetime.now()
            )
            
            logger.info(f"Portfolio summary: ${total_usd:.2f} USD, {total_btc:.8f} BTC")
            return portfolio
            
        except Exception as e:
            logger.error(f"Error getting portfolio summary: {e}")
            return CoinbasePortfolio(
                total_balance_usd=0.0,
                total_balance_btc=0.0,
                accounts=[],
                last_updated=datetime.now(),
                error=str(e)
            )
    
    def portfolio_to_dict(self, portfolio: CoinbasePortfolio) -> Dict[str, Any]:
        """Convert portfolio to dictionary for JSON serialization."""
        return {
            "total_balance_usd": portfolio.total_balance_usd,
            "total_balance_btc": portfolio.total_balance_btc,
            "accounts": [
                {
                    "uuid": account.uuid,
                    "name": account.name,
                    "currency": account.currency,
                    "available_balance": account.available_balance,
                    "hold": account.hold,
                    "total_balance": account.total_balance
                }
                for account in portfolio.accounts
            ],
            "last_updated": portfolio.last_updated.isoformat(),
            "error": portfolio.error,
            "has_credentials": self.has_credentials
        }
