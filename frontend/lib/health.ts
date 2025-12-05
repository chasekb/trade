import React from 'react';

// Application health monitoring and diagnostics
export interface HealthCheck {
  name: string;
  status: 'healthy' | 'unhealthy' | 'warning';
  responseTime?: number;
  lastChecked: Date;
  details?: Record<string, any>;
}

export interface HealthStatus {
  overall: 'healthy' | 'warning' | 'critical';
  timestamp: string;
  uptime: number;
  version: string;
  services: HealthCheck[];
  memory?: {
    used: number;
    allocated: number;
    limit: number;
    percentage: number;
  };
  database?: {
    status: 'connected' | 'disconnected' | 'error';
    responseTime?: number;
    connections?: number;
  };
}

export class HealthMonitor {
  private checks: Map<string, HealthCheck> = new Map();
  private startTime: number = Date.now();

  // API Health Check
  async checkAPI(): Promise<HealthCheck> {
    const startTime = Date.now();
    try {
      // Import config to get API URL
      const { config } = await import('./config');

      const response = await fetch(`${config.api.baseUrl}/health`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        signal: AbortSignal.timeout(5000), // 5 second timeout
      });

      const responseTime = Date.now() - startTime;

      if (response.ok) {
        const data = await response.json().catch(() => ({}));
        return {
          name: 'API Health',
          status: 'healthy',
          responseTime,
          lastChecked: new Date(),
          details: {
            statusCode: response.status,
            version: data.version,
            environment: data.environment,
          }
        };
      } else {
        return {
          name: 'API Health',
          status: 'unhealthy',
          responseTime,
          lastChecked: new Date(),
          details: {
            statusCode: response.status,
            error: response.statusText
          }
        };
      }
    } catch (error: any) {
      return {
        name: 'API Health',
        status: 'unhealthy',
        responseTime: Date.now() - startTime,
        lastChecked: new Date(),
        details: {
          error: error.message,
          type: error.name
        }
      };
    }
  }

  // WebSocket Health Check
  async checkWebSocket(): Promise<HealthCheck> {
    return new Promise<HealthCheck>((resolve) => {
      const startTime = Date.now();
      const { config } = require('./config');

      try {
        const ws = new WebSocket(config.websocket.url);
        let resolved = false;

        const timeout = setTimeout(() => {
          if (!resolved) {
            resolved = true;
            ws.close();
            resolve({
              name: 'WebSocket Health',
              status: 'unhealthy',
              responseTime: Date.now() - startTime,
              lastChecked: new Date(),
              details: { error: 'Connection timeout after 5 seconds' }
            });
          }
        }, 5000);

        ws.onopen = () => {
          if (!resolved) {
            clearTimeout(timeout);
            resolved = true;
            ws.close();
            resolve({
              name: 'WebSocket Health',
              status: 'healthy',
              responseTime: Date.now() - startTime,
              lastChecked: new Date(),
              details: { protocol: ws.protocol }
            });
          }
        };

        ws.onerror = (error) => {
          if (!resolved) {
            clearTimeout(timeout);
            resolved = true;
            resolve({
              name: 'WebSocket Health',
              status: 'unhealthy',
              responseTime: Date.now() - startTime,
              lastChecked: new Date(),
              details: { error: 'WebSocket connection failed', event: error }
            });
          }
        };

        ws.onclose = (event) => {
          if (!resolved) {
            clearTimeout(timeout);
            resolved = true;
            const isClean = event.wasClean;
            resolve({
              name: 'WebSocket Health',
              status: isClean ? 'healthy' : 'warning',
              responseTime: Date.now() - startTime,
              lastChecked: new Date(),
              details: {
                code: event.code,
                reason: event.reason,
                clean: isClean
              }
            });
          }
        };
      } catch (error: any) {
        resolve({
          name: 'WebSocket Health',
          status: 'unhealthy',
          responseTime: Date.now() - startTime,
          lastChecked: new Date(),
          details: { error: error.message, type: error.name }
        });
      }
    });
  }

  // React Query Health Check
  async checkReactQuery(): Promise<HealthCheck> {
    const startTime = Date.now();

    try {
      // Test basic query functionality
      const { useQueryClient } = await import('@tanstack/react-query');
      // In a browser environment, we can't directly test React Query
      // but we can check if the library is available
      const isAvailable = typeof useQueryClient !== 'undefined';

      return {
        name: 'React Query',
        status: isAvailable ? 'healthy' : 'unhealthy',
        responseTime: Date.now() - startTime,
        lastChecked: new Date(),
        details: { available: isAvailable }
      };
    } catch (error: any) {
      return {
        name: 'React Query',
        status: 'unhealthy',
        responseTime: Date.now() - startTime,
        lastChecked: new Date(),
        details: { error: error.message }
      };
    }
  }

  // Memory Usage Check
  checkMemory(): HealthCheck {
    const startTime = Date.now();

    try {
      if ('memory' in performance) {
        const memInfo = (performance as any).memory;
        const usedMB = memInfo.usedJSHeapSize / 1024 / 1024;
        const totalMB = memInfo.totalJSHeapSize / 1024 / 1024;
        const limitMB = memInfo.jsHeapSizeLimit / 1024 / 1024;
        const percentage = (usedMB / limitMB) * 100;

        let status: 'healthy' | 'warning' | 'unhealthy' = 'healthy';
        if (percentage > 80) status = 'unhealthy';
        else if (percentage > 60) status = 'warning';

        return {
          name: 'Memory Usage',
          status,
          responseTime: Date.now() - startTime,
          lastChecked: new Date(),
          details: {
            used: Math.round(usedMB * 100) / 100,
            allocated: Math.round(totalMB * 100) / 100,
            limit: Math.round(limitMB * 100) / 100,
            percentage: Math.round(percentage * 100) / 100
          }
        };
      } else {
        return {
          name: 'Memory Usage',
          status: 'warning',
          responseTime: Date.now() - startTime,
          lastChecked: new Date(),
          details: { message: 'Memory monitoring not available in this browser' }
        };
      }
    } catch (error: any) {
      return {
        name: 'Memory Usage',
        status: 'unhealthy',
        responseTime: Date.now() - startTime,
        lastChecked: new Date(),
        details: { error: error.message }
      };
    }
  }

  // Service Worker Check
  async checkServiceWorker(): Promise<HealthCheck> {
    const startTime = Date.now();

    try {
      if ('serviceWorker' in navigator) {
        const registration = await navigator.serviceWorker.ready;
        const isActive = !!registration.active;
        const isInstalling = !!registration.installing;
        const isWaiting = !!registration.waiting;

        let status: 'healthy' | 'warning' | 'unhealthy' = 'healthy';
        if (!isActive) status = 'unhealthy';
        else if (isInstalling || isWaiting) status = 'warning';

        return {
          name: 'Service Worker',
          status,
          responseTime: Date.now() - startTime,
          lastChecked: new Date(),
          details: {
            active: isActive,
            installing: isInstalling,
            waiting: isWaiting,
            scope: registration.scope,
            state: registration.active?.state
          }
        };
      } else {
        return {
          name: 'Service Worker',
          status: 'warning',
          responseTime: Date.now() - startTime,
          lastChecked: new Date(),
          details: { message: 'Service Worker not supported in this browser' }
        };
      }
    } catch (error: any) {
      return {
        name: 'Service Worker',
        status: 'unhealthy',
        responseTime: Date.now() - startTime,
        lastChecked: new Date(),
        details: { error: error.message }
      };
    }
  }

  // Run all health checks
  async runAllChecks(): Promise<HealthCheck[]> {
    const checks = await Promise.all([
      this.checkAPI(),
      this.checkWebSocket(),
      this.checkReactQuery(),
      this.checkServiceWorker()
    ]);

    // Add memory check (synchronous)
    checks.push(this.checkMemory());

    // Update cache
    checks.forEach(check => this.checks.set(check.name, check));

    return checks;
  }

  // Get cached health status
  getHealthStatus(): HealthCheck[] {
    return Array.from(this.checks.values());
  }

  // Determine overall system health
  isSystemHealthy(): boolean {
    const checks = this.getHealthStatus();
    return checks.every(check => check.status === 'healthy');
  }

  isSystemWarning(): boolean {
    const checks = this.getHealthStatus();
    return checks.some(check => check.status === 'warning') &&
           !checks.some(check => check.status === 'unhealthy');
  }

  isSystemCritical(): boolean {
    const checks = this.getHealthStatus();
    return checks.some(check => check.status === 'unhealthy');
  }

  // Get comprehensive health report
  async getHealthReport(): Promise<HealthStatus> {
    const services = await this.runAllChecks();
    const memory = this.checkMemory();

    let overall: 'healthy' | 'warning' | 'critical' = 'healthy';
    if (this.isSystemCritical()) overall = 'critical';
    else if (this.isSystemWarning()) overall = 'warning';

    return {
      overall,
      timestamp: new Date().toISOString(),
      uptime: Date.now() - this.startTime,
      version: process.env.NEXT_PUBLIC_APP_VERSION || '1.0.0',
      services,
      memory: memory.details as any,
    };
  }

  // Log health report for debugging
  logHealthReport(): void {
    this.getHealthReport().then(report => {
      console.group('Health Report');
      console.log('Overall Status:', report.overall);
      console.log('Uptime:', Math.round(report.uptime / 1000), 'seconds');
      console.log('Version:', report.version);
      console.log('Services:');
      report.services.forEach(service => {
        console.log(`  ${service.name}: ${service.status} (${service.responseTime}ms)`);
        if (service.details && Object.keys(service.details).length > 0) {
          console.log('    Details:', service.details);
        }
      });
      if (report.memory) {
        console.log('Memory:', report.memory);
      }
      console.groupEnd();
    }).catch(error => {
      console.error('Failed to generate health report:', error);
    });
  }
}

// Global health monitor instance - lazy initialized
let _healthMonitor: HealthMonitor | null = null;

export const healthMonitor = (() => {
  if (typeof window === 'undefined') {
    // Return a dummy object during SSR/static generation
    return {} as HealthMonitor;
  }
  if (!_healthMonitor) {
    _healthMonitor = new HealthMonitor();
  }
  return _healthMonitor;
})();

// React hook for health monitoring
export function useHealthCheck(interval = 60000) { // Default: check every minute
  const [health, setHealth] = React.useState<HealthStatus | null>(null);
  const [loading, setLoading] = React.useState(false);

  const checkHealth = React.useCallback(async () => {
    setLoading(true);
    try {
      const report = await healthMonitor.getHealthReport();
      setHealth(report);
    } catch (error) {
      console.error('Health check failed:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    checkHealth(); // Initial check

    if (interval > 0) {
      const timer = setInterval(checkHealth, interval);
      return () => clearInterval(timer);
    }
  }, [checkHealth, interval]);

  return { health, loading, checkHealth };
}
