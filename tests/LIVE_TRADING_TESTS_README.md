# Live Trading Comprehensive Test Suite

This directory contains comprehensive tests for the live trading tab functionality, covering all aspects of the trading workflow from page load to real-time data updates.

## Test Structure

### 1. API Tests (`test_live_trading_api.py`)
Tests backend API functionality without requiring frontend interactions:
- API health and connectivity
- Products API endpoint
- Simulated trading status
- Order book signals API
- Trading session management
- Session loading and restoration
- WebSocket connectivity

### 2. Frontend Tests (`test_live_trading_comprehensive.py`)
Tests frontend UI interactions using Selenium WebDriver:
- Page load and initialization
- Trading mode selection (simulated vs live)
- Strategy configuration
- Trading controls (start/stop/pause)
- Live order book signals display
- Open positions management
- Trading history display

### 3. Browser-Based Tests (`test_live_trading_frontend.html`)
Interactive HTML test page that can be run in any browser:
- Manual testing of UI components
- Real-time test execution
- Visual feedback and reporting
- Export test results

## Prerequisites

### Required Software
1. **Python 3.8+** with pip
2. **Chrome/Chromium browser** (for Selenium tests)
3. **ChromeDriver** (download from https://chromedriver.chromium.org/)
4. **Trading server running** on http://localhost:8001

### Install Dependencies
```bash
# Install test dependencies
pip install -r requirements-test.txt

# Or install individually
pip install aiohttp selenium pytest pytest-asyncio
```

### Install ChromeDriver
1. Download ChromeDriver from https://chromedriver.chromium.org/
2. Extract and place in your PATH
3. Or install via package manager:
   ```bash
   # macOS
   brew install chromedriver
   
   # Ubuntu/Debian
   sudo apt-get install chromium-chromedriver
   ```

## Running Tests

### Quick Start
```bash
# Run all tests
python run_live_trading_tests.py

# Run only API tests
python run_live_trading_tests.py --api-only

# Run only frontend tests
python run_live_trading_tests.py --frontend-only

# Run frontend tests with visible browser
python run_live_trading_tests.py --no-headless

# Open browser test page for manual testing
python run_live_trading_tests.py --open-browser
```

### Individual Test Files
```bash
# Run API tests directly
python test_live_trading_api.py

# Run comprehensive frontend tests
python test_live_trading_comprehensive.py
```

### Browser-Based Testing
1. Start the trading server: `uv run python -m uvicorn src.trade_bot.web.web_server_new:app --host 0.0.0.0 --port 8001`
2. Open `test_live_trading_frontend.html` in your browser
3. Navigate to the live trading tab
4. Click "Run All Tests" button
5. Review results and export if needed

## Test Categories

### 1. Page Load Tests
- ✅ Dashboard loads correctly
- ✅ Live trading tab is accessible
- ✅ Essential UI elements are present
- ✅ Tab switching works properly

### 2. Trading Mode Tests
- ✅ Simulated vs Live mode selection
- ✅ Single vs Universe symbol mode
- ✅ Mode persistence and UI updates

### 3. Strategy Configuration Tests
- ✅ Strategy type selection (SMA, EMA, RSI, etc.)
- ✅ Symbol selection (BTC-USD, ETH-USD, etc.)
- ✅ Universe configuration
- ✅ Parameter validation

### 4. Trading Controls Tests
- ✅ Start trading functionality
- ✅ Stop trading functionality
- ✅ Pause/Resume functionality
- ✅ Button state management
- ✅ Status updates

### 5. Live Order Book Signals Tests
- ✅ Signals table display
- ✅ Data loading and refresh
- ✅ Column headers and structure
- ✅ Real-time updates
- ✅ Error handling

### 6. Open Positions Tests
- ✅ Positions table display
- ✅ Empty state handling
- ✅ Data refresh functionality
- ✅ Position management

### 7. Trading History Tests
- ✅ History table display
- ✅ Pagination controls
- ✅ Empty state handling
- ✅ Trade data display

### 8. API Endpoint Tests
- ✅ Health endpoint
- ✅ Products endpoint
- ✅ Trading status endpoint
- ✅ Order book signals endpoint
- ✅ Session management
- ✅ WebSocket connectivity

## Test Results

### Console Output
Tests provide real-time feedback with:
- ✅ Pass indicators
- ❌ Fail indicators with details
- 📊 Progress tracking
- 📋 Category summaries

### JSON Reports
Detailed test results are saved as JSON files:
- `live_trading_api_test_results_YYYYMMDD_HHMMSS.json`
- `live_trading_combined_test_results_YYYYMMDD_HHMMSS.json`

### HTML Reports
Browser-based tests generate visual reports with:
- Test result summaries
- Detailed failure information
- Exportable results
- Real-time progress tracking

## Troubleshooting

### Common Issues

1. **ChromeDriver not found**
   ```
   Error: 'chromedriver' executable needs to be in PATH
   ```
   **Solution**: Install ChromeDriver and ensure it's in your PATH

2. **Server not running**
   ```
   Error: Cannot connect to server
   ```
   **Solution**: Start the trading server on port 8001

3. **Selenium timeout**
   ```
   Error: TimeoutException
   ```
   **Solution**: Increase wait times or check if elements are loading properly

4. **Missing dependencies**
   ```
   Error: ModuleNotFoundError
   ```
   **Solution**: Install required packages with `pip install -r requirements-test.txt`

### Debug Mode
Run tests with verbose logging:
```bash
# Enable debug logging
export PYTHONPATH=src
python -m pytest test_live_trading_api.py -v -s

# Run with Selenium debug
python test_live_trading_comprehensive.py --no-headless
```

## Test Configuration

### Environment Variables
```bash
# Set test server URL
export TEST_SERVER_URL=http://localhost:8001

# Set headless mode
export SELENIUM_HEADLESS=true

# Set test timeout
export TEST_TIMEOUT=30
```

### Custom Test Parameters
Modify test parameters in the test files:
- Symbol selection
- Strategy parameters
- Timeout values
- Wait intervals
- Test data

## Contributing

### Adding New Tests
1. Follow the existing test structure
2. Use descriptive test names
3. Include proper error handling
4. Add to the appropriate test category
5. Update this README

### Test Naming Convention
- `test_[component]_[functionality]_[expected_behavior]`
- Example: `test_trading_controls_start_button_enabled`

### Best Practices
- Test both success and failure cases
- Use meaningful assertions
- Include detailed error messages
- Clean up resources after tests
- Make tests independent and repeatable

## Performance Considerations

### Test Execution Time
- API tests: ~30 seconds
- Frontend tests: ~2-3 minutes
- Combined suite: ~3-5 minutes

### Resource Usage
- Memory: ~100-200MB
- CPU: Moderate during browser automation
- Network: Minimal (local server)

### Optimization Tips
- Run API tests first (faster)
- Use headless mode for CI/CD
- Parallel execution where possible
- Cache test data when appropriate

## CI/CD Integration

### GitHub Actions Example
```yaml
name: Live Trading Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v3
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install -r requirements-test.txt
          sudo apt-get install chromium-chromedriver
      - name: Start server
        run: |
          python -m uvicorn src.trade_bot.web.web_server_new:app --host 0.0.0.0 --port 8001 &
          sleep 10
      - name: Run tests
        run: python run_live_trading_tests.py --api-only
```

This comprehensive test suite ensures the live trading functionality works correctly across all components and provides confidence in the system's reliability.
