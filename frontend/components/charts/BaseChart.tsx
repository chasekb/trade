import React, { useRef, useEffect, useState } from 'react';
import {
  Chart as ChartJS,
  ChartData,
  ChartOptions,
  ChartType,
  Plugin,
} from 'chart.js';

interface BaseChartProps<T extends ChartType> {
  type: T;
  data: ChartData<T>;
  options?: Partial<ChartOptions<T>>;
  plugins?: Plugin<T>[];
  height?: number | string;
  width?: number | string;
  className?: string;
  responsive?: boolean;
  maintainAspectRatio?: boolean;
}

export function BaseChart<T extends ChartType>({
  type,
  data,
  options = {},
  plugins = [],
  height = 400,
  width = '100%',
  className,
  responsive = true,
  maintainAspectRatio = false,
}: BaseChartProps<T>) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [chart, setChart] = useState<ChartJS<T> | null>(null);

  useEffect(() => {
    if (!canvasRef.current) return;

    const canvas = canvasRef.current;

    // Default options that can be overridden
    const defaultOptions: Partial<ChartOptions<T>> = {
      responsive,
      maintainAspectRatio,
      ...options,
    };

    try {
      const chartInstance = new ChartJS<T>(canvas, {
        type,
        data,
        options: defaultOptions as ChartOptions<T>,
        plugins,
      });

      setChart(chartInstance);

      return () => {
        chartInstance.destroy();
        setChart(null);
      };
    } catch (error) {
      console.error('Error creating Chart.js instance:', error);
      return () => {
        // Cleanup on error
      };
    }
  }, [type, responsive, maintainAspectRatio]);

  // Update chart when data or options change
  useEffect(() => {
    if (chart && data) {
      chart.data = data;
      chart.update('active');
    }
  }, [chart, data]);

  useEffect(() => {
    if (chart && options) {
      chart.options = {
        ...chart.options,
        ...options,
      } as ChartOptions<T>;
      chart.update('active');
    }
  }, [chart, options]);

  return (
    <div className={className} style={{ height, width }}>
      <canvas ref={canvasRef} height={height} width={width} />
    </div>
  );
}
