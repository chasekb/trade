# 📊 Advanced Trading Bot - Project Overview

## 🎯 Project Summary

This is a comprehensive Python trading bot built with `coinbase-advanced-py` that provides:

- **Real-time Trading** with WebSocket integration
- **Advanced Backtesting** with historical data analysis
- **Modern Web Dashboard** with interactive charts
- **Risk Management** with stop-loss and take-profit
- **Performance Analytics** with detailed metrics
- **Session-Based Trading** with isolated trading history per session
- **Simulated Trading** with live portfolio management
- **Trade Classification** with simulated vs live trade tracking

## 🏗️ Architecture

### Core Components

1. **Trading Bot** (`src/trade_bot/trading_bot.py`)
   - Main trading logic and execution
   - WebSocket integration for real-time data
   - Risk management and position sizing

2. **Trading Strategy** (`src/trade_bot/trading_strategy.py`)
   - Simple Moving Average (SMA) strategy
   - Golden Cross / Death Cross signals
   - Configurable parameters

3. **Data Handler** (`src/trade_bot/data_handler.py`)
   - Data storage and management
   - CSV export functionality
   - Real-time data processing

4. **Backtester** (`src/trade_bot/backtester.py`)
   - Historical data backtesting
   - Performance metrics calculation
   - Strategy optimization

5. **Web Server** (`src/trade_bot/web_server.py`)
   - FastAPI-based web dashboard
   - Real-time data streaming
   - RESTful API endpoints

6. **Data Provider** (`src/trade_bot/data_provider.py`)
   - Historical data fetching from Coinbase
   - Data processing and formatting
   - Mock data for testing

## 📁 Directory Structure

```
trade/
├── src/trade_bot/           # Core modules
│   ├── __init__.py
│   ├── config.py            # Configuration management
│   ├── trading_bot.py       # Main trading bot
│   ├── trading_strategy.py  # Trading strategies
│   ├── websocket_client.py  # WebSocket client
│   ├── data_handler.py      # Data storage
│   ├── data_provider.py     # Historical data
│   ├── backtester.py        # Backtesting engine
│   └── web_server.py        # Web dashboard
├── scripts/                 # Executable scripts
│   ├── web_dashboard.py     # Web dashboard launcher
│   ├── backtest.py          # Simple backtesting
│   └── backtest_comprehensive.py  # Advanced backtesting
├── examples/                # Example usage
│   ├── test_trading_bot.py
│   ├── test_websocket.py
│   └── test_public_*.py
├── tests/                   # Test suite
│   ├── test_backtester.py
│   ├── test_data_provider.py
│   └── test_*.py
├── templates/               # Web templates
│   └── dashboard.html
├── static/                  # Web assets
│   └── js/dashboard.js
├── docs/                    # Documentation
├── outputs/                 # Generated data
├── main.py                  # Main entry point
├── pyproject.toml          # Project config
└── requirements.txt        # Dependencies
```

## 🔧 Configuration

### Environment Variables

```env
# Coinbase API Credentials
COINBASE_API_KEY=your_api_key
COINBASE_API_SECRET=your_api_secret
COINBASE_PASSPHRASE=your_passphrase

# Trading Configuration
TRADING_PRODUCT_ID=BTC-USD
MAX_POSITION_SIZE=1000.0
STOP_LOSS_PERCENTAGE=0.02
TAKE_PROFIT_PERCENTAGE=0.04
TRADING_FEE_PERCENTAGE=0.001

# Output Configuration
OUTPUT_DIR=outputs
LOG_LEVEL=INFO
```

### Trading Strategy Parameters

- **Short Window**: Short moving average period (default: 5)
- **Long Window**: Long moving average period (default: 20)
- **Stop Loss**: Percentage for stop loss (default: 2%)
- **Take Profit**: Percentage for take profit (default: 4%)

## 🚀 Usage Examples

### 1. Basic Trading Bot

```bash
# Run with default settings
uv run python main.py

# Run with custom parameters
uv run python main.py --product ETH-USD --max-position 2000
```

### 2. Web Dashboard

```bash
# Start web dashboard
uv run python scripts/web_dashboard.py

# Access at http://localhost:8001
```

### 3. Backtesting

```bash
# Simple backtest
uv run python scripts/backtest.py

# Comprehensive backtest
uv run python scripts/backtest_comprehensive.py
```

### 4. Simulated Trading

```bash
# Start simulated trading session
curl -X POST "http://localhost:8001/api/async-trading/start" \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["BTC-USD", "ETH-USD"],
    "strategy_type": "orderbook",
    "strategy_params": {},
    "initial_balance": 10000.0,
    "max_positions": 3,
    "position_size_percent": 20.0
  }'

# Get trading history for specific session
curl "http://localhost:8001/api/trades/paginated?session_id=sim_abc123_1234567890&page=1&limit=10"

# Get simulated trading status
curl "http://localhost:8001/api/simulated-trading/status"
```

### 5. Testing

```bash
# Run all tests
uv run python -m pytest

# Run specific tests
uv run python -m pytest tests/test_backtester.py
```

## 📊 Features

### Real-time Trading
- WebSocket connection to Coinbase Advanced Trading
- Live price updates and market data
- Automatic trade execution based on strategy signals
- Risk management with stop-loss and take-profit

### Backtesting System
- Historical data from Coinbase API
- Multiple strategy parameter testing
- Performance metrics calculation
- CSV export for detailed analysis

### Web Dashboard
- Real-time data visualization
- Interactive charts with Plotly.js
- Historical data analysis
- Backtesting interface
- Performance metrics display

### Risk Management
- Position sizing based on available balance
- Stop-loss and take-profit mechanisms
- Trading fee calculation
- Maximum position size limits

## 🧪 Testing

### Test Coverage
- Unit tests for all core modules
- Integration tests for WebSocket functionality
- Backtesting validation tests
- Data provider tests

### Running Tests
```bash
# All tests
uv run python -m pytest

# With coverage
uv run python -m pytest --cov=src/trade_bot

# Specific test file
uv run python -m pytest tests/test_backtester.py
```

## 📈 Performance Metrics

### Backtesting Metrics
- **Total Return**: Overall percentage return
- **Win Rate**: Percentage of profitable trades
- **Sharpe Ratio**: Risk-adjusted return
- **Max Drawdown**: Maximum peak-to-trough decline
- **Profit Factor**: Ratio of gross profit to gross loss
- **Average Win/Loss**: Average profit/loss per trade

### Real-time Metrics
- Current price and 24h change
- Volume and trading activity
- Connection status
- Trade execution statistics

## 🔒 Security

- Environment variable configuration
- No hardcoded credentials
- Secure WebSocket connections
- Input validation and sanitization
- Error handling and logging

## 🚀 Deployment

### Local Development
```bash
# Install dependencies
uv sync

# Run trading bot
uv run python main.py

# Run web dashboard
uv run python scripts/web_dashboard.py
```

### Production
```bash
# Run with production settings
uv run python main.py --log-level INFO
uv run python scripts/web_dashboard.py --host 0.0.0.0 --port 8000
```

## 📚 Documentation

- **README.md**: Main project documentation
- **WEB_DASHBOARD_README.md**: Web dashboard specific docs
- **PROJECT_OVERVIEW.md**: This file
- **Code Comments**: Comprehensive inline documentation

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 🆘 Support

For issues and questions:
1. Check the documentation
2. Review the test examples
3. Open an issue on GitHub

---

**Happy Trading! 🚀📊💰**
