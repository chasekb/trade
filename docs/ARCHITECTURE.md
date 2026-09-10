# Trade architecture

## Runtime boundary

The repository has two runtime applications:

1. `src/` and `include/` contain one Drogon C++ executable,
   `trading_bot_cpp`. It owns HTTP routes, trading services, Coinbase access,
   ML model loading/inference, persistence, and diagnostics.
2. `frontend/` contains the Next.js 16 / React 19 dashboard. It reads the
   backend through same-origin API calls and renders the six dashboard areas:
   Overview, Live Trading, Simulated Trading, Positions, Backtesting, and ML
   Analytics.

PostgreSQL stores trading and training records. Redis stores runtime/cache
state. There is no separate Python backend, ML server, Qdrant service, or
SQLite runtime in the current Compose stack.

## C++ backend layers

- `src/api/`: `PredictController` registers the complete HTTP surface.
- `src/exchange/`: Coinbase authentication, REST clients, and order models.
- `src/trading/`: live and simulated trading, signal generation, sizing,
  preflight checks, reconciliation, accounting, and diagnostics.
- `src/ml/`: feature engineering, model training/validation, ONNX and
  transformer inference, metrics, and execution cohorts.
- `src/db/` and `src/cache/`: PostgreSQL and Redis adapters.
- `include/`: shared contracts and headers used by production and CTest
  targets.

`CMakeLists.txt` is the source of truth for production sources and backend test
targets. The production binary links Drogon, JsonCpp, nlohmann-json, libpqxx,
Redis++, spdlog, ONNX Runtime, xtensor, Python development libraries, Torch,
OpenSSL, and the vcpkg toolchain dependencies.

## Data flow

```text
Coinbase REST/WebSocket data
          |
          v
  C++ exchange + trading services ---> PostgreSQL
          |                            Redis runtime/cache
          v
  signal / ML / execution diagnostics
          |
          v
  Drogon /api/* ---> Next.js rewrites ---> React dashboard
```

The simulated order-book path preserves the selected universe, normalizes one
latest signal per symbol, records market-data/inference/profitability/execution
diagnostics, and persists trades and portfolio state. The live path applies
additional account, cash, pending-order, position, notional, and spot-market
safety checks before submitting Coinbase orders.

## Frontend data boundaries

`frontend/lib/api.ts` is the HTTP and local-simulation boundary. React Query
hooks in `frontend/hooks/` fetch and cache data. Components under
`frontend/components/dashboard/` render normalized snapshots. Shared simulated
portfolio and statistics rules belong in
`frontend/lib/simulatedTradingStats.ts`, not in individual panels.

Important wire conventions:

- `win_rate` is a 0–100 percentage.
- `max_drawdown` is dollars.
- `total_value = cash_balance + total_positions_value`.
- `total_positions_value` is signed; gross exposure is separate.
- Portfolio `total_fees` replaces, rather than adds to, a per-trade fee sum.
- Zero-PnL open legs do not count as winners or losers.

## Deployment topology

Compose starts `cpp-backend`, `frontend`, `db`, and `redis`. The backend listens
on container port 8080 and is published on host port 8081. The frontend listens
on host port 3000. See [DEPLOYMENT.md](DEPLOYMENT.md) for commands and health
checks.