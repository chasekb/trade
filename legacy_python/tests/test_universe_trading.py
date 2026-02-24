#!/usr/bin/env python3
"""
Test universe trading functionality.
"""

import asyncio
import aiohttp
import json

class UniverseTradingTester:
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
    
    async def test_major_pairs_universe(self):
        """Test universe trading with major pairs."""
        print("Testing major pairs universe trading...")
        
        payload = {
            "symbols": ["BTC-USD", "ETH-USD", "ADA-USD", "SOL-USD", "DOT-USD"],
            "strategy_type": "sma",
            "mode": "simulated",
            "symbol_mode": "universe",
            "strategy_params": {
                "short_window": 10,
                "long_window": 20
            },
            "position_size": 2.0,
            "max_positions": 10,
            "universe_config": {
                "type": "major",
                "max_size": 10
            }
        }
        
        try:
            async with self.session.post(f"{self.base_url}/api/live-trading/start", 
                                       json=payload) as response:
                data = await response.json()
                
                if response.status == 200 and data.get('status') == 'success':
                    session_id = data['trading_session']['session_id']
                    self.trading_sessions.append(session_id)
                    print(f"  ✅ Major pairs universe started: {session_id}")
                    print(f"  ✅ Symbols: {data['trading_session']['symbols']}")
                    return True
                else:
                    print(f"  ❌ Failed: {data.get('error', 'Unknown error')}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def test_dex_tokens_universe(self):
        """Test universe trading with DEX tokens."""
        print("Testing DEX tokens universe trading...")
        
        payload = {
            "symbols": ["UNI-USD", "SUSHI-USD", "CAKE-USD"],
            "strategy_type": "rsi",
            "mode": "simulated",
            "symbol_mode": "universe",
            "strategy_params": {
                "window": 14,
                "overbought": 70,
                "oversold": 30
            },
            "position_size": 1.5,
            "max_positions": 5,
            "universe_config": {
                "type": "dex_tokens",
                "max_size": 5
            }
        }
        
        try:
            async with self.session.post(f"{self.base_url}/api/live-trading/start", 
                                       json=payload) as response:
                data = await response.json()
                
                if response.status == 200 and data.get('status') == 'success':
                    session_id = data['trading_session']['session_id']
                    self.trading_sessions.append(session_id)
                    print(f"  ✅ DEX tokens universe started: {session_id}")
                    print(f"  ✅ Symbols: {data['trading_session']['symbols']}")
                    return True
                else:
                    print(f"  ❌ Failed: {data.get('error', 'Unknown error')}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def test_meme_tokens_universe(self):
        """Test universe trading with meme tokens."""
        print("Testing meme tokens universe trading...")
        
        payload = {
            "symbols": ["DOGE-USD", "SHIB-USD", "PEPE-USD"],
            "strategy_type": "bollinger",
            "mode": "simulated",
            "symbol_mode": "universe",
            "strategy_params": {
                "window": 20,
                "std_dev": 2
            },
            "position_size": 1.0,
            "max_positions": 5,
            "universe_config": {
                "type": "meme_tokens",
                "max_size": 5
            }
        }
        
        try:
            async with self.session.post(f"{self.base_url}/api/live-trading/start", 
                                       json=payload) as response:
                data = await response.json()
                
                if response.status == 200 and data.get('status') == 'success':
                    session_id = data['trading_session']['session_id']
                    self.trading_sessions.append(session_id)
                    print(f"  ✅ Meme tokens universe started: {session_id}")
                    print(f"  ✅ Symbols: {data['trading_session']['symbols']}")
                    return True
                else:
                    print(f"  ❌ Failed: {data.get('error', 'Unknown error')}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def test_custom_universe(self):
        """Test universe trading with custom symbol selection."""
        print("Testing custom universe trading...")
        
        payload = {
            "symbols": ["BTC-USD", "ETH-USD", "LINK-USD", "AAVE-USD", "UNI-USD"],
            "strategy_type": "macd",
            "mode": "simulated",
            "symbol_mode": "universe",
            "strategy_params": {
                "fast_window": 12,
                "slow_window": 26,
                "signal_window": 9
            },
            "position_size": 1.0,
            "max_positions": 8,
            "universe_config": {
                "type": "custom",
                "max_size": 8
            }
        }
        
        try:
            async with self.session.post(f"{self.base_url}/api/live-trading/start", 
                                       json=payload) as response:
                data = await response.json()
                
                if response.status == 200 and data.get('status') == 'success':
                    session_id = data['trading_session']['session_id']
                    self.trading_sessions.append(session_id)
                    print(f"  ✅ Custom universe started: {session_id}")
                    print(f"  ✅ Symbols: {data['trading_session']['symbols']}")
                    return True
                else:
                    print(f"  ❌ Failed: {data.get('error', 'Unknown error')}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def test_invalid_universe_parameters(self):
        """Test invalid universe trading parameters."""
        print("Testing invalid universe parameters...")
        
        # Test too many symbols for max positions
        payload = {
            "symbols": ["BTC-USD", "ETH-USD", "ADA-USD", "SOL-USD", "DOT-USD", "LINK-USD"],
            "strategy_type": "sma",
            "mode": "simulated",
            "symbol_mode": "universe",
            "strategy_params": {},
            "position_size": 2.0,
            "max_positions": 3,  # Less than number of symbols
            "universe_config": {"type": "major", "max_size": 10}
        }
        
        try:
            async with self.session.post(f"{self.base_url}/api/live-trading/start", 
                                       json=payload) as response:
                data = await response.json()
                
                if response.status == 200 and data.get('error'):
                    print(f"  ✅ Too many symbols rejected: {data['error']}")
                    return True
                else:
                    print(f"  ❌ Too many symbols not rejected")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def test_single_symbol_fallback(self):
        """Test that single symbol trading still works."""
        print("Testing single symbol trading fallback...")
        
        payload = {
            "symbol": "BTC-USD",  # Old format
            "strategy_type": "sma",
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
                    print(f"  ✅ Single symbol trading works: {session_id}")
                    print(f"  ✅ Symbol: {data['trading_session']['symbols'][0]}")
                    return True
                else:
                    print(f"  ❌ Failed: {data.get('error', 'Unknown error')}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def test_stop_universe_trading(self):
        """Test stopping universe trading sessions."""
        print("Testing stop universe trading...")
        
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
    
    async def run_comprehensive_test(self):
        """Run comprehensive universe trading test."""
        print("🚀 Starting Universe Trading Test...")
        print("=" * 50)
        
        test_results = []
        
        # Test 1: Major Pairs Universe
        print("\n1. Testing Major Pairs Universe")
        result = await self.test_major_pairs_universe()
        test_results.append(("Major Pairs Universe", result))
        
        # Test 2: DEX Tokens Universe
        print("\n2. Testing DEX Tokens Universe")
        result = await self.test_dex_tokens_universe()
        test_results.append(("DEX Tokens Universe", result))
        
        # Test 3: Meme Tokens Universe
        print("\n3. Testing Meme Tokens Universe")
        result = await self.test_meme_tokens_universe()
        test_results.append(("Meme Tokens Universe", result))
        
        # Test 4: Custom Universe
        print("\n4. Testing Custom Universe")
        result = await self.test_custom_universe()
        test_results.append(("Custom Universe", result))
        
        # Test 5: Invalid Parameters
        print("\n5. Testing Invalid Parameters")
        result = await self.test_invalid_universe_parameters()
        test_results.append(("Invalid Parameters", result))
        
        # Test 6: Single Symbol Fallback
        print("\n6. Testing Single Symbol Fallback")
        result = await self.test_single_symbol_fallback()
        test_results.append(("Single Symbol Fallback", result))
        
        # Test 7: Stop Universe Trading
        print("\n7. Testing Stop Universe Trading")
        result = await self.test_stop_universe_trading()
        test_results.append(("Stop Universe Trading", result))
        
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
    async with UniverseTradingTester() as tester:
        success = await tester.run_comprehensive_test()
        
        print(f"\n🎉 Universe Trading Test Complete!")
        print(f"Result: {'PASS' if success else 'FAIL'}")
        
        return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
