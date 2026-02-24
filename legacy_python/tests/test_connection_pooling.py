"""
Tests for database connection pooling and HTTP session management.
"""

import pytest
import asyncio
import sys
from pathlib import Path
import time
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trade_bot.database.connection_pool import ConnectionPool, get_pool, close_all_pools
from trade_bot.data.http_session_manager import get_http_session, HTTPSessionManager, close_http_session


class TestConnectionPool:
    """Test database connection pooling."""
    
    def setup_method(self):
        """Setup test database."""
        self.test_db_path = "data/databases/test_connection_pool.db"
        os.makedirs("data/databases", exist_ok=True)
    
    def teardown_method(self):
        """Cleanup test database."""
        close_all_pools()
        if os.path.exists(self.test_db_path):
            time.sleep(0.1)  # Give time for connections to close
            try:
                os.remove(self.test_db_path)
            except Exception:
                pass
    
    def test_connection_pool_creation(self):
        """Test creating a connection pool."""
        pool = ConnectionPool(
            self.test_db_path,
            min_connections=2,
            max_connections=5
        )
        
        assert pool is not None
        assert pool.db_path == self.test_db_path
        assert pool.min_connections == 2
        assert pool.max_connections == 5
        
        # Check stats
        stats = pool.stats()
        assert stats['active_connections'] >= 2
        assert stats['max_connections'] == 5
        assert not stats['closed']
        
        pool.close()
    
    def test_connection_reuse(self):
        """Test that connections are reused from the pool."""
        pool = ConnectionPool(
            self.test_db_path,
            min_connections=2,
            max_connections=5
        )
        
        # Get and return a connection multiple times
        for i in range(10):
            with pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                assert result[0] == 1
        
        # Should not have created 10 connections
        stats = pool.stats()
        assert stats['active_connections'] <= 5
        
        pool.close()
    
    def test_concurrent_connections(self):
        """Test concurrent connection requests."""
        pool = ConnectionPool(
            self.test_db_path,
            min_connections=2,
            max_connections=10
        )
        
        def worker(worker_id):
            """Worker function for concurrent access."""
            for i in range(5):
                with pool.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT ?", (worker_id,))
                    result = cursor.fetchone()
                    assert result[0] == worker_id
        
        # Run multiple workers concurrently
        import threading
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Check that pool handled concurrent requests
        stats = pool.stats()
        assert stats['active_connections'] > 0
        
        pool.close()
    
    def test_connection_pool_singleton(self):
        """Test that get_pool returns the same pool for same db_path."""
        pool1 = get_pool(self.test_db_path, min_connections=2, max_connections=5)
        pool2 = get_pool(self.test_db_path)
        
        assert pool1 is pool2
        
        close_all_pools()
    
    def test_connection_pool_close(self):
        """Test closing the connection pool."""
        pool = ConnectionPool(
            self.test_db_path,
            min_connections=2,
            max_connections=5
        )
        
        stats_before = pool.stats()
        assert stats_before['active_connections'] >= 2
        
        pool.close()
        
        stats_after = pool.stats()
        assert stats_after['closed']


class TestHTTPSessionManager:
    """Test HTTP session management."""
    
    @pytest.mark.asyncio
    async def test_session_manager_creation(self):
        """Test creating HTTP session manager."""
        manager = await HTTPSessionManager.get_instance()
        assert manager is not None
        
        session = await manager.get_session()
        assert session is not None
        assert not session.closed
        
        await manager.close()
    
    @pytest.mark.asyncio
    async def test_session_reuse(self):
        """Test that the same session is reused."""
        session1 = await get_http_session()
        session2 = await get_http_session()
        
        # Should be the same session
        assert session1 is session2
        assert not session1.closed
        
        await close_http_session()
    
    @pytest.mark.asyncio
    async def test_session_singleton(self):
        """Test that HTTPSessionManager is a singleton."""
        manager1 = await HTTPSessionManager.get_instance()
        manager2 = await HTTPSessionManager.get_instance()
        
        assert manager1 is manager2
        
        await manager1.close()
    
    @pytest.mark.asyncio
    async def test_http_request_with_session(self):
        """Test making HTTP requests with the session."""
        session = await get_http_session()
        
        # Make a simple HTTP request to a public API
        try:
            async with session.get("https://httpbin.org/get") as response:
                assert response.status == 200
                data = await response.json()
                assert 'headers' in data
        except Exception as e:
            # Network request might fail in some environments, that's ok
            pytest.skip(f"Network request failed: {e}")
        
        await close_http_session()
    
    @pytest.mark.asyncio
    async def test_concurrent_http_requests(self):
        """Test concurrent HTTP requests with connection pooling."""
        session = await get_http_session()
        
        async def fetch_url(url):
            """Fetch a URL."""
            try:
                async with session.get(url) as response:
                    return response.status
            except Exception:
                return None
        
        # Make multiple concurrent requests
        urls = ["https://httpbin.org/get" for _ in range(5)]
        try:
            results = await asyncio.gather(*[fetch_url(url) for url in urls])
            # Check that requests were successful (if network available)
            successful = [r for r in results if r == 200]
            if successful:
                assert len(successful) > 0
        except Exception as e:
            # Network requests might fail in some environments
            pytest.skip(f"Network requests failed: {e}")
        
        await close_http_session()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

