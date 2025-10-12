/**
 * Pagination Module
 * Handles pagination for trading history, signals, and positions
 */
export class Pagination {
    constructor(dashboard) {
        this.dashboard = dashboard;
        this.tradingHistoryPage = 1;
        this.orderBookSignalsPage = 1;
        this.positionsPage = 1;
        this.backtestHistoryPage = 1;
        this.itemsPerPage = 50;
    }

    setupTradingHistoryPagination() {
        const prevBtn = document.getElementById('trading-history-prev');
        const nextBtn = document.getElementById('trading-history-next');
        const pageInfo = document.getElementById('trading-history-page-info');

        if (prevBtn) {
            prevBtn.addEventListener('click', () => {
                if (this.tradingHistoryPage > 1) {
                    this.tradingHistoryPage--;
                    this.loadTradingHistory();
                }
            });
        }

        if (nextBtn) {
            nextBtn.addEventListener('click', () => {
                this.tradingHistoryPage++;
                this.loadTradingHistory();
            });
        }

        this.loadTradingHistory();
    }

    setupOrderBookSignalsPagination() {
        const prevBtn = document.getElementById('orderbook-signals-prev');
        const nextBtn = document.getElementById('orderbook-signals-next');
        const pageInfo = document.getElementById('orderbook-signals-page-info');

        if (prevBtn) {
            prevBtn.addEventListener('click', () => {
                if (this.orderBookSignalsPage > 1) {
                    this.orderBookSignalsPage--;
                    this.loadOrderBookSignals();
                }
            });
        }

        if (nextBtn) {
            nextBtn.addEventListener('click', () => {
                this.orderBookSignalsPage++;
                this.loadOrderBookSignals();
            });
        }

        this.loadOrderBookSignals();
    }

    setupPositionsPagination() {
        const prevBtn = document.getElementById('positions-prev');
        const nextBtn = document.getElementById('positions-next');
        const pageInfo = document.getElementById('positions-page-info');

        if (prevBtn) {
            prevBtn.addEventListener('click', () => {
                if (this.positionsPage > 1) {
                    this.positionsPage--;
                    this.loadPositions();
                }
            });
        }

        if (nextBtn) {
            nextBtn.addEventListener('click', () => {
                this.positionsPage++;
                this.loadPositions();
            });
        }

        this.loadPositions();
    }

    setupBacktestHistoryPagination() {
        const prevBtn = document.getElementById('backtest-history-prev');
        const nextBtn = document.getElementById('backtest-history-next');
        const pageInfo = document.getElementById('backtest-history-page-info');

        if (prevBtn) {
            prevBtn.addEventListener('click', () => {
                if (this.backtestHistoryPage > 1) {
                    this.backtestHistoryPage--;
                    this.loadBacktestHistory();
                }
            });
        }

        if (nextBtn) {
            nextBtn.addEventListener('click', () => {
                this.backtestHistoryPage++;
                this.loadBacktestHistory();
            });
        }

        this.loadBacktestHistory();
    }

    async loadTradingHistory() {
        try {
            const data = await this.dashboard.dataManager.loadTradingHistory(
                this.tradingHistoryPage, 
                this.itemsPerPage
            );

            if (data && data.trades) {
                this.updateTradingHistoryTable(data.trades);
                this.updateTradingHistoryPagination(data.pagination);
            }
        } catch (error) {
            console.error('Error loading trading history:', error);
        }
    }

    async loadOrderBookSignals() {
        try {
            const data = await this.dashboard.dataManager.loadOrderBookHistory(
                this.orderBookSignalsPage, 
                this.itemsPerPage
            );

            if (data && data.signals) {
                this.updateOrderBookSignalsTable(data.signals);
                this.updateOrderBookSignalsPagination(data.pagination);
            }
        } catch (error) {
            console.error('Error loading order book signals:', error);
        }
    }

    async loadPositions() {
        try {
            const data = await this.dashboard.dataManager.loadPositions(
                this.positionsPage, 
                this.itemsPerPage
            );

            if (data && data.positions) {
                this.updatePositionsTable(data.positions);
                this.updatePositionsPagination(data.pagination);
            }
        } catch (error) {
            console.error('Error loading positions:', error);
        }
    }

    async loadBacktestHistory() {
        try {
            const data = await this.dashboard.dataManager.loadBacktestHistory(
                this.backtestHistoryPage, 
                this.itemsPerPage
            );

            if (data && data.backtests) {
                this.updateBacktestHistoryTable(data.backtests);
                this.updateBacktestHistoryPagination(data.pagination);
            }
        } catch (error) {
            console.error('Error loading backtest history:', error);
        }
    }

    updateTradingHistoryTable(trades) {
        const tableBody = document.getElementById('trading-history-table');
        if (!tableBody) return;

        tableBody.innerHTML = '';

        trades.forEach(trade => {
            const row = document.createElement('tr');
            row.className = 'hover:bg-gray-50';
            
            row.innerHTML = `
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${trade.id}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${trade.symbol}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${trade.side}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${trade.quantity}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">$${trade.price}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm ${trade.pnl >= 0 ? 'text-green-600' : 'text-red-600'}">
                    ${trade.pnl >= 0 ? '+' : ''}$${trade.pnl.toFixed(2)}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${new Date(trade.timestamp).toLocaleString()}</td>
            `;
            
            tableBody.appendChild(row);
        });
    }

    updateOrderBookSignalsTable(signals) {
        // Use the history table within the Order Book Signals tab content
        const tableBody = document.getElementById('orderbook-signals-history-table');
        if (!tableBody) return;

        tableBody.innerHTML = '';

        signals.forEach(signal => {
            const row = document.createElement('tr');
            row.className = 'hover:bg-gray-50';
            
            const signalClass = signal.signal_generated ? 'text-green-600 bg-green-50' : 'text-gray-600 bg-gray-50';
            const strengthColor = (signal.signal_strength || 0) >= 0.7 ? 'text-green-600' : 
                                 (signal.signal_strength || 0) >= 0.4 ? 'text-yellow-600' : 'text-red-600';
            
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

    updatePositionsTable(positions) {
        const tableBody = document.getElementById('positions-table');
        if (!tableBody) return;

        tableBody.innerHTML = '';

        positions.forEach(position => {
            const row = document.createElement('tr');
            row.className = 'hover:bg-gray-50';
            
            const pnlColor = position.unrealized_pnl >= 0 ? 'text-green-600' : 'text-red-600';
            
            row.innerHTML = `
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${position.symbol}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${position.quantity}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">$${position.avg_price}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">$${position.current_price}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm ${pnlColor}">
                    ${position.unrealized_pnl >= 0 ? '+' : ''}$${position.unrealized_pnl.toFixed(2)}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${new Date(position.timestamp).toLocaleString()}</td>
            `;
            
            tableBody.appendChild(row);
        });
    }

    updateBacktestHistoryTable(backtests) {
        const tableBody = document.getElementById('backtest-history-table');
        if (!tableBody) return;

        tableBody.innerHTML = '';

        backtests.forEach(backtest => {
            const row = document.createElement('tr');
            row.className = 'hover:bg-gray-50';
            
            const pnlColor = backtest.total_pnl >= 0 ? 'text-green-600' : 'text-red-600';
            
            row.innerHTML = `
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${backtest.id}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${backtest.strategy}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${backtest.symbols.join(', ')}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm ${pnlColor}">
                    ${backtest.total_pnl >= 0 ? '+' : ''}$${backtest.total_pnl.toFixed(2)}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${backtest.win_rate.toFixed(1)}%</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${new Date(backtest.created_at).toLocaleString()}</td>
            `;
            
            tableBody.appendChild(row);
        });
    }

    updateTradingHistoryPagination(pagination) {
        const pageInfo = document.getElementById('trading-history-page-info');
        const prevBtn = document.getElementById('trading-history-prev');
        const nextBtn = document.getElementById('trading-history-next');

        if (pageInfo) {
            pageInfo.textContent = `Page ${pagination.current_page} of ${pagination.total_pages}`;
        }

        if (prevBtn) {
            prevBtn.disabled = pagination.current_page <= 1;
        }

        if (nextBtn) {
            nextBtn.disabled = pagination.current_page >= pagination.total_pages;
        }
    }

    updateOrderBookSignalsPagination(pagination) {
        const pageInfo = document.getElementById('orderbook-signals-page-info');
        const prevBtn = document.getElementById('orderbook-signals-prev');
        const nextBtn = document.getElementById('orderbook-signals-next');

        if (pageInfo) {
            pageInfo.textContent = `Page ${pagination.current_page} of ${pagination.total_pages}`;
        }

        if (prevBtn) {
            prevBtn.disabled = pagination.current_page <= 1;
        }

        if (nextBtn) {
            nextBtn.disabled = pagination.current_page >= pagination.total_pages;
        }
    }

    updatePositionsPagination(pagination) {
        const pageInfo = document.getElementById('positions-page-info');
        const prevBtn = document.getElementById('positions-prev');
        const nextBtn = document.getElementById('positions-next');

        if (pageInfo) {
            pageInfo.textContent = `Page ${pagination.current_page} of ${pagination.total_pages}`;
        }

        if (prevBtn) {
            prevBtn.disabled = pagination.current_page <= 1;
        }

        if (nextBtn) {
            nextBtn.disabled = pagination.current_page >= pagination.total_pages;
        }
    }

    updateBacktestHistoryPagination(pagination) {
        const pageInfo = document.getElementById('backtest-history-page-info');
        const prevBtn = document.getElementById('backtest-history-prev');
        const nextBtn = document.getElementById('backtest-history-next');

        if (pageInfo) {
            pageInfo.textContent = `Page ${pagination.current_page} of ${pagination.total_pages}`;
        }

        if (prevBtn) {
            prevBtn.disabled = pagination.current_page <= 1;
        }

        if (nextBtn) {
            nextBtn.disabled = pagination.current_page >= pagination.total_pages;
        }
    }

    resetPagination() {
        this.tradingHistoryPage = 1;
        this.orderBookSignalsPage = 1;
        this.positionsPage = 1;
        this.backtestHistoryPage = 1;
    }
}
