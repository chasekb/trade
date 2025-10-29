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

    port = int(os.getenv("PORT", "8000"))
    logger.info("🚀 Starting Trading Dashboard...")
    logger.info(f"📊 Dashboard will be available at: http://localhost:{port}")
    logger.info(f"🔌 WebSocket endpoint: ws://localhost:{port}/ws")
    logger.info(f"📈 API documentation: http://localhost:{port}/docs")

    # Run the FastAPI application using import string for reload support
    try:
        port = int(os.getenv("PORT", "8000"))
        uvicorn.run(
            "src.trade_bot.web.web_server:app",
            host="0.0.0.0",
            port=port,
            log_level="info",
            reload=True
        )
    except Exception as e:
        logger.error(f"❌ Failed to start web dashboard: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
