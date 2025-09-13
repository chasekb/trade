/** Enhanced Trading Dashboard JavaScript with Full Subscription Support */

class EnhancedTradingDashboard {
    constructor() {
        this.ws = null;
        this.priceData = [];
        this.historicalData = [];
        this.backtestData = [];
        this.candlesData = [];
        this.charts = {};
        this.isConnected = false;
        this.subscriptions = {};
        this.dataSummary = {};
        this.currentCandlePeriod = 3600; // Default to 1 hour
        
        this.init();
    }

    init() {
        this.connectWebSocket();
        this.setupEventListeners();
        this.loadSubscriptions();
        
        // Load data after a short delay to ensure DOM is ready
        setTimeout(() => {
            this.loadInitialData();
            this.startDataRefresh();
        }, 100);
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.isConnected = true;
            this.updateConnectionStatus(true);
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWebSocketMessage(data);
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            this.isConnected = false;
            this.updateConnectionStatus(false);
            // Reconnect after 5 seconds
            setTimeout(() => this.connectWebSocket(), 5000);
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.isConnected = false;
            this.updateConnectionStatus(false);
        };
    }

    setupEventListeners() {
        // Subscription management
        document.getElementById('subscribe-btn').addEventListener('click', () => {
            this.subscribeToChannel();
        });
        
        document.getElementById('unsubscribe-btn').addEventListener('click', () => {
            this.unsubscribeFromChannel();
        });
        
        document.getElementById('refresh-subscriptions').addEventListener('click', () => {
            this.loadSubscriptions();
        });
        
        // Backtesting
        document.getElementById('run-backtest').addEventListener('click', () => {
            this.runBacktest();
        });
        
        // Candle period selector
        document.getElementById('candle-period').addEventListener('change', (e) => {
            this.currentCandlePeriod = parseInt(e.target.value);
            this.loadCandlesData();
        });
        
        // Refresh candles button
        document.getElementById('refresh-candles').addEventListener('click', () => {
            this.loadCandlesData();
        });
    }

    async subscribeToChannel() {
        const channel = document.getElementById('channel-select').value;
        const productId = document.getElementById('product-id').value;
        
        try {
            const response = await fetch('/api/subscribe', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    channel: channel,
                    product_id: productId
                })
            });
            
            const result = await response.json();
            if (result.success) {
                this.showNotification(`Subscribed to ${channel} for ${productId}`, 'success');
                this.loadSubscriptions();
            } else {
                this.showNotification(`Failed to subscribe: ${result.error}`, 'error');
            }
        } catch (error) {
            console.error('Subscription error:', error);
            this.showNotification('Failed to subscribe', 'error');
        }
    }

    async unsubscribeFromChannel() {
        const channel = document.getElementById('channel-select').value;
        const productId = document.getElementById('product-id').value;
        
        try {
            const response = await fetch('/api/unsubscribe', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    channel: channel,
                    product_id: productId
                })
            });
            
            const result = await response.json();
            if (result.success) {
                this.showNotification(`Unsubscribed from ${channel} for ${productId}`, 'success');
                this.loadSubscriptions();
            } else {
                this.showNotification(`Failed to unsubscribe: ${result.error}`, 'error');
            }
        } catch (error) {
            console.error('Unsubscription error:', error);
            this.showNotification('Failed to unsubscribe', 'error');
        }
    }

    async loadSubscriptions() {
        try {
            const response = await fetch('/api/subscriptions');
            const data = await response.json();
            
            if (data.error) {
                document.getElementById('subscription-list').innerHTML = 
                    `<span class="text-red-500">${data.error}</span>`;
                return;
            }
            
            this.subscriptions = data.channels || {};
            this.updateSubscriptionDisplay();
        } catch (error) {
            console.error('Failed to load subscriptions:', error);
            document.getElementById('subscription-list').innerHTML = 
                '<span class="text-red-500">Failed to load subscriptions</span>';
        }
    }

    updateSubscriptionDisplay() {
        const subscriptionList = document.getElementById('subscription-list');
        
        if (Object.keys(this.subscriptions).length === 0) {
            subscriptionList.innerHTML = '<span class="text-gray-500">No active subscriptions</span>';
            return;
        }
        
        let html = '<div class="space-y-2">';
        for (const [channel, products] of Object.entries(this.subscriptions)) {
            const productList = Array.from(products).join(', ');
            html += `
                <div class="flex items-center justify-between bg-white p-2 rounded border">
                    <span class="font-medium">${channel}</span>
                    <span class="text-sm text-gray-600">${productList}</span>
                </div>
            `;
        }
        html += '</div>';
        
        subscriptionList.innerHTML = html;
    }

    async loadDataSummary() {
        try {
            const response = await fetch('/api/data-summary');
            const data = await response.json();
            
            if (data.error) {
                console.error('Failed to load data summary:', data.error);
                return;
            }
            
            this.dataSummary = data;
            this.updateDataSummaryDisplay();
        } catch (error) {
            console.error('Failed to load data summary:', error);
        }
    }

    updateDataSummaryDisplay() {
        const summaryContainer = document.getElementById('data-summary');
        
        const dataTypes = [
            { key: 'ticker_records', label: 'Ticker', icon: 'fas fa-chart-line', color: 'text-green-500' },
            { key: 'trade_records', label: 'Trades', icon: 'fas fa-exchange-alt', color: 'text-blue-500' },
            { key: 'signal_records', label: 'Signals', icon: 'fas fa-bell', color: 'text-yellow-500' },
            { key: 'level2_records', label: 'Level2', icon: 'fas fa-layer-group', color: 'text-purple-500' },
            { key: 'candles_records', label: 'Candles', icon: 'fas fa-cube', color: 'text-indigo-500' },
            { key: 'matches_records', label: 'Matches', icon: 'fas fa-handshake', color: 'text-pink-500' },
            { key: 'status_records', label: 'Status', icon: 'fas fa-info-circle', color: 'text-gray-500' },
            { key: 'market_trades_records', label: 'Market Trades', icon: 'fas fa-chart-bar', color: 'text-red-500' }
        ];
        
        let html = '';
        dataTypes.forEach(type => {
            const count = this.dataSummary[type.key] || 0;
            html += `
                <div class="data-card rounded-lg p-4 text-center">
                    <i class="${type.icon} ${type.color} text-2xl mb-2"></i>
                    <div class="text-lg font-bold text-gray-800">${count}</div>
                    <div class="text-sm text-gray-600">${type.label}</div>
                </div>
            `;
        });
        
        summaryContainer.innerHTML = html;
        
        // Update total records
        const totalRecords = Object.values(this.dataSummary).reduce((sum, count) => sum + (count || 0), 0);
        document.getElementById('total-records').textContent = totalRecords.toLocaleString();
    }

    handleWebSocketMessage(data) {
        if (data.type === 'real_time_data') {
            this.updateRealTimeData(data.data);
            this.addToDataFeed(data.data);
            
            // Update candlestick chart if we have new candle data
            if (data.data.candles && data.data.candles.length > 0) {
                // Add new candle data to our existing data
                data.data.candles.forEach(candle => {
                    this.candlesData.push(candle);
                });
                
                // Keep only last 200 candles to prevent memory issues
                if (this.candlesData.length > 200) {
                    this.candlesData = this.candlesData.slice(-200);
                }
                
                this.updateCandlestickChart();
            }
        }
    }

    updateRealTimeData(data) {
        // Update price data
        if (data.ticker) {
            const price = parseFloat(data.ticker.price || 0);
            const change = parseFloat(data.ticker.price_change_24h || 0);
            
            document.getElementById('current-price').textContent = `$${price.toFixed(2)}`;
            
            const changeElement = document.getElementById('price-change');
            changeElement.textContent = `${change >= 0 ? '+' : ''}${change.toFixed(2)}%`;
            changeElement.className = `text-sm ${change >= 0 ? 'text-green-500' : 'text-red-500'}`;
            
            // Update volume
            const volume = parseFloat(data.ticker.volume_24h || 0);
            document.getElementById('volume-24h').textContent = volume.toLocaleString();
            
            // Add to price data for charts
            this.priceData.push({
                time: new Date(),
                price: price,
                volume: volume
            });
            
            // Keep only last 100 data points
            if (this.priceData.length > 100) {
                this.priceData = this.priceData.slice(-100);
            }
            
            this.updateCharts();
        }
        
        // Update last update time
        document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
    }

    addToDataFeed(data) {
        const feedContainer = document.getElementById('data-feed');
        const timestamp = new Date().toLocaleTimeString();
        
        let feedItem = `<div class="mb-2 p-2 bg-white rounded border-l-4 border-blue-500">`;
        feedItem += `<div class="text-xs text-gray-500">${timestamp}</div>`;
        
        if (data.ticker) {
            feedItem += `<div class="text-sm"><strong>Ticker:</strong> $${data.ticker.price}</div>`;
        }
        if (data.level2) {
            feedItem += `<div class="text-sm"><strong>Level2:</strong> ${data.level2.changes?.length || 0} changes</div>`;
        }
        if (data.matches) {
            feedItem += `<div class="text-sm"><strong>Matches:</strong> ${data.matches.matches?.length || 0} matches</div>`;
        }
        if (data.status) {
            feedItem += `<div class="text-sm"><strong>Status:</strong> ${data.status.status}</div>`;
        }
        
        feedItem += `</div>`;
        
        feedContainer.insertAdjacentHTML('afterbegin', feedItem);
        
        // Keep only last 20 items
        const items = feedContainer.children;
        if (items.length > 20) {
            feedContainer.removeChild(items[items.length - 1]);
        }
    }

    updateCharts() {
        if (this.priceData.length === 0) return;
        
        // Volume chart (keep existing)
        const volumeTrace = {
            x: this.priceData.map(d => d.time),
            y: this.priceData.map(d => d.volume),
            type: 'bar',
            name: 'Volume',
            marker: { color: '#10B981' }
        };
        
        const volumeLayout = {
            title: 'Real-time Volume',
            xaxis: { title: 'Time' },
            yaxis: { title: 'Volume' },
            margin: { t: 30, r: 30, b: 30, l: 30 }
        };
        
        Plotly.newPlot('volume-chart', [volumeTrace], volumeLayout, {responsive: true});
    }
    
    updateCandlestickChart() {
        console.log('updateCandlestickChart called with data length:', this.candlesData.length);
        
        const chartDiv = document.getElementById('price-chart');
        if (!chartDiv) {
            console.error('Chart div not found!');
            return;
        }
        
        if (this.candlesData.length === 0) {
            // Show loading message
            chartDiv.innerHTML = '<div class="flex items-center justify-center h-full text-gray-500"><i class="fas fa-spinner fa-spin mr-2"></i>Loading candlestick data...</div>';
            return;
        }
        
        // Prepare candlestick data
        const times = this.candlesData.map(candle => new Date(candle.timestamp));
        const opens = this.candlesData.map(candle => parseFloat(candle.open));
        const highs = this.candlesData.map(candle => parseFloat(candle.high));
        const lows = this.candlesData.map(candle => parseFloat(candle.low));
        const closes = this.candlesData.map(candle => parseFloat(candle.close));
        const volumes = this.candlesData.map(candle => parseFloat(candle.volume));
        
        console.log('Processed data:', {
            times: times.slice(0, 3),
            opens: opens.slice(0, 3),
            highs: highs.slice(0, 3),
            lows: lows.slice(0, 3),
            closes: closes.slice(0, 3),
            volumes: volumes.slice(0, 3)
        });
        
        // Create candlestick trace
        const candlestickTrace = {
            x: times,
            open: opens,
            high: highs,
            low: lows,
            close: closes,
            type: 'candlestick',
            name: 'Price',
            increasing: { line: { color: '#10B981' } },
            decreasing: { line: { color: '#EF4444' } }
        };
        
        // Create volume trace
        const volumeTrace = {
            x: times,
            y: volumes,
            type: 'bar',
            name: 'Volume',
            yaxis: 'y2',
            marker: {
                color: 'rgba(59, 130, 246, 0.3)',
                line: {
                    color: 'rgba(59, 130, 246, 0.8)',
                    width: 1
                }
            }
        };
        
        const layout = {
            title: `Price Chart (${this.getCandlePeriodLabel()})`,
            xaxis: { 
                title: 'Time',
                type: 'date',
                rangeslider: { visible: false }
            },
            yaxis: { 
                title: 'Price (USD)',
                domain: [0.3, 1]
            },
            yaxis2: {
                title: 'Volume',
                domain: [0, 0.3],
                side: 'right'
            },
            showlegend: true,
            margin: { t: 40, r: 40, b: 40, l: 40 },
            plot_bgcolor: 'rgba(0,0,0,0)',
            paper_bgcolor: 'rgba(0,0,0,0)'
        };
        
        Plotly.newPlot('price-chart', [candlestickTrace, volumeTrace], layout, {
            responsive: true,
            displayModeBar: true,
            modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d']
        });
    }
    
    getCandlePeriodLabel() {
        const periodMap = {
            60: '1m',
            300: '5m',
            900: '15m',
            3600: '1h',
            21600: '6h',
            86400: '1d'
        };
        return periodMap[this.currentCandlePeriod] || '1h';
    }

    async loadInitialData() {
        await this.loadDataSummary();
        await this.loadHistoricalData();
        await this.loadCandlesData();
    }
    
    async loadCandlesData() {
        try {
            console.log(`Loading candles data for period: ${this.currentCandlePeriod} (${this.getCandlePeriodLabel()})`);
            const response = await fetch(`/api/candles?granularity=${this.currentCandlePeriod}&days=7`);
            const data = await response.json();
            
            console.log('Candles API response:', data);
            
            if (Array.isArray(data) && data.length > 0) {
                this.candlesData = data;
                console.log(`Loaded ${data.length} candles for period ${this.getCandlePeriodLabel()}`);
                console.log('First candle:', data[0]);
                this.updateCandlestickChart();
            } else {
                console.warn('No candles data received');
                // Show empty chart
                this.updateCandlestickChart();
            }
        } catch (error) {
            console.error('Failed to load candles data:', error);
            this.showNotification('Failed to load candles data', 'error');
        }
    }

    async loadHistoricalData() {
        try {
            const response = await fetch('/api/historical-data?days=7');
            const data = await response.json();
            
            if (Array.isArray(data) && data.length > 0) {
                this.historicalData = data;
                this.updateCharts();
            }
        } catch (error) {
            console.error('Failed to load historical data:', error);
        }
    }

    async runBacktest() {
        const days = document.getElementById('backtest-days').value;
        const shortWindow = parseInt(document.getElementById('short-window').value);
        const longWindow = parseInt(document.getElementById('long-window').value);
        
        const resultsContainer = document.getElementById('backtest-results');
        resultsContainer.innerHTML = '<div class="text-center"><i class="fas fa-spinner fa-spin mr-2"></i>Running backtest...</div>';
        resultsContainer.classList.remove('hidden');
        
        try {
            const response = await fetch('/api/run-backtest', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    days: parseInt(days),
                    short_window: shortWindow,
                    long_window: longWindow
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.displayBacktestResults(result);
            } else {
                resultsContainer.innerHTML = `<div class="text-red-500">Error: ${result.error}</div>`;
            }
        } catch (error) {
            console.error('Backtest error:', error);
            resultsContainer.innerHTML = '<div class="text-red-500">Failed to run backtest</div>';
        }
    }

    displayBacktestResults(result) {
        const resultsContainer = document.getElementById('backtest-results');
        
        const html = `
            <div class="bg-green-50 border border-green-200 rounded-lg p-4">
                <h3 class="text-lg font-semibold text-green-800 mb-2">Backtest Results</h3>
                <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div class="text-center">
                        <div class="text-2xl font-bold text-green-600">${(result.result.total_return * 100).toFixed(2)}%</div>
                        <div class="text-sm text-gray-600">Total Return</div>
                    </div>
                    <div class="text-center">
                        <div class="text-2xl font-bold text-blue-600">${(result.result.win_rate * 100).toFixed(1)}%</div>
                        <div class="text-sm text-gray-600">Win Rate</div>
                    </div>
                    <div class="text-center">
                        <div class="text-2xl font-bold text-purple-600">${result.result.total_trades}</div>
                        <div class="text-sm text-gray-600">Total Trades</div>
                    </div>
                    <div class="text-center">
                        <div class="text-2xl font-bold text-orange-600">${result.result.sharpe_ratio?.toFixed(2) || 'N/A'}</div>
                        <div class="text-sm text-gray-600">Sharpe Ratio</div>
                    </div>
                </div>
            </div>
        `;
        
        resultsContainer.innerHTML = html;
    }

    updateConnectionStatus(connected) {
        const statusElement = document.getElementById('connection-status');
        const textElement = document.getElementById('connection-text');
        const iconElement = document.getElementById('connection-icon');
        
        if (connected) {
            statusElement.innerHTML = '<i class="fas fa-circle text-green-500 mr-2"></i>Connected';
            textElement.textContent = 'Connected';
            iconElement.className = 'fas fa-wifi text-green-500 text-2xl';
        } else {
            statusElement.innerHTML = '<i class="fas fa-circle text-red-500 mr-2"></i>Disconnected';
            textElement.textContent = 'Disconnected';
            iconElement.className = 'fas fa-wifi text-red-500 text-2xl';
        }
    }

    showNotification(message, type = 'info') {
        // Simple notification - you could enhance this with a proper notification library
        const notification = document.createElement('div');
        notification.className = `fixed top-4 right-4 p-4 rounded-lg shadow-lg z-50 ${
            type === 'success' ? 'bg-green-500 text-white' :
            type === 'error' ? 'bg-red-500 text-white' :
            'bg-blue-500 text-white'
        }`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 3000);
    }

    startDataRefresh() {
        // Refresh data summary every 30 seconds
        setInterval(() => {
            this.loadDataSummary();
        }, 30000);
        
        // Refresh subscriptions every 60 seconds
        setInterval(() => {
            this.loadSubscriptions();
        }, 60000);
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new EnhancedTradingDashboard();
});
