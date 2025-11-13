'use client';

import React, { useState, useEffect } from 'react';
import { useMLConfig } from '@/hooks/useMLConfig';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { MLConfig } from '@/types/trading';

export function MLConfigForm() {
  const { mlConfig, isLoadingMLConfig, updateMLConfig, isUpdatingMLConfig } = useMLConfig();
  const [config, setConfig] = useState<Partial<MLConfig>>({});

  useEffect(() => {
    if (mlConfig) {
      setConfig(mlConfig);
    }
  }, [mlConfig]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = e.target;
    setConfig((prevConfig) => ({
      ...prevConfig,
      [name]: type === 'checkbox' ? checked : Number(value),
    }));
  };

  const handleSave = () => {
    updateMLConfig(config);
  };

  if (isLoadingMLConfig) {
    return <div>Loading ML configuration...</div>;
  }

  return (
    <div className="p-4 bg-gray-50 rounded-lg space-y-4">
      <h4 className="text-md font-semibold text-gray-700">ML Configuration</h4>
      <div className="space-y-2">
        <label className="block text-sm font-medium text-gray-700">Continuous Training</label>
        <div className="flex items-center space-x-2">
          <input
            type="checkbox"
            id="continuous_training_enabled"
            name="continuous_training_enabled"
            checked={config.continuous_training_enabled ?? false}
            onChange={handleInputChange}
          />
          <label htmlFor="continuous_training_enabled" className="text-sm font-medium text-gray-700">
            Enable Continuous Model Training
          </label>
        </div>
      </div>
      <div className="space-y-2">
        <label className="block text-sm font-medium text-gray-700">Training Interval (seconds)</label>
        <Input
          type="number"
          name="training_interval"
          value={config.training_interval ?? 3600}
          onChange={handleInputChange}
          className="w-full"
        />
      </div>
      <div className="space-y-2">
        <label className="block text-sm font-medium text-gray-700">New Data Threshold</label>
        <Input
          type="number"
          name="new_data_threshold"
          value={config.new_data_threshold ?? 100}
          onChange={handleInputChange}
          className="w-full"
        />
      </div>
      <Button onClick={handleSave} disabled={isUpdatingMLConfig}>
        {isUpdatingMLConfig ? 'Saving...' : 'Save Configuration'}
      </Button>
    </div>
  );
}
