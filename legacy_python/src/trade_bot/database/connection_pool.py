"""
Database connection pooling for improved performance.

This module provides a thread-safe connection pool for PostgreSQL databases.
"""

import psycopg
import psycopg_pool as psycopg_pool
import threading
import time
import logging
from typing import Optional
from contextlib import contextmanager
from queue import Queue, Empty
import os

logger = logging.getLogger(__name__)


class ConnectionPool:
    """Thread-safe connection pool for PostgreSQL databases."""

    def __init__(
        self,
        db_url: str,
        min_connections: int = 2,
        max_connections: int = 10,
        timeout: float = 30.0,
        max_idle_time: float = 300.0
    ):
        """
        Initialize connection pool.

        Args:
            db_url: PostgreSQL connection URL
            min_connections: Minimum number of connections to maintain
            max_connections: Maximum number of connections allowed
            timeout: Timeout in seconds for getting a connection
            max_idle_time: Maximum time a connection can be idle before being closed
        """
        self.db_url = db_url
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.timeout = timeout
        self.max_idle_time = max_idle_time

        # Use psycopg connection pool
        self._pool = psycopg_pool.ConnectionPool(
            conninfo=db_url,
            min_size=min_connections,
            max_size=max_connections
        )

        self._closed = False

        logger.info(
            f"PostgreSQL connection pool initialized: {db_url} "
            f"(min={min_connections}, max={max_connections})"
        )

    @contextmanager
    def get_connection(self):
        """
        Get a connection from the pool (context manager).

        Usage:
            with pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM table")

        Yields:
            A database connection
        """
        if self._closed:
            raise RuntimeError("Connection pool is closed")

        conn = None
        try:
            conn = self._pool.getconn()
            yield conn
        finally:
            if conn is not None:
                try:
                    # Rollback any uncommitted transactions
                    conn.rollback()
                    # Return connection to pool
                    self._pool.putconn(conn)
                except Exception as e:
                    logger.error(f"Error returning connection to pool: {e}")
                    # If we can't return it, close it
                    try:
                        conn.close()
                    except Exception:
                        pass

    def close(self):
        """Close all connections in the pool."""
        if self._closed:
            return

        self._closed = True
        self._pool.closeall()
        logger.info("PostgreSQL connection pool closed")

    def __enter__(self):
        """Support context manager protocol."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Support context manager protocol."""
        self.close()

    def stats(self) -> dict:
        """
        Get pool statistics.

        Returns:
            Dictionary with pool statistics
        """
        return {
            "db_url": self.db_url,
            "min_connections": self.min_connections,
            "max_connections": self.max_connections,
            "closed": self._closed
        }


# Global connection pool instance (singleton pattern)
_pools: dict[str, ConnectionPool] = {}
_pools_lock = threading.Lock()


def get_pool(
    db_url: str,
    min_connections: int = 2,
    max_connections: int = 10,
    timeout: float = 30.0
) -> ConnectionPool:
    """
    Get or create a connection pool for a database.

    This function implements a singleton pattern per database URL.

    Args:
        db_url: PostgreSQL connection URL
        min_connections: Minimum number of connections to maintain
        max_connections: Maximum number of connections allowed
        timeout: Timeout in seconds for getting a connection

    Returns:
        ConnectionPool instance for the specified database
    """
    with _pools_lock:
        if db_url not in _pools or _pools[db_url]._closed:
            _pools[db_url] = ConnectionPool(
                db_url,
                min_connections=min_connections,
                max_connections=max_connections,
                timeout=timeout
            )
        return _pools[db_url]


def close_all_pools():
    """Close all connection pools."""
    with _pools_lock:
        for pool in _pools.values():
            pool.close()
        _pools.clear()
