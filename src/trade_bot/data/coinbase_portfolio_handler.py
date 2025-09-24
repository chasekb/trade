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
    available_balance_usd: Optional[float] = None
    total_unrealized_pnl: Optional[float] = None
    portfolio_breakdown: Optional[Dict[str, Any]] = None
    active_positions: Optional[List[Dict[str, Any]]] = None

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
            
            # Get portfolio breakdown for accurate data
            portfolios = self.rest_client.get_portfolios()
            if not portfolios.portfolios:
                return CoinbasePortfolio(
                    total_balance_usd=0.0,
                    total_balance_btc=0.0,
                    accounts=[],
                    last_updated=datetime.now(),
                    error="No portfolios found"
                )
            
            # Use the first portfolio (usually "Default")
            portfolio_uuid = portfolios.portfolios[0].uuid
            breakdown = self.rest_client.get_portfolio_breakdown(portfolio_uuid)
            
            # Extract portfolio data
            portfolio_balances = breakdown.breakdown['portfolio_balances']
            spot_positions = breakdown.breakdown['spot_positions']
            
            # Get total balance in USD
            total_balance_usd = float(portfolio_balances['total_balance']['value'])
            
            # Calculate available balance (cash + available to trade)
            total_cash_balance = float(portfolio_balances['total_cash_equivalent_balance']['value'])
            available_balance = total_cash_balance
            
            # Calculate 24h P&L (sum of unrealized P&L for all positions)
            total_unrealized_pnl = 0.0
            for position in spot_positions:
                # Handle both dict and object access
                if hasattr(position, 'unrealized_pnl'):
                    total_unrealized_pnl += position.unrealized_pnl
                elif isinstance(position, dict):
                    total_unrealized_pnl += position.get('unrealized_pnl', 0.0)
            
            # Get BTC balance specifically
            btc_balance = 0.0
            for position in spot_positions:
                # Handle both dict and object access
                asset = position.asset if hasattr(position, 'asset') else position.get('asset', '')
                if asset == 'BTC':
                    btc_balance = position.total_balance_crypto if hasattr(position, 'total_balance_crypto') else position.get('total_balance_crypto', 0.0)
                    break
            
            # Get all accounts for compatibility
            accounts = await self.get_accounts()
            
            # Extract active positions (non-zero balances)
            active_positions = []
            for position in spot_positions:
                # Handle both dict and object access
                if hasattr(position, 'total_balance_crypto'):
                    balance_crypto = position.total_balance_crypto
                    balance_fiat = position.total_balance_fiat
                    asset = position.asset
                    unrealized_pnl = position.unrealized_pnl
                    allocation = position.allocation
                elif isinstance(position, dict):
                    balance_crypto = position.get('total_balance_crypto', 0.0)
                    balance_fiat = position.get('total_balance_fiat', 0.0)
                    asset = position.get('asset', '')
                    unrealized_pnl = position.get('unrealized_pnl', 0.0)
                    allocation = position.get('allocation', 0.0)
                else:
                    continue
                
                # Only include positions with non-zero balance
                if balance_crypto > 0 or balance_fiat > 0:
                    active_positions.append({
                        'asset': asset,
                        'balance_crypto': balance_crypto,
                        'balance_fiat': balance_fiat,
                        'unrealized_pnl': unrealized_pnl,
                        'allocation': allocation,
                        'is_cash': asset in ['USD', 'USDC']
                    })
            
            portfolio = CoinbasePortfolio(
                total_balance_usd=total_balance_usd,
                total_balance_btc=btc_balance,
                accounts=accounts,
                last_updated=datetime.now(),
                # Add new fields for accurate portfolio data
                available_balance_usd=available_balance,
                total_unrealized_pnl=total_unrealized_pnl,
                portfolio_breakdown=breakdown.breakdown,
                active_positions=active_positions
            )
            
            logger.info(f"Portfolio summary: ${total_balance_usd:.2f} USD, {btc_balance:.8f} BTC, P&L: ${total_unrealized_pnl:.2f}")
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
            "available_balance_usd": portfolio.available_balance_usd,
            "total_unrealized_pnl": portfolio.total_unrealized_pnl,
            "active_positions": portfolio.active_positions or [],
            "accounts": [
                {
                    "uuid": account.uuid,
                    "name": account.name,
                    "currency": account.currency,
                    "available_balance": account.available_balance,
                    "hold": account.hold,
                    "total_balance": account.total_balance,
                    "available_balance_obj": account.available_balance_obj,
                    "hold_obj": account.hold_obj
                }
                for account in portfolio.accounts
            ],
            "last_updated": portfolio.last_updated.isoformat(),
            "error": portfolio.error,
            "has_credentials": self.has_credentials
        }
