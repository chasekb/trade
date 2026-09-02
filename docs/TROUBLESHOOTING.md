# Troubleshooting

These commands target the current C++/Next.js Compose stack. The retired
Python/FastAPI examples on port 8000 are not applicable.

## Check service health

```bash
podman-compose ps
curl -fsS http://localhost:8081/health
curl -fsS http://localhost:3000/api/health
podman-compose logs --tail=200 cpp-backend frontend
```

If the frontend is healthy but API requests fail, inspect the backend health
and logs first. Inside Compose, the frontend target is `cpp-backend:8080`, not
`localhost:8081`.

## Startup and dependency failures

```bash
podman-compose up --no-build
podman-compose logs db redis cpp-backend
```

The backend waits for healthy PostgreSQL and Redis services. The database is
published on host port 15432 by default while its Compose address remains
`db:5432`. If the host port is occupied, use:

```bash
POSTGRES_HOST_PORT=55432 podman-compose up --no-build
```

## Stale or incorrect images

The default images are branch-tagged GHCR images. Recreate them after a new
push, or build local images explicitly:

```bash
podman-compose pull
podman-compose up --no-build
```

```bash
podman-compose build
podman-compose up --no-build
```

Confirm the image names with `podman-compose config` before debugging source
changes that may not be present in the running container.

## Simulated trading shows no trades

Use the dashboard's Simulated Trading diagnosis, or query the backend:

```bash
curl -fsS 'http://localhost:8081/api/simulated-trading/status'
curl -fsS 'http://localhost:8081/api/simulated-trading/diagnosis'
curl -fsS 'http://localhost:8081/api/orderbook/simulated-signals?page=1&per_page=100'
```

Interpret the counts in order: selected symbols, valid market data, model
readiness, generated signals, profitability/ML gates, executable intents,
execution blockers, and persisted trades. Failed market data and transformer
warm-up must remain visible as diagnostics; they are not valid HOLD signals.

For Coinbase-backed sessions, TLS/network errors are market-data failures, not
proof that the strategy generated a losing or blocked trade. Check the
backend logs and per-symbol diagnostics before changing strategy thresholds.

## Frontend development checks

```bash
cd frontend
npm test
npx tsc --noEmit
npm run lint
```

The simulated statistics contract is centralized in
`frontend/lib/simulatedTradingStats.ts`. Do not duplicate portfolio arithmetic
inside dashboard components.

## C++ test failures

Run the supported containerized test command:

```bash
podman-compose -f docker-compose.test.yml up --build cpp-test
```

The backend dependencies and test targets are defined by `Dockerfile.cpp`,
`vcpkg.json`, and `CMakeLists.txt`. Final multi-architecture build proof comes
from the exact-head GitHub Actions Docker Build Validation run.

## Safe cleanup

```bash
podman-compose down
```

Do not delete PostgreSQL data or `data/cache/` during routine troubleshooting.