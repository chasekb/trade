import React, { useState, useMemo } from 'react';
import { Button } from './Button';
import { Card, CardContent } from './Card';
import { ChevronUpIcon, ChevronDownIcon, ChevronLeftIcon, ChevronRightIcon } from 'lucide-react';
import { DataTableProps } from '@/types/trading';
import { cn } from '@/lib/utils';

export function DataTable<T extends object>({
  data,
  columns,
  loading = false,
  pagination,
  sorting,
  onRowClick,
  className,
}: DataTableProps<T>) {
  const [localSort, setLocalSort] = useState<{
    key: string;
    direction: 'asc' | 'desc';
  } | null>(null);

  const currentSort = sorting || localSort;

  const sortedData = useMemo(() => {
    if (!currentSort || !data) return data || [];

    return [...data].sort((a, b) => {
      const sortKey = currentSort.key as keyof T;
      const aVal = a[sortKey];
      const bVal = b[sortKey];

      let comparison = 0;
      if (aVal < bVal) comparison = -1;
      if (aVal > bVal) comparison = 1;

      return currentSort.direction === 'desc' ? comparison * -1 : comparison;
    });
  }, [data, currentSort]);

  const handleSort = (key: string) => {
    const newDirection: 'asc' | 'desc' =
      currentSort?.key === key && currentSort.direction === 'asc' ? 'desc' : 'asc';

    const newSort = { key, direction: newDirection };
    setLocalSort(newSort);

    if (sorting?.onSort) {
      sorting.onSort(key, newDirection);
    }
  };

  const handlePageChange = (page: number) => {
    if (pagination?.onPageChange) {
      pagination.onPageChange(page);
    }
  };

  if (loading) {
    return <DataTableSkeleton />;
  }

  return (
    <div className={cn('space-y-4', className)}>
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="border-b border-gray-200">
              <tr>
                {columns.map((column) => (
                  <th
                    key={String(column.key)}
                    className={cn(
                      'px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider',
                      column.sortable && 'cursor-pointer hover:bg-gray-50',
                      column.className
                    )}
                    onClick={column.sortable ? () => handleSort(String(column.key)) : undefined}
                  >
                    <div className="flex items-center space-x-1">
                      <span>{column.header}</span>
                      {column.sortable && currentSort?.key === column.key && (
                        <span className="ml-1">
                          {currentSort.direction === 'asc' ? (
                            <ChevronUpIcon className="h-4 w-4" />
                          ) : (
                            <ChevronDownIcon className="h-4 w-4" />
                          )}
                        </span>
                      )}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {sortedData.map((item, index) => (
                <tr
                  key={index}
                  className={cn(
                    'hover:bg-gray-50',
                    onRowClick && 'cursor-pointer'
                  )}
                  onClick={() => onRowClick?.(item)}
                >
                  {columns.map((column) => (
                    <td
                      key={String(column.key)}
                      className={cn('px-6 py-4 whitespace-nowrap text-sm text-gray-900', column.className)}
                    >
                      {column.render
                        ? column.render(item[column.key], item)
                        : String(item[column.key] || '')
                      }
                    </td>
                  ))}
                </tr>
              ))}
              {sortedData.length === 0 && (
                <tr>
                  <td colSpan={columns.length} className="px-6 py-4 text-center text-gray-500">
                    No data available
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {pagination && (
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => handlePageChange(pagination.currentPage - 1)}
              disabled={pagination.currentPage <= 1}
            >
              <ChevronLeftIcon className="h-4 w-4 mr-1" />
              Previous
            </Button>

            <span className="text-sm text-gray-700">
              Page {pagination.currentPage} of {pagination.totalPages}
            </span>

            <Button
              variant="outline"
              size="sm"
              onClick={() => handlePageChange(pagination.currentPage + 1)}
              disabled={pagination.currentPage >= pagination.totalPages}
            >
              Next
              <ChevronRightIcon className="h-4 w-4 ml-1" />
            </Button>
          </div>

          <div className="text-sm text-gray-500">
            {sortedData.length} items
          </div>
        </div>
      )}
    </div>
  );
}

function DataTableSkeleton() {
  return (
    <Card>
      <CardContent className="p-6">
        <div className="animate-pulse">
          <div className="space-y-4">
            <div className="h-4 bg-gray-200 rounded w-1/4"></div>
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="h-12 bg-gray-200 rounded"></div>
              ))}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
