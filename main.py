#!/usr/bin/env python3
"""
Main entry point for the Trading Bot application.

This script provides a unified interface to run different components of the trading bot:
- Web Dashboard
- Backtesting
- Data Collection
- Live Trading

Usage:
    python main.py [command] [options]

Commands:
    web         Start the web dashboard
    backtest    Run backtesting
    data        Start data collection
    live        Start live trading
    help        Show this help message
"""

import sys
import os
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def run_web_dashboard():
    """Start the web dashboard server."""
    from scripts.web.web_dashboard import main
    main()

def run_backtest():
    """Run backtesting."""
    from scripts.backtest.backtest import main
    main()

def run_comprehensive_backtest():
    """Run comprehensive backtesting."""
    from scripts.backtest.backtest_comprehensive import main
    main()

def run_data_collection():
    """Start data collection."""
    print("Data collection not yet implemented")
    sys.exit(1)

def run_live_trading():
    """Start live trading."""
    print("Live trading not yet implemented")
    sys.exit(1)

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Trading Bot - Advanced Trading System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py web                    # Start web dashboard
    python main.py backtest              # Run basic backtest
    python main.py backtest --comprehensive  # Run comprehensive backtest
    python main.py data                  # Start data collection
    python main.py live                  # Start live trading
        """
    )
    
    parser.add_argument(
        'command',
        choices=['web', 'backtest', 'data', 'live', 'help'],
        help='Command to execute'
    )
    
    parser.add_argument(
        '--comprehensive',
        action='store_true',
        help='Run comprehensive backtest (only with backtest command)'
    )
    
    args = parser.parse_args()
    
    if args.command == 'help':
        parser.print_help()
        return
    
    try:
        if args.command == 'web':
            run_web_dashboard()
        elif args.command == 'backtest':
            if args.comprehensive:
                run_comprehensive_backtest()
            else:
                run_backtest()
        elif args.command == 'data':
            run_data_collection()
        elif args.command == 'live':
            run_live_trading()
    except KeyboardInterrupt:
        print("\nShutting down...")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()