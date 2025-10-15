/**
 * LiveTrading Module
 * Handles live trading functionality and order book signals
 */
export class LiveTrading {
    constructor(dashboard) {
        this.dashboard = dashboard;
        this.isActive = false;
        this.mode = 'simulated';
        this.symbolMode = 'single';
        this.strategy = null;
        this.symbols = [];
        this.positions = [];
        this.orderBookRefreshInterval = null;
        // Live Order Book pagination state
        this.orderBookPage = 1;
        this.orderBookPerPage = 50;
    }

    setupLiveTrading() {
        this.setupLiveTradingEventListeners();
        this.loadProducts();
    }

    setupLiveTradingEventListeners() {
        // Tab switching
        const liveTab = document.getElementById('live-trading-tab');
        if (liveTab) {
            liveTab.addEventListener('click', () => {
                this.loadLiveTradingData();
            });
        }

        // Trading mode selection
        const modeRadios = document.querySelectorAll('input[name="trading-mode"]');
        modeRadios.forEach(radio => {
            radio.addEventListener('change', (e) => {
                this.dashboard.liveTrading.mode = e.target.value;
                this.dashboard.uiUtils.updateTradingModeUI();
            });
        });

        // Symbol trading mode selection
        const symbolModeRadios = document.querySelectorAll('input[name="trading-symbol-mode"]');
        console.log('Found symbol mode radios:', symbolModeRadios.length);
        symbolModeRadios.forEach(radio => {
            radio.addEventListener('change', (e) => {
                console.log('Symbol mode changed to:', e.target.value);
                console.log('Dashboard object:', this.dashboard);
                console.log('Dashboard liveTrading object:', this.dashboard.liveTrading);
                
                // Ensure the liveTrading object exists
                if (!this.dashboard.liveTrading) {
                    console.error('Dashboard liveTrading object is undefined, initializing...');
                    this.dashboard.liveTrading = {
                        isActive: false,
                        mode: 'simulated',
                        symbolMode: 'single',
                        strategy: null,
                        symbols: [],
                        positions: []
                    };
                }
                
                this.dashboard.liveTrading.symbolMode = e.target.value;
                console.log('Updated symbolMode to:', this.dashboard.liveTrading.symbolMode);
                this.dashboard.uiUtils.updateSymbolModeUI();
                
                // Only refresh order book signals if trading is active
                if (this.isActive) {
                    this.loadLiveTradingData();
                }
            });
        });

        // Live trading symbol mode selection
        const liveSymbolModeRadios = document.querySelectorAll('input[name="live-trading-symbol-mode"]');
        liveSymbolModeRadios.forEach(radio => {
            radio.addEventListener('change', (e) => {
                this.dashboard.liveTrading.symbolMode = e.target.value;
                this.dashboard.uiUtils.updateSymbolModeUI();
            });
        });

        // Live trading strategy presets
        const strategySelect = document.getElementById('live-strategy-type');
        if (strategySelect) {
            strategySelect.addEventListener('change', (e) => {
                this.dashboard.strategyConfig.loadStrategyParameters(e.target.value);
            });
        }

        // Universe type selection
        const universeTypeSelect = document.getElementById('universe-type');
        if (universeTypeSelect) {
            universeTypeSelect.addEventListener('change', (e) => {
                this.dashboard.uiUtils.updateUniverseTypeUI();
                
                // Only refresh order book signals if trading is active
                if (this.isActive) {
                    this.loadLiveTradingData();
                }
            });
        }

        // Single symbol selection
        const singleSymbolSelect = document.getElementById('live-trading-symbol');
        if (singleSymbolSelect) {
            singleSymbolSelect.addEventListener('change', (e) => {
                // Only refresh order book signals if trading is active
                if (this.isActive) {
                    this.loadLiveTradingData();
                }
            });
        }

        // Custom symbol management
        const customSymbolsInput = document.getElementById('custom-symbols-input');
        if (customSymbolsInput) {
            customSymbolsInput.addEventListener('input', (e) => {
                // Only refresh order book signals if trading is active
                if (this.isActive) {
                    this.loadLiveTradingData();
                }
            });

            customSymbolsInput.addEventListener('keypress', (e) => {
                // Only refresh order book signals if trading is active
                if (e.key === 'Enter') {
                    if (this.isActive) {
                        this.loadLiveTradingData();
                    }
                }
            });
        }

        // Strategy type change
        const strategyTypeSelect = document.getElementById('live-strategy-type');
        if (strategyTypeSelect) {
            strategyTypeSelect.addEventListener('change', (e) => {
                this.dashboard.strategyConfig.loadStrategyParameters(e.target.value);
            });
        }

        // Note: Universe strategy type is now handled by the main live-strategy-type selector

        // Order Book preset selection handler
        const presetSelect = document.getElementById('live-orderbook-preset');
        if (presetSelect) {
            presetSelect.addEventListener('change', (e) => {
                this.dashboard.strategyConfig.handleOrderBookPresetSelection(e.target.value);
            });
        }

        // Trading controls
        const startButton = document.getElementById('start-trading');
        const stopButton = document.getElementById('stop-trading');
        
        console.log('Setting up trading controls:', { startButton, stopButton });
        
        if (startButton) {
            startButton.addEventListener('click', (e) => {
                console.log('Start trading button clicked');
                e.preventDefault();
                this.startTrading();
            });
        } else {
            console.warn('Start trading button not found');
        }

        if (stopButton) {
            stopButton.addEventListener('click', (e) => {
                console.log('Stop trading button clicked');
                e.preventDefault();
                this.stopTrading();
            });
        } else {
            console.warn('Stop trading button not found');
        }

        // Order book signals refresh button
        const refreshButton = document.getElementById('refresh-orderbook-signals');
        if (refreshButton) {
            refreshButton.addEventListener('click', () => {
                this.loadLiveTradingData();
            });
        }

        // Live Order Book pagination controls
        const livePrevBtn = document.getElementById('live-orderbook-prev');
        const liveNextBtn = document.getElementById('live-orderbook-next');
        const livePageSize = document.getElementById('live-orderbook-page-size');

        if (livePrevBtn) {
            livePrevBtn.addEventListener('click', () => {
                if (this.orderBookPage > 1) {
                    this.orderBookPage -= 1;
                    this.loadLiveTradingData();
                }
            });
        }

        if (liveNextBtn) {
            liveNextBtn.addEventListener('click', () => {
                this.orderBookPage += 1;
                this.loadLiveTradingData();
            });
        }

        if (livePageSize) {
            try { livePageSize.value = String(this.orderBookPerPage); } catch (_) {}
            livePageSize.addEventListener('change', () => {
                const newSize = parseInt(livePageSize.value, 10) || 50;
                this.orderBookPerPage = newSize;
                this.orderBookPage = 1;
                this.loadLiveTradingData();
            });
        }

        // Simulated trading stats refresh button
        const refreshStatsButton = document.getElementById('refresh-simulated-stats');
        if (refreshStatsButton) {
            refreshStatsButton.addEventListener('click', () => {
                this.dashboard.simulatedTrading.loadSimulatedTradingStats();
            });
        }

        // Live trading stats refresh button
        const refreshLiveStatsButton = document.getElementById('refresh-live-trading-stats');
        if (refreshLiveStatsButton) {
            refreshLiveStatsButton.addEventListener('click', () => {
                this.loadLiveTradingStats();
            });
        }

        // Strategy configuration hide/show buttons
        const hideStrategyBtn = document.getElementById('hide-strategy-config');
        const showStrategyBtn = document.getElementById('show-strategy-section');
        
        if (hideStrategyBtn) {
            hideStrategyBtn.addEventListener('click', () => {
                this.dashboard.strategyConfig.hideStrategyConfiguration();
            });
        }

        if (showStrategyBtn) {
            showStrategyBtn.addEventListener('click', () => {
                this.dashboard.strategyConfig.showStrategyConfiguration();
            });
        }

        // Auto-refresh order book signals every 30 seconds when on live trading tab
        this.startOrderBookAutoRefresh();
    }

    async loadProducts() {
        const symbolSelector = document.getElementById('live-trading-symbol');
        if (symbolSelector && symbolSelector.children.length <= 1) {
            try {
                const response = await fetch('/api/products');
                const data = await response.json();
                
                if (data.status === 'success') {
                    this.dashboard.uiUtils.populateProductSelectors(data.categories);
                }
            } catch (error) {
                console.error('Error loading products:', error);
            }
        }
    }

    async getSelectedSymbols() {
        const symbolMode = document.querySelector('input[name="trading-symbol-mode"]:checked')?.value;
        
        if (symbolMode === 'universe') {
            const universeType = document.getElementById('universe-type')?.value;
            
            if (universeType === 'custom') {
                const customSymbols = document.getElementById('custom-symbols-input')?.value;
                return customSymbols ? customSymbols.split(',').map(s => s.trim()).filter(s => s) : [];
            } else {
                // Load universe symbols from API
                try {
                    const response = await fetch('/api/products');
                    const data = await response.json();
                    
                    if (data.status === 'success') {
                        const categories = data.categories;
                        let symbols = [];
                        
                        switch (universeType) {
                            case 'major':
                                symbols = categories.major || [];
                                break;
                            case 'minor':
                                symbols = categories.minor || [];
                                break;
                            case 'crypto':
                                symbols = categories.crypto || [];
                                break;
                            case 'all_usd':
                                symbols = categories.all_usd || [];
                                break;
                            case 'all_eur':
                                symbols = categories.all_eur || [];
                                break;
                            case 'all_usdt':
                                symbols = categories.all_usdt || [];
                                break;
                            case 'all_btc':
                                symbols = categories.all_btc || [];
                                break;
                            case 'all_products':
                                symbols = categories.all_products || [];
                                break;
                            default:
                                symbols = [];
                        }
                        
                        // Apply max universe size limit
                        const maxSize = parseInt(document.getElementById('universe-max-size')?.value) || 50;
                        return symbols.slice(0, maxSize);
                    }
                } catch (error) {
                    console.error('Error loading universe symbols:', error);
                }
                return [];
            }
        } else {
            const symbol = document.getElementById('live-trading-symbol')?.value;
            return symbol ? [symbol] : [];
        }
    }

    async loadLiveTradingData() {
        // Check if trading is active locally or on the server
        let tradingActive = this.isActive;
        
        // If not active locally, check server status
        if (!tradingActive) {
            console.log('🔍 Trading not active locally, checking server status...');
            try {
                const response = await fetch('/api/simulated-trading/status');
                const data = await response.json();
                tradingActive = data.is_trading || false;
                console.log('🔍 Server trading status:', tradingActive, data);
                
                // Update local state if server shows trading is active
                if (tradingActive && !this.isActive) {
                    console.log('🔄 Updating local state to active');
                    this.isActive = true;
                    this.dashboard.liveTrading.isActive = true;
                }
            } catch (error) {
                console.error('Error checking trading status:', error);
            }
        }
        
        if (!tradingActive) {
            console.log('❌ Trading not active, showing empty state');
            // Show empty state when trading is not active
            this.updateOrderBookSignalsTable([]);
            this.updateOrderBookStatistics({
                total_analyzed: 0,
                active_signals: 0,
                last_updated: new Date().toISOString(),
                average_strength: 0,
                message: "Trading is not active. Configure your strategy and start trading to see live signals."
            });
            return;
        }

        const selectedSymbols = await this.getSelectedSymbols();
        
        if (!selectedSymbols || selectedSymbols.length === 0) {
            console.warn('No symbols selected for live trading');
            return;
        }

        // Validate symbols
        const validSymbols = selectedSymbols.filter(symbol => {
            const isValid = typeof symbol === 'string' && symbol.trim() !== '' && !symbol.includes('object');
            if (!isValid) {
                console.warn(`Invalid symbol: ${symbol}`);
            }
            return isValid;
        });

        if (validSymbols.length === 0) {
            console.error('No valid symbols selected');
            return;
        }

        try {
            let apiUrl = '/api/orderbook/live-signals';
            const symbolsParam = validSymbols.join(',');
            apiUrl += `?symbols=${symbolsParam}&page=${this.orderBookPage}&per_page=${this.orderBookPerPage}`;

            const response = await fetch(apiUrl);
            const data = await response.json();

            if (data.error) {
                console.error('Error loading order book signals:', data.error);
                return;
            }

            if (data.trading_active === false) {
                console.warn('Trading is not active');
                return;
            }

            // Update pagination if available
            if (data.pagination) {
                this.updateLiveOrderBookPagination(data.pagination);
            }

            // Update order book signals table
            if (data.signals) {
                this.updateOrderBookSignalsTable(data.signals);
                
                // Process signals if trading is active
                if (this.isActive && data.signals && data.signals.length > 0) {
                    const activeSignals = data.signals.filter(s => s.signal_generated === true);
                    
                    if (activeSignals.length > 0) {
                        try {
                            const processResponse = await fetch('/api/trading/simulated/process-signals', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json'
                                },
                                body: JSON.stringify({ signals: activeSignals })
                            });

                            const processData = await processResponse.json();
                            
                            if (processData.status === 'processed') {
                                const executedTrades = processData.executed_trades || 0;
                                if (executedTrades > 0) {
                                    console.log(`Processed ${executedTrades} trades from signals`);
                                    // Refresh trading stats after processing
                                    this.dashboard.tradingStats.loadTradingStats();
                                    this.dashboard.simulatedTrading.loadSimulatedTradingStats();
                                }
                            }
                        } catch (error) {
                            console.error('Error processing signals:', error);
                        }
                    }
                }
            }

            // Update order book statistics
            this.updateOrderBookStatistics(data);

            // Load additional trading data
            await this.loadAdditionalTradingData();

            // Auto-refresh if trading is active
            if (this.isActive) {
                this.startOrderBookFrequentRefresh();
            }
        } catch (error) {
            console.error('Error loading live trading data:', error);
        }
    }

    async loadAdditionalTradingData() {
        try {
            // Load trading stats
            await this.dashboard.tradingStats.loadTradingStats();
            
            // Load simulated trading stats
            await this.dashboard.simulatedTrading.loadSimulatedTradingStats();
            
            // Load live trading stats (ensure Live tab KPIs stay in sync in simulated mode)
            await this.loadLiveTradingStats();
            
            // Load trading history
            await this.dashboard.pagination.loadTradingHistory();
            
            // Load open positions
            await this.dashboard.pagination.loadPositions();
            
            // Load order book signals (refresh)
            await this.dashboard.pagination.loadOrderBookSignals();
        } catch (error) {
            console.error('Error loading additional trading data:', error);
        }
    }

    updateOrderBookSignalsTable(signals) {
        const tableBody = document.getElementById('orderbook-signals-table');
        if (!tableBody) {
            console.warn('Order book signals table not found');
            return;
        }

        // Clear existing content
        tableBody.innerHTML = '';

        if (signals.length === 0) {
            const row = document.createElement('tr');
            row.innerHTML = '<td colspan="4" class="px-6 py-4 text-center text-gray-500">No signals available</td>';
            tableBody.appendChild(row);
            return;
        }

        signals.forEach(signal => {
            const row = document.createElement('tr');
            row.className = 'hover:bg-gray-50';

            let signalClass = 'text-gray-600 bg-gray-50';
            if (signal.signal_generated === true) {
                signalClass = 'text-green-600 bg-green-50';
            } else if (signal.signal_generated === false) {
                signalClass = 'text-red-600 bg-red-50';
            }

            const strengthColor = (signal.signal_strength || 0) >= 0.7 ? 'text-green-600' : 
                                 (signal.signal_strength || 0) >= 0.4 ? 'text-yellow-600' : 'text-red-600';

            // Get criteria analysis
            const criteria = signal.criteria_analysis || {};
            const squeeze = criteria.bid_ask_squeeze || { enabled: false, meets_criteria: false, delta_to_threshold: 0, threshold_spread: 0 };
            const imbalanceBuy = criteria.volume_imbalance_buy || { enabled: false, meets_criteria: false, delta_to_threshold: 0, threshold: 0 };
            const imbalanceSell = criteria.volume_imbalance_sell || { enabled: false, meets_criteria: false, delta_to_threshold: 0, threshold: 0 };
            const largeTradeBuy = criteria.large_trade_buy || { enabled: false, meets_criteria: false, delta_to_threshold: 0, large_trades_count: 0 };
            const largeTradeSell = criteria.large_trade_sell || { enabled: false, meets_criteria: false, delta_to_threshold: 0, large_trades_count: 0 };

            // Helper functions for status colors
            const getStatusColor = (meets, enabled) => {
                if (!enabled) return 'text-gray-400';
                return meets ? 'text-green-600' : 'text-red-600';
            };

            const getDeltaColor = (delta) => {
                if (delta > 0) return 'text-green-600';
                if (delta < 0) return 'text-red-600';
                return 'text-gray-600';
            };

            const getDataStatusIcon = (status) => {
                switch (status) {
                    case 'sufficient': return '✅';
                    case 'insufficient': return '⚠️';
                    case 'error': return '❌';
                    default: return '❓';
                }
            };

            const getDataStatusColor = (status) => {
                switch (status) {
                    case 'sufficient': return 'text-green-600';
                    case 'insufficient': return 'text-yellow-600';
                    case 'error': return 'text-red-600';
                    default: return 'text-gray-600';
                }
            };

            row.innerHTML = `
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${signal.symbol}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm ${signalClass}">
                    ${signal.signal_generated ? 'Active' : 'Inactive'}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm ${strengthColor}">
                    ${(signal.signal_strength || 0).toFixed(2)}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${new Date(signal.timestamp).toLocaleString()}</td>
            `;

            tableBody.appendChild(row);
        });
    }

    updateLiveOrderBookPagination(pagination) {
        const pageInfo = document.getElementById('live-orderbook-page-info');
        const prevBtn = document.getElementById('live-orderbook-prev');
        const nextBtn = document.getElementById('live-orderbook-next');
        const pageSize = document.getElementById('live-orderbook-page-size');

        if (pageInfo) {
            pageInfo.textContent = `Page ${pagination.current_page} of ${pagination.total_pages}`;
        }
        if (prevBtn) {
            prevBtn.disabled = pagination.current_page <= 1;
        }
        if (nextBtn) {
            nextBtn.disabled = pagination.current_page >= pagination.total_pages;
        }
        if (pageSize) {
            try { pageSize.value = String(this.orderBookPerPage); } catch (_) {}
        }

        // Sync internal state with backend pagination (in case server adjusted values)
        this.orderBookPage = pagination.current_page || this.orderBookPage;
    }

    updateOrderBookStatistics(data) {
        const totalAnalyzed = document.getElementById('total-analyzed');
        const activeSignals = document.getElementById('active-signals');
        const lastUpdated = document.getElementById('last-updated');
        const avgStrength = document.getElementById('avg-strength');

        // Handle message display
        if (data.message) {
            const messageElement = document.getElementById('orderbook-message');
            const messageTextElement = document.getElementById('orderbook-message-text');
            
            if (messageElement && messageTextElement) {
                messageTextElement.textContent = data.message;
                messageElement.style.display = 'block';
            }
        } else {
            const messageElement = document.getElementById('orderbook-message');
            if (messageElement) {
                messageElement.style.display = 'none';
            }
        }

        // Update statistics
        if (totalAnalyzed) {
            const total = (data.pagination && typeof data.pagination.total_signals === 'number')
                ? data.pagination.total_signals
                : (typeof data.total_analyzed === 'number' ? data.total_analyzed : (data.signals ? data.signals.length : 0));
            totalAnalyzed.textContent = total;
        }

        if (activeSignals) {
            const activeCount = (typeof data.active_signals === 'number')
                ? data.active_signals
                : (data.signals ? data.signals.filter(s => s.signal_generated === true).length : 0);
            activeSignals.textContent = activeCount;
        }

        if (lastUpdated) {
            const now = new Date();
            lastUpdated.textContent = now.toLocaleTimeString();
        }

        if (avgStrength && data.signals && data.signals.length > 0) {
            const avg = data.signals.reduce((sum, s) => sum + s.signal_strength, 0) / data.signals.length;
            avgStrength.textContent = avg.toFixed(2);
        }
    }

    startOrderBookAutoRefresh() {
        // Clear existing interval
        if (this.orderBookRefreshInterval) {
            clearInterval(this.orderBookRefreshInterval);
        }

        // Start auto-refresh every 30 seconds
        this.orderBookRefreshInterval = setInterval(() => {
            this.loadLiveTradingData();
            // Keep live trading KPIs updated alongside signals
            this.loadLiveTradingStats();
            // Also refresh simulated trading stats when in simulated mode
            try {
                if (this.dashboard?.liveTrading?.mode === 'simulated' && this.dashboard?.simulatedTrading) {
                    this.dashboard.simulatedTrading.loadSimulatedTradingStats();
                }
            } catch (_) {}
        }, 30000);
    }

    startOrderBookFrequentRefresh() {
        // Clear existing interval
        if (this.orderBookRefreshInterval) {
            clearInterval(this.orderBookRefreshInterval);
        }

        // Start frequent refresh every 5 seconds when trading is active
        this.orderBookRefreshInterval = setInterval(() => {
            if (this.isActive) {
                this.loadLiveTradingData();
                // Refresh Live KPIs on the same cadence as signals
                this.loadLiveTradingStats();
                // Keep simulated trading widget in sync during simulated mode
                try {
                    if (this.dashboard?.liveTrading?.mode === 'simulated' && this.dashboard?.simulatedTrading) {
                        this.dashboard.simulatedTrading.loadSimulatedTradingStats();
                    }
                } catch (_) {}
            }
        }, 5000);
    }

    stopOrderBookAutoRefresh() {
        if (this.orderBookRefreshInterval) {
            clearInterval(this.orderBookRefreshInterval);
            this.orderBookRefreshInterval = null;
        }
    }

    async startTrading() {
        console.log('startTrading called');
        const mode = this.mode;
        const strategy = document.getElementById('live-strategy-type')?.value;
        const symbols = await this.getSelectedSymbols();
        
        console.log('Trading parameters:', { mode, strategy, symbols });
        
        if (!strategy || !symbols || symbols.length === 0) {
            this.dashboard.uiUtils.showMessage('Please select a strategy and symbols', 'error');
            return;
        }

        // Get strategy parameters
        const parameters = {};
        const paramInputs = document.querySelectorAll('#live-strategy-params input, #live-strategy-params select');
        paramInputs.forEach(input => {
            if (input.id && input.id.startsWith('live-')) {
                const paramName = input.id.replace('live-', '');
                parameters[paramName] = input.type === 'number' ? parseFloat(input.value) : input.value;
            }
        });

        // Read trading controls from UI depending on symbol mode
        let positionSizePercent;
        let maxPositions;
        let positionUpdateInterval;
        try {
            const symbolMode = document.querySelector('input[name="trading-symbol-mode"]:checked')?.value;
            positionUpdateInterval = parseInt(document.getElementById('live-position-update-interval')?.value) || 5;
            if (symbolMode === 'universe') {
                const universePositionSizeEl = document.getElementById('universe-position-size');
                const universeMaxPositionsEl = document.getElementById('universe-max-positions');
                if (universePositionSizeEl) positionSizePercent = parseFloat(universePositionSizeEl.value);
                if (universeMaxPositionsEl) maxPositions = parseInt(universeMaxPositionsEl.value);
            } else {
                const singlePosSizeEl = document.getElementById('live-position-size');
                const singleMaxPosEl = document.getElementById('live-max-positions');
                if (singlePosSizeEl) positionSizePercent = parseFloat(singlePosSizeEl.value);
                if (singleMaxPosEl) maxPositions = parseInt(singleMaxPosEl.value);
            }
        } catch (e) {
            console.warn('Unable to read trading control values:', e);
        }

        try {
            const response = await this.dashboard.dataManager.startTrading(
                mode,
                strategy,
                symbols,
                parameters,
                {
                    position_size_percent: positionSizePercent,
                    max_positions: maxPositions,
                    position_update_interval: positionUpdateInterval
                }
            );
            
            if (response && (response.status === 'success' || response.status === 'started')) {
                this.isActive = true;
                this.mode = mode;
                this.strategy = strategy;
                this.symbols = symbols;
                
                this.dashboard.uiUtils.updateTradingModeUI();
                this.dashboard.strategyConfig.autoHideStrategyOnTradingStart();
                
                this.dashboard.uiUtils.showMessage('Trading started successfully', 'success');
                
                // Load live trading data and stats immediately after starting
                await this.loadLiveTradingData();
                await this.loadLiveTradingStats();
                
                // Load simulated trading stats to update the simulated trading widget
                await this.dashboard.simulatedTrading.loadSimulatedTradingStats();
                
                // Start auto-refresh
                this.startOrderBookFrequentRefresh();
            } else {
                const errDetail = response?.error || response?.detail || response?.message || 'Unknown error';
                this.dashboard.uiUtils.showMessage('Failed to start trading: ' + errDetail, 'error');
            }
        } catch (error) {
            console.error('Error starting trading:', error);
            this.dashboard.uiUtils.showMessage('Error starting trading: ' + error.message, 'error');
        }
    }

    async stopTrading() {
        try {
            const response = await this.dashboard.dataManager.stopTrading();
            
            if (response && response.status === 'success') {
                this.isActive = false;
                this.strategy = null;
                this.symbols = [];
                
                this.dashboard.uiUtils.updateTradingModeUI();
                this.stopOrderBookAutoRefresh();
                
                this.dashboard.uiUtils.showMessage('Trading stopped successfully', 'success');
            } else {
                this.dashboard.uiUtils.showMessage('Failed to stop trading: ' + (response?.error || 'Unknown error'), 'error');
            }
        } catch (error) {
            console.error('Error stopping trading:', error);
            this.dashboard.uiUtils.showMessage('Error stopping trading: ' + error.message, 'error');
        }
    }

    async loadLiveTradingStats() {
        try {
            // Load simulated trading stats (which are the same as live stats in simulated mode)
            const response = await fetch('/api/simulated-trading/status');
            const data = await response.json();

            if (data.portfolio) {
                // Attempt to fetch Sharpe ratio from trades stats API
                let sharpeRatio = 0.0;
                try {
                    const statsResp = await fetch('/api/trades/stats');
                    const statsData = await statsResp.json();
                    if (statsData && statsData.status === 'success' && statsData.stats) {
                        sharpeRatio = statsData.stats.sharpe_ratio ?? 0.0;
                    } else if (statsData && typeof statsData.sharpe_ratio !== 'undefined') {
                        sharpeRatio = statsData.sharpe_ratio ?? 0.0;
                    }
                } catch (e) {
                    // Keep default sharpeRatio = 0.0 on failure
                    console.warn('Unable to load Sharpe ratio from /api/trades/stats:', e);
                }

                // Normalize portfolio shape to include trades and positions for UI calculations
                const portfolio = { ...data.portfolio };
                if (Array.isArray(data.recent_trades)) {
                    portfolio.trades = data.recent_trades;
                    portfolio.recent_trades = data.recent_trades;
                } else if (!Array.isArray(portfolio.trades)) {
                    portfolio.trades = [];
                }
                if (Array.isArray(data.open_positions)) {
                    portfolio.positions = data.open_positions;
                } else if (!portfolio.positions) {
                    portfolio.positions = [];
                }

                this.updateLiveTradingStats(portfolio, { sharpeRatio });
            } else {
                console.error('No portfolio data received for live trading stats');
            }
        } catch (error) {
            console.error('Error loading live trading stats:', error);
        }
    }

    updateLiveTradingStats(portfolioData, extras = {}) {
        if (!portfolioData) {
            return;
        }

        // Calculate proper statistics from portfolio data (same as simulated trading)
        const trades = portfolioData.trades || [];
        const positions = portfolioData.positions || {};

        // Calculate trade-based metrics
        const winningTrades = trades.filter(trade => trade.pnl > 0);
        const losingTrades = trades.filter(trade => trade.pnl < 0);
        const totalTrades = trades.length;
        const winningTradesCount = winningTrades.length;
        const losingTradesCount = losingTrades.length;

        // Calculate P&L metrics
        const totalPnl = portfolioData.total_pnl || 0;
        const totalFees = portfolioData.total_fees || 0;
        const netPnl = totalPnl - totalFees;

        // Calculate win rate
        const winRate = totalTrades > 0 ? (winningTradesCount / totalTrades) * 100 : 0;

        // Calculate trade size metrics (volume = quantity * price)
        const totalTradeVolume = trades.reduce((sum, trade) => sum + (trade.quantity * trade.price), 0);
        const avgTradeSize = totalTrades > 0 ? totalTradeVolume / totalTrades : 0;

        // Calculate best/worst trades (only from realized trades)
        const bestTrade = trades.length > 0 ? Math.max(...trades.map(t => t.pnl || 0)) : 0;
        const worstTrade = trades.length > 0 ? Math.min(...trades.map(t => t.pnl || 0)) : 0;

        // Calculate average win/loss
        const avgWin = winningTradesCount > 0 ? winningTrades.reduce((sum, trade) => sum + trade.pnl, 0) / winningTradesCount : 0;
        const avgLoss = losingTradesCount > 0 ? losingTrades.reduce((sum, trade) => sum + trade.pnl, 0) / losingTradesCount : 0;

        // Calculate profit factor
        const grossProfit = winningTrades.reduce((sum, trade) => sum + trade.pnl, 0);
        const grossLoss = Math.abs(losingTrades.reduce((sum, trade) => sum + trade.pnl, 0));
        const profitFactor = grossLoss > 0 ? grossProfit / grossLoss : (grossProfit > 0 ? Infinity : 0);

        // Use Sharpe ratio from extras when available (backend-derived)
        const sharpeRatio = typeof extras.sharpeRatio === 'number' ? extras.sharpeRatio : 0.0;

        // Calculate risk-adjusted return
        const riskAdjustedReturn = 0.0; // Placeholder - would need proper risk metrics

        // Count active positions
        const activePositions = Object.values(positions).filter(pos => pos.status === 'open').length;

        // Calculate position value
        const positionValue = Object.values(positions).reduce((sum, pos) => {
            if (pos.status === 'open') {
                return sum + (pos.quantity * pos.current_price || 0);
            }
            return sum;
        }, 0);

        // Max drawdown from portfolio (could be fraction [0..1] or percentage)
        const rawMaxDrawdown = typeof portfolioData.max_drawdown === 'number' ? portfolioData.max_drawdown : 0.0;
        const maxDrawdown = rawMaxDrawdown; // Keep raw; format in UI (handle fraction vs percent)

        // Update live trading stats UI
        this.updateLiveTradingStatsUI({
            totalPnl: totalPnl,
            totalFees: totalFees,
            netPnl: netPnl,
            winRate: winRate,
            totalTrades: totalTrades,
            winningTrades: winningTradesCount,
            losingTrades: losingTradesCount,
            avgWin: avgWin,
            avgLoss: avgLoss,
            bestTrade: bestTrade,
            worstTrade: worstTrade,
            profitFactor: profitFactor,
            sharpeRatio: sharpeRatio,
            riskAdjustedReturn: riskAdjustedReturn,
            totalVolume: totalTradeVolume,
            avgTradeSize: avgTradeSize,
            activePositions: activePositions,
            grossProfit: grossProfit,
            grossLoss: grossLoss,
            positionValue: positionValue,
            maxDrawdown: maxDrawdown
        });
    }

    updateLiveTradingStatsUI(stats) {
        // Update main stats
        this.updateElement('live-total-pnl', stats.netPnl.toFixed(2));
        this.updateElement('live-win-rate', stats.winRate.toFixed(1) + '%');
        this.updateElement('live-total-trades', stats.totalTrades);
        this.updateElement('live-position-value', stats.positionValue.toFixed(2));

        // Performance Metrics
        this.updateElement('live-avg-win', stats.avgWin.toFixed(2));
        this.updateElement('live-avg-loss', stats.avgLoss.toFixed(2));
        this.updateElement('live-best-trade', stats.bestTrade.toFixed(2));
        this.updateElement('live-worst-trade', stats.worstTrade.toFixed(2));

        // Risk Metrics
        this.updateElement('live-profit-factor', stats.profitFactor === Infinity ? '∞' : stats.profitFactor.toFixed(2));
        this.updateElement('live-sharpe-ratio', stats.sharpeRatio.toFixed(2));
        const maxDDPct = (typeof stats.maxDrawdown === 'number') ? (stats.maxDrawdown > 1 ? stats.maxDrawdown : stats.maxDrawdown * 100) : 0.0;
        this.updateElement('live-max-drawdown', maxDDPct.toFixed(2) + '%');
        this.updateElement('live-total-volume', stats.totalVolume.toFixed(2));

        // Additional metrics
        this.updateElement('live-pnl-change', '+$0.00'); // Placeholder
        this.updateElement('live-win-rate-change', '+0%'); // Placeholder
        this.updateElement('live-trades-today', 'Today: 0'); // Placeholder
    }

    updateElement(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
    }
}
