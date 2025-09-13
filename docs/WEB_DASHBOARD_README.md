# 🚀 Trading Dashboard Web Server

A comprehensive web-based trading dashboard that displays real-time data, historical data, backtesting results, and trading ROI metrics.

## ✨ Features

### 📊 Real-time Data
- Live price updates via WebSocket
- Real-time ticker information
- 24-hour volume and price changes
- Connection status monitoring

### 📈 Historical Data
- Interactive charts with Plotly
- Multiple timeframes (3, 7, 14, 30 days)
- OHLCV data visualization
- Responsive design

### 🧮 Backtesting
- Run backtests directly from the web interface
- Multiple strategy parameters (SMA windows)
- Real-time backtest execution
- Performance metrics display

### 💰 Trading Metrics
- ROI calculations
- Win rate analysis
- Trade statistics
- Performance comparison

## 🚀 Quick Start

### 1. Install Dependencies
```bash
uv sync
```

### 2. Configure Environment
Make sure your `.env` file contains:
```env
COINBASE_API_KEY=your_api_key
COINBASE_API_SECRET=your_api_secret
COINBASE_PASSPHRASE=your_passphrase
TRADING_PRODUCT_ID=BTC-USD
```

### 3. Start the Web Server
```bash
uv run python web_dashboard.py
```

### 4. Access the Dashboard
Open your browser and navigate to:
- **Main Dashboard**: http://localhost:8001
- **API Documentation**: http://localhost:8001/docs
- **WebSocket Endpoint**: ws://localhost:8001/ws

## 🎯 Usage

### Real-time Data
The dashboard automatically connects to Coinbase WebSocket and displays:
- Current price with live updates
- 24-hour volume
- Price change indicators
- Connection status

### Historical Data
View historical price data with:
- Interactive candlestick charts
- Multiple timeframes
- Zoom and pan functionality
- Responsive design

### Running Backtests
1. Select a trading pair (BTC-USD, ETH-USD, ADA-USD)
2. Choose time period (3, 7, 14, or 30 days)
3. Set SMA parameters (short and long windows)
4. Click "Run Backtest"
5. View results and equity curve

### Trading Metrics
Monitor performance with:
- Total return percentage
- Win rate statistics
- Number of trades executed
- Best performing strategies

## 🔧 API Endpoints

### Real-time Data
- `GET /api/real-time-data` - Current market data
- `GET /api/historical-data` - Historical OHLCV data
- `WebSocket /ws` - Real-time data stream

### Backtesting
- `POST /api/run-backtest` - Execute backtest
- `GET /api/backtest-results` - Get all backtest results

### Metrics
- `GET /api/trading-metrics` - Performance metrics
- `GET /api/health` - Server health check

## 🎨 Features

### Modern UI
- Responsive design with Tailwind CSS
- Real-time updates without page refresh
- Interactive charts with Plotly
- Beautiful gradient backgrounds
- Font Awesome icons

### Real-time Updates
- WebSocket connection for live data
- Automatic reconnection on disconnect
- Live price charts
- Real-time metrics updates

### Backtesting Interface
- Easy parameter configuration
- Real-time backtest execution
- Results visualization
- Performance comparison

## 🛠️ Technical Stack

- **Backend**: FastAPI + Uvicorn
- **Frontend**: HTML5 + JavaScript + Tailwind CSS
- **Charts**: Plotly.js
- **WebSocket**: Native WebSocket API
- **Data**: Coinbase Advanced Trading API
- **Python**: asyncio, pandas, numpy

## 📱 Responsive Design

The dashboard is fully responsive and works on:
- Desktop computers
- Tablets
- Mobile phones
- Different screen sizes

## 🔒 Security

- Environment variable configuration
- No hardcoded API keys
- Secure WebSocket connections
- Input validation

## 🚀 Performance

- Asynchronous data processing
- Efficient WebSocket handling
- Cached historical data
- Optimized chart rendering

## 📊 Example Usage

1. **View Real-time Data**: The dashboard automatically loads and displays current BTC-USD price
2. **Run a Backtest**: Select ETH-USD, 7 days, SMA(5,20) and click "Run Backtest"
3. **Analyze Results**: View the equity curve and performance metrics
4. **Compare Strategies**: Run multiple backtests with different parameters

## 🎉 Success!

Your trading dashboard is now running with:
- ✅ Real-time data streaming
- ✅ Historical data visualization
- ✅ Interactive backtesting
- ✅ Performance metrics
- ✅ Modern responsive UI

Visit **http://localhost:8001** to start trading! 🚀
