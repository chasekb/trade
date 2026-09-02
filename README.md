# Trade

Trade is a containerized trading system with a Drogon C++ backend and a
Next.js/React dashboard. The backend owns all `/api/*` routes, live and
simulated execution, ML inference, and PostgreSQL/Redis integration.

## Repository layout

```text
trade/
├── src/                    # C++ backend implementation
├── include/                # C++ headers and API contracts
├── frontend/               # Next.js 16 / React 19 dashboard
├── data/                   # Runtime and model assets (some subtrees tracked)
├── docs/                   # Current contracts, architecture, and operations docs
├── CMakeLists.txt          # Backend and CTest targets
├── Dockerfile.cpp         # C++ backend image
├── docker-compose.yml      # Published-image development/runtime stack
└── docker-compose.test.yml # Containerized C++ test entry point
```

The former Python/FastAPI application is archived history, not a runtime
dependency. Do not use the old `app.py`, `src/trade_bot/`, port 8000, ML-server,
or Qdrant instructions as current setup instructions.

## Runtime services

`docker-compose.yml` runs:

- `cpp-backend`: Drogon HTTP server, container port 8080, host port 8081
- `frontend`: Next.js dashboard on host port 3000
- `db`: PostgreSQL 15, container port 5432, host port 15432 by default
- `redis`: Redis 7 on port 6379

The frontend uses same-origin browser requests and Next.js rewrites them to the
backend. Containers use `cpp-backend:8080` and `db:5432`; host-side clients use
the published ports. Backend and frontend health checks gate startup.

## Quick start

Prerequisites: Podman or Docker Compose, and a repository `.env` containing the
database settings and any required Coinbase credentials. Never commit `.env`.

```bash
cp env.example .env
podman-compose up --no-build
```

The default Compose images are the `dev` images published to GHCR. To use
locally built images, build them first and then run with `--no-build`:

```bash
podman-compose build
podman-compose up --no-build
```

For another host PostgreSQL port, set `POSTGRES_HOST_PORT`; the internal
database address remains `db:5432`:

```bash
POSTGRES_HOST_PORT=55432 podman-compose up --no-build
```

Open the dashboard at http://localhost:3000. The backend health endpoint is
http://localhost:8081/health.

## Frontend development

```bash
cd frontend
npm install
npm test
npx tsc --noEmit
npm run lint
npm run dev
```

The canonical simulated-statistics normalization is in
`frontend/lib/simulatedTradingStats.ts`; keep new calculations there and add
tests beside it.

## C++ tests

The C++ dependencies are provided by the container toolchain. Run the test
stack with:

```bash
podman-compose -f docker-compose.test.yml up --build cpp-test
```

The complete list of backend test targets is defined in `CMakeLists.txt`.

## CI and image promotion

`.github/workflows/docker-build.yml` is the Docker Build Validation workflow.
Pushes to `dev` and `main` build the C++ and frontend images for the configured
architectures and publish branch-tagged GHCR images. A promotion from `dev` to
`main` must use the exact candidate head SHA, wait for that SHA's required jobs
to pass, and then merge. Do not use an older successful run as proof.

See:

- [Architecture](docs/ARCHITECTURE.md)
- [Deployment](docs/DEPLOYMENT.md)
- [API reference](docs/API_REFERENCE.md)
- [Strategy objective](docs/STRATEGY_OBJECTIVE.md)
- [Strategy diagnostics contract](docs/STRATEGY_DIAGNOSTICS_CONTRACT.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

Historical migration plans and archived reports remain under `docs/archive/`,
`docs/working/`, and `docs/reports/`; they are evidence, not current runtime
instructions.