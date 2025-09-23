#!/usr/bin/env python3
"""
Simple frontend validation test that checks the frontend without browser automation.

This test validates that:
1. The frontend HTML loads correctly
2. JavaScript files are accessible
3. API endpoints are working
4. Backend-frontend synchronization is correct
"""

import asyncio
import aiohttp
import logging
import sys
import os
from datetime import datetime
from typing import Dict, Any

# Add the src directory to the path
sys.path.insert(0, 'src')

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleFrontendValidationTest:
    """Simple frontend validation test without browser automation."""
    
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.session = None
        self.test_results = []
    
    def log_test_result(self, test_name: str, expected: Any, actual: Any, passed: bool, details: str):
        """Log a test result."""
        result = {
            "test_name": test_name,
            "expected": expected,
            "actual": actual,
            "passed": passed,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status} {test_name}: {details}")
    
    async def setup(self):
        """Set up the test environment."""
        logger.info("🚀 Setting up simple frontend validation test environment...")
        self.session = aiohttp.ClientSession()
        logger.info("✅ Test environment ready")
    
    async def teardown(self):
        """Clean up the test environment."""
        if self.session:
            await self.session.close()
        logger.info("🧹 Test environment cleaned up")
    
    async def test_frontend_html_loading(self):
        """Test that the frontend HTML loads correctly."""
        logger.info("🌐 Testing frontend HTML loading...")
        
        try:
            async with self.session.get(f"{self.base_url}/") as response:
                html_content = await response.text()
                
                # Check if HTML contains expected elements
                has_live_trading_tab = "tab-live-trading" in html_content
                has_orderbook_table = "orderbook-signals-table" in html_content
                has_javascript = "dashboard_enhanced.js" in html_content
                
                self.log_test_result(
                    "Frontend HTML - Live Trading Tab",
                    True,
                    has_live_trading_tab,
                    has_live_trading_tab,
                    "HTML should contain live trading tab element"
                )
                
                self.log_test_result(
                    "Frontend HTML - Order Book Table",
                    True,
                    has_orderbook_table,
                    has_orderbook_table,
                    "HTML should contain order book signals table"
                )
                
                self.log_test_result(
                    "Frontend HTML - JavaScript File",
                    True,
                    has_javascript,
                    has_javascript,
                    "HTML should reference dashboard_enhanced.js"
                )
                
                # Check for cache-busting version parameter
                has_version_param = "?v=" in html_content
                self.log_test_result(
                    "Frontend HTML - Cache Busting",
                    True,
                    has_version_param,
                    has_version_param,
                    "HTML should have cache-busting version parameter"
                )
        
        except Exception as e:
            self.log_test_result(
                "Frontend HTML - Exception",
                "No exception",
                str(e),
                False,
                f"Exception loading frontend HTML: {e}"
            )
    
    async def test_javascript_file_accessibility(self):
        """Test that JavaScript files are accessible."""
        logger.info("📜 Testing JavaScript file accessibility...")
        
        try:
            async with self.session.get(f"{self.base_url}/static/js/dashboard_enhanced.js") as response:
                js_content = await response.text()
                
                # Check if JavaScript contains expected debug messages
                has_debug_log = "Enhanced Trading Dashboard JavaScript loaded" in js_content
                has_load_function = "loadLiveTradingData" in js_content
                has_orderbook_function = "loadOrderBookSignals" in js_content
                
                self.log_test_result(
                    "JavaScript - Debug Log Present",
                    True,
                    has_debug_log,
                    has_debug_log,
                    "JavaScript should contain debug log message"
                )
                
                self.log_test_result(
                    "JavaScript - Load Function Present",
                    True,
                    has_load_function,
                    has_load_function,
                    "JavaScript should contain loadLiveTradingData function"
                )
                
                self.log_test_result(
                    "JavaScript - Order Book Function Present",
                    True,
                    has_orderbook_function,
                    has_orderbook_function,
                    "JavaScript should contain loadOrderBookSignals function"
                )
                
                # Check for recent version
                has_recent_version = "20250923" in js_content
                self.log_test_result(
                    "JavaScript - Recent Version",
                    True,
                    has_recent_version,
                    has_recent_version,
                    "JavaScript should contain recent version (20250923)"
                )
        
        except Exception as e:
            self.log_test_result(
                "JavaScript - Exception",
                "No exception",
                str(e),
                False,
                f"Exception accessing JavaScript file: {e}"
            )
    
    async def test_api_endpoints_accessibility(self):
        """Test that API endpoints are accessible."""
        logger.info("🔌 Testing API endpoints accessibility...")
        
        endpoints_to_test = [
            "/api/simulated-trading/status",
            "/api/orderbook/live-signals?symbols=BTC-USD",
            "/api/async-trading/loading-status"
        ]
        
        for endpoint in endpoints_to_test:
            try:
                async with self.session.get(f"{self.base_url}{endpoint}") as response:
                    is_accessible = response.status == 200
                    
                    self.log_test_result(
                        f"API Endpoint - {endpoint}",
                        200,
                        response.status,
                        is_accessible,
                        f"API endpoint should be accessible (status: {response.status})"
                    )
                    
                    if is_accessible:
                        # Try to parse JSON response
                        try:
                            data = await response.json()
                            self.log_test_result(
                                f"API Response - {endpoint} JSON",
                                "Valid JSON",
                                "Valid JSON",
                                True,
                                f"API endpoint returns valid JSON"
                            )
                        except Exception as json_error:
                            self.log_test_result(
                                f"API Response - {endpoint} JSON",
                                "Valid JSON",
                                "Invalid JSON",
                                False,
                                f"API endpoint JSON parsing failed: {json_error}"
                            )
            
            except Exception as e:
                self.log_test_result(
                    f"API Endpoint - {endpoint} Exception",
                    "No exception",
                    str(e),
                    False,
                    f"Exception accessing API endpoint: {e}"
                )
    
    async def test_backend_frontend_sync(self):
        """Test backend-frontend synchronization."""
        logger.info("🔄 Testing backend-frontend synchronization...")
        
        try:
            # Check trading status
            async with self.session.get(f"{self.base_url}/api/simulated-trading/status") as response:
                if response.status == 200:
                    data = await response.json()
                    is_trading = data.get('is_trading', False)
                    symbols = data.get('symbols', [])
                    
                    self.log_test_result(
                        "Backend-Frontend Sync - Trading Status",
                        "Valid response",
                        "Valid response",
                        True,
                        f"Backend trading status: {is_trading}"
                    )
                    
                    self.log_test_result(
                        "Backend-Frontend Sync - Symbols",
                        "> 0",
                        len(symbols),
                        len(symbols) > 0,
                        f"Backend should have symbols (found {len(symbols)})"
                    )
                    
                    # If trading is active, check order book signals
                    if is_trading and symbols:
                        symbol_param = symbols[0] if symbols else "BTC-USD"
                        async with self.session.get(f"{self.base_url}/api/orderbook/live-signals?symbols={symbol_param}") as signals_response:
                            if signals_response.status == 200:
                                signals_data = await signals_response.json()
                                trading_active = signals_data.get('trading_active', False)
                                signals_count = len(signals_data.get('signals', []))
                                
                                self.log_test_result(
                                    "Backend-Frontend Sync - Order Book Signals",
                                    "> 0",
                                    signals_count,
                                    signals_count > 0,
                                    f"Order book signals should be available (found {signals_count})"
                                )
                                
                                self.log_test_result(
                                    "Backend-Frontend Sync - Trading Active Flag",
                                    True,
                                    trading_active,
                                    trading_active,
                                    f"Trading active flag should be true (found: {trading_active})"
                                )
        
        except Exception as e:
            self.log_test_result(
                "Backend-Frontend Sync - Exception",
                "No exception",
                str(e),
                False,
                f"Exception testing sync: {e}"
            )
    
    async def test_async_trading_status(self):
        """Test async trading status."""
        logger.info("⏳ Testing async trading status...")
        
        try:
            async with self.session.get(f"{self.base_url}/api/async-trading/loading-status") as response:
                if response.status == 200:
                    data = await response.json()
                    is_loading = data.get('is_loading', True)
                    progress = data.get('progress', 0)
                    
                    self.log_test_result(
                        "Async Trading - Loading Status",
                        "Valid response",
                        "Valid response",
                        True,
                        f"Async trading loading: {is_loading}, progress: {progress}%"
                    )
                    
                    # If not loading, trading should be active
                    if not is_loading:
                        async with self.session.get(f"{self.base_url}/api/simulated-trading/status") as trading_response:
                            if trading_response.status == 200:
                                trading_data = await trading_response.json()
                                trading_active = trading_data.get('is_trading', False)
                                
                                self.log_test_result(
                                    "Async Trading - Trading Active After Loading",
                                    True,
                                    trading_active,
                                    trading_active,
                                    f"Trading should be active after async loading (found: {trading_active})"
                                )
        
        except Exception as e:
            self.log_test_result(
                "Async Trading - Exception",
                "No exception",
                str(e),
                False,
                f"Exception testing async trading: {e}"
            )
    
    async def run_all_tests(self):
        """Run all simple frontend validation tests."""
        logger.info("🚀 Starting simple frontend validation tests...")
        
        try:
            await self.setup()
            
            # Run test categories
            test_categories = [
                ("Frontend HTML Loading", self.test_frontend_html_loading),
                ("JavaScript File Accessibility", self.test_javascript_file_accessibility),
                ("API Endpoints Accessibility", self.test_api_endpoints_accessibility),
                ("Backend-Frontend Sync", self.test_backend_frontend_sync),
                ("Async Trading Status", self.test_async_trading_status),
            ]
            
            for category_name, test_method in test_categories:
                logger.info(f"📋 Running {category_name} tests...")
                try:
                    await test_method()
                except Exception as e:
                    self.log_test_result(
                        f"{category_name} - Test Suite Error",
                        "No exception",
                        str(e),
                        False,
                        f"Test suite failed with exception: {e}"
                    )
            
            # Generate test report
            self.generate_test_report()
            
        finally:
            await self.teardown()
    
    def generate_test_report(self):
        """Generate a comprehensive test report."""
        logger.info("📊 Generating simple frontend validation test report...")
        
        # Calculate statistics
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['passed'])
        failed_tests = total_tests - passed_tests
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        # Log summary
        logger.info("=" * 80)
        logger.info("📊 SIMPLE FRONTEND VALIDATION TEST REPORT")
        logger.info("=" * 80)
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"Passed: {passed_tests} ✅")
        logger.info(f"Failed: {failed_tests} ❌")
        logger.info(f"Success Rate: {success_rate:.1f}%")
        logger.info("=" * 80)
        
        # Log failed tests
        if failed_tests > 0:
            logger.info("❌ FAILED TESTS:")
            for result in self.test_results:
                if not result['passed']:
                    logger.info(f"  - {result['test_name']}: {result['details']}")
        
        # Save detailed report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"tests/simple_frontend_validation_results_{timestamp}.json"
        
        report_data = {
            "summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "success_rate": success_rate
            },
            "test_results": self.test_results,
            "timestamp": datetime.now().isoformat()
        }
        
        with open(report_file, 'w') as f:
            import json
            json.dump(report_data, f, indent=2)
        
        logger.info(f"📄 Detailed report saved to: {report_file}")
        
        return success_rate >= 90.0  # Consider 90%+ success rate as passing

async def main():
    """Main test runner."""
    test_suite = SimpleFrontendValidationTest()
    success = await test_suite.run_all_tests()
    
    if success:
        logger.info("🎉 Simple frontend validation tests PASSED!")
        return 0
    else:
        logger.error("💥 Simple frontend validation tests FAILED!")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
