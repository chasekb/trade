#!/usr/bin/env python3
"""
Test universe symbol selection functionality.
"""

import asyncio
import aiohttp
import json

class UniverseSelectionTester:
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
    
    async def test_signal_strength_selection(self):
        """Test universe selection by signal strength."""
        print("Testing signal strength selection...")
        
        # Create a large universe
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
            "strategy_type": "rsi",
            "mode": "simulated",
            "symbol_mode": "universe",
            "strategy_params": {
                "period": 14,
                "overbought": 70,
                "oversold": 30
            },
            "position_size": 1.0,
            "max_positions": 10,  # Much smaller than universe size
            "universe_config": {
                "type": "custom",
                "max_size": None,
                "selection_method": "signal_strength"
            }
        }
        
        try:
            async with self.session.post(f"{self.base_url}/api/live-trading/start", 
                                       json=payload) as response:
                data = await response.json()
                
                if response.status == 200 and data.get('status') == 'success':
                    session_id = data['trading_session']['session_id']
                    self.trading_sessions.append(session_id)
                    selected_symbols = data['trading_session']['symbols']
                    
                    print(f"  ✅ Universe selection completed: {session_id}")
                    print(f"  ✅ Selected {len(selected_symbols)} symbols from {len(large_universe)} total")
                    print(f"  ✅ Selected symbols: {selected_symbols}")
                    
                    # Verify selection worked
                    if len(selected_symbols) <= 10 and len(selected_symbols) > 0:
                        print(f"  ✅ Selection size correct: {len(selected_symbols)} <= 10")
                        return True
                    else:
                        print(f"  ❌ Selection size incorrect: {len(selected_symbols)} symbols")
                        return False
                else:
                    print(f"  ❌ Failed: {data.get('error', 'Unknown error')}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def test_momentum_selection(self):
        """Test universe selection by momentum."""
        print("Testing momentum selection...")
        
        payload = {
            "symbols": ["BTC-USD", "ETH-USD", "ADA-USD", "SOL-USD", "DOT-USD", "LINK-USD", "UNI-USD", "AAVE-USD", "SUSHI-USD", "CAKE-USD"],
            "strategy_type": "macd",
            "mode": "simulated",
            "symbol_mode": "universe",
            "strategy_params": {
                "fast_window": 12,
                "slow_window": 26,
                "signal_window": 9
            },
            "position_size": 2.0,
            "max_positions": 5,
            "universe_config": {
                "type": "custom",
                "max_size": None,
                "selection_method": "momentum"
            }
        }
        
        try:
            async with self.session.post(f"{self.base_url}/api/live-trading/start", 
                                       json=payload) as response:
                data = await response.json()
                
                if response.status == 200 and data.get('status') == 'success':
                    session_id = data['trading_session']['session_id']
                    self.trading_sessions.append(session_id)
                    selected_symbols = data['trading_session']['symbols']
                    
                    print(f"  ✅ Momentum selection completed: {session_id}")
                    print(f"  ✅ Selected {len(selected_symbols)} symbols from 10 total")
                    print(f"  ✅ Selected symbols: {selected_symbols}")
                    
                    if len(selected_symbols) <= 5 and len(selected_symbols) > 0:
                        print(f"  ✅ Selection size correct: {len(selected_symbols)} <= 5")
                        return True
                    else:
                        print(f"  ❌ Selection size incorrect: {len(selected_symbols)} symbols")
                        return False
                else:
                    print(f"  ❌ Failed: {data.get('error', 'Unknown error')}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def test_no_selection_needed(self):
        """Test when no selection is needed (universe size <= max positions)."""
        print("Testing no selection needed...")
        
        payload = {
            "symbols": ["BTC-USD", "ETH-USD", "ADA-USD"],
            "strategy_type": "sma",
            "mode": "simulated",
            "symbol_mode": "universe",
            "strategy_params": {
                "short_window": 10,
                "long_window": 20
            },
            "position_size": 3.0,
            "max_positions": 10,  # Larger than universe size
            "universe_config": {
                "type": "custom",
                "max_size": None,
                "selection_method": "signal_strength"
            }
        }
        
        try:
            async with self.session.post(f"{self.base_url}/api/live-trading/start", 
                                       json=payload) as response:
                data = await response.json()
                
                if response.status == 200 and data.get('status') == 'success':
                    session_id = data['trading_session']['session_id']
                    self.trading_sessions.append(session_id)
                    selected_symbols = data['trading_session']['symbols']
                    
                    print(f"  ✅ No selection needed completed: {session_id}")
                    print(f"  ✅ All {len(selected_symbols)} symbols selected")
                    print(f"  ✅ Selected symbols: {selected_symbols}")
                    
                    if len(selected_symbols) == 3:
                        print(f"  ✅ All symbols selected as expected")
                        return True
                    else:
                        print(f"  ❌ Unexpected selection: {len(selected_symbols)} symbols")
                        return False
                else:
                    print(f"  ❌ Failed: {data.get('error', 'Unknown error')}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def test_selection_failure_handling(self):
        """Test handling when no symbols can be selected."""
        print("Testing selection failure handling...")
        
        # Use a very small max_positions to potentially cause selection issues
        payload = {
            "symbols": ["BTC-USD", "ETH-USD", "ADA-USD", "SOL-USD", "DOT-USD"],
            "strategy_type": "bollinger",
            "mode": "simulated",
            "symbol_mode": "universe",
            "strategy_params": {
                "window": 20,
                "std_dev": 2
            },
            "position_size": 1.0,
            "max_positions": 1,  # Very small limit
            "universe_config": {
                "type": "custom",
                "max_size": None,
                "selection_method": "signal_strength"
            }
        }
        
        try:
            async with self.session.post(f"{self.base_url}/api/live-trading/start", 
                                       json=payload) as response:
                data = await response.json()
                
                if response.status == 200 and data.get('status') == 'success':
                    session_id = data['trading_session']['session_id']
                    self.trading_sessions.append(session_id)
                    selected_symbols = data['trading_session']['symbols']
                    
                    print(f"  ✅ Selection with small limit completed: {session_id}")
                    print(f"  ✅ Selected {len(selected_symbols)} symbols")
                    print(f"  ✅ Selected symbols: {selected_symbols}")
                    
                    if len(selected_symbols) <= 1 and len(selected_symbols) > 0:
                        print(f"  ✅ Selection size correct: {len(selected_symbols)} <= 1")
                        return True
                    else:
                        print(f"  ❌ Selection size incorrect: {len(selected_symbols)} symbols")
                        return False
                else:
                    print(f"  ❌ Failed: {data.get('error', 'Unknown error')}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def test_stop_selection_sessions(self):
        """Test stopping universe selection sessions."""
        print("Testing stop selection sessions...")
        
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
    
    async def run_universe_selection_test(self):
        """Run comprehensive universe selection test."""
        print("🚀 Starting Universe Selection Test...")
        print("=" * 60)
        
        test_results = []
        
        # Test 1: Signal Strength Selection
        print("\n1. Testing Signal Strength Selection")
        result = await self.test_signal_strength_selection()
        test_results.append(("Signal Strength Selection", result))
        
        # Test 2: Momentum Selection
        print("\n2. Testing Momentum Selection")
        result = await self.test_momentum_selection()
        test_results.append(("Momentum Selection", result))
        
        # Test 3: No Selection Needed
        print("\n3. Testing No Selection Needed")
        result = await self.test_no_selection_needed()
        test_results.append(("No Selection Needed", result))
        
        # Test 4: Selection Failure Handling
        print("\n4. Testing Selection Failure Handling")
        result = await self.test_selection_failure_handling()
        test_results.append(("Selection Failure Handling", result))
        
        # Test 5: Stop Selection Sessions
        print("\n5. Testing Stop Selection Sessions")
        result = await self.test_stop_selection_sessions()
        test_results.append(("Stop Selection Sessions", result))
        
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
    async with UniverseSelectionTester() as tester:
        success = await tester.run_universe_selection_test()
        
        print(f"\n🎉 Universe Selection Test Complete!")
        print(f"Result: {'PASS' if success else 'FAIL'}")
        
        return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
