#!/usr/bin/env python3
"""
Test script to verify JWT generation for Coinbase API.
This will help us determine if the JWT generation is working correctly.
"""

import os
import logging
from dotenv import load_dotenv
from coinbase.jwt_generator import build_rest_jwt, format_jwt_uri

# Load environment variables from .env file
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_jwt_generation():
    """Test JWT generation for Coinbase API."""
    try:
        # Load credentials from .env file
        api_key = os.getenv('COINBASE_API_KEY')
        api_secret = os.getenv('COINBASE_API_SECRET')
        
        if not api_key or not api_secret:
            logger.error("Missing COINBASE_API_KEY or COINBASE_API_SECRET in environment")
            return False
        
        logger.info(f"API Key: {api_key}")
        logger.info(f"Private Key format: {'PEM' if api_secret.startswith('-----BEGIN') else 'Unknown'}")
        
        # Test JWT generation for accounts endpoint
        method = "GET"
        path = "/api/v3/brokerage/accounts"
        
        logger.info(f"Generating JWT for {method} {path}")
        
        # Format URI
        uri = format_jwt_uri(method, path)
        logger.info(f"Formatted URI: {uri}")
        
        # Generate JWT
        jwt_token = build_rest_jwt(uri, api_key, api_secret)
        logger.info(f"JWT Token generated successfully!")
        logger.info(f"Token length: {len(jwt_token)}")
        logger.info(f"Token preview: {jwt_token[:50]}...")
        
        return True
        
    except Exception as e:
        logger.error(f"JWT generation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_jwt_generation()
