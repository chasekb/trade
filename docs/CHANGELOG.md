# 📝 Changelog

## [2.4.0] - 2025-11-12

### 🚀 Features
- **Hot-Swappable ML-Based Feature Generation**: Implemented a new system for generating features from raw order book data using hot-swappable machine learning models. This enhances the predictive power of the trading bot by moving from hand-crafted statistical features to learned representations of market microstructures.
- **FeatureModelManager**: Added a new manager for the lifecycle of feature generation models, including registration, versioning, and hot-swapping.
- **API Endpoints for Feature Generation**: Added new API endpoints to manage the feature generation models, allowing operators to list available models, switch the active model, and monitor their performance.
- **ML-Enhanced Order Book Strategy**: Integrated ML predictions into the order book trading strategy, allowing for more intelligent trading decisions.

### 📚 Documentation
- **Updated Architecture Documentation**: Updated `docs/ARCHITECTURE.md` to include the new `FeatureModelManager` and the revised data flow.
- **Updated ML Trading Optimization Documentation**: Updated `docs/ML_TRADING_OPTIMIZATION.md` to describe the new ML-based feature generation system, the role of the `FeatureModelManager`, and the updated workflow.
- **Updated ML Data Flow Documentation**: Updated `docs/ML_DATA_FLOW.md` to incorporate the new feature generation model.
- **New Feature Generation Documentation**: Created `docs/FEATURE_GENERATION.md` to provide a detailed explanation of the new feature generation system.
- **Updated Project Overview**: Updated `docs/PROJECT_OVERVIEW.md` to include the new feature and a link to the new documentation.

## [2.3.0] - 2025-11-10

### 🚀 Features
- **Order Book Signals**: Implemented comprehensive order book signals functionality.
- **Dynamic Universe Population**: Added a feature to dynamically populate the trading universe from the Coinbase API.
- **Initial Portfolio Size**: Added initial portfolio size and updated position sizing.
- **Rate Limiting**: Implemented configurable rate limiting for the Coinbase API.
- **Tooltips**: Added tooltips to the order book signals table, with model-driven contributions.
- **Live WebSocket Updates**: Implemented live WebSocket updates for simulated trading, including an open positions table and signals refresh.

### 🐛 Bug Fixes
- **Frontend**:
    - Repopulated order book signals on tab switch.
    - Correctly initialized and sent position size.
    - Fixed order book signals widget not updating after tab switch.
    - Fixed symbol input functionality in live and simulated trading tabs.
- **Backend**:
    - Resolved cascading failures in the ML pipeline.
    - Corrected column names in the data collector.
    - Fixed ML server container import errors with dual import support.
    - Resolved ML server timeout and training issues.
    - Fixed trade execution failures with detailed logging and cash management.
    - Resolved `AttributeError` in `CoinbaseDataProvider`.
    - Fixed WebSocket JSON import, implemented JSON-safe trading broadcast, and robust trade saves.
    - Fixed backend container errors related to Qdrant/Redis detection and data handler `NoneType`.
    - Fixed `Dockerfile` CMD to start the uvicorn web server.
- **Database**:
    - Fixed critical errors in PostgreSQL migration.

### 🏗️ Infrastructure
- **Database Migration**: Migrated from SQLite to PostgreSQL.
- **Docker-Optimized Entry Point**: Created a Docker-optimized entry point (`app.py`).
- **Full-Stack Deployment**: Created a comprehensive `docker-compose.yml` for full-stack deployment.

### 📚 Documentation
- **Deployment Guide**: Created `docs/DEPLOYMENT.md` to provide a clear and accurate guide to the various deployment options.
- **Architecture and Service Documentation**:
    - Updated `docs/ARCHITECTURE.md` to accurately reflect the container-based deployment model.
    - Corrected `docs/VECTOR_DATABASE_SERVICE.md` to describe the hybrid approach to service management.
- **Removed Broken Links**: Updated `docs/PROJECT_OVERVIEW.md` to remove a broken link.
- **Archival of Legacy Components**: Moved the outdated `vanilla_js_dashboard` to `docs/archive/vanilla_js_dashboard_legacy`.
- **ML System Documentation Updates**:
    - Enhanced `docs/ML_TRADING_OPTIMIZATION.md` with current implementation details including database abstraction, component descriptions, and API endpoints.
    - Updated `docs/ARCHITECTURE.md` with detailed ML system component descriptions.
    - Created comprehensive `docs/ML_DATA_FLOW.md` documenting the complete data flow into and out of ML models (8-stage pipeline, database schemas, API formats, monitoring).
    - Updated `docs/PROJECT_OVERVIEW.md` to reference the new ML data flow documentation.

## [2.2.0] - 2025-10-29

### 📚 Documentation Updates

#### Docker-Compose Deployment Alignment
- ✅ **Archived Outdated Documentation** - Moved obsolete docs to `docs/archive/` directory
- ✅ **Documentation Cleanup** - Removed references to deprecated JavaScript dashboard and old architecture
- ✅ **Organized Docs Structure** - Kept only current, relevant documentation for production deployment

#### Archived Files
- ✅ **README.md** - Contained outdated local development instructions
- ✅ **WEB_DASHBOARD_README.md** - Referenced removed JavaScript-based dashboard
- ✅ **TYPESCRIPT_TRANSITION.md** - Completed TypeScript migration documentation
- ✅ **TODO.md** - Comprehensive code review (now archived as completed)
- ✅ **CLEANUP_SUMMARY.md**, **OPTIMIZATION_SUMMARY.md**, **REFACTORING_SUMMARY.md** - JavaScript-era summaries
- ✅ **TEST_RESULTS.md** - Test artifacts moved to archive
- ✅ **spec.md** - Basic project specification
- ✅ **examples/** - Example scripts directory

#### Maintained Documentation
- ✅ **CHANGELOG.md** - This version history (updated)
- ✅ **SECURITY_SETUP.md** - Security configuration guide
- ✅ **PROJECT_OVERVIEW.md** - Current architecture overview
- ✅ **VECTOR_DATABASE_SERVICE.md** - Vector database documentation
- ✅ **WEBSOCKET_SUBSCRIPTIONS.md** - WebSocket integration docs
- ✅ **ML_TRADING_OPTIMIZATION.md** - ML features documentation
- ✅ **env.example** - Environment configuration template

### 🏗️ Architecture Documentation Updates

#### Current Stack Documentation
- ✅ **Updated Deployment Focus** - All documentation now aligned with docker-compose production deployment
- ✅ **Container Architecture** - Documented Next.js frontend (port 3000), FastAPI backend (port 8000), PostgreSQL, Redis, and Qdrant services
- ✅ **Production Readiness** - Emphasis on containerized deployment, health checks, and monitoring

### 🔧 Technical Documentation Improvements

#### Repository Organization
- ✅ **Clean Docs Structure** - Removed duplicate and outdated documentation
- ✅ **Version Control** - Proper timestamping of archived files for reference
- ✅ **Maintainability** - Improved documentation organization and relevance

## [2.1.0] - 2025-09-24

### 🔧 Simulated Trading Improvements

#### Session Management
- ✅ **Session-Based Trading History** - Trading history now only displays trades from the current trading session
- ✅ **Session ID Filtering** - API endpoints support filtering trades by session ID
- ✅ **Clean Session Management** - Removed unnecessary session saving/restoring for trading history

#### Database Enhancements
- ✅ **Trade Type Classification** - Added `trade_type` field to distinguish simulated vs live trades
- ✅ **Simulated Trade Marking** - All simulated trades are now properly marked as 'simulated' in database
- ✅ **Database Schema Update** - Added `trade_type` column to `individual_trades` table

#### Portfolio Status Fixes
- ✅ **Open Positions Count Fix** - Portfolio status widget now correctly decreases when positions are closed
- ✅ **Position Management** - Closed positions are properly removed from active positions dictionary
- ✅ **Real-time Updates** - Portfolio status accurately reflects current open positions

#### API Improvements
- ✅ **Enhanced Pagination** - Trading history API supports session-based filtering
- ✅ **Better Data Structure** - Improved trade data structure with trade type information
- ✅ **Consistent Session Tracking** - All simulated trades properly associated with session IDs

### 🐛 Bug Fixes
- Fixed open positions count not decreasing when positions are closed
- Fixed trading history showing all trades instead of current session trades
- Fixed simulated trades not being properly marked in database
- Improved position management in simulated trading manager

## [2.0.0] - 2025-09-13

### 🚀 Major Features Added

#### Web Dashboard
- ✅ **FastAPI Web Server** with real-time data streaming
- ✅ **Interactive Charts** using Plotly.js
- ✅ **Responsive Design** with Tailwind CSS
- ✅ **Real-time WebSocket** integration
- ✅ **Modern UI** with beautiful animations and gradients

#### Advanced Backtesting
- ✅ **Real Historical Data** from Coinbase API
- ✅ **Multiple Strategy Testing** with parameter optimization
- ✅ **Performance Metrics** (ROI, Sharpe ratio, max drawdown)
- ✅ **CSV Export** for detailed analysis
- ✅ **Comprehensive Reporting** with best strategy identification

#### Enhanced Trading Bot
- ✅ **Improved Configuration** with command-line arguments
- ✅ **Better Error Handling** and logging
- ✅ **Risk Management** enhancements
- ✅ **Data Provider** for historical data fetching

### 🔧 Technical Improvements

#### Code Organization
- ✅ **Structured Directory** layout
- ✅ **Separated Scripts** into dedicated folder
- ✅ **Comprehensive Documentation** with multiple README files
- ✅ **Example Scripts** for different use cases

#### Testing & Quality
- ✅ **Comprehensive Test Suite** with pytest
- ✅ **Unit Tests** for all core modules
- ✅ **Integration Tests** for WebSocket functionality
- ✅ **Backtesting Validation** tests

#### Documentation
- ✅ **Main README.md** with complete project overview
- ✅ **Web Dashboard README** with specific instructions
- ✅ **Project Overview** with architecture details
- ✅ **Changelog** for version tracking

### 📊 New Capabilities

#### Real-time Features
- Live price updates via WebSocket
- 24-hour volume and price changes
- Connection status monitoring
- Real-time chart updates

#### Backtesting Features
- Historical data from Coinbase API
- Multiple timeframes (3, 7, 14, 30 days)
- Strategy parameter optimization
- Performance comparison tools

#### Web Dashboard Features
- Interactive candlestick charts
- Real-time data visualization
- Backtesting interface
- Trading metrics display
- Performance analytics

### 🛠️ Configuration Enhancements

#### Command-line Arguments
```bash
python main.py --product ETH-USD --max-position 2000 --log-level DEBUG
```

#### Environment Variables
- Enhanced configuration management
- Better error handling for missing credentials
- Flexible output directory configuration

### 📁 Directory Structure

```
trade/
├── src/trade_bot/           # Core modules
├── scripts/                 # Executable scripts
├── examples/                # Example usage
├── tests/                   # Test suite
├── templates/               # Web templates
├── static/                  # Web assets
├── docs/                    # Documentation
├── outputs/                 # Generated data
└── main.py                  # Main entry point
```

### 🧪 Testing

#### Test Coverage
- **Backtester Tests**: 100% coverage
- **Data Provider Tests**: 100% coverage
- **Web Server Tests**: Core functionality
- **Integration Tests**: WebSocket and API

#### Test Commands
```bash
# All tests
uv run python -m pytest

# With coverage
uv run python -m pytest --cov=src/trade_bot

# Specific tests
uv run python -m pytest tests/test_backtester.py
```

### 🚀 Usage Examples

#### Trading Bot
```bash
# Basic usage
uv run python main.py

# With custom parameters
uv run python main.py --product ETH-USD --max-position 2000
```

#### Web Dashboard
```bash
# Start dashboard
uv run python scripts/web_dashboard.py

# Access at http://localhost:8001
```

#### Backtesting
```bash
# Simple backtest
uv run python scripts/backtest.py

# Comprehensive backtest
uv run python scripts/backtest_comprehensive.py
```

### 🔒 Security & Quality

- Environment variable configuration
- No hardcoded credentials
- Secure WebSocket connections
- Input validation and sanitization
- Comprehensive error handling

### 📈 Performance

- Asynchronous data processing
- Efficient WebSocket handling
- Cached historical data
- Optimized chart rendering
- Real-time updates without page refresh

## [1.0.0] - 2025-09-13

### 🎯 Initial Release

#### Core Features
- ✅ **WebSocket Trading Bot** with coinbase-advanced-py
- ✅ **Trading Strategy** implementation (SMA)
- ✅ **Data Handler** for storage and export
- ✅ **Configuration Management** with environment variables
- ✅ **Basic Testing** with pytest

#### Trading Capabilities
- Real-time market data via WebSocket
- Simple Moving Average strategy
- Golden Cross / Death Cross signals
- CSV data export
- Basic risk management

#### Technical Foundation
- Python 3.11+ support
- asyncio for asynchronous operations
- Type hints and dataclasses
- Comprehensive logging
- Git version control

---

## 🎉 Summary

This project has evolved from a basic trading bot to a comprehensive trading platform with:

- **Real-time Trading** capabilities
- **Advanced Backtesting** system
- **Modern Web Dashboard** with interactive charts
- **Comprehensive Testing** and documentation
- **Production-ready** code with proper error handling

The trading bot is now ready for both development and production use! 🚀📊💰
