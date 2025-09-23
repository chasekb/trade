"""
Coinbase Advanced Trade API portfolio data handler.

This module handles fetching and processing portfolio data from Coinbase Advanced Trade API
for live trading mode.
"""

import asyncio
import aiohttp
import logging
import base64
import hmac
import hashlib
import time
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class CoinbaseAccount:
    """Represents a Coinbase account."""
    uuid: str
    name: str
    currency: str
    available_balance: Dict[str, str]  # {"value": "1000.00", "currency": "USD"}
    hold: Dict[str, str]
    total_balance: Dict[str, str]

@dataclass
class CoinbasePortfolio:
    """Represents Coinbase portfolio data."""
    total_balance_usd: float
    total_balance_btc: float
    accounts: List[CoinbaseAccount]
    last_updated: datetime
    error: Optional[str] = None

class CoinbasePortfolioHandler:
    """Handles Coinbase Advanced Trade API portfolio data."""
    
    def __init__(self, api_key: str = None, api_secret: str = None, passphrase: str = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.base_url = "https://api.coinbase.com/api/v3/brokerage"
        
        # Check if credentials are available
        self.has_credentials = all([api_key, api_secret, passphrase])
        
        if self.has_credentials:
            logger.info("Coinbase portfolio handler initialized with credentials")
        else:
            logger.warning("Coinbase portfolio handler initialized without credentials - will use mock data")
    
    def _create_auth_headers(self, method: str, path: str, body: str = "") -> Dict[str, str]:
        """Create authentication headers for Coinbase API."""
        if not self.has_credentials:
            return {}
        
        timestamp = str(int(time.time()))
        message = timestamp + method.upper() + path + body
        
        # Decode the base64 secret
        secret = base64.b64decode(self.api_secret)
        
        # Create signature
        signature = hmac.new(secret, message.encode('utf-8'), hashlib.sha256).digest()
        signature_b64 = base64.b64encode(signature).decode('utf-8')
        
        return {
            'CB-ACCESS-KEY': self.api_key,
            'CB-ACCESS-SIGN': signature_b64,
            'CB-ACCESS-TIMESTAMP': timestamp,
            'CB-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        }
    
    async def _make_api_request(self, method: str, endpoint: str, params: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """Make authenticated API request to Coinbase Advanced Trade API."""
        if not self.has_credentials:
            logger.warning("No credentials available for Coinbase API request")
            return None
        
        try:
            url = f"{self.base_url}{endpoint}"
            body = json.dumps(params) if params else ""
            headers = self._create_auth_headers(method, endpoint, body)
            
            async with aiohttp.ClientSession() as session:
                if method.upper() == 'GET':
                    async with session.get(url, headers=headers, params=params) as response:
                        if response.status == 200:
                            return await response.json()
                        elif response.status == 401:
                            logger.error("Coinbase API authentication failed")
                            return None
                        else:
                            error_text = await response.text()
                            logger.error(f"Coinbase API request failed: {response.status} - {error_text}")
                            return None
                else:
                    async with session.post(url, headers=headers, json=params) as response:
                        if response.status == 200:
                            return await response.json()
                        elif response.status == 401:
                            logger.error("Coinbase API authentication failed")
                            return None
                        else:
                            error_text = await response.text()
                            logger.error(f"Coinbase API request failed: {response.status} - {error_text}")
                            return None
        except Exception as e:
            logger.error(f"Error making Coinbase API request: {e}")
            return None
    
    async def get_accounts(self) -> List[CoinbaseAccount]:
        """Get all Coinbase accounts."""
        try:
            data = await self._make_api_request('GET', '/accounts')
            if not data:
                return []
            
            accounts = []
            for account_data in data.get('accounts', []):
                account = CoinbaseAccount(
                    uuid=account_data.get('uuid', ''),
                    name=account_data.get('name', ''),
                    currency=account_data.get('currency', ''),
                    available_balance=account_data.get('available_balance', {}),
                    hold=account_data.get('hold', {}),
                    total_balance=account_data.get('total_balance', {})
                )
                accounts.append(account)
            
            logger.info(f"Retrieved {len(accounts)} Coinbase accounts")
            return accounts
            
        except Exception as e:
            logger.error(f"Error getting Coinbase accounts: {e}")
            return []
    
    async def get_portfolio_summary(self) -> CoinbasePortfolio:
        """Get comprehensive portfolio summary from Coinbase."""
        try:
            if not self.has_credentials:
                logger.error("No Coinbase API credentials available for live trading")
                return CoinbasePortfolio(
                    total_balance_usd=0.0,
                    total_balance_btc=0.0,
                    accounts=[],
                    last_updated=datetime.now(),
                    error="No Coinbase API credentials configured. Please configure API credentials for live trading."
                )
            
            # Get all accounts
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
                balance = account.total_balance
                if balance:
                    value = float(balance.get('value', 0))
                    currency = balance.get('currency', '')
                    
                    if currency == 'USD':
                        total_usd += value
                    elif currency == 'BTC':
                        total_btc += value
                    # For other currencies, we'd need to convert to USD/BTC
                    # This would require additional API calls to get exchange rates
            
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
