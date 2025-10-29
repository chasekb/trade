import React, { useState, useMemo } from 'react';
import { DataTable } from '@/components/ui/DataTable';
import { usePositions } from '@/hooks/useTradingData';
import { Position, DataTableColumn } from '@/types/trading';
import { cn } from '@/lib/utils';

const ITEMS_PER_PAGE = 50;

export function PositionsTable() {
  const [currentPage, setCurrentPage] = useState(1);
  const [sortConfig, setSortConfig] = useState<{
    key: string;
    direction: 'asc' | 'desc';
  }>({ key: 'unrealized_pnl', direction: 'desc' });

  const { data: response, isLoading, error } = usePositions({
    page: currentPage,
    limit: ITEMS_PER_PAGE,
    sort_by: sortConfig.key,
    sort_order: sortConfig.direction,
  });

  const positions = response?.data || [];
  const pagination = response?.pagination;

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
  };

  const handleSort = (key: string, direction: 'asc' | 'desc') => {
    setSortConfig({ key, direction });
    setCurrentPage(1); // Reset to first page when sorting changes
  };

  const positionColumns: DataTableColumn<Position>[] = [
    {
      key: 'symbol',
      header: 'Symbol',
      sortable: true,
      className: 'font-medium text-gray-900',
    },
    {
      key: 'quantity',
      header: 'Quantity',
      sortable: true,
      render: (value) => value.toLocaleString(),
      className: 'text-right',
    },
    {
      key: 'entry_price',
      header: 'Entry Price',
      sortable: true,
      render: (value) => `$${value.toFixed(2)}`,
      className: 'text-right',
    },
    {
      key: 'current_price',
      header: 'Current Price',
      sortable: true,
      render: (value) => `$${value.toFixed(2)}`,
      className: 'text-right',
    },
    {
      key: 'unrealized_pnl',
      header: 'P&L',
      sortable: true,
      render: (value, item) => (
        <div className="flex flex-col">
          <span
            className={cn(
              'font-medium',
              value >= 0 ? 'text-green-600' : 'text-red-600'
            )}
          >
            {value >= 0 ? '+' : ''}${value.toFixed(2)}
          </span>
          <span className="text-xs text-gray-500">
            ({item.pnl_percentage >= 0 ? '+' : ''}{item.pnl_percentage.toFixed(2)}%)
          </span>
        </div>
      ),
      className: 'text-right',
    },
    {
      key: 'entry_time',
      header: 'Entry Time',
      sortable: true,
      render: (value) => new Date(value).toLocaleString(),
      className: 'text-right',
    },
  ];

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-md p-4">
        <div className="flex">
          <div className="flex-shrink-0">
            <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-red-800">
              Failed to load positions
            </h3>
            <div className="mt-2 text-sm text-red-700">
              <p>{error.message}</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-medium text-gray-900">Open Positions</h3>
        <p className="mt-1 text-sm text-gray-500">
          Current open trading positions with real-time P&L updates
        </p>
      </div>

      {pagination ? (
        <DataTable
          data={positions}
          columns={positionColumns}
          loading={isLoading}
          pagination={{
            currentPage: pagination.page,
            totalPages: pagination.total_pages,
            onPageChange: handlePageChange,
          }}
          sorting={{
            key: sortConfig.key,
            direction: sortConfig.direction,
            onSort: handleSort,
          }}
          className="w-full"
        />
      ) : (
        <DataTable
          data={positions}
          columns={positionColumns}
          loading={isLoading}
          sorting={{
            key: sortConfig.key,
            direction: sortConfig.direction,
            onSort: handleSort,
          }}
          className="w-full"
        />
      )}

      {!isLoading && positions.length === 0 && (
        <div className="text-center py-8">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900">No open positions</h3>
          <p className="mt-1 text-sm text-gray-500">There are currently no open trading positions.</p>
        </div>
      )}
    </div>
  );
}
