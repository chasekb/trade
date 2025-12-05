import React, { useState } from 'react';

export function OpenPositionsSection({ positions }: { positions: any[] }) {
    const [page, setPage] = useState(1);
    const [perPage, setPerPage] = useState(10);

    const totalPages = Math.ceil(positions.length / perPage) || 1;
    const start = (page - 1) * perPage;
    const end = start + perPage;
    const pageData = positions.slice(start, end);

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <h4 className="font-semibold text-gray-700">Open Positions</h4>
                <div className="flex items-center space-x-2 text-sm">
                    <label className="text-gray-700">Show</label>
                    <select
                        value={perPage}
                        onChange={(e) => { setPerPage(parseInt(e.target.value)); setPage(1); }}
                        className="border border-gray-300 rounded-md px-2 py-1"
                    >
                        <option value={10}>10</option>
                        <option value={25}>25</option>
                        <option value={50}>50</option>
                    </select>
                    <span className="text-gray-600">per page</span>
                </div>
            </div>

            <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Symbol</th>
                            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Side</th>
                            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Quantity</th>
                            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Entry</th>
                            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Current</th>
                            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Unrealized P&L</th>
                            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Opened</th>
                        </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                        {pageData.map((pos: any, index: number) => (
                            <tr key={`${pos.symbol}-${pos.entry_time}-${index}`}>
                                <td className="px-4 py-2 text-sm text-gray-900">{pos.symbol}</td>
                                <td className="px-4 py-2 text-sm">
                                    <span className={`px-2 py-1 rounded-full text-xs ${(pos.side || '').toUpperCase() === 'LONG'
                                        ? 'bg-green-100 text-green-800'
                                        : 'bg-blue-100 text-blue-800'
                                        }`}>
                                        {(pos.side || '').toUpperCase() || '-'}
                                    </span>
                                </td>
                                <td className="px-4 py-2 text-sm text-gray-900">{Number(pos.quantity || 0).toFixed(4)}</td>
                                <td className="px-4 py-2 text-sm text-gray-900">${Number(pos.entry_price || 0).toFixed(4)}</td>
                                <td className="px-4 py-2 text-sm text-gray-900">${Number(pos.current_price || 0).toFixed(4)}</td>
                                <td className={`px-4 py-2 text-sm font-medium ${Number(pos.unrealized_pnl || 0) >= 0 ? 'text-green-600' : 'text-red-600'
                                    }`}>
                                    ${Number(pos.unrealized_pnl || 0).toFixed(2)}
                                </td>
                                <td className="px-4 py-2 text-sm text-gray-900">{(pos.entry_time ? new Date(pos.entry_time) : new Date()).toLocaleString()}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            <div className="flex items-center justify-between text-sm text-gray-600">
                <div>
                    Page {page} of {totalPages} ({positions.length} total positions)
                </div>
                <div className="flex items-center space-x-2">
                    <button
                        onClick={() => setPage(Math.max(1, page - 1))}
                        disabled={page <= 1}
                        className="px-3 py-1 border border-gray-300 rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                    >
                        <i className="fas fa-chevron-left mr-1"></i>Prev
                    </button>
                    <button
                        onClick={() => setPage(Math.min(totalPages, page + 1))}
                        disabled={page >= totalPages}
                        className="px-3 py-1 border border-gray-300 rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                    >
                        Next<i className="fas fa-chevron-right ml-1"></i>
                    </button>
                </div>
            </div>
        </div>
    );
}
