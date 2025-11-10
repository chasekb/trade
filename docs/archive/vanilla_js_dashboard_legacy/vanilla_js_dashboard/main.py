#!/usr/bin/env python3
"""
Main entry point for the Trading Bot application.

This script provides a unified interface to run different components of the trading bot:
- Web Dashboard (with integrated ML services)
- Backtesting
- Data Collection
- Live Trading
- Vector Database Services (standalone)

Usage:
    python main.py [command] [options]

Commands:
    web         Start the web dashboard (with integrated ML services)
    backtest    Run backtesting
    data        Start data collection
    live        Start live trading
    vector-db   Start vector database services (standalone)
    help        Show this help message
"""

import sys
import os
import argparse
import asyncio
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def run_web_dashboard():
    """Start the web dashboard server."""
    import subprocess
    import sys

    def check_container_running(name):
        """Check if a podman container is running."""
        try:
            result = subprocess.run([
                "podman", "ps", "--filter", f"name={name}",
                "--format", "{{.Names}}"
            ], capture_output=True, text=True, timeout=10)
            return name in result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def start_container(image, name, ports):
        """Start a podman container."""
        port_args = []
        for host_port, container_port in ports:
            port_args.extend(["-p", f"{host_port}:{container_port}"])

        try:
            subprocess.run([
                "podman", "run", "-d", "--name", name,
                "--replace"  # Replace existing container if it exists
            ] + port_args + [image], check=True, timeout=60)
            print(f"✅ Started {name} container")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"❌ Failed to start {name} container: {e}", file=sys.stderr)
            return False
        return True

    print("🔍 Checking required services...")

    # Check and start Qdrant if needed
    if not check_container_running("qdrant"):
        print("📊 Starting Qdrant vector database...")
        if not start_container("qdrant/qdrant", "qdrant", [(6333, 6333), (6334, 6334)]):
            print("⚠️ Qdrant failed to start, but continuing...")
    else:
        print("✅ Qdrant is already running")

    # Check and start Redis if needed
    if not check_container_running("redis"):
        print("🗄️ Starting Redis cache service...")
        if not start_container("redis:latest", "redis", [(6379, 6379)]):
            print("⚠️ Redis failed to start, but continuing...")
    else:
        print("✅ Redis is already running")

    # Give services time to fully start
    import time
    print("⏳ Waiting for services to be ready...")
    time.sleep(3)

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

async def run_vector_database_services():
    """Start vector database services (Qdrant, Redis, ML Server)."""
    from src.trade_bot.ml.vector_database_service import get_vector_db_service
    
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("Starting vector database services...")
        
        service = get_vector_db_service()
        
        # Start services
        if await service.start_services():
            logger.info("✅ Vector database services started successfully")
            
            # Initialize vector database
            if await service.initialize_vector_database():
                logger.info("✅ Vector database initialized")
            else:
                logger.warning("⚠️ Failed to initialize vector database")
            
            # Print service URLs
            urls = service.get_service_urls()
            logger.info("Service URLs:")
            for name, url in urls.items():
                logger.info(f"  {name}: {url}")
            
            # Keep services running
            logger.info("Vector database services are running. Press Ctrl+C to stop.")
            
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                logger.info("Shutting down vector database services...")
                await service.stop_services()
                logger.info("Vector database services stopped")
        else:
            logger.error("❌ Failed to start vector database services")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Error running vector database services: {e}")
        sys.exit(1)

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Trading Bot - Advanced Trading System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py web                    # Start web dashboard with ML services
    python main.py backtest              # Run basic backtest
    python main.py backtest --comprehensive  # Run comprehensive backtest
    python main.py data                  # Start data collection
    python main.py live                  # Start live trading
    python main.py vector-db             # Start standalone vector database services
        """
    )
    
    parser.add_argument(
        'command',
        choices=['web', 'backtest', 'data', 'live', 'vector-db', 'help'],
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
        elif args.command == 'vector-db':
            asyncio.run(run_vector_database_services())
    except KeyboardInterrupt:
        print("\nShutting down...")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
