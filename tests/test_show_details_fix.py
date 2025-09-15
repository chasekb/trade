#!/usr/bin/env python3
"""
Test the show details fix for backtest history.
"""

import asyncio
import aiohttp
import json

class ShowDetailsFixTester:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_dashboard_loading(self):
        """Test that dashboard loads with show details functionality."""
        print("Testing dashboard loading...")
        
        try:
            async with self.session.get(f"{self.base_url}/") as response:
                if response.status == 200:
                    content = await response.text()
                    
                    # Check for required elements
                    required_elements = [
                        'backtest-results',
                        'history-table-body',
                        'viewBacktest',
                        'displayBacktestResults'
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
    
    async def test_backtest_details_api(self):
        """Test that backtest details API works correctly."""
        print("Testing backtest details API...")
        
        try:
            # First get a backtest ID from history
            async with self.session.get(f"{self.base_url}/api/backtest-history") as response:
                if response.status == 200:
                    history_data = await response.json()
                    backtests = history_data.get('backtests', [])
                    
                    if len(backtests) > 0:
                        backtest_id = backtests[0]['id']
                        print(f"  ✅ Found backtest ID: {backtest_id}")
                        
                        # Now test getting details for this backtest
                        async with self.session.get(f"{self.base_url}/api/backtest/{backtest_id}") as details_response:
                            if details_response.status == 200:
                                details_data = await details_response.json()
                                
                                # Check if the data structure is correct
                                if ('results' in details_data and 
                                    'result' in details_data['results'] and
                                    'trades' in details_data['results'] and
                                    'equity_curve' in details_data['results']):
                                    
                                    result = details_data['results']['result']
                                    required_fields = ['total_return', 'win_rate', 'total_trades', 'net_profit', 'final_balance']
                                    missing_fields = [field for field in required_fields if field not in result]
                                    
                                    if missing_fields:
                                        print(f"  ❌ Missing fields in result: {missing_fields}")
                                        return False
                                    
                                    print(f"  ✅ Backtest details API working correctly")
                                    print(f"  ✅ Total return: {result.get('total_return', 'N/A')}")
                                    print(f"  ✅ Win rate: {result.get('win_rate', 'N/A')}")
                                    print(f"  ✅ Total trades: {result.get('total_trades', 'N/A')}")
                                    return True
                                else:
                                    print(f"  ❌ Invalid data structure in details response")
                                    return False
                            else:
                                print(f"  ❌ Details API error: {details_response.status}")
                                return False
                    else:
                        print(f"  ⚠️  No backtests found in history")
                        return True
                else:
                    print(f"  ❌ History API error: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return False
    
    async def run_comprehensive_test(self):
        """Run comprehensive show details fix test."""
        print("🚀 Starting Show Details Fix Test...")
        print("=" * 50)
        
        test_results = []
        
        # Test 1: Dashboard Loading
        print("\n1. Testing Dashboard Loading")
        result = await self.test_dashboard_loading()
        test_results.append(("Dashboard Loading", result))
        
        # Test 2: Backtest Details API
        print("\n2. Testing Backtest Details API")
        result = await self.test_backtest_details_api()
        test_results.append(("Details API", result))
        
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
    async with ShowDetailsFixTester() as tester:
        success = await tester.run_comprehensive_test()
        
        print(f"\n🎉 Show Details Fix Test Complete!")
        print(f"Result: {'PASS' if success else 'FAIL'}")
        
        return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
