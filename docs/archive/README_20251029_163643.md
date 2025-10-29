# Advanced Trading Bot

A comprehensive trading bot system built with Python 3.11+ using Coinbase Advanced Trading API, featuring real-time WebSocket connections, multiple trading strategies, advanced backtesting, machine learning optimization, and a modern web dashboard.

## Features

- **Real-time Trading**: WebSocket integration for live market data and automated trade execution
- **Multiple Trading Strategies**: SMA, RSI, Bollinger Bands, MACD, Fibonacci, ATR, Stochastic, and ML-enhanced order book strategies
- **Machine Learning Trading Optimization**: Integrated ML system with vector database for pattern recognition and signal optimization
- **Advanced Backtesting**: Comprehensive historical data analysis with detailed performance metrics
- **Vector Database Integration**: Qdrant + Redis architecture for ML feature storage and similarity search
- **Web Dashboard**: Modern FastAPI-based interface with real-time data visualization
- **Risk Management**: Built-in stop-loss, take-profit, and position sizing mechanisms
- **Data Management**: SQLite database with extensive data handlers and CSV export capabilities
- **Automated Service Management**: Integrated startup of vector database, ML services, and Redis cache
- **Comprehensive Testing**: Full test suite with 100+ test cases covering all components

## Project Structure

```
trade/
├── src/trade_bot/                  # Main trading bot package
│   ├── core/                      # Core functionality
│   │   ├── config.py              # Configuration management
│   │   ├── trading_bot.py         # Main bot orchestration
│   │   └── universe_selector.py   # Market universe selection
│   ├── data/                      # Data handling and providers
│   │   ├── data_provider.py       # Historical and real-time data
│   │   ├── websocket_client.py    # WebSocket client
│   │   ├── database/              # Database components
│   │   └── data_components/        # Data processing components
│   ├── trading/                   # Trading strategies and execution
│   │   ├── strategies/            # Multiple trading strategies
│   │   ├── simulated_trading_manager.py # Simulated trading
│   │   └── trade_executor.py      # Trade execution logic
│   ├── ml/                        # Machine Learning components
│   │   ├── vector_database_service.py # Vector DB manager
│   │   ├── data_collector.py      # ML data collection
│   │   ├── model_manager.py       # ML model management
│   │   └── model_trainer.py       # ML training engine
│   └── web/                       # Web dashboard components
│       ├── web_server.py         # FastAPI server
│       ├── web_components/        # UI components
│       └── web_handlers/          # API handlers
├── tests/                         # Comprehensive test suite
├── docs/                          # Extensive documentation
├── static/                        # Web assets
├── templates/                     # HTML templates
├── scripts/                       # Executable scripts
├── outputs/                       # Generated data and reports
├── main.py                        # Unified entry point
└── config/                        # Configuration files
```

## Installation

This project uses [uv](https://github.com/astral-sh/uv) for Python package management.

1. **Install uv** (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Clone and setup the project**:
   ```bash
   git clone <repository-url>
   cd trade
   uv sync
   ```

## Configuration

Set the following environment variables:

```bash
export COINBASE_API_KEY="your_api_key"
export COINBASE_API_SECRET="your_api_secret"
export COINBASE_PASSPHRASE="your_passphrase"
export TRADING_PRODUCT_ID="BTC-USD"  # Optional, defaults to BTC-USD
export MAX_POSITION_SIZE="1000.0"    # Optional, defaults to 1000.0
export STOP_LOSS_PERCENTAGE="0.02"   # Optional, defaults to 2%
export TAKE_PROFIT_PERCENTAGE="0.04" # Optional, defaults to 4%
export OUTPUT_DIR="outputs"          # Optional, defaults to outputs
export LOG_LEVEL="INFO"              # Optional, defaults to INFO
```

## Usage

### Running the Bot

```bash
uv run main.py
```

### Running Tests

```bash
uv run pytest tests/ -v
```

### Running Specific Tests

```bash
# Run only strategy tests
uv run pytest tests/test_trading_strategy.py -v

# Run only configuration tests
uv run pytest tests/test_config.py -v
```

## Trading Strategy

The bot implements a Simple Moving Average (SMA) crossover strategy:

- **Golden Cross**: When short SMA crosses above long SMA → Buy signal
- **Death Cross**: When short SMA crosses below long SMA → Sell signal
- **Stop Loss**: Automatic sell when position loses 2% (configurable)
- **Take Profit**: Automatic sell when position gains 4% (configurable)

### Strategy Parameters

- **Short SMA Window**: 10 periods (configurable)
- **Long SMA Window**: 30 periods (configurable)
- **Stop Loss**: 2% loss threshold
- **Take Profit**: 4% gain threshold

## Data Output

The bot generates CSV files in the `outputs/` directory:

- **ticker_data_*.csv**: Real-time price and volume data
- **trade_data_*.csv**: Executed trades and orders
- **signal_data_*.csv**: Generated trading signals

## API Integration

The bot integrates with Coinbase Advanced Trading API:

- **WebSocket**: Real-time market data streaming
- **REST API**: Order execution (currently simulated)
- **Authentication**: API key, secret, and passphrase

## Development

### Project Setup

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Run linting
uv run ruff check src/ tests/

# Run type checking
uv run mypy src/
```

### Adding New Strategies

1. Create a new strategy class in `src/trade_bot/strategies/`
2. Implement the required methods: `generate_signal()`, `update_position()`
3. Add tests in `tests/test_strategies/`
4. Update the main bot to use the new strategy

### Adding New Data Sources

1. Extend the `WebSocketClient` class
2. Add new message handlers
3. Update the data handler for new data types
4. Add corresponding tests

## Testing

The project includes comprehensive tests:

- **Unit Tests**: Individual component testing
- **Integration Tests**: Component interaction testing
- **Async Tests**: WebSocket and async functionality testing
- **Mock Tests**: External API mocking

Run all tests:
```bash
uv run pytest tests/ -v
```

## Security

- **API Keys**: Never commit API keys to version control
- **Environment Variables**: Use environment variables for sensitive data
- **Rate Limiting**: Built-in rate limiting for API calls
- **Error Handling**: Comprehensive error handling and logging

## Logging

The bot includes detailed logging:

- **Console Output**: Real-time status updates
- **File Logging**: Persistent log files (`trading_bot.log`)
- **Configurable Levels**: DEBUG, INFO, WARNING, ERROR

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

This project is for educational purposes. Please ensure compliance with Coinbase's terms of service and applicable regulations before using in production.

## Disclaimer

This software is for educational purposes only. Trading cryptocurrencies involves substantial risk of loss. The authors are not responsible for any financial losses incurred through the use of this software.
