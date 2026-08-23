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

## TRADE-BL-0028 closeout evidence inventory

Evidence inventory date: 2026-08-23. This section records the authoritative
closeout facts without treating queued, cancelled, or historical CI as fresh
validation.

### Repository and Docker Build Validation identity

- Repository: [`chasekb/trade`](https://github.com/chasekb/trade).
- Exact `origin/dev` SHA at this evidence capture:
  `141de1cf3495344fdd9f48a6cf6cc9914795aef5`.
- Authoritative push-triggered Docker Build Validation run for this head:
  [run 32626984237](https://github.com/chasekb/trade/actions/runs/32626984237),
  head SHA `141de1cf3495344fdd9f48a6cf6cc9914795aef5`, remains `pending` with
  no jobs materialized. No completion or success is claimed here.
- The matching pull-request run,
  [run 32626986421](https://github.com/chasekb/trade/actions/runs/32626986421),
  has the same head SHA but is not the authoritative closeout run because pull
  requests intentionally run only the amd64 build jobs and do not publish
  manifests. It is queued and is not used as closeout evidence.

The preceding push run,
[run 32626749456](https://github.com/chasekb/trade/actions/runs/32626749456),
for head SHA `cbc2c23bff0e375098cd8309a0fd5da18d94aa22`, completed `cancelled`
before any jobs materialized and is retained only as superseded CI history.

The prior green run,
[run 32598290563](https://github.com/chasekb/trade/actions/runs/32598290563),
was successful for head SHA `8af7838c9112e4f88c0f358504877d054ce9eb0c`, not
the current `origin/dev` SHA. Its required jobs all completed successfully,
but are historical evidence only:

- `Build Frontend (amd64)`
- `Build C++ Backend (amd64)`
- `Build C++ Backend (arm64)`
- `Build Frontend (arm64)`
- `Publish Frontend manifest`
- `Publish C++ Backend manifest`

For the authoritative push run `32626984237`, the required job status snapshot
was:

- `Build Frontend (amd64)`: pending/not materialized.
- `Build C++ Backend (amd64)`: pending/not materialized.
- `Build C++ Backend (arm64)`: pending/not materialized.
- `Build Frontend (arm64)`: pending/not materialized.
- `Publish Frontend manifest`: pending/not materialized.
- `Publish C++ Backend manifest`: pending/not materialized.

The prior green run,
[run 32598290563](https://github.com/chasekb/trade/actions/runs/32598290563),
remains historical evidence only: all six jobs above succeeded there for
head SHA `8af7838c9112e4f88c0f358504877d054ce9eb0c`, not this report's SHA.
Therefore, a fresh successful Docker Build Validation run for
`141de1cf3495344fdd9f48a6cf6cc9914795aef5` remains the CI closeout gate.

### Fresh recreation and smoke evidence

The post-repair recreation was healthy and retained the database-backed
runtime contract:

- `trade_db_1`: healthy, `0.0.0.0:5433->5432/tcp`.
- `trade_redis_1`: healthy, `0.0.0.0:6379->6379/tcp`.
- `trade_cpp-backend_1`: healthy, `0.0.0.0:8081->8080/tcp`.
- `trade_frontend_1`: healthy, `0.0.0.0:3000->3000/tcp`.
- `GET http://127.0.0.1:8081/health` returned
  `{"service":"trading-bot-cpp-backend","status":"healthy","version":"0.1.0"}`.
- `GET http://127.0.0.1:8081/api/trading/live/status` returned HTTP 200 with
  a database-backed stopped-session snapshot.
- `GET http://127.0.0.1:3000/api/health` returned the same healthy backend
  JSON response.

The durable runtime source artifact is this report's
[runtime verification section](#runtime-verification-after-repair). The
compose repair preserved the internal PostgreSQL endpoint `db:5432` while
moving the host mapping to `5433`.

### Host-port collision and outstanding cleanup

The unrelated `db-postgres` container (`9ab627e64ce7`) owned host
`0.0.0.0:5432` through `rootlessport` PID `2669789`; the trade stack used
`0.0.0.0:5433->5432/tcp`. This is the captured collision evidence and is
separate from the successful recreated stack.

The stale evidence container `trade-port-collision-evidence-20260822`
(`718a3a55e04f`, status `Created`) had not been removed at inventory time.
Its cleanup is a separate outstanding issue and is not represented as a
runtime or CI acceptance failure.

### Explicit validation boundary

No local Docker/Podman image builds, CMake builds, or C++ tests were run.
Fresh runtime smoke evidence and the historical green run above must not be
combined into a claim that the current SHA passed CI. Closeout requires the
fresh exact-SHA Docker Build Validation run to complete successfully.