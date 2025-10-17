# ML Trading Optimization System

This document describes the Machine Learning Trading Optimization system implemented for the Trading Bot project. The system uses machine learning to optimize order book analysis and trading decisions.

## Overview

The ML Trading Optimization system consists of several key components:

1. **Data Collection & Preprocessing** - Extracts order book signals and trade outcomes
2. **Feature Engineering** - Creates ML-ready feature vectors from raw trading data
3. **Model Training** - Trains ensemble ML models for trading signal prediction
4. **Vector Database** - Stores feature vectors for similarity search and pattern matching
5. **Model Management** - Handles model versioning, deployment, and rollback
6. **Integration** - ML-enhanced order book strategy with real-time inference
7. **Validation** - Backtesting and performance comparison tools

## Architecture

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
                       │                 │
                       │ ┌─────────────┐ │
                       │ │ FastAPI     │ │
                       │ │ Endpoints   │ │
                       │ └─────────────┘ │
                       └─────────────────┘
```

## Components

### 1. Data Collection (`src/trade_bot/ml/data_collector.py`)

Extracts and preprocesses trading data from the database:

- **Order Book Signals**: Bid-ask imbalances, spreads, wall detection
- **Trade Outcomes**: P&L, fees, duration, signal effectiveness
- **Feature Vectors**: Structured data for ML training

Key features:
- Historical data extraction with configurable time windows
- Feature vector creation from order book patterns
- Trade outcome labeling for supervised learning

### 2. Feature Engineering (`src/trade_bot/ml/feature_engineer.py`)

Transforms raw trading data into ML-ready features:

- **Order Book Features**: Imbalance ratios, spread metrics, volume analysis
- **Technical Indicators**: Momentum, volatility, trend strength
- **Derived Features**: Interaction terms, time series features
- **Scaling & Selection**: Standardization and feature importance selection

### 3. Model Training (`src/trade_bot/ml/model_trainer.py`)

Trains multiple ML models and selects the best performer:

- **Ensemble Models**: Random Forest, Gradient Boosting, Neural Networks
- **Hyperparameter Tuning**: Grid search optimization
- **Cross-Validation**: Robust performance evaluation
- **Trading Metrics**: Profit factor, Sharpe ratio, risk-adjusted returns

### 4. Vector Database (`src/trade_bot/ml/vector_db_client.py`)

Manages feature vector storage and similarity search:

- **Qdrant Integration**: High-performance vector database
- **Similarity Search**: Find similar market conditions
- **Real-time Updates**: Continuous feature vector storage
- **Pattern Matching**: Historical pattern recognition

### 5. Model Management (`src/trade_bot/ml/model_manager.py`)

Handles model lifecycle management:

- **Versioning**: Track model versions and performance
- **Deployment**: Hot-swap models without trading interruption
- **Rollback**: Revert to previous model versions
- **Performance Monitoring**: Continuous model evaluation

### 6. ML-Enhanced Strategy (`src/trade_bot/trading/strategies/ml_enhanced_orderbook.py`)

Integrates ML predictions into trading decisions:

- **Real-time Inference**: Live ML predictions during trading
- **Fallback Mechanism**: Baseline strategy when ML fails
- **Confidence Thresholds**: Only act on high-confidence predictions
- **Performance Tracking**: Monitor ML vs baseline performance

## Setup and Installation

### Prerequisites

- Python 3.11+
- Podman or Docker
- Redis
- Qdrant Vector Database

### 1. Install Dependencies

```bash
pip install -r config/requirements.txt
pip install scikit-learn pandas numpy joblib requests
```

### 2. Start Vector Database Services

```bash
# Start Qdrant, Redis, and ML Model Server
./scripts/ml/start_vector_db.sh
```

### 3. Train Initial Models

```bash
# Train ML models on historical data
python scripts/ml/train_models.py --days-back 30 --model-type ensemble
```

### 4. Test Integration

```bash
# Run comprehensive integration tests
python scripts/ml/test_integration.py
```

## Usage

### Training Models

```bash
# Train with default settings
python scripts/ml/train_models.py

# Train with custom parameters
python scripts/ml/train_models.py \
    --days-back 60 \
    --model-type ensemble \
    --min-samples 200
```

### Model Management

```bash
# List all models
python scripts/ml/manage_models.py list

# Deploy a specific model version
python scripts/ml/manage_models.py deploy trading_optimizer --version v20241201_143022

# Rollback to previous version
python scripts/ml/manage_models.py rollback trading_optimizer

# Evaluate current model
python scripts/ml/manage_models.py evaluate

# Clean up old versions
python scripts/ml/manage_models.py cleanup trading_optimizer --keep 3
```

### Strategy Validation

```bash
# Compare ML-enhanced vs baseline strategy
python scripts/ml/validate_strategy.py \
    --start-date 2024-01-01 \
    --end-date 2024-01-31 \
    --symbol BTC-USD
```

### Web Dashboard

The ML system integrates with the web dashboard at `http://localhost:8001`:

- **ML Status**: Model training status and performance
- **Feature Importance**: Most important trading features
- **Model Controls**: Train, update, and rollback models
- **Performance Metrics**: Real-time model performance

## API Endpoints

The ML Model Server provides REST API endpoints:

### Model Status
- `GET /status` - Get ML system status
- `GET /performance` - Get model performance metrics
- `GET /features/importance` - Get feature importance scores

### Model Control
- `POST /train` - Trigger model training
- `POST /update` - Update model with new data
- `POST /rollback` - Rollback to previous version

### Prediction
- `POST /predict` - Get trading signal prediction

## Configuration

### Vector Database (`config/vector-db-config.yaml`)

```yaml
qdrant:
  host: "localhost"
  port: 6333
  collection_name: "trading_features"
  vector_size: 128

redis:
  host: "localhost"
  port: 6380
  max_memory: "512MB"

ml_server:
  host: "localhost"
  port: 8002
  model_cache_size: 5
```

### ML Strategy Parameters

```python
MLEnhancedOrderBookStrategy(
    config=config,
    ml_server_url="http://localhost:8002",
    fallback_to_baseline=True,
    confidence_threshold=0.6
)
```

## Performance Monitoring

### Key Metrics

- **R² Score**: Model prediction accuracy
- **RMSE**: Root mean square error
- **Profit Factor**: Gross profit / Gross loss
- **Sharpe Ratio**: Risk-adjusted returns
- **Win Rate**: Percentage of profitable trades

### Monitoring Tools

- **Prometheus**: Metrics collection (`http://localhost:9090`)
- **Model Performance History**: Track performance over time
- **Feature Importance Tracking**: Monitor feature relevance
- **Real-time Alerts**: Performance degradation detection

## Troubleshooting

### Common Issues

1. **ML Server Not Responding**
   ```bash
   # Check service status
   podman-compose -f podman-compose-vector-db.yml ps
   
   # Check logs
   podman-compose -f podman-compose-vector-db.yml logs ml_model_server
   ```

2. **No Training Data**
   ```bash
   # Check database for signals and trades
   sqlite3 data/databases/trading_cache.db "SELECT COUNT(*) FROM order_book_signals;"
   sqlite3 data/databases/trading_cache.db "SELECT COUNT(*) FROM individual_trades;"
   ```

3. **Model Performance Degradation**
   ```bash
   # Rollback to previous version
   python scripts/ml/manage_models.py rollback trading_optimizer
   
   # Retrain with more data
   python scripts/ml/train_models.py --days-back 60
   ```

### Logs

- **Training Logs**: `outputs/ml_training_*.log`
- **Integration Tests**: `outputs/ml_integration_test_*.log`
- **Validation Reports**: `outputs/ml_validation_*.log`
- **Model Management**: `outputs/ml_model_management_*.log`

## Development

### Adding New Features

1. **New Feature Types**: Extend `FeatureEngineer` class
2. **New Models**: Add to `ModelTrainer` ensemble
3. **New Strategies**: Inherit from `MLEnhancedOrderBookStrategy`
4. **New Metrics**: Add to validation and monitoring

### Testing

```bash
# Run integration tests
python scripts/ml/test_integration.py

# Run strategy validation
python scripts/ml/validate_strategy.py --start-date 2024-01-01 --end-date 2024-01-07

# Test model management
python scripts/ml/manage_models.py list
```

## Future Enhancements

- **Reinforcement Learning**: Dynamic strategy adaptation
- **Multi-Symbol Models**: Cross-symbol pattern recognition
- **Real-time Learning**: Continuous model updates
- **Advanced Features**: Market microstructure analysis
- **Risk Management**: ML-based position sizing
- **Portfolio Optimization**: Multi-strategy coordination

## Contributing

1. Follow the existing code structure and patterns
2. Add comprehensive tests for new features
3. Update documentation for API changes
4. Ensure backward compatibility
5. Test with real trading data

## License

This ML Trading Optimization system is part of the Trading Bot project and follows the same license terms.
