# Trading Bot - Advanced Trading System

A comprehensive trading bot system with web dashboard, backtesting, live trading capabilities, and **Machine Learning Trading Optimization**.

## 🏗️ Project Structure

```
trade/
├── main.py                     # Main entry point
├── README.md                   # This file
│
├── config/                     # Configuration files
│   ├── pyproject.toml         # Python project configuration
│   ├── requirements.txt       # Python dependencies
│   ├── uv.lock               # UV lock file
│   ├── package.json          # Node.js dependencies
│   ├── package-lock.json     # Node.js lock file
│   ├── playwright.config.ts  # Playwright configuration
│   ├── vector-db-config.yaml # Vector database configuration

│
├── src/                       # Source code
│   └── trade_bot/            # Main application package
│       ├── core/             # Core functionality
│       ├── data/             # Data handling and providers
│       ├── database/         # Database management
│       ├── trading/          # Trading strategies and execution
│       ├── ml/               # Machine Learning components
│       └── web/              # Web dashboard and API
│
├── scripts/                   # Executable scripts
│   ├── backtest/             # Backtesting scripts
│   ├── web/                  # Web server scripts
│   ├── ml/                   # ML training and management scripts
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
│   ├── WEBSOCKET_SUBSCRIPTIONS.md # WebSocket documentation
│   └── ML_TRADING_OPTIMIZATION.md # ML system documentation
│
├── static/                    # Static web assets
│   ├── css/                  # Stylesheets
│   └── js/                   # JavaScript files
│
├── templates/                 # HTML templates
│   ├── dashboard.html        # Basic dashboard
│   ├── dashboard_enhanced.html # Enhanced dashboard
│   └── dashboard_enhanced_modular.html # Modular dashboard with ML
│
└── rules/                     # Development rules and guidelines
    ├── 01-core.md
    ├── 02-request.md
    └── ... (other rule files)
```

## ✨ Key Features

### 🎯 **Integrated ML Trading System**
- **One Command Setup**: `uv run python main.py web` starts everything
- **Automatic Service Management**: Vector database and ML services start automatically
- **Seamless Trading Integration**: ML predictions available for simulated and live trading
- **Real-time ML Dashboard**: Built-in ML management interface at `http://localhost:8001`
- **Health Monitoring**: Automatic service health checks and status monitoring
- **Graceful Shutdown**: Proper cleanup when stopping the system

### 🏗️ **Modern Architecture**
- **Microservices Design**: Modular, scalable component architecture
- **Async/Await**: High-performance asynchronous Python
- **Vector Database**: Qdrant for ML pattern matching and similarity search
- **Caching Layer**: Redis for high-performance data caching
- **WebSocket Integration**: Real-time data streaming
- **RESTful API**: FastAPI with automatic OpenAPI documentation

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- UV package manager
- Qdrant (for ML vector database)
- Redis (for ML caching)

### Installation
```bash
# Install Python dependencies
uv sync

# Install Node.js dependencies
npm install --prefix data/cache

# Install ML dependencies
pip install scikit-learn pandas numpy joblib requests
```

### Security Setup
**IMPORTANT:** Before running the application, you must set up your Coinbase API credentials securely.

1. **Copy the environment template:**
   ```bash
   cp docs/env.example .env
   ```

2. **Get your Coinbase API credentials** from [Coinbase Pro API Settings](https://pro.coinbase.com/profile/api)

3. **Update your `.env` file** with your actual credentials

4. **Configure all trading settings** through the web dashboard's Live Trading tab

5. **See [Security Setup Guide](docs/SECURITY_SETUP.md)** for detailed instructions

**⚠️ Never commit your `.env` file or expose your API credentials!**
```

### Running the Application

#### Web Dashboard with Integrated ML Services (Recommended)
```bash
# Start web dashboard with integrated vector database and ML services
uv run python main.py web
```

This single command starts:
- Web dashboard on `http://localhost:8001`
- Qdrant vector database on `http://localhost:6333`
- Redis cache on `localhost:6380`
- ML Model Server on `http://localhost:8002`
- All ML services available for trading

#### Standalone Vector Database Services
```bash
# Start only vector database services (for external use)
uv run python main.py vector-db
```

#### Backtesting
```bash
# Basic backtest
uv run python main.py backtest

# Comprehensive backtest
uv run python main.py backtest --comprehensive
```

#### Data Collection
```bash
uv run python main.py data
```

#### Live Trading
```bash
uv run python main.py live
```

#### Machine Learning Management
```bash
# Train ML models (when web dashboard is running)
# Access ML dashboard at http://localhost:8001/ml

# Or use standalone scripts
python scripts/ml/train_models.py --days-back 30
python scripts/ml/test_integration.py
python scripts/ml/validate_strategy.py --start-date 2024-01-01 --end-date 2024-01-31
```

## 📊 Features

- **Web Dashboard**: Real-time trading dashboard with candlestick charts
- **Backtesting**: Historical strategy testing with comprehensive metrics
- **Data Providers**: Coinbase Pro API integration for real market data
- **Trading Strategies**: Multiple built-in strategies (RSI, MACD, Bollinger Bands, etc.)
- **Simulated Trading**: Paper trading with realistic execution simulation
- **WebSocket Integration**: Real-time data streaming
- **Database Storage**: SQLite for persistent data storage
- **🤖 Machine Learning Trading Optimization**:
  - **ML-Enhanced Order Book Strategy**: Real-time ML predictions for trading signals
  - **Vector Database**: Qdrant vector database for pattern matching and similarity search
  - **Ensemble Models**: Random Forest, Gradient Boosting, Neural Networks
  - **Feature Engineering**: Advanced order book feature extraction
  - **Model Management**: Versioning, hot-swapping, and rollback capabilities
  - **Real-time Inference**: Sub-second ML predictions during live trading
  - **Performance Monitoring**: Comprehensive ML model performance tracking

## 🔧 Configuration

Configuration files are located in the `config/` directory:
- `pyproject.toml`: Python project settings
- `requirements.txt`: Python dependencies
- `package.json`: Node.js dependencies
- `playwright.config.ts`: E2E testing configuration
- `vector-db-config.yaml`: Vector database configuration for ML system

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
uv run python main.py web
```

Features:
- Real-time price charts
- Trading strategy configuration
- Backtest results visualization
- Live trading interface
- Data feed monitoring
- **🤖 Integrated ML Trading Optimization**:
  - ML model status and performance metrics
  - Feature importance visualization
  - Model control interface (train, update, rollback)
  - Real-time ML system monitoring
  - ML vs baseline strategy comparison
  - **Automatic ML Service Management**: Vector database and ML services start automatically
  - **Trading Integration**: ML predictions available for simulated and live trading

## 🤖 Machine Learning Trading Optimization

The ML Trading Optimization system enhances trading decisions using machine learning:

### ML System Architecture
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Trading Bot   │    │  ML Optimizer   │    │ Vector Database │
│                 │    │                 │    │                 │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │ Order Book  │ │───▶│ │ Data        │ │───▶│ │ Qdrant      │ │
│ │ Strategy    │ │    │ │ Collector   │ │    │ │ Vector DB   │ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
│                 │    │                 │    │                 │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │ ML Enhanced │ │◀───│ │ Model       │ │◀───│ │ Redis       │ │
│ │ Strategy    │ │    │ │ Manager     │ │    │ │ Cache       │ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │ ML Model Server │
                       │ (FastAPI)       │
                       └─────────────────┘
```

### Key Components
- **Data Collection**: Extract order book signals and trade outcomes
- **Feature Engineering**: Transform raw data into ML-ready features
- **Model Training**: Ensemble models (RF, GB, NN, Linear)
- **Vector Database**: Qdrant for pattern matching and similarity search
- **Model Management**: Versioning, deployment, and rollback
- **Real-time Inference**: Sub-second ML predictions during trading

### ML Services (Automatically Started with Web Dashboard)
- **Qdrant Vector DB**: `http://localhost:6333` - Feature vector storage
- **Redis Cache**: `localhost:6380` - High-performance caching
- **ML Model Server**: `http://localhost:8002` - Real-time inference API
- **Web Dashboard**: `http://localhost:8001` - Integrated ML management interface

### ML Service Management
- **Automatic Startup**: All ML services start automatically with `uv run python main.py web`
- **Health Monitoring**: Built-in health checks and service status monitoring
- **Graceful Shutdown**: Proper cleanup when web dashboard stops
- **Trading Integration**: ML predictions seamlessly integrated into trading strategies

## 📚 Documentation

Detailed documentation is available in the `docs/` directory:
- [Project Overview](docs/PROJECT_OVERVIEW.md)
- [Web Dashboard Guide](docs/WEB_DASHBOARD_README.md)
- [WebSocket Subscriptions](docs/WEBSOCKET_SUBSCRIPTIONS.md)
- [Test Results](docs/TEST_RESULTS.md)
- [🤖 ML Trading Optimization](docs/ML_TRADING_OPTIMIZATION.md) - Complete ML system documentation
- [Vector Database Service](docs/VECTOR_DATABASE_SERVICE.md) - Integrated service management

## 🔧 Troubleshooting

### Common Issues

#### ML Services Not Starting
```bash
# Check if Qdrant and Redis are installed
which qdrant
which redis-server

# Install missing services
# For macOS with Homebrew:
brew install qdrant redis

# For Ubuntu/Debian:
sudo apt-get install qdrant redis-server
```

#### Port Conflicts
If ports 6333, 6380, 8001, or 8002 are already in use:
```bash
# Check what's using the ports
lsof -i :6333
lsof -i :6380
lsof -i :8001
lsof -i :8002

# Stop conflicting services or change ports in config/vector-db-config.yaml
```

#### ML Model Training Issues
```bash
# Check if you have sufficient trading data
sqlite3 data/databases/trading_cache.db "SELECT COUNT(*) FROM order_book_signals;"

# If no data, run some simulated trading first
uv run python main.py web
# Then use the web dashboard to start simulated trading
```

#### Service Health Checks
```bash
# Check service status
curl http://localhost:6333/health  # Qdrant
redis-cli -p 6380 ping            # Redis
curl http://localhost:8002/health  # ML Server
curl http://localhost:8001/health  # Web Dashboard
```

## 🤝 Contributing

Please read the development rules in the `rules/` directory before contributing.

## 📄 License

This project is proprietary software. All rights reserved.
