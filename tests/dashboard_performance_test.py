#!/usr/bin/env python3
"""
Performance test suite for dashboard functionality.

This test suite measures response times and performance metrics for:
- API endpoint response times
- WebSocket message latency
- Backtest execution performance
- Data processing efficiency
"""

import asyncio
import aiohttp
import time
import statistics
import json
import logging
from datetime import datetime
from typing import Dict, List, Any

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DashboardPerformanceTest:
    """Performance test suite for dashboard functionality."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        self.performance_results = {}
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def measure_response_time(self, url: str, method: str = 'GET', data: Dict = None) -> Dict[str, Any]:
        """Measure response time for a single request."""
        start_time = time.time()
        
        try:
            if method.upper() == 'GET':
                async with self.session.get(url) as response:
                    response_data = await response.text()
                    status_code = response.status
            elif method.upper() == 'POST':
                async with self.session.post(url, json=data) as response:
                    response_data = await response.text()
                    status_code = response.status
            else:
                raise ValueError(f"Unsupported method: {method}")
                
            end_time = time.time()
            response_time = (end_time - start_time) * 1000  # Convert to milliseconds
            
            return {
                'success': True,
                'response_time_ms': response_time,
                'status_code': status_code,
                'response_size_bytes': len(response_data),
                'error': None
            }
            
        except Exception as e:
            end_time = time.time()
            response_time = (end_time - start_time) * 1000
            
            return {
                'success': False,
                'response_time_ms': response_time,
                'status_code': None,
                'response_size_bytes': 0,
                'error': str(e)
            }
    
    async def test_api_endpoint_performance(self) -> Dict[str, Any]:
        """Test performance of various API endpoints."""
        logger.info("Testing API endpoint performance...")
        
        endpoints = [
            {'name': 'Data Summary', 'url': f"{self.base_url}/api/data-summary", 'method': 'GET'},
            {'name': 'Backtest Filters', 'url': f"{self.base_url}/api/backtest-filters", 'method': 'GET'},
            {'name': 'Backtest History', 'url': f"{self.base_url}/api/backtest-history", 'method': 'GET'},
            {'name': 'SMA Backtest', 'url': f"{self.base_url}/api/run-backtest", 'method': 'POST', 
             'data': {
                 'strategy_type': 'sma',
                 'product_id': 'BTC-USD',
                 'days': 1,
                 'granularity': 3600,
                 'strategy_params': {'short_window': 5, 'long_window': 20}
             }},
            {'name': 'RSI Backtest', 'url': f"{self.base_url}/api/run-backtest", 'method': 'POST',
             'data': {
                 'strategy_type': 'rsi',
                 'product_id': 'BTC-USD',
                 'days': 1,
                 'granularity': 3600,
                 'strategy_params': {'period': 14, 'overbought': 70, 'oversold': 30}
             }}
        ]
        
        results = {}
        
        for endpoint in endpoints:
            logger.info(f"Testing {endpoint['name']}...")
            
            # Run multiple requests to get average performance
            response_times = []
            success_count = 0
            total_requests = 5
            
            for i in range(total_requests):
                result = await self.measure_response_time(
                    endpoint['url'], 
                    endpoint['method'], 
                    endpoint.get('data')
                )
                
                if result['success']:
                    response_times.append(result['response_time_ms'])
                    success_count += 1
                
                # Small delay between requests
                await asyncio.sleep(0.1)
            
            if response_times:
                results[endpoint['name']] = {
                    'avg_response_time_ms': statistics.mean(response_times),
                    'min_response_time_ms': min(response_times),
                    'max_response_time_ms': max(response_times),
                    'median_response_time_ms': statistics.median(response_times),
                    'success_rate': (success_count / total_requests) * 100,
                    'total_requests': total_requests,
                    'successful_requests': success_count
                }
            else:
                results[endpoint['name']] = {
                    'avg_response_time_ms': None,
                    'min_response_time_ms': None,
                    'max_response_time_ms': None,
                    'median_response_time_ms': None,
                    'success_rate': 0,
                    'total_requests': total_requests,
                    'successful_requests': 0
                }
        
        return results
    
    async def test_concurrent_requests(self) -> Dict[str, Any]:
        """Test performance under concurrent load."""
        logger.info("Testing concurrent request performance...")
        
        # Test concurrent data summary requests
        concurrent_requests = 10
        start_time = time.time()
        
        tasks = []
        for i in range(concurrent_requests):
            task = self.measure_response_time(f"{self.base_url}/api/data-summary")
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        total_time = (end_time - start_time) * 1000
        successful_results = [r for r in results if isinstance(r, dict) and r['success']]
        failed_results = [r for r in results if not (isinstance(r, dict) and r['success'])]
        
        if successful_results:
            response_times = [r['response_time_ms'] for r in successful_results]
            
            return {
                'concurrent_requests': concurrent_requests,
                'total_time_ms': total_time,
                'successful_requests': len(successful_results),
                'failed_requests': len(failed_results),
                'success_rate': (len(successful_results) / concurrent_requests) * 100,
                'avg_response_time_ms': statistics.mean(response_times),
                'min_response_time_ms': min(response_times),
                'max_response_time_ms': max(response_times),
                'requests_per_second': (concurrent_requests / total_time) * 1000
            }
        else:
            return {
                'concurrent_requests': concurrent_requests,
                'total_time_ms': total_time,
                'successful_requests': 0,
                'failed_requests': len(failed_results),
                'success_rate': 0,
                'avg_response_time_ms': None,
                'min_response_time_ms': None,
                'max_response_time_ms': None,
                'requests_per_second': 0
            }
    
    async def test_websocket_performance(self) -> Dict[str, Any]:
        """Test WebSocket message latency and throughput."""
        logger.info("Testing WebSocket performance...")
        
        try:
            import websockets
            
            ws_url = "ws://localhost:8000/ws"
            message_times = []
            messages_received = 0
            start_time = time.time()
            
            async with websockets.connect(ws_url) as websocket:
                # Wait for messages and measure latency
                timeout = 10  # seconds
                end_time = start_time + timeout
                
                while time.time() < end_time and messages_received < 20:
                    try:
                        message_start = time.time()
                        message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        message_end = time.time()
                        
                        message_times.append((message_end - message_start) * 1000)
                        messages_received += 1
                        
                    except asyncio.TimeoutError:
                        break
                
                total_time = (time.time() - start_time) * 1000
                
                if message_times:
                    return {
                        'messages_received': messages_received,
                        'total_time_ms': total_time,
                        'avg_message_latency_ms': statistics.mean(message_times),
                        'min_message_latency_ms': min(message_times),
                        'max_message_latency_ms': max(message_times),
                        'messages_per_second': (messages_received / total_time) * 1000
                    }
                else:
                    return {
                        'messages_received': 0,
                        'total_time_ms': total_time,
                        'avg_message_latency_ms': None,
                        'min_message_latency_ms': None,
                        'max_message_latency_ms': None,
                        'messages_per_second': 0
                    }
                    
        except ImportError:
            logger.warning("websockets library not available, skipping WebSocket performance test")
            return {'error': 'websockets library not available'}
        except Exception as e:
            logger.error(f"WebSocket performance test failed: {e}")
            return {'error': str(e)}
    
    async def test_backtest_performance_scaling(self) -> Dict[str, Any]:
        """Test backtest performance with different time periods."""
        logger.info("Testing backtest performance scaling...")
        
        test_cases = [
            {'name': '1 Day', 'days': 1, 'granularity': 3600},
            {'name': '3 Days', 'days': 3, 'granularity': 3600},
            {'name': '7 Days', 'days': 7, 'granularity': 3600},
            {'name': '30 Days', 'days': 30, 'granularity': 3600}
        ]
        
        results = {}
        
        for test_case in test_cases:
            logger.info(f"Testing {test_case['name']} backtest...")
            
            data = {
                'strategy_type': 'sma',
                'product_id': 'BTC-USD',
                'days': test_case['days'],
                'granularity': test_case['granularity'],
                'strategy_params': {'short_window': 5, 'long_window': 20}
            }
            
            result = await self.measure_response_time(
                f"{self.base_url}/api/run-backtest",
                'POST',
                data
            )
            
            if result['success']:
                results[test_case['name']] = {
                    'response_time_ms': result['response_time_ms'],
                    'response_size_bytes': result['response_size_bytes'],
                    'status_code': result['status_code']
                }
            else:
                results[test_case['name']] = {
                    'response_time_ms': None,
                    'response_size_bytes': 0,
                    'status_code': None,
                    'error': result['error']
                }
        
        return results
    
    async def run_performance_tests(self) -> Dict[str, Any]:
        """Run all performance tests and return comprehensive results."""
        logger.info("Starting dashboard performance test suite")
        logger.info("=" * 60)
        
        start_time = time.time()
        
        # Run all performance tests
        api_results = await self.test_api_endpoint_performance()
        concurrent_results = await self.test_concurrent_requests()
        websocket_results = await self.test_websocket_performance()
        scaling_results = await self.test_backtest_performance_scaling()
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        # Compile results
        results = {
            'test_timestamp': datetime.now().isoformat(),
            'total_duration_seconds': total_duration,
            'api_endpoint_performance': api_results,
            'concurrent_request_performance': concurrent_results,
            'websocket_performance': websocket_results,
            'backtest_scaling_performance': scaling_results
        }
        
        # Log summary
        logger.info("=" * 60)
        logger.info("PERFORMANCE TEST SUMMARY")
        logger.info("=" * 60)
        
        # API Performance Summary
        logger.info("API Endpoint Performance:")
        for endpoint, metrics in api_results.items():
            if metrics['avg_response_time_ms'] is not None:
                logger.info(f"  {endpoint}: {metrics['avg_response_time_ms']:.2f}ms avg "
                          f"({metrics['success_rate']:.1f}% success rate)")
            else:
                logger.info(f"  {endpoint}: FAILED")
        
        # Concurrent Performance Summary
        if 'success_rate' in concurrent_results:
            logger.info(f"Concurrent Requests: {concurrent_results['success_rate']:.1f}% success rate, "
                       f"{concurrent_results['requests_per_second']:.2f} req/s")
        
        # WebSocket Performance Summary
        if 'messages_received' in websocket_results and websocket_results['messages_received'] > 0:
            logger.info(f"WebSocket: {websocket_results['messages_received']} messages, "
                       f"{websocket_results['avg_message_latency_ms']:.2f}ms avg latency")
        
        # Backtest Scaling Summary
        logger.info("Backtest Performance Scaling:")
        for period, metrics in scaling_results.items():
            if metrics['response_time_ms'] is not None:
                logger.info(f"  {period}: {metrics['response_time_ms']:.2f}ms")
            else:
                logger.info(f"  {period}: FAILED")
        
        logger.info("=" * 60)
        
        return results

async def main():
    """Main function to run the performance test suite."""
    async with DashboardPerformanceTest() as test_suite:
        results = await test_suite.run_performance_tests()
        
        # Save results to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"tests/dashboard_performance_results_{timestamp}.json"
        
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"Performance test results saved to: {results_file}")
        
        return results

if __name__ == "__main__":
    asyncio.run(main())
