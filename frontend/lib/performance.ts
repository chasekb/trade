// Performance monitoring and analytics for trading dashboard
export class PerformanceMonitor {
  private metrics: Map<string, number[]> = new Map();

  startTiming(label: string): () => void {
    const start = performance.now();
    return () => {
      const end = performance.now();
      const duration = end - start;

      if (!this.metrics.has(label)) {
        this.metrics.set(label, []);
      }

      this.metrics.get(label)!.push(duration);

      // Log slow operations in development
      if (process.env.NODE_ENV === 'development' && duration > 100) {
        console.warn(`Slow operation: ${label} took ${duration.toFixed(2)}ms`);
      }
    };
  }

  getAverageTime(label: string): number {
    const times = this.metrics.get(label);
    return times ? times.reduce((a, b) => a + b, 0) / times.length : 0;
  }

  getMetrics(label: string): { avg: number; max: number; min: number; count: number } | null {
    const times = this.metrics.get(label);
    if (!times || times.length === 0) return null;

    return {
      avg: times.reduce((a, b) => a + b, 0) / times.length,
      max: Math.max(...times),
      min: Math.min(...times),
      count: times.length,
    };
  }

  logMetrics(): void {
    console.group('Performance Metrics');
    this.metrics.forEach((times, label) => {
      const avg = times.reduce((a, b) => a + b, 0) / times.length;
      const max = Math.max(...times);
      const count = times.length;
      console.log(`${label}: avg=${avg.toFixed(2)}ms, max=${max.toFixed(2)}ms, samples=${count}`);
    });
    console.groupEnd();
  }

  clearMetrics(): void {
    this.metrics.clear();
  }

  exportMetrics(): Record<string, { avg: number; max: number; min: number; count: number }> {
    const result: Record<string, { avg: number; max: number; min: number; count: number }> = {};

    this.metrics.forEach((times, label) => {
      if (times.length > 0) {
        result[label] = {
          avg: times.reduce((a, b) => a + b, 0) / times.length,
          max: Math.max(...times),
          min: Math.min(...times),
          count: times.length,
        };
      }
    });

    return result;
  }
}

// Global performance monitor instance - lazy initialized
let _performanceMonitor: PerformanceMonitor | null = null;

export const performanceMonitor = (() => {
  if (typeof window === 'undefined') {
    // Return a dummy object during SSR/static generation
    return {} as PerformanceMonitor;
  }
  if (!_performanceMonitor) {
    _performanceMonitor = new PerformanceMonitor();
  }
  return _performanceMonitor;
})();

// Hook for React Query performance monitoring
export function usePerformanceLogging(queryKey: string) {
  return {
    onSuccess: () => {
      const endTiming = performanceMonitor.startTiming(`query-${queryKey}`);
      endTiming();
    },
    onError: () => {
      const endTiming = performanceMonitor.startTiming(`query-error-${queryKey}`);
      endTiming();
    },
  };
}

// Performance wrapper for async operations
export async function withPerformanceLogging<T>(
  operation: () => Promise<T>,
  label: string
): Promise<T> {
  const endTiming = performanceMonitor.startTiming(label);
  try {
    const result = await operation();
    return result;
  } finally {
    endTiming();
  }
}

// Memory usage monitoring
export class MemoryMonitor {
  getMemoryUsage(): { used: number; total: number; limit: number } | null {
    if ('memory' in performance) {
      const memInfo = (performance as any).memory;
      return {
        used: memInfo.usedJSHeapSize,
        total: memInfo.totalJSHeapSize,
        limit: memInfo.jsHeapSizeLimit,
      };
    }
    return null;
  }

  logMemoryUsage(): void {
    const memory = this.getMemoryUsage();
    if (memory) {
      const usedMB = (memory.used / 1024 / 1024).toFixed(2);
      const totalMB = (memory.total / 1024 / 1024).toFixed(2);
      const limitMB = (memory.limit / 1024 / 1024).toFixed(2);

      console.log(`Memory: ${usedMB}MB used / ${totalMB}MB total / ${limitMB}MB limit`);

      // Warn if memory usage is high
      if (memory.used / memory.limit > 0.8) {
        console.warn('High memory usage detected');
      }
    }
  }
}

// Global memory monitor instance - lazy initialized
let _memoryMonitor: MemoryMonitor | null = null;

export const memoryMonitor = (() => {
  if (typeof window === 'undefined') {
    // Return a dummy object during SSR/static generation
    return {} as MemoryMonitor;
  }
  if (!_memoryMonitor) {
    _memoryMonitor = new MemoryMonitor();
  }
  return _memoryMonitor;
})();
