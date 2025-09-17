#!/usr/bin/env python3
"""
Test runner for SimulatedTradingManager tests.

This script runs all tests for the simulated trading manager and provides
detailed output about test results.
"""

import sys
import os
import pytest
from pathlib import Path

# Add the src directory to the path
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

def main():
    """Run the simulated trading manager tests."""
    print("🧪 Running SimulatedTradingManager Tests")
    print("=" * 50)
    
    # Get the test file path
    test_file = Path(__file__).parent / 'test_simulated_trading_manager.py'
    
    # Run pytest with verbose output
    args = [
        str(test_file),
        '-v',  # Verbose output
        '--tb=short',  # Short traceback format
        '--color=yes',  # Colored output
        '--durations=10'  # Show 10 slowest tests
    ]
    
    # Run the tests
    exit_code = pytest.main(args)
    
    if exit_code == 0:
        print("\n✅ All tests passed!")
    else:
        print(f"\n❌ {exit_code} test(s) failed!")
    
    return exit_code

if __name__ == '__main__':
    sys.exit(main())
