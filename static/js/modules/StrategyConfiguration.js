/**
 * StrategyConfiguration Module
 * Handles strategy setup and configuration management
 */
export class StrategyConfiguration {
    constructor(dashboard) {
        this.dashboard = dashboard;
        
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
    }

    hideStrategyConfiguration() {
        const strategySection = document.getElementById('strategy-configuration-section');
        const showStrategySection = document.getElementById('show-strategy-section');
        
        if (strategySection && showStrategySection) {
            strategySection.style.display = 'none';
            showStrategySection.style.display = 'block';
            this.saveStrategyConfigState();
            console.log('Strategy configuration hidden');
        }
    }

    showStrategyConfiguration() {
        const strategySection = document.getElementById('strategy-configuration-section');
        const showStrategySection = document.getElementById('show-strategy-section');
        
        if (strategySection && showStrategySection) {
            strategySection.style.display = 'block';
            showStrategySection.style.display = 'none';
            this.saveStrategyConfigState();
            console.log('Strategy configuration shown');
        }
    }

    autoHideStrategyOnTradingStart() {
        // Automatically hide strategy configuration when trading starts
        // This provides a cleaner interface during active trading
        if (this.dashboard.liveTrading.isActive) {
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
        const strategySection = document.getElementById('strategy-configuration-section');
        const isHidden = strategySection && strategySection.style.display === 'none';
        localStorage.setItem('strategy_config_hidden', isHidden.toString());
    }

    loadStrategyParameters(strategyType) {
        console.log('StrategyConfiguration.loadStrategyParameters called with:', strategyType);
        
        const paramsContainer = document.getElementById('live-strategy-params');
        if (!paramsContainer) {
            console.warn('Strategy parameters container not found: #live-strategy-params');
            return;
        }

        console.log('Loading strategy parameters for:', strategyType);
        
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
        
        console.log('Strategy parameters loaded successfully for:', strategyType);
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
}
