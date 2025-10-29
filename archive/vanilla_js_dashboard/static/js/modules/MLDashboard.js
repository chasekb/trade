/**
 * ML Trading Dashboard Module
 * Handles ML model status, performance metrics, and controls
 */

class MLDashboard {
    constructor() {
        this.mlServerUrl = 'http://localhost:8002';
        this.updateInterval = 30000; // 30 seconds
        this.isUpdating = false;
        this.charts = {};
        
        this.init();
    }
    
    init() {
        this.createMLSection();
        this.startPeriodicUpdate();
        this.bindEvents();
    }
    
    createMLSection() {
        const dashboard = document.getElementById('dashboard');
        if (!dashboard) return;
        
        // Create ML section
        const mlSection = document.createElement('div');
        mlSection.id = 'ml-section';
        mlSection.className = 'dashboard-section';
        mlSection.innerHTML = `
            <div class="section-header">
                <h3>🤖 ML Trading Optimization</h3>
                <div class="ml-controls">
                    <button id="train-model-btn" class="btn btn-primary">Train Model</button>
                    <button id="update-model-btn" class="btn btn-secondary">Update Model</button>
                    <button id="rollback-model-btn" class="btn btn-warning">Rollback</button>
                </div>
            </div>
            
            <div class="ml-content">
                <div class="ml-status">
                    <div class="status-card">
                        <h4>Model Status</h4>
                        <div id="model-status" class="status-indicator">
                            <span class="status-dot"></span>
                            <span class="status-text">Checking...</span>
                        </div>
                        <div id="model-info" class="model-info"></div>
                    </div>
                    
                    <div class="performance-card">
                        <h4>Performance Metrics</h4>
                        <div id="performance-metrics" class="metrics-grid"></div>
                    </div>
                </div>
                
                <div class="ml-charts">
                    <div class="chart-container">
                        <h4>Feature Importance</h4>
                        <canvas id="feature-importance-chart"></canvas>
                    </div>
                    
                    <div class="chart-container">
                        <h4>Model Performance History</h4>
                        <canvas id="performance-history-chart"></canvas>
                    </div>
                </div>
            </div>
        `;
        
        dashboard.appendChild(mlSection);
    }
    
    bindEvents() {
        // Bind button events
        document.getElementById('train-model-btn')?.addEventListener('click', () => this.trainModel());
        document.getElementById('update-model-btn')?.addEventListener('click', () => this.updateModel());
        document.getElementById('rollback-model-btn')?.addEventListener('click', () => this.rollbackModel());
    }
    
    async updateMLData() {
        if (this.isUpdating) return;
        this.isUpdating = true;
        
        try {
            const response = await fetch('/api/ml/dashboard');
            const data = await response.json();
            
            if (response.ok) {
                this.updateModelStatus(data.status);
                this.updatePerformanceMetrics(data.performance);
                this.updateFeatureImportance(data.feature_importance);
            } else {
                this.showError('Failed to fetch ML data');
            }
        } catch (error) {
            console.error('Error updating ML data:', error);
            this.showError('Error connecting to ML server');
        } finally {
            this.isUpdating = false;
        }
    }
    
    updateModelStatus(status) {
        const statusElement = document.getElementById('model-status');
        const infoElement = document.getElementById('model-info');
        
        if (!statusElement || !infoElement) return;
        
        const statusDot = statusElement.querySelector('.status-dot');
        const statusText = statusElement.querySelector('.status-text');
        
        if (status.is_trained) {
            statusDot.className = 'status-dot trained';
            statusText.textContent = 'Model Trained';
            
            infoElement.innerHTML = `
                <div class="model-details">
                    <p><strong>Last Training:</strong> ${this.formatTimestamp(status.last_training_time)}</p>
                    <p><strong>Model Type:</strong> ${status.current_model?.model_name || 'Unknown'}</p>
                    <p><strong>Version:</strong> ${status.current_model?.version_id || 'Unknown'}</p>
                </div>
            `;
        } else {
            statusDot.className = 'status-dot not-trained';
            statusText.textContent = 'Model Not Trained';
            
            if (status.error) {
                infoElement.innerHTML = `<p class="error">Error: ${status.error}</p>`;
            } else {
                infoElement.innerHTML = '<p>No trained model available</p>';
            }
        }
    }
    
    updatePerformanceMetrics(performance) {
        const metricsElement = document.getElementById('performance-metrics');
        if (!metricsElement) return;
        
        if (performance.error) {
            metricsElement.innerHTML = `<p class="error">Error: ${performance.error}</p>`;
            return;
        }
        
        const metrics = [
            { label: 'R² Score', value: performance.r2?.toFixed(4) || 'N/A' },
            { label: 'RMSE', value: performance.rmse?.toFixed(4) || 'N/A' },
            { label: 'MAE', value: performance.mae?.toFixed(4) || 'N/A' },
            { label: 'Profit Factor', value: performance.profit_factor?.toFixed(2) || 'N/A' },
            { label: 'Sharpe Ratio', value: performance.sharpe_ratio?.toFixed(2) || 'N/A' }
        ];
        
        metricsElement.innerHTML = metrics.map(metric => `
            <div class="metric-item">
                <span class="metric-label">${metric.label}:</span>
                <span class="metric-value">${metric.value}</span>
            </div>
        `).join('');
    }
    
    updateFeatureImportance(importance) {
        if (!importance || Object.keys(importance).length === 0) return;
        
        // Sort features by importance
        const sortedFeatures = Object.entries(importance)
            .sort(([,a], [,b]) => b - a)
            .slice(0, 10); // Top 10 features
        
        this.createFeatureImportanceChart(sortedFeatures);
    }
    
    createFeatureImportanceChart(features) {
        const canvas = document.getElementById('feature-importance-chart');
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        
        // Clear previous chart
        if (this.charts.featureImportance) {
            this.charts.featureImportance.destroy();
        }
        
        this.charts.featureImportance = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: features.map(([name]) => name),
                datasets: [{
                    label: 'Importance Score',
                    data: features.map(([, score]) => score),
                    backgroundColor: 'rgba(54, 162, 235, 0.8)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Importance Score'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Features'
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    title: {
                        display: true,
                        text: 'Top 10 Most Important Features'
                    }
                }
            }
        });
    }
    
    async trainModel() {
        const button = document.getElementById('train-model-btn');
        const originalText = button.textContent;
        
        try {
            button.textContent = 'Training...';
            button.disabled = true;
            
            const response = await fetch('/api/ml/train', { method: 'POST' });
            const result = await response.json();
            
            if (response.ok) {
                this.showSuccess('Model training completed successfully');
                await this.updateMLData(); // Refresh data
            } else {
                this.showError(`Training failed: ${result.error || 'Unknown error'}`);
            }
        } catch (error) {
            console.error('Error training model:', error);
            this.showError('Error training model');
        } finally {
            button.textContent = originalText;
            button.disabled = false;
        }
    }
    
    async updateModel() {
        const button = document.getElementById('update-model-btn');
        const originalText = button.textContent;
        
        try {
            button.textContent = 'Updating...';
            button.disabled = true;
            
            const response = await fetch('/api/ml/update', { method: 'POST' });
            const result = await response.json();
            
            if (response.ok) {
                this.showSuccess('Model updated successfully');
                await this.updateMLData(); // Refresh data
            } else {
                this.showError(`Update failed: ${result.error || 'Unknown error'}`);
            }
        } catch (error) {
            console.error('Error updating model:', error);
            this.showError('Error updating model');
        } finally {
            button.textContent = originalText;
            button.disabled = false;
        }
    }
    
    async rollbackModel() {
        if (!confirm('Are you sure you want to rollback to the previous model version?')) {
            return;
        }
        
        const button = document.getElementById('rollback-model-btn');
        const originalText = button.textContent;
        
        try {
            button.textContent = 'Rolling back...';
            button.disabled = true;
            
            const response = await fetch('/api/ml/rollback', { method: 'POST' });
            const result = await response.json();
            
            if (response.ok) {
                this.showSuccess('Model rolled back successfully');
                await this.updateMLData(); // Refresh data
            } else {
                this.showError(`Rollback failed: ${result.error || 'Unknown error'}`);
            }
        } catch (error) {
            console.error('Error rolling back model:', error);
            this.showError('Error rolling back model');
        } finally {
            button.textContent = originalText;
            button.disabled = false;
        }
    }
    
    startPeriodicUpdate() {
        // Initial update
        this.updateMLData();
        
        // Set up periodic updates
        setInterval(() => {
            this.updateMLData();
        }, this.updateInterval);
    }
    
    showSuccess(message) {
        this.showNotification(message, 'success');
    }
    
    showError(message) {
        this.showNotification(message, 'error');
    }
    
    showNotification(message, type) {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        
        // Add to page
        document.body.appendChild(notification);
        
        // Remove after 5 seconds
        setTimeout(() => {
            notification.remove();
        }, 5000);
    }
    
    formatTimestamp(timestamp) {
        if (!timestamp) return 'Unknown';
        
        try {
            const date = new Date(timestamp);
            return date.toLocaleString();
        } catch (error) {
            return 'Invalid date';
        }
    }
}

// Initialize ML Dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    if (typeof Chart !== 'undefined') {
        new MLDashboard();
    } else {
        console.warn('Chart.js not loaded, ML dashboard charts will not work');
    }
});
