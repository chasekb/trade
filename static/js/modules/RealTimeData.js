/**
 * RealTimeData Module
 * Handles real-time data, WebSocket connections, and chart updates
 */
export class RealTimeData {
    constructor(dashboard) {
        this.dashboard = dashboard;
        this.ws = null;
        this.priceData = [];
        this.historicalData = [];
        this.backtestData = [];
        this.charts = {};
        this.isConnected = false;
        
        // Throttle chart updates for better performance
        this.throttledChartUpdate = this.throttle(() => {
            this.updatePriceChart();
        }, 1000); // Update chart max once per second
    }

    throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }

    init() {
        this.connectWebSocket();
        this.setupEventListeners();
        this.loadInitialData();
        this.startDataRefresh();
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

    handleWebSocketMessage(data) {
        console.log('📡 RealTimeData handling WebSocket message:', data.type, data);
        if (data.type === 'real_time_data') {
            this.updateRealTimeData(data.data);
        } else if (data.type === 'trading_statistics_update') {
            // Handle simulated trading statistics updates
            console.log('📊 Updating simulated trading statistics via WebSocket');
            this.updateTradingStatistics(data.data);
        } else if (data.type === 'orderbook_signals_update') {
            // Handle order book signals updates
            console.log('📈 Updating order book signals via WebSocket');
            this.updateOrderBookSignals(data.data);
        }
    }

    updateRealTimeData(data) {
        // Batch DOM updates for better performance
        const updates = [];
        
        // Update current price
        const price = parseFloat(data.ticker?.price || 0);
        const priceChange = parseFloat(data.ticker?.price_change_24h || 0);
        
        updates.push(() => {
            const priceElement = document.getElementById('current-price');
            if (priceElement) {
                priceElement.textContent = `$${price.toFixed(2)}`;
            }
        });
        
        updates.push(() => {
            const priceChangeElement = document.getElementById('price-change');
            if (priceChangeElement) {
                priceChangeElement.textContent = `${priceChange >= 0 ? '+' : ''}${priceChange.toFixed(2)}%`;
                priceChangeElement.className = `text-sm ${priceChange >= 0 ? 'text-green-600' : 'text-red-600'}`;
            }
        });
        
        // Update volume
        updates.push(() => {
            const volumeElement = document.getElementById('volume-24h');
            if (volumeElement) {
                volumeElement.textContent = parseFloat(data.ticker?.volume_24h || 0).toLocaleString();
            }
        });
        
        // Update timestamp
        updates.push(() => {
            const timestampElement = document.getElementById('last-update');
            if (timestampElement) {
                timestampElement.textContent = new Date(data.timestamp).toLocaleTimeString();
            }
        });
        
        // Batch execute DOM updates
        requestAnimationFrame(() => {
            updates.forEach(update => update());
        });
        
        // Add to price data for chart
        this.priceData.push({
            x: new Date(data.timestamp),
            y: price
        });
        
        // Keep only last 100 data points
        if (this.priceData.length > 100) {
            this.priceData = this.priceData.slice(-100);
        }
        
        // Throttle chart updates
        this.throttledChartUpdate();
    }

    updateConnectionStatus(connected) {
        const statusElement = document.getElementById('connection-status');
        if (connected) {
            statusElement.innerHTML = '<i class="fas fa-circle text-green-500 mr-2"></i>Connected';
        } else {
            statusElement.innerHTML = '<i class="fas fa-circle text-red-500 mr-2 pulse-animation"></i>Disconnected';
        }
    }

    async loadInitialData() {
        try {
            // Load real-time data
            const realTimeResponse = await fetch('/api/real-time-data');
            const realTimeData = await realTimeResponse.json();
            if (realTimeData.price) {
                // Convert to expected format
                const formattedData = {
                    ticker: {
                        price: realTimeData.price,
                        price_change_24h: 0,
                        volume_24h: realTimeData.volume
                    },
                    timestamp: realTimeData.timestamp
                };
                this.updateRealTimeData(formattedData);
            }
            
            // Load historical data
            await this.loadHistoricalData();
            
            // Load trading metrics
            await this.loadTradingMetrics();
            
        } catch (error) {
            console.error('Error loading initial data:', error);
        }
    }

    async loadHistoricalData() {
        try {
            const response = await fetch('/api/historical-data?product_id=BTC-USD&days=7');
            this.historicalData = await response.json();
            this.updateHistoricalChart();
        } catch (error) {
            console.error('Error loading historical data:', error);
        }
    }

    async loadTradingMetrics() {
        try {
            const response = await fetch('/api/trading/metrics');
            const metrics = await response.json();
            
            if (metrics.error) {
                console.warn('No trading metrics available:', metrics.error);
                return;
            }
            
            // Update metrics cards
            document.getElementById('total-backtests').textContent = metrics.total_backtests || 0;
            
            if (metrics.best_backtest) {
                const returnPercent = (metrics.best_backtest.total_return * 100).toFixed(2);
                document.getElementById('best-return').textContent = `${returnPercent}%`;
            }
            
            // Update metrics table
            this.updateMetricsTable(metrics);
            
        } catch (error) {
            console.error('Error loading trading metrics:', error);
        }
    }

    updateMetricsTable(metrics) {
        const tableBody = document.getElementById('metrics-table');
        const metricsData = [
            { name: 'Current Price', value: `$${metrics.current_price?.toFixed(2) || 'N/A'}`, status: 'active' },
            { name: '24h Price Change', value: `${metrics.price_change_24h?.toFixed(2) || 'N/A'}%`, status: metrics.price_change_24h >= 0 ? 'positive' : 'negative' },
            { name: '24h Volume', value: metrics.volume_24h?.toLocaleString() || 'N/A', status: 'neutral' },
            { name: 'Total Backtests', value: metrics.total_backtests || 0, status: 'neutral' },
            { name: 'Best Return', value: metrics.best_backtest ? `${(metrics.best_backtest.total_return * 100).toFixed(2)}%` : 'N/A', status: 'positive' },
            { name: 'Last Update', value: new Date(metrics.timestamp).toLocaleTimeString() || 'N/A', status: 'neutral' }
        ];
        
        tableBody.innerHTML = metricsData.map(metric => `
            <tr>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${metric.name}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${metric.value}</td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                        metric.status === 'positive' ? 'bg-green-100 text-green-800' :
                        metric.status === 'negative' ? 'bg-red-100 text-red-800' :
                        metric.status === 'active' ? 'bg-blue-100 text-blue-800' :
                        'bg-gray-100 text-gray-800'
                    }">
                        ${metric.status}
                    </span>
                </td>
            </tr>
        `).join('');
    }

    updatePriceChart() {
        if (this.priceData.length === 0) return;
        
        const trace = {
            x: this.priceData.map(d => d.x),
            y: this.priceData.map(d => d.y),
            type: 'scatter',
            mode: 'lines',
            name: 'Price',
            line: { color: '#3B82F6' }
        };
        
        const layout = {
            title: 'Real-time Price',
            xaxis: { title: 'Time' },
            yaxis: { title: 'Price ($)' },
            showlegend: false,
            margin: { t: 30, r: 30, b: 30, l: 30 }
        };
        
        Plotly.newPlot('price-chart', [trace], layout, {responsive: true});
    }

    updateHistoricalChart() {
        if (this.historicalData.length === 0) return;
        
        const trace = {
            x: this.historicalData.map(d => new Date(d.timestamp)),
            y: this.historicalData.map(d => d.close),
            type: 'scatter',
            mode: 'lines',
            name: 'Close Price',
            line: { color: '#10B981' }
        };
        
        const layout = {
            title: 'Historical Data (7 days)',
            xaxis: { title: 'Date' },
            yaxis: { title: 'Price ($)' },
            showlegend: false,
            margin: { t: 30, r: 30, b: 30, l: 30 }
        };
        
        Plotly.newPlot('historical-chart', [trace], layout, {responsive: true});
    }

    updateBacktestChart(data) {
        if (!data || data.length === 0) return;
        
        const trace = {
            x: data.map(d => new Date(d.timestamp)),
            y: data.map(d => d.equity),
            type: 'scatter',
            mode: 'lines',
            name: 'Equity Curve',
            line: { color: '#8B5CF6' }
        };
        
        const layout = {
            title: 'Backtest Equity Curve',
            xaxis: { title: 'Date' },
            yaxis: { title: 'Equity ($)' },
            showlegend: false,
            margin: { t: 30, r: 30, b: 30, l: 30 }
        };
        
        Plotly.newPlot('backtest-chart', [trace], layout, {responsive: true});
    }

    setupEventListeners() {
        // Backtest button
        const runBacktestBtn = document.getElementById('run-backtest');
        if (runBacktestBtn) {
            runBacktestBtn.addEventListener('click', () => {
                this.runBacktest();
            });
        }
    }

    async runBacktest() {
        const productId = document.getElementById('backtest-product').value;
        const days = parseInt(document.getElementById('backtest-days').value);
        const shortWindow = parseInt(document.getElementById('short-window').value);
        const longWindow = parseInt(document.getElementById('long-window').value);
        
        // Show loading overlay
        document.getElementById('loading-overlay').classList.remove('hidden');
        
        try {
            // Calculate start and end dates
            const endDate = new Date();
            const startDate = new Date();
            startDate.setDate(startDate.getDate() - days);
            
            const response = await fetch('/api/backtest', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    strategy: 'SMA',
                    symbol: productId,
                    start_date: startDate.toISOString().split('T')[0],
                    end_date: endDate.toISOString().split('T')[0],
                    strategy_params: {
                        short_window: shortWindow,
                        long_window: longWindow
                    }
                })
            });
            
            const result = await response.json();
            
            if (result.error) {
                this.dashboard.uiUtils.showMessage(`Backtest failed: ${result.error}`, 'error');
                return;
            }
            
            // Update results display
            this.displayBacktestResults(result);
            
        } catch (error) {
            console.error('Backtest error:', error);
            this.dashboard.uiUtils.showMessage('Backtest failed. Please try again.', 'error');
        } finally {
            // Hide loading overlay
            document.getElementById('loading-overlay').classList.add('hidden');
        }
    }

    displayBacktestResults(result) {
        // Show results section
        document.getElementById('backtest-results').classList.remove('hidden');
        
        // Update metrics
        const returnPercent = (result.result.total_return * 100).toFixed(2);
        const winRatePercent = (result.result.win_rate * 100).toFixed(1);
        
        document.getElementById('backtest-return').textContent = `${returnPercent}%`;
        document.getElementById('backtest-win-rate').textContent = `${winRatePercent}%`;
        document.getElementById('backtest-trades').textContent = result.result.total_trades;
        
        // Update chart
        this.updateBacktestChart(result.equity_curve);
        
        // Refresh trading metrics
        this.loadTradingMetrics();
    }

    // WebSocket handler for simulated trading statistics updates
    updateTradingStatistics(data) {
        console.log('📊 Processing trading statistics update:', data);

        // Batch DOM updates for better performance
        const updates = [];

        // Update simulated trading statistics widget elements if they exist
        const elements = [
            'simulated-total-pnl',
            'simulated-win-rate',
            'simulated-total-trades',
            'simulated-active-positions',
            'simulated-position-value',
            'simulated-profit-factor',
            'simulated-sharpe-ratio',
            'simulated-max-drawdown',
            'simulated-avg-win',
            'simulated-avg-loss',
            'simulated-best-trade',
            'simulated-worst-trade'
        ];

        elements.forEach(elementId => {
            const element = document.getElementById(elementId);
            if (element && data.hasOwnProperty(this.elementIdToDataKey(elementId))) {
                let value = data[this.elementIdToDataKey(elementId)];
                let formattedValue = this.formatTradingStatistic(elementId, value);
                updates.push(() => {
                    element.textContent = formattedValue;
                });
            }
        });

        // Update timestamp if element exists
        const lastUpdateElement = document.getElementById('simulated-last-update');
        if (lastUpdateElement) {
            updates.push(() => {
                lastUpdateElement.textContent = new Date(data.timestamp || Date.now()).toLocaleTimeString();
            });
        }

        // Execute all DOM updates in batch
        requestAnimationFrame(() => {
            updates.forEach(update => update());
            console.log('✅ Simulated trading statistics updated via WebSocket');
        });
    }

    // WebSocket handler for order book signals updates
    updateOrderBookSignals(data) {
        console.log('📈 Processing order book signals update:', data);

        // Batch DOM updates for better performance
        const updates = [];

        // Update order book statistics elements if they exist
        const totalAnalyzedElement = document.getElementById('total-analyzed');
        if (totalAnalyzedElement && data.total_analyzed !== undefined) {
            updates.push(() => {
                totalAnalyzedElement.textContent = data.total_analyzed;
            });
        }

        const activeSignalsElement = document.getElementById('active-signals');
        if (activeSignalsElement && data.active_signals !== undefined) {
            updates.push(() => {
                activeSignalsElement.textContent = data.active_signals;
            });
        }

        const avgStrengthElement = document.getElementById('avg-strength');
        if (avgStrengthElement && data.average_strength !== undefined) {
            updates.push(() => {
                avgStrengthElement.textContent = data.average_strength.toFixed(2);
            });
        }

        const lastUpdatedElement = document.getElementById('last-updated');
        if (lastUpdatedElement) {
            updates.push(() => {
                lastUpdatedElement.textContent = new Date(data.last_updated || Date.now()).toLocaleTimeString();
            });
        }

        // Update signals table if signals are provided
        if (data.signals && Array.isArray(data.signals) && data.signals.length > 0) {
            const tableBody = document.getElementById('orderbook-signals-table');
            if (tableBody) {
                // Clear existing content
                updates.push(() => {
                    tableBody.innerHTML = '';

                    // Add new signals
                    data.signals.forEach(signal => {
                        const row = document.createElement('tr');
                        row.className = 'hover:bg-gray-50';

                        const signalClass = signal.signal_generated ? 'text-green-600 bg-green-50' : 'text-gray-600 bg-gray-50';
                        const strengthColor = (signal.signal_strength >= 0.7) ? 'text-green-600' :
                                           (signal.signal_strength >= 0.4) ? 'text-yellow-600' : 'text-red-600';

                        row.innerHTML = `
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${signal.symbol}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm ${signalClass}">
                                ${signal.signal_generated ? 'Active' : 'Inactive'}
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm ${strengthColor}">
                                ${signal.signal_strength.toFixed(2)}
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${new Date(signal.timestamp).toLocaleString()}</td>
                        `;

                        tableBody.appendChild(row);
                    });
                });
            }
        }

        // Execute all DOM updates in batch
        requestAnimationFrame(() => {
            updates.forEach(update => update());
            console.log('✅ Order book signals updated via WebSocket');
        });
    }

    // Helper method to map element IDs to data keys
    elementIdToDataKey(elementId) {
        const mappings = {
            'simulated-total-pnl': 'net_pnl',
            'simulated-win-rate': 'win_rate',
            'simulated-total-trades': 'total_trades',
            'simulated-active-positions': 'active_positions',
            'simulated-position-value': 'position_value',
            'simulated-profit-factor': 'profit_factor',
            'simulated-sharpe-ratio': 'sharpe_ratio',
            'simulated-max-drawdown': 'max_drawdown',
            'simulated-avg-win': 'avg_win',
            'simulated-avg-loss': 'avg_loss',
            'simulated-best-trade': 'best_trade',
            'simulated-worst-trade': 'worst_trade'
        };
        return mappings[elementId] || elementId;
    }

    // Helper method to format trading statistics for display
    formatTradingStatistic(elementId, value) {
        if (value === null || value === undefined) return '0';

        switch (elementId) {
            case 'simulated-total-pnl':
            case 'simulated-position-value':
            case 'simulated-avg-win':
            case 'simulated-avg-loss':
            case 'simulated-best-trade':
            case 'simulated-worst-trade':
                return Number(value).toFixed(2);
            case 'simulated-win-rate':
                return Number(value).toFixed(1) + '%';
            case 'simulated-profit-factor':
                return (value === Infinity) ? '∞' : Number(value).toFixed(2);
            case 'simulated-sharpe-ratio':
                return Number(value).toFixed(2);
            case 'simulated-max-drawdown':
                return Number(value).toFixed(2) + '%';
            case 'simulated-total-trades':
            case 'simulated-active-positions':
                return Math.round(Number(value)).toString();
            default:
                return value.toString();
        }
    }

    startDataRefresh() {
        // Refresh data every 30 seconds
        setInterval(() => {
            this.loadTradingMetrics();
        }, 30000);
    }

    destroy() {
        if (this.ws) {
            this.ws.close();
        }
    }
}
