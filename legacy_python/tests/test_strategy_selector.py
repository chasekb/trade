#!/usr/bin/env python3
"""
Test strategy selector functionality in live trading tab.
"""

import asyncio
import aiohttp
import json

class StrategySelectorTester:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        self.trading_sessions = []
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_single_symbol_strategy_selection(self):
        """Test strategy selection for single symbol trading."""
        print("Testing single symbol strategy selection...")
        
        strategies = ['sma', 'ema', 'rsi', 'bollinger', 'macd', 'stochastic', 'fibonacci', 'orderbook', 'dca', 'buyandhold']
        success_count = 0
        
        for strategy in strategies:
            payload = {
                "symbol": "BTC-USD",
                "strategy_type": strategy,
                "mode": "simulated",
                "strategy_params": self.get_strategy_params(strategy),
                "position_size": 5.0,
                "max_positions": 3
            }
            
            try:
                async with self.session.post(f"{self.base_url}/api/live-trading/start", 
                                           json=payload) as response:
                    data = await response.json()
                    
                    if response.status == 200 and data.get('status') == 'success':
                        session_id = data['trading_session']['session_id']
                        self.trading_sessions.append(session_id)
                        actual_strategy = data['trading_session']['strategy_type']
                        if actual_strategy == strategy:
                            print(f"  ✅ {strategy.upper()}: Correct strategy selected")
                            success_count += 1
                        else:
                            print(f"  ❌ {strategy.upper()}: Expected {strategy}, got {actual_strategy}")
                    else:
                        print(f"  ❌ {strategy.upper()}: Failed to start - {data.get('error')}")
                        
            except Exception as e:
                print(f"  ❌ {strategy.upper()}: Exception - {e}")
        
        return success_count == len(strategies)
    
    async def test_universe_strategy_selection(self):
        """Test strategy selection for universe trading."""
        print("Testing universe strategy selection...")
        
        strategies = ['sma', 'rsi', 'bollinger', 'macd', 'fibonacci', 'orderbook']
        success_count = 0
        
        for strategy in strategies:
            payload = {
                "symbols": ["BTC-USD", "ETH-USD", "ADA-USD"],
                "strategy_type": strategy,
                "mode": "simulated",
                "symbol_mode": "universe",
                "strategy_params": self.get_strategy_params(strategy),
                "position_size": 2.0,
                "max_positions": 10,
                "universe_config": {
                    "type": "major",
                    "max_size": None
                }
            }
            
            try:
                async with self.session.post(f"{self.base_url}/api/live-trading/start", 
                                           json=payload) as response:
                    data = await response.json()
                    
                    if response.status == 200 and data.get('status') == 'success':
                        session_id = data['trading_session']['session_id']
                        self.trading_sessions.append(session_id)
                        actual_strategy = data['trading_session']['strategy_type']
                        if actual_strategy == strategy:
                            print(f"  ✅ {strategy.upper()}: Correct strategy selected for universe")
                            success_count += 1
                        else:
                            print(f"  ❌ {strategy.upper()}: Expected {strategy}, got {actual_strategy}")
                    else:
                        print(f"  ❌ {strategy.upper()}: Failed to start - {data.get('error')}")
                        
            except Exception as e:
                print(f"  ❌ {strategy.upper()}: Exception - {e}")
        
        return success_count == len(strategies)
    
    async def test_strategy_parameter_handling(self):
        """Test that strategy parameters are correctly handled."""
        print("Testing strategy parameter handling...")
        
        # Test RSI with specific parameters
        payload = {
            "symbols": ["BTC-USD", "ETH-USD"],
            "strategy_type": "rsi",
            "mode": "simulated",
            "symbol_mode": "universe",
            "strategy_params": {
                "window": 21,
                "overbought": 80,
                "oversold": 20
            },
            "position_size": 1.5,
            "max_positions": 5,
            "universe_config": {
                "type": "custom",
                "max_size": None
            }
        }
        
        try:
            async with self.session.post(f"{self.base_url}/api/live-trading/start", 
                                       json=payload) as response:
                data = await response.json()
                
                if response.status == 200 and data.get('status') == 'success':
                    session_id = data['trading_session']['session_id']
                    self.trading_sessions.append(session_id)
                    params = data['trading_session']['strategy_params']
                    
                    if (params.get('window') == 21 and 
                        params.get('overbought') == 80 and 
                        params.get('oversold') == 20):
                        print(f"  ✅ RSI parameters correctly handled: {params}")
                        return True
                    else:
                        print(f"  ❌ RSI parameters incorrect: {params}")
                        return False
                else:
                    print(f"  ❌ Failed to start RSI strategy: {data.get('error')}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def test_fibonacci_strategy_universe(self):
        """Test Fibonacci strategy with universe trading."""
        print("Testing Fibonacci strategy with universe...")
        
        payload = {
            "symbols": ["BTC-USD", "ETH-USD", "SOL-USD", "ADA-USD", "DOT-USD"],
            "strategy_type": "fibonacci",
            "mode": "simulated",
            "symbol_mode": "universe",
            "strategy_params": {
                "fib_lookback_period": 50,
                "fib_levels": [0.236, 0.382, 0.5, 0.618, 0.786],
                "fib_confirmation_candles": 3
            },
            "position_size": 1.0,
            "max_positions": 20,
            "universe_config": {
                "type": "major",
                "max_size": None
            }
        }
        
        try:
            async with self.session.post(f"{self.base_url}/api/live-trading/start", 
                                       json=payload) as response:
                data = await response.json()
                
                if response.status == 200 and data.get('status') == 'success':
                    session_id = data['trading_session']['session_id']
                    self.trading_sessions.append(session_id)
                    strategy_type = data['trading_session']['strategy_type']
                    symbol_count = len(data['trading_session']['symbols'])
                    
                    if strategy_type == 'fibonacci' and symbol_count == 5:
                        print(f"  ✅ Fibonacci strategy with {symbol_count} symbols")
                        return True
                    else:
                        print(f"  ❌ Fibonacci strategy failed: {strategy_type}, {symbol_count} symbols")
                        return False
                else:
                    print(f"  ❌ Failed to start Fibonacci strategy: {data.get('error')}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def test_orderbook_strategy_universe(self):
        """Test Order Book strategy with universe trading."""
        print("Testing Order Book strategy with universe...")
        
        payload = {
            "symbols": ["BTC-USD", "ETH-USD"],
            "strategy_type": "orderbook",
            "mode": "simulated",
            "symbol_mode": "universe",
            "strategy_params": {
                "order_book_level": 5,
                "trade_history_limit": 100,
                "bid_ask_spread_threshold": 0.001,
                "volume_imbalance_threshold": 0.6,
                "large_trade_threshold": 10000
            },
            "position_size": 2.0,
            "max_positions": 5,
            "universe_config": {
                "type": "custom",
                "max_size": None
            }
        }
        
        try:
            async with self.session.post(f"{self.base_url}/api/live-trading/start", 
                                       json=payload) as response:
                data = await response.json()
                
                if response.status == 200 and data.get('status') == 'success':
                    session_id = data['trading_session']['session_id']
                    self.trading_sessions.append(session_id)
                    strategy_type = data['trading_session']['strategy_type']
                    params = data['trading_session']['strategy_params']
                    
                    if (strategy_type == 'orderbook' and 
                        params.get('order_book_level') == 5 and
                        params.get('trade_history_limit') == 100):
                        print(f"  ✅ Order Book strategy with custom parameters")
                        return True
                    else:
                        print(f"  ❌ Order Book strategy failed: {strategy_type}, {params}")
                        return False
                else:
                    print(f"  ❌ Failed to start Order Book strategy: {data.get('error')}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def test_stop_strategy_sessions(self):
        """Test stopping strategy sessions."""
        print("Testing stop strategy sessions...")
        
        if not self.trading_sessions:
            print("  ⚠️  No sessions to stop")
            return True
        
        success_count = 0
        for session_id in self.trading_sessions:
            payload = {"session_id": session_id}
            
            try:
                async with self.session.post(f"{self.base_url}/api/live-trading/stop", 
                                           json=payload) as response:
                    data = await response.json()
                    
                    if response.status == 200 and data.get('status') == 'success':
                        print(f"  ✅ Session {session_id} stopped")
                        success_count += 1
                    else:
                        print(f"  ❌ Failed to stop session {session_id}: {data.get('error')}")
                        
            except Exception as e:
                print(f"  ❌ Exception stopping session {session_id}: {e}")
        
        return success_count == len(self.trading_sessions)
    
    def get_strategy_params(self, strategy_type):
        """Get default parameters for a strategy type."""
        params_map = {
            'sma': {"short_window": 10, "long_window": 20},
            'ema': {"short_window": 10, "long_window": 20},
            'rsi': {"window": 14, "overbought": 70, "oversold": 30},
            'bollinger': {"window": 20, "std_dev": 2},
            'macd': {"fast_window": 12, "slow_window": 26, "signal_window": 9},
            'stochastic': {"k_window": 14, "d_window": 3, "overbought": 80, "oversold": 20},
            'fibonacci': {"fib_lookback_period": 20, "fib_levels": [0.236, 0.382, 0.5, 0.618, 0.786], "fib_confirmation_candles": 2},
            'orderbook': {"order_book_level": 3, "trade_history_limit": 50, "bid_ask_spread_threshold": 0.001, "volume_imbalance_threshold": 0.6, "large_trade_threshold": 10000},
            'dca': {"interval_days": 7, "amount_per_purchase": 100},
            'buyandhold': {}
        }
        return params_map.get(strategy_type, {})
    
    async def run_strategy_selector_test(self):
        """Run comprehensive strategy selector test."""
        print("🚀 Starting Strategy Selector Test...")
        print("=" * 50)
        
        test_results = []
        
        # Test 1: Single Symbol Strategy Selection
        print("\n1. Testing Single Symbol Strategy Selection")
        result = await self.test_single_symbol_strategy_selection()
        test_results.append(("Single Symbol Strategy Selection", result))
        
        # Test 2: Universe Strategy Selection
        print("\n2. Testing Universe Strategy Selection")
        result = await self.test_universe_strategy_selection()
        test_results.append(("Universe Strategy Selection", result))
        
        # Test 3: Strategy Parameter Handling
        print("\n3. Testing Strategy Parameter Handling")
        result = await self.test_strategy_parameter_handling()
        test_results.append(("Strategy Parameter Handling", result))
        
        # Test 4: Fibonacci Strategy Universe
        print("\n4. Testing Fibonacci Strategy Universe")
        result = await self.test_fibonacci_strategy_universe()
        test_results.append(("Fibonacci Strategy Universe", result))
        
        # Test 5: Order Book Strategy Universe
        print("\n5. Testing Order Book Strategy Universe")
        result = await self.test_orderbook_strategy_universe()
        test_results.append(("Order Book Strategy Universe", result))
        
        # Test 6: Stop Strategy Sessions
        print("\n6. Testing Stop Strategy Sessions")
        result = await self.test_stop_strategy_sessions()
        test_results.append(("Stop Strategy Sessions", result))
        
        # Analyze results
        print("\n📊 Test Results:")
        print("=" * 50)
        
        passed = 0
        total = len(test_results)
        
        for test_name, result in test_results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{test_name}: {status}")
            if result:
                passed += 1
        
        success_rate = (passed / total) * 100
        print(f"\nOverall Success Rate: {passed}/{total} ({success_rate:.1f}%)")
        
        return success_rate >= 80.0

async def main():
    """Main test execution."""
    async with StrategySelectorTester() as tester:
        success = await tester.run_strategy_selector_test()
        
        print(f"\n🎉 Strategy Selector Test Complete!")
        print(f"Result: {'PASS' if success else 'FAIL'}")
        
        return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
