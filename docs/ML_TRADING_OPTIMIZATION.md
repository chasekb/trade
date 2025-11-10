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


## 🚀 Usage

The ML Trading Optimization system is integrated into the main application and can be managed through the web dashboard and API endpoints.

### 1. Starting the ML Services

The vector database and ML model server are started automatically when you run the main application:

```bash
python main.py web
```

This command will start all the necessary services, including Qdrant, Redis, and the ML model server.

### 2. Training Models

Models can be trained through the web dashboard or by calling the `/api/ml/train` API endpoint.

### 3. Model Management

Model management, including deploying, rolling back, and evaluating models, can be done through the web dashboard.

### 4. Strategy Validation

The performance of the ML-enhanced strategy can be validated through the backtesting interface in the web dashboard.

### Web Dashboard

The ML system integrates with the web dashboard at `http://localhost:3000`:

- **ML Status**: Model training status and performance
- **Feature Importance**: Most important trading features
- **Model Controls**: Train, update, and rollback models
- **Performance Metrics**: Real-time model performance
- **PnL Tracking**: Display top and bottom trades by PnL
- **Model Selection**: Switch between different ML models
- **Prediction Comparison**: Compare predictions from all models

## Web Dashboard Integration Plan

### Overview

The current ML system provides comprehensive API endpoints but lacks web UI integration. This integration plan outlines implementing ML monitoring, management, and usage capabilities directly within the trading dashboard.

### Phase 1: ML Monitoring Dashboard

#### 1.1 Create ML Dashboard Components

**Frontend Integration:**
- Add "ML Analytics" tab to main dashboard navigation
- Create ML status cards showing system health, model availability, and vector database connectivity
- Integrate feature importance visualization with interactive charts
- Display real-time performance metrics (R², RMSE,PnL ratios, Sharpe ratio)

**Backend Requirements:**
- Extend `dashboard_handlers.py` with ML data retrieval methods
- Create ML-specific routes in `ml_routes.py` for dashboard serving
- Implement real-time ML status updates via WebSocket integration

**Technical Implementation:**
```python
# Add to web_routes/ml_routes.py
@router.get("/ml-dashboard", response_class=HTMLResponse)
async def get_ml_dashboard(request: Request):
    """Serve ML monitoring dashboard."""
    return templates.TemplateResponse("ml_dashboard.html", {"request": request})

# Add to web_handlers/dashboard_handlers.py
async def get_ml_system_overview(self) -> Dict[str, Any]:
    """Get comprehensive ML system overview for dashboard."""
    # Combine status, performance, and feature importance data
    return await self.ml_integration.get_ml_dashboard_data()
```

#### 1.2 ML Status Monitoring

**Real-time Status Display:**
- Model training status indicators (idle, training, completed, failed)
- Vector database connectivity and collection health
- ML optimizer availability and initialization status
- Last model update timestamp and version

**Performance Metrics Dashboard:**
- Interactive charts for R² score, RMSE trends over time
- Profit factor and Sharpe ratio visualizations
- Win rate with confidence intervals
- Feature importance bar charts with hover details

### Phase 2: ML Management Interface

#### 2.1 Training Controls

**Manual Training Interface:**
- One-click model training with progress indicators
- Training parameter controls (days back, model types, hyperparameters)
- Real-time training progress with estimated completion
- Training history and comparison of model versions

**Automated Training Features:**
- Scheduled training intervals configuration
- Threshold-based retraining triggers (performance degradation)
- Model validation metrics display during training

#### 2.2 Model Management

**Model Version Control:**
- Current active model display with version info
- Model history table with performance metrics
- Version comparison tools (side-by-side metrics)
- Rollback interface with confirmation dialogs

**Model Deployment:**
- Hot-swap capability without trading interruption
- A/B testing interface for new model validation
- Gradual rollout controls (percentage of trades)

#### 2.3 Model Update Interface

**Incremental Learning:**
- Manual update triggers for new data ingestion
- Automated daily updates scheduling
- Update status monitoring with progress bars
- Rollback options if updates degrade performance

### Phase 3: Live Trading Integration

#### 3.1 ML Strategy Selection

**Strategy Configuration:**
- Add "ML Enhanced Strategy" to live trading strategy dropdown
- ML confidence threshold slider (0.1 - 1.0)
- Fallback mode toggle (ML → Baseline on failure)
- Real-time ML prediction confidence display

**Enhanced Strategy Settings:**
```
Strategy Type: ML Enhanced Order Book Analysis
├── ML Model: trading_optimizer_v20241201
├── Confidence Threshold: 0.65
├── Fallback Strategy: orderbook_analysis
├── Update Frequency: real-time
└── Performance Tracking: enabled
```

#### 3.2 Live ML Monitoring

**During Live Trading:**
- Real-time ML prediction confidence gauge
- ML vs baseline performance comparison
- Feature importance updates during active trading
- ML signal strength indicators on order book data

**Trading Decision Tracking:**
- Log when ML predictions override baseline signals
- Track ML prediction accuracy in real-time
- Display last N ML decisions with outcomes

#### 3.3 ML-Alerts Integration

**Alert Types:**
- ML model confidence threshold breaches
- Performance degradation warnings
- Model staleness alerts (outdated training data)
- Feature drift detection notifications

### Phase 4: Advanced Features

#### 4.1 Historical ML Analysis

**ML Backtesting Section:**
- Dedicated ML strategy backtesting with historical analysis
- Compare ML performance across different market conditions
- Feature importance evolution over time
- Model robustness testing across symbols

#### 4.2 ML Model Insights

**Deep Learning Analytics:**
- Model interpretability visualizations
- Feature contribution analysis per prediction
- Prediction uncertainty quantification
- Model ensemble voting transparency

### Technical Implementation Details

#### Frontend Architecture

**ML Dashboard Template (`templates/ml_dashboard.html`):**
```html
<!-- ML Status Cards -->
<div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
    <div class="card-enhanced p-6">
        <h3 class="text-lg font-semibold">Model Status</h3>
        <div id="model-status" class="status-indicator">Ready</div>
    </div>
    <!-- Additional status cards -->
</div>

<!-- ML Performance Charts -->
<div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
    <div class="card-enhanced p-6">
        <h3 class="text-lg font-semibold">Performance Metrics</h3>
        <canvas id="performance-chart"></canvas>
    </div>
    <!-- Additional charts -->
</div>

<!-- ML Controls -->
<div class="card-enhanced p-6">
    <h3 class="text-lg font-semibold">Model Management</h3>
    <button id="train-model" class="btn-primary">Train New Model</button>
    <button id="update-model" class="btn-success">Update Model</button>
    <button id="rollback-model" class="btn-danger">Rollback</button>
</div>
```

**Live Trading ML Integration:**
```html
<!-- Add to live trading configuration -->
<div class="mb-6">
    <label class="block text-sm font-medium text-gray-700 mb-2">
        ML Enhancement
    </label>
    <div class="flex items-center space-x-4">
        <label class="flex items-center">
            <input type="checkbox" id="enable-ml" class="mr-2">
            <span class="text-sm">Enable ML Enhancement</span>
        </label>
        <div class="flex items-center space-x-2">
            <span class="text-sm">Confidence:</span>
            <input type="range" id="ml-confidence-threshold" min="0.1" max="1.0" step="0.05" value="0.6">
            <span id="confidence-value">0.6</span>
        </div>
    </div>
</div>
```

#### JavaScript Integration

**ML Data Fetching (`static/js/ml_dashboard.js`):**
```javascript
// Real-time ML status updates
async function updateMLStatus() {
    try {
        const response = await fetch('/api/ml/dashboard');
        const data = await response.json();

        // Update status indicators
        updateModelStatus(data.status);
        updatePerformanceMetrics(data.performance);
        updateFeatureImportance(data.feature_importance);
    } catch (error) {
        console.error('Error fetching ML data:', error);
    }
}

// ML training progress
async function trainModel() {
    try {
        const response = await fetch('/api/ml/train', { method: 'POST' });
        const result = await response.json();

        if (result.status === 'success') {
            showTrainingProgress();
        }
    } catch (error) {
        showError('Training failed: ' + error.message);
    }
}
```

#### Backend Extensions

**New ML Routes:**
```python
# src/trade_bot/web/web_routes/ml_routes.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/ml-dashboard", response_class=HTMLResponse)
async def ml_dashboard(request: Request):
    """Serve ML monitoring dashboard."""
    return templates.TemplateResponse("ml_dashboard.html", {"request": request})

@router.get("/api/ml/realtime-status")
async def get_ml_realtime_status():
    """Get real-time ML system status."""
    # Implementation in MLDashboardIntegration
```

**Web Server Integration:**
```python
# Add to web_server.py, in startup_event()
from ..web.web_routes import ml_routes

app.include_router(ml_routes.router)

# Add ML state to application state
app_state_local.ml_dashboard_integration = MLDashboardIntegration()
```

### Implementation Timeline

#### Phase 1 (Week 1-2): ML Monitoring Dashboard ✅ COMPLETED
- [x] Create ML dashboard template (`ml_dashboard.html`)
- [x] Implement ML routes (`ml_routes.py`)
- [x] Add ML status and performance display
- [x] Integrate feature importance charts

#### Phase 2 (Week 3): ML Management Interface
- [ ] Implement training controls and progress tracking
- [ ] Add model version management interface
- [ ] Create model update and rollback functionality

#### Phase 3 (Week 4): Live Trading Integration
- [ ] Integrate ML strategy selection in live trading tab
- [ ] Add real-time ML monitoring during live trading
- [ ] Implement ML alert system

#### Phase 4 (Week 5): Advanced Features
- [ ] Add ML backtesting capabilities
- [ ] Implement deep learning analytics
- [ ] Performance optimization and polishing

### Success Metrics

**User Experience:**
- ML dashboard loads within 3 seconds
- Real-time updates every 5 seconds during monitoring
- Training progress updates every 2 seconds
- No UI blocking during ML operations

**Functionality:**
- 100% coverage of ML API endpoints in web UI
- Consistent error handling and loading states
- Mobile-responsive design for all ML interfaces
- WebSocket integration for real-time status updates

**Performance:**
- ML dashboard memory usage under 50MB
- API response times under 500ms for monitoring endpoints
- Training operations don't impact trading performance
- Efficient data caching for repeated requests

### Testing and Validation

**Unit Tests:**
- ML dashboard component rendering
- API endpoint integration
- Form validation for ML controls
- Error state handling

**Integration Tests:**
- End-to-end ML training workflow
- Live trading with ML enhancement
- Model rollback and recovery
- Real-time monitoring accuracy

**Performance Tests:**
- Concurrent user load testing
- Memory usage during extended monitoring
- Network latency impact on real-time features
- Database query performance under load

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
- `GET /models` - Get a list of available models
- `POST /models/set_active` - Set the active model

### Prediction
- `POST /predict` - Get trading signal prediction
- `POST /prediction-comparison` - Get a comparison of predictions from all models

### PnL Tracking
- `GET /pnl-trades` - Get top and bottom trades by PnL

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
   python main.py vector-db
   
   # Check logs (services run in foreground with integrated logging)
   # Logs are displayed in the terminal where the command is run
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
