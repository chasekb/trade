import React, { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { DataTable } from '@/components/ui/DataTable';

export interface OrderBookData {
  bids: Array<[price: number, size: number]>;
  asks: Array<[price: number, size: number]>;
  timestamp?: string;
}

interface OrderBookTableProps {
  symbol: string;
  bids: Array<[price: number, size: number]>;
  asks: Array<[price: number, size: number]>;
  maxRows?: number;
  className?: string;
  lastUpdate?: string;
}

/**
 * Real-time order book component displaying bids and asks in a table format
 * Uses WebSocket connections for live streaming data updates
 */
export function OrderBookTable({
  symbol,
  bids,
  asks,
  maxRows = 10,
  className = '',
  lastUpdate
}: OrderBookTableProps) {
  // Process and limit the data
  const processedData = useMemo(() => {
    const limitedBids = bids.slice(0, maxRows).map(([price, size], index) => ({
      id: `bid-${index}`,
      side: 'bid' as const,
      price,
      size,
      total: (price * size)
    }));

    const limitedAsks = asks.slice(0, maxRows).map(([price, size], index) => ({
      id: `ask-${index}`,
      side: 'ask' as const,
      price,
      size,
      total: (price * size)
    }));

    // Combined data with asks in reverse order for typical L2 display
    return [...limitedBids, ...limitedAsks.reverse()];
  }, [bids, asks, maxRows]);

  const spread = useMemo(() => {
    if (bids.length > 0 && asks.length > 0) {
      const bestBid = bids[0][0];
      const bestAsk = asks[0][0];
      const spread = bestAsk - bestBid;
      const spreadPercent = (spread / bestBid) * 100;
      return { value: spread, percentage: spreadPercent };
    }
    return null;
  }, [bids, asks]);

  const columns = [
    {
      key: 'side',
      header: 'Side',
      render: (value: 'bid' | 'ask') => (
        <span className={`px-2 py-1 rounded text-xs font-medium ${
          value === 'bid'
            ? 'bg-green-100 text-green-800'
            : 'bg-red-100 text-red-800'
        }`}>
          {value.toUpperCase()}
        </span>
      )
    },
    {
      key: 'price',
      header: 'Price',
      render: (value: number) => (
        <span className="font-mono text-sm">
          ${value.toFixed(2)}
        </span>
      )
    },
    {
      key: 'size',
      header: 'Size',
      render: (value: number) => (
        <span className="font-mono text-sm">
          {value.toLocaleString()}
        </span>
      )
    },
    {
      key: 'total',
      header: 'Total',
      render: (value: number) => (
        <span className="font-mono text-sm text-gray-600">
          ${value.toFixed(2)}
        </span>
      )
    }
  ];

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">
            Order Book - {symbol}
          </CardTitle>
          <div className="flex items-center space-x-2">
            <div className="flex items-center space-x-1">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
              <span className="text-sm text-gray-600">Live</span>
            </div>
            {lastUpdate && (
              <span className="text-xs text-gray-500">
                Updated: {new Date(lastUpdate).toLocaleTimeString()}
              </span>
            )}
          </div>
        </div>

        {spread && (
          <div className="flex items-center space-x-4 text-sm">
            <div>
              <span className="text-gray-600">Spread: </span>
              <span className="font-mono">
                ${spread.value.toFixed(2)} ({spread.percentage.toFixed(2)}%)
              </span>
            </div>
            <div>
              <span className="text-gray-600">Best Bid: </span>
              <span className="font-mono text-green-600">
                ${bids[0]?.[0]?.toFixed(2) || 'N/A'}
              </span>
            </div>
            <div>
              <span className="text-gray-600">Best Ask: </span>
              <span className="font-mono text-red-600">
                ${asks[0]?.[0]?.toFixed(2) || 'N/A'}
              </span>
            </div>
          </div>
        )}
      </CardHeader>

      <CardContent>
        {processedData.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-2"></div>
            Waiting for order book data...
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Bids Side */}
            <div>
              <h3 className="text-sm font-medium text-green-700 mb-2">Bids</h3>
              <div className="space-y-1">
                {processedData
                  .filter(row => row.side === 'bid')
                  .map((row, index) => (
                    <div
                      key={row.id}
                      className={`flex justify-between items-center p-2 rounded text-sm ${
                        index === 0 ? 'bg-green-50 border border-green-200' : 'hover:bg-gray-50'
                      }`}
                    >
                      <span className="font-mono text-green-600">
                        ${row.price.toFixed(2)}
                      </span>
                      <span className="text-gray-600">
                        {row.size.toLocaleString()}
                      </span>
                      <span className="text-gray-500 text-xs">
                        ${row.total.toFixed(0)}
                      </span>
                    </div>
                  ))}
              </div>
            </div>

            {/* Asks Side */}
            <div>
              <h3 className="text-sm font-medium text-red-700 mb-2">Asks</h3>
              <div className="space-y-1">
                {processedData
                  .filter(row => row.side === 'ask')
                  .map((row, index) => (
                    <div
                      key={row.id}
                      className={`flex justify-between items-center p-2 rounded text-sm ${
                        index === processedData.filter(r => r.side === 'ask').length - 1
                          ? 'bg-red-50 border border-red-200'
                          : 'hover:bg-gray-50'
                      }`}
                    >
                      <span className="font-mono text-red-600">
                        ${row.price.toFixed(2)}
                      </span>
                      <span className="text-gray-600">
                        {row.size.toLocaleString()}
                      </span>
                      <span className="text-gray-500 text-xs">
                        ${row.total.toFixed(0)}
                      </span>
                    </div>
                  ))}
              </div>
            </div>
          </div>
        )}

        {processedData.length > 0 && (
          <div className="mt-4 text-xs text-gray-500 text-center">
            Showing top {maxRows} levels • Total bids: {bids.length} • Total asks: {asks.length}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

interface OrderBookProps {
  symbol: string;
  className?: string;
}

/**
 * Main OrderBook component with WebSocket integration
 * Automatically connects to WebSocket and subscribes to real-time order book data
 */
export default function OrderBook({ symbol, className }: OrderBookProps) {
  const { orderBook, connected, lastUpdate } = useRealTimeOrderBook(symbol);

  const isConnected = connected && orderBook.bids.length > 0 && orderBook.asks.length > 0;

  return (
    <div className={className}>
      {!isConnected && (
        <Card className="mb-4">
          <CardContent className="py-6">
            <div className="text-center">
              <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm ${
                connected ? 'bg-yellow-100 text-yellow-800' : 'bg-gray-100 text-gray-800'
              }`}>
                <div className={`w-2 h-2 rounded-full mr-2 ${
                  connected ? 'bg-yellow-500' : 'bg-gray-500'
                }`}></div>
                {connected ? 'Connected - Waiting for data...' : 'Connecting to WebSocket...'}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <OrderBookTable
        symbol={symbol}
        bids={orderBook.bids}
        asks={orderBook.asks}
        lastUpdate={lastUpdate || undefined}
      />
    </div>
  );
}

// Import the hook at the end to avoid circular dependencies
import { useRealTimeOrderBook } from '@/hooks/useWebSocket';
