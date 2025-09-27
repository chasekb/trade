#!/usr/bin/env python3
"""
Web Dashboard Server

Starts the FastAPI web server for the trading bot dashboard.
"""
"""Launch the trading dashboard web server."""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import uvicorn
from trade_bot.web.web_server_new import app

def main():
    """Launch the web server."""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    logger.info("🚀 Starting Trading Dashboard...")
    logger.info("📊 Dashboard will be available at: http://localhost:8001")
    logger.info("🔌 WebSocket endpoint: ws://localhost:8001/ws")
    logger.info("📈 API documentation: http://localhost:8001/docs")
    
    try:
        uvicorn.run(
            "trade_bot.web.web_server_new:app",
            host="0.0.0.0",
            port=8001,
            log_level="info",
            reload=True  # Enable auto-reload for development
        )
    except KeyboardInterrupt:
        logger.info("👋 Shutting down Trading Dashboard...")
    except Exception as e:
        logger.error(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
