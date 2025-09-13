# Trading Bot

A Python websocket trading bot using Coinbase Advanced Trading API with real-time market data processing and automated trading strategies.

## Features

- **Real-time WebSocket Connection**: Connects to Coinbase Advanced Trading WebSocket for live market data
- **Trading Strategy**: Simple Moving Average (SMA) crossover strategy with configurable parameters
- **Risk Management**: Built-in stop loss and take profit mechanisms
- **Data Export**: CSV output for ticker data, trades, and signals
- **Comprehensive Testing**: Full test suite with 49 test cases
- **Modern Python**: Built with Python 3.11+ and managed with uv

## Project Structure

```
trade/
├── src/trade_bot/           # Main trading bot package
│   ├── __init__.py
│   ├── config.py            # Configuration management
│   ├── websocket_client.py  # WebSocket client for real-time data
│   ├── trading_strategy.py  # SMA crossover trading strategy
│   ├── data_handler.py      # Data storage and CSV export
│   └── trading_bot.py       # Main bot orchestration
├── tests/                   # Comprehensive test suite
│   ├── test_config.py
│   ├── test_trading_strategy.py
│   ├── test_data_handler.py
│   └── test_websocket_client.py
├── outputs/                 # CSV data output directory
├── main.py                  # Entry point
├── pyproject.toml          # Project configuration
└── README.md
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
