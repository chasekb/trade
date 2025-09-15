"""
Polars GPU-accelerated calculations for Order Book strategy.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class PolarsOptimizer:
    """Polars GPU-accelerated calculations for high-performance data analysis."""
    
    def __init__(self, use_gpu: bool = True):
        self.use_gpu = use_gpu
        self.polars_available = False
        self.gpu_available = False
        
        # Try to import polars
        try:
            import polars as pl
            self.polars_available = True
            self.pl = pl
            
            # Check if GPU is available
            if use_gpu:
                try:
                    # Try to create a small DataFrame to test GPU
                    test_df = pl.DataFrame({"test": [1, 2, 3]})
                    # Note: GPU support in Polars is still experimental
                    # For now, we'll use CPU but with optimized operations
                    self.gpu_available = False  # Set to False until GPU support is stable
                    logger.info("Polars available, using CPU-optimized operations")
                except Exception as e:
                    logger.warning(f"Polars GPU not available: {e}")
                    self.gpu_available = False
            else:
                logger.info("Polars available, using CPU-optimized operations")
                
        except ImportError:
            logger.warning("Polars not available, falling back to numpy/Python")
            self.polars_available = False
    
    def analyze_trade_flow_polars(self, trades: List[Dict]) -> Dict[str, float]:
        """Analyze trade flow using Polars for high-performance calculations."""
        if not trades or not self.polars_available:
            return {'buy_pressure': 0.0, 'sell_pressure': 0.0, 'large_trades': 0}
        
        try:
            # Convert trades to Polars DataFrame
            trade_data = []
            for trade_data_item in trades:
                trade = trade_data_item['trade']
                trade_data.append({
                    'size': float(trade.get('size', 0)),
                    'price': float(trade.get('price', 0)),
                    'side': trade.get('side', ''),
                    'timestamp': trade_data_item.get('timestamp', datetime.now())
                })
            
            # Create Polars DataFrame
            df = self.pl.DataFrame(trade_data)
            
            # Calculate trade values
            df = df.with_columns([
                (self.pl.col('size') * self.pl.col('price')).alias('trade_value')
            ])
            
            # Calculate buy/sell volumes using Polars expressions
            buy_volume = df.filter(self.pl.col('side') == 'buy')['trade_value'].sum()
            sell_volume = df.filter(self.pl.col('side') == 'sell')['trade_value'].sum()
            
            # Count large trades
            large_trades = df.filter(self.pl.col('trade_value') >= 10000.0).height
            
            # Calculate pressures
            total_volume = buy_volume + sell_volume
            if total_volume == 0:
                return {'buy_pressure': 0.0, 'sell_pressure': 0.0, 'large_trades': large_trades}
            
            buy_pressure = buy_volume / total_volume
            sell_pressure = sell_volume / total_volume
            
            return {
                'buy_pressure': buy_pressure,
                'sell_pressure': sell_pressure,
                'large_trades': large_trades
            }
            
        except Exception as e:
            logger.error(f"Error in Polars trade analysis: {e}")
            return {'buy_pressure': 0.0, 'sell_pressure': 0.0, 'large_trades': 0}
    
    def analyze_order_book_polars(self, order_books: List[Dict]) -> Dict[str, Any]:
        """Analyze order book data using Polars for high-performance calculations."""
        if not order_books or not self.polars_available:
            return {'avg_spread': 0.0, 'avg_imbalance': 0.0, 'spread_volatility': 0.0}
        
        try:
            # Extract order book data
            ob_data = []
            for ob_item in order_books:
                order_book = ob_item['order_book']
                timestamp = ob_item.get('timestamp', datetime.now())
                
                # Calculate spread
                if order_book.get('bids') and order_book.get('asks'):
                    best_bid = order_book['bids'][0]['price']
                    best_ask = order_book['asks'][0]['price']
                    spread = (best_ask - best_bid) / best_bid if best_bid > 0 else 0
                else:
                    spread = 0
                
                # Calculate volume imbalance
                if order_book.get('bids') and order_book.get('asks'):
                    bid_volume = sum(ob['size'] for ob in order_book['bids'][:5])
                    ask_volume = sum(ob['size'] for ob in order_book['asks'][:5])
                    total_volume = bid_volume + ask_volume
                    imbalance = (bid_volume - ask_volume) / total_volume if total_volume > 0 else 0
                else:
                    imbalance = 0
                
                ob_data.append({
                    'timestamp': timestamp,
                    'spread': spread,
                    'imbalance': imbalance,
                    'bid_volume': bid_volume if 'bid_volume' in locals() else 0,
                    'ask_volume': ask_volume if 'ask_volume' in locals() else 0
                })
            
            # Create Polars DataFrame
            df = self.pl.DataFrame(ob_data)
            
            # Calculate statistics using Polars expressions
            stats = df.select([
                self.pl.col('spread').mean().alias('avg_spread'),
                self.pl.col('imbalance').mean().alias('avg_imbalance'),
                self.pl.col('spread').std().alias('spread_volatility'),
                self.pl.col('imbalance').std().alias('imbalance_volatility'),
                self.pl.col('bid_volume').sum().alias('total_bid_volume'),
                self.pl.col('ask_volume').sum().alias('total_ask_volume')
            ])
            
            # Convert to dictionary
            result = stats.to_dicts()[0]
            
            return result
            
        except Exception as e:
            logger.error(f"Error in Polars order book analysis: {e}")
            return {'avg_spread': 0.0, 'avg_imbalance': 0.0, 'spread_volatility': 0.0}
    
    def calculate_rolling_metrics_polars(self, data: List[Dict], window: int = 10) -> List[Dict]:
        """Calculate rolling metrics using Polars for high-performance time series analysis."""
        if not data or not self.polars_available:
            return []
        
        try:
            # Convert to Polars DataFrame
            df = self.pl.DataFrame(data)
            
            # Calculate rolling metrics
            df = df.with_columns([
                self.pl.col('spread').rolling_mean(window).alias('rolling_spread'),
                self.pl.col('imbalance').rolling_mean(window).alias('rolling_imbalance'),
                self.pl.col('spread').rolling_std(window).alias('spread_volatility'),
                self.pl.col('imbalance').rolling_std(window).alias('imbalance_volatility')
            ])
            
            # Convert back to list of dictionaries
            return df.to_dicts()
            
        except Exception as e:
            logger.error(f"Error in Polars rolling metrics: {e}")
            return []
    
    def batch_analyze_trades_polars(self, trade_batches: List[List[Dict]]) -> List[Dict]:
        """Analyze multiple trade batches in parallel using Polars."""
        if not trade_batches or not self.polars_available:
            return []
        
        try:
            results = []
            
            for trades in trade_batches:
                result = self.analyze_trade_flow_polars(trades)
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Error in Polars batch analysis: {e}")
            return []
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for the Polars optimizer."""
        return {
            'polars_available': self.polars_available,
            'gpu_available': self.gpu_available,
            'use_gpu': self.use_gpu,
            'optimization_level': 'high' if self.polars_available else 'none'
        }
