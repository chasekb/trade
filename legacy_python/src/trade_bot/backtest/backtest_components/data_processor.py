"""Data processing component for backtesting."""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class DataProcessor:
    """Processes data for backtesting."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def adjust_order_book_to_price(self, order_book: Dict[str, Any], target_price: float) -> Dict[str, Any]:
        """Adjust order book data to a specific price level.
        
        Args:
            order_book: Original order book data
            target_price: Target price to adjust to
            
        Returns:
            Adjusted order book data
        """
        if not order_book or 'bids' not in order_book or 'asks' not in order_book:
            return order_book
        
        adjusted_book = order_book.copy()
        
        # Adjust bids (should be below target price)
        if 'bids' in adjusted_book and adjusted_book['bids']:
            adjusted_bids = []
            for bid in adjusted_book['bids']:
                if len(bid) >= 2:
                    price = float(bid[0])
                    size = float(bid[1])
                    if price <= target_price:
                        adjusted_bids.append([str(price), str(size)])
                    else:
                        # Scale down the price but keep size
                        adjusted_price = target_price * 0.999  # Slightly below target
                        adjusted_bids.append([str(adjusted_price), str(size)])
            adjusted_book['bids'] = adjusted_bids
        
        # Adjust asks (should be above target price)
        if 'asks' in adjusted_book and adjusted_book['asks']:
            adjusted_asks = []
            for ask in adjusted_book['asks']:
                if len(ask) >= 2:
                    price = float(ask[0])
                    size = float(ask[1])
                    if price >= target_price:
                        adjusted_asks.append([str(price), str(size)])
                    else:
                        # Scale up the price but keep size
                        adjusted_price = target_price * 1.001  # Slightly above target
                        adjusted_asks.append([str(adjusted_price), str(size)])
            adjusted_book['asks'] = adjusted_asks
        
        return adjusted_book
    
    def adjust_trades_to_price(self, trades: List[Dict[str, Any]], target_price: float) -> List[Dict[str, Any]]:
        """Adjust trade data to a specific price level.
        
        Args:
            trades: Original trade data
            target_price: Target price to adjust to
            
        Returns:
            Adjusted trade data
        """
        if not trades:
            return trades
        
        adjusted_trades = []
        for trade in trades:
            adjusted_trade = trade.copy()
            
            # Adjust price
            if 'price' in adjusted_trade:
                adjusted_trade['price'] = str(target_price)
            
            # Adjust value if present
            if 'value' in adjusted_trade and 'size' in adjusted_trade:
                try:
                    size = float(adjusted_trade['size'])
                    adjusted_trade['value'] = str(target_price * size)
                except (ValueError, TypeError):
                    pass
            
            adjusted_trades.append(adjusted_trade)
        
        return adjusted_trades
    
    def process_trade_pairs(self, trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process trades into buy/sell pairs for analysis.
        
        Args:
            trades: List of individual trades
            
        Returns:
            List of trade pairs with P&L calculations
        """
        trade_pairs = []
        open_trades = []
        
        for trade in trades:
            if trade.get('action') == 'buy':
                open_trades.append(trade)
            elif trade.get('action') == 'sell' and open_trades:
                # Match with the most recent buy trade
                buy_trade = open_trades.pop()
                
                # Calculate P&L
                buy_price = float(buy_trade.get('price', 0))
                sell_price = float(trade.get('price', 0))
                quantity = float(buy_trade.get('quantity', 0))
                
                pnl = (sell_price - buy_price) * quantity
                
                trade_pair = {
                    'buy_timestamp': buy_trade.get('timestamp'),
                    'sell_timestamp': trade.get('timestamp'),
                    'buy_price': buy_price,
                    'sell_price': sell_price,
                    'quantity': quantity,
                    'pnl': pnl,
                    'return_pct': (pnl / (buy_price * quantity)) * 100 if buy_price > 0 else 0,
                    'buy_fees': float(buy_trade.get('fees', 0)),
                    'sell_fees': float(trade.get('fees', 0)),
                    'total_fees': float(buy_trade.get('fees', 0)) + float(trade.get('fees', 0)),
                    'net_pnl': pnl - (float(buy_trade.get('fees', 0)) + float(trade.get('fees', 0)))
                }
                
                trade_pairs.append(trade_pair)
        
        return trade_pairs
    
    def calculate_rolling_returns(self, equity_curve: List[Dict[str, Any]], 
                                 window: int = 30) -> List[float]:
        """Calculate rolling returns for equity curve.
        
        Args:
            equity_curve: List of equity curve data points
            window: Rolling window size
            
        Returns:
            List of rolling returns
        """
        if len(equity_curve) < window:
            return []
        
        rolling_returns = []
        
        for i in range(window, len(equity_curve) + 1):
            window_data = equity_curve[i-window:i]
            
            if len(window_data) >= 2:
                start_equity = window_data[0]['total_equity']
                end_equity = window_data[-1]['total_equity']
                
                if start_equity > 0:
                    rolling_return = (end_equity - start_equity) / start_equity * 100
                    rolling_returns.append(rolling_return)
                else:
                    rolling_returns.append(0)
            else:
                rolling_returns.append(0)
        
        return rolling_returns
    
    def calculate_volatility(self, returns: List[float]) -> float:
        """Calculate volatility of returns.
        
        Args:
            returns: List of return percentages
            
        Returns:
            Volatility as standard deviation
        """
        if len(returns) < 2:
            return 0.0
        
        import statistics
        return statistics.stdev(returns)
    
    def calculate_correlation(self, returns1: List[float], returns2: List[float]) -> float:
        """Calculate correlation between two return series.
        
        Args:
            returns1: First return series
            returns2: Second return series
            
        Returns:
            Correlation coefficient
        """
        if len(returns1) != len(returns2) or len(returns1) < 2:
            return 0.0
        
        import statistics
        
        mean1 = statistics.mean(returns1)
        mean2 = statistics.mean(returns2)
        
        numerator = sum((r1 - mean1) * (r2 - mean2) for r1, r2 in zip(returns1, returns2))
        denominator1 = sum((r1 - mean1) ** 2 for r1 in returns1)
        denominator2 = sum((r2 - mean2) ** 2 for r2 in returns2)
        
        if denominator1 == 0 or denominator2 == 0:
            return 0.0
        
        return numerator / (denominator1 * denominator2) ** 0.5
    
    def detect_outliers(self, data: List[float], threshold: float = 2.0) -> List[int]:
        """Detect outliers in data using z-score method.
        
        Args:
            data: List of numeric values
            threshold: Z-score threshold for outlier detection
            
        Returns:
            List of indices of outliers
        """
        if len(data) < 3:
            return []
        
        import statistics
        
        mean = statistics.mean(data)
        std = statistics.stdev(data)
        
        if std == 0:
            return []
        
        outliers = []
        for i, value in enumerate(data):
            z_score = abs((value - mean) / std)
            if z_score > threshold:
                outliers.append(i)
        
        return outliers
    
    def smooth_data(self, data: List[float], window: int = 5) -> List[float]:
        """Apply moving average smoothing to data.
        
        Args:
            data: List of numeric values
            window: Smoothing window size
            
        Returns:
            Smoothed data
        """
        if len(data) < window:
            return data
        
        smoothed = []
        for i in range(len(data)):
            start_idx = max(0, i - window + 1)
            end_idx = i + 1
            window_data = data[start_idx:end_idx]
            smoothed.append(sum(window_data) / len(window_data))
        
        return smoothed
