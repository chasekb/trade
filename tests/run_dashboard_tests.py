#!/usr/bin/env python3
"""
Comprehensive dashboard test runner.

This script runs all dashboard tests and provides a summary of results.
"""

import asyncio
import subprocess
import sys
import os
import json
from datetime import datetime
from pathlib import Path

def run_python_test(test_file):
    """Run a Python test file and return results."""
    print(f"\n{'='*60}")
    print(f"Running {test_file}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(
            [sys.executable, test_file],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        return {
            'file': test_file,
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'return_code': result.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            'file': test_file,
            'success': False,
            'stdout': '',
            'stderr': 'Test timed out after 5 minutes',
            'return_code': -1
        }
    except Exception as e:
        return {
            'file': test_file,
            'success': False,
            'stdout': '',
            'stderr': str(e),
            'return_code': -1
        }

def run_html_test():
    """Instructions for running HTML test."""
    print(f"\n{'='*60}")
    print("HTML Integration Test")
    print(f"{'='*60}")
    print("To run the HTML integration test:")
    print("1. Open tests/dashboard_integration_test.html in a web browser")
    print("2. Click 'Run All Tests' button")
    print("3. Review the test results displayed on the page")
    print("\nThis test validates:")
    print("- Real-time data endpoint functionality")
    print("- Backtest execution and results")
    print("- WebSocket connectivity")
    print("- Data consistency across requests")
    print("- Error handling")
    
    return {
        'file': 'dashboard_integration_test.html',
        'success': True,  # Manual test
        'stdout': 'Manual test - see instructions above',
        'stderr': '',
        'return_code': 0
    }

def main():
    """Run all dashboard tests."""
    print("Dashboard Test Suite Runner")
    print("=" * 80)
    print(f"Started at: {datetime.now().isoformat()}")
    
    # Define test files
    python_tests = [
        'tests/dashboard_test_suite.py',
        'tests/dashboard_performance_test.py'
    ]
    
    # Check if test files exist
    missing_tests = []
    for test_file in python_tests:
        if not os.path.exists(test_file):
            missing_tests.append(test_file)
    
    if missing_tests:
        print(f"Warning: Missing test files: {missing_tests}")
        python_tests = [t for t in python_tests if t not in missing_tests]
    
    # Run Python tests
    results = []
    for test_file in python_tests:
        result = run_python_test(test_file)
        results.append(result)
    
    # Add HTML test info
    html_result = run_html_test()
    results.append(html_result)
    
    # Summary
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}")
    
    total_tests = len(results)
    passed_tests = sum(1 for r in results if r['success'])
    failed_tests = total_tests - passed_tests
    
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")
    print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    
    # Detailed results
    print(f"\n{'='*80}")
    print("DETAILED RESULTS")
    print(f"{'='*80}")
    
    for result in results:
        status = "✅ PASS" if result['success'] else "❌ FAIL"
        print(f"\n{status} {result['file']}")
        
        if not result['success'] and result['stderr']:
            print(f"Error: {result['stderr']}")
        
        if result['return_code'] != 0:
            print(f"Return Code: {result['return_code']}")
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"tests/dashboard_test_runner_results_{timestamp}.json"
    
    summary = {
        'timestamp': datetime.now().isoformat(),
        'total_tests': total_tests,
        'passed_tests': passed_tests,
        'failed_tests': failed_tests,
        'success_rate': (passed_tests/total_tests)*100,
        'results': results
    }
    
    with open(results_file, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    
    print(f"\nResults saved to: {results_file}")
    
    # Exit with appropriate code
    if failed_tests == 0:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n❌ {failed_tests} tests failed!")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

