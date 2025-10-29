#!/usr/bin/env python3
"""
Docker entry point for the Trading Bot web application.

This is the production-ready entry point for containerized deployment,
optimized for Docker environments where external services (Qdrant, Redis, PostgreSQL)
are managed by docker-compose.

Usage:
    python app.py
"""

import os
import sys
import logging
import asyncio
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Configure logging for Docker
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)  # Ensure logs go to stdout for Docker
    ]
)

logger = logging.getLogger(__name__)

async def start_services():
    """Initialize and start all required services."""
    try:
        logger.info("🚀 Starting Trading Bot Web Application...")

        # Import and start web dashboard
        from scripts.web.web_dashboard import main

        # Log environment configuration
        logger.info("📋 Configuration:")
        logger.info(f"  ENV: {os.getenv('ENV', 'development')}")
        logger.info(f"  DATABASE_URL: {'*' * len(os.getenv('DATABASE_URL', 'NOT_SET'))}")
        logger.info(f"  REDIS_URL: {os.getenv('REDIS_URL', 'NOT_SET')}")
        logger.info(f"  QDRANT_URL: {os.getenv('QDRANT_URL', 'NOT_SET')}")

        # Start the web application
        logger.info("🌐 Starting web dashboard...")
        main()

    except Exception as e:
        logger.error(f"❌ Failed to start application: {e}")
        sys.exit(1)

def main():
    """Main entry point for Docker container."""
    try:
        logger.info("🐳 Trading Bot container starting...")

        # Set production environment if not specified
        if not os.getenv('ENV'):
            os.environ['ENV'] = 'production'

        # Run the async startup
        asyncio.run(start_services())

    except KeyboardInterrupt:
        logger.info("🛑 Received shutdown signal")
        sys.exit(0)
    except Exception as e:
        logger.error(f"💥 Critical error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
