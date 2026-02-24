#!/usr/bin/env python3
"""
Test backtesting with multiple product symbols to ensure all are supported.
"""

import asyncio
import aiohttp
import json
import time

class MultiSymbolTester:
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
    
    async def test_symbol_backtest(self, symbol, strategy_type="sma"):
        """Test backtesting with a specific symbol."""
        print(f"Testing {symbol} with {strategy_type} strategy...")
        
        payload = {
            "strategy_type": strategy_type,
            "product_id": symbol,
            "days": 7,
            "granularity": 3600,
            "strategy_params": {
                "short_window": 10,
                "long_window": 20
            }
        }
        
        start_time = time.time()
        
        try:
            async with self.session.post(f"{self.base_url}/api/run-backtest", 
                                       json=payload) as response:
                response_time = time.time() - start_time
                
                if response.status == 200:
                    data = await response.json()
                    result = data.get('result', {})
                    
                    test_result = {
                        'symbol': symbol,
                        'strategy': strategy_type,
                        'status': 'success',
                        'response_time': round(response_time, 2),
                        'total_signals': result.get('total_signals', 0),
                        'total_trades': result.get('total_trades', 0),
                        'data_points': result.get('data_points', 0)
                    }
                    
                    print(f"  ✅ Success: {test_result['total_signals']} signals, {test_result['total_trades']} trades")
                    return test_result
                    
                else:
                    error_text = await response.text()
                    print(f"  ❌ Failed: HTTP {response.status}")
                    return {
                        'symbol': symbol,
                        'strategy': strategy_type,
                        'status': 'error',
                        'response_time': round(response_time, 2),
                        'error': f"HTTP {response.status}"
                    }
                    
        except Exception as e:
            response_time = time.time() - start_time
            print(f"  ❌ Exception: {str(e)[:100]}")
            return {
                'symbol': symbol,
                'strategy': strategy_type,
                'status': 'exception',
                'response_time': round(response_time, 2),
                'error': str(e)
            }
    
    async def get_available_products(self):
        """Get available products from the API."""
        try:
            async with self.session.get(f"{self.base_url}/api/products") as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('categories', {})
                else:
                    print(f"Failed to get products: {response.status}")
                    return {}
        except Exception as e:
            print(f"Error getting products: {e}")
            return {}
    
    async def run_comprehensive_test(self):
        """Run comprehensive test with multiple symbols."""
        print("🚀 Starting Multi-Symbol Backtesting Test...")
        
        # Get available products
        print("📋 Fetching available products...")
        categories = await self.get_available_products()
        
        if not categories:
            print("❌ Failed to get products")
            return
        
        # Test symbols from different categories
        test_symbols = []
        
        # Major pairs (first 5)
        if 'major' in categories:
            test_symbols.extend(categories['major'][:5])
        
        # DEX tokens (first 3)
        if 'dex_tokens' in categories:
            test_symbols.extend(categories['dex_tokens'][:3])
        
        # Meme tokens (first 3)
        if 'meme_tokens' in categories:
            test_symbols.extend(categories['meme_tokens'][:3])
        
        # Stablecoins (all)
        if 'stablecoins' in categories:
            test_symbols.extend(categories['stablecoins'])
        
        print(f"Testing {len(test_symbols)} symbols: {', '.join(test_symbols)}")
        print()
        
        # Test each symbol
        for symbol in test_symbols:
            result = await self.test_symbol_backtest(symbol)
            self.results.append(result)
            await asyncio.sleep(0.5)  # Small delay between tests
        
        return self.results
    
    def analyze_results(self):
        """Analyze test results."""
        print("\n📊 Analysis Results:")
        print("=" * 50)
        
        total_tests = len(self.results)
        successful_tests = len([r for r in self.results if r['status'] == 'success'])
        failed_tests = len([r for r in self.results if r['status'] != 'success'])
        
        print(f"Total Tests: {total_tests}")
        print(f"Successful: {successful_tests} ({successful_tests/total_tests*100:.1f}%)")
        print(f"Failed: {failed_tests} ({failed_tests/total_tests*100:.1f}%)")
        print()
        
        if successful_tests > 0:
            successful_results = [r for r in self.results if r['status'] == 'success']
            
            print("✅ Successful Symbols:")
            for result in successful_results:
                print(f"  {result['symbol']}: {result['total_signals']} signals, {result['total_trades']} trades")
            print()
            
            avg_response_time = sum(r['response_time'] for r in successful_results) / successful_tests
            print(f"Average Response Time: {avg_response_time:.2f}s")
        
        if failed_tests > 0:
            print("❌ Failed Symbols:")
            for result in self.results:
                if result['status'] != 'success':
                    print(f"  {result['symbol']}: {result.get('error', 'Unknown error')}")
            print()
        
        return successful_tests / total_tests if total_tests > 0 else 0

async def main():
    """Main test execution."""
    async with MultiSymbolTester() as tester:
        await tester.run_comprehensive_test()
        success_rate = tester.analyze_results()
        
        print(f"🎉 Multi-Symbol Test Complete!")
        print(f"Success Rate: {success_rate:.1%}")
        
        return success_rate >= 0.8  # Consider 80%+ success rate as passing

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
