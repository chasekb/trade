#!/usr/bin/env python3
"""
Test that live trading tab loads all available symbols correctly.
"""

import asyncio
import aiohttp
import json

class LiveTradingSymbolsTester:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_products_api(self):
        """Test that products API returns all categories."""
        print("Testing products API...")
        
        try:
            async with self.session.get(f"{self.base_url}/api/products") as response:
                data = await response.json()
                
                if response.status == 200 and data.get('status') == 'success':
                    categories = data.get('categories', {})
                    
                    expected_categories = ['major', 'dex_tokens', 'meme_tokens', 'stablecoins', 'all_usd']
                    missing_categories = [cat for cat in expected_categories if cat not in categories]
                    
                    if missing_categories:
                        print(f"  ❌ Missing categories: {missing_categories}")
                        return False
                    
                    total_products = data.get('total_products', 0)
                    all_usd_count = len(categories.get('all_usd', []))
                    
                    print(f"  ✅ Products API working: {total_products} total products")
                    print(f"  ✅ All USD pairs: {all_usd_count}")
                    print(f"  ✅ Major pairs: {len(categories.get('major', []))}")
                    print(f"  ✅ DEX tokens: {len(categories.get('dex_tokens', []))}")
                    print(f"  ✅ Meme tokens: {len(categories.get('meme_tokens', []))}")
                    print(f"  ✅ Stablecoins: {len(categories.get('stablecoins', []))}")
                    
                    return total_products > 300 and all_usd_count > 300
                else:
                    print(f"  ❌ API error: {data.get('error', 'Unknown error')}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def test_live_trading_with_different_symbols(self):
        """Test live trading with different symbol categories."""
        print("Testing live trading with different symbols...")
        
        # Test symbols from different categories
        test_symbols = [
            ('BTC-USD', 'major'),
            ('ETH-USD', 'major'),
            ('UNI-USD', 'dex_tokens'),
            ('DOGE-USD', 'meme_tokens'),
            ('DAI-USD', 'stablecoins'),
            ('ADA-USD', 'major'),
            ('SOL-USD', 'major')
        ]
        
        success_count = 0
        
        for symbol, category in test_symbols:
            print(f"  Testing {symbol} ({category})...")
            
            payload = {
                "symbol": symbol,
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
                        print(f"    ✅ {symbol} trading started: {session_id}")
                        
                        # Stop the session
                        stop_payload = {"session_id": session_id}
                        async with self.session.post(f"{self.base_url}/api/live-trading/stop", 
                                                   json=stop_payload) as stop_response:
                            stop_data = await stop_response.json()
                            if stop_data.get('status') == 'success':
                                print(f"    ✅ {symbol} trading stopped")
                                success_count += 1
                            else:
                                print(f"    ❌ Failed to stop {symbol}: {stop_data.get('error')}")
                    else:
                        print(f"    ❌ Failed to start {symbol}: {data.get('error', 'Unknown error')}")
                        
            except Exception as e:
                print(f"    ❌ Exception with {symbol}: {e}")
        
        print(f"  Symbol testing: {success_count}/{len(test_symbols)} successful")
        return success_count == len(test_symbols)
    
    async def test_dashboard_loading(self):
        """Test that dashboard loads without errors."""
        print("Testing dashboard loading...")
        
        try:
            async with self.session.get(f"{self.base_url}/") as response:
                if response.status == 200:
                    content = await response.text()
                    
                    # Check for live trading elements
                    required_elements = [
                        'tab-live-trading',
                        'live-trading-symbol',
                        'live-strategy-type',
                        'start-trading',
                        'stop-trading'
                    ]
                    
                    missing_elements = [elem for elem in required_elements if elem not in content]
                    
                    if missing_elements:
                        print(f"  ❌ Missing elements: {missing_elements}")
                        return False
                    
                    print("  ✅ Dashboard loads with all required elements")
                    return True
                else:
                    print(f"  ❌ Dashboard load failed: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def run_comprehensive_test(self):
        """Run comprehensive live trading symbols test."""
        print("🚀 Starting Live Trading Symbols Test...")
        print("=" * 50)
        
        test_results = []
        
        # Test 1: Products API
        print("\n1. Testing Products API")
        result = await self.test_products_api()
        test_results.append(("Products API", result))
        
        # Test 2: Dashboard Loading
        print("\n2. Testing Dashboard Loading")
        result = await self.test_dashboard_loading()
        test_results.append(("Dashboard Loading", result))
        
        # Test 3: Live Trading with Different Symbols
        print("\n3. Testing Live Trading with Different Symbols")
        result = await self.test_live_trading_with_different_symbols()
        test_results.append(("Live Trading Symbols", result))
        
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
    async with LiveTradingSymbolsTester() as tester:
        success = await tester.run_comprehensive_test()
        
        print(f"\n🎉 Live Trading Symbols Test Complete!")
        print(f"Result: {'PASS' if success else 'FAIL'}")
        
        return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
