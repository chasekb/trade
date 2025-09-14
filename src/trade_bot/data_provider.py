"""Data provider for historical market data."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import aiohttp
import json


class CoinbaseDataProvider:
    """Data provider for Coinbase historical data."""
    
    def __init__(self, product_id: str = "BTC-USD"):
        """Initialize the data provider.
        
        Args:
            product_id: Trading pair (e.g., "BTC-USD")
        """
        self.product_id = product_id
        self.base_url = "https://api.exchange.coinbase.com"
        self.logger = logging.getLogger(__name__)
    
    async def get_historical_candles(self, 
                                   start_time: datetime, 
                                   end_time: datetime, 
                                   granularity: int = 60) -> List[Dict[str, Any]]:
        """Get historical candle data.
        
        Args:
            start_time: Start time for data
            end_time: End time for data
            granularity: Candle granularity in seconds (60, 300, 900, 3600, 21600, 86400)
            
        Returns:
            List of candle data
        """
        self.logger.info(f"Fetching historical data for {self.product_id} from {start_time} to {end_time}")
        
        # Convert to ISO format
        start_iso = start_time.isoformat()
        end_iso = end_time.isoformat()
        
        url = f"{self.base_url}/products/{self.product_id}/candles"
        params = {
            'start': start_iso,
            'end': end_iso,
            'granularity': granularity
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.logger.info(f"Retrieved {len(data)} candles")
                        return self._process_candle_data(data)
                    else:
                        error_text = await response.text()
                        self.logger.error(f"Failed to fetch data: {response.status} - {error_text}")
                        
                        # Try with a shorter time range if the request failed
                        if response.status == 400:
                            self.logger.info("Trying with a shorter time range...")
                            mid_time = start_time + (end_time - start_time) / 2
                            return await self.get_historical_candles(start_time, mid_time, granularity)
                        
                        return []
        except Exception as e:
            self.logger.error(f"Error fetching data: {e}")
            return []
    
    def _process_candle_data(self, raw_data: List[List]) -> List[Dict[str, Any]]:
        """Process raw candle data into our format.
        
        Args:
            raw_data: Raw candle data from Coinbase API
            
        Returns:
            Processed candle data
        """
        processed_data = []
        
        for candle in raw_data:
            # Coinbase candle format: [timestamp, low, high, open, close, volume]
            timestamp = datetime.fromtimestamp(candle[0])
            
            processed_candle = {
                'timestamp': timestamp.isoformat() + 'Z',
                'open': candle[3],
                'high': candle[2],
                'low': candle[1],
                'close': candle[4],
                'volume': candle[5],
                'price': candle[4]  # Use close price as the price
            }
            processed_data.append(processed_candle)
        
        # Sort by timestamp
        processed_data.sort(key=lambda x: x['timestamp'])
        return processed_data
    
    async def get_historical_trades(self, 
                                  start_time: datetime, 
                                  end_time: datetime,
                                  limit: int = 100) -> List[Dict[str, Any]]:
        """Get historical trade data.
        
        Args:
            start_time: Start time for data
            end_time: End time for data
            limit: Maximum number of trades to fetch
            
        Returns:
            List of trade data
        """
        self.logger.info(f"Fetching historical trades for {self.product_id}")
        
        url = f"{self.base_url}/products/{self.product_id}/trades"
        params = {
            'start': start_time.isoformat(),
            'end': end_time.isoformat(),
            'limit': limit
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    self.logger.info(f"Retrieved {len(data)} trades")
                    return self._process_trade_data(data)
                else:
                    self.logger.error(f"Failed to fetch trades: {response.status}")
                    return []
    
    def _process_trade_data(self, raw_data: List[Dict]) -> List[Dict[str, Any]]:
        """Process raw trade data into our format.
        
        Args:
            raw_data: Raw trade data from Coinbase API
            
        Returns:
            Processed trade data
        """
        processed_data = []
        
        for trade in raw_data:
            processed_trade = {
                'timestamp': trade['time'],
                'price': float(trade['price']),
                'size': float(trade['size']),
                'side': trade['side'],
                'trade_id': trade['trade_id']
            }
            processed_data.append(processed_trade)
        
        # Sort by timestamp
        processed_data.sort(key=lambda x: x['timestamp'])
        return processed_data
    
    async def get_order_book(self, level: int = 2) -> Dict[str, Any]:
        """Get current order book data.
        
        Args:
            level: Order book level (1, 2, or 3)
            
        Returns:
            Order book data with bids and asks
        """
        self.logger.info(f"Fetching order book for {self.product_id} (level {level})")
        
        url = f"{self.base_url}/products/{self.product_id}/book"
        params = {'level': level}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.logger.info(f"Retrieved order book with {len(data.get('bids', []))} bids and {len(data.get('asks', []))} asks")
                        return self._process_order_book_data(data)
                    else:
                        error_text = await response.text()
                        self.logger.error(f"Failed to fetch order book: {response.status} - {error_text}")
                        return {}
        except Exception as e:
            self.logger.error(f"Error fetching order book: {e}")
            return {}
    
    def _process_order_book_data(self, raw_data: Dict) -> Dict[str, Any]:
        """Process raw order book data into our format.
        
        Args:
            raw_data: Raw order book data from Coinbase API
            
        Returns:
            Processed order book data
        """
        processed_data = {
            'bids': [],
            'asks': [],
            'timestamp': raw_data.get('time', datetime.now().isoformat()),
            'product_id': self.product_id
        }
        
        # Process bids (buy orders)
        for bid in raw_data.get('bids', []):
            if len(bid) >= 2:
                processed_data['bids'].append({
                    'price': float(bid[0]),
                    'size': float(bid[1]),
                    'order_id': bid[2] if len(bid) > 2 else None
                })
        
        # Process asks (sell orders)
        for ask in raw_data.get('asks', []):
            if len(ask) >= 2:
                processed_data['asks'].append({
                    'price': float(ask[0]),
                    'size': float(ask[1]),
                    'order_id': ask[2] if len(ask) > 2 else None
                })
        
        # Sort bids by price (highest first) and asks by price (lowest first)
        processed_data['bids'].sort(key=lambda x: x['price'], reverse=True)
        processed_data['asks'].sort(key=lambda x: x['price'])
        
        return processed_data
    
    async def get_recent_trades(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent trade data.
        
        Args:
            limit: Maximum number of trades to fetch
            
        Returns:
            List of recent trade data
        """
        self.logger.info(f"Fetching recent trades for {self.product_id} (limit: {limit})")
        
        url = f"{self.base_url}/products/{self.product_id}/trades"
        params = {'limit': limit}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.logger.info(f"Retrieved {len(data)} recent trades")
                        return self._process_trade_data(data)
                    else:
                        error_text = await response.text()
                        self.logger.error(f"Failed to fetch recent trades: {response.status} - {error_text}")
                        return []
        except Exception as e:
            self.logger.error(f"Error fetching recent trades: {e}")
            return []
    
    async def get_product_stats(self) -> Dict[str, Any]:
        """Get product statistics.
        
        Returns:
            Product statistics including 24h volume, high, low, etc.
        """
        self.logger.info(f"Fetching product stats for {self.product_id}")
        
        url = f"{self.base_url}/products/{self.product_id}/stats"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.logger.info(f"Retrieved product stats for {self.product_id}")
                        return self._process_product_stats(data)
                    else:
                        error_text = await response.text()
                        self.logger.error(f"Failed to fetch product stats: {response.status} - {error_text}")
                        return {}
        except Exception as e:
            self.logger.error(f"Error fetching product stats: {e}")
            return {}
    
    def _process_product_stats(self, raw_data: Dict) -> Dict[str, Any]:
        """Process raw product stats data into our format.
        
        Args:
            raw_data: Raw product stats data from Coinbase API
            
        Returns:
            Processed product stats data
        """
        return {
            'open': float(raw_data.get('open', 0)),
            'high': float(raw_data.get('high', 0)),
            'low': float(raw_data.get('low', 0)),
            'volume': float(raw_data.get('volume', 0)),
            'last': float(raw_data.get('last', 0)),
            'volume_30day': float(raw_data.get('volume_30day', 0)),
            'timestamp': raw_data.get('time', datetime.now().isoformat()),
            'product_id': self.product_id
        }


class MockDataProvider:
    """Mock data provider for testing and development."""
    
    def __init__(self, product_id: str = "BTC-USD"):
        """Initialize the mock data provider.
        
        Args:
            product_id: Trading pair (e.g., "BTC-USD")
        """
        self.product_id = product_id
        self.logger = logging.getLogger(__name__)
    
    async def get_historical_candles(self, 
                                   start_time: datetime, 
                                   end_time: datetime, 
                                   granularity: int = 60) -> List[Dict[str, Any]]:
        """Generate mock historical candle data.
        
        Args:
            start_time: Start time for data
            end_time: End time for data
            granularity: Candle granularity in seconds
            
        Returns:
            List of mock candle data
        """
        self.logger.info(f"Generating mock data for {self.product_id} from {start_time} to {end_time}")
        
        # Generate mock data with some price movement
        import random
        import math
        
        data = []
        current_time = start_time
        base_price = 50000.0  # Starting price
        
        while current_time < end_time:
            # Generate some realistic price movement
            price_change = random.uniform(-0.02, 0.02)  # ±2% change
            base_price *= (1 + price_change)
            
            # Generate OHLC data
            open_price = base_price
            close_price = base_price * random.uniform(0.995, 1.005)
            high_price = max(open_price, close_price) * random.uniform(1.0, 1.01)
            low_price = min(open_price, close_price) * random.uniform(0.99, 1.0)
            volume = random.uniform(0.1, 10.0)
            
            candle = {
                'timestamp': current_time.isoformat() + 'Z',
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'volume': volume,
                'price': close_price
            }
            data.append(candle)
            
            current_time += timedelta(seconds=granularity)
        
        self.logger.info(f"Generated {len(data)} mock candles")
        return data
    
    async def get_historical_trades(self, 
                                  start_time: datetime, 
                                  end_time: datetime,
                                  limit: int = 100) -> List[Dict[str, Any]]:
        """Generate mock historical trade data.
        
        Args:
            start_time: Start time for data
            end_time: End time for data
            limit: Maximum number of trades to fetch
            
        Returns:
            List of mock trade data
        """
        self.logger.info(f"Generating mock trades for {self.product_id}")
        
        import random
        
        data = []
        current_time = start_time
        base_price = 50000.0
        
        trade_count = 0
        while current_time < end_time and trade_count < limit:
            # Generate trade
            price_change = random.uniform(-0.01, 0.01)
            base_price *= (1 + price_change)
            
            trade = {
                'timestamp': current_time.isoformat() + 'Z',
                'price': base_price,
                'size': random.uniform(0.001, 1.0),
                'side': random.choice(['buy', 'sell']),
                'trade_id': f"mock_{trade_count}"
            }
            data.append(trade)
            
            current_time += timedelta(seconds=random.randint(1, 60))
            trade_count += 1
        
        self.logger.info(f"Generated {len(data)} mock trades")
        return data
