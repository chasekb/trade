import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { DataTable } from '@/components/ui/DataTable';
import { useMLAnalytics } from '@/hooks/useMLAnalytics';

const columns = [
  {
    key: 'symbol',
    header: 'Symbol',
  },
  {
    key: 'side',
    header: 'Side',
  },
  {
    key: 'pnl',
    header: 'PnL',
    render: (pnl: number) => {
      const formatted = new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
      }).format(pnl);
      const textColor = pnl >= 0 ? 'text-green-600' : 'text-red-600';
      return <div className={textColor}>{formatted}</div>;
    },
  },
  {
    key: 'pnl_percent',
    header: 'PnL %',
    render: (pnlPercent: number) => {
      const formatted = `${pnlPercent.toFixed(2)}%`;
      const textColor = pnlPercent >= 0 ? 'text-green-600' : 'text-red-600';
      return <div className={textColor}>{formatted}</div>;
    },
  },
  {
    key: 'timestamp',
    header: 'Timestamp',
    render: (timestamp: number | string) => {
      // Accept epoch seconds, epoch milliseconds, or ISO strings.
      const date = typeof timestamp === 'number'
        ? new Date(timestamp < 1e12 ? timestamp * 1000 : timestamp)
        : new Date(timestamp);
      return <div>{Number.isNaN(date.getTime()) ? '-' : date.toLocaleString()}</div>;
    },
  },
];

export function PnlTradesTable() {
  const { pnlTrades, isPnlLoading, pnlError, sortBy, setSortBy } = useMLAnalytics();

  if (isPnlLoading) {
    return <div>Loading PnL trades...</div>;
  }

  if (pnlError) {
    return <div className="text-red-600">Error: {pnlError.message}</div>;
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Top 10 Trades</CardTitle>
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
            <option value="pnl">Sort by PnL</option>
            <option value="pnl_percent">Sort by PnL %</option>
          </select>
        </CardHeader>
        <CardContent>
          <DataTable columns={columns} data={pnlTrades?.top_trades || []} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Bottom 10 Trades</CardTitle>
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
            <option value="pnl">Sort by PnL</option>
            <option value="pnl_percent">Sort by PnL %</option>
          </select>
        </CardHeader>
        <CardContent>
          <DataTable columns={columns} data={pnlTrades?.bottom_trades || []} />
        </CardContent>
      </Card>
    </div>
  );
}
