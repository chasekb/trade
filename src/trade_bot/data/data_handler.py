"""Data handling and CSV output functionality with support for all WebSocket data types."""

import csv
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import os
import pandas as pd
import aiohttp
import asyncio
import base64
import hmac
import hashlib
import time
import json

from ..core.config import TradingConfig


logger = logging.getLogger(__name__)


class DataHandler:
    """Handles data storage and CSV output for all WebSocket data types."""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.ticker_data: List[Dict[str, Any]] = []
        self.trade_data: List[Dict[str, Any]] = []
        self.signal_data: List[Dict[str, Any]] = []
        self.level2_data: List[Dict[str, Any]] = []
        self.candles_data: List[Dict[str, Any]] = []
        self.matches_data: List[Dict[str, Any]] = []
        self.status_data: List[Dict[str, Any]] = []
        self.market_trades_data: List[Dict[str, Any]] = []
        
        # API configuration
        self.base_url = "https://api.coinbase.com/api/v3/brokerage"
        self.public_base_url = "https://api.exchange.coinbase.com"
        self.api_key = getattr(config, 'api_key', None)
        self.api_secret = getattr(config, 'api_secret', None)
        self.passphrase = getattr(config, 'passphrase', None)
        
        # Initialization logging without credential state
        logger.info("DataHandler initialized")
        
        # Ensure output directory exists
        os.makedirs(config.output_dir, exist_ok=True)
    
    def add_ticker_data(self, data: Dict[str, Any]) -> None:
        """Add ticker data point."""
        ticker_record = {
            'timestamp': datetime.now().isoformat(),
            'product_id': data.get('product_id', ''),
            'price': float(data.get('price', 0)),
            'volume_24h': float(data.get('volume_24h', 0)),
            'volume_30d': float(data.get('volume_30d', 0)),
            'best_bid': float(data.get('best_bid', 0)),
            'best_ask': float(data.get('best_ask', 0)),
            'side': data.get('side', ''),
            'time': data.get('time', ''),
            'trade_id': data.get('trade_id', ''),
            'last_size': float(data.get('last_size', 0))
        }
        self.ticker_data.append(ticker_record)
        logger.debug(f"Added ticker data: {ticker_record}")
    
    def add_trade_data(self, trade_info: Dict[str, Any]) -> None:
        """Add trade execution data."""
        trade_record = {
            'timestamp': datetime.now().isoformat(),
            'trade_id': trade_info.get('trade_id', ''),
            'product_id': trade_info.get('product_id', ''),
            'side': trade_info.get('side', ''),
            'price': float(trade_info.get('price', 0)),
            'size': float(trade_info.get('size', 0)),
            'value': float(trade_info.get('value', 0)),
            'fee': float(trade_info.get('fee', 0)),
            'status': trade_info.get('status', ''),
            'order_id': trade_info.get('order_id', '')
        }
        self.trade_data.append(trade_record)
        logger.info(f"Trade executed: {trade_record}")
    
    def add_signal_data(self, signal: Dict[str, Any]) -> None:
        """Add trading signal data."""
        signal_record = {
            'timestamp': signal.get('timestamp', datetime.now().isoformat()),
            'action': signal.get('action', ''),
            'price': float(signal.get('price', 0)),
            'quantity': float(signal.get('quantity', 0)),
            'reason': signal.get('reason', ''),
            'product_id': signal.get('product_id', '')
        }
        self.signal_data.append(signal_record)
        logger.info(f"Signal generated: {signal_record}")
    
    def add_level2_data(self, data: Dict[str, Any]) -> None:
        """Add level2 order book data."""
        level2_record = {
            'timestamp': datetime.now().isoformat(),
            'product_id': data.get('product_id', ''),
            'time': data.get('time', ''),
            'changes': data.get('changes', []),
            'sequence': data.get('sequence', 0)
        }
        self.level2_data.append(level2_record)
        logger.debug(f"Added level2 data: {level2_record}")
    
    def add_candles_data(self, data: Dict[str, Any]) -> None:
        """Add candlestick/OHLCV data."""
        candles_record = {
            'timestamp': datetime.now().isoformat(),
            'product_id': data.get('product_id', ''),
            'time': data.get('time', ''),
            'candles': data.get('candles', []),
            'granularity': data.get('granularity', 0)
        }
        self.candles_data.append(candles_record)
        logger.debug(f"Added candles data: {candles_record}")
    
    def add_matches_data(self, data: Dict[str, Any]) -> None:
        """Add trade matches data."""
        matches_record = {
            'timestamp': datetime.now().isoformat(),
            'product_id': data.get('product_id', ''),
            'time': data.get('time', ''),
            'matches': data.get('matches', []),
            'sequence': data.get('sequence', 0)
        }
        self.matches_data.append(matches_record)
        logger.debug(f"Added matches data: {matches_record}")
    
    def add_status_data(self, data: Dict[str, Any]) -> None:
        """Add product status data."""
        status_record = {
            'timestamp': datetime.now().isoformat(),
            'product_id': data.get('product_id', ''),
            'time': data.get('time', ''),
            'status': data.get('status', ''),
            'message': data.get('message', '')
        }
        self.status_data.append(status_record)
        logger.info(f"Status update: {status_record}")
    
    def add_market_trades_data(self, data: Dict[str, Any]) -> None:
        """Add market trades data."""
        market_trades_record = {
            'timestamp': datetime.now().isoformat(),
            'product_id': data.get('product_id', ''),
            'time': data.get('time', ''),
            'trades': data.get('trades', []),
            'sequence': data.get('sequence', 0)
        }
        self.market_trades_data.append(market_trades_record)
        logger.debug(f"Added market trades data: {market_trades_record}")
    
    def get_latest_ticker(self) -> Optional[Dict[str, Any]]:
        """Get the latest ticker data."""
        return self.ticker_data[-1] if self.ticker_data else None
    
    def get_latest_trades(self) -> List[Dict[str, Any]]:
        """Get the latest trade data."""
        return self.trade_data[-10:] if self.trade_data else []
    
    def get_latest_level2(self) -> Optional[Dict[str, Any]]:
        """Get the latest level2 data."""
        return self.level2_data[-1] if self.level2_data else None
    
    def get_latest_candles(self) -> Optional[Dict[str, Any]]:
        """Get the latest candles data."""
        return self.candles_data[-1] if self.candles_data else None
    
    def get_latest_matches(self) -> Optional[Dict[str, Any]]:
        """Get the latest matches data."""
        return self.matches_data[-1] if self.matches_data else None
    
    def get_latest_status(self) -> Optional[Dict[str, Any]]:
        """Get the latest status data."""
        return self.status_data[-1] if self.status_data else None
    
    def get_latest_market_trades(self) -> Optional[Dict[str, Any]]:
        """Get the latest market trades data."""
        return self.market_trades_data[-1] if self.market_trades_data else None
    
    def save_ticker_data(self) -> str:
        """Save ticker data to CSV."""
        if not self.ticker_data:
            return ""
            
        filename = os.path.join(
            self.config.output_dir, 
            f"ticker_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        df = pd.DataFrame(self.ticker_data)
        df.to_csv(filename, index=False)
        logger.info(f"Saved {len(self.ticker_data)} ticker records to {filename}")
        return filename
    
    def save_trade_data(self) -> str:
        """Save trade data to CSV."""
        if not self.trade_data:
            return ""
            
        filename = os.path.join(
            self.config.output_dir, 
            f"trade_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        df = pd.DataFrame(self.trade_data)
        df.to_csv(filename, index=False)
        logger.info(f"Saved {len(self.trade_data)} trade records to {filename}")
        return filename
    
    def save_signal_data(self) -> str:
        """Save signal data to CSV."""
        if not self.signal_data:
            return ""
            
        filename = os.path.join(
            self.config.output_dir, 
            f"signal_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        df = pd.DataFrame(self.signal_data)
        df.to_csv(filename, index=False)
        logger.info(f"Saved {len(self.signal_data)} signal records to {filename}")
        return filename
    
    def save_level2_data(self) -> str:
        """Save level2 data to CSV."""
        if not self.level2_data:
            return ""
            
        filename = os.path.join(
            self.config.output_dir, 
            f"level2_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        df = pd.DataFrame(self.level2_data)
        df.to_csv(filename, index=False)
        logger.info(f"Saved {len(self.level2_data)} level2 records to {filename}")
        return filename
    
    def save_candles_data(self) -> str:
        """Save candles data to CSV."""
        if not self.candles_data:
            return ""
            
        filename = os.path.join(
            self.config.output_dir, 
            f"candles_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        df = pd.DataFrame(self.candles_data)
        df.to_csv(filename, index=False)
        logger.info(f"Saved {len(self.candles_data)} candles records to {filename}")
        return filename
    
    def save_matches_data(self) -> str:
        """Save matches data to CSV."""
        if not self.matches_data:
            return ""
            
        filename = os.path.join(
            self.config.output_dir, 
            f"matches_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        df = pd.DataFrame(self.matches_data)
        df.to_csv(filename, index=False)
        logger.info(f"Saved {len(self.matches_data)} matches records to {filename}")
        return filename
    
    def save_status_data(self) -> str:
        """Save status data to CSV."""
        if not self.status_data:
            return ""
            
        filename = os.path.join(
            self.config.output_dir, 
            f"status_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        df = pd.DataFrame(self.status_data)
        df.to_csv(filename, index=False)
        logger.info(f"Saved {len(self.status_data)} status records to {filename}")
        return filename
    
    def save_market_trades_data(self) -> str:
        """Save market trades data to CSV."""
        if not self.market_trades_data:
            return ""
            
        filename = os.path.join(
            self.config.output_dir, 
            f"market_trades_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        df = pd.DataFrame(self.market_trades_data)
        df.to_csv(filename, index=False)
        logger.info(f"Saved {len(self.market_trades_data)} market trades records to {filename}")
        return filename
    
    def save_all_data(self) -> Dict[str, str]:
        """Save all data to CSV files."""
        files = {}
        
        if self.ticker_data:
            files['ticker'] = self.save_ticker_data()
        if self.trade_data:
            files['trades'] = self.save_trade_data()
        if self.signal_data:
            files['signals'] = self.save_signal_data()
        if self.level2_data:
            files['level2'] = self.save_level2_data()
        if self.candles_data:
            files['candles'] = self.save_candles_data()
        if self.matches_data:
            files['matches'] = self.save_matches_data()
        if self.status_data:
            files['status'] = self.save_status_data()
        if self.market_trades_data:
            files['market_trades'] = self.save_market_trades_data()
            
        return files
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics for all data types."""
        stats = {
            'ticker_records': len(self.ticker_data),
            'trade_records': len(self.trade_data),
            'signal_records': len(self.signal_data),
            'level2_records': len(self.level2_data),
            'candles_records': len(self.candles_data),
            'matches_records': len(self.matches_data),
            'status_records': len(self.status_data),
            'market_trades_records': len(self.market_trades_data)
        }
        
        if self.trade_data:
            df = pd.DataFrame(self.trade_data)
            stats['total_trades'] = len(df)
            stats['total_volume'] = df['size'].sum()
            stats['total_value'] = df['value'].sum()
            stats['total_fees'] = df['fee'].sum()
            
            if 'price' in df.columns:
                stats['avg_price'] = df['price'].mean()
                stats['min_price'] = df['price'].min()
                stats['max_price'] = df['price'].max()
        
        return stats
    
    def _generate_jwt_token(self, method: str, uri: str) -> str:
        """Generate JWT token for Coinbase Advanced Trade API authentication."""
        try:
            from coinbase import jwt_generator
            
            # Format the JWT URI according to the SDK
            jwt_uri = jwt_generator.format_jwt_uri(method, uri)
            
            # Build the JWT token using the official SDK
            jwt = jwt_generator.build_rest_jwt(jwt_uri, self.api_key, self.api_secret)
            
            return jwt
        except ImportError:
            logger.error("coinbase-advanced-py package not installed. Install with: pip install coinbase-advanced-py")
            return None
        except Exception as e:
            logger.error(f"Error generating JWT token: {e}")
            return None
    
    def _create_auth_headers(self, method: str, path: str, body: str = "") -> Dict[str, str]:
        """Create authentication headers for Coinbase Advanced Trade API using JWT."""
        if not all([self.api_key, self.api_secret]):
            logger.warning("API credentials not configured, using public endpoints only")
            return {}
        
        logger.info("Creating JWT token for authenticated request")
        jwt_token = self._generate_jwt_token(method, path)
        if not jwt_token:
            logger.warning("Failed to generate JWT token, using public endpoints only")
            return {}
        
        logger.debug("Generated JWT token")
        
        return {
            'Authorization': f'Bearer {jwt_token}',
            'Content-Type': 'application/json'
        }
    
    async def _make_api_request(self, method: str, endpoint: str, params: Dict[str, Any] = None, use_auth: bool = True) -> Optional[Dict[str, Any]]:
        """Make API request to Coinbase Advanced Trade API."""
        try:
            url = f"{self.base_url}{endpoint}"
            headers = {}
            
            if use_auth and all([self.api_key, self.api_secret]):
                logger.info(f"Making authenticated API request to {endpoint}")
                headers = self._create_auth_headers(method, endpoint)
            else:
                headers = {'Content-Type': 'application/json'}
                logger.info(f"Making public API request to {endpoint}")
            
            async with aiohttp.ClientSession() as session:
                if method.upper() == 'GET':
                    async with session.get(url, headers=headers, params=params) as response:
                        if response.status == 200:
                            return await response.json()
                        elif response.status == 401:
                            logger.warning(f"Authentication required for {endpoint}, trying public endpoint")
                            return None
                        else:
                            logger.error(f"API request failed: {response.status} - {await response.text()}")
                            return None
                else:
                    async with session.post(url, headers=headers, json=params) as response:
                        if response.status == 200:
                            return await response.json()
                        elif response.status == 401:
                            logger.warning(f"Authentication required for {endpoint}, trying public endpoint")
                            return None
                        else:
                            logger.error(f"API request failed: {response.status} - {await response.text()}")
                            return None
        except Exception as e:
            logger.error(f"Error making API request: {e}")
            return None
    
    async def _make_public_api_request(self, endpoint: str, params: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """Make public API request to Coinbase Pro (no authentication required)."""
        try:
            url = f"{self.public_base_url}{endpoint}"
            headers = {'Content-Type': 'application/json'}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"Public API request failed: {response.status} - {await response.text()}")
                        return None
        except Exception as e:
            logger.error(f"Error making public API request: {e}")
            return None
    
    async def get_product_book(self, product_id: str, limit: int = 20) -> Optional[Dict[str, Any]]:
        """Get product book data from Coinbase API."""
        try:
            # Try authenticated API first
            endpoint = "/product_book"
            params = {
                'product_id': product_id,
                'limit': limit
            }
            
            response = await self._make_api_request('GET', endpoint, params, use_auth=True)
            if response and 'pricebook' in response:
                logger.info(f"Retrieved product book data for {product_id} from authenticated API")
                return response['pricebook']
            
            # Fallback to public API
            logger.info(f"Trying public API for product book data for {product_id}")
            public_endpoint = f"/products/{product_id}/book"
            public_params = {'level': 2}
            
            response = await self._make_public_api_request(public_endpoint, public_params)
            if response:
                # Convert public API format to match expected format
                # Public API returns bids/asks as arrays of [price, size]
                # We need to convert to arrays of {price, size} objects
                bids = []
                for bid in response.get('bids', []):
                    if len(bid) >= 2:
                        bids.append({'price': str(bid[0]), 'size': str(bid[1])})
                
                asks = []
                for ask in response.get('asks', []):
                    if len(ask) >= 2:
                        asks.append({'price': str(ask[0]), 'size': str(ask[1])})
                
                order_book = {
                    'product_id': product_id,
                    'bids': bids,
                    'asks': asks,
                    'time': response.get('time', datetime.now().isoformat())
                }
                logger.info(f"Retrieved product book data for {product_id} from public API")
                return order_book
            else:
                logger.warning(f"No product book data available for {product_id}")
                return None
            
        except Exception as e:
            logger.error(f"Error getting product book for {product_id}: {e}")
            return None
    
    async def get_historical_candles(self, product_id: str, start_time: int, end_time: int, granularity: int = 60) -> List[Dict[str, Any]]:
        """Get historical candles from Coinbase API."""
        try:
            # Try authenticated API first
            endpoint = "/product_candles"
            params = {
                'product_id': product_id,
                'start': start_time,
                'end': end_time,
                'granularity': granularity
            }
            
            response = await self._make_api_request('GET', endpoint, params, use_auth=True)
            if response and 'candles' in response:
                logger.info(f"Retrieved {len(response['candles'])} historical candles for {product_id} from authenticated API")
                return response['candles']
            
            # Fallback to public API
            logger.info(f"Trying public API for historical candles for {product_id}")
            public_endpoint = f"/products/{product_id}/candles"
            public_params = {
                'start': datetime.fromtimestamp(start_time).isoformat(),
                'end': datetime.fromtimestamp(end_time).isoformat(),
                'granularity': granularity
            }
            
            response = await self._make_public_api_request(public_endpoint, public_params)
            if response:
                # Convert public API format to match expected format
                candles = []
                for candle in response:
                    candles.append({
                        'time': datetime.fromtimestamp(candle[0]).isoformat(),
                        'low': str(candle[1]),
                        'high': str(candle[2]),
                        'open': str(candle[3]),
                        'close': str(candle[4]),
                        'volume': str(candle[5])
                    })
                logger.info(f"Retrieved {len(candles)} historical candles for {product_id} from public API")
                return candles
            else:
                logger.warning(f"No historical candles data available for {product_id}")
                return []
            
        except Exception as e:
            logger.error(f"Error getting historical candles for {product_id}: {e}")
            return []
    
    async def get_recent_trades(self, product_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent trades from Coinbase API."""
        try:
            # Try authenticated API first
            endpoint = "/market_trades"
            params = {
                'product_id': product_id,
                'limit': limit
            }
            
            response = await self._make_api_request('GET', endpoint, params, use_auth=True)
            if response and 'trades' in response:
                logger.info(f"Retrieved {len(response['trades'])} recent trades for {product_id} from authenticated API")
                return response['trades']
            
            # Fallback to public API
            logger.info(f"Trying public API for recent trades for {product_id}")
            public_endpoint = f"/products/{product_id}/trades"
            public_params = {'limit': limit}
            
            response = await self._make_public_api_request(public_endpoint, public_params)
            if response:
                # Convert public API format to match expected format
                trades = []
                for trade in response:
                    trades.append({
                        'trade_id': trade.get('trade_id', ''),
                        'product_id': product_id,
                        'price': str(trade.get('price', '0')),
                        'size': str(trade.get('size', '0')),
                        'side': trade.get('side', ''),
                        'time': trade.get('time', datetime.now().isoformat())
                    })
                logger.info(f"Retrieved {len(trades)} recent trades for {product_id} from public API")
                return trades
            else:
                logger.warning(f"No recent trades data available for {product_id}")
                return []
            
        except Exception as e:
            logger.error(f"Error getting recent trades for {product_id}: {e}")
            return []
    
    async def get_product_info(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Get product information from Coinbase Advanced Trade API."""
        try:
            endpoint = f"/products/{product_id}"
            
            response = await self._make_api_request('GET', endpoint)
            if response and 'product' in response:
                logger.info(f"Retrieved product info for {product_id}")
                return response['product']
            else:
                logger.warning(f"No product info available for {product_id}")
                return None
            
        except Exception as e:
            logger.error(f"Error getting product info for {product_id}: {e}")
            return None
    
    async def get_best_bid_ask(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Get best bid/ask prices from Coinbase Advanced Trade API."""
        try:
            endpoint = "/best_bid_ask"
            params = {'product_ids': product_id}
            
            response = await self._make_api_request('GET', endpoint, params)
            if response and 'pricebooks' in response and response['pricebooks']:
                logger.info(f"Retrieved best bid/ask for {product_id}")
                return response['pricebooks'][0]
            else:
                logger.warning(f"No best bid/ask data available for {product_id}")
                return None
            
        except Exception as e:
            logger.error(f"Error getting best bid/ask for {product_id}: {e}")
            return None
    
    async def get_products(self) -> List[Dict[str, Any]]:
        """Get list of all available products from Coinbase API."""
        try:
            # Try authenticated API first
            endpoint = "/products"
            
            response = await self._make_api_request('GET', endpoint, use_auth=True)
            if response and 'products' in response:
                logger.info(f"Retrieved {len(response['products'])} products from authenticated API")
                return response['products']
            
            # Fallback to public API
            logger.info("Trying public API for products list")
            public_endpoint = "/products"
            
            response = await self._make_public_api_request(public_endpoint)
            if response:
                # Convert public API format to match expected format
                products = []
                for product in response:
                    products.append({
                        'product_id': product.get('id', ''),
                        'base_currency_id': product.get('base_currency', ''),
                        'quote_currency_id': product.get('quote_currency', ''),
                        'display_name': product.get('display_name', ''),
                        'status': product.get('status', ''),
                        'trading_disabled': product.get('trading_disabled', False)
                    })
                logger.info(f"Retrieved {len(products)} products from public API")
                return products
            else:
                logger.warning("No products data available")
                return []
            
        except Exception as e:
            logger.error(f"Error getting products: {e}")
            return []
