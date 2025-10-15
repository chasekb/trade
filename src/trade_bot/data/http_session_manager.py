"""
HTTP session manager for connection pooling and reuse.

This module provides a singleton HTTP session manager for efficient connection reuse.
"""

import aiohttp
import asyncio
import logging
from typing import Optional
import atexit

logger = logging.getLogger(__name__)


class HTTPSessionManager:
    """Singleton HTTP session manager for connection pooling."""
    
    _instance: Optional['HTTPSessionManager'] = None
    _lock = asyncio.Lock()
    
    def __init__(self):
        """Initialize the HTTP session manager."""
        self._session: Optional[aiohttp.ClientSession] = None
        self._connector: Optional[aiohttp.TCPConnector] = None
        self._timeout = aiohttp.ClientTimeout(total=30)
        
        # Register cleanup on exit
        atexit.register(self._cleanup_sync)
    
    @classmethod
    async def get_instance(cls) -> 'HTTPSessionManager':
        """
        Get the singleton instance of HTTPSessionManager.
        
        Returns:
            HTTPSessionManager instance
        """
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    async def get_session(self) -> aiohttp.ClientSession:
        """
        Get or create the HTTP session.
        
        Returns:
            aiohttp.ClientSession with connection pooling
        """
        if self._session is None or self._session.closed:
            # Create connector with connection pooling
            self._connector = aiohttp.TCPConnector(
                limit=100,  # Maximum number of simultaneous connections
                limit_per_host=30,  # Maximum connections per host
                ttl_dns_cache=300,  # DNS cache TTL in seconds
                enable_cleanup_closed=True  # Clean up closed connections
            )
            
            # Create session with connector
            self._session = aiohttp.ClientSession(
                connector=self._connector,
                timeout=self._timeout,
                headers={
                    'User-Agent': 'TradingBot/1.0',
                    'Accept': 'application/json',
                }
            )
            logger.info("HTTP session created with connection pooling")
        
        return self._session
    
    async def close(self):
        """Close the HTTP session and cleanup resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("HTTP session closed")
        
        if self._connector:
            await self._connector.close()
            self._connector = None
        
        self._session = None
    
    def _cleanup_sync(self):
        """Synchronous cleanup for atexit."""
        if self._session and not self._session.closed:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.close())
                else:
                    loop.run_until_complete(self.close())
            except Exception as e:
                logger.error(f"Error during HTTP session cleanup: {e}")
    
    async def __aenter__(self):
        """Support async context manager protocol."""
        return await self.get_session()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Support async context manager protocol."""
        # Don't close the session here, keep it alive for reuse
        pass


# Global convenience function
async def get_http_session() -> aiohttp.ClientSession:
    """
    Get the shared HTTP session.
    
    Usage:
        session = await get_http_session()
        async with session.get(url) as response:
            data = await response.json()
    
    Returns:
        Shared aiohttp.ClientSession
    """
    manager = await HTTPSessionManager.get_instance()
    return await manager.get_session()


async def close_http_session():
    """Close the shared HTTP session."""
    manager = await HTTPSessionManager.get_instance()
    await manager.close()

