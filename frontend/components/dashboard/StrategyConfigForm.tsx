import React, { useState, useEffect } from 'react';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { TradingStrategy } from '@/types/trading';
import { useStrategyParameters } from '@/hooks/useTrading';
import { useModelTraining } from '@/hooks/useModelTraining';
import { MLConfigForm } from './MLConfigForm';

interface StrategyConfigFormProps {
    strategy: TradingStrategy;
    config: Record<string, any>;
    onChange: (config: Record<string, any>) => void;
    className?: string;
    status: { isActive: boolean };
    updateStrategyParameters: (params: Record<string, any>) => void;
}

export function StrategyConfigForm({ strategy, config, onChange, className = '', status, updateStrategyParameters }: StrategyConfigFormProps) {
    const { getStrategyParameters, getOrderBookPresets } = useStrategyParameters();
    const { availableModels, setActiveModel, trainModel, isTraining, isSettingActiveModel } = useModelTraining();
    const [selectedModel, setSelectedModel] = useState('');
    const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

    const handleSetActiveModel = () => {
        if (!selectedModel) return;
        setFeedback(null);
        setActiveModel(selectedModel, {
            onSuccess: (data: any) => {
                setFeedback({ type: 'success', message: data.message || 'Model activated successfully' });
            },
            onError: (error: any) => {
                setFeedback({ type: 'error', message: error.message || 'Failed to set active model' });
            },
        });
    };

    const [selectedPreset, setSelectedPreset] = useState('aggressive');
    const [trainingFeedback, setTrainingFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

    const handleTrainModel = () => {
        setTrainingFeedback(null);
        const batchTraining = config.use_batch_training !== false; // Default to true
        trainModel(batchTraining, {
            onSuccess: (data: any) => {
                setTrainingFeedback({ type: 'success', message: data.message || 'Model training started successfully' });
            },
            onError: (error: any) => {
                setTrainingFeedback({ type: 'error', message: error.message || 'Failed to start model training' });
            },
        });
    };

    const parameters = getStrategyParameters(strategy);
    const presets = getOrderBookPresets();

    const applyPreset = (presetName: string) => {
        if (strategy === 'orderbook' && presetName in presets) {
            const typeSafePresetName = presetName as keyof typeof presets;
            const presetConfig = presets[typeSafePresetName];
            onChange({ ...config, ...presetConfig });
            setSelectedPreset(presetName);
        }
    };

    useEffect(() => {
        applyPreset(selectedPreset);
    }, [strategy]);

    const handleParameterChange = (name: string, value: any) => {
        const newConfig = { ...config, [name]: value };
        onChange(newConfig);
        if (status.isActive) {
            updateStrategyParameters({ [name]: value });
        }
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
                                {availableModels
                                    ?.sort((a: any, b: any) => new Date(b.trained_at).getTime() - new Date(a.trained_at).getTime())
                                    .map((model: any, index: number) => {
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
                        <div className="flex items-center space-x-2 mb-2">
                            <input
                                type="checkbox"
                                id="use_batch_training"
                                checked={config.use_batch_training !== false}
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
                    <div className="flex items-center space-x-2">
                        <input
                            type="checkbox"
                            id="fallback_to_baseline"
                            checked={config.fallback_to_baseline !== false}
                            onChange={(e) => handleParameterChange('fallback_to_baseline', e.target.checked)}
                        />
                        <label htmlFor="fallback_to_baseline" className="text-sm font-medium text-gray-700">
                            Fallback to Baseline Strategy
                        </label>
                    </div>
                    <MLConfigForm />
                </div>
            )}
            {strategy === 'orderbook' && (
                <div className="p-4 bg-gray-50 rounded-lg">
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                        Configuration Preset
                    </label>
                    <select
                        value={selectedPreset}
                        onChange={(e) => applyPreset(e.target.value)}
                        className="w-full border border-gray-300 rounded-md px-3 py-2 mb-3"
                    >
                        <option value="custom">Custom Configuration</option>
                        <option value="conservative">Conservative (Few High-Quality Signals)</option>
                        <option value="moderate">Moderate (Balanced Signals)</option>
                        <option value="aggressive">Aggressive (More Signals) - Recommended</option>
                        <option value="very-aggressive">Very Aggressive (Maximum Signals)</option>
                    </select>
                    <p className="text-xs text-gray-500">
                        Select a preset to automatically configure parameters for different signal frequencies
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
                                        value={config[param.name] || param.default}
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
                                        value={config[param.name] || param.default}
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
                    <div className="space-y-2">
                        <label className="block text-sm font-medium text-gray-700">Initial Portfolio Size ($)</label>
                        <Input
                            type="number"
                            min={1}
                            step={100}
                            value={config.initial_portfolio_size || 10000}
                            onChange={(e) => handleParameterChange('initial_portfolio_size', Number(e.target.value))}
                            className="w-full"
                        />
                    </div>

                    <div className="space-y-2">
                        <label className="block text-sm font-medium text-gray-700">Position Size Value</label>
                        <Input
                            type="number"
                            min={0}
                            step={(config.position_size_mode || 'percent') === 'percent' ? 0.1 : 1}
                            value={config.position_size_value ?? ((config.position_size_mode || 'percent') === 'percent' ? 1 : 100)}
                            onChange={(e) => handleParameterChange('position_size_value', Number(e.target.value))}
                            className="w-full"
                        />
                    </div>
                    <div className="text-xs text-gray-500">
                        {(config.position_size_mode || 'percent') === 'percent'
                            ? 'Example: 1 means 1% of portfolio per position'
                            : 'Example: 250 means allocate $250 per position'}
                    </div>
                </div>
            </div>
        </div>
    );
}
