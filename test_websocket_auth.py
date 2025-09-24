#!/usr/bin/env python3
"""
Test script to verify Coinbase WebSocket User API authentication.
This will help us determine if the API credentials are working correctly.
"""

import os
import asyncio
import logging
from dotenv import load_dotenv
from coinbase.websocket import WSUserClient

# Load environment variables from .env file
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def on_message(msg):
    """Handle incoming WebSocket messages."""
    logger.info(f"Received message: {msg}")

def on_error(error):
    """Handle WebSocket errors."""
    logger.error(f"WebSocket error: {error}")

def on_close():
    """Handle WebSocket close."""
    logger.info("WebSocket connection closed")

async def test_websocket_auth():
    """Test WebSocket User API authentication."""
    try:
        # Load credentials from .env file
        api_key = os.getenv('COINBASE_API_KEY')
        api_secret = os.getenv('COINBASE_API_SECRET')
        
        if not api_key or not api_secret:
            logger.error("Missing COINBASE_API_KEY or COINBASE_API_SECRET in environment")
            return False
        
        logger.info(f"API Key: {api_key}")
        logger.info(f"Private Key format: {'PEM' if api_secret.startswith('-----BEGIN') else 'Unknown'}")
        
        # Create WebSocket User API client
        client = WSUserClient(
            api_key=api_key,
            api_secret=api_secret,
            on_message=on_message
        )
        
        logger.info("Connecting to Coinbase WebSocket User API...")
        
        # Start the WebSocket client
        client.start()
        
        # Wait for a few seconds to receive messages
        logger.info("Waiting for messages...")
        await asyncio.sleep(5)
        
        # Close connection
        client.close()
        
        logger.info("WebSocket test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"WebSocket authentication test failed: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_websocket_auth())
