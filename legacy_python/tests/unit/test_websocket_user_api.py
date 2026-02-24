#!/usr/bin/env python3
"""
Test script to verify Coinbase WebSocket User API authentication.
This will help us determine if the API credentials are working correctly.
"""

import os
import time
import logging
from dotenv import load_dotenv
from coinbase.websocket import WSUserClient, WSClientConnectionClosedException, WSClientException

# Load environment variables from .env file
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def on_message(msg):
    """Handle incoming WebSocket messages."""
    logger.info(f"Received message: {msg}")

def test_websocket_user_api():
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
        
        # Create WebSocket User API client with verbose logging
        client = WSUserClient(
            api_key=api_key,
            api_secret=api_secret,
            on_message=on_message,
            verbose=True
        )
        
        logger.info("Testing WebSocket User API authentication...")
        
        try:
            # Open the connection
            logger.info("Opening WebSocket connection...")
            client.open()
            
            # Subscribe to user channel (this requires authentication)
            # Note: User channel doesn't require product_ids, but the method signature does
            logger.info("Subscribing to user channel...")
            client.subscribe(product_ids=[], channels=["user"])
            
            # Wait for messages
            logger.info("Waiting for messages (10 seconds)...")
            client.sleep_with_exception_check(sleep=10)
            
            # Unsubscribe and close
            logger.info("Unsubscribing and closing connection...")
            client.unsubscribe(product_ids=[], channels=["user"])
            client.close()
            
            logger.info("WebSocket User API test completed successfully!")
            return True
            
        except WSClientConnectionClosedException as e:
            logger.error(f"Connection closed: {e}")
            return False
        except WSClientException as e:
            logger.error(f"WebSocket error: {e}")
            return False
        
    except Exception as e:
        logger.error(f"WebSocket User API test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_websocket_user_api()
