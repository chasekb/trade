# API reference

The Drogon controller in `include/api/PredictController.hpp` is the
authoritative route registry. The browser normally calls these routes through
the Next.js same-origin proxy; host-side direct calls use port 8081.

## Base URLs

- Dashboard: `http://localhost:3000`
- C++ backend: `http://localhost:8081`
- Container-to-container backend: `http://cpp-backend:8080`

## Health and products

```text
GET  /health
GET  /api/products
POST /api/log
POST /predict
```

## Trading statistics

```text
GET /api/trades/stats
```

The response uses backend conventions documented in
`docs/STRATEGY_DIAGNOSTICS_CONTRACT.md`: `win_rate` is 0–100 and
`max_drawdown` is dollars.

## Simulated trading

Lifecycle and strategy updates:

```text
POST /api/simulated-trading/start
POST /api/trading/simulated/start       # compatibility alias
POST /api/simulated-trading/stop
POST /api/trading/simulated/stop        # compatibility alias
GET  /api/simulated-trading/status
GET  /api/trading/simulated/status      # compatibility alias
GET  /api/simulated-trading/diagnosis
GET  /api/simulated-trading/{session_id}/diagnosis
POST /api/trading/simulated/update-strategy-params
```

Order-book signals:

```text
GET /api/orderbook/simulated-signals?symbols=BTC-USD,ETH-USD&page=1&per_page=50
GET /api/orderbook/live-signals?symbols=BTC-USD,ETH-USD&page=1&per_page=50
```

Signal responses include pagination and the latest-by-symbol diagnostics,
including `data_status`, `signal_reason`, `criteria_analysis`, `ml_analysis`,
`strength_composition`, and `execution_analysis`. An optional `session_id`
keeps persisted signal reads scoped to one simulated session.

The simulated status portfolio uses:

```text
total_value = cash_balance + total_positions_value
```

`total_positions_value` is signed; gross exposure is reported separately as
`total_positions_exposure`. Portfolio `total_fees` must not be added again to a
per-trade fee sum.

## Live trading

```text
GET  /api/live-portfolio/status
GET  /api/trading/live/positions
POST /api/trading/live/start
POST /api/trading/live/stop
GET  /api/trading/live/status
POST /api/trading/live/update-strategy-params
POST /api/trading/live/execute
POST /api/trading/live/close-position
POST /api/trading/live/liquidate-holdings
GET  /api/trading/execution-reconciliation
```

Live execution remains fail-closed on account, cash, pending-order, position,
notional, and spot-market safety checks. Simulated fills are not evidence of a
Coinbase order submission or fill.

## ML

```text
POST   /api/ml/train
GET    /api/ml/status
GET    /api/ml/performance
GET    /api/ml/models
POST   /api/ml/models/set_active
GET    /api/ml/config
POST   /api/ml/config
GET    /api/ml/pnl-trades
POST   /api/ml/prediction-comparison
DELETE /api/ml/databases
```

The C++ backend owns these routes. There is no separate ML server URL. Request
and response fields must be checked against the controller implementation and
frontend client before adding examples; this document intentionally does not
invent payload schemas for routes whose schema is implementation-defined.

The legacy short aliases `/ml/train`, `/ml/status`, and `/ml/performance` are
also registered for compatibility; new clients should use the `/api/ml/*`
paths.

## Source of truth

- Route registration: `include/api/PredictController.hpp`
- Handler behavior: `src/api/PredictController.cpp`
- Browser client: `frontend/lib/api.ts`
- Frontend hooks: `frontend/hooks/`
- Simulated portfolio contract: `docs/reports/simulated-portfolio-valuation-contract.md`