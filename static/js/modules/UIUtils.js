/**
 * UIUtils Module
 * Handles UI utilities and DOM manipulation
 */
export class UIUtils {
    constructor(dashboard) {
        this.dashboard = dashboard;
    }

    updateElement(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
    }

    updateTradingModeUI() {
        const mode = this.dashboard.liveTrading.mode;
        const startButton = document.getElementById('start-trading');
        const warningText = document.querySelector('#live-mode + p');
        
        if (mode === 'live') {
            startButton.textContent = 'Start Live Trading';
            startButton.className = 'px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500';
            if (warningText) {
                warningText.textContent = '⚠️ Live trading mode - real money at risk!';
                warningText.className = 'text-red-600 text-sm mt-2';
            }
        } else {
            startButton.textContent = 'Start Simulated Trading';
            startButton.className = 'px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500';
            if (warningText) {
                warningText.textContent = 'Simulated trading mode - no real money at risk';
                warningText.className = 'text-green-600 text-sm mt-2';
            }
        }
    }

    updateSymbolModeUI() {
        console.log('updateSymbolModeUI called');
        const symbolMode = this.dashboard.liveTrading.symbolMode;
        console.log('Current symbolMode:', symbolMode);
        const singleConfig = document.getElementById('single-symbol-config');
        const universeConfig = document.getElementById('universe-config');
        const singleStrategy = document.getElementById('single-strategy');
        const universeStrategy = document.getElementById('universe-strategy');
        
        console.log('singleConfig element:', singleConfig);
        console.log('universeConfig element:', universeConfig);
        
        if (symbolMode === 'universe') {
            console.log('Setting universe mode UI');
            if (singleConfig) singleConfig.style.display = 'none';
            if (universeConfig) universeConfig.style.display = 'block';
            if (singleStrategy && universeStrategy) {
                singleStrategy.style.display = 'none';
                universeStrategy.style.display = 'block';
            }
        } else {
            console.log('Setting single symbol mode UI');
            if (singleConfig) singleConfig.style.display = 'block';
            if (universeConfig) universeConfig.style.display = 'none';
            if (singleStrategy && universeStrategy) {
                singleStrategy.style.display = 'block';
                universeStrategy.style.display = 'none';
            }
        }
    }

    updateUniverseTypeUI() {
        const universeType = document.getElementById('universe-type')?.value;
        console.log('updateUniverseTypeUI called with universeType:', universeType);
        
        const customSymbolsConfig = document.getElementById('custom-symbols-config');
        const customSymbolsInput = document.getElementById('custom-symbols-input');
        
        if (universeType === 'custom') {
            if (customSymbolsConfig) customSymbolsConfig.style.display = 'block';
            if (customSymbolsInput) customSymbolsInput.required = true;
        } else {
            if (customSymbolsConfig) customSymbolsConfig.style.display = 'none';
            if (customSymbolsInput) customSymbolsInput.required = false;
        }
        
        // Load universe symbols
        this.loadUniverseSymbols(universeType);
    }

    async loadUniverseSymbols(universeType) {
        console.log('loadUniverseSymbols called with universeType:', universeType);
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
                    case 'custom':
                        const customSymbols = document.getElementById('custom-symbols-input')?.value;
                        symbols = customSymbols ? customSymbols.split(',').map(s => s.trim()).filter(s => s) : [];
                        break;
                    default:
                        symbols = [];
                }
                
                console.log('Loaded symbols for', universeType, ':', symbols.length, 'symbols');
                this.updateUniversePreview(symbols);
            }
        } catch (error) {
            console.error('Error loading universe symbols:', error);
        }
    }

    updateUniversePreview(symbols) {
        console.log('updateUniversePreview called with symbols:', symbols.length, 'symbols');
        const universeSymbols = document.getElementById('universe-symbols');
        const universeCount = document.getElementById('universe-count');
        
        console.log('universe-symbols element:', universeSymbols);
        console.log('universe-count element:', universeCount);
        
        if (universeSymbols) {
            if (symbols.length === 0) {
                universeSymbols.innerHTML = '<div class="text-gray-500 text-sm">No symbols available</div>';
            } else {
                const symbolsHtml = symbols.map(symbol => {
                    return `
                        <span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800 mr-2 mb-2">
                            ${symbol}
                        </span>
                    `;
                }).join('');
                universeSymbols.innerHTML = symbolsHtml;
            }
        }
        
        if (universeCount) {
            universeCount.textContent = symbols.length;
        }
    }

    async loadProducts() {
        try {
            const response = await fetch('/api/products');
            const data = await response.json();
            
            if (data.status === 'success') {
                this.populateProductSelectors(data.categories);
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
            selectors = categories;
        } else {
            // Called with categories data - get all selectors that need product options
            const selectorIds = [
                'product-id', 'universe-symbol-1', 'universe-symbol-2', 'universe-symbol-3', 
                'universe-symbol-4', 'universe-symbol-5', 'live-trading-symbol'
            ];
            
            selectors = selectorIds.map(id => {
                const element = document.getElementById(id);
                return element ? { id, element } : null;
            }).filter(Boolean);
        }

        // Create options for each category
        const categoryOptions = {
            'Major Pairs': categories.major || [],
            'Minor Pairs': categories.minor || [],
            'Exotic Pairs': categories.exotic || [],
            'Crypto': categories.crypto || [],
            'Stocks': categories.stocks || [],
            'Commodities': categories.commodities || []
        };

        selectors.forEach(({ id, element }) => {
            if (!element) return;

            // Clear existing options
            element.innerHTML = '';
            
            // Add category headers and options
            Object.entries(categoryOptions).forEach(([categoryName, products]) => {
                if (products.length > 0) {
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
                }
            });

            // Set default selection
            if (id === 'product-id' || id === 'live-trading-symbol') {
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

    showMessage(message, type = 'info') {
        // Create or update message element
        let messageElement = document.getElementById('dashboard-message');
        if (!messageElement) {
            messageElement = document.createElement('div');
            messageElement.id = 'dashboard-message';
            messageElement.className = 'fixed top-4 right-4 p-4 rounded-md shadow-lg z-50';
            document.body.appendChild(messageElement);
        }

        // Set message content and styling
        messageElement.textContent = message;
        messageElement.className = `fixed top-4 right-4 p-4 rounded-md shadow-lg z-50 ${
            type === 'error' ? 'bg-red-500 text-white' :
            type === 'success' ? 'bg-green-500 text-white' :
            type === 'warning' ? 'bg-yellow-500 text-black' :
            'bg-blue-500 text-white'
        }`;

        // Auto-hide after 5 seconds
        setTimeout(() => {
            if (messageElement && messageElement.parentNode) {
                messageElement.parentNode.removeChild(messageElement);
            }
        }, 5000);
    }

    showLoading(elementId, show = true) {
        const element = document.getElementById(elementId);
        if (!element) return;

        if (show) {
            element.innerHTML = '<div class="flex items-center justify-center"><div class="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div></div>';
        } else {
            element.innerHTML = '';
        }
    }

    formatCurrency(value, currency = 'USD') {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency
        }).format(value);
    }

    formatPercentage(value, decimals = 2) {
        return `${value.toFixed(decimals)}%`;
    }

    formatNumber(value, decimals = 2) {
        return value.toFixed(decimals);
    }

    formatDate(date) {
        return new Date(date).toLocaleString();
    }

    debounce(func, wait) {
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

    throttle(func, limit) {
        let inThrottle;
        return function executedFunction(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }
}
