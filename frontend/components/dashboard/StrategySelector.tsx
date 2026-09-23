import React from 'react';
import { TradingStrategy } from '@/types/trading';

interface StrategySelectorProps {
    value: TradingStrategy;
    onChange: (strategy: TradingStrategy) => void;
    className?: string;
}

export function StrategySelector({ value, onChange, className = '' }: StrategySelectorProps) {
    const strategies: { value: TradingStrategy; label: string }[] = [
        { value: 'ml_enhanced_orderbook', label: 'ML-Enhanced Order Book (baseline; calibration deferred)' },
        { value: 'ml_orderbook_opportunity', label: 'ML Order Book (All Opportunities; calibration deferred)' },
        { value: 'orderbook', label: 'Order Book Signals (calibration deferred)' },
        { value: 'sma', label: 'Simple Moving Average (calibration deferred)' },
        { value: 'ema', label: 'Exponential Moving Average (calibration deferred)' },
        { value: 'rsi', label: 'RSI Strategy (calibration deferred)' },
        { value: 'bollinger', label: 'Bollinger Bands (calibration deferred)' },
        { value: 'macd', label: 'MACD Strategy (calibration deferred)' },
        { value: 'stochastic', label: 'Stochastic Oscillator (calibration deferred)' },
        { value: 'fibonacci', label: 'Fibonacci Retracement (calibration deferred)' },
        { value: 'dca', label: 'Dollar Cost Average (calibration deferred)' },
        { value: 'buyandhold', label: 'Buy and Hold (calibration deferred)' },
    ];

    return (
        <div className={`space-y-2 ${className}`}>
            <label className="block text-sm font-medium text-gray-700">Trading Strategy</label>
            <p className="text-xs text-amber-700">
                Calibration is deferred for every evaluated strategy. The selected option is an existing baseline only;
                no strategy or ranking mapping is promoted by calibration evidence.
            </p>
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
