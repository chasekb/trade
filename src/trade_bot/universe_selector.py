"""
Universe symbol selection logic for live trading.
"""

import asyncio
import logging
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
import numpy as np

logger = logging.getLogger(__name__)

class UniverseSelector:
    """
    Selects which symbols to trade from a universe based on strategy signals.
    """
    
    def __init__(self, data_provider, strategy_class, strategy_params: Dict):
        self.data_provider = data_provider
        self.strategy_class = strategy_class
        self.strategy_params = strategy_params
        self.symbol_signals = {}
        self.symbol_rankings = {}
        
    async def select_symbols(
        self, 
        universe_symbols: List[str], 
        max_positions: int,
        selection_method: str = "signal_strength"
    ) -> List[Tuple[str, float, Dict]]:
        """
        Select the best symbols to trade from the universe.
        
        Args:
            universe_symbols: List of all symbols in the universe
            max_positions: Maximum number of positions to open
            selection_method: Method for selecting symbols ("signal_strength", "momentum", "volatility")
            
        Returns:
            List of tuples: (symbol, signal_strength, signal_data)
        """
        logger.info(f"Selecting symbols from universe of {len(universe_symbols)} symbols")
        
        # Get signals for all symbols
        symbol_signals = await self._get_signals_for_universe(universe_symbols)
        
        # Filter symbols with valid signals
        valid_signals = {symbol: data for symbol, data in symbol_signals.items() 
                        if data and data.get('signal') != 'hold'}
        
        logger.info(f"Found {len(valid_signals)} symbols with valid signals")
        
        # Debug: Log some details about the signals
        for symbol, data in list(valid_signals.items())[:5]:  # Log first 5
            logger.info(f"Symbol {symbol}: signal={data.get('signal')}, strength={data.get('strength'):.3f}, reason={data.get('strategy_data', {}).get('reason', 'N/A')}")
        
        # Debug: Log some failed symbols
        failed_symbols = {symbol: data for symbol, data in symbol_signals.items() 
                         if data is None or data.get('signal') == 'hold'}
        logger.info(f"Found {len(failed_symbols)} symbols with no valid signals")
        for symbol in list(failed_symbols.keys())[:5]:  # Log first 5
            logger.info(f"Failed symbol {symbol}: {failed_symbols[symbol]}")
        
        if not valid_signals:
            logger.warning("No symbols with valid signals found")
            return []
        
        # Select symbols based on method
        if selection_method == "signal_strength":
            selected = self._select_by_signal_strength(valid_signals, max_positions)
        elif selection_method == "momentum":
            selected = self._select_by_momentum(valid_signals, max_positions)
        elif selection_method == "volatility":
            selected = self._select_by_volatility(valid_signals, max_positions)
        else:
            selected = self._select_by_signal_strength(valid_signals, max_positions)
        
        logger.info(f"Selected {len(selected)} symbols for trading: {[s[0] for s in selected]}")
        return selected
    
    async def _get_signals_for_universe(self, symbols: List[str]) -> Dict[str, Dict]:
        """Get trading signals for all symbols in the universe."""
        signals = {}
        
        # Process symbols in smaller batches to avoid overwhelming the API
        batch_size = 3  # Reduced batch size
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            
            # Process batch concurrently
            tasks = [self._get_signal_for_symbol(symbol) for symbol in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for symbol, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Error getting signal for {symbol}: {result}")
                    signals[symbol] = None
                else:
                    signals[symbol] = result
            
            # Longer delay between batches to respect rate limits
            await asyncio.sleep(1.0)  # Increased delay
        
        return signals
    
    async def _get_signal_for_symbol(self, symbol: str) -> Optional[Dict]:
        """Get trading signal for a single symbol."""
        try:
            # Get recent price data (shorter period to avoid rate limits)
            end_time = datetime.now()
            start_time = end_time - timedelta(days=7)  # Get 7 days of data
            
            candles = await self.data_provider.get_historical_candles(
                start_time=start_time, end_time=end_time, granularity=3600  # 1-hour candles
            )
            
            if not candles or len(candles) < 20:  # Need minimum data
                logger.warning(f"Insufficient data for {symbol}")
                return None
            
            # Initialize strategy for this symbol
            strategy = self.strategy_class(
                self.data_provider.config,  # Pass the config
                **self.strategy_params
            )
            
            # Process historical data
            for candle in candles:
                strategy.add_price(
                    price=float(candle['close']),
                    timestamp=candle['time']
                )
            
            # For Order Book strategy, we need to provide order book and trade data
            if hasattr(strategy, 'add_order_book') and hasattr(strategy, 'add_trades'):
                try:
                    # Get current order book data
                    order_book = await self.data_provider.get_order_book(level=2)
                    if order_book:
                        strategy.add_order_book(order_book, candles[-1]['time'])
                    
                    # Get recent trades
                    trades = await self.data_provider.get_recent_trades(limit=100)
                    if trades:
                        strategy.add_trades(trades, candles[-1]['time'])
                        
                except Exception as e:
                    logger.warning(f"Failed to get order book/trade data for {symbol}: {e}")
                    # For Order Book strategy, we need this data, so return None
                    if strategy.__class__.__name__ == 'OrderBookStrategy':
                        return None
            
            # Get current signal
            signal_data = strategy.generate_signal(
                current_price=float(candles[-1]['close']),
                timestamp=candles[-1]['time']
            )
            
            # Calculate signal strength
            signal_strength = self._calculate_signal_strength(strategy, signal_data)
            
            return {
                'signal': signal_data.get('action', 'hold'),
                'strength': signal_strength,
                'price': float(candles[-1]['close']),
                'volume': float(candles[-1]['volume']),
                'strategy_data': signal_data
            }
            
        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")
            return None
    
    def _calculate_signal_strength(self, strategy, signal_data: Dict) -> float:
        """Calculate signal strength based on strategy-specific metrics."""
        try:
            # Get strategy-specific statistics
            if hasattr(strategy, 'get_signal_stats'):
                stats = strategy.get_signal_stats()
                
                # Calculate strength based on strategy type
                if hasattr(strategy, 'rsi_values') and strategy.rsi_values:
                    # RSI-based strength
                    rsi = strategy.rsi_values[-1]
                    if signal_data.get('action') == 'buy':
                        strength = max(0, (30 - rsi) / 30)  # Stronger when RSI is lower
                    else:
                        strength = max(0, (rsi - 70) / 30)  # Stronger when RSI is higher
                
                elif hasattr(strategy, 'bollinger_upper') and strategy.bollinger_upper:
                    # Bollinger Bands strength
                    price = signal_data.get('price', 0)
                    upper = strategy.bollinger_upper[-1]
                    lower = strategy.bollinger_lower[-1]
                    if signal_data.get('action') == 'buy':
                        strength = max(0, (lower - price) / (upper - lower))
                    else:
                        strength = max(0, (price - upper) / (upper - lower))
                
                elif hasattr(strategy, 'macd_line') and strategy.macd_line:
                    # MACD strength
                    macd = strategy.macd_line[-1]
                    signal_line = strategy.signal_line[-1]
                    if signal_data.get('action') == 'buy':
                        strength = max(0, (signal_line - macd) / abs(signal_line) if signal_line != 0 else 0)
                    else:
                        strength = max(0, (macd - signal_line) / abs(signal_line) if signal_line != 0 else 0)
                
                elif strategy.__class__.__name__ == 'OrderBookStrategy':
                    # Order Book strategy strength based on signal type
                    signal_type = signal_data.get('reason', '')
                    if 'bid_ask_squeeze' in signal_type:
                        strength = 0.9  # High strength for squeeze signals
                    elif 'volume_imbalance' in signal_type:
                        # Extract imbalance value from reason
                        try:
                            imbalance_str = signal_type.split(': ')[-1] if ': ' in signal_type else '0'
                            imbalance = abs(float(imbalance_str))
                            strength = min(0.8, imbalance * 2)  # Scale imbalance to strength
                        except:
                            strength = 0.6
                    elif 'large_trade' in signal_type:
                        strength = 0.7  # Medium-high strength for large trades
                    else:
                        strength = 0.5  # Default strength
                
                else:
                    # Default strength calculation
                    strength = 0.5
                
                return min(1.0, max(0.0, strength))
            
        except Exception as e:
            logger.error(f"Error calculating signal strength: {e}")
        
        return 0.5  # Default moderate strength
    
    def _select_by_signal_strength(self, signals: Dict[str, Dict], max_positions: int) -> List[Tuple[str, float, Dict]]:
        """Select symbols with strongest signals."""
        # Sort by signal strength (descending)
        sorted_signals = sorted(
            signals.items(),
            key=lambda x: x[1]['strength'],
            reverse=True
        )
        
        # Take top symbols
        selected = []
        for symbol, data in sorted_signals[:max_positions]:
            selected.append((symbol, data['strength'], data))
        
        return selected
    
    def _select_by_momentum(self, signals: Dict[str, Dict], max_positions: int) -> List[Tuple[str, float, Dict]]:
        """Select symbols with highest momentum."""
        # Calculate momentum score (price change + volume)
        momentum_scores = {}
        for symbol, data in signals.items():
            price = data.get('price', 0)
            volume = data.get('volume', 0)
            strength = data.get('strength', 0)
            
            # Simple momentum calculation
            momentum = strength * (1 + volume / 1000000)  # Volume factor
            momentum_scores[symbol] = momentum
        
        # Sort by momentum
        sorted_by_momentum = sorted(
            momentum_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        selected = []
        for symbol, momentum in sorted_by_momentum[:max_positions]:
            data = signals[symbol]
            selected.append((symbol, momentum, data))
        
        return selected
    
    def _select_by_volatility(self, signals: Dict[str, Dict], max_positions: int) -> List[Tuple[str, float, Dict]]:
        """Select symbols with optimal volatility."""
        # This would require historical volatility calculation
        # For now, use signal strength as proxy
        return self._select_by_signal_strength(signals, max_positions)
    
    def get_universe_summary(self, selected_symbols: List[Tuple[str, float, Dict]]) -> Dict:
        """Get summary of selected symbols."""
        if not selected_symbols:
            return {"count": 0, "signals": {}}
        
        signals = {}
        for symbol, strength, data in selected_symbols:
            signals[symbol] = {
                "action": data.get('signal', 'hold'),
                "strength": strength,
                "price": data.get('price', 0)
            }
        
        return {
            "count": len(selected_symbols),
            "signals": signals,
            "buy_signals": len([s for s in selected_symbols if s[2].get('signal') == 'buy']),
            "sell_signals": len([s for s in selected_symbols if s[2].get('signal') == 'sell']),
            "avg_strength": np.mean([s[1] for s in selected_symbols]) if selected_symbols else 0
        }
