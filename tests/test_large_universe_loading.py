#!/usr/bin/env python3
"""
Test large universe loading functionality.
"""

import asyncio
import aiohttp
import json

class LargeUniverseTester:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_products_api_categories(self):
        """Test that products API returns all categories with correct counts."""
        print("Testing products API categories...")
        
        try:
            async with self.session.get(f"{self.base_url}/api/products") as response:
                data = await response.json()
                
                if response.status == 200 and data.get('status') == 'success':
                    categories = data['categories']
                    
                    print(f"  ✅ Total products: {data.get('total_products', 0)}")
                    print(f"  ✅ Major pairs: {len(categories.get('major', []))}")
                    print(f"  ✅ DEX tokens: {len(categories.get('dex_tokens', []))}")
                    print(f"  ✅ Meme tokens: {len(categories.get('meme_tokens', []))}")
                    print(f"  ✅ Stablecoins: {len(categories.get('stablecoins', []))}")
                    print(f"  ✅ All USD pairs: {len(categories.get('all_usd', []))}")
                    
                    # Check if we have enough symbols for large universe testing
                    all_usd_count = len(categories.get('all_usd', []))
                    if all_usd_count > 100:
                        print(f"  ✅ Sufficient symbols for large universe testing: {all_usd_count}")
                        return True
                    else:
                        print(f"  ❌ Insufficient symbols for large universe testing: {all_usd_count}")
                        return False
                else:
                    print(f"  ❌ Failed to get products: {data.get('error')}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def test_large_universe_with_products(self):
        """Test large universe trading by first getting products, then using them."""
        print("Testing large universe with products API...")
        
        # First, get the products
        try:
            async with self.session.get(f"{self.base_url}/api/products") as response:
                data = await response.json()
                
                if response.status == 200 and data.get('status') == 'success':
                    categories = data['categories']
                    all_usd_symbols = categories.get('all_usd', [])
                    
                    if len(all_usd_symbols) < 50:
                        print(f"  ❌ Not enough symbols in all_usd: {len(all_usd_symbols)}")
                        return False
                    
                    # Take a large subset (first 100 symbols)
                    large_universe = all_usd_symbols[:100]
                    
                    # Now test universe trading with these symbols
                    payload = {
                        "symbols": large_universe,
                        "strategy_type": "sma",
                        "mode": "simulated",
                        "symbol_mode": "universe",
                        "strategy_params": {
                            "short_window": 10,
                            "long_window": 20
                        },
                        "position_size": 0.1,  # Very small position size
                        "max_positions": 200,  # High max positions
                        "universe_config": {
                            "type": "all_usd",
                            "max_size": None
                        }
                    }
                    
                    async with self.session.post(f"{self.base_url}/api/live-trading/start", 
                                               json=payload) as response:
                        data = await response.json()
                        
                        if response.status == 200 and data.get('status') == 'success':
                            session_id = data['trading_session']['session_id']
                            symbol_count = len(data['trading_session']['symbols'])
                            
                            print(f"  ✅ Large universe started: {session_id}")
                            print(f"  ✅ Symbols loaded: {symbol_count}")
                            print(f"  ✅ First 5 symbols: {data['trading_session']['symbols'][:5]}")
                            
                            # Stop the session
                            stop_payload = {"session_id": session_id}
                            async with self.session.post(f"{self.base_url}/api/live-trading/stop", 
                                                       json=stop_payload) as stop_response:
                                stop_data = await stop_response.json()
                                if stop_data.get('status') == 'success':
                                    print(f"  ✅ Session stopped successfully")
                                
                            return symbol_count >= 50  # Should have at least 50 symbols
                        else:
                            print(f"  ❌ Failed to start large universe: {data.get('error')}")
                            return False
                else:
                    print(f"  ❌ Failed to get products: {data.get('error')}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def test_major_pairs_unlimited(self):
        """Test that major pairs can be used without the 24 symbol limit."""
        print("Testing major pairs unlimited...")
        
        # First, get the products to see how many major pairs we actually have
        try:
            async with self.session.get(f"{self.base_url}/api/products") as response:
                data = await response.json()
                
                if response.status == 200 and data.get('status') == 'success':
                    categories = data['categories']
                    major_symbols = categories.get('major', [])
                    
                    print(f"  ✅ Major pairs available: {len(major_symbols)}")
                    
                    if len(major_symbols) > 24:
                        print(f"  ✅ More than 24 major pairs available: {len(major_symbols)}")
                        
                        # Test with all major pairs
                        payload = {
                            "symbols": major_symbols,
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
                                "max_size": None
                            }
                        }
                        
                        async with self.session.post(f"{self.base_url}/api/live-trading/start", 
                                                   json=payload) as response:
                            data = await response.json()
                            
                            if response.status == 200 and data.get('status') == 'success':
                                session_id = data['trading_session']['session_id']
                                symbol_count = len(data['trading_session']['symbols'])
                                
                                print(f"  ✅ Major pairs universe started: {session_id}")
                                print(f"  ✅ Symbols used: {symbol_count}")
                                
                                # Stop the session
                                stop_payload = {"session_id": session_id}
                                async with self.session.post(f"{self.base_url}/api/live-trading/stop", 
                                                           json=stop_payload) as stop_response:
                                    stop_data = await stop_response.json()
                                    if stop_data.get('status') == 'success':
                                        print(f"  ✅ Session stopped successfully")
                                
                                return symbol_count == len(major_symbols)
                            else:
                                print(f"  ❌ Failed to start major pairs universe: {data.get('error')}")
                                return False
                    else:
                        print(f"  ⚠️  Only {len(major_symbols)} major pairs available (expected more than 24)")
                        return True  # Not an error, just limited data
                else:
                    print(f"  ❌ Failed to get products: {data.get('error')}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def run_large_universe_test(self):
        """Run comprehensive large universe test."""
        print("🚀 Starting Large Universe Test...")
        print("=" * 50)
        
        test_results = []
        
        # Test 1: Products API Categories
        print("\n1. Testing Products API Categories")
        result = await self.test_products_api_categories()
        test_results.append(("Products API Categories", result))
        
        # Test 2: Large Universe with Products
        print("\n2. Testing Large Universe with Products")
        result = await self.test_large_universe_with_products()
        test_results.append(("Large Universe with Products", result))
        
        # Test 3: Major Pairs Unlimited
        print("\n3. Testing Major Pairs Unlimited")
        result = await self.test_major_pairs_unlimited()
        test_results.append(("Major Pairs Unlimited", result))
        
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
    async with LargeUniverseTester() as tester:
        success = await tester.run_large_universe_test()
        
        print(f"\n🎉 Large Universe Test Complete!")
        print(f"Result: {'PASS' if success else 'FAIL'}")
        
        return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
