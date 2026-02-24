#!/usr/bin/env python3
"""
Test live trading functionality including simulated and live trading modes.
"""

import asyncio
import aiohttp
import json
import time

class LiveTradingTester:
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
    
    async def test_start_simulated_trading(self, symbol="BTC-USD", strategy="sma"):
        """Test starting simulated trading."""
        print(f"Testing simulated trading: {symbol} with {strategy}")
        
        payload = {
            "symbol": symbol,
            "strategy_type": strategy,
            "mode": "simulated",
            "strategy_params": {
                "short_window": 10,
                "long_window": 20
            },
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
                    print(f"  ✅ Simulated trading started: {session_id}")
                    return True
                else:
                    print(f"  ❌ Failed: {data.get('error', 'Unknown error')}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def test_start_live_trading(self, symbol="ETH-USD", strategy="rsi"):
        """Test starting live trading (simulation)."""
        print(f"Testing live trading: {symbol} with {strategy}")
        
        payload = {
            "symbol": symbol,
            "strategy_type": strategy,
            "mode": "live",
            "strategy_params": {
                "window": 14,
                "overbought": 70,
                "oversold": 30
            },
            "position_size": 2.0,
            "max_positions": 2
        }
        
        try:
            async with self.session.post(f"{self.base_url}/api/live-trading/start", 
                                       json=payload) as response:
                data = await response.json()
                
                if response.status == 200 and data.get('status') == 'success':
                    session_id = data['trading_session']['session_id']
                    self.trading_sessions.append(session_id)
                    print(f"  ✅ Live trading started: {session_id}")
                    return True
                else:
                    print(f"  ❌ Failed: {data.get('error', 'Unknown error')}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def test_stop_trading(self, session_id):
        """Test stopping a trading session."""
        print(f"Testing stop trading: {session_id}")
        
        payload = {"session_id": session_id}
        
        try:
            async with self.session.post(f"{self.base_url}/api/live-trading/stop", 
                                       json=payload) as response:
                data = await response.json()
                
                if response.status == 200 and data.get('status') == 'success':
                    print(f"  ✅ Trading stopped: {session_id}")
                    return True
                else:
                    print(f"  ❌ Failed: {data.get('error', 'Unknown error')}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def test_get_positions(self):
        """Test getting current positions."""
        print("Testing get positions...")
        
        try:
            async with self.session.get(f"{self.base_url}/api/live-trading/positions") as response:
                data = await response.json()
                
                if response.status == 200 and data.get('status') == 'success':
                    positions = data.get('positions', [])
                    print(f"  ✅ Positions retrieved: {len(positions)} positions")
                    return True
                else:
                    print(f"  ❌ Failed: {data.get('error', 'Unknown error')}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def test_get_trading_history(self):
        """Test getting trading history."""
        print("Testing get trading history...")
        
        try:
            async with self.session.get(f"{self.base_url}/api/live-trading/history") as response:
                data = await response.json()
                
                if response.status == 200 and data.get('status') == 'success':
                    trades = data.get('trades', [])
                    print(f"  ✅ Trading history retrieved: {len(trades)} trades")
                    return True
                else:
                    print(f"  ❌ Failed: {data.get('error', 'Unknown error')}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def test_strategy_parameters(self):
        """Test different strategy parameters."""
        strategies = [
            ("sma", {"short_window": 5, "long_window": 15}),
            ("ema", {"short_window": 8, "long_window": 21}),
            ("rsi", {"window": 21, "overbought": 75, "oversold": 25}),
            ("bollinger", {"window": 25, "std_dev": 2.5}),
            ("macd", {"fast_window": 8, "slow_window": 21, "signal_window": 7}),
            ("fibonacci", {"fib_lookback_period": 30, "fib_levels": [0.236, 0.382, 0.5, 0.618], "fib_confirmation_candles": 3}),
            ("orderbook", {"order_book_level": 10, "trade_history_limit": 200, "bid_ask_spread_threshold": 0.0005, "volume_imbalance_threshold": 0.7, "large_trade_threshold": 15000})
        ]
        
        print("Testing different strategy parameters...")
        success_count = 0
        
        for strategy, params in strategies:
            payload = {
                "symbol": "BTC-USD",
                "strategy_type": strategy,
                "mode": "simulated",
                "strategy_params": params,
                "position_size": 3.0,
                "max_positions": 2
            }
            
            try:
                async with self.session.post(f"{self.base_url}/api/live-trading/start", 
                                           json=payload) as response:
                    data = await response.json()
                    
                    if response.status == 200 and data.get('status') == 'success':
                        session_id = data['trading_session']['session_id']
                        self.trading_sessions.append(session_id)
                        print(f"  ✅ {strategy} strategy started: {session_id}")
                        success_count += 1
                        
                        # Stop the session immediately
                        await self.test_stop_trading(session_id)
                    else:
                        print(f"  ❌ {strategy} strategy failed: {data.get('error', 'Unknown error')}")
                        
            except Exception as e:
                print(f"  ❌ {strategy} strategy exception: {e}")
        
        print(f"Strategy parameter tests: {success_count}/{len(strategies)} successful")
        return success_count == len(strategies)
    
    async def test_invalid_parameters(self):
        """Test invalid parameters handling."""
        print("Testing invalid parameters...")
        
        # Test invalid mode
        payload = {
            "symbol": "BTC-USD",
            "strategy_type": "sma",
            "mode": "invalid_mode",
            "strategy_params": {},
            "position_size": 5.0,
            "max_positions": 3
        }
        
        try:
            async with self.session.post(f"{self.base_url}/api/live-trading/start", 
                                       json=payload) as response:
                data = await response.json()
                
                if response.status == 200 and data.get('error'):
                    print(f"  ✅ Invalid mode rejected: {data['error']}")
                else:
                    print(f"  ❌ Invalid mode not rejected")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
        
        # Test invalid strategy
        payload = {
            "symbol": "BTC-USD",
            "strategy_type": "invalid_strategy",
            "mode": "simulated",
            "strategy_params": {},
            "position_size": 5.0,
            "max_positions": 3
        }
        
        try:
            async with self.session.post(f"{self.base_url}/api/live-trading/start", 
                                       json=payload) as response:
                data = await response.json()
                
                if response.status == 200 and data.get('error'):
                    print(f"  ✅ Invalid strategy rejected: {data['error']}")
                    return True
                else:
                    print(f"  ❌ Invalid strategy not rejected")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def run_comprehensive_test(self):
        """Run comprehensive live trading tests."""
        print("🚀 Starting Live Trading Test Suite...")
        print("=" * 50)
        
        test_results = []
        
        # Test 1: Simulated Trading
        print("\n1. Testing Simulated Trading")
        result = await self.test_start_simulated_trading()
        test_results.append(("Simulated Trading Start", result))
        
        # Test 2: Live Trading
        print("\n2. Testing Live Trading")
        result = await self.test_start_live_trading()
        test_results.append(("Live Trading Start", result))
        
        # Test 3: Stop Trading
        print("\n3. Testing Stop Trading")
        if self.trading_sessions:
            result = await self.test_stop_trading(self.trading_sessions[0])
            test_results.append(("Stop Trading", result))
        
        # Test 4: Get Positions
        print("\n4. Testing Get Positions")
        result = await self.test_get_positions()
        test_results.append(("Get Positions", result))
        
        # Test 5: Get Trading History
        print("\n6. Testing Get Trading History")
        result = await self.test_get_trading_history()
        test_results.append(("Get Trading History", result))
        
        # Test 6: Strategy Parameters
        print("\n7. Testing Strategy Parameters")
        result = await self.test_strategy_parameters()
        test_results.append(("Strategy Parameters", result))
        
        # Test 7: Invalid Parameters
        print("\n8. Testing Invalid Parameters")
        result = await self.test_invalid_parameters()
        test_results.append(("Invalid Parameters", result))
        
        # Clean up any remaining sessions
        print("\n9. Cleaning up remaining sessions...")
        for session_id in self.trading_sessions[1:]:  # Skip first one already stopped
            await self.test_stop_trading(session_id)
        
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
        
        return success_rate >= 80.0  # Consider 80%+ success rate as passing

async def main():
    """Main test execution."""
    async with LiveTradingTester() as tester:
        success = await tester.run_comprehensive_test()
        
        print(f"\n🎉 Live Trading Test Complete!")
        print(f"Result: {'PASS' if success else 'FAIL'}")
        
        return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
