# 🏗️ System Architecture

## 🎯 Overview

This document provides a detailed overview of the system architecture for the Advanced Trading Bot. The system is designed to be modular, scalable, and resilient, with a clear separation of concerns between its various components.

## 📦 Core Components

The system is divided into several core components, each with a specific responsibility:

### 1. **Core Engine** (`src/trade_bot/core/`)

- **`TradingBot`**: The main orchestration engine that manages the trading lifecycle, including strategy execution, risk management, and order placement.
- **`TradingConfig`**: A centralized configuration management system that loads settings from environment variables and provides a unified interface for accessing configuration values.

### 2. **Data Layer** (`src/trade_bot/data/`)

- **`DataProvider`**: A unified interface for accessing market data from various sources, including real-time data from WebSocket streams and historical data from APIs.
- **`CachedDataProvider`**: A caching layer that sits on top of the `DataProvider` to reduce redundant API calls and improve performance.
- **`WebSocketClient`**: A high-performance WebSocket client for streaming real-time market data from Coinbase Advanced Trading.
- **`DataHandler`**: A component responsible for processing and storing incoming market data, including ticker data, order book updates, and trade executions.

### 3. **Database Layer** (`src/trade_bot/database/`)

- **`DatabaseManager`**: A centralized manager for all database operations, providing a consistent interface for interacting with the SQLite database.
- **Schema**: The database schema is designed to store trading history, portfolio snapshots, and other relevant data for analysis and reporting.

### 4. **Trading Engine** (`src/trade_bot/trading/`)

- **`SimulatedTradingManager`**: A manager for simulated trading sessions, allowing for backtesting and strategy evaluation without risking real capital
  - **Order Prioritization**: Configurable execution priority (signal strength, win probability, expected return)
  - **Signal Tracking**: Waits for all symbols to have signals before executing trades
  - **Performance Monitoring**: Real-time tracking of positions, P&L, and trading statistics
- **`BaseStrategy`**: An abstract base class that defines the interface for all trading strategies
- **Strategies**: A collection of trading strategies, including:
  - Simple Moving Average (SMA)
  - Relative Strength Index (RSI)
  - MACD, Bollinger Bands, ATR, Stochastic
  - ML Enhanced Order Book (with real-time ML predictions)
  - Buy and Hold, DCA

### 5. **Machine Learning System** (`src/trade_bot/ml/`)

- **`MLTradingOptimizer`**: Main orchestration system for ML trading optimization
- **`DataCollector`**: Extracts and preprocesses trading data from databases (SQLite/PostgreSQL)
- **`FeatureEngineer`**: Transforms raw trading data into ML-ready features with scaling and selection
- **`ModelTrainer`**: Trains ensemble ML models (Random Forest, Gradient Boosting, Neural Networks, SGD Regressor)
  - **Batch Training Support**: Memory-efficient processing of large datasets
  - **Incremental Learning**: SGD regressor for online learning
- **`ModelManager`**: Handles model versioning, deployment, rollback, and performance monitoring for signal prediction models
- **`FeatureModelManager`**: Manages the lifecycle of hot-swappable feature generation models
- **`VectorDBClient`**: Manages Qdrant vector database for feature vector storage and similarity search
- **`MLServer`**: FastAPI server providing REST API for model inference and management
- **`TrainingManager`**: Manages training configuration and defaults

### 6. **Web Interface** (`src/trade_bot/web/` and `frontend/`)

**Backend (`src/trade_bot/web/`)**:
- **`WebServer`**: A FastAPI-based web server that provides a RESTful API for interacting with the trading bot and a real-time web dashboard for monitoring its performance.
- **`WebSocketManager`**: A manager for WebSocket connections, allowing for real-time communication between the backend and the web dashboard.
- **Handlers**: A collection of request handlers for processing API requests and managing the flow of data between the backend and the frontend.
  - `ml_handler.py`: ML model training, management, and prediction endpoints
  - `trading_handlers.py`: Simulated and live trading session management
  - `dashboard_handlers.py`: Dashboard data aggregation and statistics

**Frontend (`frontend/`)**:
- **Next.js Application**: Modern React-based dashboard with TypeScript
- **Tab-Based Navigation**: ML Analytics, Simulated Trading, Live Trading, Backtesting
- **Key Components**:
  - `MLAnalyticsDashboard.tsx`: ML model management with batch training controls
  - `SimulatedTradingPanel.tsx`: Paper trading with order prioritization
  - `LiveTradingPanel.tsx`: Real capital trading interface
  - `OrderBookSignalsTable.tsx`: Real-time signal tracking with persistent updates
  - `PredictionComparisonChart.tsx`: Side-by-side model comparison
- **State Management**: Custom hooks for API integration (`useModelTraining`, `useOrderBookSignals`)
- **Real-time Updates**: WebSocket integration for live data streaming

## 🌐 Data Flow

The following diagram illustrates the flow of data through the system, including the ML-based feature generation and frontend interaction:

```
[Coinbase API] → [WebSocketClient] → [DataHandler] → [DatabaseManager]
                                          |
                                          v
                                [MLDataCollector] → [FeatureGenerationModel] → [FeatureEngineer] → [ModelTrainer]
                                          |                                                              |
                                          v                                                              v
                                [TradingBot] → [SimulatedTradingManager] → [DatabaseManager]    [Model Files]
                                          |              |
                                          v              v
                                [WebServer] ← [ML Endpoints]
                                          |
                                          v
                                [WebSocket Broadcast]
                                          |
                                          v
[Frontend Dashboard] ← ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
    |
    ├─ ML Analytics Tab
    ├─ Simulated Trading Tab
    ├─ Live Trading Tab
    └─ Backtesting Tab
```

1.  **Data Ingestion**: The `WebSocketClient` connects to the Coinbase Advanced Trading API and streams real-time market data.
2.  **Data Processing**: The `DataHandler` processes the incoming data and stores it in the database via the `DatabaseManager`.
3.  **ML Feature Generation**: The `MLDataCollector` retrieves raw order book data, processes it with a hot-swappable `FeatureGenerationModel` to create learned features, and combines them with statistical features.
4.  **Model Training**: The `ModelTrainer` trains ensemble models (including SGD regressor for batch training) on processed features.
5.  **Trading Logic**: The `TradingBot` retrieves market data and ML-enhanced features to execute trading strategies.
6.  **Strategy Execution**: The `SimulatedTradingManager` executes trades based on signals, with configurable order prioritization (signal strength, win probability, or expected return).
7.  **Web Interface**: The `WebServer` provides RESTful API endpoints and WebSocket broadcasting to the frontend dashboard.
8.  **Frontend Dashboard**: React/TypeScript application with four main tabs:
     - **ML Analytics**: Model training, performance tracking, predictions comparison
     - **Simulated Trading**: Paper trading with real-time signals and position tracking
     - **Live Trading**: Real capital trading with ML enhancement
     - **Backtesting**: Historical strategy validation
9.  **Real-time Updates**: WebSocket connections stream live trading data, signals, and ML predictions to the frontend.

## 🚀 Deployment

The system is designed for a flexible, container-based deployment using Docker and Docker Compose. The root `docker-compose.yml` orchestrates the entire project, while component-specific `docker-compose.yml` files (e.g., in `frontend/`) allow for individual services to be run independently.

For a comprehensive guide on the deployment options, please see the [DEPLOYMENT.md](DEPLOYMENT.md) file.
