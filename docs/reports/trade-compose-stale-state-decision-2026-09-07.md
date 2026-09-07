# Trade Compose stale-state decision

Date: 2026-09-07 (CDT, UTC-05:00)
Backlog: TRADE-BL-0029
Kanban task: t_a5c2e0ed

## Decision

No repository cleanup change is warranted. The controlled reproduction classifies every observed missing-container message as harmless stale-state reporting, not evidence of a cleanup leak. The smallest safe repair is operational: use the repaired database host mapping (`POSTGRES_HOST_PORT=5433` by default), keep Compose operations project-scoped, and make the project identity explicit when running from a worktree. Do not add a broad restart, host-wide prune, or unrelated-container removal.

## Evidence and ownership reconciliation

The runtime evidence was produced at exact commit `79c59ce74ff99b7a10b7d1f20fbf71a64d05146c` (Kanban task `t_63f7a4c5`; GitHub Actions run `32617383789`, terminal success for the required amd64 backend/frontend jobs). The static ownership trace is the completed handoff from `t_0939b863`.

- The reproduction worktree derived the implicit Compose project `t_63f7a4c5`, not the primary checkout's `trade` project. Created resources carried both `com.docker.compose.project=t_63f7a4c5` and `io.podman.compose.project=t_63f7a4c5`; the pod was `pod_t_63f7a4c5`.
- The existing `trade` project remained separately labelled `trade` and retained its healthy `trade_db_1`, `trade_redis_1`, `trade_cpp-backend_1`, and `trade_frontend_1` containers. The separately managed `db-postgres` container owning host port 5432 was outside the reproduction project and was preserved.
- The failed `POSTGRES_HOST_PORT=5432 podman-compose up --no-build` path created the database container `2d8308015cbb` (`t_63f7a4c5_db_1`) and pod `e31d8a2c0229` (`pod_t_63f7a4c5`) in `Created` state before the port-dependent start could succeed. `cpp-backend`, `frontend`, and `redis` were absent because their startup is dependency-gated on database/redis health.
- Compose `down` owns cleanup for the implicit same-project containers and pod. It removed the residual database and pod, returned exit 0, and the subsequent project filter contained no `t_63f7a4c5` containers. The unrelated `trade` project and `db-postgres` remained intact.

## Classification of each missing-container message

| Message target | Observed state | Classification | Reason |
|---|---|---|---|
| `t_63f7a4c5_cpp-backend_1` | absent after failed dependency/start path | harmless stale-state report | Backend was not created/started before the database bind failure; `down` reported the expected service name while iterating the Compose model. |
| `t_63f7a4c5_frontend_1` | absent after failed dependency/start path | harmless stale-state report | Frontend start is gated on healthy `cpp-backend`; no owned container remained to remove. |
| `t_63f7a4c5_redis_1` | absent in the captured failed-start state | harmless stale-state report | No residual Redis container was present in the project filter; the message does not identify a surviving resource. |
| `t_63f7a4c5_db_1` | present during failed cleanup, then removed | not a leak | The database container was a project-owned `Created` residual caused by non-transactional create-before-start behavior. Cleanup removed its exact ID. |
| `pod_t_63f7a4c5` | present during failed cleanup, then removed | not a leak | The pod was the project-owned residual from the same partial create path. Cleanup removed it, and `podman pod ps` showed no task pod afterward. |
| `t_63f7a4c5_*` during the subsequent recovery `down` | no project containers remained | harmless stale-state report | A later project-scoped cleanup encountered expected service names with no matching resources and returned exit 0. |

A missing-name line becomes evidence of a cleanup leak only if a readback after the cleanup still finds a container or pod carrying the same project label/identity, or if the cleanup removes a resource belonging to another project. Neither condition occurred.

## Why no source change is justified

The missing-name output is not emitted by a repository shutdown wrapper; the static trace found no such wrapper or cleanup implementation. The behavior belongs to podman-compose's project-scoped cleanup iteration after a partial create/start failure. Changing service definitions, adding broad teardown logic, or restarting the host would not fix that reporting behavior and could remove unrelated resources. The existing Compose ownership, health-gated dependency ordering, and configurable `POSTGRES_HOST_PORT` are the relevant contracts.

If an operational runbook is updated later, it should document the explicit project boundary and readback checks; it must not prescribe host-wide cleanup. No code or Compose file is changed by this task.

## Acceptance checks for a fresh same-project failed-start/recovery cycle

Run only as an approved, bounded runtime probe; do not touch the existing healthy `trade` project or `db-postgres` unless it is the explicitly selected test project.

1. Establish baseline: record the selected project name, Compose file, worktree, and protected unrelated resources. Confirm the test project has no containers/pod before fault injection.
2. Use one explicit project identity for the entire cycle (for example `-p <test-project>`), and verify `com.docker.compose.project` and `io.podman.compose.project` labels before cleanup.
3. Inject only the known host-port collision (`POSTGRES_HOST_PORT=5432`) with `--no-build` and a bounded timeout. Record the command exit code and exact container/pod IDs.
4. After failure, filter by the selected project label and reconcile every expected service name to an exact ID or absence. Confirm any `Created` residual belongs to the selected project.
5. Run project-scoped `down` for that same identity. Missing expected names may be reported, but cleanup must return 0 and remove every selected-project container and pod.
6. Read back both project-label filters and pod listing: zero selected-project containers and zero selected-project pod. Confirm the unrelated `db-postgres` and existing `trade` project are unchanged.
7. Recreate the same project with the repaired non-conflicting mapping (`POSTGRES_HOST_PORT=5433` or another explicitly free port), bounded to the selected project. Verify db and redis health before dependent services, then verify all four trade services are healthy.
8. Run a final project-scoped `down` and repeat the zero-resource and protected-resource readback. Treat any surviving selected-project ID, cross-project deletion, nonzero cleanup exit, or failure to reach healthy recovery as a regression requiring investigation.

## Limitations

The reproduction evidence establishes the failed-start cleanup classification and protected-resource behavior. It does not by itself prove a fresh successful recreation from the task worktree; that is intentionally an acceptance check rather than a claim made by this decision report. No local build or test command was run.
