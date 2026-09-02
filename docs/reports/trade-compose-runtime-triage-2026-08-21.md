# Trade Compose Runtime Triage

Date: 2026-08-21
Scope: `TAG=dev podman-compose up --no-build` in tmux pane `0:7.0`.

## Captured evidence

The pane was captured with `tmux capture-pane -t 0:7.0 -p -S -3000`, anchored
on the last visible `TAG=dev podman-compose up --no-build` command. The live
failure repeated:

```text
[db] | Error: unable to start container ...: rootlessport listen tcp 0.0.0.0:5432: bind: address already in use
```

The Redis warning about `vm.overcommit_memory` was non-fatal; Redis reached
`Ready to accept connections`. The failed compose attempt also left
`trade_db_1`, `trade_cpp-backend_1`, and `trade_frontend_1` in `Created` state,
while an existing `db-postgres` container owned host port `5432`.

## Root cause and repair

The root compose file hard-coded the database host mapping as `5432:5432`.
That host-side binding conflicts with a separately running PostgreSQL service,
even though the trade backend correctly reaches the database internally at
`db:5432`. The mapping is now `${POSTGRES_HOST_PORT:-5433}:5432`, preserving
the container contract while making host coexistence the safe default.

No local Docker, Podman image build, CMake build, or C++ test was run. Remote
GitHub Actions Docker Build Validation is the build gate.

## Runtime verification after repair

The stack was freshly recreated from the pushed `dev` images after the
PostgreSQL mapping repair. The new pane capture showed:

- `trade_db_1` healthy with `0.0.0.0:5433->5432/tcp`.
- `trade_redis_1` healthy with `0.0.0.0:6379->6379/tcp`.
- `trade_cpp-backend_1` healthy with `0.0.0.0:8081->8080/tcp`.
- `trade_frontend_1` healthy with `0.0.0.0:3000->3000/tcp`.
- PostgreSQL accepted connections and the backend connected successfully to
  both PostgreSQL and Redis.
- The backend reported `Server listening on port 8080`; Next.js reported
  `Ready`.
- No new `5432` bind error occurred. The unrelated `db-postgres` container
  continued to own host port `5432` while trade PostgreSQL used `5433`.
- No trade containers remained in `Created` state after successful recovery.

Smoke checks passed:

```text
GET http://127.0.0.1:8081/health
{"service":"trading-bot-cpp-backend","status":"healthy","version":"0.1.0"}

GET http://127.0.0.1:8081/api/trading/live/status
HTTP 200 with a database-backed stopped-session snapshot

GET http://127.0.0.1:3000/api/health
{"service":"trading-bot-cpp-backend","status":"healthy","version":"0.1.0"}
```

Local Docker/Podman image builds, CMake builds, and C++ tests were not run.
Remote Docker Build Validation was the build gate.