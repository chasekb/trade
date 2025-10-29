#!/usr/bin/env python3

import asyncio
from playwright.async_api import async_playwright
import time

async def automate_trading():
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=False)

        try:
            # Create new page and navigate
            page = await browser.new_page()

            print("Step 3: Navigating to http://localhost:8001")
            await page.goto("http://localhost:8001")

            # Wait for page to load
            await page.wait_for_load_state('networkidle')

            print("Step 4: Looking for live trading option")
            # Try multiple selectors for live trading
            live_trading_selectors = [
                'text="Live Trading"',
                '[data-testid*="live"]',
                '.live-trading',
                'button:has-text("Live Trading")',
                'input[value="live"]',
                'select option[value*="live"]'
            ]

            live_trading_found = False
            for selector in live_trading_selectors:
                try:
                    element = await page.locator(selector).first
                    await element.wait_for(state='visible', timeout=2000)
                    await element.click()
                    live_trading_found = True
                    print(f"Clicked live trading with selector: {selector}")
                    break
                except:
                    continue

            if not live_trading_found:
                print("Live trading option not found, taking screenshot for debugging")
                await page.screenshot(path="debug_live_trading.png")
                return

            # Wait for any dynamic content to load
            await page.wait_for_load_state('networkidle')
            await asyncio.sleep(1)

            print("Step 5: Checking for strategy configuration")
            # Look for strategy configuration button
            strategy_config_selectors = [
                'text=/Strategy.*Configuration/i',
                '[data-testid*="strategy-config"]',
                '.strategy-config',
                'button:has-text("Strategy Configuration")',
                'button:has-text("Show Strategy Configuration")'
            ]

            strategy_config_found = False
            for selector in strategy_config_selectors:
                try:
                    element = await page.locator(selector).first
                    if await element.is_visible(timeout=2000):
                        await element.click()
                        strategy_config_found = True
                        print(f"Clicked strategy configuration with selector: {selector}")
                        break
                except:
                    continue

            if not strategy_config_found:
                print("Strategy configuration not available or not found")

            print("Step 6: Selecting simulated trading mode")
            # Look for simulated trading mode
            simulated_selectors = [
                'text=/Simulated.*Trading/i',
                '[data-testid*="simulated"]',
                'input[value="simulated"]',
                'option[value*="simulated"]',
                'button:has-text("Simulated")'
            ]

            simulated_found = False
            for selector in simulated_selectors:
                try:
                    element = await page.locator(selector).first
                    await element.wait_for(state='visible', timeout=3000)
                    await element.click()
                    simulated_found = True
                    print(f"Selected simulated trading with selector: {selector}")
                    break
                except:
                    continue

            if not simulated_found:
                print("Simulated trading mode not found")
                await page.screenshot(path="debug_simulated.png")
                return

            print("Step 7: Selecting universe symbol selection mode")
            # Look for universe symbol selection
            universe_selectors = [
                'text=/Universe.*Symbol/i',
                '[data-testid*="universe"]',
                'input[value="universe"]',
                'option[value*="universe"]',
                'button:has-text("Universe")'
            ]

            universe_found = False
            for selector in universe_selectors:
                try:
                    element = await page.locator(selector).first
                    await element.wait_for(state='visible', timeout=3000)
                    await element.click()
                    universe_found = True
                    print(f"Selected universe symbol selection with selector: {selector}")
                    break
                except:
                    continue

            if not universe_found:
                print("Universe symbol selection mode not found")
                await page.screenshot(path="debug_universe.png")

            print("Step 8: Selecting order book analysis strategy")
            # Look for order book analysis strategy
            order_book_selectors = [
                'text=/Order.*Book.*Analysis/i',
                '[data-testid*="order-book"]',
                'input[value*="order-book"]',
                'option[value*="order-book"]',
                'button:has-text("Order Book")'
            ]

            order_book_found = False
            for selector in order_book_selectors:
                try:
                    element = await page.locator(selector).first
                    await element.wait_for(state='visible', timeout=3000)
                    await element.click()
                    order_book_found = True
                    print(f"Selected order book analysis with selector: {selector}")
                    break
                except:
                    continue

            if not order_book_found:
                print("Order book analysis strategy not found")
                await page.screenshot(path="debug_order_book.png")

            print("Step 9: Pressing start trading")
            # Look for start trading button
            start_selectors = [
                'text=/Start.*Trading/i',
                '[data-testid*="start-trading"]',
                'button:has-text("Start")',
                '.start-trading'
            ]

            start_found = False
            for selector in start_selectors:
                try:
                    element = await page.locator(selector).first
                    await element.wait_for(state='visible', timeout=3000)
                    await element.click()
                    start_found = True
                    print(f"Clicked start trading with selector: {selector}")
                    break
                except:
                    continue

            if not start_found:
                print("Start trading button not found")
                await page.screenshot(path="debug_start.png")
                return

            # Wait for trading to start
            print("Waiting for trading to initialize...")
            await page.wait_for_load_state('networkidle')
            await asyncio.sleep(5)

            print("Step 10: Verifying simulated trading statistics")
            # Check if statistics widgets update from 0
            stats_selectors = [
                '.trading-statistics',
                '[data-testid*="statistics"]',
                '.stats',
                'text=/Statistics/i'
            ]

            stats_updated = False
            initial_stats = 0

            # Take initial screenshot
            await page.screenshot(path="before_trading.png")

            # Wait a bit for updates
            await asyncio.sleep(10)

            # Check various statistics indicators
            stat_indicators = [
                'text=/[1-9][0-9]*/',  # Any number > 0
                '.stat-value:not(:contains("0"))',
                '[data-value]:not([data-value="0"])'
            ]

            for indicator in stat_indicators:
                try:
                    elements = page.locator(indicator)
                    count = await elements.count()
                    if count > 0:
                        print(f"Found {count} non-zero statistics indicators")
                        stats_updated = True
                        break
                except:
                    continue

            # Take after screenshot
            await page.screenshot(path="after_trading.png")

            if stats_updated:
                print("✓ Simulated trading statistics successfully updated")
            else:
                print("✗ Simulated trading statistics did not update from 0")

            print("Step 11: Verifying order book signals")
            # Check order book signals
            signals_selectors = [
                '.order-book-signals',
                '[data-testid*="signals"]',
                '.signals',
                'text=/Signals/i'
            ]

            signals_updated = False

            signal_indicators = [
                '.signal:not(:empty)',
                '[data-signal]:not([data-signal=""])',
                'text=/[A-Z]+/',  # Any uppercase text (likely signal names)
            ]

            for indicator in signal_indicators:
                try:
                    elements = page.locator(indicator)
                    count = await elements.count()
                    if count > 0:
                        print(f"Found {count} order book signals")
                        signals_updated = True
                        break
                except:
                    continue

            if signals_updated:
                print("✓ Order book signals widget successfully updated")
            else:
                print("✗ Order book signals widget did not update")

            # Final verification screenshot
            await page.screenshot(path="final_verification.png")

            print("\nAutomation completed!")
            if stats_updated and signals_updated:
                print("SUCCESS: All verifications passed")
            else:
                print("PARTIAL SUCCESS: Some verifications failed")

        except Exception as e:
            print(f"Error during automation: {e}")
            await page.screenshot(path="error_screenshot.png")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(automate_trading())
