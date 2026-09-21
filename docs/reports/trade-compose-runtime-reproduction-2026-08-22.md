# Trade Compose Runtime Reproduction Evidence

Date: 2026-08-22 (CDT, UTC-05:00)
Backlog: TRADE-BL-0029
Kanban task: t_63f7a4c5

## Safety scope

- The existing trade backend reported `is_active=false` and `is_trading=false` before and after the cycle.
- No live start, order submission, account mutation, image pull, image build, Docker/Podman build, CMake build, or test command was run.
- The already-present local images were used by `podman-compose ... --no-build`.
- The separately owned `db-postgres` service and the existing `trade` project were not removed. The reproduction used the task worktree's implicit Compose project name, `t_63f7a4c5`, so its containers were isolated from the healthy `trade` project.

## Project identity finding

Running `podman-compose` from this worktree does not select the primary checkout's existing project name `trade`; podman-compose 1.6.0 derived `t_63f7a4c5` from the worktree directory. The created container labels recorded:

- `com.docker.compose.project=t_63f7a4c5`
- `io.podman.compose.project=t_63f7a4c5`
- `com.docker.compose.project.working_dir=/run/media/unordered_map/priority_queue/log(perplexity)/-sum/log/Pr(context_for_token)/chasecapitalmanagement/etl/trade/.worktrees/t_63f7a4c5`
- pod: `pod_t_63f7a4c5`

The pre-existing healthy project remained labelled `trade` and retained containers `trade_db_1`, `trade_redis_1`, `trade_cpp-backend_1`, and `trade_frontend_1` throughout.

## Reproduction

The exact command transcript, including timestamps and exit codes, is preserved in:

- `docs/reports/trade-compose-runtime-reproduction-2026-08-22.txt`

The cycle was:

1. `podman-compose down` from the task worktree. Because no `t_63f7a4c5` service containers existed, it printed missing-container messages for `cpp-backend`, `frontend`, `db`, `redis`, and the pod, while returning exit 0.
2. `POSTGRES_HOST_PORT=5432 timeout 45s podman-compose up --no-build`. The host port was already owned by the separately managed `db-postgres` container. Compose emitted image IDs, created the task project's pod and a database container, and did not reach a healthy service; the bounded command exited 124.
3. Immediately after the bounded start, the project filter showed the following exact service state:

   | Resource | ID/name | State |
   |---|---|---|
   | db | `2d8308015cbb` / `t_63f7a4c5_db_1` | `Created` |
   | cpp-backend | `t_63f7a4c5_cpp-backend_1` | absent |
   | frontend | `t_63f7a4c5_frontend_1` | absent |
   | redis | `t_63f7a4c5_redis_1` | absent |
   | pod | `e31d8a2c0229` / `pod_t_63f7a4c5` | `Created` |

   The database container labels and worktree path are recorded by `podman inspect` in the task evidence and establish ownership. No unrelated project label was present on this residual.
4. `POSTGRES_HOST_PORT=5432 podman-compose down` printed missing-container messages for the absent service names, removed `t_63f7a4c5_db_1`, and removed `pod_t_63f7a4c5`; it returned exit 0.

The prior checked-in triage report (`docs/reports/trade-compose-runtime-triage-2026-08-21.md`) preserves the corresponding direct rootless-port error from the same failure class: `rootlessport listen tcp 0.0.0.0:5432: bind: address already in use`.

## Recovery and final state

The exact cleanup and final-state commands are preserved in:

- `docs/reports/trade-compose-runtime-recovery-2026-08-22.txt`

A second project-scoped `podman-compose down` at 23:12:54 printed the same absent-service/pod messages and returned exit 0. The subsequent project filter returned no `t_63f7a4c5` containers, and `podman pod ps` showed no `pod_t_63f7a4c5`. The existing `trade` pod remained running. Health checks after cleanup returned:

- `GET http://127.0.0.1:8081/health`: healthy, HTTP request exit 0.
- `GET http://127.0.0.1:8081/api/trading/live/status`: stopped live session (`is_active=false`, `is_trading=false`), with no pending orders.

The attempted task-project `POSTGRES_HOST_PORT=5433 podman-compose up -d --no-build` did not produce a bounded completion in the first transcript, so this evidence does not claim a successful fresh task-project recreation. The already-running primary `trade` project was intentionally left untouched rather than risking a collision with another owner's containers.

## Classification

- `Created` database container and `Created` pod: deterministic consequence of podman-compose creating resources before the port-dependent start completes; not evidence of an unrelated cleanup leak.
- Missing `cpp-backend`, `frontend`, `redis`, and pod/service messages during `down`: stale expected-name reporting after partial creation/removal. They are harmless here: the command returned 0, the residual database and pod were removed, and the project filter was empty afterward.
- Unrelated `db-postgres`: outside project `t_63f7a4c5`; it was preserved.

No repository cleanup code change is warranted by this reproduction. The smallest safe operational path is project-scoped `podman-compose down` followed by recreation with the repaired non-conflicting host mapping (`POSTGRES_HOST_PORT=5433` by default), and explicit project selection when operating from a worktree.
