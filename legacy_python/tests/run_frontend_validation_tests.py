#!/usr/bin/env python3
"""
Frontend validation test runner for live trading tab.

This script runs comprehensive frontend validation tests to ensure
the live trading tab is correctly displaying data from the backend.
"""

import asyncio
import sys
import os
import logging
from datetime import datetime

# Add the src directory to the path
sys.path.insert(0, 'src')

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def check_server_status(base_url: str = "http://localhost:8001") -> bool:
    """Check if the server is running."""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{base_url}/api/health", timeout=5) as response:
                return response.status == 200
    except Exception as e:
        logger.error(f"Server check failed: {e}")
        return False

async def run_frontend_validation_tests():
    """Run the frontend validation tests."""
    logger.info("🚀 Starting frontend validation tests...")
    
    # Check server status
    if not await check_server_status():
        logger.error("❌ Server is not running. Please start the server first.")
        return False
    
    logger.info("✅ Server is running")
    
    # Import and run the frontend validation tests
    try:
        from test_live_trading_frontend_validation import LiveTradingFrontendValidationTest
        
        test_suite = LiveTradingFrontendValidationTest(headless=True)
        success = await test_suite.run_all_tests()
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Failed to run frontend validation tests: {e}")
        return False

async def main():
    """Main test runner."""
    logger.info("🎯 Live Trading Frontend Validation Test Suite")
    logger.info("=" * 60)
    
    start_time = datetime.now()
    
    try:
        success = await run_frontend_validation_tests()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info("=" * 60)
        if success:
            logger.info(f"🎉 Frontend validation tests COMPLETED SUCCESSFULLY in {duration:.1f}s")
            return 0
        else:
            logger.error(f"💥 Frontend validation tests FAILED after {duration:.1f}s")
            return 1
            
    except KeyboardInterrupt:
        logger.info("⏹️ Tests interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
