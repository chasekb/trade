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

## Remaining runtime follow-up

- Recreate the stack after the pushed image/config change and capture a fresh
  pane window.
- Verify the database and backend healthchecks, then exercise `/health` and a
  database-backed API endpoint.
- Confirm stale `Created` containers are removed by the normal compose cleanup
  path; if cleanup still emits missing-container errors, trace that separately
  rather than conflating it with the port repair.