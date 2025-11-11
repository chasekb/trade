# ML Data Flow Architecture

This document describes the complete data flow into and out of the Machine Learning models in the Trading Bot system. Understanding this flow is crucial for debugging, optimization, and extending the ML capabilities.

## Overview

The ML system processes trading data through a multi-stage pipeline that transforms raw market data into actionable trading signals. The flow involves data extraction, feature engineering, model inference, and signal generation.

## Data Flow Diagram

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Raw Market    │    │   Data          │    │   Feature       │    │   ML Model      │
│   Data          │───▶│   Collection    │───▶│   Engineering   │───▶│   Inference     │
│                 │    │                 │    │                 │    │                 │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │Order Book   │ │    │ │DataCollector │ │    │ │FeatureEngi- │ │    │ │ModelManager │ │
│ │Updates      │ │    │ │             │ │    │ │neer         │ │    │ │             │ │
│ ├─────────────┤ │    │ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
│ │Trade        │ │    │                 │    │                 │    │                 │
│ │Executions   │ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ ├─────────────┤ │    │ │Database     │ │    │ │Scaling &    │ │    │ │Prediction   │ │
│ │Signals      │ │    │ │Queries      │ │    │ │Selection    │ │    │ │Generation   │ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
                                                                 │
                                                                 ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Trading       │    │   Strategy      │    │   Order         │    │   Performance   │
│   Signal        │    │   Execution     │    │   Placement     │    │   Tracking     │
│                 │    │                 │    │                 │    │                 │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │Action       │ │    │ │ML Enhanced  │ │    │ │Buy/Sell     │ │    │ │P&L          │ │
│ │(Buy/Sell/   │ │    │ │Order Book   │ │    │ │Orders       │ │    │ │Calculation  │ │
│ │Hold)        │ │    │ │Strategy     │ │    │ └─────────────┘ │    │ ├─────────────┤ │
│ ├─────────────┤ │    │ └─────────────┘ │    │                 │    │ │Accuracy     │ │
│ │Confidence   │ │    │                 │    │ ┌─────────────┐ │    │ │Metrics      │ │
│ │Score        │ │    │ ┌─────────────┐ │    │ │Risk         │ │    │ └─────────────┘ │
│ └─────────────┘ │    │ │Fallback to  │ │    │ │Management   │ │    │                 │
└─────────────────┘    │ │Baseline      │ │    │ └─────────────┘ │    └─────────────────┘
                       └─────────────────┘                        │
                                                                 │
                                                                 ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Feedback      │    │   Model         │    │   Vector DB     │
│   Loop          │    │   Training      │    │   Updates       │
│                 │    │                 │    │                 │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │Trade        │ │    │ │Feature       │ │    │ │Similarity    │ │
│ │Outcomes     │ │    │ │Vectors       │ │    │ │Search       │ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Stage 1: Data Input Sources

### 1.1 Raw Market Data

The ML system receives data from multiple sources:

#### Order Book Data
- **Source**: Coinbase Advanced Trading WebSocket API
- **Format**: Real-time bid/ask updates
- **Fields**:
  - `bids`: List of [price, quantity] pairs
  - `asks`: List of [price, quantity] pairs
  - `timestamp`: Update timestamp
  - `product_id`: Trading pair (e.g., "BTC-USD")

#### Trade Execution Data
- **Source**: Database (`individual_trades` table)
- **Fields**:
  - `trade_id`: Unique trade identifier
  - `symbol`: Trading pair
  - `side`: "buy" or "sell"
  - `price`: Execution price
  - `size`: Trade quantity
  - `pnl`: Profit/Loss
  - `fees`: Trading fees
  - `timestamp`: Execution timestamp

#### Order Book Signals
- **Source**: Database (`order_book_signals` table)
- **Fields**:
  - `signal_id`: Unique signal identifier
  - `symbol`: Trading pair
  - `signal_type`: Type of signal (e.g., "orderbook_imbalance")
  - `strength`: Signal strength (0-1)
  - `price`: Current price
  - `spread`: Bid-ask spread
  - `imbalance`: Bid/ask volume imbalance
  - `mid_price`: Mid price
  - `best_bid/best_ask`: Best bid/ask prices
  - `order_book_depth`: Number of price levels
  - `volume`: Trading volume
  - `total_signals`: Total signals in session

### 1.2 Database Schema

#### SQLite/PostgreSQL Tables

**order_book_signals**
```sql
CREATE TABLE order_book_signals (
    signal_id TEXT PRIMARY KEY,
    session_id TEXT,
    symbol TEXT,
    signal_type TEXT,
    strength REAL,
    price REAL,
    timestamp INTEGER,
    signal_data TEXT,  -- JSON with order book details
    spread REAL,
    imbalance REAL,
    mid_price REAL,
    best_bid REAL,
    best_ask REAL,
    order_book_depth INTEGER,
    volume REAL,
    total_signals INTEGER
);
```

**individual_trades**
```sql
CREATE TABLE individual_trades (
    trade_id TEXT PRIMARY KEY,
    session_id TEXT,
    symbol TEXT,
    side TEXT,
    size REAL,
    price REAL,
    timestamp INTEGER,
    strategy_type TEXT,
    signal_reason TEXT,
    pnl REAL,
    fees REAL,
    created_at TEXT
);
```

## Stage 2: Data Collection & Preprocessing

### 2.1 DataCollector Class

**Location**: `src/trade_bot/ml/data_collector.py`

**Input Processing**:
1. **Query Historical Data**: Extract signals and trades from last N days (default 30)
2. **Database Abstraction**: Support both SQLite and PostgreSQL
3. **Data Validation**: Filter invalid/missing data
4. **Time Windowing**: Configurable lookback periods

**Key Methods**:
- `extract_order_book_signals(days_back=30)`: Get order book signals
- `extract_trade_outcomes(days_back=30)`: Get trade execution data
- `create_feature_vectors(signals, trades)`: Convert to ML features
- `create_training_labels(features, outcomes)`: Create supervised learning labels

### 2.2 Feature Vector Creation

**OrderBookFeatures Dataclass**:
```python
@dataclass
class OrderBookFeatures:
    timestamp: int
    symbol: str
    bid_ask_imbalance: float      # Volume ratio bids/asks
    spread_percent: float         # Bid-ask spread as percentage
    mid_price: float              # (best_bid + best_ask) / 2
    bid_volume: float             # Total bid volume (top 5 levels)
    ask_volume: float             # Total ask volume (top 5 levels)
    order_book_depth: int         # Number of price levels
    large_bid_wall: bool          # Bid wall > 1000 units
    large_ask_wall: bool          # Ask wall > 1000 units
    wall_size: float              # Size of largest wall
    volume_weighted_price: float  # VWAP calculation
    price_momentum: float         # Price change over recent signals
    volatility: float             # Price volatility measure
    prev_win_probability: float   # Previous ML prediction (if available)
    prev_expected_return: float   # Previous expected return
    prev_confidence: float        # Previous prediction confidence
```

**TradeOutcome Dataclass**:
```python
@dataclass
class TradeOutcome:
    trade_id: str
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    fees: float
    duration_seconds: int
    signal_type: str
    signal_strength: float
    entry_timestamp: int
    exit_timestamp: int
```

## Stage 3: Feature Engineering

### 3.1 FeatureEngineer Class

**Location**: `src/trade_bot/ml/feature_engineer.py`

**Feature Engineering Pipeline**:

1. **Basic Features**: Direct extraction from OrderBookFeatures
2. **Derived Features**:
   - `volume_ratio = bid_volume / (ask_volume + 1e-8)`
   - `spread_normalized = spread_percent / (mid_price + 1e-8)`
   - `wall_size_normalized = wall_size / (bid_volume + ask_volume + 1e-8)`
   - `momentum_normalized = price_momentum / (volatility + 1e-8)`

3. **Technical Indicators**:
   - `rsi_like = tanh(momentum / 5.0)` (RSI approximation)
   - `volatility_bands = min(volatility / 10.0, 1.0)`
   - `trend_indicator = tanh(momentum / (volatility + 1e-8) / 2.0)`
   - `macd_like = tanh(mid_price - vwap) / (mid_price * 0.01)`
   - `bollinger_bands_like = (upper - lower) / mid_price`

4. **Time Series Features**:
   - Rolling means and standard deviations
   - Historical feature windows (5, 10, 20 periods)

5. **Interaction Features**:
   - Polynomial combinations of key features
   - Cross-feature interactions

### 3.2 Feature Processing Pipeline

**Preprocessing Steps**:
1. **Missing Value Imputation**: Mean imputation for NaN values
2. **Feature Scaling**: StandardScaler or MinMaxScaler
3. **Feature Selection**: SelectKBest with f_regression scoring
4. **Time Series Enhancement**: Rolling statistics
5. **Interaction Terms**: Polynomial feature combinations

**Output**: Processed feature matrix (X) and target vector (y)

## Stage 4: Model Training

### 4.1 ModelTrainer Class

**Location**: `src/trade_bot/ml/model_trainer.py`

**Training Process**:

1. **Data Splitting**: Train/test split (default 80/20)
2. **Ensemble Training**:
   - Random Forest Regressor
   - Gradient Boosting Regressor
   - Neural Network Regressor
   - Ridge Regression

3. **Hyperparameter Tuning**: Grid search for optimal parameters
4. **Model Evaluation**: R², RMSE, MAE, profit factor, Sharpe ratio
5. **Best Model Selection**: Highest R² score

**Model Persistence**:
- Models saved to `data/models/` directory
- Metadata stored in JSON format
- Versioned model files with timestamps

### 4.2 Training Metrics

**Performance Metrics**:
- **R² Score**: Coefficient of determination
- **RMSE**: Root mean square error
- **MAE**: Mean absolute error
- **Profit Factor**: Gross profit / Gross loss
- **Sharpe Ratio**: Risk-adjusted returns (annualized)

## Stage 5: Model Inference

### 5.1 MLTradingOptimizer Class

**Location**: `src/trade_bot/ml/ml_optimizer.py`

**Inference Process**:

1. **Feature Extraction**: Convert current market data to features
2. **Preprocessing**: Apply same scaling/selection as training
3. **Model Prediction**: Generate signal value (-1 to 1)
4. **Signal Interpretation**:
   - `signal_value > 0.1` → "buy"
   - `signal_value < -0.1` → "sell"
   - `abs(signal_value) <= 0.1` → "hold"

5. **Confidence Calculation**: Based on signal strength
6. **Similar Conditions**: Vector similarity search

### 5.2 ML Server API

**Location**: `src/trade_bot/ml/server.py`

**Endpoints**:
- `POST /predict`: Real-time prediction
- `GET /status`: Model status and performance
- `POST /train`: Trigger model training
- `POST /update`: Update model with new data
- `GET /performance`: Get performance metrics

**Request Format**:
```json
{
  "symbol": "BTC-USD",
  "bid_ask_imbalance": 1.23,
  "spread_percent": 0.05,
  "mid_price": 45000.0,
  "bid_volume": 1500.0,
  "ask_volume": 1200.0,
  "order_book_depth": 25,
  "large_bid_wall": false,
  "large_ask_wall": true,
  "wall_size": 2500.0,
  "volume_weighted_price": 44980.0,
  "price_momentum": 2.5,
  "volatility": 15.0,
  "timestamp": 1638360000
}
```

**Response Format**:
```json
{
  "action": "buy",
  "confidence": 0.78,
  "signal_value": 0.65,
  "reason": "ML prediction: 0.650",
  "similar_conditions": 3,
  "timestamp": "2025-11-11T15:30:00Z"
}
```

## Stage 6: Trading Strategy Integration

### 6.1 MLEnhancedOrderBookStrategy

**Location**: `src/trade_bot/trading/strategies/ml_enhanced_orderbook.py`

**Integration Points**:

1. **ML Prediction Request**: HTTP call to ML server
2. **Confidence Thresholding**: Only act on high-confidence predictions
3. **Fallback Strategy**: OrderBookStrategy when ML fails
4. **Signal Tracking**: Monitor ML vs baseline performance

**Decision Logic**:
```python
if ml_prediction and confidence >= threshold:
    return ML signal
elif fallback_enabled:
    return baseline signal
else:
    return None  # No signal
```

### 6.2 ML Signal Strategy

**Location**: `src/trade_bot/trading/strategies/ml_signal.py`

**Alternative ML Integration**:
- Direct model loading (no server dependency)
- Local feature engineering
- Simplified prediction pipeline
- Training data management

## Stage 7: Vector Database Integration

### 7.1 VectorDBClient Class

**Location**: `src/trade_bot/ml/vector_db_client.py`

**Vector Operations**:

1. **Collection Management**: Create/recreate Qdrant collections
2. **Vector Storage**: Store processed feature vectors with metadata
3. **Similarity Search**: Find similar market conditions
4. **Historical Patterns**: Retrieve past similar situations

**Vector Metadata**:
```json
{
  "symbol": "BTC-USD",
  "timestamp": 1638360000,
  "bid_ask_imbalance": 1.23,
  "spread_percent": 0.05,
  "mid_price": 45000.0,
  // ... all features
}
```

### 7.2 Similarity Search

**Use Cases**:
- **Pattern Recognition**: Find similar market conditions
- **Confidence Boosting**: More similar conditions = higher confidence
- **Historical Analysis**: Understand past similar situations
- **Feature Enhancement**: Time-series context from similar patterns

## Stage 8: Feedback Loop

### 8.1 Performance Tracking

**Metrics Collection**:
- Prediction accuracy vs actual outcomes
- P&L attribution to ML signals
- Confidence calibration
- Model drift detection

### 8.2 Model Updates

**Retraining Triggers**:
- Performance degradation below threshold
- New data accumulation (weekly/monthly)
- Market regime changes
- Feature drift detection

**Update Process**:
1. Collect new training data
2. Retrain models with expanded dataset
3. Validate on holdout set
4. Deploy if performance improves
5. Rollback option if degradation occurs

## Data Flow Summary

### Input Data Types
1. **Real-time Order Book**: WebSocket streams
2. **Trade Executions**: Database records
3. **Historical Signals**: Database archives
4. **Market Data**: Price, volume, timestamps

### Processing Stages
1. **Collection**: Extract from databases
2. **Feature Engineering**: Transform to ML features
3. **Preprocessing**: Scale, select, enhance
4. **Training**: Fit models on historical data
5. **Inference**: Generate predictions
6. **Integration**: Apply to trading strategies
7. **Feedback**: Update models with outcomes

### Output Data Types
1. **Trading Signals**: Buy/sell/hold decisions
2. **Confidence Scores**: Prediction certainty
3. **Performance Metrics**: Accuracy, P&L, Sharpe ratio
4. **Feature Vectors**: Stored in vector database
5. **Model Metadata**: Version, performance, parameters

## Monitoring & Debugging

### Key Monitoring Points
- **Data Quality**: Missing values, outliers, data drift
- **Model Performance**: Accuracy, calibration, drift
- **System Health**: API response times, error rates
- **Trading Impact**: Signal acceptance rate, P&L attribution

### Common Issues
- **Data Staleness**: Old training data reduces performance
- **Feature Drift**: Market changes make features less predictive
- **Model Overfitting**: Poor generalization to new data
- **API Failures**: Network issues, server downtime
- **Vector DB Issues**: Connection problems, dimension mismatches

### Debugging Tools
- **Feature Importance**: Understand what drives predictions
- **Partial Dependence**: Visualize feature effects
- **Error Analysis**: Examine prediction failures
- **Backtesting**: Validate on historical data
- **A/B Testing**: Compare model versions

## Performance Characteristics

### Latency Requirements
- **Real-time Inference**: <100ms for live trading
- **Feature Engineering**: <50ms per prediction
- **Vector Search**: <200ms for similarity lookup
- **Model Loading**: <5 seconds on startup

### Throughput Requirements
- **Training**: Handle 10K+ samples efficiently
- **Inference**: 100+ predictions per second
- **Data Processing**: Handle high-frequency market data
- **Vector Storage**: Store millions of feature vectors

### Accuracy Targets
- **Prediction Accuracy**: >60% directional accuracy
- **Profit Factor**: >1.2 for ML signals
- **Sharpe Ratio**: >1.5 for ML-enhanced strategies
- **Confidence Calibration**: Well-calibrated probability estimates

This comprehensive data flow ensures the ML system can effectively learn from trading data and provide actionable signals while maintaining reliability and performance in a live trading environment.
