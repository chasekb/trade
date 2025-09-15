#!/usr/bin/env python3
"""
Test unlimited universe trading functionality.
"""

import asyncio
import aiohttp
import json

class UnlimitedUniverseTester:
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
    
    async def test_large_universe_trading(self):
        """Test universe trading with a large number of symbols."""
        print("Testing large universe trading (50+ symbols)...")
        
        # Create a large universe of symbols
        large_universe = [
            "BTC-USD", "ETH-USD", "ADA-USD", "SOL-USD", "DOT-USD", "LINK-USD", "UNI-USD", "AAVE-USD",
            "SUSHI-USD", "CAKE-USD", "DOGE-USD", "SHIB-USD", "PEPE-USD", "BONK-USD", "WIF-USD",
            "MATIC-USD", "AVAX-USD", "ATOM-USD", "NEAR-USD", "FTM-USD", "ALGO-USD", "VET-USD",
            "ICP-USD", "FIL-USD", "TRX-USD", "XLM-USD", "HBAR-USD", "MANA-USD", "SAND-USD",
            "AXS-USD", "CHZ-USD", "ENJ-USD", "GALA-USD", "ILV-USD", "YGG-USD", "SLP-USD",
            "CRV-USD", "COMP-USD", "MKR-USD", "SNX-USD", "YFI-USD", "1INCH-USD", "BAL-USD",
            "LRC-USD", "ZRX-USD", "BAT-USD", "REP-USD", "KNC-USD", "REN-USD", "STORJ-USD"
        ]
        
        payload = {
            "symbols": large_universe,
            "strategy_type": "sma",
            "mode": "simulated",
            "symbol_mode": "universe",
            "strategy_params": {
                "short_window": 10,
                "long_window": 20
            },
            "position_size": 0.5,  # Smaller position size for large universe
            "max_positions": 100,  # High max positions
            "universe_config": {
                "type": "custom",
                "max_size": None  # No size limit
            }
        }
        
        try:
            async with self.session.post(f"{self.base_url}/api/live-trading/start", 
                                       json=payload) as response:
                data = await response.json()
                
                if response.status == 200 and data.get('status') == 'success':
                    session_id = data['trading_session']['session_id']
                    self.trading_sessions.append(session_id)
                    symbol_count = len(data['trading_session']['symbols'])
                    print(f"  ✅ Large universe started: {session_id}")
                    print(f"  ✅ Symbols: {symbol_count} symbols")
                    print(f"  ✅ First 5 symbols: {data['trading_session']['symbols'][:5]}")
                    return True
                else:
                    print(f"  ❌ Failed: {data.get('error', 'Unknown error')}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def test_no_size_limit(self):
        """Test universe trading with no size limit specified."""
        print("Testing no size limit universe trading...")
        
        payload = {
            "symbols": ["BTC-USD", "ETH-USD", "ADA-USD", "SOL-USD", "DOT-USD", "LINK-USD", "UNI-USD", "AAVE-USD"],
            "strategy_type": "rsi",
            "mode": "simulated",
            "symbol_mode": "universe",
            "strategy_params": {
                "window": 14,
                "overbought": 70,
                "oversold": 30
            },
            "position_size": 1.0,
            "max_positions": 50,
            "universe_config": {
                "type": "major",
                "max_size": None  # No size limit
            }
        }
        
        try:
            async with self.session.post(f"{self.base_url}/api/live-trading/start", 
                                       json=payload) as response:
                data = await response.json()
                
                if response.status == 200 and data.get('status') == 'success':
                    session_id = data['trading_session']['session_id']
                    self.trading_sessions.append(session_id)
                    symbol_count = len(data['trading_session']['symbols'])
                    print(f"  ✅ No size limit universe started: {session_id}")
                    print(f"  ✅ Symbols: {symbol_count} symbols")
                    return True
                else:
                    print(f"  ❌ Failed: {data.get('error', 'Unknown error')}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def test_zero_size_limit(self):
        """Test universe trading with zero size limit (should be treated as unlimited)."""
        print("Testing zero size limit universe trading...")
        
        payload = {
            "symbols": ["BTC-USD", "ETH-USD", "ADA-USD", "SOL-USD", "DOT-USD"],
            "strategy_type": "bollinger",
            "mode": "simulated",
            "symbol_mode": "universe",
            "strategy_params": {
                "window": 20,
                "std_dev": 2
            },
            "position_size": 2.0,
            "max_positions": 20,
            "universe_config": {
                "type": "custom",
                "max_size": 0  # Zero should be treated as unlimited
            }
        }
        
        try:
            async with self.session.post(f"{self.base_url}/api/live-trading/start", 
                                       json=payload) as response:
                data = await response.json()
                
                if response.status == 200 and data.get('status') == 'success':
                    session_id = data['trading_session']['session_id']
                    self.trading_sessions.append(session_id)
                    symbol_count = len(data['trading_session']['symbols'])
                    print(f"  ✅ Zero size limit universe started: {session_id}")
                    print(f"  ✅ Symbols: {symbol_count} symbols")
                    return True
                else:
                    print(f"  ❌ Failed: {data.get('error', 'Unknown error')}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def test_all_usd_universe(self):
        """Test trading on all USD pairs (should be unlimited)."""
        print("Testing all USD pairs universe trading...")
        
        payload = {
            "symbols": [],  # Will be populated by universe type
            "strategy_type": "macd",
            "mode": "simulated",
            "symbol_mode": "universe",
            "strategy_params": {
                "fast_window": 12,
                "slow_window": 26,
                "signal_window": 9
            },
            "position_size": 0.1,  # Very small position size for large universe
            "max_positions": 200,  # High max positions
            "universe_config": {
                "type": "all_usd",
                "max_size": None  # No size limit
            }
        }
        
        try:
            async with self.session.post(f"{self.base_url}/api/live-trading/start", 
                                       json=payload) as response:
                data = await response.json()
                
                if response.status == 200 and data.get('status') == 'success':
                    session_id = data['trading_session']['session_id']
                    self.trading_sessions.append(session_id)
                    symbol_count = len(data['trading_session']['symbols'])
                    print(f"  ✅ All USD universe started: {session_id}")
                    print(f"  ✅ Symbols: {symbol_count} symbols")
                    print(f"  ✅ Sample symbols: {data['trading_session']['symbols'][:10]}")
                    return True
                else:
                    print(f"  ❌ Failed: {data.get('error', 'Unknown error')}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def test_stop_unlimited_universe(self):
        """Test stopping unlimited universe trading sessions."""
        print("Testing stop unlimited universe trading...")
        
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
    
    async def run_unlimited_test(self):
        """Run comprehensive unlimited universe trading test."""
        print("🚀 Starting Unlimited Universe Trading Test...")
        print("=" * 60)
        
        test_results = []
        
        # Test 1: Large Universe (50+ symbols)
        print("\n1. Testing Large Universe Trading")
        result = await self.test_large_universe_trading()
        test_results.append(("Large Universe Trading", result))
        
        # Test 2: No Size Limit
        print("\n2. Testing No Size Limit")
        result = await self.test_no_size_limit()
        test_results.append(("No Size Limit", result))
        
        # Test 3: Zero Size Limit
        print("\n3. Testing Zero Size Limit")
        result = await self.test_zero_size_limit()
        test_results.append(("Zero Size Limit", result))
        
        # Test 4: All USD Universe
        print("\n4. Testing All USD Universe")
        result = await self.test_all_usd_universe()
        test_results.append(("All USD Universe", result))
        
        # Test 5: Stop Unlimited Universe
        print("\n5. Testing Stop Unlimited Universe")
        result = await self.test_stop_unlimited_universe()
        test_results.append(("Stop Unlimited Universe", result))
        
        # Analyze results
        print("\n📊 Test Results:")
        print("=" * 60)
        
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
    async with UnlimitedUniverseTester() as tester:
        success = await tester.run_unlimited_test()
        
        print(f"\n🎉 Unlimited Universe Trading Test Complete!")
        print(f"Result: {'PASS' if success else 'FAIL'}")
        
        return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
