"""Data provider for historical market data."""

import asyncio
import logging
import os
import socket
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from urllib.parse import urlsplit
import aiohttp
import json


class CoinbaseDataProvider:
    """Data provider for Coinbase Exchange public endpoints.

    Accepts either a product ID string (e.g., "BTC-USD") or a TradingConfig-like
    object that exposes a "product_id" attribute. This makes the provider
    compatible with call sites that pass a config object.
    """

    # Class-level host state to avoid per-instance spam and enable shared cooldowns
    _host_state: Dict[str, Dict[str, Any]] = {}

    def __init__(self, config_or_product_id: Any = "BTC-USD", config: Any = None):
        """Initialize the data provider.

        Args:
            config_or_product_id: Either a product ID string like "BTC-USD" or an
                object with a "product_id" attribute (e.g., TradingConfig).
            config: TradingConfig object for rate limiting configuration.
        """
        # Allow both product_id string and TradingConfig-like objects
        if isinstance(config_or_product_id, str):
            self.product_id = config_or_product_id
        else:
            # Fallback: try to pull product_id attribute from the object
            self.product_id = getattr(config_or_product_id, "product_id", "BTC-USD")

        # Store config for rate limiting
        self.config = config

        # Allow overriding public base URL via environment to support proxies/region issues
        self.base_url = os.getenv("COINBASE_PUBLIC_BASE_URL", "https://api.exchange.coinbase.com")
        self.logger = logging.getLogger(__name__)
        self._host: str = urlsplit(self.base_url).hostname or "api.exchange.coinbase.com"

        # Initialize rate limiting from config
        self._rate_limiter_enabled = getattr(config, 'coinbase_rate_limit_enabled', True) if config else True
        self._max_concurrent_requests = getattr(config, 'coinbase_max_concurrent_requests', 5) if config else 5
        self._min_request_interval = getattr(config, 'coinbase_min_request_interval', 0.1) if config else 0.1

        # Initialize rate limiting components
        if self._rate_limiter_enabled:
            if CoinbaseDataProvider._rate_limiter is None:
                CoinbaseDataProvider._rate_limiter = asyncio.Semaphore(self._max_concurrent_requests)
            if CoinbaseDataProvider._last_request_time is None:
                CoinbaseDataProvider._last_request_time = datetime.now()

        # Ensure host state exists
        CoinbaseDataProvider._host_state.setdefault(
            self._host, {"failures": 0, "cooldown_until": None}
        )

    def _get_state(self) -> Dict[str, Any]:
        return CoinbaseDataProvider._host_state[self._host]

    def _in_cooldown(self) -> bool:
        cooldown_until = self._get_state().get("cooldown_until")
        return cooldown_until is not None and datetime.now() < cooldown_until

    @property
    def _cooldown_until(self):
        """Get the cooldown until timestamp."""
        return self._get_state().get("cooldown_until")

    def _begin_cooldown(self) -> None:
        state = self._get_state()
        failures = state.get("failures", 0)
        # Exponential backoff up to 2 minutes
        backoff_seconds = min(120, 2 ** min(failures, 6))
        state["cooldown_until"] = datetime.now() + timedelta(seconds=backoff_seconds)
        self.logger.warning(
            f"Network cooldown activated for {backoff_seconds}s after {failures} failures (host={self._host})"
        )

    def _reset_cooldown(self) -> None:
        state = self._get_state()
        state["failures"] = 0
        state["cooldown_until"] = None

    async def _enforce_rate_limit(self) -> None:
        """Enforce rate limiting for API requests."""
        if not self._rate_limiter_enabled:
            return

        # Acquire semaphore for concurrent request limiting
        await CoinbaseDataProvider._rate_limiter.acquire()

        try:
            # Enforce minimum interval between requests
            now = datetime.now()
            if CoinbaseDataProvider._last_request_time:
                time_since_last_request = (now - CoinbaseDataProvider._last_request_time).total_seconds()
                if time_since_last_request < self._min_request_interval:
                    sleep_time = self._min_request_interval - time_since_last_request
                    await asyncio.sleep(sleep_time)

            CoinbaseDataProvider._last_request_time = datetime.now()
        finally:
            # Always release the semaphore
            CoinbaseDataProvider._rate_limiter.release()

    def _host_resolves(self) -> bool:
        try:
            # DNS preflight; run in thread to avoid blocking event loop
            socket.gethostbyname(self._host)
            return True
        except Exception as e:
            self.logger.warning(f"DNS resolution failed for {self._host}: {e}")
            return False

    def _session_kwargs(self) -> Dict[str, Any]:
        # Respect system proxies and set sane timeouts and headers
        timeout = aiohttp.ClientTimeout(total=10, connect=5, sock_read=7)
        return {
            "timeout": timeout,
            "trust_env": True,  # pick up HTTPS_PROXY/NO_PROXY
            "headers": {
                "User-Agent": "trade-bot/1.0 (+https://github.com/) aiohttp",
                "Accept": "application/json",
            },
        }
    
    async def get_historical_candles(self, 
                                   start_time: datetime, 
                                   end_time: datetime, 
                                   granularity: int = 60) -> List[Dict[str, Any]]:
        """Get historical candle data with pagination for longer periods.
        
        Args:
            start_time: Start time for data
            end_time: End time for data
            granularity: Candle granularity in seconds (60, 300, 900, 3600, 21600, 86400)
            
        Returns:
            List of candle data
        """
        self.logger.info(f"Fetching historical data for {self.product_id} from {start_time} to {end_time}")
        
        # Calculate expected number of candles
        time_diff = end_time - start_time
        total_seconds = time_diff.total_seconds()
        expected_candles = int(total_seconds / granularity)
        
        # Coinbase API limit is 300 candles per request
        max_candles_per_request = 300
        
        if expected_candles <= max_candles_per_request:
            # Single request is sufficient
            return await self._fetch_candles_single(start_time, end_time, granularity)
        else:
            # Need to paginate
            self.logger.info(f"Expected {expected_candles} candles, fetching in chunks of {max_candles_per_request}")
            return await self._fetch_candles_paginated(start_time, end_time, granularity, max_candles_per_request)
    
    async def _fetch_candles_single(self, start_time: datetime, end_time: datetime, granularity: int) -> List[Dict[str, Any]]:
        """Fetch candles with a single API request."""
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
                        self.logger.info(f"Retrieved {len(data)} candles in single request")
                        return self._process_candle_data(data)
                    else:
                        error_text = await response.text()
                        self.logger.error(f"Failed to fetch data: {response.status} - {error_text}")
                        return []
        except Exception as e:
            self.logger.error(f"Error fetching data: {e}")
            return []
    
    async def _fetch_candles_paginated(self, start_time: datetime, end_time: datetime, 
                                     granularity: int, max_candles: int) -> List[Dict[str, Any]]:
        """Fetch candles with pagination for longer periods."""
        all_candles = []
        current_start = start_time
        
        # Calculate chunk duration based on granularity and max candles
        chunk_seconds = granularity * max_candles
        chunk_duration = timedelta(seconds=chunk_seconds)
        
        chunk_count = 0
        while current_start < end_time:
            chunk_count += 1
            current_end = min(current_start + chunk_duration, end_time)
            
            self.logger.info(f"Fetching chunk {chunk_count}: {current_start} to {current_end}")
            
            chunk_candles = await self._fetch_candles_single(current_start, current_end, granularity)
            
            if not chunk_candles:
                self.logger.warning(f"No data received for chunk {chunk_count}")
                break
            
            all_candles.extend(chunk_candles)
            self.logger.info(f"Chunk {chunk_count} added {len(chunk_candles)} candles (total: {len(all_candles)})")
            
            # Move to next chunk
            current_start = current_end
            
            # Add small delay to avoid rate limiting
            import asyncio
            await asyncio.sleep(0.1)
        
        # Remove duplicates and sort by timestamp
        unique_candles = self._deduplicate_candles(all_candles)
        unique_candles.sort(key=lambda x: x['timestamp'])
        
        self.logger.info(f"Pagination complete: {len(unique_candles)} total candles from {chunk_count} chunks")
        return unique_candles
    
    def _deduplicate_candles(self, candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate candles based on timestamp."""
        seen_timestamps = set()
        unique_candles = []
        
        for candle in candles:
            timestamp = candle['timestamp']
            if timestamp not in seen_timestamps:
                seen_timestamps.add(timestamp)
                unique_candles.append(candle)
        
        return unique_candles
    
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
        if self._in_cooldown():
            self.logger.debug(
                f"Skipping order book fetch for {self.product_id} - in cooldown until {self._cooldown_until}"
            )
            return {}

        # Enforce rate limiting before making the request
        await self._enforce_rate_limit()

        self.logger.info(f"Fetching order book for {self.product_id} (level {level})")

        url = f"{self.base_url}/products/{self.product_id}/book"
        params = {'level': level}

        try:
            # DNS preflight to avoid tight error loops on name resolution failures
            if not await asyncio.to_thread(self._host_resolves):
                st = self._get_state()
                st["failures"] = st.get("failures", 0) + 1
                self._begin_cooldown()
                return {}

            async with aiohttp.ClientSession(**self._session_kwargs()) as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.logger.info(f"Retrieved order book with {len(data.get('bids', []))} bids and {len(data.get('asks', []))} asks")
                        self._reset_cooldown()
                        return self._process_order_book_data(data)
                    else:
                        error_text = await response.text()
                        self.logger.error(f"Failed to fetch order book: {response.status} - {error_text}")
                        st = self._get_state()
                        st["failures"] = st.get("failures", 0) + 1
                        if st["failures"] >= 3:
                            self._begin_cooldown()
                        return {}
        except Exception as e:
            st = self._get_state()
            st["failures"] = st.get("failures", 0) + 1
            self.logger.error(f"Error fetching order book: {e}")
            if st["failures"] >= 3:
                self._begin_cooldown()
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
