/**
 * DataManager Module (Optimized)
 * Handles data fetching and API communication with advanced caching and batching
 */
export class DataManager {
    constructor(dashboard) {
        this.dashboard = dashboard;
        this.cache = new Map();
        this.cacheTimeout = 30000; // 30 seconds
        this.requestQueue = new Map();
        this.batchTimeout = 100; // 100ms batch window
        this.pendingRequests = new Set();
    }

    async fetchData(url, options = {}) {
        // Check if request is already pending
        if (this.pendingRequests.has(url)) {
            return this.waitForPendingRequest(url);
        }

        this.pendingRequests.add(url);
        
        try {
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'Cache-Control': 'max-age=300', // 5 minutes
                    ...options.headers
                },
                ...options
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            return data;
        } catch (error) {
            console.error(`Error fetching data from ${url}:`, error);
            throw error;
        } finally {
            this.pendingRequests.delete(url);
        }
    }

    async waitForPendingRequest(url) {
        return new Promise((resolve, reject) => {
            const checkPending = () => {
                if (!this.pendingRequests.has(url)) {
                    // Request completed, try to get from cache
                    const cacheKey = `${url}_${JSON.stringify({})}`;
                    const cached = this.cache.get(cacheKey);
                    if (cached && Date.now() - cached.timestamp < this.cacheTimeout) {
                        resolve(cached.data);
                    } else {
                        reject(new Error('Request failed'));
                    }
                } else {
                    setTimeout(checkPending, 50);
                }
            };
            checkPending();
        });
    }

    async fetchWithCache(url, options = {}) {
        const cacheKey = `${url}_${JSON.stringify(options)}`;
        const cached = this.cache.get(cacheKey);
        
        if (cached && Date.now() - cached.timestamp < this.cacheTimeout) {
            return cached.data;
        }

        const data = await this.fetchData(url, options);
        this.cache.set(cacheKey, {
            data,
            timestamp: Date.now()
        });

        return data;
    }

    async loadTradingStats() {
        try {
            const data = await this.fetchData('/api/trades/stats');
            return data;
        } catch (error) {
            console.error('Error loading trading stats:', error);
            return null;
        }
    }

    async loadSimulatedTradingStats() {
        try {
            const data = await this.fetchData('/api/simulated-trading/status');
            return data;
        } catch (error) {
            console.error('Error loading simulated trading stats:', error);
            return null;
        }
    }

    async loadProducts() {
        try {
            const data = await this.fetchWithCache('/api/products');
            return data;
        } catch (error) {
            console.error('Error loading products:', error);
            return null;
        }
    }

    async loadOrderBookSignals(symbols) {
        try {
            const symbolsParam = symbols.join(',');
            const url = `/api/orderbook/live-signals?symbols=${symbolsParam}`;
            const data = await this.fetchData(url);
            return data;
        } catch (error) {
            console.error('Error loading order book signals:', error);
            return null;
        }
    }

    async processSignals(symbols) {
        try {
            const response = await this.fetchData('/api/trading/simulated/process-signals', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ symbols })
            });
            return response;
        } catch (error) {
            console.error('Error processing signals:', error);
            return null;
        }
    }

    async loadTradingHistory(page = 1, limit = 50) {
        try {
            const url = `/api/trades/paginated?page=${page}&per_page=${limit}`;
            const data = await this.fetchData(url);
            return data;
        } catch (error) {
            console.error('Error loading trading history:', error);
            return null;
        }
    }

    async loadOrderBookHistory(page = 1, limit = 50) {
        try {
            const url = `/api/orderbook/signals/paginated?page=${page}&per_page=${limit}`;
            const data = await this.fetchData(url);
            return data;
        } catch (error) {
            console.error('Error loading order book history:', error);
            return null;
        }
    }

    async loadPositions(page = 1, limit = 50) {
        try {
            const url = `/api/trading/live/positions?page=${page}&limit=${limit}`;
            const data = await this.fetchData(url);
            return data;
        } catch (error) {
            console.error('Error loading positions:', error);
            return null;
        }
    }

    async loadBacktestHistory(page = 1, limit = 50) {
        try {
            const url = `/api/backtest/history?limit=${limit}&offset=${(page - 1) * limit}`;
            const data = await this.fetchData(url);
            return data;
        } catch (error) {
            console.error('Error loading backtest history:', error);
            return null;
        }
    }

    async startTrading(mode, strategy, symbols, parameters) {
        try {
            // Use the correct endpoint based on trading mode
            const endpoint = mode === 'live' ? '/api/trading/live/start' : '/api/trading/simulated/start';
            
            const response = await this.fetchData(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    // Align with backend expectations
                    mode,
                    symbols,
                    strategy_type: strategy,
                    strategy_params: parameters
                })
            });
            return response;
        } catch (error) {
            console.error('Error starting trading:', error);
            return null;
        }
    }

    async stopTrading() {
        try {
            // Use simulated trading stop endpoint (since we're primarily using simulated mode)
            const response = await this.fetchData('/api/trading/simulated/stop', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            return response;
        } catch (error) {
            console.error('Error stopping trading:', error);
            return null;
        }
    }

    async runBacktest(strategy, symbols, parameters, startDate, endDate) {
        try {
            const response = await this.fetchData('/api/backtests/run', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    strategy,
                    symbols,
                    parameters,
                    start_date: startDate,
                    end_date: endDate
                })
            });
            return response;
        } catch (error) {
            console.error('Error running backtest:', error);
            return null;
        }
    }

    async batchLoadData(requests) {
        // Batch multiple API requests together
        const promises = requests.map(async (request) => {
            try {
                const data = await this.fetchWithCache(request.url, request.options);
                return { success: true, data, key: request.key };
            } catch (error) {
                console.error(`Error in batch request ${request.key}:`, error);
                return { success: false, error, key: request.key };
            }
        });

        const results = await Promise.allSettled(promises);
        
        // Process results
        const batchResults = {};
        results.forEach((result, index) => {
            const request = requests[index];
            if (result.status === 'fulfilled' && result.value.success) {
                batchResults[request.key] = result.value.data;
            } else {
                batchResults[request.key] = null;
            }
        });

        return batchResults;
    }

    clearCache() {
        this.cache.clear();
        this.pendingRequests.clear();
    }

    setCacheTimeout(timeout) {
        this.cacheTimeout = timeout;
    }

    // Smart cache invalidation
    invalidateCache(pattern) {
        for (const [key] of this.cache) {
            if (key.includes(pattern)) {
                this.cache.delete(key);
            }
        }
    }
}
