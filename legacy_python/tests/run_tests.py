#!/usr/bin/env python3
"""
Test runner script for the trading dashboard test suite.
This script provides a convenient way to run different categories of tests.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

def run_command(command, description):
    """Run a command and handle errors."""
    print(f"\n🔄 {description}")
    print(f"Command: {command}")
    print("-" * 50)
    
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running command: {e}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        return False

def run_python_tests(test_path, description):
    """Run Python tests using pytest."""
    command = f"python -m pytest {test_path} -v --tb=short"
    return run_command(command, description)

def run_fallback_tests():
    """Run fallback mechanism tests."""
    print("\n🧪 Running Fallback Mechanism Tests")
    print("=" * 50)
    
    # Run Python fallback tests
    success1 = run_python_tests("tests/fallback_tests/test_fallback_server.py", "Python Fallback Tests")
    
    # Run JavaScript tests (informational)
    print("\n📝 JavaScript Tests")
    print("To run JavaScript tests, open the following files in your browser:")
    print("- tests/fallback_tests/test_fallback_mechanism.html")
    print("- tests/fallback_tests/test_price_data_fallback.js")
    
    return success1

def run_unit_tests():
    """Run unit tests."""
    print("\n⚙️ Running Unit Tests")
    print("=" * 50)
    
    return run_python_tests("tests/unit_tests/", "Unit Tests")

def run_integration_tests():
    """Run integration tests."""
    print("\n🔗 Running Integration Tests")
    print("=" * 50)
    
    return run_python_tests("tests/integration_tests/", "Integration Tests")

def run_all_tests():
    """Run all tests."""
    print("\n🚀 Running All Tests")
    print("=" * 50)
    
    results = []
    
    # Run unit tests
    results.append(run_unit_tests())
    
    # Run integration tests
    results.append(run_integration_tests())
    
    # Run fallback tests
    results.append(run_fallback_tests())
    
    return all(results)

def show_test_structure():
    """Show the test directory structure."""
    print("\n📁 Test Directory Structure")
    print("=" * 50)
    
    def print_tree(directory, prefix="", max_depth=3, current_depth=0):
        if current_depth >= max_depth:
            return
            
        try:
            items = sorted(Path(directory).iterdir())
            for i, item in enumerate(items):
                is_last = i == len(items) - 1
                current_prefix = "└── " if is_last else "├── "
                print(f"{prefix}{current_prefix}{item.name}")
                
                if item.is_dir() and current_depth < max_depth - 1:
                    next_prefix = prefix + ("    " if is_last else "│   ")
                    print_tree(item, next_prefix, max_depth, current_depth + 1)
        except PermissionError:
            print(f"{prefix}└── [Permission Denied]")
    
    print_tree("tests/")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Trading Dashboard Test Runner")
    parser.add_argument("--type", choices=["unit", "integration", "fallback", "all"], 
                       default="all", help="Type of tests to run")
    parser.add_argument("--structure", action="store_true", 
                       help="Show test directory structure")
    parser.add_argument("--coverage", action="store_true", 
                       help="Run tests with coverage report")
    
    args = parser.parse_args()
    
    print("🧪 Trading Dashboard Test Runner")
    print("=" * 50)
    
    if args.structure:
        show_test_structure()
        return
    
    # Change to project root directory
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    success = False
    
    if args.type == "unit":
        success = run_unit_tests()
    elif args.type == "integration":
        success = run_integration_tests()
    elif args.type == "fallback":
        success = run_fallback_tests()
    elif args.type == "all":
        success = run_all_tests()
    
    # Show summary
    print("\n📊 Test Summary")
    print("=" * 50)
    if success:
        print("✅ All tests completed successfully!")
    else:
        print("❌ Some tests failed. Check the output above for details.")
        sys.exit(1)
    
    if args.coverage:
        print("\n📈 Running Coverage Report")
        print("=" * 50)
        run_command("python -m pytest --cov=src --cov-report=html --cov-report=term", 
                   "Coverage Report")

if __name__ == "__main__":
    main()

