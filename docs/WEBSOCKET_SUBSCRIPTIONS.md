# 🔌 WebSocket Subscriptions - Complete Guide

## 📊 Available Subscription Channels

The enhanced trading bot now supports **ALL** available Coinbase Advanced Trading API WebSocket subscription channels:

### 🎯 Public Channels (No Authentication Required)

| Channel | Description | Data Type | Use Case |
|---------|-------------|-----------|----------|
| **ticker** | Real-time price and volume updates | Price, Volume, 24h Change | Live price monitoring, basic analytics |
| **level2** | Order book depth updates | Bid/Ask changes, Order book | Market depth analysis, order flow |
| **candles** | OHLCV candlestick data | Open, High, Low, Close, Volume | Technical analysis, charting |
| **matches** | Trade execution matches | Trade details, Price, Size | Trade analysis, execution monitoring |
| **status** | Product status updates | Trading status, Maintenance | System health, trading availability |
| **market_trades** | Market trades feed | Public trade data | Market activity, volume analysis |

### 🔐 Private Channels (Authentication Required)

| Channel | Description | Data Type | Use Case |
|---------|-------------|-----------|----------|
| **user** | User account updates | Account changes, Orders | Portfolio management, order tracking |

## 🚀 How to Use Subscriptions

### 1. Web Dashboard Interface

The enhanced dashboard provides a user-friendly interface for managing subscriptions:

- **Channel Selection**: Choose from dropdown menu
- **Product ID**: Specify trading pair (e.g., BTC-USD, ETH-USD)
- **Subscribe/Unsubscribe**: One-click subscription management
- **Real-time Status**: See active subscriptions at a glance

### 2. API Endpoints

#### Get Available Channels
```bash
GET /api/available-channels
```

Response:
```json
{
  "channels": {
    "ticker": "Ticker updates for price and volume",
    "level2": "Level 2 order book updates",
    "candles": "Candlestick/OHLCV data",
    "matches": "Trade execution matches",
    "status": "Product status updates",
    "user": "User account updates (requires authentication)",
    "market_trades": "Market trades feed"
  }
}
```

#### Subscribe to Channel
```bash
POST /api/subscribe
Content-Type: application/json

{
  "channel": "ticker",
  "product_id": "BTC-USD"
}
```

#### Unsubscribe from Channel
```bash
POST /api/unsubscribe
Content-Type: application/json

{
  "channel": "ticker",
  "product_id": "BTC-USD"
}
```

#### Get Current Subscriptions
```bash
GET /api/subscriptions
```

Response:
```json
{
  "channels": {
    "ticker": ["BTC-USD", "ETH-USD"],
    "level2": ["BTC-USD"],
    "candles": ["BTC-USD"]
  },
  "available_channels": {...},
  "authenticated": false,
  "connected": true
}
```

### 3. Programmatic Usage

#### Python Code Example
```python
from src.trade_bot.websocket_client import WebSocketClient
from src.trade_bot.config import TradingConfig

# Initialize client
config = TradingConfig.from_env()
client = WebSocketClient(config)

# Connect
await client.connect()

# Subscribe to specific channels
await client.subscribe_to_ticker("BTC-USD")
await client.subscribe_to_level2("BTC-USD")
await client.subscribe_to_candles("BTC-USD")
await client.subscribe_to_matches("BTC-USD")
await client.subscribe_to_status("BTC-USD")
await client.subscribe_to_market_trades("BTC-USD")

# Or subscribe to all available channels
await client.subscribe_to_all_channels("BTC-USD")

# Get subscription info
info = await client.get_subscription_info()
print(f"Active subscriptions: {info['channels']}")

# Unsubscribe from specific channel
await client.unsubscribe_from_channel("ticker", ["BTC-USD"])
```

## 📈 Data Types and Storage

### Data Handler Support

The enhanced `DataHandler` class supports all subscription types:

```python
# Add data for each type
data_handler.add_ticker_data(ticker_data)
data_handler.add_level2_data(level2_data)
data_handler.add_candles_data(candles_data)
data_handler.add_matches_data(matches_data)
data_handler.add_status_data(status_data)
data_handler.add_market_trades_data(market_trades_data)

# Get latest data
latest_ticker = data_handler.get_latest_ticker()
latest_level2 = data_handler.get_latest_level2()
latest_candles = data_handler.get_latest_candles()
latest_matches = data_handler.get_latest_matches()
latest_status = data_handler.get_latest_status()
latest_market_trades = data_handler.get_latest_market_trades()

# Save all data to CSV
files = data_handler.save_all_data()
# Returns: {
#   'ticker': 'ticker_data_20250913_104140.csv',
#   'level2': 'level2_data_20250913_104140.csv',
#   'candles': 'candles_data_20250913_104140.csv',
#   'matches': 'matches_data_20250913_104140.csv',
#   'status': 'status_data_20250913_104140.csv',
#   'market_trades': 'market_trades_data_20250913_104140.csv'
# }
```

### CSV Export Format

Each data type is exported to its own CSV file with relevant fields:

#### Ticker Data
- timestamp, product_id, price, volume_24h, volume_30d
- best_bid, best_ask, side, time, trade_id, last_size

#### Level2 Data
- timestamp, product_id, time, changes, sequence

#### Candles Data
- timestamp, product_id, time, candles, granularity

#### Matches Data
- timestamp, product_id, time, matches, sequence

#### Status Data
- timestamp, product_id, time, status, message

#### Market Trades Data
- timestamp, product_id, time, trades, sequence

## 🔄 Real-time Data Flow

### WebSocket Message Handling

The web server automatically handles all subscription types:

```python
# Message handlers are registered for each type
websocket_client.register_handler('ticker', handle_ticker_message)
websocket_client.register_handler('l2update', handle_l2update_message)
websocket_client.register_handler('candles', handle_candles_message)
websocket_client.register_handler('matches', handle_matches_message)
websocket_client.register_handler('status', handle_status_message)
websocket_client.register_handler('market_trades', handle_market_trades_message)
```

### Data Broadcasting

All collected data is broadcast to connected WebSocket clients:

```json
{
  "type": "real_time_data",
  "data": {
    "ticker": {...},
    "trades": [...],
    "level2": {...},
    "candles": {...},
    "matches": {...},
    "status": {...},
    "market_trades": {...},
    "timestamp": "2025-09-13T10:49:02.780125"
  }
}
```

## 📊 Dashboard Features

### Enhanced Dashboard Components

1. **Subscription Management Panel**
   - Channel selection dropdown
   - Product ID input
   - Subscribe/Unsubscribe buttons
   - Real-time subscription status

2. **Data Summary Cards**
   - Live count of each data type
   - Visual indicators with icons
   - Color-coded by data type

3. **Real-time Data Feed**
   - Live stream of all incoming data
   - Timestamped entries
   - Scrollable history

4. **Interactive Charts**
   - Price charts with real-time updates
   - Volume charts
   - Multiple data overlays

## 🛠️ Configuration

### Environment Variables

```env
# WebSocket URL (usually don't need to change)
COINBASE_WEBSOCKET_URL=wss://advanced-trade-ws.coinbase.com

# Product ID for default subscriptions
TRADING_PRODUCT_ID=BTC-USD

# Output directory for data files
OUTPUT_DIR=outputs
```

### Default Behavior

- **Auto-subscribe**: All available channels are automatically subscribed on startup
- **Data Storage**: All data is stored in memory and can be exported to CSV
- **Real-time Updates**: Data is broadcast to all connected dashboard clients
- **Error Handling**: Failed subscriptions are logged but don't stop the system

## 🚨 Error Handling

### Common Issues

1. **Authentication Required**: User channels require JWT authentication
2. **Invalid Channel**: Unknown channels are rejected with error message
3. **Connection Lost**: Automatic reconnection with exponential backoff
4. **Rate Limiting**: Coinbase may limit subscription frequency

### Error Responses

```json
{
  "error": "Unknown channel: invalid_channel. Available: ['ticker', 'level2', ...]"
}
```

```json
{
  "error": "WebSocket client not initialized"
}
```

## 🎯 Best Practices

### 1. Subscription Management
- Only subscribe to channels you need
- Unsubscribe from unused channels to reduce bandwidth
- Monitor subscription status regularly

### 2. Data Storage
- Export data regularly to prevent memory issues
- Use appropriate data retention policies
- Monitor disk space for CSV exports

### 3. Performance
- Limit the number of concurrent subscriptions
- Use appropriate update intervals
- Monitor WebSocket connection health

### 4. Error Handling
- Implement proper error handling for all subscription operations
- Log subscription changes for debugging
- Handle connection failures gracefully

## 🔍 Monitoring and Debugging

### Health Check Endpoint
```bash
GET /api/health
```

Returns comprehensive system status including:
- WebSocket connection status
- Active subscription count
- Data handler status
- Cached data points

### Data Summary Endpoint
```bash
GET /api/data-summary
```

Returns counts of all collected data types for monitoring.

## 🎉 Summary

The enhanced WebSocket subscription system provides:

- ✅ **Complete Coverage**: All available Coinbase WebSocket channels
- ✅ **Easy Management**: Web dashboard and API endpoints
- ✅ **Data Storage**: CSV export for all data types
- ✅ **Real-time Updates**: Live data streaming to dashboard
- ✅ **Error Handling**: Robust error management
- ✅ **Monitoring**: Health checks and data summaries

Your trading bot now has access to the full spectrum of real-time market data! 🚀📊💰
