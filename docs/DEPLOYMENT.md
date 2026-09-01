# Deployment guide

## Stack

The supported deployment is the root `docker-compose.yml` stack:

| Service | Image/runtime | Container port | Default host port |
| --- | --- | ---: | ---: |
| `cpp-backend` | Published Drogon C++ image | 8080 | 8081 |
| `frontend` | Published Next.js image | 3000 | 3000 |
| `db` | PostgreSQL 15 | 5432 | 15432 |
| `redis` | Redis 7 | 6379 | 6379 |

There are no `backend`, `ml-server`, or `qdrant` services in the supported
stack. The C++ backend includes the ML inference and API surfaces.

## Prerequisites

- Podman Compose or Docker Compose
- A `.env` file based on `env.example`
- Coinbase credentials only when using Coinbase-backed live or paper data

Keep credentials out of Git and logs. The Compose file mounts `.env` read-only
into the backend container.

## Start the published development stack

```bash
podman-compose up --no-build
```

The default image variables resolve to:

```text
ghcr.io/chasekb/trade/cpp-backend:dev
```

Override them explicitly when testing another branch tag:

```bash
CPP_BACKEND_IMAGE=ghcr.io/chasekb/trade/cpp-backend:dev \
FRONTEND_IMAGE=ghcr.io/chasekb/trade/frontend:dev \
podman-compose up --no-build
```

Compose waits for PostgreSQL, Redis, and the backend/frontend health checks.
Verify the host-facing services with:

```bash
curl -fsS http://localhost:8081/health
curl -fsS http://localhost:3000/api/health
```

## Build local images

```bash
podman-compose build
podman-compose up --no-build
```

The C++ image uses `Dockerfile.cpp` and its vcpkg toolchain. Prefer the
push-triggered GitHub Actions Docker Build Validation workflow for final
multi-architecture proof.

## Host database port

Containers always reach PostgreSQL at `db:5432`. Change only the host binding
when another service occupies the default port:

```bash
POSTGRES_HOST_PORT=55432 podman-compose up --no-build
```

The default host binding is 15432, not 5432.

## C++ test container

```bash
podman-compose -f docker-compose.test.yml up --build cpp-test
```

That service configures CMake with the image's vcpkg toolchain and runs the
configured CTest target(s). The authoritative target list is in
`CMakeLists.txt`.

## Stop and inspect

```bash
podman-compose ps
podman-compose logs --tail=200 cpp-backend frontend
podman-compose down
```

Do not remove `data/databases` or `data/cache` as part of routine cleanup.