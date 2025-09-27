# Trading Bot - Advanced Trading System

A comprehensive trading bot system with web dashboard, backtesting, and live trading capabilities.

## 🏗️ Project Structure

```
trade/
├── main.py                     # Main entry point
├── README.md                   # This file
├── TODO.md                     # Project tasks and roadmap
│
├── config/                     # Configuration files
│   ├── pyproject.toml         # Python project configuration
│   ├── requirements.txt       # Python dependencies
│   ├── uv.lock               # UV lock file
│   ├── package.json          # Node.js dependencies
│   ├── package-lock.json     # Node.js lock file
│   ├── playwright.config.ts  # Playwright configuration
│   └── vercel.json           # Vercel deployment config
│
├── src/                       # Source code
│   └── trade_bot/            # Main application package
│       ├── core/             # Core functionality
│       ├── data/             # Data handling and providers
│       ├── database/         # Database management
│       ├── trading/          # Trading strategies and execution
│       └── web/              # Web dashboard and API
│
├── scripts/                   # Executable scripts
│   ├── backtest/             # Backtesting scripts
│   ├── web/                  # Web server scripts
│   └── utilities/            # Utility scripts
│
├── tests/                     # Test suite
│   ├── unit/                 # Unit tests
│   ├── integration/          # Integration tests
│   └── e2e/                  # End-to-end tests
│
├── data/                      # Data storage
│   ├── databases/            # SQLite databases
│   ├── outputs/              # Generated output files
│   └── cache/                # Cached data and node_modules
│
├── docs/                      # Documentation
│   ├── examples/             # Example code and tutorials
│   ├── CHANGELOG.md          # Version history
│   ├── PROJECT_OVERVIEW.md   # Project overview
│   ├── spec.md               # Technical specifications
│   ├── TEST_RESULTS.md       # Test results
│   ├── WEB_DASHBOARD_README.md # Web dashboard documentation
│   └── WEBSOCKET_SUBSCRIPTIONS.md # WebSocket documentation
│
├── static/                    # Static web assets
│   ├── css/                  # Stylesheets
│   └── js/                   # JavaScript files
│
├── templates/                 # HTML templates
│   ├── dashboard.html        # Basic dashboard
│   └── dashboard_enhanced.html # Enhanced dashboard
│
└── rules/                     # Development rules and guidelines
    ├── 01-core.md
    ├── 02-request.md
    └── ... (other rule files)
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- UV package manager

### Installation
```bash
# Install Python dependencies
uv sync

# Install Node.js dependencies
npm install --prefix data/cache
```

### Running the Application

#### Web Dashboard
```bash
python main.py web
# or
uv run python main.py web
```

#### Backtesting
```bash
# Basic backtest
python main.py backtest

# Comprehensive backtest
python main.py backtest --comprehensive
```

#### Data Collection
```bash
python main.py data
```

#### Live Trading
```bash
python main.py live
```

## 📊 Features

- **Web Dashboard**: Real-time trading dashboard with candlestick charts
- **Backtesting**: Historical strategy testing with comprehensive metrics
- **Data Providers**: Coinbase Pro API integration for real market data
- **Trading Strategies**: Multiple built-in strategies (RSI, MACD, Bollinger Bands, etc.)
- **Simulated Trading**: Paper trading with realistic execution simulation
- **WebSocket Integration**: Real-time data streaming
- **Database Storage**: SQLite for persistent data storage

## 🔧 Configuration

Configuration files are located in the `config/` directory:
- `pyproject.toml`: Python project settings
- `requirements.txt`: Python dependencies
- `package.json`: Node.js dependencies
- `playwright.config.ts`: E2E testing configuration

## 🧪 Testing

```bash
# Run unit tests
python -m pytest tests/unit/

# Run integration tests
python -m pytest tests/integration/

# Run E2E tests
npx playwright test
```

## 📈 Data Management

- **Databases**: Stored in `data/databases/`
- **Outputs**: Generated files in `data/outputs/`
- **Cache**: Temporary data in `data/cache/`

## 🌐 Web Dashboard

Access the web dashboard at `http://localhost:8001` after running:
```bash
python main.py web
```

Features:
- Real-time price charts
- Trading strategy configuration
- Backtest results visualization
- Live trading interface
- Data feed monitoring

## 📚 Documentation

Detailed documentation is available in the `docs/` directory:
- [Project Overview](docs/PROJECT_OVERVIEW.md)
- [Web Dashboard Guide](docs/WEB_DASHBOARD_README.md)
- [WebSocket Subscriptions](docs/WEBSOCKET_SUBSCRIPTIONS.md)
- [Test Results](docs/TEST_RESULTS.md)

## 🤝 Contributing

Please read the development rules in the `rules/` directory before contributing.

## 📄 License

This project is proprietary software. All rights reserved.