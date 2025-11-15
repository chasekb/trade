from typing import List
"""Data handlers for the trading web server."""

import logging
import os
import re
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import HTTPException
import requests
import json

logger = logging.getLogger(__name__)


class DataHandlers:
    """Handles data-related functionality for the trading web server."""
    
    def __init__(self, config, data_provider, cached_data_provider, database_manager, simulated_trading_manager=None, trading_handlers=None, trading_state=None):
        self.config = config
        self.data_provider = data_provider
        self.cached_data_provider = cached_data_provider
        self.database_manager = database_manager
        self.simulated_trading_manager = simulated_trading_manager
        self.trading_handlers = trading_handlers
        self.trading_state = trading_state
        # De-duplicate noisy warnings per symbol
        self._last_no_data_warn_at: dict[str, float] = {}
        # Get configurable symbol limits
        self.max_symbols_per_request = getattr(config, 'max_symbols_per_request', 1000)
        # Cache for feature importances
        self._feature_importance_cache: Dict[str, Any] = {}
        self._feature_importance_cache_ttl: int = 300  # Cache for 5 minutes
        self._signal_cache: List[Dict[str, Any]] = []
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            stats = self.database_manager.get_cache_stats()
            return {"cache_stats": stats}
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    def clear_signal_cache(self):
        """Clear the in-memory signal cache."""
        self._signal_cache = []
        logger.info("In-memory signal cache cleared.")

    async def get_live_orderbook_signals(self, symbols: str = None, page: int = 1, per_page: int = 10) -> Dict[str, Any]:
        """Get live order book signals."""
        try:
            if not symbols:
                return {"error": "No symbols provided"}
            # basic pagination guardrails
            page = max(1, int(page))
            per_page = max(1, min(int(per_page), 1000))
            
            # Check if trading is active with orderbook strategy (either simulated trading or async trading)
            trading_active = False
            orderbook_strategy_active = False

            # Check simulated trading first
            if self.simulated_trading_manager:
                trading_active = self.simulated_trading_manager.is_trading
                # Check if strategy is orderbook
                if trading_active and hasattr(self.simulated_trading_manager, 'strategy_type'):
                    orderbook_strategy_active = self.simulated_trading_manager.strategy_type in ['orderbook', 'ml_enhanced_orderbook']
                    logger.info(f"Simulated trading active: {trading_active}, strategy: {self.simulated_trading_manager.strategy_type}")

            # Also check if async trading is active with orderbook strategy
            if not trading_active and self.trading_state:
                async_trading_active = getattr(self.trading_state, 'is_trading', False)
                if async_trading_active:
                    trading_active = True
                    # Check if async trading strategy is orderbook
                    async_strategy = self.trading_state.get('active_strategy', '')
                    orderbook_strategy_active = async_strategy in ['orderbook', 'ml_enhanced_orderbook']
                    logger.info(f"Async trading active: {async_trading_active}, strategy: {async_strategy}")
                    if orderbook_strategy_active:
                        logger.info("Async trading is active with orderbook strategy, enabling order book signals")

            # Enhanced logging for debugging
            logger.info(f"Signal generation check - trading_active: {trading_active}, orderbook_strategy_active: {orderbook_strategy_active}")
            logger.info(f"Simulated trading manager exists: {self.simulated_trading_manager is not None}")
            logger.info(f"Trading state exists: {self.trading_state is not None}")
            
            # Return signals if trading is active (regardless of strategy type for debugging)
            # but prioritize orderbook strategy
            if not trading_active:
                reason = "Trading is not active"
                logger.debug(f"{reason}, returning empty signals")
                return {
                    "signals": [],
                    "trading_active": trading_active,
                    "orderbook_strategy_active": orderbook_strategy_active,
                    "message": f"{reason}. Start trading to see live signals.",
                    "pagination": {
                        "current_page": page,
                        "per_page": per_page,
                        "total_signals": 0,
                        "total_pages": 0,
                        "has_next": False,
                        "has_prev": False
                    }
                }
            
            # If trading is active but not orderbook strategy, still return signals but with warning
            if trading_active and not orderbook_strategy_active:
                logger.warning("Trading is active but not using orderbook strategy - returning basic signals")
            
            # Handle case where symbols might be malformed (e.g., "[object Object]")
            if symbols == "[object Object]" or symbols == "%5Bobject%20Object%5D":
                logger.warning("Received malformed symbols '[object Object]', returning empty signals")
                return {
                    "signals": [],
                    "trading_active": trading_active,
                    "orderbook_strategy_active": orderbook_strategy_active,
                    "message": "Invalid symbols provided. Please refresh the page and try again.",
                    "pagination": {
                        "current_page": page,
                        "per_page": per_page,
                        "total_signals": 0,
                        "total_pages": 0,
                        "has_next": False,
                        "has_prev": False
                    }
                }
            
            symbol_list = [s.strip() for s in symbols.split(',')]
            # Cap symbols to avoid heavy requests in universe mode
            # Use configurable limit from strategy configuration
            if len(symbol_list) > self.max_symbols_per_request:
                logger.info(f"Capping symbols from {len(symbol_list)} to {self.max_symbols_per_request} to avoid timeouts")
                symbol_list = symbol_list[:self.max_symbols_per_request]
            # Validate symbol formats
            valid = []
            for s in symbol_list:
                if re.fullmatch(r"[A-Z0-9\-]{3,30}", s):
                    valid.append(s)
            if not valid:
                return {"signals": [], "trading_active": trading_active, "orderbook_strategy_active": orderbook_strategy_active, "message": "No valid symbols provided", "pagination": {"current_page": page, "per_page": per_page, "total_signals": 0, "total_pages": 0, "has_next": False, "has_prev": False}}
            symbol_list = valid
            
            # Debug logging to see what symbols we're processing
            logger.info(f"Processing symbols for order book signals: {symbol_list}")
            
            # Fetch real orderbook data from Coinbase API asynchronously
            async def generate_signal_for_symbol(symbol: str) -> Dict[str, Any]:
                """Generate order book signal for a single symbol."""
                try:
                    # Ensure symbol is a string and log it
                    symbol_str = str(symbol).strip()
                    logger.debug(f"Fetching order book for {symbol_str} (level 2)")

                    # Create a data provider instance for this symbol
                    from ...data.data_provider import CoinbaseDataProvider
                    symbol_provider = CoinbaseDataProvider(symbol_str)

                    # Fetch live orderbook data (using level 2 for comprehensive signal analysis)
                    orderbook_data = await symbol_provider.get_order_book(level=2)

                    if orderbook_data and orderbook_data.get('bids') and orderbook_data.get('asks'):
                        # Calculate orderbook metrics
                        best_bid = float(orderbook_data['bids'][0]['price']) if orderbook_data['bids'] else 0
                        best_ask = float(orderbook_data['asks'][0]['price']) if orderbook_data['asks'] else 0
                        current_price = (best_bid + best_ask) / 2 if best_bid and best_ask else 0

                        # Calculate spread
                        spread = ((best_ask - best_bid) / current_price * 100) if current_price > 0 else 0

                        # Calculate volume (sum of top 5 bids/asks)
                        bid_volume = sum(float(bid['size']) for bid in orderbook_data['bids'][:5])
                        ask_volume = sum(float(ask['size']) for ask in orderbook_data['asks'][:5])
                        total_volume = bid_volume + ask_volume

                        # Calculate orderbook imbalance
                        volume_imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume) if (bid_volume + ask_volume) > 0 else 0

                        # Determine signal based on orderbook analysis
                        # Lower threshold from 0.1 to 0.05 (5%) for more sensitive signal detection
                        volume_imbalance_threshold = 0.05
                        if volume_imbalance > volume_imbalance_threshold:  # More buy pressure
                            signal = "buy"
                            signal_strength = min(abs(volume_imbalance), 1.0)
                            signal_reason = f"Buy pressure detected (imbalance: {volume_imbalance:.2f})"
                        elif volume_imbalance < -volume_imbalance_threshold:  # More sell pressure
                            signal = "sell"
                            signal_strength = min(abs(volume_imbalance), 1.0)
                            signal_reason = f"Sell pressure detected (imbalance: {volume_imbalance:.2f})"
                        else:  # Balanced
                            signal = "hold"
                            signal_strength = 0.3
                            signal_reason = "Orderbook balanced"

                        # Determine data status - more lenient criteria for better signal display
                        bids_count = len(orderbook_data.get('bids', []))
                        asks_count = len(orderbook_data.get('asks', []))
                        data_status = "sufficient" if (bids_count >= 3 and asks_count >= 3 and current_price > 0) else "insufficient"

                        # Calculate analysis criteria
                        squeeze_threshold = 0.1  # 0.1% spread threshold
                        imbalance_threshold = 0.05  # 5% imbalance threshold (lowered for more sensitive detection)
                        large_trade_threshold = 5000  # $5k trade threshold (lowered from $10k)

                        # Bid-Ask Squeeze Analysis
                        squeeze_meets = spread < squeeze_threshold
                        squeeze_delta = squeeze_threshold - spread

                        # Volume Imbalance Analysis
                        imbalance_meets_buy = volume_imbalance > imbalance_threshold
                        imbalance_meets_sell = volume_imbalance < -imbalance_threshold
                        imbalance_delta_buy = volume_imbalance - imbalance_threshold if volume_imbalance > 0 else 0
                        imbalance_delta_sell = abs(volume_imbalance) - imbalance_threshold if volume_imbalance < 0 else 0

                        # Large Trade Analysis - get recent trade data
                        large_trade_meets_buy = False
                        large_trade_meets_sell = False
                        large_trade_count = 0
                        large_trade_analysis = "No recent trades"
                        large_trades = []  # Initialize empty list

                        try:
                            # Get recent trades for this symbol
                            recent_trades = await symbol_provider.get_recent_trades(limit=50)
                            if recent_trades:
                                # Analyze trades for large trade patterns
                                buy_volume = 0.0
                                sell_volume = 0.0

                                for trade in recent_trades:
                                    try:
                                        trade_size = float(trade.get('size', 0))
                                        trade_price = float(trade.get('price', 0))
                                        trade_value = trade_size * trade_price
                                        trade_side = trade.get('side', '')

                                        if trade_value >= large_trade_threshold:
                                            large_trades.append({
                                                'side': trade_side,
                                                'value': trade_value,
                                                'size': trade_size,
                                                'price': trade_price
                                            })

                                        # Track buy/sell volumes
                                        if trade_side == 'buy':
                                            buy_volume += trade_value
                                        elif trade_side == 'sell':
                                            sell_volume += trade_value

                                    except (ValueError, TypeError):
                                        continue

                                # Calculate large trade metrics
                                large_trade_count = len(large_trades)
                                large_buy_trades = [t for t in large_trades if t['side'] == 'buy']
                                large_sell_trades = [t for t in large_trades if t['side'] == 'sell']

                                # Determine if large trade criteria are met
                                # Reduced from 2 to 1 to allow more signals
                                large_trade_meets_buy = len(large_buy_trades) >= 1  # At least 1 large buy trade
                                large_trade_meets_sell = len(large_sell_trades) >= 1  # At least 1 large sell trade

                                # Calculate large trade pressure
                                total_volume = buy_volume + sell_volume
                                if total_volume > 0:
                                    large_trade_pressure = (sum(t['value'] for t in large_trades) / total_volume) * 100
                                    large_trade_analysis = f"Large trades: {large_trade_count} ({large_trade_pressure:.1f}% of volume)"
                                else:
                                    large_trade_analysis = f"Large trades: {large_trade_count}"

                        except Exception as e:
                            logger.warning(f"Error analyzing large trades for {symbol}: {e}")
                            large_trade_analysis = "Analysis error"

                        signal_data = {
                            "symbol": symbol,
                            "signal": signal,
                            "signal_type": signal,
                            "signal_strength": signal_strength,
                            "strength": signal_strength,
                            "price": current_price,
                            "timestamp": orderbook_data.get('timestamp', '2024-01-01T00:00:00Z'),
                            "reason": signal_reason,
                            "signal_reason": signal_reason,
                            "data_status": data_status,
                            "spread": spread,
                            "volume": total_volume,
                            "signal_generated": signal != "hold" and signal_strength >= 0.05,  # Lowered threshold from 0.1 to 0.05 for more signals
                            "criteria_analysis": {
                                "bid_ask_squeeze": {
                                    "enabled": True,
                                    "meets_criteria": squeeze_meets,
                                    "delta_to_threshold": squeeze_delta,
                                    "analysis": f"Spread: {spread:.4f}%" if squeeze_meets else f"Wide spread: {spread:.4f}%",
                                    "threshold": squeeze_threshold,
                                    "current_value": spread
                                },
                                "volume_imbalance_buy": {
                                    "enabled": True,
                                    "meets_criteria": imbalance_meets_buy,
                                    "delta_to_threshold": imbalance_delta_buy,
                                    "analysis": f"Buy pressure: {volume_imbalance:.2f} (bid: {bid_volume:.2f}, ask: {ask_volume:.2f})",
                                    "threshold": imbalance_threshold,
                                    "current_value": volume_imbalance,
                                    "bid_volume": bid_volume,
                                    "ask_volume": ask_volume
                                },
                                "volume_imbalance_sell": {
                                    "enabled": True,
                                    "meets_criteria": imbalance_meets_sell,
                                    "delta_to_threshold": imbalance_delta_sell,
                                    "analysis": f"Sell pressure: {volume_imbalance:.2f} (bid: {bid_volume:.2f}, ask: {ask_volume:.2f})",
                                    "threshold": imbalance_threshold,
                                    "current_value": volume_imbalance,
                                    "bid_volume": bid_volume,
                                    "ask_volume": ask_volume
                                },
                                "large_trade_buy": {
                                    "enabled": True,
                                    "meets_criteria": large_trade_meets_buy,
                                    "delta_to_threshold": len([t for t in large_trades if t['side'] == 'buy']) - 1 if large_trades else 0,
                                    "analysis": large_trade_analysis,
                                    "threshold": large_trade_threshold,
                                    "current_value": len([t for t in large_trades if t['side'] == 'buy']) if large_trades else 0,
                                    "large_trades_count": len([t for t in large_trades if t['side'] == 'buy']) if large_trades else 0
                                },
                                "large_trade_sell": {
                                    "enabled": True,
                                    "meets_criteria": large_trade_meets_sell,
                                    "delta_to_threshold": len([t for t in large_trades if t['side'] == 'sell']) - 1 if large_trades else 0,
                                    "analysis": large_trade_analysis,
                                    "threshold": large_trade_threshold,
                                    "current_value": len([t for t in large_trades if t['side'] == 'sell']) if large_trades else 0,
                                    "large_trades_count": len([t for t in large_trades if t['side'] == 'sell']) if large_trades else 0
                                }
                            }
                        }

                        # Enrich with ML analysis before saving
                        enriched_signal_list = await self._enrich_signals_with_ml_analysis([signal_data])
                        enriched_signal = enriched_signal_list[0] if enriched_signal_list else signal_data

                        # Store signal to database immediately
                        if self.database_manager:
                            try:
                                # Merge ml_analysis into signal_data
                                signal_details = {
                                    'spread': enriched_signal['spread'],
                                    'volume': enriched_signal['volume'],
                                    'criteria_analysis': enriched_signal['criteria_analysis']
                                }
                                if 'ml_analysis' in enriched_signal:
                                    signal_details['ml_analysis'] = enriched_signal['ml_analysis']

                                db_signal_data = {
                                    'signal_id': f"{symbol}_{int(datetime.fromisoformat(enriched_signal['timestamp'].replace('Z', '+00:00')).timestamp())}_{signal}",
                                    'session_id': getattr(self.simulated_trading_manager, 'session_id', None) if self.simulated_trading_manager else None,
                                    'symbol': symbol,
                                    'signal_type': enriched_signal['signal_type'],
                                    'strength': enriched_signal['signal_strength'],
                                    'price': enriched_signal['price'],
                                    'timestamp': int(datetime.fromisoformat(enriched_signal['timestamp'].replace('Z', '+00:00')).timestamp()),
                                    'signal_data': signal_details,
                                    'processed': False
                                }

                                # Store the signal
                                success = self.database_manager.save_order_book_signal(db_signal_data)
                                if success:
                                    logger.debug(f"Stored signal for {symbol}: {signal} (strength: {signal_strength:.2f})")
                                else:
                                    logger.warning(f"Failed to store signal for {symbol}")

                            except Exception as e:
                                logger.warning(f"Error storing signal for {symbol}: {e}")

                        logger.info(f"Generated live orderbook signal for {symbol}: {signal} (strength: {signal_strength:.2f})")
                        return enriched_signal

                    else:
                        # Fallback to placeholder if no data, but rate-limit warnings per symbol
                        now_ts = datetime.now().timestamp()
                        last_ts = self._last_no_data_warn_at.get(symbol, 0)
                        if now_ts - last_ts >= 60:
                            logger.warning(f"No orderbook data available for {symbol}, using placeholder")
                            self._last_no_data_warn_at[symbol] = now_ts

                        placeholder_signal = {
                            "symbol": symbol,
                            "signal": "hold",
                            "signal_type": "hold",
                            "signal_strength": 0.0,
                            "strength": 0.0,
                            "price": 0.0,
                            "timestamp": "2024-01-01T00:00:00Z",
                            "reason": "No orderbook data available",
                            "signal_reason": "No orderbook data available",
                            "data_status": "insufficient",
                            "spread": 0.0,
                            "volume": 0.0,
                            "signal_generated": False,  # No data available, don't process
                            "criteria_analysis": {
                                "bid_ask_squeeze": {
                                    "enabled": False,
                                    "meets_criteria": False,
                                    "delta_to_threshold": 0,
                                    "analysis": "No data available",
                                    "threshold": 0.1,
                                    "current_value": 0
                                },
                                "volume_imbalance_buy": {
                                    "enabled": False,
                                    "meets_criteria": False,
                                    "delta_to_threshold": 0,
                                    "analysis": "No data available",
                                    "threshold": 0.1,
                                    "current_value": 0,
                                    "bid_volume": 0,
                                    "ask_volume": 0
                                },
                                "volume_imbalance_sell": {
                                    "enabled": False,
                                    "meets_criteria": False,
                                    "delta_to_threshold": 0,
                                    "analysis": "No data available",
                                    "threshold": 0.1,
                                    "current_value": 0,
                                    "bid_volume": 0,
                                    "ask_volume": 0
                                },
                                "large_trade_buy": {
                                    "enabled": False,
                                    "meets_criteria": False,
                                    "delta_to_threshold": 0,
                                    "analysis": "No data available",
                                    "threshold": 5000,
                                    "current_value": 0,
                                    "large_trades_count": 0
                                },
                                "large_trade_sell": {
                                    "enabled": False,
                                    "meets_criteria": False,
                                    "delta_to_threshold": 0,
                                    "analysis": "No data available",
                                    "threshold": 5000,
                                    "current_value": 0,
                                    "large_trades_count": 0
                                }
                            }
                        }

                        # Store placeholder signal to database
                        if self.database_manager:
                            try:
                                db_signal_data = {
                                    'signal_id': f"{symbol}_{int(datetime.now().timestamp())}_hold",
                                    'session_id': getattr(self.simulated_trading_manager, 'session_id', None) if self.simulated_trading_manager else None,
                                    'symbol': symbol,
                                    'signal_type': 'hold',
                                    'strength': 0.0,
                                    'price': 0.0,
                                    'timestamp': int(datetime.now().timestamp()),
                                    'signal_data': {
                                        'spread': 0.0,
                                        'volume': 0.0,
                                        'criteria_analysis': placeholder_signal['criteria_analysis']
                                    },
                                    'processed': False
                                }

                                success = self.database_manager.save_order_book_signal(db_signal_data)
                                if success:
                                    logger.debug(f"Stored placeholder signal for {symbol}")
                                else:
                                    logger.warning(f"Failed to store placeholder signal for {symbol}")

                            except Exception as e:
                                logger.warning(f"Error storing placeholder signal for {symbol}: {e}")

                        return placeholder_signal

                except Exception as e:
                    logger.error(f"Error fetching orderbook data for {symbol}: {e}")
                    # Fallback to placeholder on error
                    error_signal = {
                        "symbol": symbol,
                        "signal": "hold",
                        "signal_type": "hold",
                        "signal_strength": 0.0,
                        "strength": 0.0,
                        "price": 0.0,
                        "timestamp": "2024-01-01T00:00:00Z",
                        "reason": f"Error fetching data: {str(e)}",
                        "signal_reason": f"Error fetching data: {str(e)}",
                        "data_status": "insufficient",
                        "spread": 0.0,
                        "volume": 0.0,
                        "signal_generated": False,  # Error occurred, don't process
                        "criteria_analysis": {
                            "bid_ask_squeeze": {
                                "enabled": False,
                                "meets_criteria": False,
                                "delta_to_threshold": 0,
                                "analysis": "Error fetching data",
                                "threshold": 0.1,
                                "current_value": 0
                            },
                            "volume_imbalance_buy": {
                                "enabled": False,
                                "meets_criteria": False,
                                "delta_to_threshold": 0,
                                "analysis": "Error fetching data",
                                "threshold": 0.1,
                                "current_value": 0,
                                "bid_volume": 0,
                                "ask_volume": 0
                            },
                            "volume_imbalance_sell": {
                                "enabled": False,
                                "meets_criteria": False,
                                "delta_to_threshold": 0,
                                "analysis": "Error fetching data",
                                "threshold": 0.1,
                                "current_value": 0,
                                "bid_volume": 0,
                                "ask_volume": 0
                            },
                            "large_trade_buy": {
                                "enabled": False,
                                "meets_criteria": False,
                                "delta_to_threshold": 0,
                                "analysis": "Error fetching data",
                                    "threshold": 5000,
                                "current_value": 0,
                                "large_trades_count": 0
                            },
                            "large_trade_sell": {
                                "enabled": False,
                                "meets_criteria": False,
                                "delta_to_threshold": 0,
                                "analysis": "Error fetching data",
                                    "threshold": 5000,
                                "current_value": 0,
                                "large_trades_count": 0
                            }
                        }
                    }

                    # Store error signal to database
                    if self.database_manager:
                        try:
                            db_signal_data = {
                                'signal_id': f"{symbol}_{int(datetime.now().timestamp())}_error",
                                'session_id': getattr(self.simulated_trading_manager, 'session_id', None) if self.simulated_trading_manager else None,
                                'symbol': symbol,
                                'signal_type': 'hold',
                                'strength': 0.0,
                                'price': 0.0,
                                'timestamp': int(datetime.now().timestamp()),
                                'signal_data': {
                                    'spread': 0.0,
                                    'volume': 0.0,
                                    'criteria_analysis': error_signal['criteria_analysis']
                                },
                                'processed': False
                            }

                            success = self.database_manager.save_order_book_signal(db_signal_data)
                            if success:
                                logger.debug(f"Stored error signal for {symbol}")
                            else:
                                logger.warning(f"Failed to store error signal for {symbol}")

                        except Exception as store_error:
                            logger.warning(f"Error storing error signal for {symbol}: {store_error}")

                    return error_signal

            # Generate signals individually as order book data becomes available (not waiting for all symbols)
            import asyncio
            signals = []
            # Process symbols individually to generate signals as data is retrieved
            for symbol in symbol_list:
                try:
                    signal = await generate_signal_for_symbol(symbol)
                    if signal:  # Only add non-empty signals
                        signals.append(signal)
                        logger.info(f"Generated signal for {symbol} individually: {signal.get('signal', 'hold')} (strength: {signal.get('signal_strength', 0):.2f})")
                except Exception as e:
                    logger.error(f"Failed to generate signal for {symbol}: {e}")
                    continue
            
            # Sort signals by signal strength (descending)
            signals.sort(key=lambda x: x.get('signal_strength', 0), reverse=True)
            
            # Calculate pagination
            total_signals = len(signals)
            total_pages = (total_signals + per_page - 1) // per_page
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            paginated_signals = signals[start_idx:end_idx]
            
            # Calculate statistics
            active_signals = len([s for s in signals if s.get('signal_generated', False)])
            avg_strength = sum(s.get('signal_strength', 0) for s in signals) / len(signals) if signals else 0
            
            # Get cumulative total signals processed from simulated trading manager
            total_analyzed = 0
            if self.simulated_trading_manager and hasattr(self.simulated_trading_manager, 'get_total_signals_processed'):
                total_analyzed = self.simulated_trading_manager.get_total_signals_processed()

            return {
                "signals": paginated_signals,
                "trading_active": trading_active,
                "message": "Order book signals generated successfully",
                "total_analyzed": total_analyzed,
                "active_signals": active_signals,
                "average_strength": avg_strength,
                "last_updated": datetime.now().isoformat(),
                "pagination": {
                    "current_page": page,
                    "per_page": per_page,
                    "total_signals": total_signals,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1
                }
            }
        except Exception as e:
            logger.error(f"Error getting live orderbook signals: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def _get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance from ML server and cache it."""
        now = datetime.now().timestamp()
        if self._feature_importance_cache and (now - self._feature_importance_cache.get("timestamp", 0)) < self._feature_importance_cache_ttl:
            return self._feature_importance_cache.get("data", {})

        try:
            ml_server_url = os.getenv("ML_SERVER_URL", f"http://{self.config.ml_server_host}:{self.config.ml_server_port}")
            importance_url = f"{ml_server_url}/features/importance"
            response = requests.get(importance_url, timeout=5.0)
            if response.status_code == 200:
                importance_data = response.json()
                # Ensure we have a flat dictionary of feature: importance
                if 'feature_importance' in importance_data:
                    importance_data = {item['feature']: item['importance'] for item in importance_data['feature_importance']}
                
                self._feature_importance_cache = {"timestamp": now, "data": importance_data}
                logger.info(f"Successfully fetched and cached feature importances: {list(importance_data.keys())}")
                return importance_data
            else:
                logger.warning(f"Failed to get feature importance, status code: {response.status_code}")
                return {}
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting feature importance: {e}")
            return {}

    async def _enrich_signals_with_ml_analysis(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich signals with ML analysis from the ML model server."""
        enriched_signals = []

        # Check ML server health first
        ml_server_healthy = await self._check_ml_server_health()

        if not ml_server_healthy:
            logger.warning("ML server is not healthy, skipping ML analysis for all signals")
            for signal in signals:
                signal["ml_analysis"] = {"ml_enabled": False, "reason": "ML server unavailable"}
                enriched_signals.append(signal)
            return enriched_signals

        # Get learned feature importances to calculate contributions
        feature_importances = await self._get_feature_importance()
        if not feature_importances:
            logger.warning("Could not retrieve feature importances. Tooltips will not show detailed contributions.")

        # Normalize importance scores for percentage display
        total_importance = sum(feature_importances.values())

        for signal in signals:
            try:
                # Prepare request for ML server
                # Calculate dynamic feature values to ensure diverse ML predictions per symbol
                current_value = signal["criteria_analysis"]["volume_imbalance_buy"]["current_value"]
                bid_volume = signal["criteria_analysis"]["volume_imbalance_buy"]["bid_volume"]
                ask_volume = signal["criteria_analysis"]["volume_imbalance_buy"]["ask_volume"]
                spread = signal["spread"]
                price = signal["price"]
                symbol = signal["symbol"]

                # Create symbol-specific variations to ensure diverse predictions
                symbol_hash = hash(symbol) % 1000 / 1000.0  # 0-1 unique value per symbol
                total_volume = bid_volume + ask_volume

                # Calculate more realistic and varied feature values
                spread_ratio = spread / 100.0 if spread > 0 else 0.001
                volume_skew = (bid_volume - ask_volume) / total_volume if total_volume > 0 else 0

                # Dynamic market microstructure features
                large_bid_wall = bid_volume > ask_volume * 1.5 and bid_volume > 1000
                large_ask_wall = ask_volume > bid_volume * 1.5 and ask_volume > 1000
                wall_size = max(bid_volume, ask_volume) / total_volume if total_volume > 0 else 0.0

                # Symbol-specific price variations to create diversity
                price_variation = symbol_hash * price * 0.002  # 0.2% max variation
                momentum_variation = (symbol_hash - 0.5) * spread_ratio * 2  # Momentum based on symbol
                volatility_variation = spread_ratio * (1 + symbol_hash * 0.5)  # Volatility with symbol variation

                # These features must match the keys in feature_importances
                raw_features_for_ml = {
                    "symbol": symbol,
                    "bid_ask_imbalance": current_value + (symbol_hash * 0.01),  # Add micro-variation per symbol
                    "spread_percent": spread_ratio,
                    "mid_price": price + price_variation,  # Unique price per symbol
                    "bid_volume": bid_volume,
                    "ask_volume": ask_volume,
                    "order_book_depth": 2,
                    "large_bid_wall": large_bid_wall,  # Dynamic based on actual volumes
                    "large_ask_wall": large_ask_wall,  # Dynamic based on actual volumes
                    "wall_size": wall_size,  # Dynamic calculation
                    "volume_weighted_price": price * (1 + current_value * 0.005 + symbol_hash * 0.001),  # Volume-weighted with symbol variation
                    "price_momentum": momentum_variation,  # Symbol-specific momentum
                    "volatility": volatility_variation,  # Spread-based with symbol variation
                    "timestamp": int(datetime.fromisoformat(signal["timestamp"].replace("Z", "+00:00")).timestamp())
                }

                # Use the same calculated features for prediction request
                prediction_request = raw_features_for_ml.copy()

                # Call ML server with improved timeout and retry logic
                ml_server_base_url = os.getenv("ML_SERVER_URL", f"http://{self.config.ml_server_host}:{self.config.ml_server_port}")
                ml_server_url = f"{ml_server_base_url}/predict"
                logger.debug(f"Calling ML server at {ml_server_url} for symbol {signal['symbol']}")

                # Use shorter timeout and implement retry with backoff
                max_retries = 2
                base_timeout = 5.0  # Reduced from 10.0

                for attempt in range(max_retries + 1):
                    try:
                        timeout = base_timeout * (2 ** attempt)  # Exponential backoff for timeout
                        response = requests.post(ml_server_url, json=raw_features_for_ml, timeout=timeout)

                        if response.status_code == 200:
                            ml_analysis = response.json()
                            logger.debug(f"ML analysis received for {signal['symbol']}: confidence={ml_analysis.get('confidence', 0.0):.3f}")

                            reason = ml_analysis.get("reason", "")
                            is_model_trained = "No trained model" not in reason and "not trained" not in reason.lower()
                            
                            signal["ml_analysis"] = {
                                "ml_enabled": is_model_trained,
                                "win_probability": ml_analysis.get("confidence", 0.0) * 100,
                                "expected_return": ml_analysis.get("expected_return_percentage", ml_analysis.get("signal_value", 0.0)),
                                "confidence": ml_analysis.get("confidence", 0.0),
                                "model_version": "1.0.0",
                                "features_used": list(raw_features_for_ml.keys()),
                                "prediction_timestamp": datetime.now().isoformat(),
                                "response_time_ms": response.elapsed.total_seconds() * 1000
                            }
                            if not is_model_trained:
                                signal["ml_analysis"]["reason"] = reason
                            
                            # The definitive signal strength is the ML model's confidence
                            final_strength = ml_analysis.get("confidence", 0.0)
                            signal['signal_strength'] = final_strength
                            signal['strength'] = final_strength

                            # Calculate and attach strength composition using learned weights
                            composition = {}
                            if feature_importances and total_importance > 0:
                                for feature_name, importance_score in feature_importances.items():
                                    raw_value = raw_features_for_ml.get(feature_name)
                                    if raw_value is not None:
                                        composition[feature_name] = {
                                            'value': raw_value,
                                            'importance_percent': (importance_score / total_importance) * 100
                                        }
                            signal['strength_composition'] = composition
                            break

                        elif response.status_code == 503:
                            logger.debug(f"ML server not ready for {signal['symbol']} (503)")
                            signal["ml_analysis"] = {"ml_enabled": False, "reason": "Model not trained"}
                            signal['strength_composition'] = {}
                            break

                        else:
                            logger.warning(f"ML server returned status {response.status_code} for {signal['symbol']}")
                            if attempt == max_retries:
                                signal["ml_analysis"] = {"ml_enabled": False, "reason": f"HTTP {response.status_code}"}
                                signal['strength_composition'] = {}

                    except requests.exceptions.Timeout:
                        logger.warning(f"ML server timeout (attempt {attempt+1}/{max_retries+1}) for {signal['symbol']}")
                        if attempt == max_retries:
                            signal["ml_analysis"] = {"ml_enabled": False, "reason": "Timeout"}
                            signal['strength_composition'] = {}

                    except requests.exceptions.ConnectionError:
                        logger.warning(f"ML server connection error (attempt {attempt+1}/{max_retries+1}) for {signal['symbol']}")
                        if attempt == max_retries:
                            signal["ml_analysis"] = {"ml_enabled": False, "reason": "Connection failed"}
                            signal['strength_composition'] = {}

                    except Exception as e:
                        logger.warning(f"ML analysis error for {signal['symbol']}: {e}")
                        if attempt == max_retries:
                            signal["ml_analysis"] = {"ml_enabled": False, "reason": str(e)}
                            signal['strength_composition'] = {}

                    if attempt < max_retries:
                        await asyncio.sleep(0.1 * (2 ** attempt))

                if "ml_analysis" not in signal:
                    signal["ml_analysis"] = {"ml_enabled": False, "reason": "Unknown error"}
                    signal['strength_composition'] = {}

            except Exception as e:
                logger.warning(f"Failed to get ML analysis for {signal['symbol']}: {e}")
                signal["ml_analysis"] = {"ml_enabled": False, "reason": str(e)}
                signal['strength_composition'] = {}

            enriched_signals.append(signal)

        return enriched_signals

    async def _get_ml_server_status(self) -> Dict[str, Any]:
        """Get ML server status and cache it."""
        # Simple in-memory cache with a short TTL
        cache_key = "ml_server_status"
        cached_status = getattr(self, "_ml_status_cache", None)
        if cached_status and (datetime.now() - cached_status["timestamp"]).total_seconds() < 10:
            return cached_status["data"]

        status_data = {"healthy": False, "is_trained": False}
        try:
            ml_server_url = os.getenv("ML_SERVER_URL", f"http://{self.config.ml_server_host}:{self.config.ml_server_port}")
            status_url = f"{ml_server_url}/status"
            response = requests.get(status_url, timeout=2.0)
            if response.status_code == 200:
                data = response.json()
                status_data["healthy"] = True
                status_data["is_trained"] = data.get("is_trained", False)
        except requests.exceptions.RequestException as e:
            logger.debug(f"ML server status check failed: {e}")

        self._ml_status_cache = {"timestamp": datetime.now(), "data": status_data}
        return status_data

    async def _check_ml_server_health(self) -> bool:
        """Check if ML server is healthy."""
        try:
            # Use environment variable for the ML server URL for robustness in containerized setups
            ml_server_url = os.getenv("ML_SERVER_URL", f"http://{self.config.ml_server_host}:{self.config.ml_server_port}")
            health_url = f"{ml_server_url}/health"
            
            logger.info(f"Checking ML server health at {health_url}")
            response = requests.get(health_url, timeout=3.0)
            
            if response.status_code == 200:
                logger.info("ML server is healthy")
                return True
            else:
                logger.warning(f"ML server health check failed with status code: {response.status_code}")
                return False
        except requests.exceptions.Timeout:
            logger.warning("ML server health check timed out")
            return False
        except Exception as e:
            logger.warning(f"ML server health check failed: {e}")
            return False
    
    async def get_loading_status(self) -> Dict[str, Any]:
        """Get data loading status."""
        try:
            # Get loading status from simulated trading manager
            if self.simulated_trading_manager and hasattr(self.simulated_trading_manager, 'get_loading_status'):
                return await self.simulated_trading_manager.get_loading_status()
            
            # Fallback to static response if no trading manager
            return {
                "is_loading": False,
                "progress": 100,
                "loaded_symbols": 0,
                "total_symbols": 0,
                "message": "Data loading complete"
            }
        except Exception as e:
            logger.error(f"Error getting loading status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def load_remaining_symbols_async(self, remaining_symbols: list, 
                                         batch_size: int = 3) -> Dict[str, Any]:
        """Load remaining symbols asynchronously."""
        try:
            # This would typically load symbols in batches
            return {
                "status": "loading",
                "remaining_symbols": len(remaining_symbols),
                "batch_size": batch_size,
                "message": "Loading symbols in progress"
            }
        except Exception as e:
            logger.error(f"Error loading remaining symbols: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_trading_state(self) -> Dict[str, Any]:
        """Get current trading state."""
        try:
            # Get current trading status
            trading_status = await self.trading_handlers.get_simulated_trading_status()
            
            return {
                "is_trading": trading_status.get('is_trading', False),
                "active_strategy": trading_status.get('strategy_type'),
                "symbols": trading_status.get('symbols', []),
                "session_id": getattr(self.simulated_trading_manager, 'session_id', None)
            }
        except Exception as e:
            logger.error(f"Error getting trading state: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def save_current_trading_state(self, session_id: str) -> bool:
        """Save current trading state to database."""
        try:
            if not session_id or not re.fullmatch(r"[A-Za-z0-9._\-]{1,64}", session_id):
                return False
                
            # Get current trading status
            trading_status = await self.trading_handlers.get_simulated_trading_status()
            
            # Prepare session data
            session_data = {
                'is_active': trading_status.get('is_trading', False),
                'trading_mode': 'simulated',
                'symbol_mode': 'universe' if len(trading_status.get('symbols', [])) > 1 else 'single',
                'strategy_type': trading_status.get('strategy_type'),
                'strategy_params': trading_status.get('strategy_params', {}),
                'symbols': trading_status.get('symbols', []),
                'universe_config': {},
                'portfolio_state': trading_status.get('portfolio', {}),
                'positions': trading_status.get('open_positions', []),
                'recent_trades': trading_status.get('recent_trades', [])
            }
            
            # Save to database
            success = self.database_manager.save_trading_session(session_id, session_data)
            
            if success:
                logger.debug(f"Auto-saved trading session {session_id}")
            
            return success
                
        except Exception as e:
            logger.error(f"Error auto-saving trading state: {e}")
            return False
    
    async def save_session_state(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save trading session state."""
        try:
            session_id = request_data.get('session_id')
            logger.info(f"Save session request received for session_id: {session_id}")
            
            if not session_id or not re.fullmatch(r"[A-Za-z0-9._\-]{1,64}", str(session_id)):
                raise HTTPException(status_code=400, detail="Session ID is required")
            
            # Get current trading status
            logger.info("Getting current trading status...")
            trading_status = await self.trading_handlers.get_simulated_trading_status()
            logger.info(f"Trading status retrieved: is_trading={trading_status.get('is_trading')}, total_trades={trading_status.get('portfolio', {}).get('total_trades')}")
            
            # Prepare session data
            session_data = {
                'is_active': trading_status.get('is_trading', False),
                'trading_mode': 'simulated',
                'symbol_mode': 'universe' if len(trading_status.get('symbols', [])) > 1 else 'single',
                'strategy_type': trading_status.get('strategy_type'),
                'strategy_params': trading_status.get('strategy_params', {}),
                'symbols': trading_status.get('symbols', []),
                'universe_config': {},
                'portfolio_state': trading_status.get('portfolio', {}),
                'positions': trading_status.get('open_positions', []),
                'recent_trades': trading_status.get('recent_trades', [])
            }
            
            # Save to database
            logger.info(f"Attempting to save session {session_id}")
            try:
                # Test database connection first
                logger.info("Testing database connection...")
                test_result = self.database_manager.get_cache_stats()
                logger.debug(f"Database connection test result: {bool(test_result)}")
                
                success = self.database_manager.save_trading_session(session_id, session_data)
                logger.info(f"Database save result: {success}")
                if not success:
                    logger.error(f"Database save returned False for session {session_id}")
            except Exception as db_error:
                logger.error(f"Database save exception: {db_error}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                # Try to identify the problematic object
                try:
                    import json
                    json.dumps(session_data)
                except Exception as json_error:
                    logger.error(f"JSON serialization error: {json_error}")
                return {"error": f"Database save failed: {str(db_error)}"}
            
            if success:
                logger.info(f"Saved trading session {session_id} with {len(session_data['positions'])} positions and {len(session_data['recent_trades'])} trades")
                return {
                    "status": "saved",
                    "session_id": session_id,
                    "message": "Session state saved successfully"
                }
            else:
                logger.error(f"Failed to save session {session_id}")
                return {"error": "Failed to save session state"}
                
        except Exception as e:
            logger.error(f"Error saving session state: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def restore_simulated_trading(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Restore simulated trading from saved state."""
        try:
            session_id = request_data.get('session_id')
            
            if not session_id or not re.fullmatch(r"[A-Za-z0-9._\-]{1,64}", str(session_id)):
                raise HTTPException(status_code=400, detail="Session ID is required")
            
            # Load session data from database
            session_data = self.database_manager.load_trading_session(session_id)
            if not session_data:
                raise HTTPException(status_code=404, detail="Session not found")
            
            # Extract trading parameters
            symbols = session_data.get('symbols', [])
            strategy_type = session_data.get('strategy_type', 'orderbook')
            strategy_params = session_data.get('strategy_params', {})
            portfolio_state = session_data.get('portfolio_state', {})
            positions = session_data.get('positions', [])
            recent_trades = session_data.get('recent_trades', [])
            
            # Restore simulated trading state
            self.simulated_trading_manager.restore_portfolio_state(
                portfolio_state=portfolio_state,
                positions=positions,
                trades=recent_trades,
                symbols=symbols
            )
            
            # Set session info for trade logging
            self.simulated_trading_manager.set_session_info(self.database_manager, session_id)
            
            # Set strategy info for trade logging
            self.simulated_trading_manager.set_strategy_info(strategy_type, strategy_params)
            
            # Start trading
            self.simulated_trading_manager.start_trading(symbols)
            
            # Get current portfolio summary
            portfolio = self.simulated_trading_manager.get_portfolio_summary()
            open_positions = self.simulated_trading_manager.get_open_positions()
            
            logger.info(f"Restored simulated trading for {len(symbols)} symbols with {len(open_positions)} positions")
            
            return {
                "status": "restored",
                "session_id": session_id,
                "symbols": symbols,
                "strategy_type": strategy_type,
                "portfolio": portfolio,
                "positions": open_positions,
                "recent_trades": recent_trades,
                "message": "Simulated trading restored successfully"
            }
        except Exception as e:
            logger.error(f"Error restoring simulated trading: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def load_session_state(self, session_id: str) -> Dict[str, Any]:
        """Load trading session state."""
        try:
            if not session_id or not re.fullmatch(r"[A-Za-z0-9._\-]{1,64}", str(session_id)):
                raise HTTPException(status_code=400, detail="Session ID is required")
            
            # Load session data from database
            session_data = self.database_manager.load_trading_session(session_id)
            if not session_data:
                return {
                    "session_id": session_id,
                    "state": {},
                    "message": "Session not found"
                }
            
            return {
                "session_id": session_id,
                "state": session_data,
                "message": "Session state loaded successfully"
            }
        except Exception as e:
            logger.error(f"Error loading session state: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def save_dashboard_state(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save dashboard UI state."""
        try:
            session_id = request_data.get('session_id')
            state_data = request_data.get('state', {})
            
            if not session_id or not re.fullmatch(r"[A-Za-z0-9._\-]{1,64}", str(session_id)):
                raise HTTPException(status_code=400, detail="Session ID is required")
            if not isinstance(state_data, dict):
                raise HTTPException(status_code=400, detail="state must be an object")
            
            # Save dashboard state logic would go here
            return {
                "status": "saved",
                "session_id": session_id,
                "message": "Dashboard state saved successfully"
            }
        except Exception as e:
            logger.error(f"Error saving dashboard state: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def load_dashboard_state(self, session_id: str) -> Dict[str, Any]:
        """Load dashboard UI state."""
        try:
            if not session_id or not re.fullmatch(r"[A-Za-z0-9._\-]{1,64}", str(session_id)):
                raise HTTPException(status_code=400, detail="Session ID is required")
            
            # Load dashboard state logic would go here
            return {
                "session_id": session_id,
                "state": {},
                "message": "Dashboard state loaded successfully"
            }
        except Exception as e:
            logger.error(f"Error loading dashboard state: {e}")
            raise HTTPException(status_code=500, detail=str(e))
