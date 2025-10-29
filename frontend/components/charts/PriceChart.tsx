import React from 'react';
import {
  Chart as ChartJS,
  ChartData,
  ChartOptions,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  TimeScale,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import 'chartjs-adapter-date-fns';
import { BaseChart } from './BaseChart';

// Register necessary Chart.js components for line charts
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  TimeScale,
  Title,
  Tooltip,
  Legend
);

export interface PriceDataPoint {
  timestamp: string | number;
  price: number;
  volume?: number;
  high?: number;
  low?: number;
  open?: number;
  close?: number;
}

export interface PriceChartProps {
  data: PriceDataPoint[];
  symbol?: string;
  timeframe?: '1m' | '5m' | '15m' | '1h' | '4h' | '1d';
  height?: number;
  width?: number | string;
  showVolume?: boolean;
  className?: string;
}

export function PriceChart({
  data,
  symbol = '',
  timeframe = '1h',
  height = 400,
  width = '100%',
  showVolume = false,
  className,
}: PriceChartProps) {
  // Transform price data for Chart.js
  const chartData: ChartData<'line'> = {
    labels: data.map(point =>
      typeof point.timestamp === 'string'
        ? new Date(point.timestamp).toLocaleString()
        : point.timestamp
    ),
    datasets: [
      {
        label: `${symbol} Price`,
        data: data.map(point => point.price),
        borderColor: 'rgb(59, 130, 246)',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 4,
        tension: 0.1,
        fill: false,
      },
      ...(showVolume && data[0]?.volume !== undefined
        ? [{
            label: `${symbol} Volume`,
            data: data.map(point => point.volume || 0),
            borderColor: 'rgb(156, 163, 175)',
            backgroundColor: 'rgba(156, 163, 175, 0.1)',
            borderWidth: 1,
            pointRadius: 0,
            pointHoverRadius: 0,
            tension: 0,
            fill: false,
            yAxisID: 'volume',
          }]
        : []
      ),
    ],
  };

  const chartOptions: Partial<ChartOptions<'line'>> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'index',
      intersect: false,
    },
    plugins: {
      legend: {
        display: true,
        position: 'top' as const,
      },
      tooltip: {
        mode: 'index',
        intersect: false,
        callbacks: {
          label: function(context: any) {
            let label = context.dataset.label || '';
            if (label) {
              label += ': ';
            }
            if (context.parsed.y !== null) {
              label += new Intl.NumberFormat('en-US', {
                style: 'currency',
                currency: 'USD',
              }).format(context.parsed.y);
            }
            return label;
          },
        },
      },
    },
    scales: {
      x: {
        type: 'time',
        time: {
          unit: timeframe === '1d' ? 'hour' : 'minute',
          displayFormats: {
            minute: 'HH:mm',
            hour: 'MMM dd HH:mm',
            day: 'MMM dd',
          },
        },
        ticks: {
          maxTicksLimit: 10,
        },
      },
      y: {
        type: 'linear',
        position: 'left',
        title: {
          display: true,
          text: 'Price ($)',
        },
        ticks: {
          callback: function(value: any) {
            return new Intl.NumberFormat('en-US', {
              style: 'currency',
              currency: 'USD',
              minimumFractionDigits: 2,
            }).format(value);
          },
        },
      },
      ...(showVolume && {
        volume: {
          type: 'linear',
          position: 'right',
          title: {
            display: true,
            text: 'Volume',
          },
          ticks: {
            callback: function(value: any) {
              return new Intl.NumberFormat('en-US').format(value);
            },
          },
          grid: {
            drawOnChartArea: false,
          },
        },
      }),
    },
  };

  return (
    <BaseChart
      type="line"
      data={chartData}
      options={chartOptions}
      height={height}
      width={width}
      className={className}
    />
  );
}
