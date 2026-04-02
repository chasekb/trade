// API client for trading dashboard
import { ApiResponse, TradingStats, Position, PaginatedResponse, PaginationParams, OrderBookSignal } from '@/types/trading';

// Always use same-origin requests from the browser and let Next.js rewrites
// proxy to the appropriate backend target for the current environment.
const API_BASE_URL = '';

class ApiClient {
  private async request<T>(
    endpoint: string,
    options?: RequestInit
  ): Promise<ApiResponse<T>> {
    try {
      const url = `${API_BASE_URL}${endpoint}`;
      const response = await fetch(url, {
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers,
        },
        ...options,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      // Wrap the backend response in the expected ApiResponse format
      return {
        status: 'success' as const,
        data: data,
        timestamp: new Date().toISOString(),
      };
    } catch (error) {
      console.error(`API request failed for ${endpoint}:`, error);
      return {
        status: 'error' as const,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString(),
      };
    }
  }

  async getTradingStats(): Promise<ApiResponse<TradingStats>> {
    return this.request<TradingStats>('/api/trades/stats');
  }

  async getPositions(params?: PaginationParams): Promise<PaginatedResponse<Position>> {
    const queryParams = new URLSearchParams();
    if (params?.page) queryParams.append('page', params.page.toString());
    if (params?.limit) queryParams.append('limit', params.limit.toString());
    if (params?.sort_by) queryParams.append('sort_by', params.sort_by);
    if (params?.sort_order) queryParams.append('sort_order', params.sort_order);

    const query = queryParams.toString();
    const endpoint = `/api/trading/live/positions${query ? `?${query}` : ''}`;

    return this.request<Position[]>('/api/trading/live/positions')
      .then(response => {
        // Mock pagination for now - in real implementation this would come from backend
        const positions = Array.isArray(response.data) ? response.data : [];
        const page = params?.page || 1;
        const limit = params?.limit || 50;
        const total = positions.length;
        const totalPages = Math.ceil(total / limit);
        const startIndex = (page - 1) * limit;
        const endIndex = startIndex + limit;
        const paginatedData = positions.slice(startIndex, endIndex);

        return {
          ...response,
          data: paginatedData,
          pagination: {
            page,
            limit,
            total,
            total_pages: totalPages,
            has_next: page < totalPages,
            has_prev: page > 1,
          },
        } as PaginatedResponse<Position>;
      });
  }

  async getTradingHistory(params?: PaginationParams): Promise<PaginatedResponse<any>> {
    const queryParams = new URLSearchParams();
    if (params?.page) queryParams.append('page', params.page.toString());
    if (params?.limit) queryParams.append('limit', params.limit.toString());
    if (params?.sort_by) queryParams.append('sort_by', params.sort_by);
    if (params?.sort_order) queryParams.append('sort_order', params.sort_order);

    const query = queryParams.toString();
    return this.request<any[]>(`/api/trades/paginated${query ? `?${query}` : ''}`)
      .then(response => {
        const trades = Array.isArray(response.data) ? response.data : [];
        const page = params?.page || 1;
        const limit = params?.limit || 50;
        const total = trades.length;
        const totalPages = Math.ceil(total / limit);
        const startIndex = (page - 1) * limit;
        const endIndex = startIndex + limit;
        const paginatedData = trades.slice(startIndex, endIndex);

        return {
          ...response,
          data: paginatedData,
          pagination: {
            page,
            limit,
            total,
            total_pages: totalPages,
            has_next: page < totalPages,
            has_prev: page > 1,
          },
        } as PaginatedResponse<any>;
      });
  }

  // Trading operations
  async startTrading(
    mode: 'live' | 'simulated',
    strategy: string,
    symbols: string[],
    parameters: Record<string, any>,
    config: {
      position_size_percent?: number;
      max_positions?: number;
      position_update_interval?: number;
    }
  ): Promise<ApiResponse<{ is_active: boolean; message: string }>> {
    const url = mode === 'live' ? `${API_BASE_URL}/api/trading/live/start` : `${API_BASE_URL}/api/async-trading/start`;
    return fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        symbols,
        strategy_type: strategy,
        strategy_params: parameters,
        initial_balance: 10000.0,
        max_positions: config.max_positions,
        position_size_percent: config.position_size_percent,
        position_update_interval: config.position_update_interval || 5,
        immediate_start: true,
        batch_size: 3
      }),
    }).then(async (response) => {
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        return {
          status: 'error',
          error: errorData.error || `HTTP ${response.status}`,
          timestamp: new Date().toISOString(),
        };
      }
      return response.json();
    }).catch(error => ({
      status: 'error',
      error: error.message,
      timestamp: new Date().toISOString(),
    }));
  }

  async stopTrading(): Promise<ApiResponse<{ message: string }>> {
    return fetch(`${API_BASE_URL}/api/trading/simulated/stop`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    }).then(async (response) => {
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        return {
          status: 'error',
          error: errorData.error || `HTTP ${response.status}`,
          timestamp: new Date().toISOString(),
        };
      }
      return response.json();
    }).catch(error => ({
      status: 'error',
      error: error.message,
      timestamp: new Date().toISOString(),
    }));
  }

  async closePosition(symbol: string): Promise<ApiResponse<{ message: string; trade_id?: string }>> {
    return fetch(`${API_BASE_URL}/api/trading/live/close-position`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ symbol }),
    }).then(async (response) => {
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        return {
          status: 'error',
          error: errorData.error || `HTTP ${response.status}`,
          timestamp: new Date().toISOString(),
        };
      }
      return response.json();
    }).catch(error => ({
      status: 'error',
      error: error.message,
      timestamp: new Date().toISOString(),
    }));
  }

  // Simulated Trading Status
  async getSimulatedTradingStatus(): Promise<ApiResponse<any>> {
    return this.request('/api/simulated-trading/status');
  }

  // Live Portfolio Status
  async getLivePortfolioStatus(): Promise<ApiResponse<any>> {
    return this.request('/api/live-portfolio/status');
  }

  // Order Book Signals
  async getOrderBookSignals(
    symbols?: string[],
    params?: { page?: number; per_page?: number }
  ): Promise<ApiResponse<{
    signals: OrderBookSignal[];
    pagination?: any;
    total_analyzed?: number;
    active_signals?: number;
    last_updated?: string;
    average_strength?: number;
  }>> {
    const queryParams = new URLSearchParams();
    if (symbols && symbols.length > 0) {
      queryParams.append('symbols', symbols.join(','));
    }
    if (params?.page) queryParams.append('page', params.page.toString());
    if (params?.per_page) queryParams.append('per_page', params.per_page.toString());

    const query = queryParams.toString();
    return this.request(`/api/orderbook/live-signals${query ? `?${query}` : ''}`);
  }

  // Backtesting
  async runBacktest(config: {
    strategy: string;
    symbols: string[];
    parameters: Record<string, any>;
    start_date: string;
    end_date: string;
  }): Promise<ApiResponse<any>> {
    return fetch(`${API_BASE_URL}/api/backtests/run`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(config),
    }).then(async (response) => {
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        return {
          status: 'error',
          error: errorData.error || `HTTP ${response.status}`,
          timestamp: new Date().toISOString(),
        };
      }
      return response.json();
    }).catch(error => ({
      status: 'error',
      error: error.message,
      timestamp: new Date().toISOString(),
    }));
  }

  // Products/Symbols
  async getProducts(): Promise<ApiResponse<{ categories: Record<string, string[]> }>> {
    return this.request('/api/products');
  }

  // ML Analytics
  async getMLDashboard(): Promise<ApiResponse<import('@/types/trading').MLDashboardData>> {
    try {
      const dashboardResponse = await fetch(`${API_BASE_URL}/api/ml/dashboard`, {
        headers: {
          'Content-Type': 'application/json',
        },
      });

      // Preferred endpoint exists
      if (dashboardResponse.ok) {
        const data = await dashboardResponse.json();
        return {
          status: 'success',
          data,
          timestamp: new Date().toISOString(),
        };
      }

      // Backward-compatible fallback for backends without /api/ml/dashboard
      if (dashboardResponse.status === 404) {
        const [statusResp, performanceResp] = await Promise.all([
          fetch(`${API_BASE_URL}/api/ml/status`, {
            headers: { 'Content-Type': 'application/json' },
          }),
          fetch(`${API_BASE_URL}/api/ml/performance`, {
            headers: { 'Content-Type': 'application/json' },
          }),
        ]);

        if (!statusResp.ok || !performanceResp.ok) {
          throw new Error(`HTTP error! status: ${!statusResp.ok ? statusResp.status : performanceResp.status}`);
        }

        const statusData = await statusResp.json();
        const performanceData = await performanceResp.json();

        const trainingStatus = typeof statusData?.status === 'string' ? statusData.status : '';
        const isTraining = trainingStatus === 'training';
        const isTrained = trainingStatus === 'completed';
        const modelStatus: import('@/types/trading').MLModelStatus = {
          is_training: isTraining,
          is_trained: isTrained,
          ...(trainingStatus === 'failed' ? { error: 'Model training failed' } : {}),
        };

        return {
          status: 'success',
          data: {
            status: modelStatus,
            performance: performanceData || {},
            feature_importance: performanceData?.feature_importance || {},
          },
          timestamp: new Date().toISOString(),
        };
      }

      throw new Error(`HTTP error! status: ${dashboardResponse.status}`);
    } catch (error) {
      console.error('API request failed for /api/ml/dashboard:', error);
      return {
        status: 'error',
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString(),
      };
    }
  }

  async trainMLModel(batchTraining?: boolean, autoSetActive?: boolean): Promise<ApiResponse<import('@/types/trading').MLTrainingResponse>> {
    const queryParams = new URLSearchParams();
    if (batchTraining !== undefined) {
      queryParams.append('batch_training', batchTraining.toString());
    }
    if (autoSetActive !== undefined) {
      queryParams.append('auto_set_active', autoSetActive.toString());
    }
    const query = queryParams.toString();

    return fetch(`${API_BASE_URL}/api/ml/train${query ? `?${query}` : ''}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    }).then(async (response) => {
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        return {
          status: 'error',
          error: errorData.error || `HTTP ${response.status}`,
          timestamp: new Date().toISOString(),
        };
      }
      return response.json();
    }).catch(error => ({
      status: 'error',
      error: error.message,
      timestamp: new Date().toISOString(),
    }));
  }

  async getMLStatus(): Promise<ApiResponse<any>> {
    return this.request('/api/ml/status');
  }


  async updateMLModel(): Promise<ApiResponse<import('@/types/trading').MLTrainingResponse>> {
    return fetch(`${API_BASE_URL}/api/ml/update`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    }).then(async (response) => {
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        return {
          status: 'error',
          error: errorData.error || `HTTP ${response.status}`,
          timestamp: new Date().toISOString(),
        };
      }
      return response.json();
    }).catch(error => ({
      status: 'error',
      error: error.message,
      timestamp: new Date().toISOString(),
    }));
  }

  async rollbackMLModel(): Promise<ApiResponse<import('@/types/trading').MLTrainingResponse>> {
    return fetch(`${API_BASE_URL}/api/ml/rollback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    }).then(async (response) => {
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        return {
          status: 'error',
          error: errorData.error || `HTTP ${response.status}`,
          timestamp: new Date().toISOString(),
        };
      }
      return response.json();
    }).catch(error => ({
      status: 'error',
      error: error.message,
      timestamp: new Date().toISOString(),
    }));
  }

  async getPnlTrades(sortBy: string = 'pnl'): Promise<ApiResponse<any>> {
    return this.request(`/api/ml/pnl-trades?sort_by=${sortBy}`);
  }

  async getMLModels(): Promise<ApiResponse<any>> {
    return this.request('/api/ml/models');
  }

  async getAvailableModels(): Promise<ApiResponse<any>> {
    return this.request('/api/ml/models');
  }

  async setActiveModel(modelName: string): Promise<ApiResponse<any>> {
    return this.request(`/api/ml/models/set_active?model_name=${modelName}`, {
      method: 'POST',
    });
  }

  async deleteModel(modelName: string): Promise<ApiResponse<any>> {
    return this.request(`/api/ml/models/${modelName}`, {
      method: 'DELETE',
    });
  }

  async deleteAllModels(): Promise<ApiResponse<any>> {
    return this.request('/api/ml/models', {
      method: 'DELETE',
    });
  }

  async resetDatabases(): Promise<ApiResponse<any>> {
    return this.request('/api/ml/databases', {
      method: 'DELETE',
    });
  }

  async getPredictionComparison(modelIds: string[], features: any): Promise<ApiResponse<any>> {
    return this.request('/api/ml/prediction-comparison', {
      method: 'POST',
      body: JSON.stringify({
        model_ids: modelIds,
        features: features
      }),
    });
  }

  async getMLConfig(): Promise<ApiResponse<any>> {
    return this.request('/api/ml/config');
  }

  async updateMLConfig(newConfig: any): Promise<ApiResponse<any>> {
    return this.request('/api/ml/config', {
      method: 'POST',
      body: JSON.stringify(newConfig),
    });
  }

  async updateStrategyParameters(parameters: Record<string, any>): Promise<ApiResponse<any>> {
    return this.request('/api/trading/simulated/update-strategy-params', {
      method: 'POST',
      body: JSON.stringify({ parameters }),
    });
  }

  async logMessage(message: string): Promise<ApiResponse<any>> {
    return this.request('/api/log', {
      method: 'POST',
      body: JSON.stringify({ message }),
    });
  }
}

export const apiClient = new ApiClient();

// Query keys for React Query
export const queryKeys = {
  tradingStats: ['trading', 'stats'] as const,
  positions: (params?: PaginationParams) => ['trading', 'positions', params] as const,
  tradingHistory: (params?: PaginationParams) => ['trading', 'history', params] as const,
} as const;
