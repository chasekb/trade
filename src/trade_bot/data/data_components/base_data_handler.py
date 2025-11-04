from typing import List
"""Base data handler with common functionality."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import os

from ...core.config import TradingConfig

logger = logging.getLogger(__name__)


class BaseDataHandler:
    """Base data handler with common functionality."""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.data: List[Dict[str, Any]] = []
        
        # Ensure output directory exists
        os.makedirs(config.output_dir, exist_ok=True)
    
    def add_data(self, data: Dict[str, Any]) -> None:
        """Add data point to the collection."""
        self.data.append(data)
        logger.debug(f"Added data: {data}")
    
    def get_latest(self) -> Optional[Dict[str, Any]]:
        """Get the latest data point."""
        return self.data[-1] if self.data else None
    
    def get_all_data(self) -> List[Dict[str, Any]]:
        """Get all collected data."""
        return self.data.copy()
    
    def clear_data(self) -> None:
        """Clear all collected data."""
        self.data.clear()
        logger.info("Data cleared")
    
    def get_data_count(self) -> int:
        """Get the number of data points collected."""
        return len(self.data)
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics for the data."""
        if not self.data:
            return {'count': 0, 'latest_timestamp': None}
        
        timestamps = [item.get('timestamp', '') for item in self.data if 'timestamp' in item]
        
        return {
            'count': len(self.data),
            'latest_timestamp': max(timestamps) if timestamps else None,
            'first_timestamp': min(timestamps) if timestamps else None
        }
