#!/usr/bin/env python3
"""
Test backtest details functionality to debug the show details issue.
"""

import asyncio
import aiohttp
import json

class BacktestDetailsTester:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_backtest_api_structure(self):
        """Test the structure of the backtest API response."""
        print("Testing backtest API structure...")
        
        try:
            async with self.session.get(f"{self.base_url}/api/backtest/1") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    print(f"  ✅ API Response Status: {response.status}")
                    print(f"  ✅ Response Keys: {list(data.keys())}")
                    
                    if 'results' in data:
                        print(f"  ✅ Results Keys: {list(data['results'].keys())}")
                        
                        if 'result' in data['results']:
                            result_keys = list(data['results']['result'].keys())
                            print(f"  ✅ Result Keys: {result_keys}")
                            
                            # Check for required fields
                            required_fields = ['total_return', 'win_rate', 'total_trades', 'net_profit', 'final_balance']
                            missing_fields = [field for field in required_fields if field not in data['results']['result']]
                            
                            if missing_fields:
                                print(f"  ❌ Missing required fields: {missing_fields}")
                                return False
                            else:
                                print(f"  ✅ All required fields present")
                                return True
                        else:
                            print(f"  ❌ Missing 'result' key in results")
                            return False
                    else:
                        print(f"  ❌ Missing 'results' key")
                        return False
                else:
                    print(f"  ❌ API Error: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def test_backtest_history_api(self):
        """Test the backtest history API."""
        print("Testing backtest history API...")
        
        try:
            async with self.session.get(f"{self.base_url}/api/backtest-history") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    print(f"  ✅ History API Status: {response.status}")
                    print(f"  ✅ History Keys: {list(data.keys())}")
                    
                    if 'backtests' in data:
                        backtests = data['backtests']
                        print(f"  ✅ Number of backtests: {len(backtests)}")
                        
                        if len(backtests) > 0:
                            first_backtest = backtests[0]
                            print(f"  ✅ First backtest ID: {first_backtest.get('id')}")
                            print(f"  ✅ First backtest keys: {list(first_backtest.keys())}")
                            
                            # Test getting details for first backtest
                            backtest_id = first_backtest.get('id')
                            if backtest_id:
                                return await self.test_individual_backtest(backtest_id)
                        else:
                            print(f"  ⚠️  No backtests found in history")
                            return True
                    else:
                        print(f"  ❌ Missing 'backtests' key in history")
                        return False
                else:
                    print(f"  ❌ History API Error: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def test_individual_backtest(self, backtest_id):
        """Test getting individual backtest details."""
        print(f"Testing individual backtest {backtest_id}...")
        
        try:
            async with self.session.get(f"{self.base_url}/api/backtest/{backtest_id}") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    print(f"  ✅ Individual backtest status: {response.status}")
                    print(f"  ✅ Backtest ID: {data.get('id')}")
                    print(f"  ✅ Symbol: {data.get('symbol')}")
                    print(f"  ✅ Strategy: {data.get('strategy_type')}")
                    
                    # Check if the data structure matches what the frontend expects
                    if 'results' in data and 'result' in data['results']:
                        result = data['results']['result']
                        print(f"  ✅ Result structure valid")
                        print(f"  ✅ Total return: {result.get('total_return', 'N/A')}")
                        print(f"  ✅ Win rate: {result.get('win_rate', 'N/A')}")
                        print(f"  ✅ Total trades: {result.get('total_trades', 'N/A')}")
                        return True
                    else:
                        print(f"  ❌ Invalid result structure")
                        return False
                else:
                    print(f"  ❌ Individual backtest error: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def run_comprehensive_test(self):
        """Run comprehensive backtest details test."""
        print("🚀 Starting Backtest Details Test...")
        print("=" * 50)
        
        test_results = []
        
        # Test 1: Backtest API Structure
        print("\n1. Testing Backtest API Structure")
        result = await self.test_backtest_api_structure()
        test_results.append(("API Structure", result))
        
        # Test 2: Backtest History API
        print("\n2. Testing Backtest History API")
        result = await self.test_backtest_history_api()
        test_results.append(("History API", result))
        
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
    async with BacktestDetailsTester() as tester:
        success = await tester.run_comprehensive_test()
        
        print(f"\n🎉 Backtest Details Test Complete!")
        print(f"Result: {'PASS' if success else 'FAIL'}")
        
        return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
