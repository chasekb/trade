'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useQueryClient } from '@tanstack/react-query';
import { useLiveTabProducer } from '@/hooks/useTrading';
import { firstLiveTabProducerBlocker, normalizeLiveTabProducerSnapshot } from '@/lib/liveTabProducer';

interface ManualTradeSectionProps {
  symbols: string[];
}

type ManualPosition = {
  symbol?: string;
  asset?: string;
  quantity?: number | string;
  balance_crypto?: number | string;
};

function isManualPosition(value: unknown): value is ManualPosition {
  return Boolean(value && typeof value === 'object');
}

function positionMatchesSymbol(position: ManualPosition, symbol: string): boolean {
  return position.symbol === symbol || position.asset === symbol.split('-')[0];
}

export function ManualTradeSection({ symbols }: ManualTradeSectionProps) {
  const queryClient = useQueryClient();
  const { data: producerData } = useLiveTabProducer(true);
  const producer = normalizeLiveTabProducerSnapshot(producerData ?? {});
  const portfolio = producerData?.portfolio ?? producerData;
  const [isVisible, setIsVisible] = useState(false);
  const [selectedSymbol, setSelectedSymbol] = useState(symbols[0] || 'BTC-USD');
  const [side, setSide] = useState<'buy' | 'sell'>('buy');
  const [amount, setAmount] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Update selected symbol if props change and current selection is invalid
  useEffect(() => {
    if (symbols.length > 0 && !symbols.includes(selectedSymbol)) {
      setSelectedSymbol(symbols[0]);
    }
  }, [symbols, selectedSymbol]);

  const getAvailableBalance = () => {
    if (!portfolio) return 0;
    
    if (side === 'buy') {
      // Return USD balance
      return Number(portfolio.cash_balance ?? portfolio.available_balance_usd ?? 0);
    } else {
      // Return Crypto balance for selected symbol
      const positions = portfolio.positions ?? portfolio.active_positions_data ?? [];
      
      let position: ManualPosition | undefined;
      if (Array.isArray(positions)) {
         position = positions.filter(isManualPosition).find((p) => positionMatchesSymbol(p, selectedSymbol));
      } else {
         const positionsBySymbol = positions as Record<string, unknown>;
         const directPosition = positionsBySymbol[selectedSymbol];
         position = isManualPosition(directPosition)
           ? directPosition
           : Object.values(positionsBySymbol).filter(isManualPosition).find((p) => positionMatchesSymbol(p, selectedSymbol));
      }
      
      if (position) {
          return Number(position.quantity ?? position.balance_crypto ?? 0);
      }
      return 0;
    }
  };

  const handleMaxClick = () => {
    const balance = getAvailableBalance();
    setAmount(balance.toString());
  };

  const handleExecute = async () => {
    setIsLoading(true);
    setMessage(null);
    try {
      const response = await fetch('/api/trading/live/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: selectedSymbol,
          side: side,
          amount: parseFloat(amount),
          amount_type: side === 'buy' ? 'quote' : 'base'
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || data.message || 'Trade failed');
      }

      setMessage({ type: 'success', text: data.message || 'Trade executed successfully' });
      setAmount('');
      queryClient.invalidateQueries({ queryKey: ['live-tab-producer'] });
      queryClient.invalidateQueries({ queryKey: ['live-portfolio-status'] });
    } catch (error: unknown) {
      setMessage({ type: 'error', text: error instanceof Error ? error.message : 'Trade failed' });
    } finally {
      setIsLoading(false);
    }
  };

  const availableBalance = getAvailableBalance();
  const balanceLabel = side === 'buy' ? 'USD Available' : `${selectedSymbol.split('-')[0]} Available`;
  const disabledReason = producer.canTrade ? null : firstLiveTabProducerBlocker(producer) || 'Live trading is not ready.';

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
            <CardTitle>Manual Trade Execution</CardTitle>
            <Button variant="secondary" size="sm" onClick={() => setIsVisible(!isVisible)}>
                {isVisible ? 'Hide' : 'Show'}
            </Button>
        </div>
      </CardHeader>
      {isVisible && (
          <CardContent className="space-y-4">
            {/* Symbol Selection */}
            <div className="space-y-2">
                <label className="block text-sm font-medium text-gray-700">Symbol</label>
                <select
                  value={selectedSymbol}
                  onChange={(e) => setSelectedSymbol(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2"
                >
                  {symbols.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
            </div>

            {/* Side Selection */}
            <div className="flex rounded-md shadow-sm" role="group">
              <button
                type="button"
                onClick={() => setSide('buy')}
                className={`px-4 py-2 text-sm font-medium border rounded-l-lg flex-1 ${
                  side === 'buy'
                    ? 'bg-green-600 text-white border-green-600'
                    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                }`}
              >
                Buy
              </button>
              <button
                type="button"
                onClick={() => setSide('sell')}
                className={`px-4 py-2 text-sm font-medium border rounded-r-lg flex-1 ${
                  side === 'sell'
                    ? 'bg-red-600 text-white border-red-600'
                    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                }`}
              >
                Sell
              </button>
            </div>

            {/* Balance Display */}
            <div className="flex justify-between text-sm text-gray-600">
                <span>{balanceLabel}:</span>
                <span className="font-medium cursor-pointer text-blue-600" onClick={handleMaxClick}>
                    {availableBalance.toFixed(side === 'buy' ? 2 : 6)}
                </span>
            </div>

            {/* Amount Input */}
            <div className="space-y-2">
                <label className="block text-sm font-medium text-gray-700">
                    Amount ({side === 'buy' ? 'USD' : selectedSymbol.split('-')[0]})
                </label>
                <div className="flex space-x-2">
                    <Input
                        type="number"
                        value={amount}
                        onChange={(e) => setAmount(e.target.value)}
                        placeholder={side === 'buy' ? "0.00" : "0.000000"}
                        className="flex-1"
                    />
                    <Button variant="secondary" onClick={handleMaxClick} size="sm">
                        Max
                    </Button>
                </div>
            </div>

            {/* Submit Button */}
            <Button
              onClick={handleExecute}
              disabled={Boolean(disabledReason) || isLoading || !amount || parseFloat(amount) <= 0 || parseFloat(amount) > availableBalance}
              className="w-full"
            >
              {isLoading ? 'Executing...' : `Execute ${side.toUpperCase()} Order`}
            </Button>
            {disabledReason && (
              <p className="text-sm text-yellow-800">{disabledReason}</p>
            )}

            {/* Message */}
            {message && (
                <div className={`p-3 rounded-md text-sm ${message.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
                    {message.text}
                </div>
            )}

          </CardContent>
      )}
    </Card>
  );
}
