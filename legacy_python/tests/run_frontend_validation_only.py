#!/usr/bin/env python3
"""
Quick runner for frontend validation tests only.

This script runs only the enhanced frontend validation tests
to check if the live trading tab is displaying data correctly.
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

async def main():
    """Run frontend validation tests only."""
    logger.info("🎯 Frontend Validation Tests Only")
    logger.info("=" * 50)
    
    start_time = datetime.now()
    
    try:
        # Import and run the frontend validation tests
        from test_live_trading_frontend_validation import LiveTradingFrontendValidationTest
        
        test_suite = LiveTradingFrontendValidationTest(headless=True)
        success = await test_suite.run_all_tests()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info("=" * 50)
        if success:
            logger.info(f"🎉 Frontend validation tests PASSED in {duration:.1f}s")
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
