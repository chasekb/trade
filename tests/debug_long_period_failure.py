#!/usr/bin/env python3
"""
Debug script to investigate why OrderBookStrategy fails for longer time periods.
"""

import asyncio
import aiohttp
import json
import traceback

async def debug_long_period_failure():
    """Debug a specific long period failure."""
    print("🔍 Debugging OrderBookStrategy long period failure...")
    
    # Test a failing case: 60 days, 1h granularity
    payload = {
        "strategy_type": "orderbook",
        "product_id": "BTC-USD",
        "days": 60,
        "granularity": 3600,  # 1h
        "strategy_params": {
            "order_book_level": 2,
            "trade_history_limit": 100,
            "bid_ask_spread_threshold": 0.001,
            "volume_imbalance_threshold": 0.6,
            "large_trade_threshold": 10000.0
        }
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            print(f"Testing: {payload['days']} days, {payload['granularity']}s granularity")
            print(f"Payload: {json.dumps(payload, indent=2)}")
            print()
            
            async with session.post("http://localhost:8000/api/run-backtest", 
                                  json=payload) as response:
                print(f"Response Status: {response.status}")
                print(f"Response Headers: {dict(response.headers)}")
                print()
                
                if response.status == 200:
                    data = await response.json()
                    print("✅ Success!")
                    print(f"Result: {json.dumps(data, indent=2)}")
                else:
                    error_text = await response.text()
                    print("❌ Error Response:")
                    print(f"Status: {response.status}")
                    print(f"Error: {error_text}")
                    
                    # Try to parse as JSON for more details
                    try:
                        error_data = json.loads(error_text)
                        print(f"Parsed Error: {json.dumps(error_data, indent=2)}")
                    except:
                        print("Could not parse error as JSON")
                        
    except Exception as e:
        print(f"❌ Exception occurred:")
        print(f"Type: {type(e).__name__}")
        print(f"Message: {str(e)}")
        print(f"Traceback:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_long_period_failure())
