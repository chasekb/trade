"""Rate limiter for REST API calls per Coinbase documentation."""

import asyncio
import time
from typing import List


class RateLimiter:
    """Rate limiter for REST API calls per Coinbase documentation."""
    
    def __init__(self, max_requests_per_hour: int = 10000):
        """
        Initialize rate limiter.
        
        Args:
            max_requests_per_hour: Maximum requests per hour (default: 10,000 per Coinbase docs)
        """
        self.max_requests_per_hour = max_requests_per_hour
        self.requests: List[float] = []
        self.lock = asyncio.Lock()
    
    async def is_allowed(self) -> bool:
        """
        Check if a request is allowed under rate limiting.
        
        Returns:
            True if request is allowed, False otherwise
        """
        async with self.lock:
            current_time = time.time()
            hour_ago = current_time - 3600  # 1 hour in seconds
            
            # Remove requests older than 1 hour
            self.requests = [req_time for req_time in self.requests if req_time > hour_ago]
            
            # Check if we're under the limit
            if len(self.requests) < self.max_requests_per_hour:
                self.requests.append(current_time)
                return True
            
            return False
    
    async def get_remaining_requests(self) -> int:
        """Get the number of remaining requests in the current hour."""
        async with self.lock:
            current_time = time.time()
            hour_ago = current_time - 3600
            
            # Remove requests older than 1 hour
            self.requests = [req_time for req_time in self.requests if req_time > hour_ago]
            
            return max(0, self.max_requests_per_hour - len(self.requests))
    
    async def get_reset_time(self) -> float:
        """Get the time when the rate limit resets (in seconds from now)."""
        if not self.requests:
            return 0.0
        
        # Find the oldest request still in the window
        current_time = time.time()
        hour_ago = current_time - 3600
        valid_requests = [req_time for req_time in self.requests if req_time > hour_ago]
        
        if not valid_requests:
            return 0.0
        
        oldest_request = min(valid_requests)
        return oldest_request + 3600 - current_time
