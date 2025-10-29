"use client";

import { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { TradingStatisticsDashboard } from '@/components/dashboard/TradingStatisticsDashboard';
import LiveTradingPanel from '@/components/dashboard/LiveTradingPanel';
import BacktestingPanel from '@/components/dashboard/BacktestingPanel';
import MLAnalyticsDashboard from '@/components/dashboard/MLAnalyticsDashboard';
import { PositionsTable } from '@/components/dashboard/PositionsTable';
import { cn } from '@/lib/utils';

type TabType = 'overview' | 'live-trading' | 'positions' | 'backtesting' | 'ml-analytics';

export const dynamic = 'force-dynamic';

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<TabType>('overview');

  const tabs: Array<{ id: TabType; label: string; icon: string }> = [
    { id: 'overview', label: 'Overview', icon: 'fas fa-tachometer-alt' },
    { id: 'live-trading', label: 'Live Trading', icon: 'fas fa-play-circle' },
    { id: 'positions', label: 'Positions', icon: 'fas fa-wallet' },
    { id: 'backtesting', label: 'Backtesting', icon: 'fas fa-chart-bar' },
    { id: 'ml-analytics', label: 'ML Analytics', icon: 'fas fa-brain' },
  ];

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview':
        return <TradingStatisticsDashboard />;
      case 'live-trading':
        return <LiveTradingPanel />;
      case 'positions':
        return <PositionsTable />;
      case 'backtesting':
        return <BacktestingPanel />;
      case 'ml-analytics':
        return <MLAnalyticsDashboard />;
      default:
        return <TradingStatisticsDashboard />;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-gradient-to-r from-indigo-600 to-blue-600 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center space-x-3">
              <i className="fas fa-chart-line text-white text-3xl"></i>
              <div>
                <h1 className="text-white text-2xl font-bold">Advanced Trading Dashboard</h1>
                <p className="text-indigo-200 text-sm">Real-time Analytics & ML-Powered Trading</p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <Button variant="ghost" className="text-white hover:bg-white/10">
                <i className="fas fa-wifi mr-2"></i>Test API
              </Button>
              <span className="inline-flex items-center px-3 py-1 rounded-full text-sm bg-green-500 text-white">
                <span className="w-2 h-2 bg-white rounded-full mr-2 animate-pulse"></span>
                Connected
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Tab Navigation */}
      <nav className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex space-x-8 overflow-x-auto">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "flex items-center px-1 py-4 border-b-2 font-medium text-sm whitespace-nowrap transition-colors duration-200",
                  activeTab === tab.id
                    ? "border-indigo-500 text-indigo-600"
                    : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                )}
              >
                <i className={`${tab.icon} mr-2`}></i>
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="transition-all duration-300 ease-in-out">
          {renderTabContent()}
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex justify-between items-center">
            <p className="text-sm text-gray-500">
              Advanced Trading System v2.0 - Real-time trading insights powered by ML
            </p>
            <div className="flex items-center space-x-4 text-sm text-gray-500">
              <span>Last updated: {new Date().toLocaleString()}</span>
              <span>•</span>
              <span>Status: Operational</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
