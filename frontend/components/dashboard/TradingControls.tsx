import React from 'react';
import { Button } from '@/components/ui/Button';
import { TradingMode, TradingStrategy } from '@/types/trading';

interface TradingControlsProps {
    status: {
        isActive: boolean;
        mode?: TradingMode;
        strategy?: TradingStrategy;
        symbols?: string[];
    };
    onStart: () => Promise<void>;
    onStop: () => Promise<void>;
    loading?: boolean;
    className?: string;
}

export function TradingControls({ status, onStart, onStop, loading = false, className = '' }: TradingControlsProps) {
    return (
        <div className={`flex gap-3 ${className}`}>
            <Button
                onClick={onStart}
                disabled={loading || status.isActive}
                className="flex-1"
                variant={status.isActive ? 'secondary' : 'primary'}
            >
                {loading ? 'Starting...' : status.isActive ? 'Trading Active' : 'Start Trading'}
            </Button>
            <Button
                onClick={onStop}
                disabled={loading || !status.isActive}
                variant="danger"
                className="flex-1"
            >
                {loading ? 'Stopping...' : 'Stop Trading'}
            </Button>
        </div>
    );
}
