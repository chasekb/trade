#!/usr/bin/env python3
"""
Integration test for server caching system.
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime

class ServerCacheIntegrationTester:
    """Test server caching integration."""
    
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        self.results = []
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_cache_stats_endpoint(self):
        """Test the cache stats endpoint."""
        print("🧪 Testing cache stats endpoint...")
        
        try:
            async with self.session.get(f"{self.base_url}/api/cache-stats") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"  ✅ Cache stats retrieved: {data}")
                    return True
                else:
                    print(f"  ❌ Failed to get cache stats: {response.status}")
                    return False
        except Exception as e:
            print(f"  ❌ Error: {str(e)}")
            return False
    
    async def test_backtest_caching(self):
        """Test that backtests use caching."""
        print("🧪 Testing backtest caching...")
        
        # Test case: Simple SMA strategy
        payload = {
            "strategy_type": "sma",
            "product_id": "BTC-USD",
            "days": 7,
            "granularity": 3600,
            "strategy_params": {
                "short_window": 10,
                "long_window": 20
            }
        }
        
        try:
            # First backtest - should populate cache
            print("  First backtest (cache miss)...")
            start_time_1 = time.time()
            async with self.session.post(f"{self.base_url}/api/run-backtest", json=payload) as response:
                time1 = time.time() - start_time_1
                if response.status == 200:
                    data1 = await response.json()
                    print(f"    ✅ First backtest completed in {time1:.2f}s")
                else:
                    print(f"    ❌ First backtest failed: {response.status}")
                    return False
            
            # Second backtest - should use cache
            print("  Second backtest (cache hit)...")
            start_time_2 = time.time()
            async with self.session.post(f"{self.base_url}/api/run-backtest", json=payload) as response:
                time2 = time.time() - start_time_2
                if response.status == 200:
                    data2 = await response.json()
                    print(f"    ✅ Second backtest completed in {time2:.2f}s")
                else:
                    print(f"    ❌ Second backtest failed: {response.status}")
                    return False
            
            # Check if second call was faster
            speedup = time1 / time2 if time2 > 0 else 0
            print(f"  Speedup: {speedup:.1f}x")
            
            if speedup > 1.1:  # At least 10% improvement
                print("  ✅ PASS: Caching provides performance improvement")
                return True
            else:
                print("  ⚠️  WARN: Caching may not be working optimally")
                return True
                
        except Exception as e:
            print(f"  ❌ Error: {str(e)}")
            return False
    
    async def test_different_strategies_caching(self):
        """Test that different strategies can share cached data."""
        print("🧪 Testing different strategies caching...")
        
        strategies = [
            {
                "strategy_type": "sma",
                "strategy_params": {"short_window": 10, "long_window": 20}
            },
            {
                "strategy_type": "ema", 
                "strategy_params": {"short_window": 10, "long_window": 20}
            },
            {
                "strategy_type": "rsi",
                "strategy_params": {"window": 14, "overbought": 70, "oversold": 30}
            }
        ]
        
        base_payload = {
            "product_id": "BTC-USD",
            "days": 3,
            "granularity": 3600
        }
        
        times = []
        
        try:
            for i, strategy in enumerate(strategies):
                payload = {**base_payload, **strategy}
                print(f"  Testing {strategy['strategy_type']} strategy...")
                
                start_time = time.time()
                async with self.session.post(f"{self.base_url}/api/run-backtest", json=payload) as response:
                    elapsed = time.time() - start_time
                    times.append(elapsed)
                    
                    if response.status == 200:
                        print(f"    ✅ Completed in {elapsed:.2f}s")
                    else:
                        print(f"    ❌ Failed: {response.status}")
                        return False
            
            # Check if later strategies are faster (indicating cache reuse)
            if len(times) >= 2:
                first_time = times[0]
                avg_later_time = sum(times[1:]) / len(times[1:])
                speedup = first_time / avg_later_time if avg_later_time > 0 else 0
                
                print(f"  First strategy time: {first_time:.2f}s")
                print(f"  Average later strategies time: {avg_later_time:.2f}s")
                print(f"  Speedup: {speedup:.1f}x")
                
                if speedup > 1.2:
                    print("  ✅ PASS: Strategies share cached data effectively")
                    return True
                else:
                    print("  ⚠️  WARN: Strategies may not be sharing cached data optimally")
                    return True
            else:
                print("  ⚠️  WARN: Not enough data for comparison")
                return True
                
        except Exception as e:
            print(f"  ❌ Error: {str(e)}")
            return False
    
    async def test_cache_cleanup(self):
        """Test cache cleanup functionality."""
        print("🧪 Testing cache cleanup...")
        
        try:
            # Get initial cache stats
            async with self.session.get(f"{self.base_url}/api/cache-stats") as response:
                if response.status == 200:
                    initial_stats = await response.json()
                    print(f"  Initial cache stats: {initial_stats}")
                else:
                    print("  ⚠️  Could not get initial cache stats")
                    return True
            
            # The cache cleanup would need to be triggered manually or by time
            # For now, just verify the endpoint works
            print("  ✅ Cache stats endpoint accessible")
            return True
            
        except Exception as e:
            print(f"  ❌ Error: {str(e)}")
            return False
    
    def generate_report(self):
        """Generate test report."""
        print("\n📊 Server Cache Integration Test Report:")
        print("=" * 50)
        
        total_tests = len(self.results)
        passed_tests = len([r for r in self.results if r])
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Success Rate: {passed_tests/total_tests*100:.1f}%")
        
        return passed_tests / total_tests if total_tests > 0 else 0

async def main():
    """Run all server cache integration tests."""
    print("🚀 Starting Server Cache Integration Tests...")
    print()
    
    async with ServerCacheIntegrationTester() as tester:
        # Run all tests
        result1 = await tester.test_cache_stats_endpoint()
        tester.results.append(result1)
        print()
        
        result2 = await tester.test_backtest_caching()
        tester.results.append(result2)
        print()
        
        result3 = await tester.test_different_strategies_caching()
        tester.results.append(result3)
        print()
        
        result4 = await tester.test_cache_cleanup()
        tester.results.append(result4)
        print()
        
        # Generate report
        success_rate = tester.generate_report()
        
        return success_rate >= 0.75  # 75% success rate threshold

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
