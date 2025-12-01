# API Reference

Complete API endpoint reference for the Trading Bot system.

## Base URLs

- **Backend API**: `http://localhost:8000`
- **Frontend**: `http://localhost:3000`
- **ML Server**: Integrated into backend at `/api/ml/*`

## ML Endpoints

### Training

#### Train ML Models
```http
POST /api/ml/train
Content-Type: application/json

{
  "days_back": 30,
  "batch_training": true,
  "batch_size": 1000
}
```

**Parameters:**
- `days_back` (integer, optional): Number of days of historical data to use (default: 30)
- `batch_training` (boolean, optional): Enable batch training mode for memory efficiency (default: false)
- `batch_size` (integer, optional): Number of samples per batch when batch training is enabled (default: 1000)

**Response:**
```json
{
  "status": "training_started",
  "message": "Model training initiated",
  "job_id": "train_20241201_112900"
}
```

### Model Management

#### List Available Models
```http
GET /api/ml/models
```

**Response:**
```json
{
  "models": [
    {
      "name": "trading_optimizer_v20241201_112900",
      "version": "v20241201_112900",
      "training_date": "2024-12-01T11:29:00Z",
      "performance": {
        "r2_score": 0.85,
        "rmse": 0.12,
        "sharpe_ratio": 1.8
      },
      "is_active": true
    }
  ]
}
```

#### Set Active Model
```http
POST /api/ml/models/set_active
Content-Type: application/json

{
  "model_name": "trading_optimizer_v20241201_112900"
}
```

**Response:**
```json
{
  "status": "success",
  "active_model": "trading_optimizer_v20241201_112900"
}
```

#### Rollback Model
```http
POST /api/ml/rollback
```

**Response:**
```json
{
  "status": "success",
  "message": "Rolled back to previous model",
  "active_model": "trading_optimizer_v20241130_103000"
}
```

### Model Performance

#### Get ML System Status
```http
GET /api/ml/status
```

**Response:**
```json
{
  "status": "ready",
  "model_loaded": true,
  "active_model": "trading_optimizer_v20241201_112900",
  "vector_db_connected": true,
  "last_training": "2024-12-01T11:29:00Z"
}
```

#### Get Model Performance
```http
GET /api/ml/performance
```

**Response:**
```json
{
  "r2_score": 0.85,
  "rmse": 0.12,
  "mae": 0.08,
  "profit_factor": 1.6,
  "sharpe_ratio": 1.8,
  "win_rate": 0.62
}
```

#### Get Feature Importance
```http
GET /api/ml/features/importance
```

**Response:**
```json
{
  "features": [
    {"name": "bid_ask_imbalance", "importance": 0.25},
    {"name": "spread_percent", "importance": 0.18},
    {"name": "volume_ratio", "importance": 0.15}
  ]
}
```

### Prediction

#### Predict Trading Signal
```http
POST /api/ml/predict
Content-Type: application/json

{
  "symbol": "BTC-USD",
  "bid_ask_imbalance": 1.23,
  "spread_percent": 0.05,
  "mid_price": 45000.0,
  "bid_volume": 1500.0,
  "ask_volume": 1200.0
}
```

**Response:**
```json
{
  "action": "buy",
  "confidence": 0.78,
  "signal_value": 0.65,
  "win_probability": 0.72,
  "expected_return": 0.015,
  "reason": "ML prediction: 0.650",
  "timestamp": "2024-12-01T11:30:00Z"
}
```

#### Compare Model Predictions
```http
POST /api/ml/prediction-comparison
Content-Type: application/json

{
  "model1": "trading_optimizer_v20241201_112900",
  "model2": "trading_optimizer_v20241130_103000",
  "features": {
    "symbol": "BTC-USD",
    "bid_ask_imbalance": 1.23,
    "spread_percent": 0.05
  }
}
```

**Response:**
```json
{
  "model1": {
    "name": "trading_optimizer_v20241201_112900",
    "expected_return": 0.015,
    "win_probability": 0.72,
    "confidence": 0.78
  },
  "model2": {
    "name": "trading_optimizer_v20241130_103000",
    "expected_return": 0.012,
    "win_probability": 0.68,
    "confidence": 0.71
  }
}
```

### PnL Tracking

#### Get Top/Bottom PnL Trades
```http
GET /api/ml/pnl-trades?limit=10&sort_by=pnl
```

**Parameters:**
- `limit` (integer, optional): Number of trades to return (default: 10)
- `sort_by` (string, optional): Sort field - `pnl`, `fees`, or `duration` (default: pnl)

**Response:**
```json
{
  "top_trades": [
    {
      "trade_id": "trade_123",
      "symbol": "BTC-USD",
      "pnl": 150.50,
      "fees": 2.25,
      "duration_seconds": 3600
    }
  ],
  "bottom_trades": [
    {
      "trade_id": "trade_456",
      "symbol": "ETH-USD",
      "pnl": -45.30,
      "fees": 1.80,
      "duration_seconds": 1800
    }
  ]
}
```

## Simulated Trading Endpoints

### Session Management

#### Start Simulated Trading
```http
POST /api/simulated-trading/start
Content-Type: application/json

{
  "strategy": "ml_enhanced_orderbook",
  "symbols": ["BTC-USD", "ETH-USD"],
  "capital": 10000,
  "position_size": 0.1,
  "stop_loss": 0.02,
  "take_profit": 0.03,
  "order_prioritization": "signal_strength"
}
```

**Parameters:**
- `strategy` (string): Strategy type (e.g., "ml_enhanced_orderbook", "rsi", "macd")
- `symbols` (array): List of trading symbols
- `capital` (number): Initial capital
- `position_size` (number): Position size as fraction of capital
- `stop_loss` (number, optional): Stop loss percentage
- `take_profit` (number, optional): Take profit percentage
- `order_prioritization` (string, optional): Order execution priority - `signal_strength`, `win_probability`, or `expected_return` (default: signal_strength)

**Response:**
```json
{
  "status": "success",
  "session_id": "sim_20241201_112900",
  "message": "Simulated trading started"
}
```

#### Stop Simulated Trading
```http
POST /api/simulated-trading/stop
Content-Type: application/json

{
  "session_id": "sim_20241201_112900"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Simulated trading stopped",
  "final_pnl": 250.75
}
```

#### Update Strategy Parameters
```http
POST /api/simulated-trading/update-strategy
Content-Type: application/json

{
  "session_id": "sim_20241201_112900",
  "position_size": 0.15,
  "order_prioritization": "win_probability"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Strategy parameters updated"
}
```

### Status and Signals

#### Get Simulated Trading Status
```http
GET /api/simulated-trading/status?session_id=sim_20241201_112900
```

**Response:**
```json
{
  "session_id": "sim_20241201_112900",
  "status": "active",
  "strategy": "ml_enhanced_orderbook",
  "symbols": ["BTC-USD", "ETH-USD"],
  "current_capital": 10250.75,
  "total_pnl": 250.75,
  "open_positions": 2,
  "total_trades": 15
}
```

#### Get Order Book Signals
```http
GET /api/simulated-trading/signals?session_id=sim_20241201_112900&symbols=BTC-USD,ETH-USD
```

**Response:**
```json
{
  "signals": [
    {
      "symbol": "BTC-USD",
      "signal_type": "buy",
      "strength": 0.78,
      "win_probability": 0.72,
      "expected_return": 0.015,
      "confidence": 0.78,
      "timestamp": "2024-12-01T11:30:00Z"
    }
  ]
}
```

## Live Trading Endpoints

Live trading endpoints follow the same structure as simulated trading endpoints, with the `/api/live-trading/*` prefix:

- `POST /api/live-trading/start` - Start live trading session
- `POST /api/live-trading/stop` - Stop live trading session
- `POST /api/live-trading/update-strategy` - Update strategy parameters
- `GET /api/live-trading/status` - Get live trading status
- `GET /api/live-trading/signals` - Get order book signals

> [!CAUTION]
> Live trading uses real capital. Ensure proper risk management and testing before deployment.

## WebSocket Endpoints

### Real-time Data Subscription

**Connection URL:** `ws://localhost:8000/ws`

**Subscribe to Market Data:**
```json
{
  "action": "subscribe",
  "channel": "ticker",
  "product_id": "BTC-USD"
}
```

**Available Channels:**
- `ticker` - Price and volume updates
- `level2` - Order book depth
- `candles` - OHLCV candlestick data
- `matches` - Trade executions
- `status` - Product status
- `market_trades` - Market trades feed

**Unsubscribe:**
```json
{
  "action": "unsubscribe",
  "channel": "ticker",
  "product_id": "BTC-USD"
}
```

**Data Broadcast:**
```json
{
  "type": "real_time_data",
  "data": {
    "ticker": {
      "product_id": "BTC-USD",
      "price": 45000.50,
      "volume_24h": 1234.56
    },
    "timestamp": "2024-12-01T11:30:00Z"
  }
}
```

## Error Responses

All endpoints may return error responses in the following format:

```json
{
  "status": "error",
  "error": "Error message describing what went wrong",
  "code": "ERROR_CODE"
}
```

**Common Error Codes:**
- `INVALID_PARAMETERS` - Request parameters are invalid
- `MODEL_NOT_FOUND` - Requested model does not exist
- `TRAINING_IN_PROGRESS` - Cannot perform operation while training
- `INSUFFICIENT_DATA` - Not enough data for requested operation
- `SERVICE_UNAVAILABLE` - ML service or database unavailable

## Rate Limiting

Currently, there are no rate limits enforced. For production deployment, implement appropriate rate limiting based on your infrastructure.

## Authentication

> [!NOTE]
> Authentication is required for live trading endpoints. See [SECURITY_SETUP.md](SECURITY_SETUP.md) for details on API credential configuration.

For local development and simulated trading, no authentication is required.
