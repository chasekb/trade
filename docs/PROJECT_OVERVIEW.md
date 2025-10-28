# 📊 Advanced Trading Bot - Project Overview

## 🎯 Project Summary

This is a comprehensive Python trading bot system built with modern technologies and advanced machine learning capabilities. The system integrates multiple trading strategies, real-time data processing, automated backtesting, and an intelligent ML optimization layer for enhanced trading decisions.

## 🚀 Key Features

### Core Trading Capabilities
- **Real-time Trading**: WebSocket integration with Coinbase Advanced Trading API
- **Multiple Trading Strategies**: 10+ strategies including SMA, RSI, Bollinger Bands, MACD, FIB, ATR, Stochastic, ML-enhanced order book analysis
- **Advanced Backtesting**: Comprehensive historical data analysis with detailed performance metrics
- **Modern Web Dashboard**: FastAPI-based interface with real-time data visualization and ML management
- **Risk Management**: Multi-level risk controls with stop-loss, take-profit, and position sizing
- **Session-Based Trading**: Isolated trading sessions with comprehensive tracking and analytics

### Machine Learning Optimization System
- **ML Trading Optimization**: Integrated machine learning system for signal optimization and pattern recognition
- **Vector Database Integration**: Qdrant + Redis architecture for ML feature storage and similarity search
- **Automated Service Management**: Integrated startup of vector database, ML model server, and Redis cache
- **Real-time Model Inference**: Sub-second ML predictions integrated into live trading strategies
- **Model Management Framework**: Versioning, hot-swapping, and performance monitoring
- **Feature Engineering Pipeline**: Advanced order book feature extraction and trading fee optimization

### Data Architecture
- **Comprehensive Data Handling**: Multi-tier data architecture with specialized handlers
- **Database Integration**: SQLite with advanced connection pooling and optimization
- **Real-time Data Streaming**: WebSocket and REST API integration for live market data
- **Data Export & Analytics**: CSV export with detailed trade signal and performance analysis

## 🏗️ Advanced Architecture

### Core System Components

1. **Core Engine** (`src/trade_bot/core/`)
   - **Trading Bot** (`trading_bot.py`): Main orchestration engine with multi-strategy support
   - **Configuration System** (`config.py`): Multi-environment configuration management
   - **Universe Selector** (`universe_selector.py`): Dynamic market selection and portfolio optimization

2. **Data Layer** (`src/trade_bot/data/`)
   - **Data Provider** (`data_provider.py`): Unified data access with caching and optimization
   - **WebSocket Client** (`websocket_client.py`): High-performance real-time data streaming
   - **Database System** (`database/`): Advanced SQLite implementation with connection pooling
   - **Data Components** (`data_components/`): Specialized handlers for trades, signals, and market data

3. **Trading Engine** (`src/trade_bot/trading/`)
   - **Strategy Framework** (`strategies/`): 10+ technical analysis and ML strategies
   - **Simulated Trading Manager** (`simulated_trading_manager.py`): Live portfolio simulation with realistic execution
   - **Trading Components** (`simulated_components/`): Modular trading logic and portfolio management

### Machine Learning System (`src/trade_bot/ml/`)

1. **Vector Database Service** (`vector_database_service.py`)
   - Integrated Qdrant + Redis management
   - Automated service startup and health monitoring
   - Real-time feature vector storage and similarity search

2. **Data Collection & Processing** (`data_collector.py`)
   - Historical trading data extraction
   - Feature vector creation from order book patterns
   - ML training data preparation and labeling

3. **ML Model Management** (`model_manager.py`)
   - Model versioning and deployment
   - Performance monitoring and rollback capabilities
   - Automated model replacement triggers

4. **Model Training Engine** (`model_trainer.py`)
   - Ensemble model training (Random Forest, Gradient Boosting, Neural Networks)
   - Hyperparameter optimization and cross-validation
   - Trading-domain specific performance metrics

### Web Interface System (`src/trade_bot/web/`)

1. **FastAPI Server** (`web_server.py`)
   - High-performance async web server
   - Real-time WebSocket data streaming
   - Comprehensive REST API with OpenAPI documentation

2. **UI Components** (`web_components/`)
   - Modular dashboard components
   - ML management interface
   - Real-time data visualization

3. **API Handlers** (`web_handlers/`)
   - Specialized handlers for trading, backtesting, and ML operations
   - Rate limiting and request validation
   - Comprehensive error handling

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
