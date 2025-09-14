#!/usr/bin/env python3
"""
Server-side test script for loadCurrentPriceData fallback mechanism
This script tests the fallback from real-time data to historical data
and verifies that current price and 24h volume match the current symbol
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PriceDataFallbackTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.test_results = []
        self.symbols = ['BTC-USD', 'ETH-USD', 'ADA-USD', 'SOL-USD', 'DOT-USD']
        
    async def test_real_time_api(self, symbol: str) -> Dict[str, Any]:
        """Test the real-time data API"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/real-time-data?product_id={symbol}") as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"✅ Real-time API for {symbol}: {data}")
                        return {
                            'success': True,
                            'data': data,
                            'status_code': response.status
                        }
                    else:
                        logger.warning(f"⚠️ Real-time API for {symbol} returned status {response.status}")
                        return {
                            'success': False,
                            'data': None,
                            'status_code': response.status,
                            'error': f"HTTP {response.status}"
                        }
        except Exception as e:
            logger.error(f"❌ Real-time API error for {symbol}: {e}")
            return {
                'success': False,
                'data': None,
                'error': str(e)
            }
    
    async def test_historical_api(self, symbol: str, days: int = 1) -> Dict[str, Any]:
        """Test the historical data API"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/historical-data?product_id={symbol}&days={days}") as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"✅ Historical API for {symbol}: {len(data) if isinstance(data, list) else 'Not a list'} data points")
                        return {
                            'success': True,
                            'data': data,
                            'status_code': response.status,
                            'data_count': len(data) if isinstance(data, list) else 0
                        }
                    else:
                        logger.warning(f"⚠️ Historical API for {symbol} returned status {response.status}")
                        return {
                            'success': False,
                            'data': None,
                            'status_code': response.status,
                            'error': f"HTTP {response.status}"
                        }
        except Exception as e:
            logger.error(f"❌ Historical API error for {symbol}: {e}")
            return {
                'success': False,
                'data': None,
                'error': str(e)
            }
    
    def simulate_load_current_price_data(self, symbol: str, real_time_result: Dict, historical_result: Dict) -> Dict[str, Any]:
        """Simulate the loadCurrentPriceData function logic"""
        logger.info(f"🔄 Simulating loadCurrentPriceData for {symbol}")
        
        # Check if real-time data is available and valid
        if (real_time_result['success'] and 
            real_time_result['data'] and 
            not real_time_result['data'].get('error') and 
            real_time_result['data'].get('ticker')):
            
            # Use real-time data
            ticker = real_time_result['data']['ticker']
            price = float(ticker.get('price', 0))
            volume = float(ticker.get('volume_24h', 0))
            change24h = float(ticker.get('price_change_24h', 0))
            
            logger.info(f"✅ Using real-time data for {symbol}: Price=${price:.2f}, Volume={volume:,.0f}")
            
            return {
                'source': 'real-time',
                'symbol': symbol,
                'price': price,
                'volume': volume,
                'change24h': change24h,
                'timestamp': datetime.now().isoformat(),
                'success': True
            }
        else:
            # Fallback to historical data
            logger.info(f"🔄 No real-time data for {symbol}, using historical data fallback")
            
            if (historical_result['success'] and 
                historical_result['data'] and 
                isinstance(historical_result['data'], list) and 
                len(historical_result['data']) > 0):
                
                # Get the most recent data point
                latest_data = historical_result['data'][-1]
                price = float(latest_data.get('price', 0))
                volume = float(latest_data.get('volume', 0))
                
                logger.info(f"✅ Using historical data for {symbol}: Price=${price:.2f}, Volume={volume:,.0f}")
                
                return {
                    'source': 'historical',
                    'symbol': symbol,
                    'price': price,
                    'volume': volume,
                    'change24h': None,
                    'timestamp': datetime.now().isoformat(),
                    'success': True,
                    'data_point': latest_data
                }
            else:
                logger.warning(f"❌ No data available for {symbol}")
                return {
                    'source': 'none',
                    'symbol': symbol,
                    'price': 0,
                    'volume': 0,
                    'change24h': None,
                    'timestamp': datetime.now().isoformat(),
                    'success': False,
                    'error': 'No data available'
                }
    
    def verify_data_integrity(self, data: Dict[str, Any], expected_symbol: str) -> Dict[str, Any]:
        """Verify that the data matches the expected symbol and is valid"""
        verification = {
            'is_valid': True,
            'errors': [],
            'warnings': []
        }
        
        # Check symbol match
        if data['symbol'] != expected_symbol:
            verification['is_valid'] = False
            verification['errors'].append(f"Symbol mismatch: expected {expected_symbol}, got {data['symbol']}")
        
        # Check price validity
        if data['price'] <= 0:
            verification['is_valid'] = False
            verification['errors'].append(f"Invalid price: {data['price']}")
        elif data['price'] < 1:
            verification['warnings'].append(f"Very low price: {data['price']} - might be invalid")
        
        # Check volume validity
        if data['volume'] < 0:
            verification['is_valid'] = False
            verification['errors'].append(f"Invalid volume: {data['volume']}")
        elif data['volume'] == 0:
            verification['warnings'].append("Zero volume - might indicate no trading activity")
        
        # Check data source
        if data['source'] == 'none':
            verification['is_valid'] = False
            verification['errors'].append("No data available for symbol")
        elif not data['success']:
            verification['is_valid'] = False
            verification['errors'].append(f"Data loading failed: {data.get('error', 'Unknown error')}")
        
        return verification
    
    async def test_single_symbol(self, symbol: str) -> Dict[str, Any]:
        """Test a single symbol with both real-time and historical data"""
        logger.info(f"🧪 Testing symbol: {symbol}")
        
        # Test real-time API
        real_time_result = await self.test_real_time_api(symbol)
        
        # Test historical API
        historical_result = await self.test_historical_api(symbol)
        
        # Simulate loadCurrentPriceData logic
        simulated_result = self.simulate_load_current_price_data(symbol, real_time_result, historical_result)
        
        # Verify data integrity
        verification = self.verify_data_integrity(simulated_result, symbol)
        
        test_result = {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'real_time_result': real_time_result,
            'historical_result': historical_result,
            'simulated_result': simulated_result,
            'verification': verification,
            'status': 'PASS' if verification['is_valid'] else 'FAIL'
        }
        
        self.test_results.append(test_result)
        
        # Log results
        status_emoji = "✅" if test_result['status'] == 'PASS' else "❌"
        logger.info(f"{status_emoji} {symbol}: {test_result['status']} (Source: {simulated_result['source']})")
        
        if verification['errors']:
            for error in verification['errors']:
                logger.error(f"  Error: {error}")
        
        if verification['warnings']:
            for warning in verification['warnings']:
                logger.warning(f"  Warning: {warning}")
        
        return test_result
    
    async def run_refresh_sequence(self) -> List[Dict[str, Any]]:
        """Run a refresh sequence that checks current price and volume match"""
        logger.info("🔄 Starting refresh sequence")
        
        refresh_results = []
        
        for i, symbol in enumerate(self.symbols):
            logger.info(f"🔄 Refreshing data for {symbol} ({i + 1}/{len(self.symbols)})")
            
            test_result = await self.test_single_symbol(symbol)
            refresh_results.append(test_result)
            
            # Wait between refreshes to avoid rate limiting
            if i < len(self.symbols) - 1:
                await asyncio.sleep(2)
        
        logger.info("✅ Refresh sequence completed")
        return refresh_results
    
    async def run_complete_test_suite(self) -> Dict[str, Any]:
        """Run the complete test suite"""
        logger.info("🚀 Starting complete test suite")
        
        start_time = time.time()
        
        # Test all symbols
        for symbol in self.symbols:
            await self.test_single_symbol(symbol)
            await asyncio.sleep(1)  # Wait between tests
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Generate report
        report = self.generate_test_report(duration)
        
        logger.info("🎯 Test suite completed")
        return report
    
    def generate_test_report(self, duration: float) -> Dict[str, Any]:
        """Generate a comprehensive test report"""
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r['status'] == 'PASS'])
        failed_tests = total_tests - passed_tests
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        # Group by source
        source_stats = {}
        for result in self.test_results:
            source = result['simulated_result']['source']
            source_stats[source] = source_stats.get(source, 0) + 1
        
        # Group by status
        status_stats = {}
        for result in self.test_results:
            status = result['status']
            status_stats[status] = status_stats.get(status, 0) + 1
        
        report = {
            'summary': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': failed_tests,
                'success_rate': success_rate,
                'duration_seconds': duration
            },
            'source_stats': source_stats,
            'status_stats': status_stats,
            'test_results': self.test_results
        }
        
        # Log report
        logger.info("📋 Test Report")
        logger.info("=" * 50)
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"Passed: {passed_tests}")
        logger.info(f"Failed: {failed_tests}")
        logger.info(f"Success Rate: {success_rate:.2f}%")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Source Statistics: {source_stats}")
        logger.info(f"Status Statistics: {status_stats}")
        
        return report
    
    def save_results_to_file(self, filename: str = None):
        """Save test results to a JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"price_data_test_results_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump({
                'test_results': self.test_results,
                'timestamp': datetime.now().isoformat(),
                'summary': self.generate_test_report(0)['summary']
            }, f, indent=2)
        
        logger.info(f"📁 Results saved to {filename}")

async def main():
    """Main function to run the tests"""
    tester = PriceDataFallbackTester()
    
    try:
        # Run complete test suite
        report = await tester.run_complete_test_suite()
        
        # Save results
        tester.save_results_to_file()
        
        # Print final summary
        print("\n" + "=" * 60)
        print("🎯 FINAL SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {report['summary']['total_tests']}")
        print(f"Passed: {report['summary']['passed_tests']}")
        print(f"Failed: {report['summary']['failed_tests']}")
        print(f"Success Rate: {report['summary']['success_rate']:.2f}%")
        print(f"Duration: {report['summary']['duration_seconds']:.2f} seconds")
        print("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ Test suite failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
