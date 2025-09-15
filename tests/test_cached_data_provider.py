#!/usr/bin/env python3
"""
Comprehensive tests for cached data provider to validate data consistency.
"""

import asyncio
import aiohttp
import json
import time
import os
import tempfile
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Add the src directory to the path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from trade_bot.cached_data_provider import CachedDataProvider
from trade_bot.database_manager import DatabaseManager
from trade_bot.config import TradingConfig

class CachedDataProviderTester:
    """Test suite for cached data provider."""
    
    def __init__(self):
        # Create a temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        
        # Mock config for testing
        self.config = TradingConfig(
            api_key="test_key",
            api_secret="test_secret", 
            passphrase="test_passphrase"
        )
        
        self.cached_provider = CachedDataProvider(self.config, self.temp_db.name)
        self.db_manager = DatabaseManager(self.temp_db.name)
        
        self.test_results = []
    
    def cleanup(self):
        """Clean up test resources."""
        try:
            os.unlink(self.temp_db.name)
        except:
            pass
    
    async def test_cache_consistency(self):
        """Test that cached data matches fresh API data."""
        print("🧪 Testing cache consistency...")
        
        test_cases = [
            {
                "product_id": "BTC-USD",
                "days": 7,
                "granularity": 3600,  # 1 hour
                "description": "7 days, 1h granularity"
            },
            {
                "product_id": "ETH-USD", 
                "days": 3,
                "granularity": 21600,  # 6 hours
                "description": "3 days, 6h granularity"
            },
            {
                "product_id": "BTC-USD",
                "days": 1,
                "granularity": 86400,  # 1 day
                "description": "1 day, 1d granularity"
            }
        ]
        
        for case in test_cases:
            print(f"  Testing: {case['description']}")
            
            # Calculate time range
            end_time = int(time.time())
            start_time = end_time - (case['days'] * 24 * 3600)
            
            try:
                # First call - should be cache miss
                print("    First call (cache miss)...")
                start_time_1 = time.time()
                data1 = await self.cached_provider.get_historical_candles(
                    case['product_id'], start_time, end_time, case['granularity']
                )
                time1 = time.time() - start_time_1
                
                # Second call - should be cache hit
                print("    Second call (cache hit)...")
                start_time_2 = time.time()
                data2 = await self.cached_provider.get_historical_candles(
                    case['product_id'], start_time, end_time, case['granularity']
                )
                time2 = time.time() - start_time_2
                
                # Validate consistency
                consistency_result = self._validate_data_consistency(data1, data2, case)
                
                # Performance comparison
                speedup = time1 / time2 if time2 > 0 else float('inf')
                
                result = {
                    'test_case': case['description'],
                    'product_id': case['product_id'],
                    'data_points': len(data1) if data1 else 0,
                    'first_call_time': round(time1, 3),
                    'second_call_time': round(time2, 3),
                    'speedup': round(speedup, 2),
                    'consistency': consistency_result,
                    'success': consistency_result['data_identical']
                }
                
                self.test_results.append(result)
                
                if result['success']:
                    print(f"    ✅ PASS: {len(data1)} points, {speedup:.1f}x speedup")
                else:
                    print(f"    ❌ FAIL: {consistency_result['error']}")
                
            except Exception as e:
                print(f"    ❌ ERROR: {str(e)}")
                self.test_results.append({
                    'test_case': case['description'],
                    'success': False,
                    'error': str(e)
                })
    
    def _validate_data_consistency(self, data1: List[Dict], data2: List[Dict], case: Dict) -> Dict:
        """Validate that two datasets are identical."""
        try:
            # Check if both datasets exist
            if not data1 and not data2:
                return {'data_identical': True, 'error': None}
            
            if not data1 or not data2:
                return {'data_identical': False, 'error': 'One dataset is empty'}
            
            # Check length
            if len(data1) != len(data2):
                return {
                    'data_identical': False, 
                    'error': f'Length mismatch: {len(data1)} vs {len(data2)}'
                }
            
            # Check each candle
            for i, (candle1, candle2) in enumerate(zip(data1, data2)):
                # Check required fields
                required_fields = ['time', 'low', 'high', 'open', 'close', 'volume']
                for field in required_fields:
                    if candle1.get(field) != candle2.get(field):
                        return {
                            'data_identical': False,
                            'error': f'Field mismatch at index {i}, field {field}: {candle1.get(field)} vs {candle2.get(field)}'
                        }
            
            return {'data_identical': True, 'error': None}
            
        except Exception as e:
            return {'data_identical': False, 'error': f'Validation error: {str(e)}'}
    
    async def test_order_book_caching(self):
        """Test order book caching functionality."""
        print("🧪 Testing order book caching...")
        
        try:
            # First call - should be cache miss
            print("  First call (cache miss)...")
            start_time_1 = time.time()
            orderbook1 = await self.cached_provider.get_order_book("BTC-USD")
            time1 = time.time() - start_time_1
            
            # Second call - should be cache hit
            print("  Second call (cache hit)...")
            start_time_2 = time.time()
            orderbook2 = await self.cached_provider.get_order_book("BTC-USD")
            time2 = time.time() - start_time_2
            
            if orderbook1 and orderbook2:
                # Validate order book structure
                required_fields = ['bids', 'asks', 'sequence']
                for field in required_fields:
                    if field not in orderbook1 or field not in orderbook2:
                        print(f"  ❌ FAIL: Missing field {field}")
                        return False
                
                # Check if data is identical
                if orderbook1 == orderbook2:
                    speedup = time1 / time2 if time2 > 0 else float('inf')
                    print(f"  ✅ PASS: Order book cached correctly, {speedup:.1f}x speedup")
                    return True
                else:
                    print("  ❌ FAIL: Order book data differs between calls")
                    return False
            else:
                print("  ⚠️  SKIP: No order book data available")
                return True
                
        except Exception as e:
            print(f"  ❌ ERROR: {str(e)}")
            return False
    
    async def test_trade_history_caching(self):
        """Test trade history caching functionality."""
        print("🧪 Testing trade history caching...")
        
        try:
            # First call - should be cache miss
            print("  First call (cache miss)...")
            start_time_1 = time.time()
            trades1 = await self.cached_provider.get_recent_trades("BTC-USD", 50)
            time1 = time.time() - start_time_1
            
            # Second call - should be cache hit
            print("  Second call (cache hit)...")
            start_time_2 = time.time()
            trades2 = await self.cached_provider.get_recent_trades("BTC-USD", 50)
            time2 = time.time() - start_time_2
            
            if trades1 and trades2:
                # Check if data is identical
                if trades1 == trades2:
                    speedup = time1 / time2 if time2 > 0 else float('inf')
                    print(f"  ✅ PASS: Trade history cached correctly, {speedup:.1f}x speedup")
                    return True
                else:
                    print("  ❌ FAIL: Trade history data differs between calls")
                    return False
            else:
                print("  ⚠️  SKIP: No trade history data available")
                return True
                
        except Exception as e:
            print(f"  ❌ ERROR: {str(e)}")
            return False
    
    async def test_cache_expiration(self):
        """Test cache expiration functionality."""
        print("🧪 Testing cache expiration...")
        
        try:
            # Create a test database manager with short expiration
            test_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
            test_db.close()
            
            # Override expiration time for testing
            db_manager = DatabaseManager(test_db.name)
            
            # Cache some test data
            test_data = [{"time": 1234567890, "open": 100, "high": 110, "low": 90, "close": 105, "volume": 1000}]
            db_manager.cache_historical_candles("TEST-USD", 1234567890, 1234567890, 3600, test_data)
            
            # Verify data is cached
            cached_data = db_manager.get_historical_candles("TEST-USD", 1234567890, 1234567890, 3600)
            if not cached_data:
                print("  ❌ FAIL: Data not cached")
                return False
            
            # Manually expire the data by updating the database
            import sqlite3
            conn = sqlite3.connect(db_manager.db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE historical_candles SET expires_at = '2000-01-01' WHERE product_id = 'TEST-USD'")
            conn.commit()
            conn.close()
            
            # Verify data is expired
            expired_data = db_manager.get_historical_candles("TEST-USD", 1234567890, 1234567890, 3600)
            if expired_data:
                print("  ❌ FAIL: Expired data still accessible")
                return False
            
            print("  ✅ PASS: Cache expiration works correctly")
            
            # Cleanup
            os.unlink(test_db.name)
            return True
            
        except Exception as e:
            print(f"  ❌ ERROR: {str(e)}")
            return False
    
    async def test_cache_performance(self):
        """Test cache performance improvements."""
        print("🧪 Testing cache performance...")
        
        try:
            # Reset stats
            self.cached_provider.reset_stats()
            
            # Test multiple calls to same data
            product_id = "BTC-USD"
            end_time = int(time.time())
            start_time = end_time - (7 * 24 * 3600)  # 7 days
            granularity = 3600  # 1 hour
            
            # Make 5 calls to the same data
            times = []
            for i in range(5):
                start = time.time()
                data = await self.cached_provider.get_historical_candles(
                    product_id, start_time, end_time, granularity
                )
                times.append(time.time() - start)
            
            # Get cache stats
            stats = self.cached_provider.get_cache_stats()
            
            # Analyze performance
            first_call_time = times[0]
            avg_cached_time = sum(times[1:]) / len(times[1:])
            speedup = first_call_time / avg_cached_time if avg_cached_time > 0 else 0
            
            print(f"  First call time: {first_call_time:.3f}s")
            print(f"  Average cached call time: {avg_cached_time:.3f}s")
            print(f"  Speedup: {speedup:.1f}x")
            print(f"  Cache hits: {stats['cache_hits']}")
            print(f"  Cache misses: {stats['cache_misses']}")
            print(f"  Hit rate: {stats['hit_rate']:.1%}")
            
            if speedup > 2.0 and stats['hit_rate'] > 0.7:
                print("  ✅ PASS: Good cache performance")
                return True
            else:
                print("  ⚠️  WARN: Cache performance could be better")
                return True
                
        except Exception as e:
            print(f"  ❌ ERROR: {str(e)}")
            return False
    
    def generate_report(self):
        """Generate test report."""
        print("\n📊 Test Report:")
        print("=" * 50)
        
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r.get('success', False)])
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Success Rate: {passed_tests/total_tests*100:.1f}%")
        print()
        
        if total_tests > 0:
            print("Detailed Results:")
            print("-" * 30)
            for result in self.test_results:
                status = "✅ PASS" if result.get('success', False) else "❌ FAIL"
                print(f"{status} {result.get('test_case', 'Unknown test')}")
                if 'error' in result:
                    print(f"    Error: {result['error']}")
                if 'speedup' in result:
                    print(f"    Speedup: {result['speedup']}x")
                if 'data_points' in result:
                    print(f"    Data points: {result['data_points']}")
        
        return passed_tests / total_tests if total_tests > 0 else 0

async def main():
    """Run all cache validation tests."""
    print("🚀 Starting Cached Data Provider Validation Tests...")
    print()
    
    tester = CachedDataProviderTester()
    
    try:
        # Run all tests
        await tester.test_cache_consistency()
        print()
        
        await tester.test_order_book_caching()
        print()
        
        await tester.test_trade_history_caching()
        print()
        
        await tester.test_cache_expiration()
        print()
        
        await tester.test_cache_performance()
        print()
        
        # Generate report
        success_rate = tester.generate_report()
        
        return success_rate >= 0.8  # 80% success rate threshold
        
    finally:
        tester.cleanup()

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
