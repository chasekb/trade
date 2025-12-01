# Troubleshooting Guide

Comprehensive troubleshooting guide based on common issues and their solutions.

## ML System Issues

### 1. NaN Scores During Model Training

**Symptoms:**
- Training logs show `NaN` for R² score or RMSE
- Model training completes but performance metrics are invalid
- Error message: "Insufficient samples for train/test split"

**Root Cause:**
Insufficient training samples for the configured train/test split ratio.

**Solutions:**

**Option 1: Increase Training Data**
```bash
# Use more historical data
curl -X POST http://localhost:8000/api/ml/train \
  -H "Content-Type: application/json" \
  -d '{"days_back": 60}'
```

**Option 2: Use Batch Training**
```bash
# Enable batch training for better handling of small datasets
curl -X POST http://localhost:8000/api/ml/train \
  -H "Content-Type: application/json" \
  -d '{"batch_training": true, "batch_size": 500}'
```

**Fix Applied:**
The system now automatically adjusts `test_size` based on sample count to prevent this issue.

###  2. Extreme Win Probability / Expected Return Values

**Symptoms:**
- Win probability showing extremely low values (e.g., 5.0%)
- Expected return showing extreme negative values (e.g., -439378310.2%)
- Signal confidence appears normal but derived metrics are wrong

**Root Cause:**
Division by zero or logarithm of zero in feature engineering when `ask_volume` is zero.

**Solutions:**

**Immediate Fix:**
Retrain the model to use updated feature engineering:
```bash
curl -X POST http://localhost:8000/api/ml/train \
  -H "Content-Type: application/json" \
  -d '{"days_back": 30}'
```

**Verification:**
Check that the active model uses the latest feature engineering:
```bash
curl http://localhost:8000/api/ml/status
# Verify training_date is recent
```

**Fix Applied:**
- Feature engineering now uses log transform with epsilon: `log(volume + 1e-8)`
- Division operations include safety checks: `numerator / (denominator + 1e-8)`

### 3. ML Server 503 Errors (Model is Loading)

**Symptoms:**
- HTTP 503 response from ML endpoints
- Error message: "Model is loading, please try again later"
- Occurs when trying to set active model or make predictions

**Root Cause:**
`model_ready` flag remains `False` if initial model load fails.

**Solutions:**

**Check ML Server Status:**
```bash
curl http://localhost:8000/api/ml/status
```

**Restart ML Server (Docker):**
```bash
docker-compose restart backend
```

**Set Active Model:**
```bash
curl -X POST http://localhost:8000/api/ml/models/set_active \
  -H "Content-Type: application/json" \
  -d '{"model_name": "trading_optimizer_v20241201_112900"}'
```

**Fix Applied:**
ML server now sets `model_ready=True` during initialization regardless of initial model load success, allowing subsequent model activation.

### 4. Model Training Display Shows "Failed" When Training Succeeds

**Symptoms:**
- Frontend shows "Failed to train model"
- Backend logs show successful training
- Status endpoint returns `training_started`

**Root Cause:**
Frontend incorrectly interprets `training_started` status as a failure.

**Solutions:**

**Verify Backend Status:**
```bash
curl http://localhost:8000/api/ml/status
```

**Check Training Logs:**
```bash
docker-compose logs backend | grep "training"
```

**Fix Applied:**
Frontend now correctly displays "Training Started" for `training_started` status and polls for completion.

### 5. Model Not Found Error

**Symptoms:**
- Error: "Model not found: trading_optimizer_vXXXXXX"
- Cannot set active model
- Model list is empty

**Root Cause:**
Model files missing from `data/models/` directory or metadata corruption.

**Solutions:**

**List Available Models:**
```bash
curl http://localhost:8000/api/ml/models
```

**Train New Model:**
```bash
curl -X POST http://localhost:8000/api/ml/train \
  -H "Content-Type: application/json" \
  -d '{"days_back": 30}'
```

**Check Model Directory:**
```bash
ls -la data/models/
```

**Clean Up Empty Metadata:**
```bash
# Remove empty metadata files
find data/models/ -name "*.json" -size 0 -delete
```

### 6. Insufficient Training Data

**Symptoms:**
- Training fails with "No training data available"
- Very few samples in database
- Recently started simulated trading

**Root Cause:**
Not enough order book signals or trades collected yet.

**Solutions:**

**Check Data Availability:**
```bash
# Check signals count
sqlite3 data/databases/trading_cache.db \
  "SELECT COUNT(*) FROM order_book_signals;"

# Check trades count
sqlite3 data/databases/trading_cache.db \
  "SELECT COUNT(*) FROM individual_trades;"
```

**Generate Training Data:**
1. Navigate to Simulated Trading tab
2. Start a simulated trading session
3. Let it run for at least 30-60 minutes
4. Stop the session
5. Attempt training again

**Minimum Requirements:**
- At least 100 order book signals
- At least 50 completed trades

## Frontend Issues

### 7. Order Book Signals Table Not Rendering

**Symptoms:**
- Signals table empty despite backend showing signals generated
- Table only shows signals for one symbol
- Signals disappear when switching tabs

**Root Cause:**
- WebSocket disconnection
- Component lifecycle issues
- Symbol list not properly initialized

**Solutions:**

**Check WebSocket Connection:**
```javascript
// In browser console
console.log('WebSocket status:', navigator.onLine);
```

**Verify Signals API:**
```bash
curl "http://localhost:8000/api/simulated-trading/signals?symbols=BTC-USD,ETH-USD"
```

**Refresh Page:**
Simply refreshing the browser often resolves stale WebSocket connections.

**Fix Applied:**
- Signals table now persists data across tab switches
- Improved symbol list initialization
- Better WebSocket reconnection handling

### 8. Model Prediction Comparison Shows "N/A" or "Error"

**Symptoms:**
- Comparison results show "N/A" for version
- "Error" for expected return
- Warning: "Some models encountered errors during prediction"

**Root Cause:**
- Model version mismatch
- Prediction endpoint error
- Missing model metadata

**Solutions:**

**Check Available Models:**
```bash
curl http://localhost:8000/api/ml/models
```

**Test Prediction Endpoint:**
```bash
curl -X POST http://localhost:8000/api/ml/predict \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC-USD",
    "bid_ask_imbalance": 1.2,
    "spread_percent": 0.05
  }'
```

**Check Backend Logs:**
```bash
docker-compose logs backend | grep "prediction"
```

### 9. Frontend Build Errors

**Symptoms:**
- `npm run build` fails
- Type errors in TypeScript
- Missing dependencies

**Solutions:**

**Clear Cache and Reinstall:**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

**Fix Type Errors:**
```bash
npm run type-check
```

**Update Dependencies:**
```bash
npm update
```

## Trading System Issues

### 10. Orders Not Executing After Signals Generated

**Symptoms:**
- Signals appear in table
- No trades executed
- Order book shows activity but no positions opened

**Root Cause:**
- Order prioritization waiting for all symbols to have signals
- Risk management constraints preventing execution
- Insufficient capital

**Solutions:**

**Check Order Prioritization:**
Ensure all symbols in the universe have generated signals before execution begins.

**Verify Capital:**
```bash
curl "http://localhost:8000/api/simulated-trading/status"
# Check current_capital > 0
```

**Review Strategy Parameters:**
- Reduce position sizes if hitting capital limits
- Check stop loss / take profit settings
- Verify order prioritization mode is set

### 11. Signal Confidence Always Same Value

**Symptoms:**
- All signals show same confidence (e.g., 1.0)
- No variation in confidence across signals

**Root Cause:**
- Older implementation using `tanh` normalization
- Win probability incorrectly used as confidence

**Solutions:**

**Verify Latest Implementation:**
The system should use `confidence = abs(signal_value)`.

**Check Code Version:**
```bash
grep "confidence.*signal_value" src/trade_bot/ml/ml_optimizer.py
```

**Fix Applied:**
Reverted to using absolute signal value for confidence, ensuring meaningful variation.

## Database Issues

### 12. Database Lock Errors

**Symptoms:**
- "database is locked" error
- Timeouts during database operations
- Multiple processes accessing database

**Solutions:**

**Increase Timeout:**
```python
# In code configuration
db_timeout = 30  # seconds
```

**Close Idle Connections:**
```bash
# Restart backend to reset connections
docker-compose restart backend
```

**Check Multiple Processes:**
```bash
lsof data/databases/trading_cache.db
```

### 13. Missing Database Tables

**Symptoms:**
- "no such table" errors
- Fresh installation
- Database corruption

**Solutions:**

**Reinitialize Database:**
```bash
# Backup existing data
cp data/databases/trading_cache.db data/databases/trading_cache.db.backup

# Remove and recreate
rm data/databases/trading_cache.db

# Restart backend to recreate tables
docker-compose restart backend
```

## Docker and Deployment Issues

### 14. Port Already in Use

**Symptoms:**
- Error: "port 8000 is already allocated"
- Cannot start Docker containers
- Address already in use

**Solutions:**

**Check Port Usage:**
```bash
lsof -i :8000
lsof -i :3000
lsof -i :6333
```

**Kill Existing Process:**
```bash
kill -9 <PID>
```

**Change Ports in docker-compose.yml:**
```yaml
ports:
  - "8001:8000"  # External:Internal
```

### 15. Container Build Failures


**Symptoms:**
- Docker build fails
- Dependency installation errors
- Out of disk space

**Solutions:**

**Clean Docker Cache:**
```bash
docker system prune -a
```

**Rebuild Containers:**
```bash
docker-compose build --no-cache
docker-compose up
```

**Check Disk Space:**
```bash
df -h
```

## Performance Issues

### 16. Slow ML Training

**Symptoms:**
- Training takes very long time
- System becomes unresponsive
- Memory usage spikes

**Solutions:**

**Use Batch Training:**
```bash
curl -X POST http://localhost:8000/api/ml/train \
  -H "Content-Type: application/json" \
  -d '{
    "batch_training": true,
    "batch_size": 500,
    "days_back": 30
  }'
```

**Reduce Historical Data:**
```bash
# Use fewer days of data
curl -X POST http://localhost:8000/api/ml/train \
  -H "Content-Type: application/json" \
  -d '{"days_back": 14}'
```

**Monitor Resources:**
```bash
docker stats
```

### 17. WebSocket Disconnections

**Symptoms:**
- Real-time updates stop
- "WebSocket disconnected" in console
- Need to refresh page frequently

**Solutions:**

**Check Network:**
Ensure stable internet connection and no firewall blocking WebSocket.

**Increase Timeout:**
```typescript
// In WebSocket client
const ws = new WebSocket(url, {
  perMessageDeflate: false,
  handshakeTimeout: 10000
});
```

**Manual Reconnect:**
Refresh the page to re-establish WebSocket connection.

## Getting Help

If you encounter issues not covered in this guide:

1. **Check Logs:**
   ```bash
   docker-compose logs backend
   docker-compose logs frontend
   ```

2. **Verify Service Health:**
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:3000/api/health
   ```

3. **Review Recent Changes:**
   Check `docs/CHANGELOG.md` for recent updates that might affect behavior.

4. **Create an Issue:**
   Open a GitHub issue with:
   - Detailed description of the problem
   - Steps to reproduce
   - Relevant log excerpts
   - System information (OS, Docker version, etc.)

## Common Diagnostic Commands

```bash
# Check all services status
docker-compose ps

# View real-time logs
docker-compose logs -f backend

# Restart specific service
docker-compose restart backend

# Full system restart
docker-compose down
docker-compose up -d

# Check database integrity
sqlite3 data/databases/trading_cache.db "PRAGMA integrity_check;"

# Monitor resource usage
docker stats

# Test API endpoints
curl http://localhost:8000/api/ml/status
curl http://localhost:8000/api/simulated-trading/status
```
