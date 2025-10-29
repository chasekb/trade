import React from 'react';
import { Card, CardContent } from '@/components/ui/Card';
import { StatCardProps } from '@/types/trading';
import { cn } from '@/lib/utils';

export function StatCard({
  title,
  value,
  format = 'number',
  change,
  className
}: StatCardProps) {
  const formatValue = (val: number | string): string => {
    if (typeof val === 'string') return val;

    switch (format) {
      case 'currency':
        return new Intl.NumberFormat('en-US', {
          style: 'currency',
          currency: 'USD',
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        }).format(val);
      case 'percentage':
        return `${val.toFixed(1)}%`;
      case 'number':
        return val.toLocaleString();
      default:
        return val.toString();
    }
  };

  const formatChange = (changeVal?: number): { text: string; isPositive: boolean } | null => {
    if (changeVal === undefined) return null;

    const isPositive = changeVal >= 0;
    const sign = isPositive ? '+' : '';
    let formattedChange: string;

    switch (format) {
      case 'currency':
        formattedChange = `${sign}${new Intl.NumberFormat('en-US', {
          style: 'currency',
          currency: 'USD',
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        }).format(changeVal)}`;
        break;
      case 'percentage':
        formattedChange = `${sign}${changeVal.toFixed(1)}%`;
        break;
      default:
        formattedChange = `${sign}${changeVal.toLocaleString()}`;
    }

    return { text: formattedChange, isPositive };
  };

  const changeInfo = formatChange(change);

  return (
    <Card className={cn('transition-all duration-200 hover:shadow-lg', className)}>
      <CardContent className="p-6">
        <div className="flex flex-col space-y-2">
          <p className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
            {title}
          </p>
          <div className="flex items-center justify-between">
            <p className="text-2xl font-bold text-foreground">
              {formatValue(value)}
            </p>
            {changeInfo && (
              <span className={cn(
                'text-sm font-medium',
                changeInfo.isPositive ? 'text-green-600' : 'text-red-600'
              )}>
                {changeInfo.text}
              </span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
