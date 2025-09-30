/**
 * Enhanced Trading Dashboard - Modular Version (Optimized)
 * Main dashboard class that orchestrates all modules with performance optimizations
 */
import { TradingStats } from './modules/TradingStats.js';
import { SimulatedTrading } from './modules/SimulatedTrading.js';
import { StrategyConfiguration } from './modules/StrategyConfiguration.js';
import { UIUtils } from './modules/UIUtils.js';
import { DataManager } from './modules/DataManager.js';
import { Pagination } from './modules/Pagination.js';
import { LiveTrading } from './modules/LiveTrading.js';
import { RealTimeData } from './modules/RealTimeData.js';
import { PerformanceMonitor } from './modules/PerformanceMonitor.js';

// Performance optimization utilities
class PerformanceOptimizer {
    static debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    static throttle(func, limit) {
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

    static batchDOMUpdates(updates) {
        requestAnimationFrame(() => {
            updates.forEach(update => update());
        });
    }
}

class EnhancedTradingDashboard {
    constructor() {
        // Initialize state
        this.tradingStats = {};
        this.simulatedTradingStats = {};
        this.liveTrading = {
            isActive: false,
            mode: 'simulated',
            symbolMode: 'single',
            strategy: null,
            symbols: [],
            positions: []
        };

        // Backtest history properties
        this.backtestHistory = {
            page: 1,
            limit: 50,
            totalPages: 0,
            backtests: []
        };


        // Reset inputs to defaults on page load
        this.resetInputsToDefaults();

        // Trading stats
        this.tradingStats = {
            totalPnl: 0,
            totalFees: 0,
            netPnl: 0,
            winRate: 0,
            totalTrades: 0,
            winningTrades: 0,
            losingTrades: 0,
            avgWin: 0,
            avgLoss: 0,
            bestTrade: 0,
            worstTrade: 0,
            profitFactor: 0,
            sharpeRatio: 0,
            maxDrawdown: 0,
            totalVolume: 0,
            avgTradeSize: 0,
            tradesToday: 0,
            lastTradeTime: null
        };

        // Simulated trading stats
        this.simulatedTradingStats = {
            totalPnl: 0,
            totalFees: 0,
            netPnl: 0,
            winRate: 0,
            totalTrades: 0,
            winningTrades: 0,
            losingTrades: 0,
            avgWin: 0,
            avgLoss: 0,
            bestTrade: 0,
            worstTrade: 0,
            profitFactor: 0,
            sharpeRatio: 0,
            riskAdjustedReturn: 0,
            totalVolume: 0,
            avgTradeSize: 0,
            activePositions: 0,
            grossProfit: 0,
            grossLoss: 0
        };

        // Strategy configuration visibility state
        this.strategyConfigHidden = false;

        // Trading history pagination state
        this.tradingHistoryPage = 1;
        this.tradingHistoryLimit = 50;

        // Order book signals pagination state
        this.orderBookSignalsPage = 1;
        this.orderBookSignalsLimit = 50;

        // Open positions pagination state
        this.positionsPage = 1;
        this.positionsLimit = 50;

        // Initialize modules
        this.dataManager = new DataManager(this);
        this.uiUtils = new UIUtils(this);
        this.tradingStats = new TradingStats(this);
        this.simulatedTrading = new SimulatedTrading(this);
        this.strategyConfig = new StrategyConfiguration(this);
        this.pagination = new Pagination(this);
        this.liveTrading = new LiveTrading(this);
        this.realTimeData = new RealTimeData(this);
        this.performanceMonitor = new PerformanceMonitor(this);

        // Initialize the dashboard
        this.init();
    }

    resetInputsToDefaults() {
        // Set default values for form inputs
        const defaults = {
            'trading-mode': 'simulated',
            'trading-symbol-mode': 'single',
            'live-trading-symbol-mode': 'single',
            'live-strategy-type': 'orderbook',
            'universe-type': 'all_usd',
            'live-trading-symbol': 'BTC-USD',
            'universe-max-size': '324', // Default to all USD pairs count
            'universe-position-size': '1.0',
            'universe-max-positions': '95'
        };

        Object.entries(defaults).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) {
                if (element.type === 'radio') {
                    element.checked = true;
                } else {
                    element.value = value;
                }
            }
        });
    }

    async init() {
        // Performance optimization: Batch initialization
        const initTasks = [
            () => this.pagination.setupTradingHistoryPagination(),
            () => this.pagination.setupOrderBookSignalsPagination(),
            () => this.pagination.setupPositionsPagination(),
            () => this.pagination.setupBacktestHistoryPagination(),
            () => this.setupAccountsListToggle(),
            () => this.setupPositionsListToggle(),
            () => this.setupStrategyConfigToggle(),
            () => this.setupTestAPIStatusButton(),
            () => this.setupTabSwitching(),
            () => this.setupStrategyTypeListeners()
        ];

        // Execute setup tasks in parallel
        PerformanceOptimizer.batchDOMUpdates(initTasks);

        // Optimized data loading with batching
        requestAnimationFrame(async () => {
            try {
                // Initialize real-time data and charts
                this.realTimeData.init();

                // Batch load critical data
                await this.loadInitialDataBatch();

                // Restore strategy configuration visibility state
                this.strategyConfig.restoreStrategyConfigState();

                // Setup live trading
                this.liveTrading.setupLiveTrading();

                // Initialize symbol mode UI
                this.uiUtils.updateSymbolModeUI();

                // Initialize universe selection
                this.uiUtils.updateUniverseTypeUI();

                // Strategy parameters will be loaded when Live Trading tab is first activated
                // This is because the tab content is not in DOM until activated

                // Start trading stats updates with throttling
                this.tradingStats.startTradingStatsUpdates();
            } catch (error) {
                console.error('Error during initialization:', error);
            }
        });
    }

    async loadInitialDataBatch() {
        // Batch load all critical data in parallel
        const dataPromises = [
            this.tradingStats.loadTradingStats(),
            this.pagination.loadTradingHistory(),
            this.dataManager.loadProducts()
        ];

        try {
            await Promise.allSettled(dataPromises);
        } catch (error) {
            console.error('Error loading initial data batch:', error);
        }
    }

    loadInitialStrategyParameters() {
        // Use a more robust approach to ensure DOM elements are available
        const waitForElement = (selector, maxAttempts = 20, interval = 50) => {
            return new Promise((resolve, reject) => {
                let attempts = 0;
                const checkElement = () => {
                    const element = document.querySelector(selector);
                    if (element) {
                        resolve(element);
                    } else if (attempts < maxAttempts) {
                        attempts++;
                        setTimeout(checkElement, interval);
                    } else {
                        reject(new Error(`Element ${selector} not found after ${maxAttempts} attempts`));
                    }
                };
                checkElement();
            });
        };

        // Wait for the strategy type select element to be available
        waitForElement('#live-strategy-type')
            .then((strategySelect) => {
                const initialStrategyType = strategySelect.value || 'orderbook';
                console.log('Loading initial strategy parameters for:', initialStrategyType);
                this.strategyConfig.loadStrategyParameters(initialStrategyType);
            })
            .catch((error) => {
                console.warn('Strategy type element not found, using default:', error.message);
                // Fallback: load with default strategy type
                this.strategyConfig.loadStrategyParameters('orderbook');
            });
    }

    setupAccountsListToggle() {
        const accountsToggle = document.getElementById('toggle-accounts');
        const accountsList = document.getElementById('accounts-list');

        if (accountsToggle && accountsList) {
            accountsToggle.addEventListener('click', () => {
                const isHidden = accountsList.style.display === 'none';
                accountsList.style.display = isHidden ? 'block' : 'none';
                accountsToggle.textContent = isHidden ? 'Hide Accounts' : 'Show Accounts';
            });
        }
    }

    setupPositionsListToggle() {
        const positionsToggle = document.getElementById('toggle-positions');
        const positionsList = document.getElementById('positions-list');

        if (positionsToggle && positionsList) {
            positionsToggle.addEventListener('click', () => {
                const isHidden = positionsList.style.display === 'none';
                positionsList.style.display = isHidden ? 'block' : 'none';
                positionsToggle.textContent = isHidden ? 'Hide Positions' : 'Show Positions';
            });
        }
    }

    setupStrategyConfigToggle() {
        const hideStrategyBtn = document.getElementById('hide-strategy-config');
        const showStrategyBtn = document.getElementById('show-strategy-section');

        if (hideStrategyBtn) {
            hideStrategyBtn.addEventListener('click', () => {
                this.strategyConfig.hideStrategyConfiguration();
            });
        }

        if (showStrategyBtn) {
            showStrategyBtn.addEventListener('click', () => {
                this.strategyConfig.showStrategyConfiguration();
            });
        }
    }

    setupTestAPIStatusButton() {
        const testAPIBtn = document.getElementById('test-api-status');
        if (testAPIBtn) {
            testAPIBtn.addEventListener('click', async () => {
                try {
                    const response = await fetch('/api/status');
                    const data = await response.json();
                    
                    if (data.status === 'success') {
                        this.uiUtils.showMessage('API is working correctly', 'success');
                    } else {
                        this.uiUtils.showMessage('API error: ' + data.error, 'error');
                    }
                } catch (error) {
                    this.uiUtils.showMessage('API connection failed: ' + error.message, 'error');
                }
            });
        }

        // Setup performance report button
        const performanceBtn = document.getElementById('performance-report');
        if (performanceBtn) {
            performanceBtn.addEventListener('click', () => {
                this.logPerformanceReport();
            });
        }
    }

    setupTabSwitching() {
        // Get all tab buttons
        const tabButtons = document.querySelectorAll('.tab-button');
        
        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const tabName = button.id.replace('-tab', '');
                this.switchTab(tabName);
            });
        });
    }

    setupStrategyTypeListeners() {
        // Strategy type change listeners
        document.getElementById('live-strategy-type')?.addEventListener('change', (e) => {
            this.strategyConfig.loadStrategyParameters(e.target.value);
        });

        // Note: Universe strategy type is now handled by the main live-strategy-type selector
    }

    // Tab switching functionality
    switchTab(tabName) {
        // Hide all tab contents
        const tabContents = document.querySelectorAll('.tab-content');
        tabContents.forEach(content => {
            content.classList.add('hidden');
        });

        // Remove active class from all tabs
        const tabs = document.querySelectorAll('.tab-button');
        tabs.forEach(tab => {
            tab.classList.remove('active');
        });

        // Show selected tab content
        const selectedTabContent = document.getElementById(`${tabName}-content`);
        if (selectedTabContent) {
            selectedTabContent.classList.remove('hidden');
        }

        // Add active class to selected tab
        const selectedTab = document.getElementById(`${tabName}-tab`);
        if (selectedTab) {
            selectedTab.classList.add('active');
        }

        // Load data for specific tabs
        if (tabName === 'live-trading') {
            this.liveTrading.loadLiveTradingData();
            // Load strategy parameters when Live Trading tab is first activated
            this.loadInitialStrategyParameters();
        } else if (tabName === 'trading-history') {
            this.pagination.loadTradingHistory();
        } else if (tabName === 'orderbook-signals') {
            this.pagination.loadOrderBookSignals();
        } else if (tabName === 'positions') {
            this.pagination.loadPositions();
        } else if (tabName === 'backtest-history') {
            this.pagination.loadBacktestHistory();
        }
    }

    // Cleanup method
    destroy() {
        this.tradingStats.stopTradingStatsUpdates();
        this.liveTrading.stopOrderBookAutoRefresh();
        this.realTimeData.destroy();
        this.dataManager.clearCache();
        this.performanceMonitor.destroy();
    }

    // Performance reporting
    getPerformanceReport() {
        return this.performanceMonitor.getPerformanceReport();
    }

    logPerformanceReport() {
        this.performanceMonitor.logPerformanceReport();
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new EnhancedTradingDashboard();
});

// Export for module usage
export default EnhancedTradingDashboard;
