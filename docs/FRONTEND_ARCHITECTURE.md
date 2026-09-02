# Frontend architecture

Current runtime note: this Next.js application talks to the Drogon C++ backend
through same-origin requests and the Next.js rewrites. The host backend URL is
`http://localhost:8081`; `http://localhost:8000` and the former Python service
are retired. See [API_REFERENCE.md](API_REFERENCE.md) for the current route
registry.

This document describes the architecture of the Next.js React frontend for the Trading Bot dashboard.

## Technology Stack

- **Framework**: Next.js 14 with App Router
- **Language**: TypeScript
- **UI Components**: Custom React components
- **State Management**: React hooks and context
- **API Integration**: Custom hooks with fetch API
- **Styling**: CSS modules
- **Charts**: Lightweight Chart library for financial charts

## Project Structure

```
frontend/
├── app/                          # Next.js app directory
│   ├── page.tsx                 # Main dashboard page
│   ├── layout.tsx               # Root layout
│   └── globals.css              # Global styles
│
├── components/                   # React components
│   ├── dashboard/               # Dashboard-specific components
│   │   ├── MLAnalyticsDashboard.tsx
│   │   ├── SimulatedTradingPanel.tsx
│   │   ├── LiveTradingPanel.tsx
│   │   ├── BacktestingPanel.tsx
│   │   ├── OrderBookSignalsTable.tsx
│   │   ├── PredictionComparisonChart.tsx
│   │   ├── StrategyConfigForm.tsx
│   │   └── ...
│   ├── charts/                  # Chart components
│   ├── layout/                  # Layout components
│   ├── providers/               # Context providers
│   ├── trading/                 # Trading-specific components
│   └── ui/                      # Reusable UI components
│
├── lib/                         # Utility functions and hooks
│   ├── api.ts                   # API client
│   ├── hooks/                   # Custom React hooks
│   └── utils/                   # Helper functions
│
└── types/                       # TypeScript type definitions
    ├── trading.ts
    ├── ml.ts
    └── api.ts
```

## Dashboard Architecture

### Tab-Based Navigation

The main dashboard uses a tab-based interface with four primary sections:

1. **ML Analytics** - Machine learning model management and analytics
2. **Simulated Trading** - Paper trading with real-time simulation
3. **Live Trading** - Real capital trading interface
4. **Backtesting** - Historical strategy testing and validation

### Component Hierarchy

```
DashboardPage
├── TabNavigation
├── MLAnalyticsDashboard (Tab 1)
│   ├── MLConfigForm
│   ├── ModelControlsCard
│   ├── ModelPerformanceCard
│   ├── FeatureImportanceChart
│   ├── PredictionComparisonChart
│   ├── PnlTradesTable
│   └── ModelListDropdown
│
├── SimulatedTradingPanel (Tab 2)
│   ├── TradingControls
│   ├── StrategyConfigForm
│   │   └── StrategySelector
│   ├── TradingStatisticsDashboard
│   │   └── StatCard (multiple)
│   ├── OrderBookSignalsTable
│   ├── OpenPositionsSection
│   │   └── PositionsTable
│   └── RecentTradesSection
│
├── LiveTradingPanel (Tab 3)
│   ├── [Similar structure to SimulatedTradingPanel]
│   └── RealTimeWarnings
│
└── BacktestingPanel (Tab 4)
    ├── BacktestConfigForm
    ├── BacktestResults
    └── PerformanceCharts
```

## Key Components

### MLAnalyticsDashboard.tsx

**Purpose:** Comprehensive ML model management interface

**Features:**
- Model training controls with batch training toggle
- Model list with version history (ordered by most recent)
- Performance metrics display (R², RMSE, Sharpe ratio)
- Feature importance visualization
- Model comparison tool
- Top/bottom PnL trades table
- Active model selection and rollback

**State Management:**
```typescript
interface MLState {
  models: Model[];
  activeModel: string | null;
  trainingStatus: 'idle' | 'training' | 'completed' | 'failed';
  performance: ModelPerformance;
  batchTrainingEnabled: boolean;
  batchSize: number;
}
```

**API Integration:**
- `useModelTraining` hook for training operations
- `useModelList` hook for fetching available models
- `useModelPerformance` hook for performance metrics

### SimulatedTradingPanel.tsx

**Purpose:** Paper trading interface with ML-enhanced strategies

**Features:**
- Strategy selection (ML Enhanced Order Book, RSI, MACD, etc.)
- Order prioritization configuration (signal strength, win probability, expected return)
- Real-time order book signals table
- Open positions tracking
- Recent trades history
- Trading statistics dashboard
- Start/stop trading controls

**Order Prioritization:**
```typescript
type OrderPrioritization = 
  | 'signal_strength'  // Execute orders by signal strength (descending)
  | 'win_probability'  // Execute by ML win probability (descending)
  | 'expected_return'; // Execute by expected return (descending)
```

**Signal Tracking:**
The order book signals table displays:
- Symbol
- Signal type (buy/sell/hold)
- Strength (0-1)
- Win probability (from ML model)
- Expected return (from ML model)
- Confidence score
- Timestamp

**Key Feature - Persistent Signal Updates:**
The signals table intelligently updates by:
1. Adding new signals for symbols not yet present
2. Updating existing signals only if new signal is fresher
3. Maintaining full signal history (doesn't wipe on new data)

### OrderBookSignalsTable.tsx

**Purpose:** Display and track order book signals with intelligent updates

**Features:**
- Real-time signal updates via WebSocket
- Persistent signal tracking (no data wiping)
- Symbol-based signal organization
- Timestamp-based freshness detection
- Color-coded signal types
- Sortable columns

**Update Logic:**
```typescript
function updateSignals(newSignals: Signal[], existingSignals: Signal[]): Signal[] {
  const signalMap = new Map(existingSignals.map(s => [s.symbol, s]));
  
  newSignals.forEach(newSignal => {
    const existing = signalMap.get(newSignal.symbol);
    if (!existing || newSignal.timestamp > existing.timestamp) {
      signalMap.set(newSignal.symbol, newSignal);
    }
  });
  
  return Array.from(signalMap.values());
}
```

### StrategyConfigForm.tsx

**Purpose:** Strategy configuration and parameter management

**Features:**
- Strategy type selection
- Symbol universe configuration
- Position sizing controls
- Stop loss / take profit settings
- Order prioritization selector
- ML model selection (when using ML strategies)
- Batch training toggle for "Train New Model" button

**ML Integration:**
When ML Enhanced Order Book strategy is selected:
- Display ML model dropdown
- Show confidence threshold slider
- Enable order prioritization options
- Show batch training controls

### PredictionComparisonChart.tsx

**Purpose:** Side-by-side comparison of predictions from multiple models

**Features:**
- Dual model selection dropdowns (ordered by training date)
- Compare button to trigger comparison
- Results table showing:
  - Model name/version
  - Expected return
  - Win probability
  - Confidence score
- Visual differentiation between models

## State Management

### API Hooks Pattern

The frontend uses custom hooks for API integration:

```typescript
// Example: useModelTraining hook
export function useModelTraining() {
  const [status, setStatus] = useState<TrainingStatus>('idle');
  const [error, setError] = useState<string | null>(null);

  const trainModel = async (params: TrainingParams) => {
    try {
      setStatus('training');
      const response = await api.post('/api/ml/train', params);
      setStatus('completed');
      return response.data;
    } catch (err) {
      setStatus('failed');
      setError(err.message);
    }
  };

  return { status, error, trainModel };
}
```

### WebSocket Integration

Real-time data updates use WebSocket connections:

```typescript
// WebSocket hook for real-time signals
export function useOrderBookSignals(symbols: string[]) {
  const [signals, setSignals] = useState<Signal[]>([]);
  
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8081/ws');
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'order_book_signal') {
        setSignals(prev => updateSignals([data.signal], prev));
      }
    };
    
    return () => ws.close();
  }, [symbols]);
  
  return signals;
}
```

## Data Flow

### Frontend → Backend Flow

```
User Action (Component)
    ↓
Custom Hook (API Call)
    ↓
API Client (fetch)
    ↓
Backend Endpoint
    ↓
Response
    ↓
State Update
    ↓
Component Re-render
```

### Backend → Frontend (Real-time)

```
Backend Event
    ↓
WebSocket Broadcast
    ↓
WebSocket Hook (Frontend)
    ↓
State Update
    ↓
Component Re-render
```

## Type Definitions

### Core Types

```typescript
// trading.ts
export interface Signal {
  symbol: string;
  signal_type: 'buy' | 'sell' | 'hold';
  strength: number;
  win_probability: number;
  expected_return: number;
  confidence: number;
  timestamp: number;
}

export interface Position {
  symbol: string;
  side: 'long' | 'short';
  size: number;
  entry_price: number;
  current_price: number;
  pnl: number;
}

export interface TradingSession {
  session_id: string;
  strategy: string;
  symbols: string[];
  capital: number;
  current_capital: number;
  total_pnl: number;
  status: 'active' | 'stopped';
}
```

```typescript
// ml.ts
export interface Model {
  name: string;
  version: string;
  training_date: string;
  performance: ModelPerformance;
  is_active: boolean;
}

export interface ModelPerformance {
  r2_score: number;
  rmse: number;
  sharpe_ratio: number;
  win_rate: number;
}

export interface TrainingParams {
  days_back: number;
  batch_training: boolean;
  batch_size?: number;
}
```

## Styling Approach

### CSS Modules

Each component uses CSS modules for scoped styling:

```tsx
import styles from './MLAnalyticsDashboard.module.css';

export function MLAnalyticsDashboard() {
  return (
    <div className={styles.container}>
      <div className={styles.card}>
        {/* Content */}
      </div>
    </div>
  );
}
```

### Design System

**Color Palette:**
- Primary: Blue tones for main actions
- Success: Green for positive metrics/actions
- Warning: Yellow for cautionary states
- Danger: Red for errors/negative metrics
- Neutral: Gray scale for text and borders

**Typography:**
- Headings: Bold, larger font sizes
- Body: Regular weight
- Monospace: For numeric data and IDs

## Performance Optimization

### Memoization

Heavy computations use React.useMemo:

```typescript
const sortedModels = useMemo(() => {
  return models.sort((a, b) => 
    new Date(b.training_date).getTime() - 
    new Date(a.training_date).getTime()
  );
}, [models]);
```

### Lazy Loading

Components are code-split for faster initial load:

```typescript
const BacktestingPanel = lazy(() => import('./BacktestingPanel'));
```

### Debouncing

User inputs are debounced to reduce API calls:

```typescript
const debouncedUpdate = useDebouncedCallback((value) => {
  updateStrategy({ position_size: value });
}, 500);
```

## Error Handling

### Error Boundaries

```typescript
export class ErrorBoundary extends React.Component {
  componentDidCatch(error, errorInfo) {
    console.error('Component error:', error, errorInfo);
    // Log to error tracking service
  }

  render() {
    if (this.state.hasError) {
      return <ErrorFallback />;
    }
    return this.props.children;
  }
}
```

### API Error Handling

```typescript
try {
  const response = await api.post('/api/ml/train', params);
  // Handle success
} catch (error) {
  if (error.response?.status === 400) {
    setError('Invalid parameters');
  } else if (error.response?.status === 503) {
    setError('Service unavailable');
  } else {
    setError('An unexpected error occurred');
  }
}
```

## Testing Strategy

### Component Testing

- Unit tests for individual components
- Integration tests for component interactions
- E2E tests with Playwright for critical user flows

### Key Test Scenarios

1. ML model training workflow
2. Simulated trading session lifecycle
3. Signal table updates and persistence
4. Model comparison functionality
5. WebSocket connection and reconnection

## Future Enhancements

- Advanced charting with custom indicators
- Real-time performance dashboard
- Mobile-responsive design improvements
- Progressive Web App (PWA) support
- Advanced filtering and search for signals/trades
- Export functionality for reports and data
