import React from 'react';

export type RecentTradeRow = {
  timestamp?: string | number;
  symbol?: string;
  side?: string;
  quantity?: number | string;
  price?: number | string;
  pnl?: number | string;
  fee?: number | string;
  fees?: number | string;
};

interface RecentTradesTableProps {
  trades: RecentTradeRow[];
  includeFees?: boolean;
}

export function RecentTradesTable({ trades, includeFees = false }: RecentTradesTableProps) {
  return (
    <div className="space-y-4">
      <h4 className="font-semibold text-gray-700">Recent Trades</h4>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Time</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Symbol</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Side</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Quantity</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Price</th>
              {includeFees && (
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Fees</th>
              )}
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">P&amp;L</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {trades.map((trade: RecentTradeRow, index: number) => (
              <tr key={index}>
                <td className="px-4 py-2 text-sm text-gray-900">
                  {trade.timestamp ? new Date(trade.timestamp).toLocaleString() : '-'}
                </td>
                <td className="px-4 py-2 text-sm text-gray-900">{trade.symbol || '-'}</td>
                <td className="px-4 py-2 text-sm">
                  <span className={`px-2 py-1 rounded-full text-xs ${(trade.side || '').toUpperCase() === 'BUY'
                    ? 'bg-green-100 text-green-800'
                    : 'bg-red-100 text-red-800'
                    }`}>
                    {(trade.side || '').toUpperCase() || '-'}
                  </span>
                </td>
                <td className="px-4 py-2 text-sm text-gray-900">
                  {typeof trade.quantity === 'number' ? trade.quantity.toFixed(4) : trade.quantity || 0}
                </td>
                <td className="px-4 py-2 text-sm text-gray-900">
                  ${typeof trade.price === 'number' ? trade.price.toFixed(2) : trade.price || 0}
                </td>
                {includeFees && (
                  <td className="px-4 py-2 text-sm text-gray-900 text-red-600">
                    ${(() => {
                      const fee = trade.fees ?? trade.fee ?? 0;
                      return typeof fee === 'number' ? fee.toFixed(2) : fee;
                    })()}
                  </td>
                )}
                {(() => {
                  const tradePnl = Number(trade.pnl ?? 0);
                  return (
                    <td className={`px-4 py-2 text-sm font-medium ${tradePnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {tradePnl.toFixed(2)}
                    </td>
                  );
                })()}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}