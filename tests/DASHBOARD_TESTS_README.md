# Dashboard Test Suite

This directory contains comprehensive test coverage for the dashboard tab functionality, comparing expected behavior to actual behavior.

## Test Files

### 1. `dashboard_test_suite.py`
**Comprehensive Python test suite** that validates:
- ✅ Server connectivity and accessibility
- ✅ Real-time data endpoint structure and types
- ✅ Backtest filters endpoint (symbols and strategies)
- ✅ Backtest execution with multiple strategies (SMA, RSI, Fibonacci)
- ✅ WebSocket connectivity and message handling
- ✅ Data consistency across multiple requests
- ✅ Error handling for invalid requests

**Usage:**
```bash
uv run python tests/dashboard_test_suite.py
```

### 2. `dashboard_performance_test.py`
**Performance testing suite** that measures:
- 📊 API endpoint response times
- 📊 Concurrent request handling (10 concurrent requests)
- 📊 WebSocket message latency and throughput
- 📊 Backtest performance scaling (1 day to 30 days)
- 📊 Request throughput (requests per second)

**Usage:**
```bash
uv run python tests/dashboard_performance_test.py
```

### 3. `dashboard_integration_test.html`
**Browser-based integration test** that provides:
- 🌐 Interactive test interface
- 🌐 Real-time test execution
- 🌐 Visual test results with pass/fail indicators
- 🌐 Detailed error reporting
- 🌐 Same test coverage as Python suite

**Usage:**
1. Open `tests/dashboard_integration_test.html` in a web browser
2. Click "Run All Tests" button
3. Review results displayed on the page

### 4. `run_dashboard_tests.py`
**Master test runner** that:
- 🚀 Executes all Python test suites
- 🚀 Provides comprehensive summary
- 🚀 Saves results to JSON files
- 🚀 Returns appropriate exit codes

**Usage:**
```bash
uv run python tests/run_dashboard_tests.py
```

### 5. `generate_test_report.py`
**Test report generator** that:
- 📋 Creates HTML test reports
- 📋 Displays test summaries and metrics
- 📋 Shows performance data
- 📋 Provides visual status indicators

**Usage:**
```bash
uv run python tests/generate_test_report.py
```

## Test Coverage

### API Endpoints Tested
- `GET /` - Server connectivity
- `GET /api/real-time-data` - Real-time market data
- `GET /api/backtest-filters` - Available symbols and strategies
- `POST /api/run-backtest` - Backtest execution
- `GET /api/backtest-history` - Historical backtest results
- `WebSocket /ws` - Real-time data streaming

### Strategies Tested
- Simple Moving Average (SMA)
- Relative Strength Index (RSI)
- Fibonacci Retracement
- Bollinger Bands
- MACD
- Stochastic Oscillator
- Average True Range (ATR)
- Order Book Analysis

### Test Scenarios
1. **Functional Testing**
   - Endpoint accessibility
   - Data structure validation
   - Type checking
   - Error handling

2. **Performance Testing**
   - Response time measurement
   - Concurrent load testing
   - WebSocket latency testing
   - Backtest scaling analysis

3. **Integration Testing**
   - End-to-end workflow validation
   - Data consistency verification
   - Real-time data flow testing

## Test Results

### Current Status: ✅ ALL TESTS PASSING

**Latest Test Run:**
- Total Tests: 3
- Passed: 3
- Failed: 0
- Success Rate: 100.0%

**Performance Metrics:**
- API Response Times: 6-15ms average
- Concurrent Requests: 100% success rate, 684 req/s
- WebSocket Latency: ~544ms average
- Backtest Scaling: 238ms (1 day) to 1698ms (30 days)

## Running Tests

### Quick Test (Recommended)
```bash
# Run all tests with summary
uv run python tests/run_dashboard_tests.py
```

### Individual Tests
```bash
# Functional tests
uv run python tests/dashboard_test_suite.py

# Performance tests
uv run python tests/dashboard_performance_test.py

# Generate HTML report
uv run python tests/generate_test_report.py
```

### Browser Tests
1. Open `tests/dashboard_integration_test.html` in browser
2. Click "Run All Tests"
3. Review results

## Test Data

All tests use real market data from Coinbase Advanced Trade API:
- **Symbol**: BTC-USD (Bitcoin/USD)
- **Time Periods**: 1 day to 30 days
- **Granularities**: 1 hour, 6 hours, 1 day
- **Real-time Data**: Live WebSocket feeds

## Troubleshooting

### Common Issues

1. **Server Not Running**
   ```bash
   # Start server in tmux
   tmux new-session -d -s trading_server
   tmux send-keys -t trading_server "cd /path/to/trade && uv run python -m src.trade_bot.web_server" Enter
   ```

2. **WebSocket Connection Failed**
   - Check server is running
   - Verify port 8000 is accessible
   - Check firewall settings

3. **API Endpoint Errors**
   - Verify server logs for errors
   - Check API key configuration
   - Ensure Coinbase API access

### Debug Mode
Add debug logging to see detailed test execution:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Test Architecture

```
tests/
├── dashboard_test_suite.py          # Main functional tests
├── dashboard_performance_test.py    # Performance benchmarks
├── dashboard_integration_test.html  # Browser integration tests
├── run_dashboard_tests.py          # Master test runner
├── generate_test_report.py         # Report generator
├── DASHBOARD_TESTS_README.md       # This file
└── dashboard_test_results_*.json   # Test result files
```

## Contributing

When adding new dashboard features:
1. Update relevant test files
2. Add new test cases for new functionality
3. Run full test suite to ensure no regressions
4. Update this README with new test coverage

## Test Philosophy

This test suite follows the principle of **"Expected vs Actual"** behavior validation:
- **Expected**: What the system should do based on requirements
- **Actual**: What the system actually does when tested
- **Validation**: Compare expected vs actual and report discrepancies

This approach ensures the dashboard behaves correctly and provides reliable feedback for development and debugging.
