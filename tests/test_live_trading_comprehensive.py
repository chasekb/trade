#!/usr/bin/env python3
"""
Comprehensive test suite for live trading tab functionality.

This test suite covers the complete live trading workflow:
1. Page load and initialization
2. Trading mode selection (simulated vs live)
3. Strategy configuration
4. Trading controls (start/stop/pause)
5. Live order book signals
6. Open positions management
7. Trading history display

Tests both frontend UI interactions and backend API functionality.
"""

import asyncio
import json
import logging
import time
import unittest
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import aiohttp
import sys
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Add the src directory to the path
sys.path.insert(0, 'src')

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LiveTradingComprehensiveTest:
    """Comprehensive test suite for live trading tab functionality."""
    
    def __init__(self, base_url: str = "http://localhost:8001", headless: bool = True):
        self.base_url = base_url
        self.headless = headless
        self.driver = None
        self.session = None
        self.test_results = []
        self.trading_session_id = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
        if self.driver:
            self.driver.quit()
    
    def setup_driver(self):
        """Setup Chrome WebDriver for frontend testing."""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.implicitly_wait(10)
        
    def log_test_result(self, test_name: str, expected: Any, actual: Any, passed: bool, details: str = ""):
        """Log test result with expected vs actual comparison."""
        result = {
            'test_name': test_name,
            'expected': expected,
            'actual': actual,
            'passed': passed,
            'details': details,
            'timestamp': datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status} {test_name}: {details}")
        if not passed:
            logger.info(f"  Expected: {expected}")
            logger.info(f"  Actual: {actual}")
    
    async def test_page_load(self):
        """Test 1: Page load and initialization."""
        logger.info("🧪 Testing page load and initialization...")
        
        try:
            # Load the dashboard page
            self.driver.get(f"{self.base_url}")
            
            # Wait for page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "live-trading-tab"))
            )
            
            # Check if live trading tab is present
            live_trading_tab = self.driver.find_element(By.ID, "live-trading-tab")
            self.log_test_result(
                "Page Load - Live Trading Tab Present",
                True,
                live_trading_tab is not None,
                live_trading_tab is not None,
                "Live trading tab should be present on page load"
            )
            
            # Click on live trading tab
            live_trading_tab.click()
            
            # Wait for live trading content to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "live-trading-content"))
            )
            
            # Check if live trading content is visible
            live_trading_content = self.driver.find_element(By.ID, "live-trading-content")
            is_visible = live_trading_content.is_displayed()
            
            self.log_test_result(
                "Page Load - Live Trading Content Visible",
                True,
                is_visible,
                is_visible,
                "Live trading content should be visible after tab click"
            )
            
            # Check for essential UI elements
            essential_elements = [
                "trading-mode-simulated",
                "trading-mode-live", 
                "trading-symbol-mode-single",
                "trading-symbol-mode-universe",
                "live-trading-symbol",
                "live-strategy-type",
                "start-trading-btn"
            ]
            
            for element_id in essential_elements:
                try:
                    element = self.driver.find_element(By.ID, element_id)
                    self.log_test_result(
                        f"Page Load - {element_id} Present",
                        True,
                        element is not None,
                        element is not None,
                        f"Essential UI element {element_id} should be present"
                    )
                except NoSuchElementException:
                    self.log_test_result(
                        f"Page Load - {element_id} Present",
                        True,
                        False,
                        False,
                        f"Essential UI element {element_id} is missing"
                    )
            
            return True
            
        except Exception as e:
            self.log_test_result(
                "Page Load - Exception",
                "No exception",
                str(e),
                False,
                f"Exception during page load: {e}"
            )
            return False
    
    async def test_trading_mode_selection(self):
        """Test 2: Trading mode selection (simulated vs live)."""
        logger.info("🧪 Testing trading mode selection...")
        
        try:
            # Test simulated mode selection
            simulated_radio = self.driver.find_element(By.ID, "trading-mode-simulated")
            simulated_radio.click()
            
            # Check if simulated mode is selected
            is_simulated_selected = simulated_radio.is_selected()
            self.log_test_result(
                "Trading Mode - Simulated Selection",
                True,
                is_simulated_selected,
                is_simulated_selected,
                "Simulated trading mode should be selectable"
            )
            
            # Test live mode selection
            live_radio = self.driver.find_element(By.ID, "trading-mode-live")
            live_radio.click()
            
            # Check if live mode is selected
            is_live_selected = live_radio.is_selected()
            self.log_test_result(
                "Trading Mode - Live Selection",
                True,
                is_live_selected,
                is_live_selected,
                "Live trading mode should be selectable"
            )
            
            # Switch back to simulated for further tests
            simulated_radio.click()
            
            # Test symbol mode selection
            single_radio = self.driver.find_element(By.ID, "trading-symbol-mode-single")
            single_radio.click()
            
            is_single_selected = single_radio.is_selected()
            self.log_test_result(
                "Trading Mode - Single Symbol Selection",
                True,
                is_single_selected,
                is_single_selected,
                "Single symbol mode should be selectable"
            )
            
            # Test universe mode selection
            universe_radio = self.driver.find_element(By.ID, "trading-symbol-mode-universe")
            universe_radio.click()
            
            is_universe_selected = universe_radio.is_selected()
            self.log_test_result(
                "Trading Mode - Universe Selection",
                True,
                is_universe_selected,
                is_universe_selected,
                "Universe mode should be selectable"
            )
            
            # Switch back to single for further tests
            single_radio.click()
            
            return True
            
        except Exception as e:
            self.log_test_result(
                "Trading Mode - Exception",
                "No exception",
                str(e),
                False,
                f"Exception during trading mode selection: {e}"
            )
            return False
    
    async def test_strategy_configuration(self):
        """Test 3: Strategy configuration."""
        logger.info("🧪 Testing strategy configuration...")
        
        try:
            # Test strategy type selection
            strategy_select = Select(self.driver.find_element(By.ID, "live-strategy-type"))
            
            # Get available strategies
            available_strategies = [option.text for option in strategy_select.options]
            expected_strategies = ["SMA", "EMA", "RSI", "MACD", "Bollinger Bands", "Stochastic", "ATR", "Fibonacci", "Order Book", "DCA", "Buy and Hold"]
            
            self.log_test_result(
                "Strategy Config - Available Strategies",
                expected_strategies,
                available_strategies,
                len(available_strategies) >= 5,
                f"Should have multiple strategy options available"
            )
            
            # Select SMA strategy
            strategy_select.select_by_visible_text("SMA")
            selected_strategy = strategy_select.first_selected_option.text
            
            self.log_test_result(
                "Strategy Config - SMA Selection",
                "SMA",
                selected_strategy,
                selected_strategy == "SMA",
                "SMA strategy should be selectable"
            )
            
            # Test symbol selection
            symbol_select = Select(self.driver.find_element(By.ID, "live-trading-symbol"))
            
            # Get available symbols
            available_symbols = [option.text for option in symbol_select.options if option.text]
            self.log_test_result(
                "Strategy Config - Available Symbols",
                "Multiple symbols",
                f"{len(available_symbols)} symbols",
                len(available_symbols) > 10,
                f"Should have multiple trading symbols available"
            )
            
            # Select BTC-USD
            symbol_select.select_by_visible_text("BTC-USD")
            selected_symbol = symbol_select.first_selected_option.text
            
            self.log_test_result(
                "Strategy Config - BTC-USD Selection",
                "BTC-USD",
                selected_symbol,
                selected_symbol == "BTC-USD",
                "BTC-USD should be selectable"
            )
            
            # Test universe configuration
            universe_radio = self.driver.find_element(By.ID, "trading-symbol-mode-universe")
            universe_radio.click()
            
            # Wait for universe config to appear
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.ID, "universe-config"))
            )
            
            # Test universe type selection
            universe_type_select = Select(self.driver.find_element(By.ID, "universe-type"))
            universe_type_select.select_by_visible_text("All USD Pairs (324 symbols) - Recommended")
            
            selected_universe_type = universe_type_select.first_selected_option.text
            self.log_test_result(
                "Strategy Config - Universe Type Selection",
                "All USD Pairs",
                selected_universe_type,
                "All USD Pairs" in selected_universe_type,
                "Universe type should be selectable"
            )
            
            # Switch back to single symbol mode
            single_radio = self.driver.find_element(By.ID, "trading-symbol-mode-single")
            single_radio.click()
            
            return True
            
        except Exception as e:
            self.log_test_result(
                "Strategy Config - Exception",
                "No exception",
                str(e),
                False,
                f"Exception during strategy configuration: {e}"
            )
            return False
    
    async def test_trading_controls(self):
        """Test 4: Trading controls (start/stop/pause)."""
        logger.info("🧪 Testing trading controls...")
        
        try:
            # Test start trading button
            start_button = self.driver.find_element(By.ID, "start-trading-btn")
            
            # Check if start button is initially enabled
            is_start_enabled = start_button.is_enabled()
            self.log_test_result(
                "Trading Controls - Start Button Enabled",
                True,
                is_start_enabled,
                is_start_enabled,
                "Start trading button should be enabled initially"
            )
            
            # Click start trading
            start_button.click()
            
            # Wait for trading to start
            WebDriverWait(self.driver, 10).until(
                EC.text_to_be_present_in_element((By.ID, "start-trading-btn"), "Stop Trading")
            )
            
            # Check if button text changed to "Stop Trading"
            button_text = start_button.text
            self.log_test_result(
                "Trading Controls - Start Trading",
                "Stop Trading",
                button_text,
                "Stop Trading" in button_text,
                "Button should change to 'Stop Trading' after starting"
            )
            
            # Check if trading status shows as active
            try:
                trading_status = self.driver.find_element(By.ID, "trading-status")
                status_text = trading_status.text
                self.log_test_result(
                    "Trading Controls - Trading Status Active",
                    "Active",
                    status_text,
                    "Active" in status_text,
                    "Trading status should show as active"
                )
            except NoSuchElementException:
                self.log_test_result(
                    "Trading Controls - Trading Status Active",
                    "Active",
                    "Element not found",
                    False,
                    "Trading status element not found"
                )
            
            # Test pause trading
            try:
                pause_button = self.driver.find_element(By.ID, "pause-trading-btn")
                pause_button.click()
                
                # Check if pause button text changed
                pause_text = pause_button.text
                self.log_test_result(
                    "Trading Controls - Pause Trading",
                    "Resume Trading",
                    pause_text,
                    "Resume" in pause_text,
                    "Pause button should change to 'Resume' after pausing"
                )
                
                # Resume trading
                pause_button.click()
                
            except NoSuchElementException:
                self.log_test_result(
                    "Trading Controls - Pause Trading",
                    "Available",
                    "Element not found",
                    False,
                    "Pause button not found"
                )
            
            # Test stop trading
            start_button.click()  # This should now be the stop button
            
            # Wait for trading to stop
            WebDriverWait(self.driver, 10).until(
                EC.text_to_be_present_in_element((By.ID, "start-trading-btn"), "Start Trading")
            )
            
            # Check if button text changed back to "Start Trading"
            button_text = start_button.text
            self.log_test_result(
                "Trading Controls - Stop Trading",
                "Start Trading",
                button_text,
                "Start Trading" in button_text,
                "Button should change back to 'Start Trading' after stopping"
            )
            
            return True
            
        except Exception as e:
            self.log_test_result(
                "Trading Controls - Exception",
                "No exception",
                str(e),
                False,
                f"Exception during trading controls test: {e}"
            )
            return False
    
    async def test_live_order_book_signals(self):
        """Test 5: Live order book signals."""
        logger.info("🧪 Testing live order book signals...")
        
        try:
            # Start trading first
            start_button = self.driver.find_element(By.ID, "start-trading-btn")
            start_button.click()
            
            # Wait for trading to start
            WebDriverWait(self.driver, 10).until(
                EC.text_to_be_present_in_element((By.ID, "start-trading-btn"), "Stop Trading")
            )
            
            # Wait for order book signals to load
            time.sleep(5)  # Give time for signals to load
            
            # Check if order book signals table exists
            try:
                signals_table = self.driver.find_element(By.ID, "orderbook-signals-table")
                self.log_test_result(
                    "Order Book Signals - Table Present",
                    True,
                    signals_table is not None,
                    signals_table is not None,
                    "Order book signals table should be present"
                )
                
                # Check if table has rows
                rows = signals_table.find_elements(By.TAG_NAME, "tr")
                has_data_rows = len(rows) > 1  # More than just header row
                
                self.log_test_result(
                    "Order Book Signals - Data Rows",
                    True,
                    has_data_rows,
                    has_data_rows,
                    f"Order book signals table should have data rows (found {len(rows)} rows)"
                )
                
                # Check for specific columns
                if len(rows) > 0:
                    header_row = rows[0]
                    headers = [cell.text for cell in header_row.find_elements(By.TAG_NAME, "th")]
                    expected_headers = ["Symbol", "Bid Price", "Ask Price", "Spread", "Volume", "Squeeze Analysis", "Imbalance Analysis", "Large Trade Analysis"]
                    
                    self.log_test_result(
                        "Order Book Signals - Headers Present",
                        expected_headers,
                        headers,
                        len(headers) >= 5,
                        f"Order book signals should have proper headers"
                    )
                
            except NoSuchElementException:
                self.log_test_result(
                    "Order Book Signals - Table Present",
                    True,
                    False,
                    False,
                    "Order book signals table not found"
                )
            
            # Test refresh button
            try:
                refresh_button = self.driver.find_element(By.ID, "refresh-orderbook-signals")
                refresh_button.click()
                
                self.log_test_result(
                    "Order Book Signals - Refresh Button",
                    True,
                    True,
                    True,
                    "Refresh button should be clickable"
                )
                
            except NoSuchElementException:
                self.log_test_result(
                    "Order Book Signals - Refresh Button",
                    True,
                    False,
                    False,
                    "Refresh button not found"
                )
            
            # Stop trading
            start_button.click()
            
            return True
            
        except Exception as e:
            self.log_test_result(
                "Order Book Signals - Exception",
                "No exception",
                str(e),
                False,
                f"Exception during order book signals test: {e}"
            )
            return False
    
    async def test_open_positions(self):
        """Test 6: Open positions management."""
        logger.info("🧪 Testing open positions...")
        
        try:
            # Check if positions table exists
            try:
                positions_table = self.driver.find_element(By.ID, "positions-tbody")
                self.log_test_result(
                    "Open Positions - Table Present",
                    True,
                    positions_table is not None,
                    positions_table is not None,
                    "Open positions table should be present"
                )
                
                # Check if table shows "No open positions" initially
                table_content = positions_table.text
                has_no_positions = "No open positions" in table_content
                
                self.log_test_result(
                    "Open Positions - No Positions Initially",
                    True,
                    has_no_positions,
                    has_no_positions,
                    "Should show 'No open positions' when no trades are active"
                )
                
            except NoSuchElementException:
                self.log_test_result(
                    "Open Positions - Table Present",
                    True,
                    False,
                    False,
                    "Open positions table not found"
                )
            
            # Test refresh button
            try:
                refresh_button = self.driver.find_element(By.ID, "refresh-trading-stats")
                refresh_button.click()
                
                self.log_test_result(
                    "Open Positions - Refresh Button",
                    True,
                    True,
                    True,
                    "Refresh button should be clickable"
                )
                
            except NoSuchElementException:
                self.log_test_result(
                    "Open Positions - Refresh Button",
                    True,
                    False,
                    False,
                    "Refresh button not found"
                )
            
            return True
            
        except Exception as e:
            self.log_test_result(
                "Open Positions - Exception",
                "No exception",
                str(e),
                False,
                f"Exception during open positions test: {e}"
            )
            return False
    
    async def test_trading_history(self):
        """Test 7: Trading history display."""
        logger.info("🧪 Testing trading history...")
        
        try:
            # Check if trading history table exists
            try:
                history_table = self.driver.find_element(By.ID, "trading-history-tbody")
                self.log_test_result(
                    "Trading History - Table Present",
                    True,
                    history_table is not None,
                    history_table is not None,
                    "Trading history table should be present"
                )
                
                # Check if table shows "No recent trades" initially
                table_content = history_table.text
                has_no_trades = "No recent trades" in table_content
                
                self.log_test_result(
                    "Trading History - No Trades Initially",
                    True,
                    has_no_trades,
                    has_no_trades,
                    "Should show 'No recent trades' when no trades have been executed"
                )
                
            except NoSuchElementException:
                self.log_test_result(
                    "Trading History - Table Present",
                    True,
                    False,
                    False,
                    "Trading history table not found"
                )
            
            # Test pagination controls
            try:
                pagination = self.driver.find_element(By.CLASS_NAME, "pagination")
                self.log_test_result(
                    "Trading History - Pagination Present",
                    True,
                    pagination is not None,
                    pagination is not None,
                    "Trading history should have pagination controls"
                )
                
            except NoSuchElementException:
                self.log_test_result(
                    "Trading History - Pagination Present",
                    True,
                    False,
                    False,
                    "Trading history pagination not found"
                )
            
            return True
            
        except Exception as e:
            self.log_test_result(
                "Trading History - Exception",
                "No exception",
                str(e),
                False,
                f"Exception during trading history test: {e}"
            )
            return False
    
    async def test_api_endpoints(self):
        """Test backend API endpoints for live trading."""
        logger.info("🧪 Testing API endpoints...")
        
        try:
            # Test health endpoint
            async with self.session.get(f"{self.base_url}/api/health") as response:
                health_data = await response.json()
                self.log_test_result(
                    "API - Health Endpoint",
                    200,
                    response.status,
                    response.status == 200,
                    "Health endpoint should return 200"
                )
            
            # Test products endpoint
            async with self.session.get(f"{self.base_url}/api/products") as response:
                products_data = await response.json()
                has_categories = 'categories' in products_data
                self.log_test_result(
                    "API - Products Endpoint",
                    True,
                    has_categories,
                    has_categories,
                    "Products endpoint should return categories"
                )
            
            # Test simulated trading status
            async with self.session.get(f"{self.base_url}/api/simulated-trading/status") as response:
                status_data = await response.json()
                has_portfolio = 'portfolio' in status_data
                self.log_test_result(
                    "API - Simulated Trading Status",
                    True,
                    has_portfolio,
                    has_portfolio,
                    "Simulated trading status should return portfolio data"
                )
            
            # Test order book signals endpoint
            async with self.session.get(f"{self.base_url}/api/orderbook/live-signals?symbols=BTC-USD") as response:
                signals_data = await response.json()
                has_signals = 'signals' in signals_data
                self.log_test_result(
                    "API - Order Book Signals",
                    True,
                    has_signals,
                    has_signals,
                    "Order book signals endpoint should return signals data"
                )
            
            return True
            
        except Exception as e:
            self.log_test_result(
                "API - Exception",
                "No exception",
                str(e),
                False,
                f"Exception during API testing: {e}"
            )
            return False
    
    async def run_all_tests(self):
        """Run all live trading tests."""
        logger.info("🚀 Starting comprehensive live trading tests...")
        
        # Setup WebDriver
        self.setup_driver()
        
        # Run all test categories
        test_categories = [
            ("Page Load", self.test_page_load),
            ("Trading Mode Selection", self.test_trading_mode_selection),
            ("Strategy Configuration", self.test_strategy_configuration),
            ("Trading Controls", self.test_trading_controls),
            ("Live Order Book Signals", self.test_live_order_book_signals),
            ("Open Positions", self.test_open_positions),
            ("Trading History", self.test_trading_history),
            ("API Endpoints", self.test_api_endpoints)
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
        
        return self.test_results
    
    def generate_test_report(self):
        """Generate comprehensive test report."""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['passed'])
        failed_tests = total_tests - passed_tests
        
        logger.info("=" * 80)
        logger.info("📊 LIVE TRADING COMPREHENSIVE TEST REPORT")
        logger.info("=" * 80)
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"Passed: {passed_tests} ✅")
        logger.info(f"Failed: {failed_tests} ❌")
        logger.info(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        logger.info("=" * 80)
        
        # Group results by category
        categories = {}
        for result in self.test_results:
            category = result['test_name'].split(' - ')[0]
            if category not in categories:
                categories[category] = {'passed': 0, 'failed': 0, 'tests': []}
            
            if result['passed']:
                categories[category]['passed'] += 1
            else:
                categories[category]['failed'] += 1
            
            categories[category]['tests'].append(result)
        
        # Print category summary
        for category, stats in categories.items():
            total = stats['passed'] + stats['failed']
            success_rate = (stats['passed'] / total) * 100 if total > 0 else 0
            logger.info(f"{category}: {stats['passed']}/{total} ({success_rate:.1f}%)")
        
        # Save detailed results
        report_data = {
            'summary': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': failed_tests,
                'success_rate': (passed_tests/total_tests)*100 if total_tests > 0 else 0
            },
            'categories': categories,
            'detailed_results': self.test_results,
            'timestamp': datetime.now().isoformat()
        }
        
        report_filename = f"live_trading_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(f"tests/{report_filename}", 'w') as f:
            json.dump(report_data, f, indent=2)
        
        logger.info(f"📄 Detailed report saved to: tests/{report_filename}")

async def main():
    """Main test runner."""
    async with LiveTradingComprehensiveTest() as tester:
        await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())
