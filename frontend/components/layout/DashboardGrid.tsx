import React from 'react';
import { cn } from '@/lib/utils';

export interface DashboardGridProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  responsive?: boolean;
  columns?: number;
  gap?: 'sm' | 'md' | 'lg' | 'xl';
}

export const DashboardGrid: React.FC<DashboardGridProps> = ({
  children,
  responsive = true,
  columns = 4,
  gap = 'md',
  className,
  ...props
}) => {
  const gapClasses = {
    sm: 'gap-2',
    md: 'gap-4',
    lg: 'gap-6',
    xl: 'gap-8',
  };

  const gridClasses = {
    1: 'grid-cols-1',
    2: responsive ? 'grid-cols-1 md:grid-cols-2' : 'grid-cols-2',
    3: responsive ? 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3' : 'grid-cols-3',
    4: responsive ? 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4' : 'grid-cols-4',
    5: responsive ? 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5' : 'grid-cols-5',
    6: responsive ? 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-6' : 'grid-cols-6',
  };

  return (
    <div
      className={cn(
        'grid w-full',
        gridClasses[columns as keyof typeof gridClasses] || gridClasses[4],
        gapClasses[gap],
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
};

export interface DashboardSectionProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  title?: string;
  description?: string;
}

export const DashboardSection: React.FC<DashboardSectionProps> = ({
  children,
  title,
  description,
  className,
  ...props
}) => (
  <div className={cn('space-y-6', className)} {...props}>
    {(title || description) && (
      <div className="space-y-2">
        {title && (
          <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
        )}
        {description && (
          <p className="text-muted-foreground">{description}</p>
        )}
      </div>
    )}
    {children}
  </div>
);

export interface SidebarLayoutProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  sidebar: React.ReactNode;
  sidebarWidth?: string;
}

export const SidebarLayout: React.FC<SidebarLayoutProps> = ({
  children,
  sidebar,
  sidebarWidth = '250px',
  className,
  ...props
}) => (
  <div className={cn('flex', className)} {...props}>
    <aside
      className="flex-shrink-0 border-r border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900"
      style={{ width: sidebarWidth }}
    >
      {sidebar}
    </aside>
    <main className="flex-1 overflow-x-hidden">
      {children}
    </main>
  </div>
);
