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
        this.currentSymbol = 'BTC-USD'; // Default symbol
        this.currentYAxisRange = null; // Store current y-axis range
        this.currentLayout = null; // Store current layout
        this.percentageTimeframe = '24h'; // Default percentage timeframe
        this.historicalPrices = {}; // Store historical prices for percentage calculation
        this.apiChange24h = null; // Store API's 24h change as fallback
        this.isSwitchingSymbol = false; // Flag to prevent real-time updates during symbol switch
        
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
            this.loadRealtimeStatus();
        }, 100);
    }

    connectWebSocket() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            return;
        }
        
        try {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            
            this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.isConnected = true;
            this.updateConnectionStatus(true);
            // Load subscriptions after connection
            this.loadSubscriptions();
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
        
        } catch (error) {
            console.error('Failed to create WebSocket connection:', error);
            this.isConnected = false;
            this.updateConnectionStatus(false);
        }
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
        
        // Symbol selector
        document.getElementById('symbol-selector').addEventListener('change', (e) => {
            this.currentSymbol = e.target.value;
            this.switchSymbol();
        });
        
        // Tab switching
        document.getElementById('tab-dashboard').addEventListener('click', () => {
            this.switchTab('dashboard');
        });
        document.getElementById('tab-backtesting').addEventListener('click', () => {
            this.switchTab('backtesting');
        });
        document.getElementById('tab-data').addEventListener('click', () => {
            this.switchTab('data');
        });
        document.getElementById('tab-settings').addEventListener('click', () => {
            this.switchTab('settings');
        });
        
        // Real-time data toggle
        document.getElementById('realtime-toggle').addEventListener('change', (e) => {
            this.toggleRealtimeData(e.target.checked);
        });
        
        // Percentage timeframe selector
        document.getElementById('percentage-timeframe').addEventListener('change', (e) => {
            this.percentageTimeframe = e.target.value;
            this.updatePercentageChange();
        });
        
        // Clear results button
        document.getElementById('clear-results').addEventListener('click', () => {
            this.clearBacktestResults();
        });

        // Strategy type change handler
        document.getElementById('strategy-type').addEventListener('change', (e) => {
            this.updateStrategyParameters();
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
                return {};
            }
            
            this.subscriptions = data.channels || {};
            this.updateSubscriptionDisplay();
            return this.subscriptions;
        } catch (error) {
            console.error('Failed to load subscriptions:', error);
            document.getElementById('subscription-list').innerHTML = 
                '<span class="text-red-500">Failed to load subscriptions</span>';
            return {};
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
        console.log('WebSocket message received:', {
            product_id: data.product_id,
            currentSymbol: this.currentSymbol,
            type: data.type,
            isSwitchingSymbol: this.isSwitchingSymbol
        });
        
        // Skip all WebSocket messages if we're switching symbols
        if (this.isSwitchingSymbol) {
            console.log('Skipping WebSocket message during symbol switch');
            return;
        }
        
        // Check if the message is for the current symbol
        if (data.product_id && data.product_id !== this.currentSymbol) {
            console.log('Ignoring message for different symbol:', data.product_id);
            return; // Ignore messages for other symbols
        }
        
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
        // Skip real-time updates if we're switching symbols
        if (this.isSwitchingSymbol) {
            console.log('Skipping real-time update during symbol switch');
            return;
        }
        
        // Update price data
        if (data.ticker) {
            const price = parseFloat(data.ticker.price || 0);
            const apiChange24h = parseFloat(data.ticker.price_change_24h || 0);
            
            console.log('Updating real-time data:', {
                currentSymbol: this.currentSymbol,
                price,
                volume: data.ticker.volume_24h,
                change24h: apiChange24h
            });
            
            document.getElementById('current-price').textContent = `$${price.toFixed(2)}`;
            
            // Store current price for percentage calculation
            this.historicalPrices[new Date().toISOString()] = price;
            
            // Store API's 24h change as fallback
            this.apiChange24h = apiChange24h;
            
            // Clean up old historical prices (keep only last 1000 entries)
            const priceEntries = Object.entries(this.historicalPrices);
            if (priceEntries.length > 1000) {
                const sortedEntries = priceEntries.sort((a, b) => new Date(a[0]) - new Date(b[0]));
                const toKeep = sortedEntries.slice(-1000);
                this.historicalPrices = Object.fromEntries(toKeep);
            }
            
            // Update percentage change
            this.updatePercentageChange();
            
            // Update volume
            const volume = parseFloat(data.ticker.volume_24h || 0);
            document.getElementById('volume-24h').textContent = volume.toLocaleString();
            
            // Add to price data for real-time updates
            this.priceData.push({
                time: new Date(),
                price: price
            });
            
            // Keep only last 100 data points
            if (this.priceData.length > 100) {
                this.priceData = this.priceData.slice(-100);
            }
            
            // Update candlestick chart with real-time data
            this.updateCandlestickChartWithRealtimeData(price);
        }
        
        // Update last update time
        document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
    }
    
    updatePercentageChange() {
        const currentPrice = parseFloat(document.getElementById('current-price').textContent.replace('$', ''));
        if (!currentPrice || currentPrice === 0) {
            console.log('No current price available for percentage calculation');
            return;
        }
        
        console.log('Updating percentage change:', {
            currentPrice,
            timeframe: this.percentageTimeframe,
            historicalPricesCount: Object.keys(this.historicalPrices).length,
            candlesDataCount: this.candlesData.length
        });
        
        const now = new Date();
        let targetTime;
        
        // Calculate target time based on selected timeframe
        switch (this.percentageTimeframe) {
            case '1h':
                targetTime = new Date(now.getTime() - 60 * 60 * 1000);
                break;
            case '24h':
                targetTime = new Date(now.getTime() - 24 * 60 * 60 * 1000);
                break;
            case '7d':
                targetTime = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
                break;
            case '30d':
                targetTime = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
                break;
            case '365d':
                targetTime = new Date(now.getTime() - 365 * 24 * 60 * 60 * 1000);
                break;
            default:
                targetTime = new Date(now.getTime() - 24 * 60 * 60 * 1000);
        }
        
        // Find the closest historical price to the target time
        let historicalPrice = null;
        let closestTime = null;
        let minTimeDiff = Infinity;
        
        console.log('Looking for historical price at target time:', targetTime.toISOString());
        console.log('Available historical prices:', Object.keys(this.historicalPrices).slice(0, 5));
        
        for (const [timeStr, price] of Object.entries(this.historicalPrices)) {
            const time = new Date(timeStr);
            const timeDiff = Math.abs(time.getTime() - targetTime.getTime());
            
            if (timeDiff < minTimeDiff) {
                minTimeDiff = timeDiff;
                historicalPrice = price;
                closestTime = time;
            }
        }
        
        console.log('Found historical price:', {
            historicalPrice,
            closestTime: closestTime?.toISOString(),
            timeDiff: minTimeDiff
        });
        
        // If no historical price found, try to get from candles data
        if (!historicalPrice && this.candlesData.length > 0) {
            const targetTimeMs = targetTime.getTime();
            let closestCandle = null;
            let minCandleDiff = Infinity;
            
            for (const candle of this.candlesData) {
                const candleTime = new Date(candle.timestamp).getTime();
                const timeDiff = Math.abs(candleTime - targetTimeMs);
                
                if (timeDiff < minCandleDiff) {
                    minCandleDiff = timeDiff;
                    closestCandle = candle;
                }
            }
            
            if (closestCandle) {
                historicalPrice = parseFloat(closestCandle.close);
            }
        }
        
        // Calculate percentage change
        let percentageChange = 0;
        if (historicalPrice && historicalPrice > 0) {
            percentageChange = ((currentPrice - historicalPrice) / historicalPrice) * 100;
        } else {
            // Fallback: use API's built-in percentage change for 24h
            if (this.percentageTimeframe === '24h' && this.apiChange24h !== undefined) {
                percentageChange = this.apiChange24h;
                console.log('Using API fallback for 24h change:', this.apiChange24h);
            } else {
                console.log('No historical price found and no API fallback available');
            }
        }
        
        // Update the display
        const changeElement = document.getElementById('price-change');
        changeElement.textContent = `${percentageChange >= 0 ? '+' : ''}${percentageChange.toFixed(2)}%`;
        changeElement.className = `text-sm ${percentageChange >= 0 ? 'text-green-500' : 'text-red-500'}`;
        
        console.log(`Percentage change for ${this.percentageTimeframe}:`, {
            currentPrice,
            historicalPrice,
            percentageChange,
            timeframe: this.percentageTimeframe
        });
    }

    async toggleRealtimeData(enabled) {
        try {
            const response = await fetch('/api/toggle-realtime', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const result = await response.json();
            
            if (response.ok) {
                // Update the status display
                const statusElement = document.getElementById('realtime-status');
                if (enabled) {
                    statusElement.textContent = 'Connected';
                    statusElement.className = 'text-sm text-green-500';
                    this.showNotification('Real-time data collection started', 'success');
                } else {
                    statusElement.textContent = 'Disabled';
                    statusElement.className = 'text-sm text-red-500';
                    this.showNotification('Real-time data collection stopped', 'warning');
                }
                
                // If disabling, close WebSocket connection
                if (!enabled && this.ws) {
                    this.ws.close();
                    this.isConnected = false;
                }
                // If enabling, reconnect WebSocket
                else if (enabled && !this.isConnected) {
                    this.connectWebSocket();
                }
            } else {
                this.showNotification(`Failed to toggle real-time data: ${result.error}`, 'error');
                // Revert the toggle state
                document.getElementById('realtime-toggle').checked = !enabled;
            }
        } catch (error) {
            console.error('Error toggling real-time data:', error);
            this.showNotification('Failed to toggle real-time data', 'error');
            // Revert the toggle state
            document.getElementById('realtime-toggle').checked = !enabled;
        }
    }

    async loadRealtimeStatus() {
        try {
            const response = await fetch('/api/realtime-status');
            const status = await response.json();
            
            // Update the toggle state
            const toggle = document.getElementById('realtime-toggle');
            const statusElement = document.getElementById('realtime-status');
            
            toggle.checked = status.enabled;
            
            if (status.enabled && status.websocket_connected) {
                statusElement.textContent = 'Connected';
                statusElement.className = 'text-sm text-green-500';
            } else if (status.enabled && !status.websocket_connected) {
                statusElement.textContent = 'Connecting...';
                statusElement.className = 'text-sm text-yellow-500';
            } else {
                statusElement.textContent = 'Disabled';
                statusElement.className = 'text-sm text-red-500';
            }
        } catch (error) {
            console.error('Error loading real-time status:', error);
        }
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
        // Volume chart removed - only candlestick chart remains
        // This method is kept for compatibility but no longer creates charts
    }
    
    updateCandlestickChart(forceRescale = false) {
        console.log('updateCandlestickChart called with data length:', this.candlesData.length, 'forceRescale:', forceRescale);
        
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
            yaxis: 'y', // Explicitly use the first y-axis for price
            increasing: { line: { color: '#10B981' } },
            decreasing: { line: { color: '#EF4444' } }
        };
        
        // Create volume trace
        const volumeTrace = {
            x: times,
            y: volumes,
            type: 'bar',
            name: 'Volume',
            yaxis: 'y2', // Use the second y-axis for volume
            marker: {
                color: 'rgba(59, 130, 246, 0.3)',
                line: {
                    color: 'rgba(59, 130, 246, 0.8)',
                    width: 1
                }
            }
        };
        
        console.log('Trace configuration:', {
            candlestickTrace: { yaxis: candlestickTrace.yaxis, type: candlestickTrace.type },
            volumeTrace: { yaxis: volumeTrace.yaxis, type: volumeTrace.type }
        });
        
        // Calculate price range for proper scaling
        const allPrices = [...opens, ...highs, ...lows, ...closes].filter(price => !isNaN(price) && isFinite(price));
        
        let minPrice, maxPrice, padding;
        if (allPrices.length > 0) {
            minPrice = Math.min(...allPrices);
            maxPrice = Math.max(...allPrices);
            const priceRange = maxPrice - minPrice;
            padding = priceRange * 0.05; // 5% padding
            
            console.log(`Price range for ${this.currentSymbol}:`, {
                minPrice: minPrice,
                maxPrice: maxPrice,
                priceRange: priceRange,
                padding: padding,
                yAxisRange: [minPrice - padding, maxPrice + padding]
            });
        } else {
            // Fallback for empty data
            minPrice = 0;
            maxPrice = 100;
            padding = 10;
            console.log(`Using fallback price range for ${this.currentSymbol}:`, [minPrice, maxPrice]);
        }
        
        const layout = {
            title: `${this.currentSymbol} - Real-time Price Chart (${this.getCandlePeriodLabel()})`,
            xaxis: { 
                title: 'Time',
                type: 'date',
                rangeslider: { visible: false }
            },
            yaxis: { 
                title: 'Price (USD)',
                domain: [0.3, 1],
                range: [minPrice - padding, maxPrice + padding],
                autorange: false,
                fixedrange: false
            },
            yaxis2: {
                title: 'Volume',
                domain: [0, 0.3],
                side: 'right',
                autorange: true
            },
            showlegend: true,
            margin: { t: 40, r: 40, b: 40, l: 40 },
            plot_bgcolor: 'rgba(0,0,0,0)',
            paper_bgcolor: 'rgba(0,0,0,0)'
        };
        
        console.log('Layout configuration:', {
            yaxis: { title: layout.yaxis.title, domain: layout.yaxis.domain },
            yaxis2: { title: layout.yaxis2.title, domain: layout.yaxis2.domain }
        });
        
        if (forceRescale) {
            // Store the y-axis range and layout for this symbol
            this.currentYAxisRange = [minPrice - padding, maxPrice + padding];
            this.currentLayout = layout;
            console.log(`Storing y-axis range for ${this.currentSymbol}:`, this.currentYAxisRange);
            
            // Clear the chart completely and recreate it to ensure proper scaling
            Plotly.purge('price-chart');
            Plotly.newPlot('price-chart', [candlestickTrace, volumeTrace], layout, {
                responsive: true,
                displayModeBar: true,
                modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d']
            });
        } else {
            // Check if chart already exists
            const chartDiv = document.getElementById('price-chart');
            if (chartDiv && chartDiv.data && this.currentLayout) {
                // Chart exists, use react to update data but preserve layout
                const preservedLayout = {
                    ...this.currentLayout,
                    'yaxis.range': this.currentYAxisRange,
                    'yaxis.autorange': false,
                    'yaxis2.autorange': true
                };
                
                console.log('Using preserved layout for real-time update:', {
                    yaxis: { title: preservedLayout.yaxis?.title, domain: preservedLayout.yaxis?.domain },
                    yaxis2: { title: preservedLayout.yaxis2?.title, domain: preservedLayout.yaxis2?.domain }
                });
                
                Plotly.react('price-chart', [candlestickTrace, volumeTrace], preservedLayout, {
                    responsive: true,
                    displayModeBar: true,
                    modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d']
                });
            } else {
                // Chart doesn't exist, create it
                Plotly.newPlot('price-chart', [candlestickTrace, volumeTrace], layout, {
                    responsive: true,
                    displayModeBar: true,
                    modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d']
                });
            }
        }
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
    
    updateCandlestickChartWithRealtimeData(price) {
        if (this.candlesData.length === 0) return;
        
        const now = new Date();
        const currentTime = now.getTime();
        const periodMs = this.currentCandlePeriod * 1000;
        
        // Find the current candle period
        const currentPeriodStart = new Date(Math.floor(currentTime / periodMs) * periodMs);
        
        // Check if we need to create a new candle or update the current one
        const lastCandle = this.candlesData[this.candlesData.length - 1];
        const lastCandleTime = new Date(lastCandle.timestamp);
        
        if (lastCandleTime.getTime() === currentPeriodStart.getTime()) {
            // Update the current candle
            lastCandle.close = price;
            lastCandle.high = Math.max(lastCandle.high, price);
            lastCandle.low = Math.min(lastCandle.low, price);
        } else {
            // Fill in missing candles between last candle and current period
            let fillTime = new Date(lastCandleTime.getTime() + periodMs);
            while (fillTime.getTime() < currentPeriodStart.getTime()) {
                const fillCandle = {
                    timestamp: fillTime.toISOString(),
                    open: lastCandle.close, // Use last close as open
                    high: lastCandle.close,
                    low: lastCandle.close,
                    close: lastCandle.close,
                    volume: 0,
                    price: lastCandle.close
                };
                this.candlesData.push(fillCandle);
                fillTime = new Date(fillTime.getTime() + periodMs);
            }
            
            // Create the current candle
            const newCandle = {
                timestamp: currentPeriodStart.toISOString(),
                open: price,
                high: price,
                low: price,
                close: price,
                volume: 0, // We don't have real-time volume data
                price: price
            };
            
            this.candlesData.push(newCandle);
            
            // Keep only last 200 candles
            if (this.candlesData.length > 200) {
                this.candlesData = this.candlesData.slice(-200);
            }
        }
        
        // Update the chart with real-time data (no rescaling)
        this.updateCandlestickChart(false);
    }

    async loadInitialData() {
        await this.loadDataSummary();
        await this.loadHistoricalData();
        await this.loadCandlesData();
    }
    
    async loadCandlesData() {
        try {
            console.log(`Loading candles data for ${this.currentSymbol} period: ${this.currentCandlePeriod} (${this.getCandlePeriodLabel()})`);
            const response = await fetch(`/api/candles?product_id=${this.currentSymbol}&granularity=${this.currentCandlePeriod}&days=7`);
            const data = await response.json();
            
            console.log('Candles API response:', data);
            
            if (Array.isArray(data) && data.length > 0) {
                this.candlesData = data;
                console.log(`Loaded ${data.length} candles for period ${this.getCandlePeriodLabel()}`);
                console.log('First candle:', data[0]);
                console.log('Last candle:', data[data.length - 1]);
                
                // Store historical prices from candle data
                this.candlesData.forEach(candle => {
                    this.historicalPrices[candle.timestamp] = parseFloat(candle.close);
                });
                
                console.log('Stored historical prices from candles:', {
                    count: this.candlesData.length,
                    firstPrice: this.candlesData[0]?.close,
                    lastPrice: this.candlesData[this.candlesData.length - 1]?.close,
                    firstTime: this.candlesData[0]?.timestamp,
                    lastTime: this.candlesData[this.candlesData.length - 1]?.timestamp
                });
                
                // Fill in any gaps with real-time data
                this.fillDataGaps();
                
                // Update percentage change with historical data
                this.updatePercentageChange();
                
                this.updateCandlestickChart(true);
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
    
    fillDataGaps() {
        if (this.candlesData.length === 0) return;
        
        const now = new Date();
        const currentTime = now.getTime();
        const periodMs = this.currentCandlePeriod * 1000;
        
        // Find the current candle period
        const currentPeriodStart = new Date(Math.floor(currentTime / periodMs) * periodMs);
        
        // Get the last candle time
        const lastCandle = this.candlesData[this.candlesData.length - 1];
        const lastCandleTime = new Date(lastCandle.timestamp);
        
        // If there's a gap, fill it with placeholder candles
        if (lastCandleTime.getTime() < currentPeriodStart.getTime()) {
            console.log(`Filling data gap from ${lastCandleTime.toISOString()} to ${currentPeriodStart.toISOString()}`);
            
            let fillTime = new Date(lastCandleTime.getTime() + periodMs);
            while (fillTime.getTime() < currentPeriodStart.getTime()) {
                const fillCandle = {
                    timestamp: fillTime.toISOString(),
                    open: lastCandle.close, // Use last close as open
                    high: lastCandle.close,
                    low: lastCandle.close,
                    close: lastCandle.close,
                    volume: 0,
                    price: lastCandle.close
                };
                this.candlesData.push(fillCandle);
                fillTime = new Date(fillTime.getTime() + periodMs);
            }
            
            console.log(`Added ${Math.floor((currentPeriodStart.getTime() - lastCandleTime.getTime()) / periodMs)} placeholder candles`);
        }
    }

    async loadHistoricalData() {
        try {
            const response = await fetch(`/api/historical-data?product_id=${this.currentSymbol}&days=7`);
            const data = await response.json();
            
            if (Array.isArray(data) && data.length > 0) {
                this.historicalData = data;
                // Volume chart removed - no longer needed
            }
        } catch (error) {
            console.error('Failed to load historical data:', error);
        }
    }
    
    async loadCurrentPriceData() {
        try {
            console.log(`Loading current price data for ${this.currentSymbol}`);
            
            // Try to get real-time data first
            const realTimeResponse = await fetch(`/api/real-time-data?product_id=${this.currentSymbol}`);
            const realTimeData = await realTimeResponse.json();
            
            if (realTimeData && !realTimeData.error && realTimeData.ticker) {
                // Use real-time data if available
                const price = parseFloat(realTimeData.ticker.price || 0);
                const volume = parseFloat(realTimeData.ticker.volume_24h || 0);
                const change24h = parseFloat(realTimeData.ticker.price_change_24h || 0);
                
                document.getElementById('current-price').textContent = `$${price.toFixed(2)}`;
                document.getElementById('volume-24h').textContent = volume.toLocaleString();
                
                // Store the API change for percentage calculation
                this.apiChange24h = change24h;
                
                console.log(`Updated price data from real-time for ${this.currentSymbol}:`, {
                    price,
                    volume,
                    change24h
                });
            } else {
                // Fallback: get latest data from historical data API
                console.log(`No real-time data for ${this.currentSymbol}, using historical data fallback`);
                const historicalResponse = await fetch(`/api/historical-data?product_id=${this.currentSymbol}&days=1`);
                const historicalData = await historicalResponse.json();
                
                if (Array.isArray(historicalData) && historicalData.length > 0) {
                    // Get the most recent data point
                    const latestData = historicalData[historicalData.length - 1];
                    const price = parseFloat(latestData.price || 0);
                    const volume = parseFloat(latestData.volume || 0);
                    
                    document.getElementById('current-price').textContent = `$${price.toFixed(2)}`;
                    document.getElementById('volume-24h').textContent = volume.toLocaleString();
                    
                    console.log(`Updated price data from historical for ${this.currentSymbol}:`, {
                        price,
                        volume
                    });
                } else {
                    console.warn('No data available for', this.currentSymbol);
                    // Set default values
                    document.getElementById('current-price').textContent = '$0.00';
                    document.getElementById('volume-24h').textContent = '0';
                }
            }
            
            // Update percentage change
            this.updatePercentageChange();
            
        } catch (error) {
            console.error('Failed to load current price data:', error);
            // Set default values on error
            document.getElementById('current-price').textContent = '$0.00';
            document.getElementById('volume-24h').textContent = '0';
            document.getElementById('price-change').textContent = '+0.00%';
        }
    }

    async runBacktest() {
        const strategyType = document.getElementById('strategy-type').value;
        const symbol = document.getElementById('backtest-symbol').value;
        const days = document.getElementById('backtest-days').value;
        const granularity = document.getElementById('backtest-granularity').value;
        const stopLoss = parseFloat(document.getElementById('stop-loss').value);
        const takeProfit = parseFloat(document.getElementById('take-profit').value);
        const initialCapital = parseFloat(document.getElementById('initial-capital').value);
        
        // Get strategy-specific parameters
        let strategyParams = {};
        if (strategyType === 'sma' || strategyType === 'ema') {
            strategyParams = {
                short_window: parseInt(document.getElementById('short-window').value),
                long_window: parseInt(document.getElementById('long-window').value)
            };
        } else if (strategyType === 'rsi') {
            strategyParams = {
                period: parseInt(document.getElementById('rsi-period').value),
                oversold: parseInt(document.getElementById('rsi-oversold').value),
                overbought: parseInt(document.getElementById('rsi-overbought').value)
            };
        } else if (strategyType === 'bollinger') {
            strategyParams = {
                period: parseInt(document.getElementById('bb-period').value),
                std_dev: parseFloat(document.getElementById('bb-std').value)
            };
        }
        
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
                    strategy_type: strategyType,
                    product_id: symbol,
                    days: parseInt(days),
                    granularity: parseInt(granularity),
                    stop_loss: stopLoss,
                    take_profit: takeProfit,
                    initial_capital: initialCapital,
                    strategy_params: strategyParams
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.displayBacktestResults(result);
            } else {
                resultsContainer.innerHTML = `
                    <div class="bg-red-50 border border-red-200 rounded-lg p-4">
                        <div class="flex items-center">
                            <i class="fas fa-exclamation-triangle text-red-500 mr-2"></i>
                            <h3 class="text-lg font-semibold text-red-800">Backtest Error</h3>
                        </div>
                        <p class="text-red-600 mt-2">${result.error}</p>
                        ${result.details ? `<details class="mt-2"><summary class="text-sm text-gray-600 cursor-pointer">Technical Details</summary><pre class="text-xs text-gray-500 mt-1 overflow-auto">${result.details}</pre></details>` : ''}
                    </div>
                `;
            }
        } catch (error) {
            console.error('Backtest error:', error);
            resultsContainer.innerHTML = `
                <div class="bg-red-50 border border-red-200 rounded-lg p-4">
                    <div class="flex items-center">
                        <i class="fas fa-exclamation-triangle text-red-500 mr-2"></i>
                        <h3 class="text-lg font-semibold text-red-800">Backtest Failed</h3>
                    </div>
                    <p class="text-red-600 mt-2">Failed to run backtest: ${error.message}</p>
                    <p class="text-sm text-gray-500 mt-1">Please check the server logs for more details.</p>
                </div>
            `;
        }
    }

    displayBacktestResults(result) {
        const resultsContainer = document.getElementById('backtest-results');
        
        const totalReturn = (result.result.total_return * 100).toFixed(2);
        const winRate = (result.result.win_rate * 100).toFixed(1);
        const totalTrades = result.result.total_trades;
        const sharpeRatio = result.result.sharpe_ratio?.toFixed(2) || 'N/A';
        const maxDrawdown = (result.result.max_drawdown * 100).toFixed(2);
        const profitFactor = result.result.profit_factor?.toFixed(2) || 'N/A';
        const netProfit = result.result.net_profit?.toFixed(2) || 'N/A';
        const finalBalance = result.result.final_balance?.toFixed(2) || 'N/A';
        
        // Signal statistics
        const totalSignals = result.result.total_signals || 0;
        const signalRate = result.result.signal_rate?.toFixed(2) || '0.00';
        const noSignalCount = result.result.no_signal_count || 0;
        const signalsByType = result.result.signals_by_type || {};
        
        const html = `
            <div class="bg-gradient-to-r from-green-50 to-blue-50 border border-green-200 rounded-lg p-6">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-xl font-bold text-gray-800">
                        <i class="fas fa-chart-line mr-2"></i>Backtest Results
                    </h3>
                    <span class="text-sm text-gray-500">${result.backtest_key}</span>
                </div>
                
                <!-- Key Metrics -->
                <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                    <div class="text-center bg-white rounded-lg p-3 shadow-sm">
                        <div class="text-2xl font-bold ${totalReturn >= 0 ? 'text-green-600' : 'text-red-600'}">${totalReturn}%</div>
                        <div class="text-sm text-gray-600">Total Return</div>
                    </div>
                    <div class="text-center bg-white rounded-lg p-3 shadow-sm">
                        <div class="text-2xl font-bold text-blue-600">${winRate}%</div>
                        <div class="text-sm text-gray-600">Win Rate</div>
                    </div>
                    <div class="text-center bg-white rounded-lg p-3 shadow-sm">
                        <div class="text-2xl font-bold text-purple-600">${totalTrades}</div>
                        <div class="text-sm text-gray-600">Total Trades</div>
                    </div>
                    <div class="text-center bg-white rounded-lg p-3 shadow-sm">
                        <div class="text-2xl font-bold text-orange-600">${sharpeRatio}</div>
                        <div class="text-sm text-gray-600">Sharpe Ratio</div>
                    </div>
                </div>
                
                <!-- Additional Metrics -->
                <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                    <div class="text-center bg-white rounded-lg p-3 shadow-sm">
                        <div class="text-lg font-semibold text-red-600">${maxDrawdown}%</div>
                        <div class="text-sm text-gray-600">Max Drawdown</div>
                    </div>
                    <div class="text-center bg-white rounded-lg p-3 shadow-sm">
                        <div class="text-lg font-semibold text-indigo-600">${profitFactor}</div>
                        <div class="text-sm text-gray-600">Profit Factor</div>
                    </div>
                    <div class="text-center bg-white rounded-lg p-3 shadow-sm">
                        <div class="text-lg font-semibold ${netProfit >= 0 ? 'text-green-600' : 'text-red-600'}">$${netProfit}</div>
                        <div class="text-sm text-gray-600">Net Profit</div>
                    </div>
                    <div class="text-center bg-white rounded-lg p-3 shadow-sm">
                        <div class="text-lg font-semibold text-gray-600">$${finalBalance}</div>
                        <div class="text-sm text-gray-600">Final Balance</div>
                    </div>
                </div>
                
                <!-- Performance Summary -->
                <div class="bg-white rounded-lg p-4 shadow-sm mb-6">
                    <h4 class="font-semibold text-gray-800 mb-2">Performance Summary</h4>
                    <div class="text-sm text-gray-600">
                        <p><strong>Period:</strong> ${result.result.start_date} to ${result.result.end_date}</p>
                        <p><strong>Initial Balance:</strong> $${result.result.initial_balance?.toFixed(2) || 'N/A'}</p>
                        <p><strong>Winning Trades:</strong> ${result.result.winning_trades} | <strong>Losing Trades:</strong> ${result.result.losing_trades}</p>
                        <p><strong>Average Win:</strong> $${result.result.avg_win?.toFixed(2) || 'N/A'} | <strong>Average Loss:</strong> $${result.result.avg_loss?.toFixed(2) || 'N/A'}</p>
                    </div>
                </div>
                
                <!-- Signal Statistics -->
                <div class="bg-white rounded-lg p-4 shadow-sm mb-6">
                    <h4 class="font-semibold text-gray-800 mb-4">
                        <i class="fas fa-signal mr-2"></i>Signal Statistics
                    </h4>
                    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                        <div class="text-center">
                            <div class="text-2xl font-bold text-blue-600">${totalSignals}</div>
                            <div class="text-sm text-gray-600">Total Signals</div>
                        </div>
                        <div class="text-center">
                            <div class="text-2xl font-bold text-green-600">${signalRate}%</div>
                            <div class="text-sm text-gray-600">Signal Rate</div>
                        </div>
                        <div class="text-center">
                            <div class="text-2xl font-bold text-orange-600">${noSignalCount}</div>
                            <div class="text-sm text-gray-600">No Signal Count</div>
                        </div>
                        <div class="text-center">
                            <div class="text-2xl font-bold text-purple-600">${totalTrades}</div>
                            <div class="text-sm text-gray-600">Executed Trades</div>
                        </div>
                    </div>
                    <div class="mt-4">
                        <h5 class="font-medium text-gray-700 mb-2">Signal Breakdown by Type:</h5>
                        <div class="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                            <div class="flex justify-between">
                                <span class="text-gray-600">Golden Cross:</span>
                                <span class="font-medium">${signalsByType.golden_cross || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Death Cross:</span>
                                <span class="font-medium">${signalsByType.death_cross || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Momentum Buy:</span>
                                <span class="font-medium">${signalsByType.momentum_buy || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Momentum Sell:</span>
                                <span class="font-medium">${signalsByType.momentum_sell || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Trend Buy:</span>
                                <span class="font-medium">${signalsByType.trend_buy || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Trend Sell:</span>
                                <span class="font-medium">${signalsByType.trend_sell || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Stop Loss:</span>
                                <span class="font-medium">${signalsByType.stop_loss || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Take Profit:</span>
                                <span class="font-medium">${signalsByType.take_profit || 0}</span>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Trades Table -->
                <div class="bg-white rounded-lg p-4 shadow-sm">
                    <div class="flex items-center justify-between mb-4">
                        <h4 class="font-semibold text-gray-800">
                            <i class="fas fa-list mr-2"></i>Trade History (${result.trades ? result.trades.length : 0} trades)
                        </h4>
                        <div class="flex space-x-2">
                            <button id="export-trades" class="text-green-600 hover:text-green-800 text-sm font-medium">
                                <i class="fas fa-download mr-1"></i>Export CSV
                            </button>
                            <button id="toggle-trades" class="text-blue-600 hover:text-blue-800 text-sm font-medium">
                                <i class="fas fa-eye mr-1"></i>Show Details
                            </button>
                        </div>
                    </div>
                    
                    <div id="trades-table-container" class="hidden">
                        ${this.generateTradesTable(result.trades || [])}
                    </div>
                    
                    <div id="trades-summary" class="text-sm text-gray-600">
                        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <div>
                                <p><strong>Total Trades:</strong> ${result.trades ? result.trades.length : 0}</p>
                                <p><strong>Winning Trades:</strong> ${result.trades ? result.trades.filter(t => t.pnl > 0).length : 0}</p>
                                <p><strong>Losing Trades:</strong> ${result.trades ? result.trades.filter(t => t.pnl < 0).length : 0}</p>
                            </div>
                            <div>
                                <p><strong>Largest Win:</strong> $${result.trades ? Math.max(...result.trades.map(t => t.pnl || 0)).toFixed(2) : '0.00'}</p>
                                <p><strong>Largest Loss:</strong> $${result.trades ? Math.min(...result.trades.map(t => t.pnl || 0)).toFixed(2) : '0.00'}</p>
                                <p><strong>Avg Win:</strong> $${result.trades ? (result.trades.filter(t => t.pnl > 0).reduce((sum, t) => sum + (t.pnl || 0), 0) / Math.max(result.trades.filter(t => t.pnl > 0).length, 1)).toFixed(2) : '0.00'}</p>
                            </div>
                            <div>
                                <p><strong>Avg Loss:</strong> $${result.trades ? (result.trades.filter(t => t.pnl < 0).reduce((sum, t) => sum + (t.pnl || 0), 0) / Math.max(result.trades.filter(t => t.pnl < 0).length, 1)).toFixed(2) : '0.00'}</p>
                                <p><strong>Total P&L:</strong> $${result.trades ? result.trades.reduce((sum, t) => sum + (t.pnl || 0), 0).toFixed(2) : '0.00'}</p>
                                <p><strong>Win Rate:</strong> ${result.trades ? ((result.trades.filter(t => t.pnl > 0).length / Math.max(result.trades.length, 1)) * 100).toFixed(1) : '0.0'}%</p>
                            </div>
                            <div>
                                <p><strong>Avg Trade:</strong> $${result.trades ? (result.trades.reduce((sum, t) => sum + (t.pnl || 0), 0) / Math.max(result.trades.length, 1)).toFixed(2) : '0.00'}</p>
                                <p><strong>Best Streak:</strong> ${this.calculateBestStreak(result.trades || [])}</p>
                                <p><strong>Worst Streak:</strong> ${this.calculateWorstStreak(result.trades || [])}</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        resultsContainer.innerHTML = html;
        
        // Add event listener for toggle trades button
        const toggleButton = document.getElementById('toggle-trades');
        if (toggleButton) {
            toggleButton.addEventListener('click', () => {
                const tableContainer = document.getElementById('trades-table-container');
                const icon = toggleButton.querySelector('i');
                
                if (tableContainer.classList.contains('hidden')) {
                    tableContainer.classList.remove('hidden');
                    icon.className = 'fas fa-eye-slash mr-1';
                    toggleButton.innerHTML = '<i class="fas fa-eye-slash mr-1"></i>Hide Details';
                } else {
                    tableContainer.classList.add('hidden');
                    icon.className = 'fas fa-eye mr-1';
                    toggleButton.innerHTML = '<i class="fas fa-eye mr-1"></i>Show Details';
                }
            });
        }

        // Add event listener for export trades button
        const exportButton = document.getElementById('export-trades');
        if (exportButton) {
            exportButton.addEventListener('click', () => {
                this.exportTradesToCSV(result.trades || []);
            });
        }
    }

    generateTradesTable(trades) {
        if (!trades || trades.length === 0) {
            return '<p class="text-gray-500 text-center py-4">No trades executed during this backtest period.</p>';
        }

        const tableRows = trades.map((trade, index) => {
            const entryTime = trade.entry_time ? new Date(trade.entry_time).toLocaleString() : 'N/A';
            const exitTime = trade.exit_time ? new Date(trade.exit_time).toLocaleString() : 'N/A';
            const pnl = parseFloat(trade.pnl || trade.profit_loss || 0);
            const pnlClass = pnl > 0 ? 'text-green-600' : pnl < 0 ? 'text-red-600' : 'text-gray-600';
            const pnlIcon = pnl > 0 ? 'fas fa-arrow-up' : pnl < 0 ? 'fas fa-arrow-down' : 'fas fa-minus';
            const duration = trade.duration ? `${trade.duration.toFixed(1)}h` : 'N/A';
            
            return `
                <tr class="border-b border-gray-200 hover:bg-gray-50">
                    <td class="px-4 py-3 text-sm text-gray-600">${index + 1}</td>
                    <td class="px-4 py-3 text-sm font-medium text-gray-900">${trade.side || 'Long'}</td>
                    <td class="px-4 py-3 text-sm text-gray-600">$${parseFloat(trade.entry_price || 0).toFixed(2)}</td>
                    <td class="px-4 py-3 text-sm text-gray-600">${parseFloat(trade.quantity || 0).toFixed(6)}</td>
                    <td class="px-4 py-3 text-sm text-gray-600">$${parseFloat(trade.exit_price || 0).toFixed(2)}</td>
                    <td class="px-4 py-3 text-sm text-gray-600">${entryTime}</td>
                    <td class="px-4 py-3 text-sm text-gray-600">${exitTime}</td>
                    <td class="px-4 py-3 text-sm font-medium ${pnlClass}">
                        <i class="${pnlIcon} mr-1"></i>$${pnl.toFixed(2)}
                    </td>
                    <td class="px-4 py-3 text-sm text-gray-600">${duration}</td>
                </tr>
            `;
        }).join('');

        return `
            <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-gray-200">
                    <thead class="bg-gray-50">
                        <tr>
                            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">#</th>
                            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Side</th>
                            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Entry Price</th>
                            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Quantity</th>
                            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Exit Price</th>
                            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Entry Time</th>
                            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Exit Time</th>
                            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">P&L</th>
                            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Duration</th>
                        </tr>
                    </thead>
                    <tbody class="bg-white divide-y divide-gray-200">
                        ${tableRows}
                    </tbody>
                </table>
            </div>
        `;
    }

    exportTradesToCSV(trades) {
        if (!trades || trades.length === 0) {
            this.showNotification('No trades to export', 'warning');
            return;
        }

        // Create CSV content
        const headers = ['Trade #', 'Side', 'Entry Price', 'Quantity', 'Exit Price', 'Entry Time', 'Exit Time', 'P&L', 'Duration (hours)', 'Fees'];
        const csvContent = [
            headers.join(','),
            ...trades.map((trade, index) => [
                index + 1,
                trade.side || 'Long',
                trade.entry_price || 0,
                trade.quantity || 0,
                trade.exit_price || 0,
                trade.entry_time || 'N/A',
                trade.exit_time || 'N/A',
                trade.pnl || trade.profit_loss || 0,
                trade.duration || 0,
                trade.fees || 0
            ].join(','))
        ].join('\n');

        // Create and download file
        const blob = new Blob([csvContent], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `backtest_trades_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        this.showNotification('Trades exported successfully', 'success');
    }

    calculateBestStreak(trades) {
        if (!trades || trades.length === 0) return 0;
        
        let currentStreak = 0;
        let bestStreak = 0;
        
        for (const trade of trades) {
            if (trade.pnl > 0) {
                currentStreak++;
                bestStreak = Math.max(bestStreak, currentStreak);
            } else {
                currentStreak = 0;
            }
        }
        
        return bestStreak;
    }

    calculateWorstStreak(trades) {
        if (!trades || trades.length === 0) return 0;
        
        let currentStreak = 0;
        let worstStreak = 0;
        
        for (const trade of trades) {
            if (trade.pnl < 0) {
                currentStreak++;
                worstStreak = Math.min(worstStreak, -currentStreak);
            } else {
                currentStreak = 0;
            }
        }
        
        return Math.abs(worstStreak);
    }

    switchTab(tabName) {
        // Hide all tab contents
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.add('hidden');
        });
        
        // Remove active class from all tab buttons
        document.querySelectorAll('.tab-button').forEach(button => {
            button.classList.remove('active');
            button.classList.add('border-transparent', 'text-white', 'text-opacity-80');
            button.classList.remove('border-white', 'text-white');
        });
        
        // Show selected tab content
        const contentId = `content-${tabName}`;
        const contentElement = document.getElementById(contentId);
        if (contentElement) {
            contentElement.classList.remove('hidden');
        }
        
        // Activate selected tab button
        const buttonId = `tab-${tabName}`;
        const buttonElement = document.getElementById(buttonId);
        if (buttonElement) {
            buttonElement.classList.add('active', 'border-white', 'text-white');
            buttonElement.classList.remove('border-transparent', 'text-white', 'text-opacity-80');
        }
        
        // Load data for specific tabs if needed
        if (tabName === 'dashboard') {
            this.loadInitialData();
        } else if (tabName === 'data') {
            this.loadDataFeed();
        }
    }

    clearBacktestResults() {
        const resultsContainer = document.getElementById('backtest-results');
        resultsContainer.classList.add('hidden');
        resultsContainer.innerHTML = '';
    }

    loadDataFeed() {
        // This method can be used to load data feed specific content
        console.log('Loading data feed...');
        // Load data summary when switching to data tab
        this.loadDataSummary();
    }

    updateStrategyParameters() {
        const strategyType = document.getElementById('strategy-type').value;
        
        // Hide all parameter groups
        document.querySelectorAll('.strategy-param-group').forEach(group => {
            group.classList.add('hidden');
        });
        
        // Show the selected strategy parameters
        const paramGroup = document.getElementById(`${strategyType}-params`);
        if (paramGroup) {
            paramGroup.classList.remove('hidden');
        }
        
        console.log(`Switched to ${strategyType} strategy parameters`);
    }

    async switchSymbol() {
        console.log(`Switching to symbol: ${this.currentSymbol}`);
        
        // Set flag to prevent real-time updates during switch
        this.isSwitchingSymbol = true;
        
        // Clear existing data
        this.candlesData = [];
        this.priceData = [];
        
        // Show loading notification
        this.showNotification(`Switching to ${this.currentSymbol}...`, 'info');
        
        console.log('Current state before switch:', {
            currentSymbol: this.currentSymbol,
            priceDataLength: this.priceData.length,
            candlesDataLength: this.candlesData.length
        });
        
        try {
            // Update WebSocket subscriptions (if connected)
            await this.updateWebSocketSubscriptions();
            
            // Clear existing chart data, y-axis range, layout, and historical prices
            this.candlesData = [];
            this.currentYAxisRange = null;
            this.currentLayout = null;
            this.historicalPrices = {};
            
            // Load current price and volume data for the new symbol
            await this.loadCurrentPriceData();
            
            // Reload chart data with rescaling
            await this.loadCandlesData();
            // Force chart rescale for new symbol
            this.updateCandlestickChart(true);
            
            // Update historical data
            await this.loadHistoricalData();
            
            // Wait a bit more to ensure WebSocket subscriptions are fully processed
            console.log('Waiting for WebSocket subscriptions to stabilize...');
            await new Promise(resolve => setTimeout(resolve, 2000));
            
            // Show success notification
            this.showNotification(`Successfully switched to ${this.currentSymbol}`, 'success');
        } catch (error) {
            console.error('Error switching symbol:', error);
            this.showNotification(`Error switching to ${this.currentSymbol}: ${error.message}`, 'error');
        } finally {
            // Clear the switching flag
            this.isSwitchingSymbol = false;
            console.log('Symbol switch completed, real-time updates re-enabled');
        }
    }

    async updateWebSocketSubscriptions() {
        // Check if WebSocket is connected
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            console.log('WebSocket not connected, skipping subscription updates');
            return;
        }
        
        try {
            // Get current subscriptions to unsubscribe from
            const subscriptions = await this.loadSubscriptions();
            console.log('Current subscriptions before switch:', subscriptions);
            
            // Unsubscribe from all current channels for any symbol
            const channels = ['ticker', 'level2', 'candles', 'matches', 'status', 'market_trades'];
            for (const channel of channels) {
                if (subscriptions[channel] && subscriptions[channel].length > 0) {
                    for (const productId of subscriptions[channel]) {
                        console.log(`Unsubscribing from ${channel} for ${productId}`);
                        await this.unsubscribeFromChannel(channel, productId);
                    }
                }
            }
            
            // Wait longer for unsubscriptions to complete
            console.log('Waiting for unsubscriptions to complete...');
            await new Promise(resolve => setTimeout(resolve, 1000));
            
            // Verify unsubscriptions worked
            const updatedSubscriptions = await this.loadSubscriptions();
            console.log('Subscriptions after unsubscribe:', updatedSubscriptions);
            
            // Subscribe to new symbol
            console.log(`Subscribing to ${this.currentSymbol}...`);
            await this.subscribeToChannel('ticker', this.currentSymbol);
            await this.subscribeToChannel('level2', this.currentSymbol);
            await this.subscribeToChannel('candles', this.currentSymbol);
            
            // Verify final subscriptions
            const finalSubscriptions = await this.loadSubscriptions();
            console.log('Final subscriptions:', finalSubscriptions);
            
            console.log(`Successfully switched to ${this.currentSymbol}`);
        } catch (error) {
            console.error('Error updating WebSocket subscriptions:', error);
            // If WebSocket operations fail, just reload the data without WebSocket updates
            console.log('Falling back to data-only mode for symbol switch');
        }
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
        // Refresh data summary every 5 seconds
        setInterval(() => {
            this.loadDataSummary();
        }, 5000);
        
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
