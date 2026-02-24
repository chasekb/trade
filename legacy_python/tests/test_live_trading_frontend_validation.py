#!/usr/bin/env python3
"""
Enhanced frontend validation test suite for live trading tab.

This test suite specifically focuses on validating that the frontend
is correctly displaying data from the backend APIs, including:
1. Browser console log validation
2. Order book signals widget data validation
3. Auto-refresh mechanism testing
4. Frontend-backend synchronization validation
"""

import asyncio
import json
import logging
import time
import unittest
from datetime import datetime
from typing import Dict, Any, List, Optional
import aiohttp
import sys
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Add the src directory to the path
sys.path.insert(0, 'src')

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LiveTradingFrontendValidationTest:
    """Enhanced frontend validation test suite for live trading tab."""
    
    def __init__(self, base_url: str = "http://localhost:8001", headless: bool = True):
        self.base_url = base_url
        self.headless = headless
        self.driver = None
        self.session = None
        self.test_results = []
        self.trading_session_id = None
    
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
        logger.info("🚀 Setting up frontend validation test environment...")
        
        # Set up Chrome options
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # Enable console logging
        chrome_options.add_argument("--enable-logging")
        chrome_options.add_argument("--log-level=0")
        chrome_options.set_capability('goog:loggingPrefs', {'browser': 'ALL'})
        
        # Initialize WebDriver
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.get(self.base_url)
        
        # Initialize HTTP session
        self.session = aiohttp.ClientSession()
        
        # Wait for page to load
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "tab-live-trading"))
        )
        
        # Navigate to live trading tab
        live_trading_tab = self.driver.find_element(By.ID, "tab-live-trading")
        live_trading_tab.click()
        
        # Wait for live trading tab to load
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "live-trading-content"))
        )
        
        logger.info("✅ Frontend validation test environment ready")
    
    async def teardown(self):
        """Clean up the test environment."""
        if self.driver:
            self.driver.quit()
        if self.session:
            await self.session.close()
        logger.info("🧹 Test environment cleaned up")
    
    async def check_browser_console_logs(self):
        """Check browser console logs for debugging information."""
        logger.info("🔍 Checking browser console logs...")
        
        try:
            # Get console logs
            logs = self.driver.get_log('browser')
            
            # Look for our debug messages
            debug_messages = []
            error_messages = []
            
            for log in logs:
                message = log.get('message', '')
                level = log.get('level', '')
                
                # Collect debug messages
                if 'Enhanced Trading Dashboard JavaScript loaded' in message:
                    debug_messages.append(message)
                elif 'loadLiveTradingData called' in message:
                    debug_messages.append(message)
                elif 'Trading not active locally' in message:
                    debug_messages.append(message)
                elif 'Server trading status' in message:
                    debug_messages.append(message)
                elif 'Trading is active, loading order book signals' in message:
                    debug_messages.append(message)
                elif 'Calling order book signals API' in message:
                    debug_messages.append(message)
                elif 'Order book signals API response' in message:
                    debug_messages.append(message)
                
                # Collect error messages
                if level == 'SEVERE':
                    error_messages.append(message)
            
            self.log_test_result(
                "Console Logs - Debug Messages Present",
                "> 0",
                len(debug_messages),
                len(debug_messages) > 0,
                f"Should have debug messages in console (found {len(debug_messages)}): {debug_messages[:3]}..."
            )
            
            self.log_test_result(
                "Console Logs - No JavaScript Errors",
                0,
                len(error_messages),
                len(error_messages) == 0,
                f"Should have no JavaScript errors (found {len(error_messages)}): {error_messages}"
            )
            
            # Log all debug messages for analysis
            for msg in debug_messages:
                logger.info(f"🔍 Console: {msg}")
        
        except Exception as e:
            self.log_test_result(
                "Console Logs - Exception",
                "No exception",
                str(e),
                False,
                f"Exception checking console logs: {e}"
            )
    
    async def validate_frontend_backend_sync(self):
        """Validate that frontend and backend are synchronized."""
        logger.info("🔄 Validating frontend-backend synchronization...")
        
        try:
            # Check backend trading status
            async with self.session.get(f"{self.base_url}/api/simulated-trading/status") as response:
                if response.status == 200:
                    backend_data = await response.json()
                    backend_trading_active = backend_data.get('is_trading', False)
                    
                    # Check frontend trading status
                    start_button = self.driver.find_element(By.ID, "start-trading-btn")
                    frontend_trading_active = "Stop Trading" in start_button.text
                    
                    self.log_test_result(
                        "Frontend-Backend Sync - Trading Status",
                        backend_trading_active,
                        frontend_trading_active,
                        backend_trading_active == frontend_trading_active,
                        f"Frontend ({frontend_trading_active}) should match backend ({backend_trading_active})"
                    )
                    
                    # Check symbols synchronization
                    if backend_trading_active:
                        backend_symbols = backend_data.get('symbols', [])
                        
                        # Check if frontend has symbols in strategy
                        try:
                            # Look for symbols in the order book signals table or other UI elements
                            symbols_present = len(backend_symbols) > 0
                            
                            self.log_test_result(
                                "Frontend-Backend Sync - Symbols",
                                "> 0",
                                len(backend_symbols),
                                len(backend_symbols) > 0,
                                f"Backend should have symbols (found {len(backend_symbols)}): {backend_symbols}"
                            )
                        except Exception as e:
                            logger.warning(f"Could not validate symbols sync: {e}")
        
        except Exception as e:
            self.log_test_result(
                "Frontend-Backend Sync - Exception",
                "No exception",
                str(e),
                False,
                f"Exception validating sync: {e}"
            )
    
    async def validate_order_book_signals_widget(self):
        """Validate the order book signals widget is displaying data correctly."""
        logger.info("📊 Validating order book signals widget...")
        
        try:
            # Check if order book signals table exists
            signals_table = self.driver.find_element(By.ID, "orderbook-signals-table")
            self.log_test_result(
                "Order Book Signals - Table Present",
                True,
                signals_table is not None,
                signals_table is not None,
                "Order book signals table should be present"
            )
            
            # Check if table has data rows
            rows = signals_table.find_elements(By.TAG_NAME, "tr")
            has_data_rows = len(rows) > 1  # More than just header row
            
            self.log_test_result(
                "Order Book Signals - Data Rows Present",
                True,
                has_data_rows,
                has_data_rows,
                f"Order book signals table should have data rows (found {len(rows)} rows)"
            )
            
            if has_data_rows:
                # Validate data content
                await self.validate_order_book_data_content(rows)
            else:
                # Check for empty state message
                await self.check_empty_state_message()
            
            # Check order book statistics
            await self.validate_order_book_statistics()
            
        except NoSuchElementException:
            self.log_test_result(
                "Order Book Signals - Table Present",
                True,
                False,
                False,
                "Order book signals table not found"
            )
    
    async def validate_order_book_data_content(self, rows):
        """Validate the content of order book signals data."""
        logger.info("📋 Validating order book signals data content...")
        
        try:
            # Check header row
            header_row = rows[0]
            headers = [cell.text.strip() for cell in header_row.find_elements(By.TAG_NAME, "th")]
            expected_headers = ["Symbol", "Bid Price", "Ask Price", "Spread", "Volume", "Squeeze Analysis", "Imbalance Analysis", "Large Trade Analysis"]
            
            self.log_test_result(
                "Order Book Signals - Headers Present",
                expected_headers,
                headers,
                len(headers) >= len(expected_headers),
                f"Order book signals table should have expected headers (found: {headers})"
            )
            
            # Check data rows
            data_rows = rows[1:]  # Skip header row
            for i, row in enumerate(data_rows[:3]):  # Check first 3 data rows
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 8:  # Should have at least 8 columns
                    symbol = cells[0].text.strip()
                    bid_price = cells[1].text.strip()
                    ask_price = cells[2].text.strip()
                    spread = cells[3].text.strip()
                    volume = cells[4].text.strip()
                    squeeze_analysis = cells[5].text.strip()
                    imbalance_analysis = cells[6].text.strip()
                    large_trade_analysis = cells[7].text.strip()
                    
                    # Validate symbol is not empty
                    self.log_test_result(
                        f"Order Book Signals - Row {i+1} Symbol",
                        "Not empty",
                        symbol,
                        symbol != "",
                        f"Symbol should not be empty (found: '{symbol}')"
                    )
                    
                    # Validate prices are not empty
                    self.log_test_result(
                        f"Order Book Signals - Row {i+1} Bid Price",
                        "Not empty",
                        bid_price,
                        bid_price != "" and bid_price != "N/A",
                        f"Bid price should not be empty (found: '{bid_price}')"
                    )
                    
                    self.log_test_result(
                        f"Order Book Signals - Row {i+1} Ask Price",
                        "Not empty",
                        ask_price,
                        ask_price != "" and ask_price != "N/A",
                        f"Ask price should not be empty (found: '{ask_price}')"
                    )
                    
                    # Validate analysis columns are not "N/A"
                    self.log_test_result(
                        f"Order Book Signals - Row {i+1} Squeeze Analysis",
                        "Not N/A",
                        squeeze_analysis,
                        squeeze_analysis != "N/A",
                        f"Squeeze analysis should not be N/A (found: '{squeeze_analysis}')"
                    )
                    
                    self.log_test_result(
                        f"Order Book Signals - Row {i+1} Imbalance Analysis",
                        "Not N/A",
                        imbalance_analysis,
                        imbalance_analysis != "N/A",
                        f"Imbalance analysis should not be N/A (found: '{imbalance_analysis}')"
                    )
                    
                    logger.info(f"📊 Row {i+1} data: {symbol} | {bid_price} | {ask_price} | {spread} | {volume} | {squeeze_analysis} | {imbalance_analysis} | {large_trade_analysis}")
        
        except Exception as e:
            self.log_test_result(
                "Order Book Signals - Data Content Validation",
                "No exception",
                str(e),
                False,
                f"Exception validating data content: {e}"
            )
    
    async def check_empty_state_message(self):
        """Check for empty state message."""
        logger.info("🔍 Checking for empty state message...")
        
        try:
            # Look for "No order book signals available" message
            empty_message_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'No order book signals available')]")
            
            self.log_test_result(
                "Order Book Signals - Empty State Message",
                "Present",
                len(empty_message_elements) > 0,
                len(empty_message_elements) > 0,
                f"Should show empty state message when no signals (found {len(empty_message_elements)} elements)"
            )
            
            if len(empty_message_elements) > 0:
                logger.warning("⚠️ Order book signals widget shows empty state - this may indicate a frontend issue")
        
        except Exception as e:
            self.log_test_result(
                "Order Book Signals - Empty State Check",
                "No exception",
                str(e),
                False,
                f"Exception checking empty state: {e}"
            )
    
    async def validate_order_book_statistics(self):
        """Validate order book statistics widget."""
        logger.info("📈 Validating order book statistics...")
        
        try:
            # Check if statistics elements exist
            total_analyzed = self.driver.find_element(By.ID, "total-analyzed")
            active_signals = self.driver.find_element(By.ID, "active-signals")
            last_updated = self.driver.find_element(By.ID, "last-updated")
            average_strength = self.driver.find_element(By.ID, "average-strength")
            
            # Validate statistics values
            total_analyzed_text = total_analyzed.text.strip()
            active_signals_text = active_signals.text.strip()
            last_updated_text = last_updated.text.strip()
            average_strength_text = average_strength.text.strip()
            
            self.log_test_result(
                "Order Book Statistics - Total Analyzed",
                "Not empty",
                total_analyzed_text,
                total_analyzed_text != "",
                f"Total analyzed should not be empty (found: '{total_analyzed_text}')"
            )
            
            self.log_test_result(
                "Order Book Statistics - Active Signals",
                "Not empty",
                active_signals_text,
                active_signals_text != "",
                f"Active signals should not be empty (found: '{active_signals_text}')"
            )
            
            self.log_test_result(
                "Order Book Statistics - Last Updated",
                "Not empty",
                last_updated_text,
                last_updated_text != "",
                f"Last updated should not be empty (found: '{last_updated_text}')"
            )
            
            logger.info(f"📈 Statistics: Total={total_analyzed_text}, Active={active_signals_text}, Updated={last_updated_text}, Strength={average_strength_text}")
        
        except NoSuchElementException:
            self.log_test_result(
                "Order Book Statistics - Elements Present",
                True,
                False,
                False,
                "Order book statistics elements not found"
            )
        except Exception as e:
            self.log_test_result(
                "Order Book Statistics - Validation",
                "No exception",
                str(e),
                False,
                f"Exception validating statistics: {e}"
            )
    
    async def test_order_book_auto_refresh(self):
        """Test that order book signals auto-refresh is working."""
        logger.info("🔄 Testing order book signals auto-refresh...")
        
        try:
            # Get initial data
            initial_rows = self.driver.find_element(By.ID, "orderbook-signals-table").find_elements(By.TAG_NAME, "tr")
            initial_count = len(initial_rows)
            
            # Wait for potential refresh (5 seconds)
            time.sleep(5)
            
            # Check if data has been refreshed
            refreshed_rows = self.driver.find_element(By.ID, "orderbook-signals-table").find_elements(By.TAG_NAME, "tr")
            refreshed_count = len(refreshed_rows)
            
            # Check browser console for refresh logs
            logs = self.driver.get_log('browser')
            refresh_logs = [log for log in logs if 'Frequent refresh triggered' in log.get('message', '')]
            
            self.log_test_result(
                "Order Book Signals - Auto Refresh Logs",
                "> 0",
                len(refresh_logs),
                len(refresh_logs) > 0,
                f"Should have auto-refresh logs (found {len(refresh_logs)})"
            )
            
            # Data should still be present after refresh
            self.log_test_result(
                "Order Book Signals - Data After Refresh",
                "Present",
                refreshed_count > 1,
                refreshed_count > 1,
                f"Data should still be present after refresh (rows: {refreshed_count})"
            )
        
        except Exception as e:
            self.log_test_result(
                "Order Book Signals - Auto Refresh Test",
                "No exception",
                str(e),
                False,
                f"Exception testing auto-refresh: {e}"
            )
    
    async def start_trading_and_validate(self):
        """Start trading and validate the entire flow."""
        logger.info("🚀 Starting trading and validating flow...")
        
        try:
            # Start trading first
            start_button = self.driver.find_element(By.ID, "start-trading-btn")
            start_button.click()
            
            # Wait for trading to start
            WebDriverWait(self.driver, 10).until(
                EC.text_to_be_present_in_element((By.ID, "start-trading-btn"), "Stop Trading")
            )
            
            # Wait for async trading to complete
            await self.wait_for_async_trading_completion()
            
            # Check browser console logs after trading starts
            await self.check_browser_console_logs()
            
            # Validate frontend-backend synchronization
            await self.validate_frontend_backend_sync()
            
            # Validate order book signals widget
            await self.validate_order_book_signals_widget()
            
            # Test auto-refresh mechanism
            await self.test_order_book_auto_refresh()
            
        except Exception as e:
            self.log_test_result(
                "Trading Flow - Exception",
                "No exception",
                str(e),
                False,
                f"Exception during trading flow: {e}"
            )
    
    async def wait_for_async_trading_completion(self):
        """Wait for async trading to complete."""
        logger.info("⏳ Waiting for async trading to complete...")
        
        max_wait_time = 30  # Maximum wait time in seconds
        wait_interval = 2   # Check every 2 seconds
        waited = 0
        
        while waited < max_wait_time:
            try:
                # Check async trading loading status via API
                async with self.session.get(f"{self.base_url}/api/async-trading/loading-status") as response:
                    if response.status == 200:
                        data = await response.json()
                        is_loading = data.get('is_loading', True)
                        
                        if not is_loading:
                            logger.info(f"✅ Async trading completed after {waited} seconds")
                            break
                        
                        logger.info(f"⏳ Async trading still loading... ({waited}s)")
                
                await asyncio.sleep(wait_interval)
                waited += wait_interval
                
            except Exception as e:
                logger.warning(f"Error checking async trading status: {e}")
                await asyncio.sleep(wait_interval)
                waited += wait_interval
        
        if waited >= max_wait_time:
            logger.warning("⚠️ Async trading did not complete within expected time")
        
        # Additional wait for frontend to process
        time.sleep(3)
    
    async def run_all_tests(self):
        """Run all frontend validation tests."""
        logger.info("🚀 Starting live trading frontend validation tests...")
        
        try:
            await self.setup()
            
            # Run test categories
            test_categories = [
                ("Browser Console Logs", self.check_browser_console_logs),
                ("Frontend-Backend Sync", self.validate_frontend_backend_sync),
                ("Trading Flow", self.start_trading_and_validate),
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
        logger.info("📊 Generating frontend validation test report...")
        
        # Calculate statistics
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['passed'])
        failed_tests = total_tests - passed_tests
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        # Log summary
        logger.info("=" * 80)
        logger.info("📊 LIVE TRADING FRONTEND VALIDATION TEST REPORT")
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
        report_file = f"tests/live_trading_frontend_validation_results_{timestamp}.json"
        
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
            json.dump(report_data, f, indent=2)
        
        logger.info(f"📄 Detailed report saved to: {report_file}")
        
        return success_rate >= 90.0  # Consider 90%+ success rate as passing

async def main():
    """Main test runner."""
    test_suite = LiveTradingFrontendValidationTest(headless=True)
    success = await test_suite.run_all_tests()
    
    if success:
        logger.info("🎉 Frontend validation tests PASSED!")
        return 0
    else:
        logger.error("💥 Frontend validation tests FAILED!")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
