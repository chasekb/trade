#!/usr/bin/env python3
"""
Test runner for live trading comprehensive test suite.

This script runs all live trading tests:
1. API tests (backend functionality)
2. Frontend tests (requires browser automation)
3. Integration tests (end-to-end workflow)

Usage:
    python run_live_trading_tests.py [--api-only] [--frontend-only] [--headless]
"""

import asyncio
import argparse
import logging
import sys
import os
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, 'src')

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_api_tests():
    """Run API-focused tests."""
    logger.info("🚀 Running API tests...")
    
    try:
        from test_live_trading_api import LiveTradingAPITest
        
        async with LiveTradingAPITest() as tester:
            results = await tester.run_all_tests()
            return results
    except Exception as e:
        logger.error(f"❌ API tests failed: {e}")
        return []

async def run_frontend_tests(headless=True):
    """Run frontend tests using Selenium."""
    logger.info("🚀 Running frontend tests...")
    
    try:
        from test_live_trading_comprehensive import LiveTradingComprehensiveTest
        
        async with LiveTradingComprehensiveTest(headless=headless) as tester:
            results = await tester.run_all_tests()
            return results
    except Exception as e:
        logger.error(f"❌ Frontend tests failed: {e}")
        return []

def check_dependencies():
    """Check if required dependencies are installed."""
    logger.info("🔍 Checking dependencies...")
    
    missing_deps = []
    
    # Check Python packages
    required_packages = ['aiohttp', 'selenium']
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_deps.append(package)
    
    # Check Chrome/Chromium
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.quit()
    except Exception as e:
        missing_deps.append(f"Chrome WebDriver: {e}")
    
    if missing_deps:
        logger.error("❌ Missing dependencies:")
        for dep in missing_deps:
            logger.error(f"  - {dep}")
        logger.error("\nTo install missing packages:")
        logger.error("  pip install aiohttp selenium")
        logger.error("\nTo install Chrome WebDriver:")
        logger.error("  Visit: https://chromedriver.chromium.org/")
        return False
    
    logger.info("✅ All dependencies are available")
    return True

def check_server_running(base_url="http://localhost:8001"):
    """Check if the trading server is running."""
    logger.info("🔍 Checking if server is running...")
    
    try:
        import aiohttp
        import asyncio
        
        async def check():
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{base_url}/api/health") as response:
                    return response.status == 200
        
        result = asyncio.run(check())
        if result:
            logger.info("✅ Server is running")
            return True
        else:
            logger.error("❌ Server is not responding")
            return False
    except Exception as e:
        logger.error(f"❌ Cannot connect to server: {e}")
        return False

def open_frontend_test_page():
    """Open the frontend test page in browser."""
    logger.info("🌐 Opening frontend test page...")
    
    test_file = Path(__file__).parent / "test_live_trading_frontend.html"
    if test_file.exists():
        webbrowser.open(f"file://{test_file.absolute()}")
        logger.info("✅ Frontend test page opened in browser")
        logger.info("💡 Run the tests manually in the browser")
    else:
        logger.error("❌ Frontend test file not found")

def generate_combined_report(api_results, frontend_results):
    """Generate a combined test report."""
    logger.info("📊 Generating combined test report...")
    
    all_results = api_results + frontend_results
    total_tests = len(all_results)
    passed_tests = sum(1 for result in all_results if result['passed'])
    failed_tests = total_tests - passed_tests
    success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
    
    # Group results by test suite
    suites = {
        'API Tests': [r for r in all_results if 'API' in r['test_name'] or 'Simulated Trading' in r['test_name'] or 'Order Book' in r['test_name'] or 'Products' in r['test_name'] or 'Session' in r['test_name'] or 'WebSocket' in r['test_name']],
        'Frontend Tests': [r for r in all_results if r not in suites['API Tests']]
    }
    
    logger.info("=" * 80)
    logger.info("📊 LIVE TRADING COMPREHENSIVE TEST REPORT")
    logger.info("=" * 80)
    logger.info(f"Total Tests: {total_tests}")
    logger.info(f"Passed: {passed_tests} ✅")
    logger.info(f"Failed: {failed_tests} ❌")
    logger.info(f"Success Rate: {success_rate:.1f}%")
    logger.info("=" * 80)
    
    for suite_name, suite_results in suites.items():
        if suite_results:
            suite_passed = sum(1 for r in suite_results if r['passed'])
            suite_total = len(suite_results)
            suite_rate = (suite_passed / suite_total) * 100 if suite_total > 0 else 0
            logger.info(f"{suite_name}: {suite_passed}/{suite_total} ({suite_rate:.1f}%)")
    
    # Save detailed report
    report_data = {
        'summary': {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': failed_tests,
            'success_rate': success_rate,
            'timestamp': datetime.now().isoformat()
        },
        'suites': suites,
        'detailed_results': all_results
    }
    
    report_filename = f"live_trading_combined_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path = Path(__file__).parent / report_filename
    
    with open(report_path, 'w') as f:
        import json
        json.dump(report_data, f, indent=2)
    
    logger.info(f"📄 Detailed report saved to: {report_path}")
    
    return success_rate >= 80  # Consider 80%+ success rate as passing

async def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(description='Run live trading comprehensive tests')
    parser.add_argument('--api-only', action='store_true', help='Run only API tests')
    parser.add_argument('--frontend-only', action='store_true', help='Run only frontend tests')
    parser.add_argument('--headless', action='store_true', default=True, help='Run frontend tests in headless mode')
    parser.add_argument('--no-headless', action='store_true', help='Run frontend tests with visible browser')
    parser.add_argument('--open-browser', action='store_true', help='Open frontend test page in browser')
    parser.add_argument('--skip-deps', action='store_true', help='Skip dependency checks')
    
    args = parser.parse_args()
    
    logger.info("🧪 Live Trading Comprehensive Test Suite")
    logger.info("=" * 50)
    
    # Check dependencies
    if not args.skip_deps:
        if not check_dependencies():
            logger.error("❌ Dependency check failed. Use --skip-deps to bypass.")
            return 1
    
    # Check server
    if not check_server_running():
        logger.error("❌ Server check failed. Please start the trading server first.")
        return 1
    
    # Open browser test page if requested
    if args.open_browser:
        open_frontend_test_page()
        return 0
    
    # Run tests
    api_results = []
    frontend_results = []
    
    # Run API tests
    if not args.frontend_only:
        api_results = await run_api_tests()
    
    # Run frontend tests
    if not args.api_only:
        headless_mode = args.headless and not args.no_headless
        frontend_results = await run_frontend_tests(headless=headless_mode)
    
    # Generate combined report
    if api_results or frontend_results:
        success = generate_combined_report(api_results, frontend_results)
        return 0 if success else 1
    else:
        logger.error("❌ No tests were run")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
