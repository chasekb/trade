import React from 'react';
import { TradingStrategy } from '@/types/trading';

interface StrategySelectorProps {
    value: TradingStrategy;
    onChange: (strategy: TradingStrategy) => void;
    className?: string;
}

export function StrategySelector({ value, onChange, className = '' }: StrategySelectorProps) {
    const strategies: { value: TradingStrategy; label: string }[] = [
        { value: 'ml_enhanced_orderbook', label: 'ML-Enhanced Order Book' },
        { value: 'orderbook', label: 'Order Book Signals' },
        { value: 'sma', label: 'Simple Moving Average' },
        { value: 'ema', label: 'Exponential Moving Average' },
        { value: 'rsi', label: 'RSI Strategy' },
        { value: 'bollinger', label: 'Bollinger Bands' },
        { value: 'macd', label: 'MACD Strategy' },
        { value: 'stochastic', label: 'Stochastic Oscillator' },
        { value: 'fibonacci', label: 'Fibonacci Retracement' },
        { value: 'dca', label: 'Dollar Cost Average' },
        { value: 'buyandhold', label: 'Buy and Hold' },
    ];

    return (
        <div className={`space-y-2 ${className}`}>
            <label className="block text-sm font-medium text-gray-700">Trading Strategy</label>
            <select
                value={value}
                onChange={(e) => onChange(e.target.value as TradingStrategy)}
                className="w-full border border-gray-300 rounded-md px-3 py-2"
            >
                {strategies.map(strategy => (
                    <option key={strategy.value} value={strategy.value}>
                        {strategy.label}
                    </option>
                ))}
            </select>
        </div>
    );
}
