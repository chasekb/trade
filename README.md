# 🚀 Advanced Trading Bot with Web Dashboard

A comprehensive Python trading bot built with `coinbase-advanced-py` featuring real-time data streaming, advanced backtesting, and a modern web dashboard.

## ✨ Features

### 🤖 Core Trading Bot
- **Real-time WebSocket Integration** with Coinbase Advanced Trading API
- **Intelligent Trading Strategies** (Simple Moving Average with Golden Cross/Death Cross)
- **Risk Management** with stop-loss and take-profit mechanisms
- **Data Storage** with CSV export for analysis
- **Simulated Trading** with live portfolio management
- **Order Book Analysis** with real-time signal generation

### 📊 Web Dashboard
- **Real-time Data Visualization** with live price updates
- **Interactive Charts** using Plotly.js
- **Historical Data Analysis** with multiple timeframes
- **Responsive Design** with Tailwind CSS
- **WebSocket Integration** for live data streaming
- **Live Trading Interface** with position management
- **Trading Statistics Widget** with comprehensive metrics
- **Strategy Configuration** with hide/show functionality

### 🧮 Advanced Backtesting
- **Real Historical Data** from Coinbase API
- **Multiple Strategy Testing** with parameter optimization
- **Performance Metrics** (ROI, Sharpe ratio, max drawdown)
- **CSV Export** for detailed analysis
- **Comprehensive Reporting** with best strategy identification

### 🔧 Technical Features
- **Asynchronous Architecture** with asyncio
- **Comprehensive Testing** with pytest
- **Modern Python** with type hints and dataclasses
- **Dependency Management** with uv
- **Git Integration** with proper version control
- **Database Persistence** with SQLite
- **Session Management** with state restoration
- **Rate Limiting** and error handling

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repository-url>
cd trade

# Install dependencies
uv sync
```

### 2. Configuration

Create a `.env` file with your Coinbase credentials:

```env
COINBASE_API_KEY=your_api_key
COINBASE_API_SECRET=your_api_secret
COINBASE_PASSPHRASE=your_passphrase
TRADING_PRODUCT_ID=BTC-USD
MAX_POSITION_SIZE=1000.0
STOP_LOSS_PERCENTAGE=0.02
TAKE_PROFIT_PERCENTAGE=0.04
TRADING_FEE_PERCENTAGE=0.001
```

### 3. Run the Trading Bot

```bash
# Start the trading bot
uv run python main.py

# Or run with specific configuration
uv run python main.py --product ETH-USD --max-position 2000
```

### 4. Launch Web Dashboard

```bash
# Start the web dashboard
uv run python scripts/web_dashboard.py

# Access at http://localhost:8001
```

### 5. Run Backtests

```bash
# Simple backtest
uv run python scripts/backtest.py

# Comprehensive backtest with multiple strategies
uv run python scripts/backtest_comprehensive.py
```

## 📊 Project Statistics

### Code Metrics
- **Total Lines of Code**: ~44,000+ lines
- **Python Files**: 23,887 lines (71 files)
- **JavaScript Files**: 5,274 lines (3 files)
- **HTML Templates**: 3,638 lines (6 files)
- **Documentation**: 2,754 lines (22 files)
- **Configuration**: 10,500+ lines (JSON, TOML, etc.)

### Largest Components
1. **`dashboard_enhanced.js`** - 4,633 lines (Frontend dashboard)
2. **`trading_strategy.py`** - 3,440 lines (Trading strategies)
3. **`web_server.py`** - 2,048 lines (FastAPI backend)
4. **`dashboard_enhanced.html`** - 1,462 lines (UI templates)
5. **`database_manager.py`** - 819 lines (Data persistence)

## 🆕 Recent Updates

### Latest Features (v2.0+)
- **Trading Statistics Widget**: Comprehensive real-time metrics dashboard
- **Strategy Configuration Hide/Show**: Cleaner interface during active trading
- **Session State Persistence**: Maintains trading state across page refreshes
- **Individual Trade Logging**: Detailed trade history in SQLite database
- **Order Book Signal Generation**: Real-time trading signals from market data
- **Enhanced WebSocket Management**: Improved connection stability and error handling
- **Live Trading Interface**: Complete simulated trading with position management

### Technical Improvements
- **Database Integration**: SQLite for persistent data storage
- **API Enhancements**: Comprehensive REST endpoints for trading data
- **Frontend Optimization**: Real-time updates and responsive design
- **Error Handling**: Robust error management and recovery
- **Performance**: Optimized data processing and caching

## 📁 Project Structure

```
trade/
├── src/trade_bot/           # Core trading bot modules (23,887 lines)
│   ├── __init__.py
│   ├── config.py            # Configuration management
│   ├── trading_bot.py       # Main trading bot class
│   ├── trading_strategy.py  # Trading strategies (3,440 lines)
│   ├── websocket_client.py  # WebSocket client
│   ├── data_handler.py      # Data storage and management
│   ├── data_provider.py     # Historical data provider
│   ├── backtester.py        # Backtesting engine
│   ├── web_server.py        # FastAPI web server (2,048 lines)
│   ├── database_manager.py  # SQLite database operations (819 lines)
│   ├── simulated_trading_manager.py  # Live trading simulation
│   └── orderbook_analyzer.py # Order book signal generation
├── scripts/                 # Executable scripts
│   ├── web_dashboard.py     # Web dashboard launcher
│   ├── backtest.py          # Simple backtesting
│   └── backtest_comprehensive.py  # Advanced backtesting
├── tests/                   # Comprehensive test suite
│   ├── test_*.py            # Unit and integration tests
│   ├── dashboard_test_suite.py  # Dashboard testing (866 lines)
│   ├── integration_tests/   # Integration test suite
│   └── fallback_tests/      # Fallback testing scenarios
├── templates/               # Web dashboard templates (3,638 lines)
│   ├── dashboard.html       # Basic dashboard
│   └── dashboard_enhanced.html  # Enhanced dashboard (1,462 lines)
├── static/                  # Static web assets (5,274 lines)
│   ├── js/
│   │   ├── dashboard.js     # Basic dashboard logic
│   │   └── dashboard_enhanced.js  # Enhanced dashboard (4,633 lines)
│   └── css/                 # Styling files
├── docs/                    # Documentation (2,754 lines)
│   ├── WEB_DASHBOARD_README.md
│   ├── PROJECT_OVERVIEW.md
│   ├── CHANGELOG.md
│   └── *.md
├── outputs/                 # Generated data and results
├── test_outputs/           # Test-generated outputs
├── rules/                  # Development rules and guidelines
├── main.py                 # Main entry point
├── pyproject.toml         # Project configuration
├── requirements.txt       # Python dependencies
├── trading_cache.db       # SQLite database for persistence
└── backtests.db          # Backtest results database
```

## 🎯 Usage Examples

### Basic Trading Bot

```python
from src.trade_bot.trading_bot import TradingBot
from src.trade_bot.config import TradingConfig

# Load configuration
config = TradingConfig.from_env()

# Create and run trading bot
bot = TradingBot(config)
await bot.run()
```

### Web Dashboard

```python
# Start the web server
from src.trade_bot.web_server import app
import uvicorn

uvicorn.run(app, host="0.0.0.0", port=8001)
```

### Backtesting

```python
from src.trade_bot.backtester import Backtester
from src.trade_bot.trading_strategy import SimpleMovingAverageStrategy

# Create backtester
backtester = Backtester(
    config=config,
    strategy_class=SimpleMovingAverageStrategy,
    strategy_params={'short_window': 5, 'long_window': 20}
)

# Run backtest
result = await backtester.run_backtest(historical_data)
```

## 📊 Web Dashboard Features

### Real-time Data
- Live price updates via WebSocket
- 24-hour volume and price changes
- Connection status monitoring

### Historical Analysis
- Interactive candlestick charts
- Multiple timeframes (3, 7, 14, 30 days)
- Zoom and pan functionality

### Backtesting Interface
- Easy parameter configuration
- Real-time backtest execution
- Results visualization
- Performance comparison

### Trading Metrics
- ROI calculations
- Win rate analysis
- Trade statistics
- Best strategy identification

### Live Trading Interface
- **Real-time Portfolio Management** with position tracking
- **Trading Statistics Widget** with comprehensive metrics
- **Order Book Signal Generation** for market analysis
- **Session State Persistence** across page refreshes
- **Strategy Configuration** with hide/show functionality
- **Live P&L Tracking** with real-time updates

## 🧪 Testing

```bash
# Run all tests
uv run python -m pytest

# Run specific test categories
uv run python -m pytest tests/test_backtester.py
uv run python -m pytest tests/test_data_provider.py

# Run with coverage
uv run python -m pytest --cov=src/trade_bot
```

## 📈 API Endpoints

### Web Dashboard API
- `GET /` - Main dashboard page
- `GET /api/real-time-data` - Current market data
- `GET /api/historical-data` - Historical OHLCV data
- `POST /api/run-backtest` - Execute backtest
- `GET /api/trading-metrics` - Performance metrics
- `WebSocket /ws` - Real-time data stream

### Live Trading API
- `POST /api/simulated-trading/start` - Start simulated trading
- `POST /api/simulated-trading/stop` - Stop simulated trading
- `GET /api/simulated-trading/status` - Get trading status
- `GET /api/portfolio/status` - Get portfolio information
- `GET /api/positions` - Get open positions
- `GET /api/trades/recent` - Get recent trades

### Trading Statistics API
- `GET /api/trades/stats` - Comprehensive trading statistics
- `GET /api/trades/session/{session_id}` - Session-specific trades
- `GET /api/trades/symbol/{symbol}` - Symbol-specific trades
- `GET /api/trades/recent` - Recent trades across all sessions

### Order Book API
- `GET /api/orderbook/live-signals` - Live order book signals
- `GET /api/orderbook/signals/{symbol}` - Symbol-specific signals

### Session Management API
- `POST /api/session/save` - Save trading session state
- `GET /api/session/load/{session_id}` - Load trading session state
- `POST /api/session/save-dashboard` - Save dashboard UI state
- `GET /api/session/load-dashboard/{session_id}` - Load dashboard UI state
- `GET /api/session/active` - Get active trading sessions
- `POST /api/session/deactivate/{session_id}` - Deactivate session

### Health Check
- `GET /api/health` - Server health status
- `GET /api/realtime-status` - Real-time data collection status

## 🔧 Configuration Options

### Environment Variables
- `COINBASE_API_KEY` - Coinbase API key
- `COINBASE_API_SECRET` - Coinbase API secret
- `COINBASE_PASSPHRASE` - Coinbase passphrase
- `TRADING_PRODUCT_ID` - Trading pair (default: BTC-USD)
- `MAX_POSITION_SIZE` - Maximum position size (default: 1000.0)
- `STOP_LOSS_PERCENTAGE` - Stop loss percentage (default: 0.02)
- `TAKE_PROFIT_PERCENTAGE` - Take profit percentage (default: 0.04)
- `TRADING_FEE_PERCENTAGE` - Trading fee percentage (default: 0.001)

### Trading Strategy Parameters
- `short_window` - Short moving average window (default: 5)
- `long_window` - Long moving average window (default: 20)

## 🚀 Deployment

### Local Development
```bash
# Start trading bot
uv run python main.py

# Start web dashboard
uv run python scripts/web_dashboard.py
```

### Production
```bash
# Run with production settings
uv run python main.py --log-level INFO
uv run python scripts/web_dashboard.py --host 0.0.0.0 --port 8000
```

## 📊 Performance Metrics

The backtesting system provides comprehensive metrics:
- **Total Return** - Overall percentage return
- **Win Rate** - Percentage of profitable trades
- **Sharpe Ratio** - Risk-adjusted return
- **Max Drawdown** - Maximum peak-to-trough decline
- **Profit Factor** - Ratio of gross profit to gross loss
- **Average Win/Loss** - Average profit/loss per trade

## 🔒 Security

- Environment variable configuration
- No hardcoded API keys
- Secure WebSocket connections
- Input validation and sanitization

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check the documentation in `docs/`
2. Review the test examples in `examples/`
3. Open an issue on GitHub

## 🎉 Success!

Your trading bot is now ready with:
- ✅ Real-time data streaming
- ✅ Advanced backtesting capabilities
- ✅ Modern web dashboard
- ✅ Comprehensive testing
- ✅ Production-ready code

Happy trading! 🚀📊💰
