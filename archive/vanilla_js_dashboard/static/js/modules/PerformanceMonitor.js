/**
 * PerformanceMonitor Module
 * Tracks and reports performance metrics for the dashboard
 */
export class PerformanceMonitor {
    constructor(dashboard) {
        this.dashboard = dashboard;
        this.metrics = {
            pageLoadTime: 0,
            apiResponseTimes: new Map(),
            domUpdateTimes: new Map(),
            memoryUsage: 0,
            renderTimes: new Map()
        };
        this.observers = [];
        this.init();
    }

    init() {
        // Track page load time
        if (window.performance) {
            window.addEventListener('load', () => {
                const loadTime = window.performance.timing.loadEventEnd - window.performance.timing.navigationStart;
                this.metrics.pageLoadTime = loadTime;
                console.log(`📊 Page load time: ${loadTime}ms`);
            });
        }

        // Monitor memory usage
        this.startMemoryMonitoring();

        // Track API performance
        this.interceptFetch();

        // Track DOM updates
        this.observeDOM();
    }

    startMemoryMonitoring() {
        if (performance.memory) {
            setInterval(() => {
                this.metrics.memoryUsage = performance.memory.usedJSHeapSize;
            }, 5000);
        }
    }

    interceptFetch() {
        const originalFetch = window.fetch;
        window.fetch = async (...args) => {
            const startTime = performance.now();
            const url = args[0];
            
            try {
                const response = await originalFetch(...args);
                const endTime = performance.now();
                const duration = endTime - startTime;
                
                this.metrics.apiResponseTimes.set(url, duration);
                
                // Log slow requests
                if (duration > 1000) {
                    console.warn(`🐌 Slow API request: ${url} took ${duration.toFixed(2)}ms`);
                }
                
                return response;
            } catch (error) {
                const endTime = performance.now();
                const duration = endTime - startTime;
                console.error(`❌ API request failed: ${url} after ${duration.toFixed(2)}ms`, error);
                throw error;
            }
        };
    }

    observeDOM() {
        const observer = new MutationObserver((mutations) => {
            const startTime = performance.now();
            
            mutations.forEach((mutation) => {
                if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                    const endTime = performance.now();
                    const duration = endTime - startTime;
                    this.metrics.domUpdateTimes.set('DOM_UPDATE', duration);
                }
            });
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true,
            attributes: true
        });

        this.observers.push(observer);
    }

    trackRenderTime(component, renderFunction) {
        const startTime = performance.now();
        const result = renderFunction();
        const endTime = performance.now();
        const duration = endTime - startTime;
        
        this.metrics.renderTimes.set(component, duration);
        
        if (duration > 16) { // More than one frame at 60fps
            console.warn(`🐌 Slow render: ${component} took ${duration.toFixed(2)}ms`);
        }
        
        return result;
    }

    getPerformanceReport() {
        const report = {
            pageLoadTime: this.metrics.pageLoadTime,
            averageApiResponseTime: this.getAverageApiResponseTime(),
            averageDOMUpdateTime: this.getAverageDOMUpdateTime(),
            memoryUsage: this.metrics.memoryUsage,
            slowestApiCalls: this.getSlowestApiCalls(5),
            slowestRenders: this.getSlowestRenders(5)
        };

        return report;
    }

    getAverageApiResponseTime() {
        const times = Array.from(this.metrics.apiResponseTimes.values());
        return times.length > 0 ? times.reduce((a, b) => a + b, 0) / times.length : 0;
    }

    getAverageDOMUpdateTime() {
        const times = Array.from(this.metrics.domUpdateTimes.values());
        return times.length > 0 ? times.reduce((a, b) => a + b, 0) / times.length : 0;
    }

    getSlowestApiCalls(count = 5) {
        return Array.from(this.metrics.apiResponseTimes.entries())
            .sort((a, b) => b[1] - a[1])
            .slice(0, count)
            .map(([url, time]) => ({ url, time: time.toFixed(2) }));
    }

    getSlowestRenders(count = 5) {
        return Array.from(this.metrics.renderTimes.entries())
            .sort((a, b) => b[1] - a[1])
            .slice(0, count)
            .map(([component, time]) => ({ component, time: time.toFixed(2) }));
    }

    logPerformanceReport() {
        const report = this.getPerformanceReport();
        console.group('📊 Performance Report');
        console.log(`Page Load Time: ${report.pageLoadTime}ms`);
        console.log(`Average API Response Time: ${report.averageApiResponseTime.toFixed(2)}ms`);
        console.log(`Average DOM Update Time: ${report.averageDOMUpdateTime.toFixed(2)}ms`);
        console.log(`Memory Usage: ${(report.memoryUsage / 1024 / 1024).toFixed(2)}MB`);
        
        if (report.slowestApiCalls.length > 0) {
            console.group('Slowest API Calls');
            report.slowestApiCalls.forEach(call => {
                console.log(`${call.url}: ${call.time}ms`);
            });
            console.groupEnd();
        }
        
        if (report.slowestRenders.length > 0) {
            console.group('Slowest Renders');
            report.slowestRenders.forEach(render => {
                console.log(`${render.component}: ${render.time}ms`);
            });
            console.groupEnd();
        }
        
        console.groupEnd();
    }

    destroy() {
        this.observers.forEach(observer => observer.disconnect());
        this.observers = [];
    }
}
