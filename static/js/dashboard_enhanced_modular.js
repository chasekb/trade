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
            'universe-max-size': '50', // Safer default to avoid heavy initial requests
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

                // Initialize trading mode UI visibility (simulated vs live stats)
                this.uiUtils.updateTradingModeUI();

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
            // Load live trading stats
            this.liveTrading.loadLiveTradingStats();
            // Load strategy parameters when Live Trading tab is first activated
            this.loadInitialStrategyParameters();
        } else if (tabName === 'trading-history') {
            this.pagination.loadTradingHistory();
            this.pagination.loadPositions();
        } else if (tabName === 'orderbook-signals') {
            this.pagination.loadOrderBookSignals();
        } else if (tabName === 'backtest-history') {
            this.pagination.loadBacktestHistory();
        } else if (tabName === 'ml-analytics') {
            this.loadMLAlyticsData();
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

    // ML Analytics methods
    async loadMLAlyticsData() {
        console.log('Loading ML analytics data...');
        await this.loadMLDashboardData();
        this.setupMLEventListeners();
    }

    async loadMLDashboardData() {
        try {
            const response = await fetch('/api/ml/dashboard');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            this.updateMLDashboard(data);
        } catch (error) {
            console.error('Error loading ML dashboard data:', error);
            this.showMLErrorStatus('Failed to load ML data: ' + error.message);
        }
    }

    updateMLDashboard(data) {
        // Update status cards
        this.updateMLStatusCards(data.status || {});
        this.updateMLPerformanceData(data.performance || {});
        this.updateMLFeatureImportance(data.feature_importance || {});
    }

    updateMLStatusCards(status) {
        // Update model status
        const modelStatusElement = document.getElementById('ml-model-status');
        const modelIconElement = document.getElementById('ml-model-status-icon');
        const lastUpdatedElement = document.getElementById('ml-model-last-updated');

        if (modelStatusElement) {
            modelStatusElement.textContent = status.is_trained ? 'Trained' : 'Not Trained';
            modelStatusElement.className = status.is_trained ? 'text-2xl font-bold text-green-600' : 'text-2xl font-bold text-red-600';
        }

        if (modelIconElement) {
            modelIconElement.className = status.is_trained ? 'fas fa-brain text-green-500 text-2xl' : 'fas fa-brain text-red-500 text-2xl';
        }

        if (lastUpdatedElement && status.last_updated) {
            lastUpdatedElement.textContent = new Date(status.last_updated).toLocaleString();
        }

        // Update vector DB status
        const vectorStatusElement = document.getElementById('ml-vector-db-status');
        if (vectorStatusElement) {
            vectorStatusElement.textContent = 'Connected';
        }

        // Update collection count (placeholder)
        const collectionElement = document.getElementById('ml-collection-count');
        if (collectionElement) {
            collectionElement.textContent = '1';
        }
    }

    updateMLPerformanceData(performance) {
        // Update performance chart
        this.updateMLPerformanceChart(performance);

        // Update performance table
        this.updateMLPerformanceTable(performance);
    }

    updateMLPerformanceChart(performance) {
        const performanceChartElement = document.getElementById('ml-performance-chart');

        // If Chart.js is not available, skip chart updates
        if (typeof Chart === 'undefined') {
            console.warn('Chart.js not available for ML performance chart');
            return;
        }

        const chartData = {
            labels: ['R² Score', 'RMSE', 'Profit Factor', 'Sharpe Ratio', 'Win Rate'],
            datasets: [{
                label: 'Performance Metrics',
                data: [
                    performance.r2_score || 0,
                    performance.rmse || 0,
                    performance.profit_factor || 0,
                    performance.sharpe_ratio || 0,
                    (performance.win_rate || 0) * 100
                ],
                backgroundColor: [
                    'rgba(54, 162, 235, 0.6)',
                    'rgba(255, 99, 132, 0.6)',
                    'rgba(75, 192, 192, 0.6)',
                    'rgba(255, 205, 86, 0.6)',
                    'rgba(153, 102, 255, 0.6)'
                ],
                borderColor: [
                    'rgba(54, 162, 235, 1)',
                    'rgba(255, 99, 132, 1)',
                    'rgba(75, 192, 192, 1)',
                    'rgba(255, 205, 86, 1)',
                    'rgba(153, 102, 255, 1)'
                ],
                borderWidth: 1
            }]
        };

        const chartOptions = {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        };

        if (this.mlPerformanceChart) {
            this.mlPerformanceChart.destroy();
        }

        try {
            this.mlPerformanceChart = new Chart(performanceChartElement, {
                type: 'bar',
                data: chartData,
                options: chartOptions
            });
        } catch (error) {
            console.error('Error creating ML performance chart:', error);
            if (performanceChartElement) {
                performanceChartElement.innerHTML = '<div class="flex items-center justify-center h-full text-gray-500"><i class="fas fa-chart-bar text-4xl mb-4"></i><p>Chart unavailable</p></div>';
            }
        }
    }

    updateMLFeatureImportance(featureImportance) {
        const featureChartElement = document.getElementById('ml-feature-importance-chart');

        // If Chart.js is not available, skip chart updates
        if (typeof Chart === 'undefined') {
            console.warn('Chart.js not available for ML feature importance chart');
            return;
        }

        const features = Object.keys(featureImportance);
        const importances = Object.values(featureImportance);

        const chartData = {
            labels: features,
            datasets: [{
                label: 'Feature Importance',
                data: importances,
                backgroundColor: 'rgba(54, 162, 235, 0.6)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1
            }]
        };

        const chartOptions = {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    beginAtZero: true
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        };

        if (this.mlFeatureImportanceChart) {
            this.mlFeatureImportanceChart.destroy();
        }

        try {
            this.mlFeatureImportanceChart = new Chart(featureChartElement, {
                type: 'bar',
                data: chartData,
                options: chartOptions
            });
        } catch (error) {
            console.error('Error creating ML feature importance chart:', error);
            if (featureChartElement) {
                featureChartElement.innerHTML = '<div class="flex items-center justify-center h-full text-gray-500"><i class="fas fa-sliders-h text-4xl mb-4"></i><p>Chart unavailable</p></div>';
            }
        }
    }

    updateMLPerformanceTable(performance) {
        const tbody = document.getElementById('ml-performance-table-body');
        const statusElement = document.getElementById('ml-performance-table-status');

        if (!tbody) {
            console.warn('ML performance table body not found');
            return;
        }

        // Define performance metrics to display
        const metrics = [
            {
                name: 'R² Score',
                value: performance.r2_score,
                benchmark: '>0.7',
                format: (val) => val?.toFixed(3) || '0.000'
            },
            {
                name: 'RMSE',
                value: performance.rmse,
                benchmark: '<0.05',
                format: (val) => val?.toFixed(4) || '0.0000'
            },
            {
                name: 'Profit Factor',
                value: performance.profit_factor,
                benchmark: '>1.2',
                format: (val) => val?.toFixed(2) || '0.00'
            },
            {
                name: 'Sharpe Ratio',
                value: performance.sharpe_ratio,
                benchmark: '>1.0',
                format: (val) => val?.toFixed(2) || '0.00'
            },
            {
                name: 'Win Rate',
                value: performance.win_rate,
                benchmark: '>55%',
                format: (val) => val ? (val * 100).toFixed(1) + '%' : '0.0%'
            }
        ];

        tbody.innerHTML = '';

        metrics.forEach(metric => {
            const row = document.createElement('tr');

            const value = metric.value !== undefined ? metric.value : 0;
            const formattedValue = metric.format(value);

            const isGood = metric.benchmark.startsWith('>') ?
                value > parseFloat(metric.benchmark.substring(1)) :
                value < parseFloat(metric.benchmark.substring(1));

            row.innerHTML = `
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${metric.name}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${formattedValue}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${metric.benchmark}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">-</td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${isGood ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                        ${isGood ? 'Good' : 'Needs Attention'}
                    </span>
                </td>
            `;

            tbody.appendChild(row);
        });

        if (statusElement) {
            statusElement.textContent = `Last updated: ${new Date().toLocaleString()}`;
        }
    }

    showMLErrorStatus(message) {
        // Update status cards with error
        const modelStatusElement = document.getElementById('ml-model-status');
        const vectorStatusElement = document.getElementById('ml-vector-db-status');

        if (modelStatusElement) {
            modelStatusElement.textContent = 'Error';
            modelStatusElement.className = 'text-2xl font-bold text-red-600';
        }

        if (vectorStatusElement) {
            vectorStatusElement.textContent = 'Error';
            vectorStatusElement.className = 'text-2xl font-bold text-red-600';
        }

        const statusElement = document.getElementById('ml-performance-table-status');
        if (statusElement) {
            statusElement.textContent = message;
        }

        // Clear charts with error message
        const performanceChart = document.getElementById('ml-performance-chart');
        const featureChart = document.getElementById('ml-feature-importance-chart');

        if (performanceChart) {
            performanceChart.innerHTML = '<div class="flex items-center justify-center h-full text-red-500"><i class="fas fa-exclamation-triangle text-4xl mb-4"></i><p>Error loading data</p></div>';
        }

        if (featureChart) {
            featureChart.innerHTML = '<div class="flex items-center justify-center h-full text-red-500"><i class="fas fa-exclamation-triangle text-4xl mb-4"></i><p>Error loading data</p></div>';
        }
    }

    setupMLEventListeners() {
        // Setup ML button event listeners
        const trainBtn = document.getElementById('ml-train-model-btn');
        const updateBtn = document.getElementById('ml-update-model-btn');
        const rollbackBtn = document.getElementById('ml-rollback-model-btn');
        const refreshBtn = document.getElementById('ml-refresh-dashboard');

        if (trainBtn) {
            trainBtn.addEventListener('click', () => this.performMLAction('train'));
        }

        if (updateBtn) {
            updateBtn.addEventListener('click', () => this.performMLAction('update'));
        }

        if (rollbackBtn) {
            rollbackBtn.addEventListener('click', () => this.performMLAction('rollback'));
        }

        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadMLDashboardData());
        }
    }

    async performMLAction(action) {
        const buttonMap = {
            'train': 'ml-train-model-btn',
            'update': 'ml-update-model-btn',
            'rollback': 'ml-rollback-model-btn'
        };

        const buttonId = buttonMap[action];
        if (!buttonId) return;

        const button = document.getElementById(buttonId);
        const progressElement = document.getElementById('ml-training-progress');
        const statusElement = document.getElementById('ml-action-status');

        if (!button) return;

        try {
            // Disable button and show loading
            const originalText = button.innerHTML;
            button.disabled = true;
            button.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Processing...';

            // Show progress for training
            if (action === 'train' && progressElement) {
                progressElement.classList.remove('hidden');
                this.simulateTrainingProgress();
            }

            // Call API
            const response = await fetch(`/api/ml/${action}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const result = await response.json();

            // Show result
            if (statusElement) {
                statusElement.className = result.error ? 'bg-red-100 border border-red-400 text-red-700 p-3 rounded-md' : 'bg-green-100 border border-green-400 text-green-700 p-3 rounded-md';
                statusElement.textContent = result.error || result.message || 'Action completed successfully';
                statusElement.classList.remove('hidden');
            }

            // Hide progress and refresh data after delay
            setTimeout(() => {
                if (progressElement) {
                    progressElement.classList.add('hidden');
                }
                this.loadMLDashboardData();
            }, 3000);

        } catch (error) {
            if (statusElement) {
                statusElement.className = 'bg-red-100 border border-red-400 text-red-700 p-3 rounded-md';
                statusElement.textContent = 'Error: ' + error.message;
                statusElement.classList.remove('hidden');
            }
        } finally {
            // Re-enable button
            button.disabled = false;
            button.innerHTML = button.getAttribute('data-original-text') || originalText;
        }
    }

    simulateTrainingProgress() {
        const progressBar = document.getElementById('ml-progress-bar');
        const progressPercent = document.getElementById('ml-progress-percent');
        const progressMessage = document.getElementById('ml-progress-message');

        if (!progressBar || !progressPercent || !progressMessage) return;

        let progress = 0;
        const interval = setInterval(() => {
            progress += Math.random() * 15;
            if (progress > 100) progress = 100;

            progressBar.style.width = progress + '%';
            progressPercent.textContent = Math.round(progress) + '%';

            // Update messages based on progress
            if (progress < 25) {
                progressMessage.textContent = 'Loading data and preprocessing...';
            } else if (progress < 50) {
                progressMessage.textContent = 'Training model...';
            } else if (progress < 75) {
                progressMessage.textContent = 'Validating performance...';
            } else if (progress < 100) {
                progressMessage.textContent = 'Saving model...';
            } else {
                progressMessage.textContent = 'Training completed!';
                clearInterval(interval);
            }
        }, 1000);
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new EnhancedTradingDashboard();
});

// Export for module usage
export default EnhancedTradingDashboard;
