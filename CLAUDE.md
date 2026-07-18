# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A trading bot with two halves:

- **C++ backend** (`src/`, `include/`) — a single Drogon HTTP server (`trading_bot_cpp`) that does live/simulated trading, ML inference (ONNX Runtime + libtorch), and serves every `/api/*` endpoint. Talks to Postgres (libpqxx) and Redis.
- **Next.js frontend** (`frontend/`) — a 6-tab trading dashboard (Overview, Live Trading, Simulated Trading, Positions, Backtesting, ML Analytics). Next 16 / React 19, TanStack React Query, Chart.js, Tailwind 4, Zustand.

The root README still describes a Python/FastAPI backend (`app.py`); that no longer exists — the C++ backend replaced it.

## Commands

### Frontend (run from `frontend/`)

```bash
npm test                          # jest (unit tests)
npx jest lib/simulatedTradingStats.test.ts   # single test file
npx jest -t "test name"           # single test by name
npx tsc --noEmit                  # typecheck
npm run lint                      # eslint
npm run dev                       # dev server on :3000
npm run test:e2e                  # playwright
```

### C++ backend

There is no host-native build; it builds inside Docker with a vcpkg toolchain (`Dockerfile.cpp`). Unit tests (`src/tests/test_*.cpp`, each a CMake target) run in the container:

```bash
docker compose -f docker-compose.test.yml run --rm cpp-test
```

To add a source file, add it to `set(SOURCES ...)` in `CMakeLists.txt`; test executables are separate `add_executable` targets there.

### Building and CI

**Prefer remote CI over local Docker builds.** Pushing to `dev` or `main` triggers `.github/workflows/docker-build.yml` ("Docker Build Validation"), which builds cpp-backend and frontend images for amd64+arm64 and publishes to `ghcr.io/chasekb/trade`. Verify with:

```bash
gh run list --workflow docker-build.yml --limit 3
gh run view <run-id> --json status,conclusion,jobs
```

`docker-compose.yml` pulls those published images (`ghcr.io/chasekb/trade/{cpp-backend,frontend}:dev`); it does not build locally. Services: cpp-backend (host 8081 → container 8080), frontend (3000), db, redis — startup is gated on health checks.

## Architecture notes

- **`src/api/PredictController.cpp`** is the single API controller — all HTTP routes (`/api/trades/stats`, `/api/ml/performance`, simulated/live trading endpoints, `/health`) live there. Before assuming an endpoint or response field exists, check it; e.g. `/api/ml/pnl-trades` has no backend route.
- **Backend unit conventions (the frontend must match these):**
  - `win_rate` is always a 0–100 percentage — `TradingStatsCalculator.cpp` and `ExecutionCohorts.cpp` multiply by 100 before serializing. Never multiply again in the frontend.
  - `max_drawdown` is in dollars, not percent.
  - Portfolio-level `total_fees` already includes per-trade fees: it must **replace** a per-trade fee sum, never be added to it.
  - Win rate counts winners/(winners+losers), excluding zero-PnL open legs.
  - Sharpe is per-trade (mean/std of trade PnL), not annualized.
- **`frontend/lib/simulatedTradingStats.ts`** is the canonical stats layer: `deriveStats` computes stats from raw trades, `mergeStats` overlays backend-provided values, `normalizeSimulatedTradingSnapshot` normalizes the several snapshot shapes the backend can return. New stat calculations belong here (with tests in the adjacent `.test.ts`), not inline in components.
- Frontend data flow: `hooks/` (React Query wrappers like `useTradingData`, `useMLAnalytics`, `useWebSocket`) → `components/dashboard/` panels. `lib/api.ts` holds the API client.
- Numeric fallbacks in the frontend use `??`, not `||`, so legitimate zeros aren't replaced.
- `frontend/components/ui/DataTable.tsx` never slices its data — pagination display is the caller's responsibility.

## Repo conventions

- `rules/` contains operational doctrine docs for coding agents (git hygiene, output organization, etc.); `rules/08-git.md` asks for a commit per change with brief messages.
- Working branch is `dev` (also the PR target).
