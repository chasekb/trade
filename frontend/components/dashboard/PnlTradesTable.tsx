import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { DataTable } from '@/components/ui/DataTable';

interface PnlTradesTableProps {
  data: {
    top_trades: any[];
    bottom_trades: any[];
  };
  isLoading: boolean;
  error: Error | null;
}

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
    key: 'timestamp',
    header: 'Timestamp',
    render: (timestamp: number) => {
      const date = new Date(timestamp * 1000);
      return <div>{date.toLocaleString()}</div>;
    },
  },
];

export function PnlTradesTable({ data, isLoading, error }: PnlTradesTableProps) {
  if (isLoading) {
    return <div>Loading PnL trades...</div>;
  }

  if (error) {
    return <div className="text-red-600">Error: {error.message}</div>;
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Top 10 Trades by PnL</CardTitle>
        </CardHeader>
        <CardContent>
          <DataTable columns={columns} data={data?.top_trades || []} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Bottom 10 Trades by PnL</CardTitle>
        </CardHeader>
        <CardContent>
          <DataTable columns={columns} data={data?.bottom_trades || []} />
        </CardContent>
      </Card>
    </div>
  );
}
