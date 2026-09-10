import React, { useState } from 'react';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { TradingStrategy } from '@/types/trading';
import { useStrategyParameters } from '@/hooks/useTrading';
import { useModelTraining } from '@/hooks/useModelTraining';
import { MLConfigForm } from './MLConfigForm';

type TradingConfigState = {
    position_size_mode: 'percent' | 'dollar' | string;
    position_size_value: number;
    initial_portfolio_size: number;
    use_batch_training?: boolean;
    training_model_type?: 'random_forest' | 'gradient_boosting' | 'transformer';
    training_model_name?: string;
    ml_server_url?: string;
    confidence_threshold?: number;
    order_prioritization?: string;
    fallback_to_baseline?: boolean;
    stop_loss_percent?: number;
    take_profit_percent?: number;
    [key: string]: string | number | boolean | undefined;
};

interface StrategyConfigFormProps {
    strategy: TradingStrategy;
    config: TradingConfigState;
    onChange: React.Dispatch<React.SetStateAction<TradingConfigState>>;
    className?: string;
    status: { isActive: boolean };
    updateStrategyParameters: (params: Record<string, string | number | boolean | undefined>) => void;
    showInitialPortfolioSize?: boolean;
}

export function StrategyConfigForm({ strategy, config, onChange, className = '', status, updateStrategyParameters, showInitialPortfolioSize = true }: StrategyConfigFormProps) {
    const { getStrategyParameters, getOrderBookPresets } = useStrategyParameters();
    const { availableModels, setActiveModel, trainModel, isTraining, isSettingActiveModel } = useModelTraining();
    const [selectedModel, setSelectedModel] = useState('');
    const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

    const handleSetActiveModel = () => {
        if (!selectedModel) return;
        setFeedback(null);
        setActiveModel(selectedModel, {
            onSuccess: (data: { message?: string }) => {
                setFeedback({ type: 'success', message: data.message || 'Model activated successfully' });
            },
            onError: (error: { message?: string }) => {
                setFeedback({ type: 'error', message: error.message || 'Failed to set active model' });
            },
        });
    };

    const [selectedPreset, setSelectedPreset] = useState('aggressive');
    const [trainingFeedback, setTrainingFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

    const handleTrainModel = () => {
        setTrainingFeedback(null);
        const batchTraining = config.use_batch_training !== false; // Default to true
        const modelType = (config.training_model_type as 'random_forest' | 'gradient_boosting' | 'transformer' | undefined) || 'random_forest';
        const modelName = typeof config.training_model_name === 'string' ? config.training_model_name : 'default_model';
        trainModel({
            batchTraining,
            autoSetActive: true,
            modelType,
            modelName,
        }, {
            onSuccess: (data: { message?: string }) => {
                setTrainingFeedback({ type: 'success', message: data.message || 'Model training started successfully' });
            },
            onError: (error: { message?: string }) => {
                setTrainingFeedback({ type: 'error', message: error.message || 'Failed to start model training' });
            },
        });
    };

    const parameters = getStrategyParameters(strategy);
    const presets = getOrderBookPresets();

    const applyPreset = (presetName: string) => {
        if ((strategy === 'orderbook' || strategy === 'ml_enhanced_orderbook') && presetName in presets) {
            const typeSafePresetName = presetName as keyof typeof presets;
            const presetConfig = presets[typeSafePresetName];
            onChange({ ...config, ...presetConfig });
            setSelectedPreset(presetName);
        } else if (presetName !== 'custom') {
            setFeedback({ type: 'error', message: `Order-book preset '${presetName}' is not supported by ${strategy}.` });
        }
    };


    const handleParameterChange = (name: string, value: string | number | boolean) => {
        const newConfig = { ...config, [name]: value };
        onChange(newConfig);
        if (status.isActive) {
            const updates: Record<string, string | number | boolean | undefined> = { [name]: value };
            // The backend sizes percent mode from position_size_percent, so keep
            // that read-key in sync whenever the sizing mode or value changes.
            if (name === 'position_size_value' || name === 'position_size_mode') {
                const mode = name === 'position_size_mode' ? value : (newConfig.position_size_mode || 'percent');
                updates.position_size_mode = mode as string;
                updates.position_size_value = newConfig.position_size_value;
                if (mode === 'percent' && typeof newConfig.position_size_value === 'number') {
                    updates.position_size_percent = newConfig.position_size_value;
                }
            }
            updateStrategyParameters(updates);
        }
    };

    const getConfigValue = (value: unknown, fallback: string | number): string | number => {
        return typeof value === 'string' || typeof value === 'number' ? value : fallback;
    };

    const getConfigBoolean = (value: unknown, fallback: boolean): boolean => {
        return typeof value === 'boolean' ? value : fallback;
    };

    return (
        <div className={`space-y-4 ${className}`}>
            {strategy === 'ml_enhanced_orderbook' && (
                <div className="p-4 bg-gray-50 rounded-lg space-y-4">
                    <h4 className="text-md font-semibold text-gray-700">ML Configuration</h4>
                    <div className="space-y-2">
                        <label className="block text-sm font-medium text-gray-700">Available Models</label>
                        <div className="flex items-center space-x-2">
                            <select
                                value={selectedModel}
                                onChange={(e) => setSelectedModel(e.target.value)}
                                className="w-full border border-gray-300 rounded-md px-3 py-2"
                            >
                                {(availableModels ?? [])
                                    .sort((a: { trained_at: string }, b: { trained_at: string }) => new Date(b.trained_at).getTime() - new Date(a.trained_at).getTime())
                                    .map((model: { model_id: string; trained_at: string }, index: number) => {
                                        // Auto-select the first model if none is selected
                                        if (index === 0 && !selectedModel) {
                                            setTimeout(() => setSelectedModel(model.model_id), 0);
                                        }
                                        return (
                                            <option key={model.model_id} value={model.model_id}>
                                                {model.model_id} ({new Date(model.trained_at).toLocaleDateString()})
                                            </option>
                                        );
                                    })}
                            </select>
                            <Button onClick={handleSetActiveModel} disabled={!selectedModel || isSettingActiveModel}>
                                {isSettingActiveModel ? 'Setting...' : 'Set Active'}
                            </Button>
                        </div>
                        {feedback && (
                            <div className={`mt-2 text-sm ${feedback.type === 'success' ? 'text-green-600' : 'text-red-600'}`}>
                                {feedback.message}
                            </div>
                        )}
                    </div>
                    <div className="space-y-2">
                        <div className="flex items-center justify-between">
                            <label className="block text-sm font-medium text-gray-700">Model Training</label>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">Model Type</label>
                                <select
                                    value={config.training_model_type || 'random_forest'}
                                    onChange={(e) => handleParameterChange('training_model_type', e.target.value)}
                                    className="w-full border border-gray-300 rounded-md px-3 py-2"
                                >
                                    <option value="random_forest">Random Forest</option>
                                    <option value="gradient_boosting">Gradient Boosting</option>
                                    <option value="transformer">Transformer</option>
                                </select>
                            </div>
                            <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">Model Name</label>
                                <Input
                                    type="text"
                                    value={config.training_model_name || 'default_model'}
                                    onChange={(e) => handleParameterChange('training_model_name', e.target.value)}
                                    className="w-full"
                                />
                            </div>
                        </div>
                        <div className="flex items-center space-x-2 mb-2">
                            <input
                                type="checkbox"
                                id="use_batch_training"
                                checked={getConfigBoolean(config.use_batch_training, true)}
                                onChange={(e) => handleParameterChange('use_batch_training', e.target.checked)}
                            />
                            <label htmlFor="use_batch_training" className="text-sm font-medium text-gray-700">
                                Use Batch Training (Memory Efficient)
                            </label>
                        </div>
                        <Button onClick={handleTrainModel} disabled={isTraining}>
                            {isTraining ? 'Training...' : 'Train New Model'}
                        </Button>
                        {trainingFeedback && (
                            <div className={`mt-2 text-sm ${trainingFeedback.type === 'success' ? 'text-green-600' : 'text-red-600'}`}>
                                {trainingFeedback.message}
                            </div>
                        )}
                    </div>


                    <div className="space-y-2">
                        <label className="block text-sm font-medium text-gray-700">ML Server URL</label>
                        <Input
                            type="text"
                            value={config.ml_server_url || 'http://localhost:8002'}
                            onChange={(e) => handleParameterChange('ml_server_url', e.target.value)}
                            className="w-full"
                        />
                    </div>
                    <div className="space-y-2">
                        <label className="block text-sm font-medium text-gray-700">Confidence Threshold</label>
                        <Input
                            type="number"
                            min={0}
                            max={1}
                            step={0.1}
                            value={config.confidence_threshold || 0.6}
                            onChange={(e) => handleParameterChange('confidence_threshold', Number(e.target.value))}
                            className="w-full"
                        />
                    </div>
                    <div className="space-y-2">
                        <label className="block text-sm font-medium text-gray-700">Order Prioritization</label>
                        <select
                            value={config.order_prioritization || 'signal_strength'}
                            onChange={(e) => handleParameterChange('order_prioritization', e.target.value)}
                            className="w-full border border-gray-300 rounded-md px-3 py-2"
                        >
                            <option value="signal_strength">Signal Strength</option>
                            <option value="win_probability">Win Probability</option>
                            <option value="expected_return">Expected Return (Descending)</option>
                            <option value="none">No Prioritization (Immediate Execution)</option>
                        </select>
                    </div>
                    <div className="flex items-center space-x-2">
                        <input
                            type="checkbox"
                            id="fallback_to_baseline"
                            checked={getConfigBoolean(config.fallback_to_baseline, true)}
                            onChange={(e) => handleParameterChange('fallback_to_baseline', e.target.checked)}
                        />
                        <label htmlFor="fallback_to_baseline" className="text-sm font-medium text-gray-700">
                            Fallback to Baseline Strategy
                        </label>
                    </div>
                    <MLConfigForm />
                </div>
            )}
            {(strategy === 'orderbook' || strategy === 'ml_enhanced_orderbook') && (
                <div className="p-4 bg-gray-50 rounded-lg">
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                        Configuration Preset
                    </label>
                    <select
                        value={selectedPreset}
                        onChange={(e) => {
                            const presetName = e.target.value;
                            setSelectedPreset(presetName);
                            applyPreset(presetName);
                        }}
                        className="w-full border border-gray-300 rounded-md px-3 py-2 mb-3"
                    >
                        <option value="custom">Custom Configuration</option>
                        <option value="conservative">Conservative (Few High-Quality Signals)</option>
                        <option value="moderate">Moderate (Balanced Signals)</option>
                        <option value="aggressive">Aggressive (More Signals) - Recommended</option>
                        <option value="very-aggressive">Very Aggressive (Maximum Signals)</option>
                    </select>
                    <p className="text-xs text-gray-500">
                        Select a preset to automatically configure order-book risk controls, max positions, and fee/slippage profitability hurdles.
                    </p>
                </div>
            )}

            {parameters.length > 0 && (
                <div className="space-y-4">
                    <h4 className="text-md font-semibold text-gray-700">Strategy Parameters</h4>
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        {parameters.map(param => (
                            <div key={param.name} className="space-y-2">
                                <label className="block text-sm font-medium text-gray-700">
                                    {param.label}
                                </label>
                                {param.type === 'select' ? (
                                    <select
                                        value={getConfigValue(config[param.name], param.default)}
                                        onChange={(e) => handleParameterChange(param.name, e.target.value)}
                                        className="w-full border border-gray-300 rounded-md px-3 py-2"
                                    >
                                        {param.options?.map(option => (
                                            <option key={option} value={option}>
                                                {option.charAt(0).toUpperCase() + option.slice(1)}
                                            </option>
                                        ))}
                                    </select>
                                ) : (
                                    <Input
                                        type={param.type}
                                        value={getConfigValue(config[param.name], param.default)}
                                        onChange={(e) => handleParameterChange(param.name, e.target.value)}
                                        min={param.min}
                                        max={param.max}
                                        step={('step' in param) ? param.step : undefined}
                                        className="w-full"
                                    />
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Risk Settings: Max Position Size */}
            <div className="space-y-3 p-4 bg-gray-50 rounded-lg">
                <h4 className="text-md font-semibold text-gray-700">Risk Settings</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 items-end">
                    {showInitialPortfolioSize && (
                        <div className="space-y-2">
                            <label className="block text-sm font-medium text-gray-700">Initial Portfolio Size ($)</label>
                            <Input
                                type="number"
                                min={1}
                                step={100}
                                value={getConfigValue(config.initial_portfolio_size, 10000)}
                                onChange={(e) => handleParameterChange('initial_portfolio_size', Number(e.target.value))}
                                className="w-full"
                            />
                        </div>
                    )}

                    <div className="space-y-2">
                        <label className="block text-sm font-medium text-gray-700">Position Size Mode</label>
                        <select
                            value={(config.position_size_mode as string) || 'percent'}
                            onChange={(e) => handleParameterChange('position_size_mode', e.target.value)}
                            className="w-full border border-gray-300 rounded-md px-3 py-2"
                        >
                            <option value="percent">Percent of portfolio value</option>
                            <option value="dollar">Fixed dollar amount</option>
                        </select>
                    </div>

                    <div className="space-y-2">
                        <label className="block text-sm font-medium text-gray-700">Position Size Value</label>
                        <Input
                            type="number"
                            min={0}
                            step={1}
                            value={getConfigValue(config.position_size_value, config.position_size_mode === 'percent' ? 1 : 100)}
                            onChange={(e) => handleParameterChange('position_size_value', Number(e.target.value))}
                            className="w-full"
                        />
                    </div>
                    <div className="text-xs text-gray-500">
                        {(config.position_size_mode || 'percent') === 'percent'
                            ? 'Example: 1 means 1% of current portfolio value per position (compounds)'
                            : 'Example: 250 means allocate $250 per position'}
                    </div>

                    <div className="space-y-2">
                        <label className="block text-sm font-medium text-gray-700">Stop Loss (%)</label>
                        <Input
                            type="number"
                            min={0}
                            step={0.1}
                            placeholder="0 (Disabled)"
                            value={getConfigValue(config.stop_loss_percent, '')}
                            onChange={(e) => handleParameterChange('stop_loss_percent', Number(e.target.value))}
                            className="w-full"
                        />
                    </div>

                    <div className="space-y-2">
                        <label className="block text-sm font-medium text-gray-700">Take Profit (%)</label>
                        <Input
                            type="number"
                            min={0}
                            step={0.1}
                            placeholder="0 (Disabled)"
                            value={getConfigValue(config.take_profit_percent, '')}
                            onChange={(e) => handleParameterChange('take_profit_percent', Number(e.target.value))}
                            className="w-full"
                        />
                    </div>
                </div>
                {strategy === 'ml_enhanced_orderbook' && (
                    <p className="text-xs text-gray-500">
                        ML-enhanced order-book sessions use expected return after round-trip fees, slippage, and spread to skip simulated trades below the configured minimum net P&L, unless explicitly allowed.
                    </p>
                )}
            </div>
        </div>
    );
}
