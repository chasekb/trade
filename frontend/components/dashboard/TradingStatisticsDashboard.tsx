import React from 'react';
import { DashboardGrid } from '@/components/layout/DashboardGrid';
import { StatCard } from './StatCard';
import { useTradingStats } from '@/hooks/useTradingData';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { cn } from '@/lib/utils';

export function TradingStatisticsDashboard() {
  const { data: stats, isLoading, error } = useTradingStats();

  if (error) {
    return (
      <Card className="border-red-200 bg-red-50">
        <CardContent className="p-6">
          <div className="text-center">
            <p className="text-red-800 font-medium">Failed to load trading statistics</p>
            <p className="text-red-600 text-sm mt-1">{error.message}</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (isLoading || !stats) {
    return <TradingStatsSkeleton />;
  }

  return (
    <div className="space-y-6">
      {/* Main Performance Metrics */}
      <DashboardGrid>
        <StatCard
          title="Net P&L"
          value={stats.net_pnl}
          format="currency"
          className={cn(
            stats.net_pnl >= 0 ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'
          )}
        />
        <StatCard title="Win Rate" value={stats.win_rate} format="percentage" />
        <StatCard title="Total Trades" value={stats.total_trades} format="number" />
        <StatCard
          title="Profit Factor"
          value={stats.profit_factor >= 999 ? '∞' : stats.profit_factor}
          format="number"
          className="border-blue-200 bg-blue-50"
        />
      </DashboardGrid>

      {/* Trade Analysis */}
      <Card>
        <CardHeader>
          <CardTitle>Trade Analysis</CardTitle>
        </CardHeader>
        <CardContent>
          <DashboardGrid>
            <StatCard title="Winning Trades" value={stats.winning_trades} format="number" />
            <StatCard title="Losing Trades" value={stats.losing_trades} format="number" />
            <StatCard title="Avg Win" value={stats.avg_win} format="currency" />
            <StatCard title="Avg Loss" value={stats.avg_loss} format="currency" />
          </DashboardGrid>
        </CardContent>
      </Card>

      {/* Performance Metrics */}
      <Card>
        <CardHeader>
          <CardTitle>Performance Metrics</CardTitle>
        </CardHeader>
        <CardContent>
          <DashboardGrid>
            <StatCard title="Best Trade" value={stats.best_trade} format="currency" />
            <StatCard title="Worst Trade" value={stats.worst_trade} format="currency" />
            <StatCard title="Sharpe Ratio" value={stats.sharpe_ratio} format="number" />
            <StatCard
              title="Max Drawdown"
              value={stats.max_drawdown}
              format="currency"
              className="border-orange-200 bg-orange-50"
            />
          </DashboardGrid>
        </CardContent>
      </Card>

      {/* Trading Volume & Activity */}
      <Card>
        <CardHeader>
          <CardTitle>Trading Volume & Activity</CardTitle>
        </CardHeader>
        <CardContent>
          <DashboardGrid>
            <StatCard title="Total Volume" value={stats.total_volume} format="currency" />
            <StatCard title="Avg Trade Size" value={stats.avg_trade_size} format="currency" />
            <StatCard title="Trades Today" value={stats.trades_today} format="number" />
            <StatCard title="Total Fees" value={stats.total_fees} format="currency" />
          </DashboardGrid>
        </CardContent>
      </Card>

      {/* Additional Info */}
      {stats.last_trade_time && (
        <Card className="border-gray-200">
          <CardContent className="p-4">
            <div className="text-center text-sm text-muted-foreground">
              Last Trade: {new Date(stats.last_trade_time).toLocaleString()}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function TradingStatsSkeleton() {
  return (
    <div className="space-y-6">
      <DashboardGrid>
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i} className="animate-pulse">
            <CardContent className="p-6">
              <div className="space-y-2">
                <div className="h-4 bg-gray-200 rounded w-20"></div>
                <div className="h-8 bg-gray-200 rounded w-24"></div>
              </div>
            </CardContent>
          </Card>
        ))}
      </DashboardGrid>

      {Array.from({ length: 3 }).map((_, i) => (
        <Card key={i} className="animate-pulse">
          <CardContent className="p-6">
            <div className="h-6 bg-gray-200 rounded w-40 mb-4"></div>
            <DashboardGrid>
              {Array.from({ length: 4 }).map((_, j) => (
                <div key={j} className="space-y-2">
                  <div className="h-4 bg-gray-200 rounded w-20"></div>
                  <div className="h-8 bg-gray-200 rounded w-24"></div>
                </div>
              ))}
            </DashboardGrid>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
