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
        this.websocketSubscriptionsUpdated = false; // Flag to track when WebSocket subscriptions are updated
        this.hasRealTimeData = false; // Track if we have real-time data for current symbol
        
        // Backtest history properties
        this.historyLimit = 20;
        this.currentHistoryOffset = 0;
        this.totalHistoryCount = 0;
        
        // Order Book strategy presets
        this.orderBookPresets = {
            'conservative': {
                order_book_level: 2,
                trade_history_limit: 100,
                bid_ask_spread_threshold: 0.1,
                volume_imbalance_threshold: 0.6,
                large_trade_threshold: 10000,
                data_analysis_mode: 'recent',
                recent_data_limit: 50,
                sampling_ratio: 0.1
            },
            'moderate': {
                order_book_level: 2,
                trade_history_limit: 500,
                bid_ask_spread_threshold: 0.2,
                volume_imbalance_threshold: 0.4,
                large_trade_threshold: 5000,
                data_analysis_mode: 'recent',
                recent_data_limit: 100,
                sampling_ratio: 0.1
            },
            'aggressive': {
                order_book_level: 2,
                trade_history_limit: 1000,
                bid_ask_spread_threshold: 0.5,
                volume_imbalance_threshold: 0.3,
                large_trade_threshold: 2000,
                data_analysis_mode: 'all',
                recent_data_limit: 200,
                sampling_ratio: 0.1
            },
            'very-aggressive': {
                order_book_level: 2,
                trade_history_limit: 1000,
                bid_ask_spread_threshold: 1.0,
                volume_imbalance_threshold: 0.2,
                large_trade_threshold: 1000,
                data_analysis_mode: 'all',
                recent_data_limit: 500,
                sampling_ratio: 0.1
            }
        };
        
        this.init();
        
        // Reset inputs to defaults on page load
        this.resetBacktestingInputs();
        this.resetLiveTradingInputs();
        
        // Session management
        this.sessionId = this.getOrCreateSessionId();
        this.autoSaveInterval = null;
        
        // Trading stats
        this.tradingStats = {
            totalPnl: 0,
            winRate: 0,
            totalTrades: 0,
            activePositions: 0,
            maxDrawdown: 0,
            sharpeRatio: 0,
            bestTrade: 0,
            worstTrade: 0,
            avgWin: 0,
            avgLoss: 0,
            tradesToday: 0,
            totalVolume: 0,
            sessionStartTime: null,
            sessionTrades: 0,
            sessionPnl: 0,
            lastTradeTime: null
        };
        this.statsUpdateInterval = null;
        
        // Strategy configuration visibility state
        this.strategyConfigHidden = false;
        
        // Trading history pagination state
        this.tradingHistoryPagination = {
            currentPage: 1,
            perPage: 10,
            totalPages: 1,
            totalTrades: 0
        };
        
        // Order book signals pagination state
        this.orderBookSignalsPagination = {
            currentPage: 1,
            perPage: 10,
            totalPages: 1,
            totalSignals: 0
        };
        
        // Open positions pagination state
        this.positionsPagination = {
            currentPage: 1,
            perPage: 10,
            totalPages: 1,
            totalPositions: 0
        };
    }

    getOrCreateSessionId() {
        // Try to get existing session ID from localStorage
        let sessionId = localStorage.getItem('trading_session_id');
        if (!sessionId) {
            // Create new session ID
            sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('trading_session_id', sessionId);
        }
        return sessionId;
    }

    async checkAndRestoreSession() {
        try {
            // Check if there's an active session
            const response = await fetch('/api/session/active');
            const data = await response.json();
            
            if (data.sessions && data.sessions.length > 0) {
                // Find our session or use the most recent one
                let sessionToRestore = data.sessions.find(s => s.session_id === this.sessionId);
                if (!sessionToRestore) {
                    sessionToRestore = data.sessions[0]; // Use most recent
                    this.sessionId = sessionToRestore.session_id;
                    localStorage.setItem('trading_session_id', this.sessionId);
                }
                
                // Load session data
                await this.loadSessionData(this.sessionId);
            }
        } catch (error) {
            console.error('Error checking for existing session:', error);
        }
    }

    async loadSessionData(sessionId) {
        try {
            const response = await fetch(`/api/session/load/${sessionId}`);
            const data = await response.json();
            
            if (data.session_data) {
                await this.restoreTradingState(data.session_data);
                this.logTradingEvent(`Restored session: ${sessionId}`);
            }
        } catch (error) {
            console.error('Error loading session data:', error);
        }
    }

    async saveSessionState() {
        try {
            const sessionData = {
                is_active: this.liveTrading.isActive,
                trading_mode: this.liveTrading.mode,
                symbol_mode: this.liveTrading.symbolMode,
                strategy_type: this.liveTrading.strategy?.type,
                strategy_params: this.liveTrading.strategy?.params || {},
                symbols: this.liveTrading.strategy?.symbols || [],
                universe_config: this.liveTrading.universe,
                portfolio_state: this.liveTrading.portfolio,
                positions: this.liveTrading.positions,
                recent_trades: this.liveTrading.history
            };

            const response = await fetch('/api/session/save', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    session_data: sessionData
                })
            });

            const result = await response.json();
            if (result.status === 'saved') {
                console.log('Session state saved successfully');
            }
        } catch (error) {
            console.error('Error saving session state:', error);
        }
    }

    async saveDashboardState() {
        try {
            const stateData = {
                current_symbol: this.currentSymbol,
                current_timeframe: this.currentCandlePeriod,
                chart_settings: {
                    yAxisRange: this.currentYAxisRange,
                    layout: this.currentLayout
                },
                ui_preferences: {
                    percentageTimeframe: this.percentageTimeframe,
                    subscriptions: this.subscriptions
                }
            };

            const response = await fetch('/api/session/save-dashboard', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    state_data: stateData
                })
            });

            const result = await response.json();
            if (result.status === 'saved') {
                console.log('Dashboard state saved successfully');
            }
        } catch (error) {
            console.error('Error saving dashboard state:', error);
        }
    }

    async restoreTradingState(sessionData) {
        if (!sessionData) return;

        // Restore trading state
        this.liveTrading.isActive = sessionData.is_active || false;
        this.liveTrading.mode = sessionData.trading_mode || 'simulated';
        this.liveTrading.symbolMode = sessionData.symbol_mode || 'single';
        this.liveTrading.strategy = sessionData.strategy_type ? {
            type: sessionData.strategy_type,
            params: sessionData.strategy_params || {},
            symbols: sessionData.symbols || []
        } : null;
        this.liveTrading.universe = sessionData.universe_config || this.liveTrading.universe;
        this.liveTrading.portfolio = sessionData.portfolio_state || this.liveTrading.portfolio;
        this.liveTrading.positions = sessionData.positions || [];
        this.liveTrading.history = sessionData.recent_trades || [];

        // Update UI
        this.updateTradingControls();
        this.updateTradingStatus(this.liveTrading.isActive ? 'active' : 'stopped');
        
        // Update positions and history tables
        this.updateOpenPositions(this.liveTrading.positions);
        this.updateRecentTrades(this.liveTrading.history);

        // If trading is active, restore the backend state
        if (this.liveTrading.isActive) {
            try {
                const response = await fetch('/api/data/restore-trading', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        session_id: this.sessionId
                    })
                });

                const data = await response.json();
                if (data.status === 'restored') {
                    // Update with restored data
                    this.liveTrading.portfolio = data.portfolio;
                    this.liveTrading.positions = data.positions;
                    this.liveTrading.history = data.recent_trades;
                    
                    // Update UI with restored data
                    this.updateOpenPositions(this.liveTrading.positions);
                    this.updateRecentTrades(this.liveTrading.history);
                    
                    this.logTradingEvent(`Restored trading session with ${data.positions.length} positions and $${data.portfolio.cash_balance?.toFixed(2) || '0.00'} balance`);
                } else {
                    this.logTradingEvent(`Failed to restore trading session: ${data.error}`);
                }
            } catch (error) {
                this.logTradingEvent(`Error restoring trading session: ${error.message}`);
            }
            
            this.startPortfolioStatusUpdates();
            // Only load order book signals if trading is actually active (not just restored)
            if (this.liveTrading.isActive) {
                this.loadOrderBookSignals();
                this.startOrderBookAutoRefresh();
            }
        }
    }

    // Trading Stats Methods
    
    async loadTradingStats() {
        try {
            // Load stats from API
            const response = await fetch('/api/trades/stats');
            const data = await response.json();
            
            if (data.status === 'success') {
                this.updateTradingStats(data.stats);
            }
            
            // Also load session-specific stats if we have a session
            if (this.sessionId) {
                const sessionResponse = await fetch(`/api/trades/session/${this.sessionId}`);
                const sessionData = await sessionResponse.json();
                
                if (sessionData.status === 'success') {
                    this.updateSessionStats(sessionData.trades);
                }
            }
            
        } catch (error) {
            console.error('Error loading trading stats:', error);
        }
    }
    
    updateTradingStats(stats) {
        if (!stats) return;
        
        // Update main stats
        this.tradingStats.totalPnl = stats.total_pnl || 0;
        this.tradingStats.winRate = stats.win_rate || 0;
        this.tradingStats.totalTrades = stats.total_trades || 0;
        this.tradingStats.maxDrawdown = stats.max_drawdown || 0;
        this.tradingStats.sharpeRatio = stats.sharpe_ratio || 0;
        this.tradingStats.bestTrade = stats.best_trade || 0;
        this.tradingStats.worstTrade = stats.worst_trade || 0;
        this.tradingStats.avgWin = stats.avg_win || 0;
        this.tradingStats.avgLoss = stats.avg_loss || 0;
        this.tradingStats.tradesToday = stats.trades_today || 0;
        this.tradingStats.totalVolume = stats.total_volume || 0;
        
        // Update UI
        this.updateTradingStatsUI();
    }
    
    updateSessionStats(trades) {
        if (!trades) return;
        
        // Calculate session stats
        const today = new Date().toDateString();
        const sessionTrades = trades.filter(trade => {
            const tradeDate = new Date(trade.timestamp).toDateString();
            return tradeDate === today;
        });
        
        this.tradingStats.sessionTrades = sessionTrades.length;
        this.tradingStats.sessionPnl = sessionTrades.reduce((sum, trade) => sum + (trade.pnl || 0), 0);
        
        if (trades.length > 0) {
            this.tradingStats.lastTradeTime = new Date(trades[0].timestamp).toLocaleTimeString();
        }
        
        // Update UI
        this.updateTradingStatsUI();
    }
    
    updateTradingStatsUI() {
        // Performance Metrics
        this.updateElement('total-pnl', `$${this.tradingStats.totalPnl.toFixed(2)}`);
        this.updateElement('win-rate', `${this.tradingStats.winRate.toFixed(2)}%`);
        this.updateElement('total-trades', this.tradingStats.totalTrades.toString());
        this.updateElement('active-positions', this.liveTrading.positions.length.toString());
        
        // Risk Metrics
        this.updateElement('max-drawdown', `${this.tradingStats.maxDrawdown.toFixed(2)}%`);
        this.updateElement('sharpe-ratio', this.tradingStats.sharpeRatio.toFixed(2));
        this.updateElement('risk-adjusted-return', `${(this.tradingStats.sharpeRatio * 10).toFixed(2)}%`);
        
        // Trading Activity
        this.updateElement('trades-today-count', this.tradingStats.tradesToday.toString());
        this.updateElement('avg-trade-size', `$${(this.tradingStats.totalVolume / Math.max(this.tradingStats.totalTrades, 1)).toFixed(2)}`);
        this.updateElement('total-volume', `$${this.tradingStats.totalVolume.toFixed(2)}`);
        
        // Performance Trends
        this.updateElement('best-trade', `$${this.tradingStats.bestTrade.toFixed(2)}`);
        this.updateElement('worst-trade', `$${this.tradingStats.worstTrade.toFixed(2)}`);
        this.updateElement('avg-win', `$${this.tradingStats.avgWin.toFixed(2)}`);
        this.updateElement('avg-loss', `$${this.tradingStats.avgLoss.toFixed(2)}`);
        
        // Session Info
        this.updateElement('session-trades', this.tradingStats.sessionTrades.toString());
        this.updateElement('session-pnl', `$${this.tradingStats.sessionPnl.toFixed(2)}`);
        this.updateElement('last-trade-time', this.tradingStats.lastTradeTime || 'Never');
        
        // Update position value
        const positionValue = this.liveTrading.positions.reduce((sum, pos) => {
            return sum + (pos.quantity * pos.currentPrice);
        }, 0);
        this.updateElement('position-value', `$${positionValue.toFixed(2)} value`);
        
        // Update trades today
        this.updateElement('trades-today', `${this.tradingStats.tradesToday} today`);
        
        // Update PnL change (simplified)
        const pnlChange = this.tradingStats.totalPnl > 0 ? '+' : '';
        this.updateElement('pnl-change', `${pnlChange}${this.tradingStats.totalPnl.toFixed(2)}%`);
        
        // Update win rate change (simplified)
        const winRateChange = this.tradingStats.winRate > 50 ? '+' : '';
        this.updateElement('win-rate-change', `${winRateChange}${(this.tradingStats.winRate - 50).toFixed(2)}%`);
    }
    
    updateElement(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
    }
    
    startTradingStatsUpdates() {
        // Clear existing interval
        if (this.statsUpdateInterval) {
            clearInterval(this.statsUpdateInterval);
        }
        
        // Update stats every 30 seconds
        this.statsUpdateInterval = setInterval(async () => {
            await this.loadTradingStats();
        }, 30000);
        
        // Update session duration every second
        this.sessionDurationInterval = setInterval(() => {
            this.updateSessionDuration();
        }, 1000);
    }
    
    stopTradingStatsUpdates() {
        if (this.statsUpdateInterval) {
            clearInterval(this.statsUpdateInterval);
            this.statsUpdateInterval = null;
        }
        if (this.sessionDurationInterval) {
            clearInterval(this.sessionDurationInterval);
            this.sessionDurationInterval = null;
        }
    }
    
    updateSessionDuration() {
        if (this.tradingStats.sessionStartTime) {
            const now = new Date();
            const duration = now - this.tradingStats.sessionStartTime;
            const hours = Math.floor(duration / 3600000);
            const minutes = Math.floor((duration % 3600000) / 60000);
            const seconds = Math.floor((duration % 60000) / 1000);
            
            const durationStr = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
            this.updateElement('session-duration', durationStr);
        }
    }
    
    // Strategy Configuration Hide/Show Methods
    
    hideStrategyConfiguration() {
        const strategySection = document.getElementById('strategy-configuration-section');
        const showStrategySection = document.getElementById('show-strategy-section');
        
        if (strategySection && showStrategySection) {
            strategySection.style.display = 'none';
            showStrategySection.classList.remove('hidden');
            this.strategyConfigHidden = true;
            this.saveStrategyConfigState();
            
            // Log the action
            this.logTradingEvent('Strategy configuration hidden');
        }
    }
    
    showStrategyConfiguration() {
        const strategySection = document.getElementById('strategy-configuration-section');
        const showStrategySection = document.getElementById('show-strategy-section');
        
        if (strategySection && showStrategySection) {
            strategySection.style.display = 'block';
            showStrategySection.classList.add('hidden');
            this.strategyConfigHidden = false;
            this.saveStrategyConfigState();
            
            // Log the action
            this.logTradingEvent('Strategy configuration shown');
        }
    }
    
    autoHideStrategyOnTradingStart() {
        // Automatically hide strategy configuration when trading starts
        // This provides a cleaner interface during active trading
        if (this.liveTrading.isActive) {
            this.hideStrategyConfiguration();
        }
    }
    
    restoreStrategyConfigState() {
        // Restore strategy configuration visibility state from localStorage
        const savedState = localStorage.getItem('strategy_config_hidden');
        if (savedState === 'true') {
            this.hideStrategyConfiguration();
        }
    }
    
    saveStrategyConfigState() {
        // Save strategy configuration visibility state to localStorage
        localStorage.setItem('strategy_config_hidden', this.strategyConfigHidden.toString());
    }

    startAutoSave() {
        // Save session state every 30 seconds
        this.autoSaveInterval = setInterval(() => {
            this.saveSessionState();
            this.saveDashboardState();
        }, 30000);
    }

    stopAutoSave() {
        if (this.autoSaveInterval) {
            clearInterval(this.autoSaveInterval);
            this.autoSaveInterval = null;
        }
    }

    init() {
        this.connectWebSocket();
        this.setupEventListeners();
        this.loadSubscriptions();
        this.setupLiveTrading();
        
        // Setup trading history pagination
        this.setupTradingHistoryPagination();
        
        // Setup order book signals pagination
        this.setupOrderBookSignalsPagination();
        
        // Setup positions pagination
        this.setupPositionsPagination();
        
        // Load data after a short delay to ensure DOM is ready
        setTimeout(() => {
            this.loadAvailableProducts();
            this.loadInitialData();
            this.startDataRefresh();
            this.loadRealtimeStatus();
            
            // Load trading stats
            this.loadTradingStats();
            
            // Load initial paginated trading history
            this.loadPaginatedTradingHistory();
            
            // Check for existing session and restore state
            this.checkAndRestoreSession();
            
            // Restore strategy configuration visibility state
            this.restoreStrategyConfigState();
        }, 100);
    }

    async loadAvailableProducts() {
        try {
            const response = await fetch('/api/products');
            const data = await response.json();
            
            if (data.status === 'success') {
                this.populateProductSelectors(data.categories);
                console.log('Loaded products:', data.total_products, 'total');
            } else {
                console.error('Failed to load products:', data.error);
            }
        } catch (error) {
            console.error('Error loading products:', error);
        }
    }

    populateProductSelectors(categories) {
        // Handle both direct selector objects and selector IDs
        let selectors = [];
        
        if (typeof categories === 'object' && !categories.major) {
            // Called with specific selector objects
            selectors = Object.entries(categories).map(([id, element]) => ({ id, element }));
        } else {
            // Called with categories data - get all selectors that need product options
            const selectorIds = [
                'symbol-selector',
                'backtest-symbol',
                'live-trading-symbol'
            ];
            
            selectors = selectorIds.map(id => {
                const element = document.getElementById(id);
                return { id, element };
            }).filter(item => item.element);
        }
        
        // Create options for each category
        const categoryOptions = {
            'Major Pairs': categories.major || [],
            'DEX Tokens': categories.dex_tokens || [],
            'Meme Tokens': categories.meme_tokens || [],
            'Stablecoins': categories.stablecoins || [],
            'All USD Pairs': categories.all_usd || []
        };
        
        selectors.forEach(({ id, element }) => {
            if (!element) return;
            
            // Clear existing options
            element.innerHTML = '';
            
            // Add category headers and options
            Object.entries(categoryOptions).forEach(([categoryName, products]) => {
                if (products.length === 0) return;
                
                // Add category header
                const optgroup = document.createElement('optgroup');
                optgroup.label = categoryName;
                
                // Add products to this category
                products.forEach(product => {
                    const option = document.createElement('option');
                    option.value = product;
                    option.textContent = product;
                    optgroup.appendChild(option);
                });
                
                element.appendChild(optgroup);
            });
            
            // Set default selection
            if (['symbol-selector', 'backtest-symbol', 'live-trading-symbol'].includes(id)) {
                element.value = 'BTC-USD';
            }
        });
        
        // Update product ID inputs
        const productInputs = document.querySelectorAll('input[value="BTC-USD"]');
        productInputs.forEach(input => {
            if (input.id !== 'product-id') {
                input.value = 'BTC-USD';
            }
        });
    }

    setupLiveTrading() {
        // Live trading state
        this.liveTrading = {
            isActive: false,
            isPaused: false,
            mode: 'simulated', // 'simulated' or 'live'
            symbolMode: 'single', // 'single' or 'universe'
            strategy: null,
            positions: [],
            history: [],
            universe: {
                type: 'all_usd',
                symbols: [],
                customSymbols: [],
                maxSize: 50,
                positionSize: 1.0,
                maxPositions: 50
            },
            portfolio: {
                balance: 10000,
                totalValue: 10000,
                openPositions: 0,
                dailyPnL: 0
            }
        };
        
        // Setup live trading event listeners
        this.setupLiveTradingEventListeners();
    }

    setupLiveTradingEventListeners() {
        // Tab switching
        document.getElementById('tab-live-trading')?.addEventListener('click', async () => {
            this.switchTab('live-trading');
            this.resetLiveTradingInputs();
            await this.loadLiveTradingProducts();
            // loadLiveTradingData() will be called by switchTab()
        });

        // Trading mode selection
        document.querySelectorAll('input[name="trading-mode"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                this.liveTrading.mode = e.target.value;
                this.updateTradingModeUI();
            });
        });

        // Symbol trading mode selection
        document.querySelectorAll('input[name="trading-symbol-mode"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                this.liveTrading.symbolMode = e.target.value;
                this.updateSymbolModeUI();
                // Only refresh order book signals if trading is active
                if (this.liveTrading.isActive) {
                    this.loadOrderBookSignals();
                }
            });
        });

        // Universe type selection
        document.getElementById('universe-type')?.addEventListener('change', (e) => {
            this.updateUniverseSelection(e.target.value);
            // Only refresh order book signals if trading is active
            if (this.liveTrading.isActive) {
                this.loadOrderBookSignals();
            }
        });

        // Single symbol selection
        document.getElementById('live-trading-symbol')?.addEventListener('change', () => {
            // Only refresh order book signals if trading is active
            if (this.liveTrading.isActive) {
                this.loadOrderBookSignals();
            }
        });

        // Custom symbol management
        document.getElementById('add-custom-symbol')?.addEventListener('click', () => {
            this.addCustomSymbol();
            // Only refresh order book signals if trading is active
            if (this.liveTrading.isActive) {
                this.loadOrderBookSignals();
            }
        });

        document.getElementById('custom-symbol-input')?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.addCustomSymbol();
                // Only refresh order book signals if trading is active
                if (this.liveTrading.isActive) {
                    this.loadOrderBookSignals();
                }
            }
        });

        // Strategy type change
        document.getElementById('live-strategy-type')?.addEventListener('change', (e) => {
            this.loadStrategyParameters(e.target.value);
        });

        // Universe strategy type change
        document.getElementById('universe-strategy-type')?.addEventListener('change', (e) => {
            this.loadStrategyParameters(e.target.value);
        });
        
        // Order Book preset selection handler
        document.getElementById('orderbook-preset')?.addEventListener('change', (e) => {
            this.applyOrderBookPreset(e.target.value);
        });

        // Trading controls
        document.getElementById('start-trading')?.addEventListener('click', () => {
            this.startLiveTrading();
        });

        document.getElementById('stop-trading')?.addEventListener('click', () => {
            this.stopLiveTrading();
        });

        document.getElementById('pause-trading')?.addEventListener('click', () => {
            this.pauseLiveTrading();
        });

        document.getElementById('emergency-stop')?.addEventListener('click', () => {
            this.emergencyStop();
        });
        
        // Order book signals refresh button
        document.getElementById('refresh-orderbook-signals')?.addEventListener('click', async () => {
            if (this.liveTrading.isActive) {
                await this.loadOrderBookSignals();
            } else {
                this.logTradingEvent("Please start trading first to refresh order book signals.");
            }
        });
        
        // Trading stats refresh button
        document.getElementById('refresh-trading-stats')?.addEventListener('click', async () => {
            await this.loadTradingStats();
        });
        
        // Strategy configuration hide/show buttons
        document.getElementById('hide-strategy-btn')?.addEventListener('click', () => {
            this.hideStrategyConfiguration();
        });
        
        document.getElementById('show-strategy-btn')?.addEventListener('click', () => {
            this.showStrategyConfiguration();
        });
        
        // Auto-refresh order book signals every 30 seconds when on live trading tab
        this.orderBookRefreshInterval = null;
        this.portfolioUpdateInterval = null;
    }

    async loadLiveTradingProducts() {
        // Load products for live trading symbol selector
        const symbolSelector = document.getElementById('live-trading-symbol');
        if (symbolSelector && symbolSelector.children.length <= 1) {
            try {
                // Fetch products from API
                const response = await fetch('/api/products');
                const data = await response.json();
                
                if (data.status === 'success') {
                    // Use the same product loading logic as other selectors
                    this.populateProductSelectors(data.categories);
                    console.log('Loaded products for live trading:', data.total_products, 'total');
                } else {
                    console.error('Failed to load products for live trading:', data.error);
                }
            } catch (error) {
                console.error('Error loading products for live trading:', error);
            }
        }
    }

    getSelectedSymbols() {
        // Get the current trading symbol mode
        const symbolMode = document.querySelector('input[name="trading-symbol-mode"]:checked')?.value;
        
        if (symbolMode === 'universe') {
            // Get universe symbols
            const universeType = document.getElementById('universe-type')?.value;
            
            if (universeType === 'custom') {
                // Get custom symbols from the universe widget
                return this.liveTrading.universe.customSymbols || [];
            } else {
                // Get predefined universe symbols
                return this.liveTrading.universe.symbols || [];
            }
        } else {
            // Single symbol mode
            const symbol = document.getElementById('live-trading-symbol')?.value;
            return symbol ? [symbol] : [];
        }
    }

    async loadOrderBookSignals(page = 1, perPage = 10) {
        try {
            // Check if trading is active
            if (!this.liveTrading.isActive) {
                this.updateOrderBookSignalsTable([]);
                this.updateOrderBookStatistics({
                    total_analyzed: 0,
                    active_signals: 0,
                    last_updated: new Date().toISOString(),
                    average_strength: 0,
                    message: "Trading is not active. Start trading to see live signals."
                });
                return;
            }

            // Get symbols from current trading strategy (for async trading) or form (for regular trading)
            const selectedSymbols = this.liveTrading.strategy?.symbols || this.getSelectedSymbols();
            
            // If no symbols are selected, show appropriate message
            if (!selectedSymbols || selectedSymbols.length === 0) {
                this.updateOrderBookSignalsTable([]);
                this.updateOrderBookStatistics({
                    total_analyzed: 0,
                    active_signals: 0,
                    last_updated: new Date().toISOString(),
                    average_strength: 0,
                    message: "No symbols selected for trading. Please select symbols to see live signals."
                });
                return;
            }
            
            // Build API URL with symbols and pagination parameters
            let apiUrl = '/api/orderbook/live-signals';
            const symbolsParam = selectedSymbols.join(',');
            apiUrl += `?symbols=${encodeURIComponent(symbolsParam)}&page=${page}&per_page=${perPage}`;
            
            const response = await fetch(apiUrl);
            const data = await response.json();
            
            if (data.error) {
                console.error('Error loading order book signals:', data.error);
                this.updateOrderBookSignalsTable([]);
                return;
            }
            
            // Check if trading is not active from server response
            if (data.trading_active === false) {
                this.updateOrderBookSignalsTable([]);
                this.updateOrderBookStatistics({
                    total_analyzed: 0,
                    active_signals: 0,
                    last_updated: new Date().toISOString(),
                    average_strength: 0,
                    message: data.message || "Trading is not active."
                });
                return;
            }
            
            // Update pagination info
            if (data.pagination) {
                this.orderBookSignalsPagination = {
                    currentPage: data.pagination.current_page,
                    perPage: data.pagination.per_page,
                    totalSignals: data.pagination.total_signals,
                    totalPages: data.pagination.total_pages,
                    hasNext: data.pagination.has_next,
                    hasPrev: data.pagination.has_prev
                };
            }
            
            this.updateOrderBookSignalsTable(data.signals);
            this.updateOrderBookStatistics(data);
            this.updateOrderBookPaginationControls();
            
            // Process signals for trading if trading is active
            if (this.liveTrading.isActive && data.signals && data.signals.length > 0) {
                const activeSignals = data.signals.filter(s => s.signal_generated === true);
                console.log(`Found ${activeSignals.length} active signals out of ${data.signals.length} total signals`);
                console.log('Active signals:', activeSignals);
                
                if (activeSignals.length > 0) {
                    this.logTradingEvent(`Processing ${activeSignals.length} active signals from live order book analysis`);
                    activeSignals.forEach(signal => {
                        this.logTradingEvent(`Signal: ${signal.signal.toUpperCase()} ${signal.symbol} @ $${signal.price} (${signal.signal_type})`);
                    });
                    
                    // Process signals through simulated trading
                    console.log('Calling signal processing endpoint...');
                    try {
                        const processResponse = await fetch('/api/trading/simulated/process-signals', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                signals: activeSignals
                            })
                        });
                        
                        const processData = await processResponse.json();
                        console.log('Signal processing response:', processData);
                        
                        if (processData.status === 'processed') {
                            const executedTrades = processData.executed_trades || 0;
                            if (executedTrades > 0) {
                                this.logTradingEvent(`Executed ${executedTrades} trades based on order book signals`);
                                console.log(`Executed ${executedTrades} trades`);
                            } else {
                                console.log('No trades executed');
                            }
                        } else {
                            console.log('Signal processing failed:', processData);
                        }
                    } catch (error) {
                        console.error('Error processing signals:', error);
                        this.logTradingEvent(`Error processing signals: ${error.message}`);
                    }
                }
            }
            
            // Update portfolio status when new signals are processed
            if (this.liveTrading.isActive) {
                await this.updateTradingStatusFromAPI();
            }

        } catch (error) {
            console.error('Error loading order book signals:', error);
            this.updateOrderBookSignalsTable([]);
        }
    }

    updateOrderBookSignalsTable(signals) {
        const tableBody = document.getElementById('orderbook-signals-table');
        if (!tableBody) return;
        
        if (signals.length === 0) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="11" class="px-6 py-4 text-center text-gray-500">
                        <i class="fas fa-exclamation-triangle mr-2"></i>No order book signals available
                    </td>
                </tr>
            `;
            return;
        }
        
        tableBody.innerHTML = signals.map(signal => {
            // Determine signal class based on signal and data status
            let signalClass = 'text-gray-600 bg-gray-50';
            if (signal.data_status === 'sufficient') {
                signalClass = signal.signal === 'buy' ? 'text-green-600 bg-green-50' : 
                             signal.signal === 'sell' ? 'text-red-600 bg-red-50' : 
                             'text-gray-600 bg-gray-50';
            } else if (signal.data_status === 'insufficient') {
                signalClass = 'text-yellow-600 bg-yellow-50';
            } else {
                signalClass = 'text-gray-400 bg-gray-100';
            }
            
            const strengthColor = signal.signal_strength >= 0.7 ? 'text-green-600' : 
                                 signal.signal_strength >= 0.4 ? 'text-yellow-600' : 
                                 'text-red-600';
            
            // Get criteria analysis
            const criteria = signal.criteria_analysis || {};
            const squeeze = criteria.bid_ask_squeeze || {};
            const imbalanceBuy = criteria.volume_imbalance_buy || {};
            const imbalanceSell = criteria.volume_imbalance_sell || {};
            const largeTradeBuy = criteria.large_trade_buy || {};
            const largeTradeSell = criteria.large_trade_sell || {};
            
            // Helper function to get status color
            const getStatusColor = (meets, enabled) => {
                if (!enabled) return 'text-gray-400';
                return meets ? 'text-green-600' : 'text-red-600';
            };
            
            // Helper function to get delta color
            const getDeltaColor = (delta) => {
                if (delta >= 0.8) return 'text-green-600';
                if (delta >= 0.5) return 'text-yellow-600';
                if (delta >= 0.2) return 'text-orange-600';
                return 'text-red-600';
            };
            
            // Get data status indicator
            const getDataStatusIcon = (status) => {
                switch (status) {
                    case 'sufficient': return '✓';
                    case 'insufficient': return '⚠';
                    case 'none': return '✗';
                    default: return '?';
                }
            };
            
            const getDataStatusColor = (status) => {
                switch (status) {
                    case 'sufficient': return 'text-green-600';
                    case 'insufficient': return 'text-yellow-600';
                    case 'none': return 'text-red-600';
                    default: return 'text-gray-400';
                }
            };
            
            return `
                <tr class="hover:bg-gray-50">
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        ${signal.timestamp ? new Date(signal.timestamp).toLocaleString() : 'N/A'}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <div class="flex items-center space-x-2">
                            <div class="text-sm font-medium text-gray-900">${signal.symbol}</div>
                            <span class="text-xs ${getDataStatusColor(signal.data_status)}" title="Data Status: ${signal.data_status}">
                                ${getDataStatusIcon(signal.data_status)}
                            </span>
                        </div>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <div class="text-sm text-gray-900">$${signal.price.toFixed(2)}</div>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <span class="inline-flex px-2 py-1 text-xs font-semibold rounded-full ${signalClass}">
                            ${signal.data_status === 'sufficient' ? signal.signal.toUpperCase() : 
                              signal.data_status === 'insufficient' ? 'WAITING' : 'NO DATA'}
                        </span>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <div class="flex items-center">
                            <div class="w-16 bg-gray-200 rounded-full h-2 mr-2">
                                <div class="bg-blue-600 h-2 rounded-full" style="width: ${signal.signal_strength * 100}%"></div>
                            </div>
                            <span class="text-sm font-medium ${strengthColor}">${signal.signal_strength.toFixed(2)}</span>
                        </div>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <div class="text-xs">
                            <div class="flex items-center space-x-1">
                                <span class="${getStatusColor(squeeze.meets_criteria, squeeze.enabled)}">
                                    ${squeeze.enabled ? (squeeze.meets_criteria ? '✓' : '✗') : '○'}
                                </span>
                                <span class="text-gray-600">${squeeze.enabled ? squeeze.delta_to_threshold.toFixed(2) : 'N/A'}</span>
                            </div>
                            <div class="text-gray-500 text-xs mt-1">
                                ${squeeze.enabled ? `T: ${squeeze.threshold_spread.toFixed(4)}` : 'No data'}
                            </div>
                        </div>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <div class="text-xs">
                            <div class="flex items-center space-x-1">
                                <span class="${getStatusColor(imbalanceBuy.meets_criteria, imbalanceBuy.enabled)}">
                                    ${imbalanceBuy.enabled ? (imbalanceBuy.meets_criteria ? '✓' : '✗') : '○'}
                                </span>
                                <span class="text-gray-600">${imbalanceBuy.enabled ? imbalanceBuy.delta_to_threshold.toFixed(2) : 'N/A'}</span>
                            </div>
                            <div class="text-gray-500 text-xs mt-1">
                                ${imbalanceBuy.enabled ? `T: ${imbalanceBuy.threshold.toFixed(2)}` : 'No data'}
                            </div>
                        </div>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <div class="text-xs">
                            <div class="flex items-center space-x-1">
                                <span class="${getStatusColor(largeTradeBuy.meets_criteria, largeTradeBuy.enabled)}">
                                    ${largeTradeBuy.enabled ? (largeTradeBuy.meets_criteria ? '✓' : '✗') : '○'}
                                </span>
                                <span class="text-gray-600">${largeTradeBuy.enabled ? largeTradeBuy.delta_to_threshold.toFixed(2) : 'N/A'}</span>
                            </div>
                            <div class="text-gray-500 text-xs mt-1">
                                ${largeTradeBuy.enabled ? `Trades: ${largeTradeBuy.large_trades_count}` : 'No data'}
                            </div>
                        </div>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <div class="text-sm text-gray-900">${signal.spread.toFixed(4)}%</div>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <div class="text-sm text-gray-900">${signal.volume.toFixed(2)}</div>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <button onclick="this.nextElementSibling.classList.toggle('hidden')" 
                                class="text-blue-600 hover:text-blue-800 text-xs font-medium">
                            <i class="fas fa-info-circle mr-1"></i>Details
                        </button>
                        <div class="hidden absolute z-10 bg-white border border-gray-200 rounded-lg shadow-lg p-4 mt-1 max-w-md">
                            <div class="text-xs space-y-2">
                                <div><strong>Signal Type:</strong> ${signal.signal_type || 'None'}</div>
                                <div><strong>Reason:</strong> ${signal.signal_reason}</div>
                                <div class="border-t pt-2">
                                    <div><strong>Squeeze:</strong> ${squeeze.analysis || 'N/A'}</div>
                                    <div><strong>Imbalance Buy:</strong> ${imbalanceBuy.analysis || 'N/A'}</div>
                                    <div><strong>Imbalance Sell:</strong> ${imbalanceSell.analysis || 'N/A'}</div>
                                    <div><strong>Large Trade Buy:</strong> ${largeTradeBuy.analysis || 'N/A'}</div>
                                    <div><strong>Large Trade Sell:</strong> ${largeTradeSell.analysis || 'N/A'}</div>
                                </div>
                            </div>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    }

    updateOrderBookStatistics(data) {
        const totalAnalyzed = document.getElementById('total-analyzed');
        const activeSignals = document.getElementById('active-signals');
        const lastUpdated = document.getElementById('last-updated');
        const avgStrength = document.getElementById('avg-strength');
        
        // Show message if trading is not active
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
        
        if (totalAnalyzed) {
            totalAnalyzed.textContent = data.total_analyzed || 0;
        }
        
        if (activeSignals) {
            const activeCount = data.signals ? data.signals.filter(s => s.signal_generated === true).length : 0;
            activeSignals.textContent = activeCount;
        }
        
        if (lastUpdated) {
            const now = new Date();
            lastUpdated.textContent = now.toLocaleTimeString();
        }
        
        if (avgStrength && data.signals && data.signals.length > 0) {
            const avg = data.signals.reduce((sum, s) => sum + s.signal_strength, 0) / data.signals.length;
            avgStrength.textContent = avg.toFixed(2);
        } else if (avgStrength) {
            avgStrength.textContent = '0.00';
        }
    }

    startOrderBookAutoRefresh() {
        // Clear existing interval
        if (this.orderBookRefreshInterval) {
            clearInterval(this.orderBookRefreshInterval);
        }
        
        // Start new interval - refresh every 30 seconds
        this.orderBookRefreshInterval = setInterval(async () => {
            await this.loadOrderBookSignals(this.orderBookSignalsPagination.currentPage, this.orderBookSignalsPagination.perPage);
        }, 30000);
    }

    startOrderBookFrequentRefresh() {
        // Clear existing interval
        if (this.orderBookRefreshInterval) {
            clearInterval(this.orderBookRefreshInterval);
        }
        
        // Start more frequent refresh during async loading - every 5 seconds
        this.orderBookRefreshInterval = setInterval(async () => {
            await this.loadOrderBookSignals(this.orderBookSignalsPagination.currentPage, this.orderBookSignalsPagination.perPage);
        }, 5000);
    }

    stopOrderBookAutoRefresh() {
        if (this.orderBookRefreshInterval) {
            clearInterval(this.orderBookRefreshInterval);
            this.orderBookRefreshInterval = null;
        }
    }

    loadStrategyParameters(strategyType) {
        const paramsContainer = document.getElementById('live-strategy-params');
        if (!paramsContainer) return;

        // Clear existing parameters
        paramsContainer.innerHTML = '';

        const strategyParams = this.getStrategyParameters(strategyType);
        
        if (strategyParams.length === 0) {
            paramsContainer.innerHTML = '<p class="text-gray-500 text-sm">No additional parameters required for this strategy.</p>';
            return;
        }

        // Special handling for Order Book strategy to include preset dropdown
        let presetHTML = '';
        if (strategyType === 'orderbook') {
            presetHTML = `
                <div class="mb-4 p-4 bg-gray-50 rounded-lg">
                    <label class="block text-sm font-medium text-gray-700 mb-2">Configuration Preset</label>
                    <select id="live-orderbook-preset" class="w-full border border-gray-300 rounded-md px-3 py-2 mb-3">
                        <option value="custom">Custom Configuration</option>
                        <option value="conservative">Conservative (Few High-Quality Signals)</option>
                        <option value="moderate">Moderate (Balanced Signals)</option>
                        <option value="aggressive" selected>Aggressive (More Signals) - Recommended</option>
                        <option value="very-aggressive">Very Aggressive (Maximum Signals)</option>
                    </select>
                    <p class="text-xs text-gray-500">Select a preset to automatically configure parameters for different signal frequencies</p>
                </div>
            `;
        }

        // Create parameter inputs
        const paramsHTML = strategyParams.map(param => {
            if (param.type === 'select') {
                const options = param.options.map(opt => `<option value="${opt}">${opt.charAt(0).toUpperCase() + opt.slice(1)}</option>`).join('');
                return `
                    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">${param.label}</label>
                            <select id="live-param-${param.name}" class="w-full border border-gray-300 rounded-md px-3 py-2">
                                ${options}
                            </select>
                        </div>
                    </div>
                `;
            } else {
                return `
                    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">${param.label}</label>
                            <input type="${param.type}" 
                                   id="live-param-${param.name}" 
                                   value="${param.default}" 
                                   min="${param.min || ''}" 
                                   max="${param.max || ''}" 
                                   step="${param.step || ''}"
                                   class="w-full border border-gray-300 rounded-md px-3 py-2">
                        </div>
                    </div>
                `;
            }
        }).join('');

        paramsContainer.innerHTML = `
            <h4 class="text-md font-semibold text-gray-700 mb-4">Strategy Parameters</h4>
            ${presetHTML}
            ${paramsHTML}
        `;

        // Add event listener for Order Book preset selection
        if (strategyType === 'orderbook') {
            const presetSelect = document.getElementById('live-orderbook-preset');
            if (presetSelect) {
                presetSelect.addEventListener('change', (e) => {
                    this.applyLiveOrderBookPreset(e.target.value);
                });
            }
        }
    }

    getStrategyParameters(strategyType) {
        const parameters = {
            'sma': [
                { name: 'short_window', label: 'Short Window', type: 'number', default: 10, min: 2, max: 100 },
                { name: 'long_window', label: 'Long Window', type: 'number', default: 20, min: 5, max: 200 }
            ],
            'ema': [
                { name: 'short_window', label: 'Short Window', type: 'number', default: 10, min: 2, max: 100 },
                { name: 'long_window', label: 'Long Window', type: 'number', default: 20, min: 5, max: 200 }
            ],
            'rsi': [
                { name: 'window', label: 'RSI Window', type: 'number', default: 14, min: 5, max: 50 },
                { name: 'overbought', label: 'Overbought Level', type: 'number', default: 70, min: 60, max: 90 },
                { name: 'oversold', label: 'Oversold Level', type: 'number', default: 30, min: 10, max: 40 }
            ],
            'bollinger': [
                { name: 'window', label: 'Window', type: 'number', default: 20, min: 5, max: 100 },
                { name: 'std_dev', label: 'Standard Deviations', type: 'number', default: 2, min: 1, max: 3, step: 0.1 }
            ],
            'macd': [
                { name: 'fast_window', label: 'Fast Window', type: 'number', default: 12, min: 5, max: 50 },
                { name: 'slow_window', label: 'Slow Window', type: 'number', default: 26, min: 10, max: 100 },
                { name: 'signal_window', label: 'Signal Window', type: 'number', default: 9, min: 5, max: 30 }
            ],
            'stochastic': [
                { name: 'k_window', label: 'K Window', type: 'number', default: 14, min: 5, max: 50 },
                { name: 'd_window', label: 'D Window', type: 'number', default: 3, min: 2, max: 10 },
                { name: 'overbought', label: 'Overbought Level', type: 'number', default: 80, min: 70, max: 90 },
                { name: 'oversold', label: 'Oversold Level', type: 'number', default: 20, min: 10, max: 30 }
            ],
            'fibonacci': [
                { name: 'fib_lookback_period', label: 'Lookback Period', type: 'number', default: 20, min: 10, max: 100 },
                { name: 'fib_levels', label: 'Fibonacci Levels', type: 'text', default: '0.236,0.382,0.5,0.618,0.786' },
                { name: 'fib_confirmation_candles', label: 'Confirmation Candles', type: 'number', default: 2, min: 1, max: 5 }
            ],
            'orderbook': [
                { name: 'order_book_level', label: 'Order Book Level', type: 'number', default: 2, min: 1, max: 3 },
                { name: 'trade_history_limit', label: 'Trade History Limit', type: 'number', default: 1000, min: 10, max: 1000 },
                { name: 'bid_ask_spread_threshold', label: 'Bid-Ask Spread Threshold (%)', type: 'number', default: 0.5, min: 0.01, max: 1.0, step: 0.01 },
                { name: 'volume_imbalance_threshold', label: 'Volume Imbalance Threshold', type: 'number', default: 0.3, min: 0.1, max: 0.9, step: 0.1 },
                { name: 'large_trade_threshold', label: 'Large Trade Threshold ($)', type: 'number', default: 2000, min: 1000, max: 100000 },
                { name: 'data_analysis_mode', label: 'Data Analysis Mode', type: 'select', default: 'all', options: ['recent', 'all', 'sampled'] },
                { name: 'recent_data_limit', label: 'Recent Data Limit', type: 'number', default: 200, min: 10, max: 1000 },
                { name: 'sampling_ratio', label: 'Sampling Ratio', type: 'number', default: 0.1, min: 0.01, max: 1.0, step: 0.01 }
            ],
            'dca': [
                { name: 'interval_hours', label: 'Interval (Hours)', type: 'number', default: 24, min: 1, max: 168 },
                { name: 'amount', label: 'Amount per Interval', type: 'number', default: 100, min: 10, max: 10000 }
            ],
            'buyandhold': [
                { name: 'amount', label: 'Investment Amount', type: 'number', default: 1000, min: 100, max: 100000 }
            ]
        };

        return parameters[strategyType] || [];
    }

    updateTradingModeUI() {
        const mode = this.liveTrading.mode;
        const startButton = document.getElementById('start-trading');
        const warningText = document.querySelector('#live-mode + p');
        
        if (mode === 'live') {
            startButton.classList.add('bg-red-600', 'hover:bg-red-700');
            startButton.classList.remove('bg-green-600', 'hover:bg-green-700');
            startButton.innerHTML = '<i class="fas fa-exclamation-triangle mr-2"></i>Start LIVE Trading';
            if (warningText) {
                warningText.classList.add('text-red-600', 'font-semibold');
            }
        } else {
            startButton.classList.add('bg-green-600', 'hover:bg-green-700');
            startButton.classList.remove('bg-red-600', 'hover:bg-red-700');
            startButton.innerHTML = '<i class="fas fa-play mr-2"></i>Start Trading';
            if (warningText) {
                warningText.classList.remove('text-red-600', 'font-semibold');
            }
        }
    }

    updateSymbolModeUI() {
        const symbolMode = this.liveTrading.symbolMode;
        const singleConfig = document.getElementById('single-symbol-config');
        const universeConfig = document.getElementById('universe-config');
        
        if (symbolMode === 'universe') {
            singleConfig.classList.add('hidden');
            universeConfig.classList.remove('hidden');
            this.updateUniverseSelection(this.liveTrading.universe.type);
            
            // Sync strategy selectors
            const singleStrategy = document.getElementById('live-strategy-type');
            const universeStrategy = document.getElementById('universe-strategy-type');
            if (singleStrategy && universeStrategy) {
                universeStrategy.value = singleStrategy.value;
            }
        } else {
            singleConfig.classList.remove('hidden');
            universeConfig.classList.add('hidden');
            
            // Sync strategy selectors
            const singleStrategy = document.getElementById('live-strategy-type');
            const universeStrategy = document.getElementById('universe-strategy-type');
            if (singleStrategy && universeStrategy) {
                singleStrategy.value = universeStrategy.value;
            }
        }
    }

    async updateUniverseSelection(universeType) {
        this.liveTrading.universe.type = universeType;
        
        // Show/hide custom symbols config
        const customConfig = document.getElementById('custom-symbols-config');
        if (universeType === 'custom') {
            customConfig.classList.remove('hidden');
        } else {
            customConfig.classList.add('hidden');
        }
        
        // Load symbols based on type
        if (universeType === 'custom') {
            this.updateUniversePreview(this.liveTrading.universe.customSymbols);
        } else {
            await this.loadUniverseSymbols(universeType);
        }
    }

    async loadUniverseSymbols(universeType) {
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
                    case 'dex_tokens':
                        symbols = categories.dex_tokens || [];
                        break;
                    case 'meme_tokens':
                        symbols = categories.meme_tokens || [];
                        break;
                    case 'stablecoins':
                        symbols = categories.stablecoins || [];
                        break;
                    case 'all_usd':
                        symbols = categories.all_usd || [];
                        break;
                }
                
                // Limit symbols based on max size (if specified)
                const maxSizeInput = document.getElementById('universe-max-size').value;
                const maxSize = maxSizeInput ? parseInt(maxSizeInput) : null;
                if (maxSize && maxSize > 0) {
                    symbols = symbols.slice(0, maxSize);
                }
                
                this.liveTrading.universe.symbols = symbols;
                this.updateUniversePreview(symbols);
            }
        } catch (error) {
            console.error('Error loading universe symbols:', error);
        }
    }

    addCustomSymbol() {
        const input = document.getElementById('custom-symbol-input');
        const symbol = input.value.trim().toUpperCase();
        
        if (symbol && symbol.endsWith('-USD')) {
            if (!this.liveTrading.universe.customSymbols.includes(symbol)) {
                this.liveTrading.universe.customSymbols.push(symbol);
                input.value = '';
                this.updateUniversePreview(this.liveTrading.universe.customSymbols);
            } else {
                alert('Symbol already added to universe');
            }
        } else {
            alert('Please enter a valid USD symbol (e.g., BTC-USD)');
        }
    }

    removeCustomSymbol(symbol) {
        this.liveTrading.universe.customSymbols = this.liveTrading.universe.customSymbols.filter(s => s !== symbol);
        this.updateUniversePreview(this.liveTrading.universe.customSymbols);
    }

    updateUniversePreview(symbols) {
        const preview = document.getElementById('universe-symbols');
        const count = document.getElementById('universe-count');
        
        if (symbols.length === 0) {
            preview.innerHTML = '<div class="text-gray-500 text-sm">No symbols selected</div>';
            count.textContent = '0';
        } else {
            const symbolsHtml = symbols.map(symbol => {
                if (this.liveTrading.universe.type === 'custom') {
                    return `
                        <span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800 mr-2 mb-2">
                            ${symbol}
                            <button onclick="dashboard.removeCustomSymbol('${symbol}')" class="ml-1 text-blue-600 hover:text-blue-800">
                                <i class="fas fa-times"></i>
                            </button>
                        </span>
                    `;
                } else {
                    return `
                        <span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800 mr-2 mb-2">
                            ${symbol}
                        </span>
                    `;
                }
            }).join('');
            
            preview.innerHTML = symbolsHtml;
            count.textContent = symbols.length;
        }
    }

    resetBacktestingInputs() {
        // Reset backtesting form inputs to defaults
        console.log('Resetting backtesting inputs to defaults');
        
        // Strategy type
        const strategySelect = document.getElementById('strategy-type');
        if (strategySelect) {
            strategySelect.value = 'sma';
        }
        
        // Symbol
        const symbolSelect = document.getElementById('backtest-symbol');
        if (symbolSelect) {
            symbolSelect.value = 'BTC-USD';
        }
        
        // Time period
        const daysSelect = document.getElementById('backtest-days');
        if (daysSelect) {
            daysSelect.value = '30';
        }
        
        // Granularity
        const granularitySelect = document.getElementById('backtest-granularity');
        if (granularitySelect) {
            granularitySelect.value = '1h';
        }
        
        // Portfolio percentage
        const portfolioInput = document.getElementById('portfolio-percentage');
        if (portfolioInput) {
            portfolioInput.value = '5';
        }
        
        // Reset strategy-specific parameters
        this.loadStrategyParameters('sma');
        
        // Clear any previous results
        const resultsContainer = document.getElementById('backtest-results');
        if (resultsContainer) {
            resultsContainer.classList.add('hidden');
        }
        
        // Clear backtest history display
        const historyContainer = document.getElementById('backtest-history');
        if (historyContainer) {
            historyContainer.innerHTML = '<div class="text-gray-500 text-center py-8">No backtests yet. Run a backtest to see results here.</div>';
        }
    }

    resetLiveTradingInputs() {
        // Reset live trading form inputs to defaults
        console.log('Resetting live trading inputs to defaults');
        
        // Trading mode
        const simulatedMode = document.getElementById('simulated-mode');
        if (simulatedMode) {
            simulatedMode.checked = true;
        }
        const liveMode = document.getElementById('live-mode');
        if (liveMode) {
            liveMode.checked = false;
        }
        this.liveTrading.mode = 'simulated';
        
        // Symbol mode
        const singleSymbolMode = document.getElementById('single-symbol-mode');
        if (singleSymbolMode) {
            singleSymbolMode.checked = true;
        }
        const universeMode = document.getElementById('universe-mode');
        if (universeMode) {
            universeMode.checked = false;
        }
        this.liveTrading.symbolMode = 'single';
        
        // Single symbol configuration
        const symbolSelect = document.getElementById('live-trading-symbol');
        if (symbolSelect) {
            symbolSelect.value = 'BTC-USD';
        }
        
        const singleStrategySelect = document.getElementById('live-strategy-type');
        if (singleStrategySelect) {
            singleStrategySelect.value = 'sma';
        }
        
        const positionSizeInput = document.getElementById('live-position-size');
        if (positionSizeInput) {
            positionSizeInput.value = '5';
        }
        
        const maxPositionsInput = document.getElementById('live-max-positions');
        if (maxPositionsInput) {
            maxPositionsInput.value = '3';
        }
        
        const positionUpdateIntervalInput = document.getElementById('live-position-update-interval');
        if (positionUpdateIntervalInput) {
            positionUpdateIntervalInput.value = '5';
        }
        
        // Universe configuration
        const universeTypeSelect = document.getElementById('universe-type');
        if (universeTypeSelect) {
            universeTypeSelect.value = 'all_usd';
        }
        
        const universeStrategySelect = document.getElementById('universe-strategy-type');
        if (universeStrategySelect) {
            universeStrategySelect.value = 'sma';
        }
        
        const universeMaxSizeInput = document.getElementById('universe-max-size');
        if (universeMaxSizeInput) {
            universeMaxSizeInput.value = '';
        }
        
        const universePositionSizeInput = document.getElementById('universe-position-size');
        if (universePositionSizeInput) {
            universePositionSizeInput.value = '1';
        }
        
        const universeMaxPositionsInput = document.getElementById('universe-max-positions');
        if (universeMaxPositionsInput) {
            universeMaxPositionsInput.value = '50';
        }
        
        const universeSelectionMethodInput = document.getElementById('universe-selection-method');
        if (universeSelectionMethodInput) {
            universeSelectionMethodInput.value = 'signal_strength';
        }
        
        // Reset universe state
        this.liveTrading.universe = {
            type: 'all_usd',
            symbols: [],
            customSymbols: [],
            maxSize: 50,
            positionSize: 1.0,
            maxPositions: 50
        };
        
        // Reset custom symbols
        const customSymbolsList = document.getElementById('custom-symbols-list');
        if (customSymbolsList) {
            customSymbolsList.innerHTML = '';
        }
        
        const customSymbolInput = document.getElementById('custom-symbol-input');
        if (customSymbolInput) {
            customSymbolInput.value = '';
        }
        
        // Reset universe preview
        this.updateUniversePreview([]);
        
        // Update UI to reflect single symbol mode
        this.updateSymbolModeUI();
        
        // Reset strategy parameters
        this.loadStrategyParameters('sma');
        
        // Clear trading log
        const tradingLog = document.getElementById('trading-log');
        if (tradingLog) {
            tradingLog.innerHTML = '<div class="text-gray-500 text-sm">Trading log will appear here...</div>';
        }
        
        // Clear positions table
        const positionsTable = document.getElementById('positions-table-body');
        if (positionsTable) {
            positionsTable.innerHTML = '<tr><td colspan="6" class="text-center text-gray-500 py-4">No open positions</td></tr>';
        }
        
        // Clear trading history
        const historyTable = document.getElementById('trading-history-table-body');
        if (historyTable) {
            historyTable.innerHTML = '<tr><td colspan="7" class="text-center text-gray-500 py-4">No trading history</td></tr>';
        }
        
        // Reset trading state
        this.liveTrading.isActive = false;
        this.liveTrading.isPaused = false;
        this.liveTrading.positions = [];
        this.liveTrading.history = [];
        
        // Update trading controls
        this.updateTradingControls();
        this.updateTradingStatus('inactive');
    }
    
    applyOrderBookPreset(presetName) {
        if (presetName === 'custom') {
            return; // Don't change anything for custom
        }
        
        const preset = this.orderBookPresets[presetName];
        if (!preset) {
            console.warn(`Unknown preset: ${presetName}`);
            return;
        }
        
        // Apply preset values to form inputs
        const orderBookLevel = document.getElementById('order-book-level');
        if (orderBookLevel) orderBookLevel.value = preset.order_book_level;
        
        const tradeHistoryLimit = document.getElementById('trade-history-limit');
        if (tradeHistoryLimit) tradeHistoryLimit.value = preset.trade_history_limit;
        
        const bidAskSpreadThreshold = document.getElementById('bid-ask-spread-threshold');
        if (bidAskSpreadThreshold) bidAskSpreadThreshold.value = preset.bid_ask_spread_threshold;
        
        const volumeImbalanceThreshold = document.getElementById('volume-imbalance-threshold');
        if (volumeImbalanceThreshold) volumeImbalanceThreshold.value = preset.volume_imbalance_threshold;
        
        const largeTradeThreshold = document.getElementById('large-trade-threshold');
        if (largeTradeThreshold) largeTradeThreshold.value = preset.large_trade_threshold;
        
        const dataAnalysisMode = document.getElementById('data-analysis-mode');
        if (dataAnalysisMode) dataAnalysisMode.value = preset.data_analysis_mode;
        
        const recentDataLimit = document.getElementById('recent-data-limit');
        if (recentDataLimit) recentDataLimit.value = preset.recent_data_limit;
        
        const samplingRatio = document.getElementById('sampling-ratio');
        if (samplingRatio) samplingRatio.value = preset.sampling_ratio;
        
        console.log(`Applied Order Book preset: ${presetName}`, preset);
    }
    
    applyLiveOrderBookPreset(presetName) {
        if (presetName === 'custom') {
            return; // Don't change anything for custom
        }
        
        const preset = this.orderBookPresets[presetName];
        if (!preset) {
            console.warn(`Unknown preset: ${presetName}`);
            return;
        }
        
        // Apply preset values to live trading form inputs
        const orderBookLevel = document.getElementById('live-param-order_book_level');
        if (orderBookLevel) orderBookLevel.value = preset.order_book_level;
        
        const tradeHistoryLimit = document.getElementById('live-param-trade_history_limit');
        if (tradeHistoryLimit) tradeHistoryLimit.value = preset.trade_history_limit;
        
        const bidAskSpreadThreshold = document.getElementById('live-param-bid_ask_spread_threshold');
        if (bidAskSpreadThreshold) bidAskSpreadThreshold.value = preset.bid_ask_spread_threshold;
        
        const volumeImbalanceThreshold = document.getElementById('live-param-volume_imbalance_threshold');
        if (volumeImbalanceThreshold) volumeImbalanceThreshold.value = preset.volume_imbalance_threshold;
        
        const largeTradeThreshold = document.getElementById('live-param-large_trade_threshold');
        if (largeTradeThreshold) largeTradeThreshold.value = preset.large_trade_threshold;
        
        const dataAnalysisMode = document.getElementById('live-param-data_analysis_mode');
        if (dataAnalysisMode) dataAnalysisMode.value = preset.data_analysis_mode;
        
        const recentDataLimit = document.getElementById('live-param-recent_data_limit');
        if (recentDataLimit) recentDataLimit.value = preset.recent_data_limit;
        
        const samplingRatio = document.getElementById('live-param-sampling_ratio');
        if (samplingRatio) samplingRatio.value = preset.sampling_ratio;
        
        console.log(`Applied live Order Book preset: ${presetName}`, preset);
    }

    async startLiveTrading() {
        if (this.liveTrading.isActive) return;

        // Get strategy type based on symbol mode
        const strategyType = this.liveTrading.symbolMode === 'universe' 
            ? document.getElementById('universe-strategy-type').value
            : document.getElementById('live-strategy-type').value;
        
        // Get configuration based on symbol mode
        let symbols, positionSize, maxPositions, positionUpdateInterval;
        
        if (this.liveTrading.symbolMode === 'universe') {
            // Universe trading configuration
            const universeType = document.getElementById('universe-type').value;
            const universeMaxSizeInput = document.getElementById('universe-max-size').value;
            const universeMaxSize = universeMaxSizeInput ? parseInt(universeMaxSizeInput) : null;
            const universePositionSize = parseFloat(document.getElementById('universe-position-size').value) || 2.0;
            const universeMaxPositions = parseInt(document.getElementById('universe-max-positions').value) || 20;
            positionUpdateInterval = parseInt(document.getElementById('live-position-update-interval').value) || 5;
            
            if (universeType === 'custom') {
                symbols = this.liveTrading.universe.customSymbols;
            } else {
                symbols = this.liveTrading.universe.symbols;
                // Apply size limit only if specified and greater than 0
                if (universeMaxSize && universeMaxSize > 0) {
                    symbols = symbols.slice(0, universeMaxSize);
                }
            }
            
            if (symbols.length === 0) {
                alert('Please select symbols for universe trading');
                return;
            }
            
            positionSize = universePositionSize;
            maxPositions = universeMaxPositions;
        } else {
            // Single symbol trading configuration
            const symbol = document.getElementById('live-trading-symbol').value;
            symbols = [symbol];
            positionSize = parseFloat(document.getElementById('live-position-size').value);
            maxPositions = parseInt(document.getElementById('live-max-positions').value);
            positionUpdateInterval = parseInt(document.getElementById('live-position-update-interval').value) || 5;
        }

        // Get strategy parameters
        const strategyParams = this.getStrategyParameters(strategyType);
        const params = {};
        strategyParams.forEach(param => {
            const element = document.getElementById(`live-param-${param.name}`);
            if (element) {
                let value = element.value;
                if (param.type === 'number') {
                    value = parseFloat(value);
                } else if (param.name === 'fib_levels') {
                    value = value.split(',').map(v => parseFloat(v.trim()));
                }
                params[param.name] = value;
            }
        });

        try {
            // Call backend API to start asynchronous trading
            const response = await fetch('/api/async-trading/start', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    symbols: symbols,
                    strategy_type: strategyType,
                    strategy_params: params,
                    initial_balance: 10000.0,
                    max_positions: maxPositions,
                    position_size_percent: positionSize,
                    position_update_interval: positionUpdateInterval,
                    session_id: this.sessionId,
                    immediate_start: true,
                    batch_size: 3
                })
            });

            const data = await response.json();

            if (data.status === 'started') {
                // Initialize strategy with async loading info
                this.liveTrading.strategy = {
                    type: strategyType,
                    symbols: data.initial_symbols,
                    allSymbols: symbols,
                    symbolMode: this.liveTrading.symbolMode,
                    params: params,
                    positionSize: positionSize,
                    maxPositions: maxPositions,
                    strategyType: data.strategy_type,
                    strategyParams: data.strategy_params,
                    loadingProgress: data.loading_progress
                };

                this.liveTrading.isActive = true;
                this.liveTrading.isPaused = false;
                this.liveTrading.asyncLoading = true;

                this.updateTradingControls();
                this.updateTradingStatus('active');
                
                // Start loading order book signals immediately when trading starts
                await this.loadOrderBookSignals();
                // Start frequent order book signals refresh for async loading
                this.startOrderBookFrequentRefresh();
                
                // Show loading progress
                this.updateLoadingProgress(data.loading_progress);
                
                // Start monitoring loading progress
                this.startLoadingProgressMonitoring();
                
                // Update portfolio status immediately
                await this.updateTradingStatusFromAPI();
                
                // Log appropriate message based on symbol mode
                if (this.liveTrading.symbolMode === 'universe') {
                    this.logTradingEvent(`Started ${this.liveTrading.mode} universe trading with ${strategyType} strategy on ${symbols.length} symbols: ${symbols.join(', ')}`);
                } else {
                    this.logTradingEvent(`Started ${this.liveTrading.mode} trading with ${strategyType} strategy on ${symbols[0]}`);
                }

                // Start strategy monitoring
                this.startStrategyMonitoring();
                
                // Start periodic portfolio status updates
                this.startPortfolioStatusUpdates();
                
                // Start auto-save and save initial state
                this.startAutoSave();
                await this.saveSessionState();
                
                // Start trading stats updates
                this.startTradingStatsUpdates();
                this.tradingStats.sessionStartTime = new Date();
                
                // Auto-hide strategy configuration for cleaner interface
                this.autoHideStrategyOnTradingStart();
            } else {
                this.logTradingEvent(`Failed to start trading: ${data.error}`);
            }
        } catch (error) {
            this.logTradingEvent(`Error starting trading: ${error.message}`);
        }
    }

    async stopLiveTrading() {
        if (!this.liveTrading.isActive) return;

        try {
            // Call backend API to stop simulated trading
            const response = await fetch('/api/simulated-trading/stop', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            const data = await response.json();
            if (data.status === 'stopped') {
                this.logTradingEvent('Trading stopped successfully');
                
                // Stop live order book signals refresh
                this.stopOrderBookAutoRefresh();
                
                // Clear order book signals display
                this.updateOrderBookSignalsTable([]);
                this.updateOrderBookStatistics({
                    total_analyzed: 0,
                    active_signals: 0,
                    last_updated: new Date().toISOString(),
                    average_strength: 0,
                    message: "Trading stopped. Configure your strategy and start trading to see live signals."
                });
                
                // Stop portfolio status updates
                this.stopPortfolioStatusUpdates();
                
                // Stop loading progress monitoring
                this.stopLoadingProgressMonitoring();
                
                // Update portfolio status one final time
                await this.updateTradingStatusFromAPI();
            } else {
                this.logTradingEvent(`Error stopping trading: ${data.error}`);
            }
        } catch (error) {
            this.logTradingEvent(`Error stopping trading: ${error.message}`);
        }

        this.liveTrading.isActive = false;
        this.liveTrading.isPaused = false;

        this.updateTradingControls();
        this.updateTradingStatus('stopped');
        this.logTradingEvent('Trading stopped');
        
        // Stop auto-save and save final state
        this.stopAutoSave();
        await this.saveSessionState();
        
        // Stop trading stats updates
        this.stopTradingStatsUpdates();
        
        // Show strategy configuration again when trading stops
        this.showStrategyConfiguration();
    }

    pauseLiveTrading() {
        if (!this.liveTrading.isActive) return;

        this.liveTrading.isPaused = !this.liveTrading.isPaused;
        this.updateTradingControls();
        this.updateTradingStatus(this.liveTrading.isPaused ? 'paused' : 'active');
        this.logTradingEvent(this.liveTrading.isPaused ? 'Trading paused' : 'Trading resumed');
    }

    emergencyStop() {
        this.liveTrading.isActive = false;
        this.liveTrading.isPaused = false;
        
        // Stop auto-refresh
        this.stopOrderBookAutoRefresh();
        this.stopPortfolioStatusUpdates();
        
        // Clear order book signals display
        this.updateOrderBookSignalsTable([]);
        this.updateOrderBookStatistics({
            total_analyzed: 0,
            active_signals: 0,
            last_updated: new Date().toISOString(),
            average_strength: 0,
            message: "Emergency stop activated. Configure your strategy and start trading to see live signals."
        });
        
        // Close all positions if in live mode
        if (this.liveTrading.mode === 'live') {
            this.closeAllPositions();
        }

        this.updateTradingControls();
        this.updateTradingStatus('emergency_stop');
        this.logTradingEvent('EMERGENCY STOP - All trading halted');
        
        // Show strategy configuration again after emergency stop
        this.showStrategyConfiguration();
    }

    updateTradingControls() {
        const startBtn = document.getElementById('start-trading');
        const stopBtn = document.getElementById('stop-trading');
        const pauseBtn = document.getElementById('pause-trading');

        if (this.liveTrading.isActive) {
            startBtn.disabled = true;
            stopBtn.disabled = false;
            pauseBtn.disabled = false;
            pauseBtn.innerHTML = this.liveTrading.isPaused ? 
                '<i class="fas fa-play mr-2"></i>Resume Trading' : 
                '<i class="fas fa-pause mr-2"></i>Pause Trading';
        } else {
            startBtn.disabled = false;
            stopBtn.disabled = true;
            pauseBtn.disabled = true;
            pauseBtn.innerHTML = '<i class="fas fa-pause mr-2"></i>Pause Trading';
        }
    }

    updateTradingStatus(status) {
        const indicator = document.getElementById('trading-status-indicator');
        const text = document.getElementById('trading-status-text');
        const lastUpdate = document.getElementById('last-trading-update');

        const statusConfig = {
            'stopped': { color: 'bg-gray-400', text: 'Stopped' },
            'active': { color: 'bg-green-500', text: 'Active' },
            'paused': { color: 'bg-yellow-500', text: 'Paused' },
            'emergency_stop': { color: 'bg-red-500', text: 'Emergency Stop' }
        };

        const config = statusConfig[status] || statusConfig['stopped'];
        
        if (indicator) {
            indicator.className = `w-3 h-3 ${config.color} rounded-full`;
        }
        if (text) {
            text.textContent = config.text;
        }
        if (lastUpdate) {
            lastUpdate.textContent = new Date().toLocaleTimeString();
        }
    }

    logTradingEvent(message) {
        const logContainer = document.getElementById('trading-log');
        if (!logContainer) return;

        const timestamp = new Date().toLocaleTimeString();
        const logEntry = document.createElement('div');
        logEntry.className = 'text-green-400';
        logEntry.innerHTML = `[${timestamp}] ${message}`;

        logContainer.appendChild(logEntry);
        logContainer.scrollTop = logContainer.scrollHeight;

        // Keep only last 100 entries
        while (logContainer.children.length > 100) {
            logContainer.removeChild(logContainer.firstChild);
        }
        
        // Store log event in session for restoration
        this.storeTradingLogEvent(message, timestamp);
    }
    
    storeTradingLogEvent(message, timestamp) {
        // Store trading log events in localStorage for session restoration
        const logEvents = JSON.parse(localStorage.getItem('trading_log_events') || '[]');
        logEvents.push({
            message: message,
            timestamp: timestamp,
            fullTimestamp: new Date().toISOString()
        });
        
        // Keep only last 50 events in localStorage
        if (logEvents.length > 50) {
            logEvents.splice(0, logEvents.length - 50);
        }
        
        localStorage.setItem('trading_log_events', JSON.stringify(logEvents));
    }

    updatePortfolioStatus(portfolioData) {
        // Update available balance
        const availableBalance = document.getElementById('available-balance');
        if (availableBalance && portfolioData.cash_balance !== undefined) {
            availableBalance.textContent = `$${portfolioData.cash_balance.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        }

        // Update total value
        const totalValue = document.getElementById('total-value');
        if (totalValue && portfolioData.total_value !== undefined) {
            totalValue.textContent = `$${portfolioData.total_value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        }

        // Update open positions count
        const openPositions = document.getElementById('open-positions');
        if (openPositions) {
            // Count open positions from the positions object
            const positionsCount = portfolioData.positions ? Object.keys(portfolioData.positions).length : 0;
            openPositions.textContent = positionsCount;
        }

        // Update daily P&L
        const dailyPnl = document.getElementById('daily-pnl');
        if (dailyPnl && portfolioData.total_pnl !== undefined) {
            const pnlValue = portfolioData.total_pnl;
            dailyPnl.textContent = `${pnlValue >= 0 ? '+' : ''}$${pnlValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            dailyPnl.className = `text-sm font-semibold ${pnlValue >= 0 ? 'text-green-600' : 'text-red-600'}`;
        }
    }

    async updateTradingStatusFromAPI() {
        try {
            const response = await fetch('/api/simulated-trading/status');
            const data = await response.json();
            
            if (data.error) {
                console.error('Error fetching trading status:', data.error);
                return;
            }

            // Update portfolio status
            if (data.portfolio) {
                this.updatePortfolioStatus(data.portfolio);
            }

            // Update open positions if available
            if (data.open_positions) {
                this.liveTrading.positions = data.open_positions;
                this.updateOpenPositions(data.open_positions);
            }

            // Update recent trades if available
            if (data.recent_trades) {
                this.liveTrading.history = data.recent_trades;
                this.updateRecentTrades(data.recent_trades);
            }

            // Refresh paginated trading history to show latest trades
            this.loadPaginatedTradingHistory(this.tradingHistoryPagination.currentPage, this.tradingHistoryPagination.perPage);
            
            // Update trading stats when portfolio status changes
            this.loadTradingStats();

        } catch (error) {
            console.error('Error updating trading status:', error);
        }
    }

    updateOpenPositions(positions) {
        // Update the open positions display with pagination
        const tbody = document.getElementById('positions-tbody');
        if (!tbody) return;

        if (!positions || positions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="px-6 py-4 text-center text-gray-500">No open positions</td></tr>';
            this.updatePositionsPagination(0);
            return;
        }

        // Update pagination state
        this.positionsPagination.totalPositions = positions.length;
        this.positionsPagination.totalPages = Math.ceil(positions.length / this.positionsPagination.perPage);
        
        // Ensure current page is valid
        if (this.positionsPagination.currentPage > this.positionsPagination.totalPages) {
            this.positionsPagination.currentPage = Math.max(1, this.positionsPagination.totalPages);
        }

        // Calculate pagination slice
        const startIndex = (this.positionsPagination.currentPage - 1) * this.positionsPagination.perPage;
        const endIndex = startIndex + this.positionsPagination.perPage;
        const paginatedPositions = positions.slice(startIndex, endIndex);

        if (paginatedPositions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="px-6 py-4 text-center text-gray-500">No positions on this page</td></tr>';
        } else {
            tbody.innerHTML = paginatedPositions.map(position => `
                <tr>
                    <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${position.symbol}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${position.side}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${position.quantity.toFixed(6)}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">$${position.entry_price.toFixed(2)}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">$${position.current_price.toFixed(2)}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm ${position.unrealized_pnl >= 0 ? 'text-green-600' : 'text-red-600'}">
                        ${position.unrealized_pnl >= 0 ? '+' : ''}$${position.unrealized_pnl.toFixed(2)}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        <button onclick="dashboard.closePosition('${position.symbol}')" 
                                class="text-red-600 hover:text-red-900">Close</button>
                    </td>
                </tr>
            `).join('');
        }

        // Update pagination controls
        this.updatePositionsPagination(positions.length);

        // Also log for debugging
        this.logTradingEvent(`Updated ${positions.length} open positions (showing ${paginatedPositions.length} on page ${this.positionsPagination.currentPage})`);
    }

    updateRecentTrades(trades) {
        // Update the trading history display
        const tbody = document.getElementById('history-tbody');
        if (!tbody) return;

        if (!trades || trades.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="px-6 py-4 text-center text-gray-500">No trading history</td></tr>';
            return;
        }

        tbody.innerHTML = trades.map(trade => {
            // Format strategy information
            const strategyInfo = trade.strategy_type || 'Unknown';
            const strategyParams = trade.strategy_params || {};
            const strategyTooltip = Object.keys(strategyParams).length > 0 
                ? `title="${JSON.stringify(strategyParams, null, 2)}"` 
                : '';
            
            return `
                <tr>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${new Date(trade.timestamp).toLocaleString()}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${trade.symbol}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${trade.side === 'buy' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                            ${trade.side.toUpperCase()}
                        </span>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${trade.quantity.toFixed(6)}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">$${trade.price.toFixed(2)}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm ${trade.pnl >= 0 ? 'text-green-600' : 'text-red-600'}">
                        ${trade.pnl >= 0 ? '+' : ''}$${trade.pnl.toFixed(2)}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500" ${strategyTooltip}>
                        <span class="px-2 py-1 text-xs font-medium bg-blue-100 text-blue-800 rounded-full">
                            ${strategyInfo}
                        </span>
                    </td>
                </tr>
            `;
        }).join('');

        // Also log for debugging
        this.logTradingEvent(`Updated ${trades.length} recent trades`);
    }

    // Paginated Trading History Methods
    async loadPaginatedTradingHistory(page = 1, perPage = 10) {
        try {
            const sessionId = this.liveTrading.strategy?.sessionId || this.sessionId;
            const params = new URLSearchParams({
                page: page.toString(),
                per_page: perPage.toString()
            });
            
            if (sessionId) {
                params.append('session_id', sessionId);
            }
            
            const response = await fetch(`/api/trades/paginated?${params}`);
            const data = await response.json();
            
            if (data.error) {
                console.error('Error loading paginated trading history:', data.error);
                this.updateTradingHistoryInfo('Error loading history', 0, 0);
                return;
            }
            
            // Update pagination state
            this.tradingHistoryPagination = {
                currentPage: data.pagination.current_page,
                perPage: data.pagination.per_page,
                totalPages: data.pagination.total_pages,
                totalTrades: data.pagination.total_trades
            };
            
            // Update the display
            this.updateRecentTrades(data.trades);
            this.updateTradingHistoryInfo(
                `Page ${data.pagination.current_page} of ${data.pagination.total_pages}`,
                data.pagination.total_trades,
                data.trades.length
            );
            this.updatePaginationControls();
            
        } catch (error) {
            console.error('Error loading paginated trading history:', error);
            this.updateTradingHistoryInfo('Error loading history', 0, 0);
        }
    }

    updateTradingHistoryInfo(pageInfo, totalTrades, currentPageTrades) {
        const infoElement = document.getElementById('trading-history-info');
        if (infoElement) {
            if (totalTrades > 0) {
                infoElement.textContent = `${pageInfo} (${totalTrades} total trades, showing ${currentPageTrades})`;
            } else {
                infoElement.textContent = 'No trading history';
            }
        }
    }

    updatePaginationControls() {
        const { currentPage, totalPages, totalTrades } = this.tradingHistoryPagination;
        
        // Update page info
        const pageInfoElement = document.getElementById('page-info');
        if (pageInfoElement) {
            pageInfoElement.textContent = `Page ${currentPage} of ${totalPages}`;
        }
        
        // Update button states
        const firstPageBtn = document.getElementById('first-page');
        const prevPageBtn = document.getElementById('prev-page');
        const nextPageBtn = document.getElementById('next-page');
        const lastPageBtn = document.getElementById('last-page');
        
        if (firstPageBtn) firstPageBtn.disabled = currentPage <= 1;
        if (prevPageBtn) prevPageBtn.disabled = currentPage <= 1;
        if (nextPageBtn) nextPageBtn.disabled = currentPage >= totalPages;
        if (lastPageBtn) lastPageBtn.disabled = currentPage >= totalPages;
        
        // Show/hide pagination controls based on total pages
        const paginationElement = document.getElementById('trading-history-pagination');
        if (paginationElement) {
            paginationElement.style.display = totalPages > 1 ? 'flex' : 'none';
        }
    }

    setupTradingHistoryPagination() {
        // First page button
        const firstPageBtn = document.getElementById('first-page');
        if (firstPageBtn) {
            firstPageBtn.addEventListener('click', () => {
                this.loadPaginatedTradingHistory(1, this.tradingHistoryPagination.perPage);
            });
        }
        
        // Previous page button
        const prevPageBtn = document.getElementById('prev-page');
        if (prevPageBtn) {
            prevPageBtn.addEventListener('click', () => {
                const newPage = Math.max(1, this.tradingHistoryPagination.currentPage - 1);
                this.loadPaginatedTradingHistory(newPage, this.tradingHistoryPagination.perPage);
            });
        }
        
        // Next page button
        const nextPageBtn = document.getElementById('next-page');
        if (nextPageBtn) {
            nextPageBtn.addEventListener('click', () => {
                const newPage = Math.min(this.tradingHistoryPagination.totalPages, this.tradingHistoryPagination.currentPage + 1);
                this.loadPaginatedTradingHistory(newPage, this.tradingHistoryPagination.perPage);
            });
        }
        
        // Last page button
        const lastPageBtn = document.getElementById('last-page');
        if (lastPageBtn) {
            lastPageBtn.addEventListener('click', () => {
                this.loadPaginatedTradingHistory(this.tradingHistoryPagination.totalPages, this.tradingHistoryPagination.perPage);
            });
        }
        
        // Per page selector
        const perPageSelect = document.getElementById('per-page-select');
        if (perPageSelect) {
            perPageSelect.addEventListener('change', (e) => {
                const newPerPage = parseInt(e.target.value);
                this.tradingHistoryPagination.perPage = newPerPage;
                this.loadPaginatedTradingHistory(1, newPerPage); // Reset to first page
            });
        }
        
        // Refresh button
        const refreshBtn = document.getElementById('refresh-trading-history');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.loadPaginatedTradingHistory(this.tradingHistoryPagination.currentPage, this.tradingHistoryPagination.perPage);
            });
        }
    }

    setupOrderBookSignalsPagination() {
        // First page button
        const firstPageBtn = document.getElementById('orderbook-first-page');
        if (firstPageBtn) {
            firstPageBtn.addEventListener('click', () => {
                this.loadPaginatedOrderBookSignals(1, this.orderBookSignalsPagination.perPage);
            });
        }
        
        // Previous page button
        const prevPageBtn = document.getElementById('orderbook-prev-page');
        if (prevPageBtn) {
            prevPageBtn.addEventListener('click', () => {
                const newPage = Math.max(1, this.orderBookSignalsPagination.currentPage - 1);
                this.loadPaginatedOrderBookSignals(newPage, this.orderBookSignalsPagination.perPage);
            });
        }
        
        // Next page button
        const nextPageBtn = document.getElementById('orderbook-next-page');
        if (nextPageBtn) {
            nextPageBtn.addEventListener('click', () => {
                const newPage = Math.min(this.orderBookSignalsPagination.totalPages, this.orderBookSignalsPagination.currentPage + 1);
                this.loadPaginatedOrderBookSignals(newPage, this.orderBookSignalsPagination.perPage);
            });
        }
        
        // Last page button
        const lastPageBtn = document.getElementById('orderbook-last-page');
        if (lastPageBtn) {
            lastPageBtn.addEventListener('click', () => {
                this.loadPaginatedOrderBookSignals(this.orderBookSignalsPagination.totalPages, this.orderBookSignalsPagination.perPage);
            });
        }
        
        // Per page selector
        const perPageSelect = document.getElementById('orderbook-per-page');
        if (perPageSelect) {
            perPageSelect.addEventListener('change', (e) => {
                const newPerPage = parseInt(e.target.value);
                this.orderBookSignalsPagination.perPage = newPerPage;
                this.loadPaginatedOrderBookSignals(1, newPerPage); // Reset to first page
            });
        }
        
        // Refresh button
        const refreshBtn = document.getElementById('refresh-orderbook-signals');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.loadPaginatedOrderBookSignals(this.orderBookSignalsPagination.currentPage, this.orderBookSignalsPagination.perPage);
            });
        }
    }

    // Paginated Order Book Signals Methods
    async loadPaginatedOrderBookSignals(page = 1, perPage = 10) {
        try {
            const sessionId = this.liveTrading.strategy?.sessionId || this.sessionId;
            const params = new URLSearchParams({
                page: page.toString(),
                per_page: perPage.toString()
            });
            
            if (sessionId) {
                params.append('session_id', sessionId);
            }
            
            const response = await fetch(`/api/orderbook/signals/paginated?${params}`);
            const data = await response.json();
            
            if (data.status !== 'success') {
                console.error('Error loading paginated order book signals:', data.message);
                this.updateOrderBookSignalsInfo('Error loading signals', 0, 0);
                return;
            }
            
            // Update pagination state
            this.orderBookSignalsPagination = {
                currentPage: data.pagination.current_page,
                perPage: data.pagination.per_page,
                totalPages: data.pagination.total_pages,
                totalSignals: data.pagination.total_signals
            };
            
            // Update the display
            this.updateOrderBookSignalsTable(data.signals);
            this.updateOrderBookSignalsInfo(
                `Page ${data.pagination.current_page} of ${data.pagination.total_pages}`,
                data.pagination.total_signals,
                data.signals.length
            );
            this.updateOrderBookSignalsPaginationControls();
            
        } catch (error) {
            console.error('Error loading paginated order book signals:', error);
            this.updateOrderBookSignalsInfo('Error loading signals', 0, 0);
        }
    }

    updateOrderBookSignalsInfo(pageInfo, totalSignals, currentPageSignals) {
        const infoElement = document.getElementById('orderbook-signals-info');
        if (infoElement) {
            if (totalSignals > 0) {
                infoElement.textContent = `${pageInfo} (${totalSignals} total signals, showing ${currentPageSignals})`;
            } else {
                infoElement.textContent = 'No order book signals available';
            }
        }
    }

    updateOrderBookPaginationControls() {
        const { currentPage, totalPages, totalSignals } = this.orderBookSignalsPagination;
        
        // Update page info
        const pageInfoElement = document.getElementById('orderbook-page-info');
        if (pageInfoElement) {
            pageInfoElement.textContent = `Page ${currentPage} of ${totalPages}`;
        }
        
        // Update button states
        const firstPageBtn = document.getElementById('orderbook-first-page');
        const prevPageBtn = document.getElementById('orderbook-prev-page');
        const nextPageBtn = document.getElementById('orderbook-next-page');
        const lastPageBtn = document.getElementById('orderbook-last-page');
        
        if (firstPageBtn) firstPageBtn.disabled = currentPage <= 1;
        if (prevPageBtn) prevPageBtn.disabled = currentPage <= 1;
        if (nextPageBtn) nextPageBtn.disabled = currentPage >= totalPages;
        if (lastPageBtn) lastPageBtn.disabled = currentPage >= totalPages;
    }

    // Open Positions Pagination Methods
    updatePositionsPagination(totalPositions) {
        const { currentPage, totalPages } = this.positionsPagination;
        
        // Update page info
        const pageInfoElement = document.getElementById('positions-page-info');
        if (pageInfoElement) {
            pageInfoElement.textContent = `Page ${currentPage} of ${totalPages}`;
        }
        
        // Update button states
        const firstPageBtn = document.getElementById('positions-first-page');
        const prevPageBtn = document.getElementById('positions-prev-page');
        const nextPageBtn = document.getElementById('positions-next-page');
        const lastPageBtn = document.getElementById('positions-last-page');
        
        if (firstPageBtn) firstPageBtn.disabled = currentPage <= 1;
        if (prevPageBtn) prevPageBtn.disabled = currentPage <= 1;
        if (nextPageBtn) nextPageBtn.disabled = currentPage >= totalPages;
        if (lastPageBtn) lastPageBtn.disabled = currentPage >= totalPages;
        
        // Update positions info
        const positionsInfoElement = document.getElementById('positions-info');
        if (positionsInfoElement) {
            if (totalPositions === 0) {
                positionsInfoElement.textContent = 'No open positions';
            } else {
                const startIndex = (currentPage - 1) * this.positionsPagination.perPage + 1;
                const endIndex = Math.min(currentPage * this.positionsPagination.perPage, totalPositions);
                positionsInfoElement.textContent = `Showing ${startIndex}-${endIndex} of ${totalPositions} positions`;
            }
        }
    }

    setupPositionsPagination() {
        // First page button
        const firstPageBtn = document.getElementById('positions-first-page');
        if (firstPageBtn) {
            firstPageBtn.addEventListener('click', () => {
                this.positionsPagination.currentPage = 1;
                this.updateOpenPositions(this.liveTrading.positions);
            });
        }
        
        // Previous page button
        const prevPageBtn = document.getElementById('positions-prev-page');
        if (prevPageBtn) {
            prevPageBtn.addEventListener('click', () => {
                this.positionsPagination.currentPage = Math.max(1, this.positionsPagination.currentPage - 1);
                this.updateOpenPositions(this.liveTrading.positions);
            });
        }
        
        // Next page button
        const nextPageBtn = document.getElementById('positions-next-page');
        if (nextPageBtn) {
            nextPageBtn.addEventListener('click', () => {
                this.positionsPagination.currentPage = Math.min(this.positionsPagination.totalPages, this.positionsPagination.currentPage + 1);
                this.updateOpenPositions(this.liveTrading.positions);
            });
        }
        
        // Last page button
        const lastPageBtn = document.getElementById('positions-last-page');
        if (lastPageBtn) {
            lastPageBtn.addEventListener('click', () => {
                this.positionsPagination.currentPage = this.positionsPagination.totalPages;
                this.updateOpenPositions(this.liveTrading.positions);
            });
        }
        
        // Per page selector
        const perPageSelect = document.getElementById('positions-per-page');
        if (perPageSelect) {
            perPageSelect.addEventListener('change', (e) => {
                this.positionsPagination.perPage = parseInt(e.target.value);
                this.positionsPagination.currentPage = 1; // Reset to first page
                this.updateOpenPositions(this.liveTrading.positions);
            });
        }
        
        // Refresh button
        const refreshBtn = document.getElementById('refresh-positions');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.updateOpenPositions(this.liveTrading.positions);
            });
        }
    }

    updateOrderBookSignalsPaginationControls() {
        const { currentPage, totalPages, totalSignals } = this.orderBookSignalsPagination;
        
        // Update page info
        const pageInfoElement = document.getElementById('orderbook-page-info');
        if (pageInfoElement) {
            pageInfoElement.textContent = `Page ${currentPage} of ${totalPages}`;
        }
        
        // Update button states
        const firstBtn = document.getElementById('orderbook-first-page');
        const prevBtn = document.getElementById('orderbook-prev-page');
        const nextBtn = document.getElementById('orderbook-next-page');
        const lastBtn = document.getElementById('orderbook-last-page');
        
        if (firstBtn) {
            firstBtn.disabled = currentPage <= 1;
        }
        if (prevBtn) {
            prevBtn.disabled = currentPage <= 1;
        }
        if (nextBtn) {
            nextBtn.disabled = currentPage >= totalPages;
        }
        if (lastBtn) {
            lastBtn.disabled = currentPage >= totalPages;
        }
        
        // Show/hide pagination controls
        const paginationElement = document.getElementById('orderbook-signals-pagination');
        if (paginationElement) {
            paginationElement.style.display = totalPages > 1 ? 'flex' : 'none';
        }
    }

    startPortfolioStatusUpdates() {
        // Clear existing interval
        if (this.portfolioUpdateInterval) {
            clearInterval(this.portfolioUpdateInterval);
        }

        // Update portfolio status every 5 seconds while trading is active
        this.portfolioUpdateInterval = setInterval(async () => {
            if (this.liveTrading.isActive) {
                await this.updateTradingStatusFromAPI();
            } else {
                // Stop updating if trading is not active
                this.stopPortfolioStatusUpdates();
            }
        }, 5000);
    }

    stopPortfolioStatusUpdates() {
        if (this.portfolioUpdateInterval) {
            clearInterval(this.portfolioUpdateInterval);
            this.portfolioUpdateInterval = null;
        }
    }

    startStrategyMonitoring() {
        // This would integrate with the WebSocket data feed
        // For now, we'll simulate strategy monitoring
        if (!this.liveTrading.isActive) return;

        // In a real implementation, this would:
        // 1. Subscribe to real-time price data for the symbol
        // 2. Run the strategy on each price update
        // 3. Execute trades based on strategy signals
        // 4. Update positions and portfolio

        this.logTradingEvent('Strategy monitoring started - waiting for signals...');
    }

    closeAllPositions() {
        // Close all open positions
        this.liveTrading.positions.forEach(position => {
            this.closePosition(position.id);
        });
    }

    closePosition(positionId) {
        // Close a specific position
        const position = this.liveTrading.positions.find(p => p.id === positionId);
        if (position) {
            // In live mode, this would execute actual trades
            // In simulated mode, this updates the portfolio
            this.logTradingEvent(`Closing position: ${position.symbol} ${position.side} ${position.size}`);
            
            // Remove from positions
            this.liveTrading.positions = this.liveTrading.positions.filter(p => p.id !== positionId);
            this.updatePositionsTable();
        }
    }

    updatePositionsTable() {
        const tbody = document.getElementById('positions-tbody');
        if (!tbody) return;

        if (this.liveTrading.positions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="px-6 py-4 text-center text-gray-500">No open positions</td></tr>';
            return;
        }

        tbody.innerHTML = this.liveTrading.positions.map(position => `
            <tr>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${position.symbol}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${position.side}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${position.size}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">$${position.entryPrice.toFixed(2)}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">$${position.currentPrice.toFixed(2)}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm ${position.pnl >= 0 ? 'text-green-600' : 'text-red-600'}">
                    ${position.pnl >= 0 ? '+' : ''}$${position.pnl.toFixed(2)}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    <button onclick="dashboard.closePosition('${position.id}')" 
                            class="text-red-600 hover:text-red-900">Close</button>
                </td>
            </tr>
        `).join('');
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
            this.resetBacktestingInputs();
        });
        document.getElementById('tab-data').addEventListener('click', () => {
            this.switchTab('data');
        });
        document.getElementById('tab-trading-history').addEventListener('click', () => {
            this.switchTab('trading-history');
        });
        document.getElementById('tab-settings').addEventListener('click', () => {
            this.switchTab('settings');
        });
        
        // Real-time data toggle
        document.getElementById('realtime-toggle').addEventListener('change', (e) => {
            this.updateToggleVisualState(e.target.checked);
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

        // Backtest history handlers
        document.getElementById('refresh-history').addEventListener('click', () => {
            this.loadBacktestHistory();
        });

        document.getElementById('clear-history').addEventListener('click', () => {
            this.clearOldBacktests();
        });

        document.getElementById('history-symbol-filter').addEventListener('change', () => {
            this.loadBacktestHistory();
        });

        document.getElementById('history-strategy-filter').addEventListener('change', () => {
            this.loadBacktestHistory();
        });

        document.getElementById('history-prev').addEventListener('click', () => {
            this.loadBacktestHistory(this.currentHistoryOffset - this.historyLimit);
        });

        document.getElementById('history-next').addEventListener('click', () => {
            this.loadBacktestHistory(this.currentHistoryOffset + this.historyLimit);
        });

        // DCA toggle handler
        document.getElementById('enable-dca').addEventListener('change', (e) => {
            this.toggleDCAOptions(e.target.checked);
        });

        // Buy and Hold toggle handler
        document.getElementById('enable-buy-hold').addEventListener('change', (e) => {
            this.toggleBuyHoldOptions(e.target.checked);
        });

        // Buy and Hold exit condition handler
        document.getElementById('buy-hold-exit-condition').addEventListener('change', (e) => {
            this.toggleBuyHoldProfitTarget(e.target.value);
        });
        
        // Risk management toggles
        document.getElementById('enable-stop-loss').addEventListener('change', (e) => {
            this.toggleStopLossOptions(e.target.checked);
        });
        
        document.getElementById('enable-take-profit').addEventListener('change', (e) => {
            this.toggleTakeProfitOptions(e.target.checked);
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
            isSwitchingSymbol: this.isSwitchingSymbol,
            websocketSubscriptionsUpdated: this.websocketSubscriptionsUpdated,
            hasTickerData: !!(data.data && data.data.ticker)
        });
        
        // Check if the message is for the current symbol
        if (data.product_id && data.product_id !== this.currentSymbol) {
            console.log('Ignoring message for different symbol:', data.product_id, 'current:', this.currentSymbol);
            return; // Ignore messages for other symbols
        }
        
        // If no product_id is specified, assume it's for the current symbol
        if (!data.product_id) {
            console.log('WebSocket message without product_id, assuming current symbol:', this.currentSymbol);
        }
        
        // Skip WebSocket messages if we're switching symbols and subscriptions haven't been updated yet
        if (this.isSwitchingSymbol && !this.websocketSubscriptionsUpdated) {
            console.log('Skipping WebSocket message during symbol switch (subscriptions not updated yet)');
            return;
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
        } else if (data.type === 'symbol_loading_progress') {
            // Handle symbol loading progress updates
            this.handleSymbolLoadingProgress(data.data).catch(error => {
                console.error('Error handling symbol loading progress:', error);
            });
        } else if (data.type === 'symbol_loading_complete') {
            // Handle symbol loading completion
            this.handleSymbolLoadingComplete(data.data).catch(error => {
                console.error('Error handling symbol loading complete:', error);
            });
        } else if (data.type === 'symbol_loading_error') {
            // Handle symbol loading errors
            this.handleSymbolLoadingError(data.data).catch(error => {
                console.error('Error handling symbol loading error:', error);
            });
        }
    }

    updateRealTimeData(data) {
        // Update price data
        if (data.ticker) {
            const price = parseFloat(data.ticker.price || 0);
            const apiChange24h = parseFloat(data.ticker.price_change_24h || 0);
            
            console.log('Updating real-time data:', {
                currentSymbol: this.currentSymbol,
                price,
                volume: data.ticker.volume_24h,
                change24h: apiChange24h,
                isSwitchingSymbol: this.isSwitchingSymbol,
                websocketSubscriptionsUpdated: this.websocketSubscriptionsUpdated
            });
            
            document.getElementById('current-price').textContent = `$${price.toFixed(2)}`;
            
            // Mark that we have real-time data for this symbol
            this.hasRealTimeData = true;
            
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
                this.updateToggleVisualState(!enabled);
            }
        } catch (error) {
            console.error('Error toggling real-time data:', error);
            this.showNotification('Failed to toggle real-time data', 'error');
            // Revert the toggle state
            document.getElementById('realtime-toggle').checked = !enabled;
            this.updateToggleVisualState(!enabled);
        }
    }

    updateToggleVisualState(checked) {
        const toggleSwitch = document.getElementById('toggle-switch');
        const toggleKnob = document.getElementById('toggle-knob');
        
        if (checked) {
            toggleSwitch.classList.remove('bg-gray-200');
            toggleSwitch.classList.add('bg-blue-600');
            toggleKnob.classList.remove('translate-x-0');
            toggleKnob.classList.add('translate-x-5');
        } else {
            toggleSwitch.classList.remove('bg-blue-600');
            toggleSwitch.classList.add('bg-gray-200');
            toggleKnob.classList.remove('translate-x-5');
            toggleKnob.classList.add('translate-x-0');
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
            this.updateToggleVisualState(status.enabled);
            
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
            console.log(`Loading current price data for ${this.currentSymbol}`, {
                hasRealTimeData: this.hasRealTimeData,
                isSwitchingSymbol: this.isSwitchingSymbol
            });
            
            // If we already have real-time data and we're not switching symbols, don't override it
            // But always load data during symbol switches to ensure we have something to display
            if (this.hasRealTimeData && !this.isSwitchingSymbol) {
                console.log('Already have real-time data, skipping loadCurrentPriceData');
                return;
            }
            
            // Force load data if we're switching symbols or if we don't have real-time data
            if (this.isSwitchingSymbol || !this.hasRealTimeData) {
                console.log('Force loading data - switching symbols or no real-time data');
            }
            
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
                
                console.log('Updated display with real-time data:', {
                    price: `$${price.toFixed(2)}`,
                    volume: volume.toLocaleString(),
                    source: 'real-time'
                });
                
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
                    
                    console.log('Updated display with historical data:', {
                        price: `$${price.toFixed(2)}`,
                        volume: volume.toLocaleString(),
                        source: 'historical'
                    });
                    
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
            
            // Force update the display to ensure it's showing the correct values
            console.log('Final display values after loadCurrentPriceData:', {
                currentPrice: document.getElementById('current-price').textContent,
                volume: document.getElementById('volume-24h').textContent,
                symbol: this.currentSymbol
            });
            
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
        const enableStopLoss = document.getElementById('enable-stop-loss').checked;
        const enableTakeProfit = document.getElementById('enable-take-profit').checked;
        const initialCapital = parseFloat(document.getElementById('initial-capital').value);
        const portfolioPercentage = parseFloat(document.getElementById('portfolio-percentage').value);
        
        // Get strategy-specific parameters
        let strategyParams = {};
        if (strategyType === 'sma') {
            strategyParams = {
                short_window: parseInt(document.getElementById('short-window').value),
                long_window: parseInt(document.getElementById('long-window').value)
            };
        } else if (strategyType === 'ema') {
            const alphaValue = document.getElementById('ema-alpha').value;
            strategyParams = {
                short_ema: parseInt(document.getElementById('ema-short').value),
                long_ema: parseInt(document.getElementById('ema-long').value),
                alpha: alphaValue ? parseFloat(alphaValue) : null
            };
        } else if (strategyType === 'rsi') {
            strategyParams = {
                period: parseInt(document.getElementById('rsi-period').value),
                oversold: parseInt(document.getElementById('rsi-oversold').value),
                overbought: parseInt(document.getElementById('rsi-overbought').value)
            };
        } else if (strategyType === 'macd') {
            strategyParams = {
                fast_ema: parseInt(document.getElementById('macd-fast').value),
                slow_ema: parseInt(document.getElementById('macd-slow').value),
                signal_ema: parseInt(document.getElementById('macd-signal').value)
            };
        } else if (strategyType === 'stochastic') {
            strategyParams = {
                k_period: parseInt(document.getElementById('stoch-k-period').value),
                d_period: parseInt(document.getElementById('stoch-d-period').value),
                overbought: parseInt(document.getElementById('stoch-overbought').value),
                oversold: parseInt(document.getElementById('stoch-oversold').value)
            };
        } else if (strategyType === 'atr') {
            strategyParams = {
                period: parseInt(document.getElementById('atr-period').value),
                atr_multiplier: parseFloat(document.getElementById('atr-multiplier').value),
                volatility_threshold: parseFloat(document.getElementById('atr-volatility-threshold').value),
                position_size_atr: parseFloat(document.getElementById('atr-position-size').value) / 100
            };
        } else if (strategyType === 'bollinger') {
            strategyParams = {
                period: parseInt(document.getElementById('bb-period').value),
                std_dev: parseFloat(document.getElementById('bb-std').value)
            };
        } else if (strategyType === 'fibonacci') {
            const fibLevelsString = document.getElementById('fib-levels').value;
            const fibLevels = fibLevelsString.split(',').map(level => parseFloat(level.trim()));
            strategyParams = {
                lookback_period: parseInt(document.getElementById('fib-lookback-period').value),
                fib_levels: fibLevels,
                confirmation_candles: parseInt(document.getElementById('fib-confirmation-candles').value)
            };
        } else if (strategyType === 'orderbook') {
            strategyParams = {
                order_book_level: parseInt(document.getElementById('order-book-level').value),
                trade_history_limit: parseInt(document.getElementById('trade-history-limit').value),
                bid_ask_spread_threshold: parseFloat(document.getElementById('bid-ask-spread-threshold').value) / 100, // Convert percentage to decimal
                volume_imbalance_threshold: parseFloat(document.getElementById('volume-imbalance-threshold').value),
                large_trade_threshold: parseFloat(document.getElementById('large-trade-threshold').value),
                data_analysis_mode: document.getElementById('data-analysis-mode').value,
                recent_data_limit: parseInt(document.getElementById('recent-data-limit').value),
                sampling_ratio: parseFloat(document.getElementById('sampling-ratio').value)
            };
        }
        
        const resultsContainer = document.getElementById('backtest-results');
        resultsContainer.innerHTML = '<div class="text-center"><i class="fas fa-spinner fa-spin mr-2"></i>Running backtest...</div>';
        resultsContainer.classList.remove('hidden');
        
        // Refresh backtest history at the beginning of each new backtest
        try {
            this.loadBacktestHistory(0);
        } catch (error) {
            console.warn('Failed to refresh history at start of backtest:', error);
        }
        
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
                    enable_stop_loss: enableStopLoss,
                    enable_take_profit: enableTakeProfit,
                    initial_capital: initialCapital,
                    portfolio_percentage: portfolioPercentage,
                    strategy_params: strategyParams,
                    enable_dca: document.getElementById('enable-dca').checked,
                    dca_amount: parseFloat(document.getElementById('dca-amount').value),
                    dca_frequency: parseInt(document.getElementById('dca-frequency').value),
                    dca_max_investments: parseInt(document.getElementById('dca-max-investments').value),
                    dca_start_delay: parseInt(document.getElementById('dca-start-delay').value),
                    enable_buy_hold: document.getElementById('enable-buy-hold').checked,
                    buy_hold_exit_condition: document.getElementById('buy-hold-exit-condition').value,
                    buy_hold_profit_target: parseFloat(document.getElementById('buy-hold-profit-target').value)
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.displayBacktestResults(result);
                // Refresh history after successful backtest
                try {
                    this.loadBacktestHistory(0);
                } catch (error) {
                    console.warn('Failed to refresh history after backtest:', error);
                }
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
                            <!-- SMA Strategy Signals -->
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
                            <!-- Bollinger Bands Strategy Signals -->
                            <div class="flex justify-between">
                                <span class="text-gray-600">Upper Band Touch:</span>
                                <span class="font-medium">${signalsByType.upper_band_touch || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Lower Band Touch:</span>
                                <span class="font-medium">${signalsByType.lower_band_touch || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Middle Band Cross:</span>
                                <span class="font-medium">${signalsByType.middle_band_cross || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Bollinger Squeeze:</span>
                                <span class="font-medium">${signalsByType.squeeze || 0}</span>
                            </div>
                            <!-- RSI Strategy Signals -->
                            <div class="flex justify-between">
                                <span class="text-gray-600">Oversold Buy:</span>
                                <span class="font-medium">${signalsByType.oversold_buy || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Overbought Sell:</span>
                                <span class="font-medium">${signalsByType.overbought_sell || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">RSI Cross Oversold:</span>
                                <span class="font-medium">${signalsByType.rsi_cross_oversold || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">RSI Cross Overbought:</span>
                                <span class="font-medium">${signalsByType.rsi_cross_overbought || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">RSI Divergence Buy:</span>
                                <span class="font-medium">${signalsByType.rsi_divergence_buy || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">RSI Divergence Sell:</span>
                                <span class="font-medium">${signalsByType.rsi_divergence_sell || 0}</span>
                            </div>
                            <!-- MACD Strategy Signals -->
                            <div class="flex justify-between">
                                <span class="text-gray-600">MACD Cross Above:</span>
                                <span class="font-medium">${signalsByType.macd_cross_above || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">MACD Cross Below:</span>
                                <span class="font-medium">${signalsByType.macd_cross_below || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Histogram Positive:</span>
                                <span class="font-medium">${signalsByType.histogram_positive || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Histogram Negative:</span>
                                <span class="font-medium">${signalsByType.histogram_negative || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Histogram Cross Zero:</span>
                                <span class="font-medium">${signalsByType.histogram_cross_zero || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">MACD Divergence Buy:</span>
                                <span class="font-medium">${signalsByType.macd_divergence_buy || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">MACD Divergence Sell:</span>
                                <span class="font-medium">${signalsByType.macd_divergence_sell || 0}</span>
                            </div>
                            <!-- Stochastic Strategy Signals -->
                            <div class="flex justify-between">
                                <span class="text-gray-600">K Cross Above D:</span>
                                <span class="font-medium">${signalsByType.k_cross_above_d || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">K Cross Below D:</span>
                                <span class="font-medium">${signalsByType.k_cross_below_d || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">K Cross Oversold:</span>
                                <span class="font-medium">${signalsByType.k_cross_oversold || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">K Cross Overbought:</span>
                                <span class="font-medium">${signalsByType.k_cross_overbought || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">D Cross Oversold:</span>
                                <span class="font-medium">${signalsByType.d_cross_oversold || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">D Cross Overbought:</span>
                                <span class="font-medium">${signalsByType.d_cross_overbought || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Stochastic Divergence Buy:</span>
                                <span class="font-medium">${signalsByType.stochastic_divergence_buy || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Stochastic Divergence Sell:</span>
                                <span class="font-medium">${signalsByType.stochastic_divergence_sell || 0}</span>
                            </div>
                            <!-- DCA Strategy Signals -->
                            <div class="flex justify-between">
                                <span class="text-gray-600">DCA Buy:</span>
                                <span class="font-medium">${signalsByType.dca_buy || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">DCA Sell:</span>
                                <span class="font-medium">${signalsByType.dca_sell || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Strategy Buy:</span>
                                <span class="font-medium">${signalsByType.strategy_buy || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Strategy Sell:</span>
                                <span class="font-medium">${signalsByType.strategy_sell || 0}</span>
                            </div>
                            <!-- Buy and Hold Strategy Signals -->
                            <div class="flex justify-between">
                                <span class="text-gray-600">Buy and Hold Buy:</span>
                                <span class="font-medium">${signalsByType.buy_and_hold_buy || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Buy and Hold Sell:</span>
                                <span class="font-medium">${signalsByType.buy_and_hold_sell || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Profit Target Exit:</span>
                                <span class="font-medium">${signalsByType.profit_target_exit || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">End of Period Exit:</span>
                                <span class="font-medium">${signalsByType.end_of_period_exit || 0}</span>
                            </div>
                            <!-- ATR Strategy Signals -->
                            <div class="flex justify-between">
                                <span class="text-gray-600">ATR Breakout Buy:</span>
                                <span class="font-medium">${signalsByType.atr_breakout_buy || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">ATR Breakout Sell:</span>
                                <span class="font-medium">${signalsByType.atr_breakout_sell || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">ATR Stop Loss:</span>
                                <span class="font-medium">${signalsByType.atr_stop_loss || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">ATR Take Profit:</span>
                                <span class="font-medium">${signalsByType.atr_take_profit || 0}</span>
                            </div>
                            <!-- Fibonacci Strategy Signals -->
                            <div class="flex justify-between">
                                <span class="text-gray-600">Fibonacci Support Buy:</span>
                                <span class="font-medium">${signalsByType.fib_support_buy || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Fibonacci Resistance Sell:</span>
                                <span class="font-medium">${signalsByType.fib_resistance_sell || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Swing High Buy:</span>
                                <span class="font-medium">${signalsByType.swing_high_buy || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Swing Low Sell:</span>
                                <span class="font-medium">${signalsByType.swing_low_sell || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Confirmation Buy:</span>
                                <span class="font-medium">${signalsByType.confirmation_buy || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Confirmation Sell:</span>
                                <span class="font-medium">${signalsByType.confirmation_sell || 0}</span>
                            </div>
                            <!-- Order Book Strategy Signals -->
                            <div class="flex justify-between">
                                <span class="text-gray-600">Bid-Ask Squeeze:</span>
                                <span class="font-medium">${signalsByType.bid_ask_squeeze || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Volume Imbalance Buy:</span>
                                <span class="font-medium">${signalsByType.volume_imbalance_buy || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Volume Imbalance Sell:</span>
                                <span class="font-medium">${signalsByType.volume_imbalance_sell || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Large Trade Buy:</span>
                                <span class="font-medium">${signalsByType.large_trade_buy || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Large Trade Sell:</span>
                                <span class="font-medium">${signalsByType.large_trade_sell || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Order Book Pressure Buy:</span>
                                <span class="font-medium">${signalsByType.order_book_pressure_buy || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Order Book Pressure Sell:</span>
                                <span class="font-medium">${signalsByType.order_book_pressure_sell || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Spread Expansion Buy:</span>
                                <span class="font-medium">${signalsByType.spread_expansion_buy || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Spread Expansion Sell:</span>
                                <span class="font-medium">${signalsByType.spread_expansion_sell || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Volatility Expansion:</span>
                                <span class="font-medium">${signalsByType.volatility_expansion || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Volatility Contraction:</span>
                                <span class="font-medium">${signalsByType.volatility_contraction || 0}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">ATR Position Size:</span>
                                <span class="font-medium">${signalsByType.atr_position_size || 0}</span>
                            </div>
                            <!-- Common Signals -->
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
        
        // Stop order book auto-refresh when leaving live trading tab
        if (tabName !== 'live-trading') {
            this.stopOrderBookAutoRefresh();
        }
        
        // Load data for specific tabs if needed
        if (tabName === 'dashboard') {
            this.loadInitialData();
        } else if (tabName === 'data') {
            this.loadDataFeed();
        } else if (tabName === 'backtesting') {
            this.loadBacktestFilters();
            this.loadBacktestHistory();
        } else if (tabName === 'live-trading') {
            this.loadLiveTradingData();
        } else if (tabName === 'trading-history') {
            this.loadTradingHistory();
        }
    }

    clearBacktestResults() {
        const resultsContainer = document.getElementById('backtest-results');
        resultsContainer.classList.add('hidden');
        resultsContainer.innerHTML = '';
    }
    
    async loadLiveTradingData() {
        // Only load order book signals if trading is active
        if (this.liveTrading.isActive) {
            await this.loadOrderBookSignals();
            this.startOrderBookAutoRefresh();
        } else {
            // Show empty state when trading is not active
            this.updateOrderBookSignalsTable([]);
            this.updateOrderBookStatistics({
                total_analyzed: 0,
                active_signals: 0,
                last_updated: new Date().toISOString(),
                average_strength: 0,
                message: "Trading is not active. Configure your strategy and start trading to see live signals."
            });
        }
        
        // Load recent trades and positions
        await this.updateTradingStatusFromAPI();
        
        // Restore trading log from session if available
        await this.restoreTradingLog();
    }
    
    async restoreTradingLog() {
        const logContainer = document.getElementById('trading-log');
        if (!logContainer) return;
        
        // Clear existing log
        logContainer.innerHTML = '';
        
        // First, try to restore from localStorage (trading events)
        const logEvents = JSON.parse(localStorage.getItem('trading_log_events') || '[]');
        if (logEvents.length > 0) {
            // Add recent trading events to log
            logEvents.slice(-20).forEach(event => {
                const logEntry = document.createElement('div');
                logEntry.className = 'text-green-400';
                logEntry.innerHTML = `[${event.timestamp}] ${event.message}`;
                logContainer.appendChild(logEntry);
            });
        }
        
        // Then, try to load recent trades from the session
        if (this.sessionId) {
            try {
                const response = await fetch(`/api/trades/session/${this.sessionId}`);
                const data = await response.json();
                
                if (data.status === 'success' && data.trades && data.trades.length > 0) {
                    // Add separator if we have both events and trades
                    if (logEvents.length > 0) {
                        const separator = document.createElement('div');
                        separator.className = 'text-gray-500 text-sm my-2';
                        separator.innerHTML = '--- Recent trades ---';
                        logContainer.appendChild(separator);
                    }
                    
                    // Add recent trades to log
                    const recentTrades = data.trades.slice(0, 10); // Show last 10 trades
                    recentTrades.reverse().forEach(trade => {
                        const timestamp = new Date(trade.timestamp).toLocaleTimeString();
                        const logEntry = document.createElement('div');
                        logEntry.className = 'text-blue-400';
                        logEntry.innerHTML = `[${timestamp}] Trade: ${trade.action} ${trade.quantity} ${trade.symbol} at $${trade.price}`;
                        logContainer.appendChild(logEntry);
                    });
                }
            } catch (error) {
                console.error('Error restoring trading log from session:', error);
            }
        }
        
        // If no data to restore, show placeholder
        if (logContainer.children.length === 0) {
            const placeholder = document.createElement('div');
            placeholder.className = 'text-gray-500 text-sm';
            placeholder.innerHTML = 'Trading log will appear here...';
            logContainer.appendChild(placeholder);
        }
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

    toggleDCAOptions(enabled) {
        const dcaOptions = document.getElementById('dca-options');
        if (enabled) {
            dcaOptions.classList.remove('hidden');
        } else {
            dcaOptions.classList.add('hidden');
        }
    }

    toggleBuyHoldOptions(enabled) {
        const buyHoldOptions = document.getElementById('buy-hold-options');
        if (enabled) {
            buyHoldOptions.classList.remove('hidden');
        } else {
            buyHoldOptions.classList.add('hidden');
        }
    }

    toggleBuyHoldProfitTarget(exitCondition) {
        const profitTargetInput = document.getElementById('buy-hold-profit-target');
        if (exitCondition === 'profit_target') {
            profitTargetInput.disabled = false;
            profitTargetInput.required = true;
        } else {
            profitTargetInput.disabled = true;
            profitTargetInput.required = false;
            profitTargetInput.value = 0;
        }
    }
    
    toggleStopLossOptions(enabled) {
        const stopLossGroup = document.getElementById('stop-loss-group');
        if (enabled) {
            stopLossGroup.classList.remove('opacity-50');
            stopLossGroup.querySelector('input').disabled = false;
        } else {
            stopLossGroup.classList.add('opacity-50');
            stopLossGroup.querySelector('input').disabled = true;
        }
    }
    
    toggleTakeProfitOptions(enabled) {
        const takeProfitGroup = document.getElementById('take-profit-group');
        if (enabled) {
            takeProfitGroup.classList.remove('opacity-50');
            takeProfitGroup.querySelector('input').disabled = false;
        } else {
            takeProfitGroup.classList.add('opacity-50');
            takeProfitGroup.querySelector('input').disabled = true;
        }
    }

    async switchSymbol() {
        console.log(`Switching to symbol: ${this.currentSymbol}`);
        
        // Set flag to prevent real-time updates during switch
        this.isSwitchingSymbol = true;
        this.websocketSubscriptionsUpdated = false;
        this.hasRealTimeData = false; // Reset real-time data flag for new symbol
        
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
            
            // Force load data again after a short delay to ensure we have something
            // Only if we don't have real-time data yet
            setTimeout(async () => {
                if (!this.hasRealTimeData) {
                    console.log('Force loading data after symbol switch (no real-time data yet)...');
                    await this.loadCurrentPriceData();
                } else {
                    console.log('Skipping force load - real-time data already available');
                }
            }, 1000);
            
            // Reload chart data with rescaling
            await this.loadCandlesData();
            // Force chart rescale for new symbol
            this.updateCandlestickChart(true);
            
            // Update historical data
            await this.loadHistoricalData();
            
            // Wait a bit more to ensure WebSocket subscriptions are fully processed
            console.log('Waiting for WebSocket subscriptions to stabilize...');
            await new Promise(resolve => setTimeout(resolve, 2000));
            
            // Clear the switching flag BEFORE showing success notification
            // This allows WebSocket updates to start processing for the new symbol
            this.isSwitchingSymbol = false;
            this.websocketSubscriptionsUpdated = true; // Ensure this is set
            console.log('Symbol switch completed, real-time updates re-enabled');
            
            // Don't immediately load API data here - let the WebSocket data come through first
            // The timeouts below will handle loading API data if needed
            
            // Set multiple timeouts to ensure data is loaded
            // Only load if we don't have real-time data to prevent overriding
            setTimeout(() => {
                console.log('Checking data status after 2 seconds...', {
                    hasRealTimeData: this.hasRealTimeData,
                    currentPrice: document.getElementById('current-price').textContent,
                    volume: document.getElementById('volume-24h').textContent
                });
                if (!this.hasRealTimeData) {
                    console.log('No real-time data received after 2 seconds, loading from API...');
                    this.loadCurrentPriceData();
                } else {
                    console.log('Real-time data available, skipping API load');
                }
            }, 2000); // Check after 2 seconds
            
            setTimeout(() => {
                console.log('Checking data status after 5 seconds...', {
                    hasRealTimeData: this.hasRealTimeData,
                    currentPrice: document.getElementById('current-price').textContent,
                    volume: document.getElementById('volume-24h').textContent
                });
                if (!this.hasRealTimeData) {
                    console.log('No real-time data received after 5 seconds, loading from API...');
                    this.loadCurrentPriceData();
                } else {
                    console.log('Real-time data available, skipping API load');
                }
            }, 5000); // Check after 5 seconds
            
            setTimeout(() => {
                console.log('Checking data status after 10 seconds...', {
                    hasRealTimeData: this.hasRealTimeData,
                    currentPrice: document.getElementById('current-price').textContent,
                    volume: document.getElementById('volume-24h').textContent
                });
                if (!this.hasRealTimeData) {
                    console.log('No real-time data received after 10 seconds, loading from API...');
                    this.loadCurrentPriceData();
                } else {
                    console.log('Real-time data available, skipping API load');
                }
            }, 10000); // Check after 10 seconds
            
            // Show success notification
            this.showNotification(`Successfully switched to ${this.currentSymbol}`, 'success');
            
            // Final check to ensure data is displayed
            setTimeout(() => {
                const currentPrice = document.getElementById('current-price').textContent;
                const volume = document.getElementById('volume-24h').textContent;
                console.log('Final data check:', {
                    currentPrice,
                    volume,
                    hasRealTimeData: this.hasRealTimeData
                });
                
                // If we still don't have proper data AND we don't have real-time data, force load it
                if ((currentPrice === '$0.00' || volume === '0') && !this.hasRealTimeData) {
                    console.log('Data still showing default values and no real-time data, forcing reload...');
                    this.loadCurrentPriceData();
                } else if (this.hasRealTimeData) {
                    console.log('Real-time data available, skipping final reload');
                }
            }, 3000);
        } catch (error) {
            console.error('Error switching symbol:', error);
            this.showNotification(`Error switching to ${this.currentSymbol}: ${error.message}`, 'error');
            // Make sure to clear the flag even on error
            this.isSwitchingSymbol = false;
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
            // Mark that WebSocket subscriptions have been updated
            this.websocketSubscriptionsUpdated = true;
        } catch (error) {
            console.error('Error updating WebSocket subscriptions:', error);
            // If WebSocket operations fail, just reload the data without WebSocket updates
            console.log('Falling back to data-only mode for symbol switch');
            // Still mark as updated to allow data processing
            this.websocketSubscriptionsUpdated = true;
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
        // Refresh data summary every 10 seconds
        setInterval(() => {
            this.loadDataSummary();
        }, 10000);
        
        // Refresh subscriptions every 60 seconds
        setInterval(() => {
            this.loadSubscriptions();
        }, 60000);
    }

    // Backtest History Methods
    async loadBacktestFilters() {
        try {
            const response = await fetch('/api/backtest-filters');
            const data = await response.json();
            
            if (data.success) {
                this.populateSymbolFilter(data.symbols);
                this.populateStrategyFilter(data.strategies);
            } else {
                console.error('Failed to load backtest filters:', data);
            }
        } catch (error) {
            console.error('Error loading backtest filters:', error);
        }
    }

    populateSymbolFilter(symbols) {
        const symbolFilter = document.getElementById('history-symbol-filter');
        // Clear existing options except "All Symbols"
        symbolFilter.innerHTML = '<option value="">All Symbols</option>';
        
        // Add symbols from database
        symbols.forEach(symbol => {
            const option = document.createElement('option');
            option.value = symbol;
            option.textContent = symbol;
            symbolFilter.appendChild(option);
        });
    }

    populateStrategyFilter(strategies) {
        const strategyFilter = document.getElementById('history-strategy-filter');
        // Clear existing options except "All Strategies"
        strategyFilter.innerHTML = '<option value="">All Strategies</option>';
        
        // Add strategies from database
        strategies.forEach(strategy => {
            const option = document.createElement('option');
            option.value = strategy;
            option.textContent = strategy.toUpperCase();
            strategyFilter.appendChild(option);
        });
    }

    async loadBacktestHistory(offset = 0) {
        try {
            const symbolFilter = document.getElementById('history-symbol-filter').value;
            const strategyFilter = document.getElementById('history-strategy-filter').value;
            
            const params = new URLSearchParams({
                limit: this.historyLimit,
                offset: offset
            });
            
            if (symbolFilter) params.append('symbol', symbolFilter);
            if (strategyFilter) params.append('strategy_type', strategyFilter);
            
            const response = await fetch(`/api/backtest-history?${params}`);
            const data = await response.json();
            
            if (data.success) {
                this.currentHistoryOffset = offset;
                this.totalHistoryCount = data.total_count;
                this.displayBacktestHistory(data.backtests);
                this.displayHistoryStats(data.stats);
                this.updateHistoryPagination();
            } else {
                console.error('Failed to load backtest history:', data);
            }
        } catch (error) {
            console.error('Error loading backtest history:', error);
        }
    }

    displayBacktestHistory(backtests) {
        const tbody = document.getElementById('history-table-body');
        tbody.innerHTML = '';
        
        if (backtests.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="11" class="px-4 py-8 text-center text-gray-500">
                        No backtests found
                    </td>
                </tr>
            `;
            return;
        }
        
        backtests.forEach(backtest => {
            const row = document.createElement('tr');
            row.className = 'hover:bg-gray-50';
            
            // Safely access the results data
            const results = backtest.results || {};
            const result = results.result || {};
            
            const totalReturn = (result.total_return || 0) * 100; // Convert to percentage
            const tradesCount = result.total_trades || 0;
            const winRate = (result.win_rate || 0) * 100; // Convert to percentage
            const netProfit = result.net_profit || 0;
            const finalBalance = result.final_balance || 0;
            const timestamp = new Date(backtest.timestamp).toLocaleString();
            
            // Format strategy parameters
            const params = Object.entries(backtest.strategy_params || {})
                .map(([key, value]) => `${key}: ${value}`)
                .join(', ');
            
            // Format backtest parameters for display
            const backtestParams = backtest.backtest_params || {};
            const capital = backtestParams.initial_capital || 'N/A';
            const stopLoss = backtestParams.stop_loss || 'N/A';
            const takeProfit = backtestParams.take_profit || 'N/A';
            
            row.innerHTML = `
                <td class="px-4 py-3 text-sm text-gray-900">${backtest.id}</td>
                <td class="px-4 py-3 text-sm text-gray-900">${timestamp}</td>
                <td class="px-4 py-3 text-sm text-gray-900">${backtest.symbol}</td>
                <td class="px-4 py-3 text-sm text-gray-900">${backtest.strategy_type.toUpperCase()}</td>
                <td class="px-4 py-3 text-sm text-gray-500" title="${params}">${params.length > 30 ? params.substring(0, 30) + '...' : params}</td>
                <td class="px-4 py-3 text-sm ${totalReturn >= 0 ? 'text-green-600' : 'text-red-600'}">${totalReturn.toFixed(2)}%</td>
                <td class="px-4 py-3 text-sm text-gray-900">${tradesCount}</td>
                <td class="px-4 py-3 text-sm text-gray-900">${winRate.toFixed(1)}%</td>
                <td class="px-4 py-3 text-sm ${netProfit >= 0 ? 'text-green-600' : 'text-red-600'}">$${netProfit.toFixed(2)}</td>
                <td class="px-4 py-3 text-sm text-gray-900">$${finalBalance.toFixed(2)}</td>
                <td class="px-4 py-3 text-sm text-gray-900">
                    <button onclick="dashboard.viewBacktest(${backtest.id})" class="text-blue-600 hover:text-blue-800 mr-2" title="View Details">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button onclick="dashboard.deleteBacktest(${backtest.id})" class="text-red-600 hover:text-red-800" title="Delete">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            `;
            
            tbody.appendChild(row);
        });
    }

    displayHistoryStats(stats) {
        const statsContainer = document.getElementById('history-stats');
        
        // Calculate additional statistics
        const totalBacktests = stats.total_backtests || 0;
        const recentBacktests = stats.recent_backtests || 0;
        const strategyCount = Object.keys(stats.strategy_counts || {}).length;
        const symbolCount = Object.keys(stats.symbol_counts || {}).length;
        
        // Get most used strategy
        const mostUsedStrategy = Object.entries(stats.strategy_counts || {})
            .sort(([,a], [,b]) => b - a)[0];
        const mostUsedStrategyName = mostUsedStrategy ? mostUsedStrategy[0].toUpperCase() : 'N/A';
        const mostUsedStrategyCount = mostUsedStrategy ? mostUsedStrategy[1] : 0;
        
        // Get most tested symbol
        const mostTestedSymbol = Object.entries(stats.symbol_counts || {})
            .sort(([,a], [,b]) => b - a)[0];
        const mostTestedSymbolName = mostTestedSymbol ? mostTestedSymbol[0] : 'N/A';
        const mostTestedSymbolCount = mostTestedSymbol ? mostTestedSymbol[1] : 0;
        
        statsContainer.innerHTML = `
            <div class="bg-blue-50 p-4 rounded-lg">
                <div class="text-2xl font-bold text-blue-600">${totalBacktests}</div>
                <div class="text-sm text-blue-800">Total Backtests</div>
            </div>
            <div class="bg-green-50 p-4 rounded-lg">
                <div class="text-2xl font-bold text-green-600">${recentBacktests}</div>
                <div class="text-sm text-green-800">Last 7 Days</div>
            </div>
            <div class="bg-purple-50 p-4 rounded-lg">
                <div class="text-2xl font-bold text-purple-600">${strategyCount}</div>
                <div class="text-sm text-purple-800">Strategies Used</div>
                <div class="text-xs text-purple-600 mt-1">Most: ${mostUsedStrategyName} (${mostUsedStrategyCount})</div>
            </div>
            <div class="bg-orange-50 p-4 rounded-lg">
                <div class="text-2xl font-bold text-orange-600">${symbolCount}</div>
                <div class="text-sm text-orange-800">Symbols Tested</div>
                <div class="text-xs text-orange-600 mt-1">Most: ${mostTestedSymbolName} (${mostTestedSymbolCount})</div>
            </div>
        `;
    }

    updateHistoryPagination() {
        const showing = Math.min(this.currentHistoryOffset + this.historyLimit, this.totalHistoryCount);
        const total = this.totalHistoryCount;
        
        document.getElementById('history-showing').textContent = showing;
        document.getElementById('history-total').textContent = total;
        
        const prevBtn = document.getElementById('history-prev');
        const nextBtn = document.getElementById('history-next');
        
        prevBtn.disabled = this.currentHistoryOffset === 0;
        nextBtn.disabled = this.currentHistoryOffset + this.historyLimit >= total;
    }

    async viewBacktest(backtestId) {
        try {
            const response = await fetch(`/api/backtest/${backtestId}`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const backtest = await response.json();
            
            if (backtest && backtest.results) {
                // Transform the data structure to match what displayBacktestResults expects
                const resultData = {
                    success: true,
                    result: backtest.results.result,
                    trades: backtest.results.trades,
                    equity_curve: backtest.results.equity_curve,
                    backtest_key: `History #${backtest.id}`,
                    backtest_id: backtest.id
                };
                
                // Display the backtest results in the main results area
                this.displayBacktestResults(resultData);
                
                // Make sure the results container is visible
                const resultsContainer = document.getElementById('backtest-results');
                resultsContainer.classList.remove('hidden');
                
                // Scroll to results
                resultsContainer.scrollIntoView({ behavior: 'smooth' });
            } else {
                console.error('Invalid backtest data structure:', backtest);
                alert('Failed to load backtest details - invalid data structure');
            }
        } catch (error) {
            console.error('Error viewing backtest:', error);
            alert('Failed to load backtest details: ' + error.message);
        }
    }

    async deleteBacktest(backtestId) {
        if (!confirm('Are you sure you want to delete this backtest?')) {
            return;
        }
        
        try {
            const response = await fetch(`/api/backtest/${backtestId}`, {
                method: 'DELETE'
            });
            
            const result = await response.json();
            
            if (result.success) {
                // Reload history
                this.loadBacktestHistory(this.currentHistoryOffset);
            } else {
                alert('Failed to delete backtest');
            }
        } catch (error) {
            console.error('Error deleting backtest:', error);
            alert('Failed to delete backtest');
        }
    }

    async clearOldBacktests() {
        if (!confirm('Are you sure you want to clear backtests older than 30 days?')) {
            return;
        }
        
        try {
            // This would need a new API endpoint for clearing old backtests
            // For now, just show a message
            alert('Clear old backtests feature not yet implemented');
        } catch (error) {
            console.error('Error clearing old backtests:', error);
        }
    }

    // Asynchronous Trading Methods
    updateLoadingProgress(progress) {
        const progressContainer = document.getElementById('loading-progress');
        if (!progressContainer) {
            // Create progress container if it doesn't exist
            this.createLoadingProgressUI();
        }
        
        const progressBar = document.getElementById('loading-progress-bar');
        const progressText = document.getElementById('loading-progress-text');
        const statusText = document.getElementById('loading-status-text');
        
        if (progressBar && progressText && statusText) {
            const percentage = (progress.loaded / progress.total) * 100;
            progressBar.style.width = `${percentage}%`;
            progressText.textContent = `${progress.loaded}/${progress.total} symbols loaded`;
            
            if (progress.status === 'loading') {
                statusText.textContent = `Loading ${progress.remaining} remaining symbols...`;
                statusText.className = 'loading-status loading';
            } else if (progress.status === 'complete') {
                statusText.textContent = 'All symbols loaded successfully!';
                statusText.className = 'loading-status complete';
                this.liveTrading.asyncLoading = false;
            } else if (progress.status === 'error') {
                statusText.textContent = 'Error loading some symbols';
                statusText.className = 'loading-status error';
                this.liveTrading.asyncLoading = false;
            }
        }
    }

    createLoadingProgressUI() {
        // Create loading progress container
        const progressContainer = document.createElement('div');
        progressContainer.id = 'loading-progress';
        progressContainer.className = 'loading-progress-container';
        progressContainer.innerHTML = `
            <div class="loading-progress-header">
                <h4>Symbol Loading Progress</h4>
                <span id="loading-status-text" class="loading-status">Loading symbols...</span>
            </div>
            <div class="loading-progress-bar-container">
                <div id="loading-progress-bar" class="loading-progress-bar"></div>
            </div>
            <div class="loading-progress-text">
                <span id="loading-progress-text">0/0 symbols loaded</span>
            </div>
        `;
        
        // Insert after trading controls
        const tradingControls = document.getElementById('trading-controls');
        if (tradingControls && tradingControls.parentNode) {
            tradingControls.parentNode.insertBefore(progressContainer, tradingControls.nextSibling);
        }
    }

    async startLoadingProgressMonitoring() {
        if (this.loadingProgressInterval) {
            clearInterval(this.loadingProgressInterval);
        }
        
        this.loadingProgressInterval = setInterval(async () => {
            if (!this.liveTrading.asyncLoading) {
                clearInterval(this.loadingProgressInterval);
                return;
            }
            
            try {
                const response = await fetch('/api/async-trading/loading-status');
                const data = await response.json();
                
                if (data.loading_progress) {
                    this.updateLoadingProgress(data.loading_progress);
                    
                    // Update strategy symbols if they've changed
                    if (this.liveTrading.strategy && data.current_symbols) {
                        this.liveTrading.strategy.symbols = data.current_symbols;
                        this.liveTrading.strategy.loadingProgress = data.loading_progress;
                    }
                    
                    // Update portfolio status to refresh open positions and trading history
                    await this.updateTradingStatusFromAPI();
                    
                    // Reload order book signals continuously during loading (only if trading is active)
                    if (this.liveTrading.isActive) {
                        if (data.loading_progress.status === 'loading') {
                            // Refresh orderbook signals every time we check loading progress
                            await this.loadOrderBookSignals();
                        } else if (data.loading_progress.status === 'complete') {
                            // Switch back to normal refresh rate when loading is complete
                            this.startOrderBookAutoRefresh();
                        }
                    }
                }
            } catch (error) {
                console.error('Error monitoring loading progress:', error);
            }
        }, 2000); // Check every 2 seconds
    }

    stopLoadingProgressMonitoring() {
        if (this.loadingProgressInterval) {
            clearInterval(this.loadingProgressInterval);
            this.loadingProgressInterval = null;
        }
    }

    async addSymbolsToTrading(symbols) {
        try {
            const response = await fetch('/api/async-trading/add-symbols', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    symbols: symbols
                })
            });

            const data = await response.json();
            
            if (data.status === 'success') {
                this.logTradingEvent(`Added ${data.added_symbols.length} symbols to trading: ${data.added_symbols.join(', ')}`);
                
                // Update strategy symbols
                if (this.liveTrading.strategy) {
                    this.liveTrading.strategy.symbols = data.current_symbols;
                    this.liveTrading.strategy.loadingProgress = data.loading_progress;
                }
                
                // Reload order book signals (only if trading is active)
                if (this.liveTrading.isActive) {
                    await this.loadOrderBookSignals();
                }
                
                return true;
            } else {
                this.logTradingEvent(`Failed to add symbols: ${data.error}`);
                return false;
            }
        } catch (error) {
            this.logTradingEvent(`Error adding symbols: ${error.message}`);
            return false;
        }
    }

    // WebSocket Symbol Loading Handlers
    async handleSymbolLoadingProgress(data) {
        if (data.loading_progress) {
            this.updateLoadingProgress(data.loading_progress);
            
            // Update strategy symbols if they've changed
            if (this.liveTrading.strategy && data.current_symbols) {
                this.liveTrading.strategy.symbols = data.current_symbols;
                this.liveTrading.strategy.loadingProgress = data.loading_progress;
            }
            
            // Update portfolio status to refresh open positions and trading history
            await this.updateTradingStatusFromAPI();
            
            // Always reload order book signals when symbols change (only if trading is active)
            if (this.liveTrading.isActive) {
                await this.loadOrderBookSignals();
            }
        }
    }

    async handleSymbolLoadingComplete(data) {
        if (data.loading_progress) {
            this.updateLoadingProgress(data.loading_progress);
            
            // Update strategy symbols
            if (this.liveTrading.strategy && data.current_symbols) {
                this.liveTrading.strategy.symbols = data.current_symbols;
                this.liveTrading.strategy.loadingProgress = data.loading_progress;
            }
            
            // Update portfolio status to refresh open positions and trading history
            await this.updateTradingStatusFromAPI();
            
            // Final reload of order book signals (only if trading is active)
            if (this.liveTrading.isActive) {
                await this.loadOrderBookSignals();
            }
            
            // Log completion message
            this.logTradingEvent(data.message || 'All symbols loaded successfully!');
        }
    }

    async handleSymbolLoadingError(data) {
        if (data.loading_progress) {
            this.updateLoadingProgress(data.loading_progress);
        }
        
        // Update portfolio status even on error
        await this.updateTradingStatusFromAPI();
        
        // Reload order book signals even on error (only if trading is active)
        if (this.liveTrading.isActive) {
            await this.loadOrderBookSignals();
        }
        
        // Log error message
        this.logTradingEvent(data.message || 'Error loading some symbols');
        
        if (data.error) {
            console.error('Symbol loading error:', data.error);
        }
    }

    // Trading History Methods
    async loadTradingHistory() {
        console.log('Loading trading history...');
        try {
            // Load trading metrics
            await this.loadTradingMetrics();
            
            // Load trading history table
            await this.loadTradingHistoryTable();
            
            // Load charts
            await this.loadTradingHistoryCharts();
            
            // Setup event listeners
            this.setupTradingHistoryEventListeners();
            
        } catch (error) {
            console.error('Error loading trading history:', error);
        }
    }

    async loadTradingMetrics() {
        try {
            const response = await fetch('/api/trading/metrics');
            const data = await response.json();
            
            if (data.error) {
                console.error('Error loading trading metrics:', data.error);
                return;
            }
            
            // Update metrics display
            document.getElementById('total-trades').textContent = data.total_trades || 0;
            document.getElementById('total-pnl').textContent = `$${(data.total_pnl || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            document.getElementById('win-rate').textContent = `${(data.win_rate || 0).toFixed(1)}%`;
            document.getElementById('avg-trade-size').textContent = `$${(data.avg_trade_size || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            
            // Update P&L color
            const pnlElement = document.getElementById('total-pnl');
            if (data.total_pnl > 0) {
                pnlElement.className = 'text-2xl font-bold text-green-600';
            } else if (data.total_pnl < 0) {
                pnlElement.className = 'text-2xl font-bold text-red-600';
            } else {
                pnlElement.className = 'text-2xl font-bold text-gray-900';
            }
            
        } catch (error) {
            console.error('Error loading trading metrics:', error);
        }
    }

    async loadTradingHistoryTable(page = 1, perPage = 25) {
        try {
            const response = await fetch(`/api/trading/history/all?limit=${perPage}&offset=${(page - 1) * perPage}`);
            const data = await response.json();
            
            if (data.error) {
                console.error('Error loading trading history:', data.error);
                return;
            }
            
            // Update pagination info
            const totalPages = Math.ceil(data.total_count / perPage);
            document.getElementById('trading-history-page-info').textContent = `Page ${page} of ${totalPages}`;
            
            // Update pagination buttons
            document.getElementById('trading-history-prev-page').disabled = page <= 1;
            document.getElementById('trading-history-next-page').disabled = page >= totalPages;
            
            // Populate table
            this.populateTradingHistoryTable(data.trades);
            
        } catch (error) {
            console.error('Error loading trading history table:', error);
        }
    }

    populateTradingHistoryTable(trades) {
        const tbody = document.getElementById('trading-history-table-body');
        tbody.innerHTML = '';
        
        if (!trades || trades.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" class="px-6 py-4 text-center text-gray-500">No trades found</td></tr>';
            return;
        }
        
        trades.forEach(trade => {
            const row = document.createElement('tr');
            row.className = 'hover:bg-gray-50';
            
            const timestamp = new Date(trade.timestamp).toLocaleString();
            const pnl = trade.pnl || 0;
            const pnlClass = pnl > 0 ? 'text-green-600' : pnl < 0 ? 'text-red-600' : 'text-gray-600';
            
            row.innerHTML = `
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${timestamp}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${trade.symbol || 'N/A'}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    <span class="px-2 py-1 text-xs font-semibold rounded-full ${trade.side === 'buy' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                        ${trade.side || 'N/A'}
                    </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${(trade.quantity || 0).toFixed(6)}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">$${(trade.price || 0).toFixed(2)}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm ${pnlClass}">$${pnl.toFixed(2)}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">$${(trade.fees || 0).toFixed(2)}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${trade.strategy_type || 'N/A'}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${trade.reason || 'N/A'}</td>
            `;
            
            tbody.appendChild(row);
        });
    }

    async loadTradingHistoryCharts() {
        try {
            // Load strategy performance chart
            await this.loadStrategyPerformanceChart();
            
            // Load daily P&L chart
            await this.loadDailyPnlChart();
            
        } catch (error) {
            console.error('Error loading trading history charts:', error);
        }
    }

    async loadStrategyPerformanceChart() {
        try {
            const response = await fetch('/api/trading/metrics');
            const data = await response.json();
            
            if (data.error || !data.strategy_performance) {
                console.error('Error loading strategy performance:', data.error);
                return;
            }
            
            const strategies = Object.keys(data.strategy_performance);
            const pnlData = strategies.map(strategy => data.strategy_performance[strategy].pnl);
            const tradeCounts = strategies.map(strategy => data.strategy_performance[strategy].trades);
            
            const ctx = document.getElementById('strategy-performance-chart').getContext('2d');
            
            // Destroy existing chart if it exists
            if (this.charts.strategyPerformance) {
                this.charts.strategyPerformance.destroy();
            }
            
            this.charts.strategyPerformance = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: strategies,
                    datasets: [{
                        data: pnlData,
                        backgroundColor: [
                            '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#06B6D4'
                        ],
                        borderWidth: 2,
                        borderColor: '#fff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom'
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const strategy = context.label;
                                    const pnl = context.parsed;
                                    const trades = tradeCounts[context.dataIndex];
                                    return `${strategy}: $${pnl.toFixed(2)} (${trades} trades)`;
                                }
                            }
                        }
                    }
                }
            });
            
        } catch (error) {
            console.error('Error loading strategy performance chart:', error);
        }
    }

    async loadDailyPnlChart() {
        try {
            const response = await fetch('/api/trading/metrics');
            const data = await response.json();
            
            if (data.error || !data.daily_pnl) {
                console.error('Error loading daily P&L data:', data.error);
                return;
            }
            
            const dates = data.daily_pnl.map(day => day.date).reverse();
            const pnlValues = data.daily_pnl.map(day => day.pnl).reverse();
            
            const ctx = document.getElementById('daily-pnl-chart').getContext('2d');
            
            // Destroy existing chart if it exists
            if (this.charts.dailyPnl) {
                this.charts.dailyPnl.destroy();
            }
            
            this.charts.dailyPnl = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: dates,
                    datasets: [{
                        label: 'Daily P&L',
                        data: pnlValues,
                        borderColor: '#3B82F6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: 'rgba(0, 0, 0, 0.1)'
                            }
                        },
                        x: {
                            grid: {
                                color: 'rgba(0, 0, 0, 0.1)'
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: false
                        }
                    }
                }
            });
            
        } catch (error) {
            console.error('Error loading daily P&L chart:', error);
        }
    }

    setupTradingHistoryEventListeners() {
        // Refresh button
        document.getElementById('refresh-trading-history')?.addEventListener('click', () => {
            this.loadTradingHistory();
        });
        
        // Export button
        document.getElementById('export-trading-history')?.addEventListener('click', () => {
            this.exportTradingHistory();
        });
        
        // Pagination controls
        document.getElementById('trading-history-prev-page')?.addEventListener('click', () => {
            const currentPage = parseInt(document.getElementById('trading-history-page-info').textContent.split(' ')[1]);
            const perPage = parseInt(document.getElementById('history-per-page').value);
            if (currentPage > 1) {
                this.loadTradingHistoryTable(currentPage - 1, perPage);
            }
        });
        
        document.getElementById('trading-history-next-page')?.addEventListener('click', () => {
            const pageInfo = document.getElementById('trading-history-page-info').textContent;
            const currentPage = parseInt(pageInfo.split(' ')[1]);
            const totalPages = parseInt(pageInfo.split(' ')[3]);
            const perPage = parseInt(document.getElementById('history-per-page').value);
            if (currentPage < totalPages) {
                this.loadTradingHistoryTable(currentPage + 1, perPage);
            }
        });
        
        // Per page selector
        document.getElementById('history-per-page')?.addEventListener('change', (e) => {
            this.loadTradingHistoryTable(1, parseInt(e.target.value));
        });
    }

    async exportTradingHistory() {
        try {
            const response = await fetch('/api/trading/history/all?limit=10000');
            const data = await response.json();
            
            if (data.error) {
                console.error('Error exporting trading history:', data.error);
                return;
            }
            
            // Convert to CSV
            const csv = this.convertTradesToCSV(data.trades);
            
            // Download CSV
            const blob = new Blob([csv], { type: 'text/csv' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `trading_history_${new Date().toISOString().split('T')[0]}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            
        } catch (error) {
            console.error('Error exporting trading history:', error);
        }
    }

    convertTradesToCSV(trades) {
        const headers = ['Timestamp', 'Symbol', 'Side', 'Quantity', 'Price', 'P&L', 'Fees', 'Strategy', 'Reason'];
        const csvRows = [headers.join(',')];
        
        trades.forEach(trade => {
            const row = [
                trade.timestamp || '',
                trade.symbol || '',
                trade.side || '',
                trade.quantity || 0,
                trade.price || 0,
                trade.pnl || 0,
                trade.fees || 0,
                trade.strategy_type || '',
                trade.reason || ''
            ];
            csvRows.push(row.join(','));
        });
        
        return csvRows.join('\n');
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new EnhancedTradingDashboard();
});
