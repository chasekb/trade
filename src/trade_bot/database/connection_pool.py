"""
Database connection pooling for improved performance.

This module provides a thread-safe connection pool for SQLite databases.
"""

import sqlite3
import threading
import time
import logging
from typing import Optional
from contextlib import contextmanager
from queue import Queue, Empty

logger = logging.getLogger(__name__)


class ConnectionPool:
    """Thread-safe connection pool for SQLite databases."""
    
    def __init__(
        self,
        db_path: str,
        min_connections: int = 2,
        max_connections: int = 10,
        timeout: float = 30.0,
        max_idle_time: float = 300.0
    ):
        """
        Initialize connection pool.
        
        Args:
            db_path: Path to the SQLite database file
            min_connections: Minimum number of connections to maintain
            max_connections: Maximum number of connections allowed
            timeout: Timeout in seconds for getting a connection
            max_idle_time: Maximum time a connection can be idle before being closed
        """
        self.db_path = db_path
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.timeout = timeout
        self.max_idle_time = max_idle_time
        
        self._pool: Queue = Queue(maxsize=max_connections)
        self._active_connections = 0
        self._lock = threading.Lock()
        self._closed = False
        
        # Initialize minimum connections
        self._initialize_pool()
        
        logger.info(
            f"Connection pool initialized: {db_path} "
            f"(min={min_connections}, max={max_connections})"
        )
    
    def _initialize_pool(self):
        """Initialize the pool with minimum connections."""
        for _ in range(self.min_connections):
            try:
                conn = self._create_connection()
                self._pool.put((conn, time.time()))
                self._active_connections += 1
            except Exception as e:
                logger.error(f"Failed to create initial connection: {e}")
    
    def _create_connection(self) -> sqlite3.Connection:
        """
        Create a new database connection.
        
        Returns:
            A new SQLite connection
        """
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,  # Allow connection to be used across threads
            timeout=self.timeout
        )
        # Enable row factory for easier data access
        conn.row_factory = sqlite3.Row
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    
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
            # Try to get a connection from the pool
            try:
                conn, last_used = self._pool.get(timeout=self.timeout)
                
                # Check if connection is still valid and not too old
                if time.time() - last_used > self.max_idle_time:
                    logger.debug("Closing idle connection")
                    conn.close()
                    conn = self._create_connection()
                else:
                    # Test if connection is still alive
                    try:
                        conn.execute("SELECT 1")
                    except sqlite3.Error:
                        logger.debug("Connection test failed, creating new connection")
                        conn.close()
                        conn = self._create_connection()
            
            except Empty:
                # No connections available, try to create a new one
                with self._lock:
                    if self._active_connections < self.max_connections:
                        conn = self._create_connection()
                        self._active_connections += 1
                        logger.debug(
                            f"Created new connection "
                            f"({self._active_connections}/{self.max_connections})"
                        )
                    else:
                        # Wait for a connection to become available
                        logger.warning("Connection pool exhausted, waiting...")
                        conn, _ = self._pool.get(timeout=self.timeout)
            
            yield conn
            
        finally:
            # Return connection to pool
            if conn is not None:
                try:
                    # Rollback any uncommitted transactions
                    conn.rollback()
                    # Return to pool with current timestamp
                    self._pool.put((conn, time.time()))
                except Exception as e:
                    logger.error(f"Error returning connection to pool: {e}")
                    # If we can't return it, close it and decrement count
                    try:
                        conn.close()
                    except Exception:
                        pass
                    with self._lock:
                        self._active_connections -= 1
    
    def close(self):
        """Close all connections in the pool."""
        if self._closed:
            return
        
        self._closed = True
        closed_count = 0
        
        # Close all connections in the pool
        while not self._pool.empty():
            try:
                conn, _ = self._pool.get_nowait()
                conn.close()
                closed_count += 1
            except Empty:
                break
            except Exception as e:
                logger.error(f"Error closing connection: {e}")
        
        logger.info(f"Connection pool closed: {closed_count} connections closed")
    
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
            "db_path": self.db_path,
            "active_connections": self._active_connections,
            "available_connections": self._pool.qsize(),
            "max_connections": self.max_connections,
            "closed": self._closed
        }


# Global connection pool instance (singleton pattern)
_pools: dict[str, ConnectionPool] = {}
_pools_lock = threading.Lock()


def get_pool(
    db_path: str,
    min_connections: int = 2,
    max_connections: int = 10,
    timeout: float = 30.0
) -> ConnectionPool:
    """
    Get or create a connection pool for a database.
    
    This function implements a singleton pattern per database path.
    
    Args:
        db_path: Path to the SQLite database file
        min_connections: Minimum number of connections to maintain
        max_connections: Maximum number of connections allowed
        timeout: Timeout in seconds for getting a connection
    
    Returns:
        ConnectionPool instance for the specified database
    """
    with _pools_lock:
        if db_path not in _pools or _pools[db_path]._closed:
            _pools[db_path] = ConnectionPool(
                db_path,
                min_connections=min_connections,
                max_connections=max_connections,
                timeout=timeout
            )
        return _pools[db_path]


def close_all_pools():
    """Close all connection pools."""
    with _pools_lock:
        for pool in _pools.values():
            pool.close()
        _pools.clear()

