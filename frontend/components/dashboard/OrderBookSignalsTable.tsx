import React, { useState, useMemo } from 'react';
import { DataTable } from '@/components/ui/DataTable';
import Tooltip from '@/components/ui/Tooltip';
import { DataTableColumn, OrderBookSignal } from '@/types/trading';

export function OrderBookSignalsTable({
    signals,
    pagination,
    onPageChange,
    onPageSizeChange,
    summary,
}: {
    signals: OrderBookSignal[];
    pagination?: {
        current_page: number;
        per_page: number;
        total_pages: number;
        total_signals: number;
        has_next: boolean;
        has_prev: boolean;
    };
    onPageChange?: (page: number) => void;
    onPageSizeChange?: (pageSize: number) => void;
    summary?: {
        total_analyzed?: number;
        active_signals?: number;
        average_strength?: number;
        last_updated?: string;
    };
}) {
    const [sortKey, setSortKey] = useState<keyof OrderBookSignal | null>('timestamp');
    const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

    const handleSort = (key: string) => {
        const newDirection = sortKey === key && sortDirection === 'asc' ? 'desc' : 'asc';
        setSortKey(key as keyof OrderBookSignal);
        setSortDirection(newDirection);
    };

    const sortedSignals = useMemo(() => {
        if (!sortKey || !signals) return signals || [];

        return [...signals].sort((a, b) => {
            const aVal = a[sortKey];
            const bVal = b[sortKey];

            // Handle null/undefined values to be consistently at the start or end
            if (aVal == null) return 1;
            if (bVal == null) return -1;

            let comparison = 0;
            if (aVal < bVal) {
                comparison = -1;
            } else if (aVal > bVal) {
                comparison = 1;
            }

            return sortDirection === 'desc' ? comparison * -1 : comparison;
        });
    }, [signals, sortKey, sortDirection]);

    // Use pagination from props
    const activePage = pagination?.current_page || 1;
    const activePageSize = pagination?.per_page || 10;
    const totalPages = pagination?.total_pages || 1;
    const totalSignals = (summary?.total_analyzed ?? pagination?.total_signals ?? (signals?.length || 0));

    // Data is paginated by the server, so we use it directly.
    const paginatedSignals = sortedSignals;

    const handlePageChange = (page: number) => {
        onPageChange?.(page);
    };

    const handlePageSizeChange = (newPageSize: number) => {
        onPageSizeChange?.(newPageSize);
    };

    const columns: DataTableColumn<OrderBookSignal>[] = [
        {
            key: 'timestamp',
            header: 'Time',
            sortable: true,
            className: "px-2 py-2",
            render: (value) => new Date(value).toLocaleString(),
        },
        {
            key: 'symbol',
            header: 'Symbol',
            sortable: true,
            className: "px-2 py-2",
            render: (value, row) => (
                <div className="flex items-center space-x-2">
                    <div className="text-sm font-medium text-gray-900">{value}</div>
                    <span className="text-xs" title={`Data Status: ${row.data_status}`}>
                        {row.data_status === 'sufficient' ? '✓' :
                            row.data_status === 'insufficient' ? '⚠' : '✗'}
                    </span>
                </div>
            ),
        },
        {
            key: 'price',
            header: 'Price',
            sortable: true,
            className: "px-2 py-2",
            render: (value) => `$${value?.toFixed(2) || '0.00'}`,
        },
        {
            key: 'signal_generated',
            header: 'Signal',
            sortable: true,
            className: "px-2 py-2",
            render: (value, row) => {
                const signalClass = row.data_status === 'sufficient'
                    ? (row.signal === 'buy' ? 'text-green-600 bg-green-50' :
                        row.signal === 'sell' ? 'text-red-600 bg-red-50' :
                            'text-gray-600 bg-gray-50')
                    : row.data_status === 'insufficient'
                        ? 'text-yellow-600 bg-yellow-50'
                        : 'text-gray-400 bg-gray-100';

                // Get the actual signal value, fallback to 'hold' if undefined
                const actualSignal = row.signal || 'hold';

                return (
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${signalClass}`}>
                        {row.data_status === 'sufficient' ? actualSignal.toUpperCase() :
                            row.data_status === 'insufficient' ? 'WAITING' : 'NO DATA'}
                    </span>
                );
            },
        },
        {
            key: 'signal_strength',
            header: 'Strength',
            sortable: true,
            className: "px-2 py-2",
            render: (value, row) => {
                const composition = row.strength_composition || {};
                const tooltipContent = (
                    <div>
                        <p className="font-bold mb-1">Signal Strength: {(value || 0).toFixed(2)}</p>
                        <p className="text-xs mb-2">This is the ML model's confidence in the signal. It is composed of the following features, weighted by their learned importance:</p>
                        <ul className="list-disc list-inside text-xs">
                            {Object.entries(composition).map(([key, val]) => (
                                <li key={key}>
                                    <span className="font-semibold">{key.replace(/_/g, ' ')}:</span> {val.importance_percent.toFixed(1)}%
                                </li>
                            ))}
                        </ul>
                    </div>
                );

                return (
                    <div className="flex items-center">
                        <div className="w-16 bg-gray-200 rounded-full h-2 mr-2">
                            <div className="bg-blue-600 h-2 rounded-full" style={{ width: `${(value || 0) * 100}%` }}></div>
                        </div>
                        <span className={`text-sm font-medium ${(value || 0) >= 0.7 ? 'text-green-600' :
                            (value || 0) >= 0.4 ? 'text-yellow-600' : 'text-red-600'
                            }`}>
                            {(value || 0).toFixed(2)}
                        </span>
                    </div>
                );
            },
        },
        {
            key: 'spread',
            header: 'Spread',
            sortable: true,
            className: "px-2 py-2",
            render: (value) => `${(value || 0).toFixed(4)}%`,
        },
        {
            key: 'volume',
            header: 'Volume',
            sortable: true,
            className: "px-2 py-2",
            render: (value) => (value || 0).toFixed(2),
        },
        {
            key: 'criteria_analysis',
            header: 'Criteria',
            className: "px-2 py-2",
            render: (value, row) => {
                const criteria = value || {};
                const squeeze = criteria.bid_ask_squeeze || {};
                const imbalanceBuy = criteria.volume_imbalance_buy || {};
                const largeTradeBuy = criteria.large_trade_buy || {};

                return (
                    <div className="text-xs space-y-1">
                        <div className="flex items-center space-x-1">
                            <span className={squeeze.meets_criteria ? 'text-green-600' : 'text-red-600'}>
                                {squeeze.enabled ? (squeeze.meets_criteria ? '✓' : '✗') : '○'}
                            </span>
                            <span className="text-gray-600">Squeeze</span>
                        </div>
                        <div className="flex items-center space-x-1">
                            <span className={imbalanceBuy.meets_criteria ? 'text-green-600' : 'text-red-600'}>
                                {imbalanceBuy.enabled ? (imbalanceBuy.meets_criteria ? '✓' : '✗') : '○'}
                            </span>
                            <span className="text-gray-600">Imbalance</span>
                        </div>
                        <div className="flex items-center space-x-1">
                            <span className={largeTradeBuy.meets_criteria ? 'text-green-600' : 'text-red-600'}>
                                {largeTradeBuy.enabled ? (largeTradeBuy.meets_criteria ? '✓' : '✗') : '○'}
                            </span>
                            <span className="text-gray-600">Large Trade</span>
                        </div>
                    </div>
                );
            },
        },
        {
            key: 'ml_analysis',
            header: 'ML Analysis',
            className: "px-2 py-2",
            render: (value, row) => {
                const ml = value || {};
                if (!ml.ml_enabled) {
                    return <span className="text-xs text-gray-400">No ML</span>;
                }

                // Fix: Clamp win probability to 100%
                const rawWinProb = ml.win_probability || 0;
                const winProb = Math.min(rawWinProb, 100);

                return (
                    <div className="text-xs space-y-1">
                        <div className="flex items-center space-x-1">
                            <span className="text-blue-600">🤖</span>
                            <span className={`font-medium ${winProb >= 60 ? 'text-green-600' :
                                winProb >= 40 ? 'text-yellow-600' : 'text-red-600'
                                }`}>
                                Win Probability: {winProb.toFixed(1)}%
                            </span>
                        </div>
                        <div className="text-gray-500">
                            Expected Return: {(ml.expected_return || 0).toFixed(1)}%
                        </div>
                    </div>
                );
            },
        },
        {
            key: 'timestamp' as keyof OrderBookSignal,
            header: 'Details',
            className: "px-2 py-2",
            render: (value, row) => (
                <button
                    onClick={() => {
                        // Create a modal or tooltip with detailed analysis
                        const details = `
Signal: ${row.signal || 'None'}
Reason: ${row.signal_reason || 'N/A'}
Type: ${row.signal_type || 'N/A'}

Criteria Analysis:
- Bid-Ask Squeeze: ${row.criteria_analysis?.bid_ask_squeeze?.analysis || 'N/A'}
- Volume Imbalance Buy: ${row.criteria_analysis?.volume_imbalance_buy?.analysis || 'N/A'}
- Volume Imbalance Sell: ${row.criteria_analysis?.volume_imbalance_sell?.analysis || 'N/A'}
- Large Trade Buy: ${row.criteria_analysis?.large_trade_buy?.analysis || 'N/A'}
- Large Trade Sell: ${row.criteria_analysis?.large_trade_sell?.analysis || 'N/A'}

${row.ml_analysis?.ml_enabled ? `
ML Analysis:
- Win Probability: ${(row.ml_analysis.win_probability).toFixed(4)}%
- Expected Return: ${(row.ml_analysis.expected_return).toFixed(4)}%
- Confidence: ${(row.ml_analysis.confidence * 100).toFixed(2)}%
- Model: ${row.ml_analysis.model_version || 'N/A'}

Analytics:
${(row.ml_analysis.analytics && Object.keys(row.ml_analysis.analytics).length > 0) ? JSON.stringify(row.ml_analysis.analytics, null, 2) : 'No detailed analytics available (Empty/Null)'}
` : 'ML Analysis: Not enabled'}
            `;
                        alert(details); // Replace with proper modal in production
                    }}
                    className="text-blue-600 hover:text-blue-800 text-xs font-medium"
                >
                    <i className="fas fa-info-circle mr-1"></i>Details
                </button>
            ),
        },
    ];

    return (
        <div className="space-y-4">
            {/* Pagination Controls */}
            <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                    <label className="text-sm text-gray-700">Show:</label>
                    <select
                        value={activePageSize}
                        onChange={(e) => handlePageSizeChange(parseInt(e.target.value))}
                        className="border border-gray-300 rounded-md px-2 py-1 text-sm"
                    >
                        <option value={10}>10</option>
                        <option value={25}>25</option>
                        <option value={50}>50</option>
                        <option value={100}>100</option>
                    </select>
                    <span className="text-sm text-gray-600">
                        per page
                    </span>
                </div>

                <div className="text-sm text-gray-600">
                    Page {activePage} of {totalPages} ({totalSignals} total signals)
                </div>

                <div className="flex items-center space-x-2">
                    <button
                        onClick={() => handlePageChange(activePage - 1)}
                        disabled={activePage <= 1}
                        className="px-3 py-1 border border-gray-300 rounded-md text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                    >
                        <i className="fas fa-chevron-left mr-1"></i>Prev
                    </button>

                    <div className="flex items-center space-x-1">
                        {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                            const pageNum = Math.max(1, Math.min(totalPages - 4, activePage - 2)) + i;
                            if (pageNum > totalPages) return null;

                            return (
                                <button
                                    key={pageNum}
                                    onClick={() => handlePageChange(pageNum)}
                                    className={`px-3 py-1 border rounded-md text-sm ${pageNum === activePage
                                        ? 'bg-blue-600 text-white border-blue-600'
                                        : 'border-gray-300 hover:bg-gray-50'
                                        }`}
                                >
                                    {pageNum}
                                </button>
                            );
                        })}
                    </div>

                    <button
                        onClick={() => handlePageChange(activePage + 1)}
                        disabled={activePage >= totalPages}
                        className="px-3 py-1 border border-gray-300 rounded-md text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                    >
                        Next<i className="fas fa-chevron-right ml-1"></i>
                    </button>
                </div>
            </div>

            {/* Data Table */}
            <DataTable
                data={paginatedSignals}
                columns={columns}
                loading={false}
                sorting={{
                    key: sortKey || 'timestamp',
                    direction: sortDirection,
                    onSort: handleSort,
                }}
                className="w-full"
            />

            {/* Statistics Summary */}
            {signals && signals.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mt-4 p-4 bg-gray-50 rounded-lg">
                    <div className="text-center">
                        <div className="text-lg font-semibold text-gray-900">{totalSignals}</div>
                        <div className="text-sm text-gray-600">Total Analyzed</div>
                    </div>
                    <div className="text-center">
                        <div className="text-lg font-semibold text-green-600">
                            {summary?.active_signals ?? signals.filter(s => s.signal_generated === true).length}
                        </div>
                        <div className="text-sm text-gray-600">Active Signals</div>
                    </div>
                    <div className="text-center">
                        <div className="text-lg font-semibold text-blue-600">
                            {(
                                summary?.average_strength ??
                                (signals.length > 0 ? (signals.reduce((sum, s) => sum + (s.signal_strength || 0), 0) / signals.length) : 0)
                            ).toFixed(2)}
                        </div>
                        <div className="text-sm text-gray-600">Avg Strength</div>
                    </div>
                    <div className="text-center">
                        <div className="text-lg font-semibold text-gray-900">
                            {(summary?.last_updated ? new Date(summary.last_updated) : new Date()).toLocaleTimeString()}
                        </div>
                        <div className="text-sm text-gray-600">Last Updated</div>
                    </div>
                </div>
            )}
        </div>
    );
}
