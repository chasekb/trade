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
    onStart: () => void;
    onStop: () => void;
    loading?: boolean;
    className?: string;
    startDisabledReason?: string | null;
}

export function TradingControls({ status, onStart, onStop, loading = false, className = '', startDisabledReason = null }: TradingControlsProps) {
    const startDisabled = loading || status.isActive || Boolean(startDisabledReason);
    return (
        <div className={className}>
            <div className="flex gap-3">
                <Button
                    onClick={onStart}
                    disabled={startDisabled}
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
            {startDisabledReason && !status.isActive && (
                <p className="mt-2 text-sm text-yellow-800">{startDisabledReason}</p>
            )}
        </div>
    );
}
