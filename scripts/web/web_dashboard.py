#!/usr/bin/env python3
"""
Web Dashboard Script - Main entry point for the trading dashboard.

This script launches the FastAPI web server using uvicorn.
"""

import os
import sys
import logging

def main():
    """Start the trading dashboard web server."""
    # Import uvicorn
    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn not installed. Install with: uv add uvicorn")
        sys.exit(1)

    # Set up logging for dashboard startup
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger = logging.getLogger("scripts.web.web_dashboard")

    logger.info("🚀 Starting Trading Dashboard...")
    logger.info("📊 Dashboard will be available at: http://localhost:8001")
    logger.info("🔌 WebSocket endpoint: ws://localhost:8001/ws")
    logger.info("📈 API documentation: http://localhost:8001/docs")

    # Run the FastAPI application using import string for reload support
    try:
        uvicorn.run(
            "src.trade_bot.web.web_server:app",
            host="0.0.0.0",
            port=8001,
            log_level="info",
            reload=True
        )
    except Exception as e:
        logger.error(f"❌ Failed to start web dashboard: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
