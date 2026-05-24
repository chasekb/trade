# Trading Bot - Advanced Trading System

A comprehensive trading bot system with web dashboard, backtesting, live trading capabilities, and **Machine Learning Trading Optimization**.

## 🏗️ Project Structure

```text
trade/
├── app.py                      # FastAPI backend server (Docker deployment)
├── docker-compose.yml          # Docker Compose deployment configuration
├── docker-compose.test.yml     # Testing configuration for C++ backend
├── Dockerfile                  # Python Backend Docker configuration
├── Dockerfile.cpp              # C++ Backend Docker configuration
├── frontend/                   # Next.js React/TypeScript frontend
├── src/                        # C++ Source code (New)
│   └── cpp_backend/            # High-performance C++ backend
├── README.md                   # This file
│
├── archive/                    # Archived unused code (see archive/README.md)
│   └── vanilla_js_dashboard/  # Previously used vanilla JS dashboard
│
├── config/                     # Configuration files
│   ├── pyproject.toml         # Python project configuration
│   ├── requirements.txt       # Python dependencies
│   ├── uv.lock               # UV lock file
│   ├── package.json          # Node.js dependencies
│   ├── package-lock.json     # Node.js lock file
│   ├── playwright.config.ts  # Playwright configuration
│   └── vector-db-config.yaml # Vector database configuration
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
│   ├── TYPESCRIPT_TRANSITION.md # React/TypeScript transition documentation
│   ├── WEBSOCKET_SUBSCRIPTIONS.md # WebSocket documentation
│   └── ML_TRADING_OPTIMIZATION.md # ML system documentation
│
└── rules/                     # Development rules and guidelines
    ├── 01-core.md
    ├── 02-request.md
    └── ... (other rule files)
```

## ✨ Key Features

### 🎯 **Integrated ML Trading System**

- **One Command Setup**: `docker-compose up` starts everything
- **Automatic Service Management**: Backend support services start automatically
- **Seamless Trading Integration**: ML predictions available for simulated and live trading
- **Real-time ML Dashboard**: Built-in ML management interface at `http://localhost:3000`
- **Health Monitoring**: Automatic service health checks and status monitoring
- **Graceful Shutdown**: Proper cleanup when stopping the system

### 🏗️ **Modern Architecture**

- **Microservices Design**: Modular, scalable component architecture
- **Async/Await**: High-performance asynchronous Python
- **Caching Layer**: Redis for high-performance data caching
- **WebSocket Integration**: Real-time data streaming
- **RESTful API**: FastAPI with automatic OpenAPI documentation

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- UV package manager
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

```text

### Running the Application

#### Docker Compose Deployment (Recommended)
```bash
# Start all services using Docker Compose
docker-compose up
```

This single command starts:

- **C++ Backend**: High-performance ML inference at `http://localhost:8080`
- **Frontend**: Next.js React dashboard on `http://localhost:3000`
- **Backend**: FastAPI server on `http://localhost:8000` (Legacy/Integration)
- Redis cache on `localhost:6379`
- PostgreSQL database on `localhost:5432`

#### ☁️ Remote Build & CI/CD

The system uses **GitHub Actions** for remote multi-platform builds. Images are tagged by branch name (e.g., `:dev`, `:main`) ensuring isolation between development and production.

**To run the latest `dev` branch images locally:**

```bash
# Pull branch-specific images from GHCR
TAG=dev podman-compose pull

# Run using the dev branch images (force remote build usage)
TAG=dev podman-compose up --no-build
```

**To run the production (`main`) images:**

```bash
# Defaults to :latest (linked to main)
TAG=main podman-compose pull
TAG=main podman-compose up --no-build
```

#### 🧪 Running C++ Tests

```bash
# Run the C++ test suite via Podman
podman-compose -f docker-compose.test.yml up --build cpp-test
```

#### Development Mode (Individual Services)

If you need to run services individually for development:

```bash
# Start backend only
docker-compose up backend

# Start frontend only (requires backend running)
cd frontend && npm run dev

# Start databases only
docker-compose up db redis
```

#### Previous CLI Commands (Archived)

The previous CLI interface using `main.py` has been archived. If you need to restore the vanilla JavaScript dashboard for comparison or testing, see `archive/README.md` for restoration instructions.

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

Access the web dashboard at `http://localhost:3000` after running:

```bash
docker-compose up
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
  - **Automatic ML Service Management**: Backend support services start automatically
  - **Trading Integration**: ML predictions available for simulated and live trading

## 🤖 Machine Learning Trading Optimization

The ML Trading Optimization system enhances trading decisions using machine learning:

### ML System Architecture

```text
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Trading Bot   │    │  ML Optimizer   │    │ Support Svcs   │
│                 │    │                 │    │                │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌────────────┐ │
│ │ Order Book  │ │───▶│ │ Data        │ │───▶│ │ Postgres   │ │
│ │ Strategy    │ │    │ │ Collector   │ │    │ │ + Redis    │ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └────────────┘ │
│                 │    │                 │    │                │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌────────────┐ │
│ │ ML Enhanced │ │◀───│ │ Model       │ │◀───│ │ ONNX       │ │
│ │ Strategy    │ │    │ │ Manager     │ │    │ │ Artifacts  │ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └────────────┘ │
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
- **Model Management**: Versioning, deployment, and rollback
- **Real-time Inference**: Sub-second ML predictions during trading

### ML Services (Automatically Started with Docker Compose)

- **Redis Cache**: `localhost:6379` - High-performance caching
- **PostgreSQL DB**: `localhost:5432` - Main database
- **Backend API**: `http://localhost:8000` - FastAPI backend server
- **Web Dashboard**: `http://localhost:3000` - Next.js React dashboard

### ML Service Management

- **Automatic Startup**: All ML services start automatically with `docker-compose up`
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

## 🔧 Troubleshooting

### Common Issues

#### ML Services Not Starting

```bash
# Check if Redis is installed
which redis-server

# Install missing services
# For macOS with Homebrew:
brew install redis

# For Ubuntu/Debian:
sudo apt-get install redis-server
```

#### Port Conflicts

If ports 3000, 8000, 6379, or 5432 are already in use:

```bash
# Check what's using the ports
lsof -i :3000  # Frontend
lsof -i :8000  # Backend
lsof -i :6379  # Redis
lsof -i :5432  # PostgreSQL

# Stop conflicting services or modify ports in docker-compose.yml
```

#### ML Model Training Issues

```bash
# Start the application with Docker Compose
docker-compose up

# Access the dashboard at http://localhost:3000
# Use the ML Analytics tab to start simulated trading and generate training data
```

#### Service Health Checks

```bash
# Check service status
redis-cli -p 6379 ping                  # Redis
curl http://localhost:8000/health       # Backend API
curl http://localhost:3000/api/health   # Frontend API
```

## 🤝 Contributing

Please read the development rules in the `rules/` directory before contributing.

## 📄 License

This project is proprietary software. All rights reserved.
