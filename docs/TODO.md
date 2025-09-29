# TODO List

## Top Priority Items

### Critical Bug Fixes & Stability
- [ ] **Fix remaining test import errors and ensure all tests can run successfully**
  - [ ] a) Resolve remaining 20 test collection errors
  - [ ] b) Fix any missing module imports in test files
  - [ ] c) Ensure all test dependencies are properly configured
  - [ ] d) Verify all tests can be executed with `uv run python -m pytest tests/`
  - [ ] e) Run full test suite to ensure no regressions
- [x] **On simulated trading tab, when start trading is pressed and trades are executed, no trade information is written to database**
  - [x] a) Investigate why trades are not being saved to individual_trades table
  - [x] b) Verify database connection and session setup in simulated trading flow
  - [x] c) Check if _save_trade_to_db method is being called correctly
  - [x] d) Ensure db_manager and session_id are properly initialized
  - [x] e) Test and verify trades are written to trading_cache.db after fix
- [x] **ML signal integration into the live orderbook signals endpoint for the simulated trading tab**
  - [x] a) Import the MLStrategy class
  - [x] b) Add ML signal generation alongside the OrderBookStrategy
  - [x] c) Combine both signal types in the response
  - [x] d) Update the frontend to display ML signal information
- [x] On simulated trading tab, in simulated trading statistics widget, in performance trends fix all calculations
- [x] Create tests to validate all calculations in Simulated Trading Statistics widget. Risk Metrics, Trading Activity, and Performance Trends display incorrect values
- [x] On simulated trading tab, in live order book signals, Large Trade Analysis is N/A
- [x] On simulated trading tab, in live order book signals, provide a hover that describes the meaning of the displays for Squeeze Analysis, Imbalance Analysis, and Large Trade Analysis
- [x] Develop and include a machine learning signal that takes as input all available data about each trade and iteratively learns to predict win probability for each trade and predict probabilities for size of return
- [ ] Fix any remaining JavaScript console errors
- [ ] Resolve WebSocket connection stability issues
- [ ] Ensure all API endpoints return consistent error handling
- [ ] Fix any memory leaks in long-running sessions
- [ ] Resolve database connection timeout issues

### Essential User Experience
- [ ] Add loading states for all async operations
- [ ] Implement proper error messages for failed operations
- [ ] Add confirmation dialogs for destructive actions
- [ ] Ensure all forms have proper validation
- [ ] Add keyboard navigation support

### Core Trading Functionality
- [ ] Implement proper position sizing validation
- [ ] Add trade execution confirmation system
- [ ] Ensure accurate P&L calculations
- [ ] Implement proper risk management checks
- [ ] Add trade execution logging and audit trail

## High Priority Items

### Frontend/UI Improvements
- [ ] Add dark mode toggle to the dashboard
- [ ] Implement responsive design for mobile devices
- [ ] Add keyboard shortcuts for common actions
- [ ] Create user preferences/settings panel
- [ ] Add data export functionality (CSV, JSON)

### Trading Features
- [ ] Implement advanced order types (stop-loss, take-profit)
- [ ] Add portfolio rebalancing functionality
- [ ] Create custom trading strategies builder
- [ ] Implement backtesting with multiple timeframes
- [ ] Add paper trading mode with real-time data

### Data & Analytics
- [ ] Add more technical indicators (RSI, MACD, Bollinger Bands)
- [ ] Implement portfolio performance analytics
- [ ] Create risk management tools
- [ ] Add market sentiment analysis
- [ ] Implement correlation analysis between assets

### API & Integration
- [ ] Add support for additional exchanges (Binance, Kraken)
- [ ] Implement webhook notifications
- [ ] Add REST API rate limiting
- [ ] Create API key management system
- [ ] Implement OAuth authentication

### Database & Storage
- [ ] Add data archiving for old trades
- [ ] Implement database backup/restore
- [ ] Add data compression for historical data
- [ ] Create data migration tools
- [ ] Implement database optimization

### Security & Compliance
- [ ] Add two-factor authentication
- [ ] Implement audit logging
- [ ] Add data encryption at rest
- [ ] Create compliance reporting tools
- [ ] Add IP whitelisting functionality

### Performance & Monitoring
- [ ] Implement application monitoring
- [ ] Add performance metrics dashboard
- [ ] Create alerting system for errors
- [ ] Implement caching strategies
- [ ] Add load balancing support

### Documentation & Testing
- [ ] Create comprehensive API documentation
- [ ] Add unit tests for all modules
- [ ] Implement integration tests
- [ ] Create user manual
- [ ] Add developer documentation

## Medium Priority Items

### User Experience
- [ ] Add tooltips and help text
- [ ] Implement drag-and-drop functionality
- [ ] Create customizable dashboard layouts
- [ ] Add search functionality across all data
- [ ] Implement data filtering and sorting

### Trading Tools
- [ ] Add position sizing calculator
- [ ] Create risk/reward ratio calculator
- [ ] Implement trade journal functionality
- [ ] Add performance comparison tools
- [ ] Create trading calendar

### Data Visualization
- [ ] Add candlestick charts
- [ ] Implement volume analysis charts
- [ ] Create portfolio allocation pie charts
- [ ] Add performance comparison charts
- [ ] Implement heat maps for correlations

### Automation
- [ ] Add scheduled trading functionality
- [ ] Implement email/SMS notifications
- [ ] Create automated report generation
- [ ] Add data synchronization tools
- [ ] Implement automated testing

## Low Priority Items

### Advanced Features
- [ ] Add machine learning predictions
- [ ] Implement social trading features
- [ ] Create copy trading functionality
- [ ] Add news sentiment analysis
- [ ] Implement advanced charting tools

### Integration & Extensions
- [ ] Create browser extension
- [ ] Add mobile app
- [ ] Implement Slack/Discord integration
- [ ] Add Telegram bot
- [ ] Create WordPress plugin

### Infrastructure
- [ ] Add Docker containerization
- [ ] Implement Kubernetes deployment
- [ ] Add CI/CD pipeline
- [ ] Create monitoring and alerting
- [ ] Implement auto-scaling

## Completed Items

### Recent Completed Tasks
- [x] **On simulated trading tab, in simulated trading statistics widget, in performance trends fix all calculations** - Verified that performance trends calculations (best trade, worst trade, avg win, avg loss) are working correctly. The calculations were already accurate from previous fixes.
- [x] **Develop and include a machine learning signal that takes as input all available data about each trade and iteratively learns to predict win probability for each trade and predict probabilities for size of return** - Created comprehensive ML signal generator (`ml_signal.py`) and ML-enhanced trading strategy (`ml_strategy.py`) with feature extraction, model training, prediction generation, and accuracy tracking. Includes test suite for validation.
- [x] Create comprehensive tests for Simulated Trading Statistics calculations (8 test cases, all passing)
- [x] Fix Large Trade Analysis showing N/A in live order book signals with real trade data analysis
- [x] Add hover descriptions for analysis displays in live order book signals (Squeeze, Imbalance, Large Trade)
- [x] Move trading statistics widget from dashboard tab to simulated trading tab
- [x] Remove connections to trading statistics widget that don't connect to simulated trading session
- [x] Ensure all positions opened/closed reflect on trading statistics widget
- [x] Ensure trading does not begin until start trading button is pressed
- [x] Add .env copy to .gitignore and remove from git tracking
- [x] Update project statistics on README
- [x] Update API Endpoints section of README
- [x] Fix simulated trading history to only display trades from current session
- [x] Fix open positions count accuracy in portfolio status widget
- [x] Add trade type classification (simulated vs live)
- [x] Implement session-based trading history filtering
- [x] Update documentation (CHANGELOG, PROJECT_OVERVIEW, TEST_RESULTS)

---

**Note:** This TODO list is for future reference. Work on these items will only begin when explicitly requested by the user.
