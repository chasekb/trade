# Trade Compose Runtime Triage

Report date: 2026-08-21 (report filename and original incident date)
Fresh validation date: 2026-08-23 00:52 CDT
Scope: the `trade` Compose project, including the induced host-port collision,
recovery, ownership checks, and repository-only checks. Runtime evidence was
captured without image pulls or builds.

## Executive result

The original failure was a host-port collision: the trade database attempted
to bind `0.0.0.0:5432`, which was already owned by the unrelated
`db-postgres` container. The checked-in minimal repair is the database mapping
`${POSTGRES_HOST_PORT:-5433}:5432`; the backend still reaches PostgreSQL
internally as `db:5432`. A fresh reproduction with `POSTGRES_HOST_PORT=5432`
returned exit 125 and reproduced the stale orchestration/runtime messages.
Recovery with the default 5433 mapping returned all four trade services to
healthy state and left zero trade containers in `Created` state.

The separately observed `pg_input_is_valid(...) does not exist` errors and
frontend proxy resets are application/PostgreSQL compatibility workload
anomalies after startup. They are not evidence that Compose recovery failed
and are intentionally not folded into the port-collision repair.

## Reproduction and recovery commands

Run from the repository root. Both commands explicitly prohibit image builds
and pulls:

```sh
env POSTGRES_HOST_PORT=5432 podman-compose --env-file ./.env -p trade up \
  --no-build --pull=never --abort-on-container-failure
# exit 125

podman-compose --env-file ./.env -p trade up --no-build --pull=never -d
# exit 0
```

The first command produced these relevant messages:

```text
Error: no container with name or ID "trade_frontend_1" found: no such container
[redis] cannot open .../crun/.../exec.fifo: No such file or directory
[db] ... rootlessport listen tcp 0.0.0.0:5432: bind: address already in use
```

## Classification and ownership mapping

| Message/state | Classification | Owner and disposition |
| --- | --- | --- |
| `trade_frontend_1` not found | Stale/missing Compose orchestration reference during the failed start; not an unrelated project container | `trade` Compose project; recreated by recovery as `fa480bc0d3ea` |
| Redis `crun/.../exec.fifo` missing | Stale rootless runtime state for the pre-existing trade Redis container; not a missing image | `trade` Compose project; recovery retained Redis `80da1c0a8adb` and it became healthy |
| `0.0.0.0:5432 ... address already in use` | Expected induced collision, not an application defect in the internal `db:5432` contract | Unrelated `db-postgres` owns host 5432; trade uses host 5433 by default |
| Failed-start `Created` containers | Intermediate failed-start state, not an orphan after recovery | `trade` Compose project; replaced/reconciled by the recovery command |

During the failed start, the preserved state was Redis `80da1c0a8adb`
(running/healthy), `trade_db_1` `1be6b68f9a7d` (Created),
`trade_cpp-backend_1` `8945c0afe27a` (Created), and `trade_frontend_1`
`a4023469bbcb` (Created). Recovery preserved Redis and created/reconciled:

| Service | Container ID | Final state and mapping |
| --- | --- | --- |
| `db` | `888ec23d399a` | running/healthy; `5433:5432` |
| `redis` | `80da1c0a8adb` | running/healthy; `6379:6379` |
| `cpp-backend` | `a626182768d7` | running/healthy; `8081:8080` |
| `frontend` | `fa480bc0d3ea` | running/healthy; `3000:3000` |

## Runtime health and cleanup evidence

- `podman exec trade_db_1 pg_isready` reported
  `/var/run/postgresql:5432 - accepting connections`.
- Database logs reached `database system is ready to accept connections`;
  Redis reached `Ready to accept connections`; the backend reported
  `Server listening on port 8080`; and the frontend reported `Ready`.
- `GET http://127.0.0.1:8081/health` returned
  `{"service":"trading-bot-cpp-backend","status":"healthy","version":"0.1.0"}`.
- `GET http://127.0.0.1:3000/api/health` returned the same healthy JSON.
- `GET /api/trading/live/status` returned HTTP 200 with the stopped live-session
  snapshot.
- `podman ps -a --filter label=com.docker.compose.project=trade` showed exactly
  the four final trade services above and no trade container in `Created` state.
- The only host `Created` container remaining was the intentionally retained,
  unlabeled historical evidence container `trade-port-collision-evidence-20260822`
  (`718a3a55e04f`, `postgres:15-alpine`). It is not owned by the `trade`
  Compose project and was retained as port-collision evidence; it was not
  treated as an orphaned trade container.

The unrelated `db-postgres` mapping remained `5432:5432`, while
`podman port trade_db_1` reported `5432/tcp -> 0.0.0.0:5433`. Before/after
snapshots showed these unrelated containers and IDs unchanged:

```text
cohida-db-prod d818ffea8246
db-postgres 9ab627e64ce7
db-metabase ea77e0e5d4ae
transform_transform_app_tmp51602 afa3bdd128c
arhida-qdrant 140005a14eca
arhida-embeddings 8f3d04e543fd
arhida-cpp_app_tmp38031 bf2290be1bf4
```

## Minimal repair / no-change rationale

No additional repository repair is warranted by this cycle. The existing
`${POSTGRES_HOST_PORT:-5433}:5432` mapping is the smallest safe change: it
resolves coexistence with the unrelated host PostgreSQL service without
changing the container-network contract or requiring a blacklist, service
removal, or destructive cleanup. The stale frontend reference and Redis
runtime message were reconciled by the no-pull recovery and did not justify a
source change. The compatibility anomaly requires separate application/
database investigation rather than being silently attributed to Compose.

## Repository evidence (separate from runtime evidence)

All checks below were read-only and ran without local image builds, image
pulls, CMake builds, CTest, or C++ test execution:

```text
podman-compose -f docker-compose.yml config       exit 0
  rendered config: 2,645 bytes; stderr empty
podman-compose -f docker-compose.test.yml config  exit 0
  rendered config: 580 bytes; stderr empty
git diff --check                                exit 0
git status --porcelain=v1 plus staged/unstaged diff names
  empty before this report change
```

The focused C++ path identified in `docker-compose.test.yml` configures and
builds `test_feature_engineer` before running it. It was intentionally not run
because the task requires remote-only build/test verification. There were no
repository changes in the prerequisite evidence collection, so no exact-SHA
GitHub Actions run applied to that unchanged worktree. Remote CI remains the
build gate for source changes.

## Reproducibility and evidence boundaries

The runtime evidence came from the fresh no-pull failed-start/recovery cycle
and preserved container IDs/output recorded by the prerequisite runtime task.
The repository evidence came from the separate repository-check task. These
are deliberately separated so a healthy runtime does not get presented as a
passing C++ test, and a passing Compose config check does not get presented as
proof of application workload compatibility.

## Remote CI closeout

This report is carried on the dependent closeout branch. The prerequisite
report commit was pushed as `0346757f86cbc41232cb7a74bb82f736cbc5bf99` and its
exact pull-request validation run completed successfully:

```text
Workflow: Docker Build Validation
Run: 32621600528
URL: https://github.com/chasekb/trade/actions/runs/32621600528
Head SHA: 0346757f86cbc41232cb7a74bb82f736cbc5bf99
Conclusion: success
Build C++ Backend (amd64): success
  https://github.com/chasekb/trade/actions/runs/32621600528/job/97150452653
Build Frontend (amd64): success
  https://github.com/chasekb/trade/actions/runs/32621600528/job/97150452683
Publish Frontend manifest: skipped (pull-request gate)
Publish C++ Backend manifest: skipped (pull-request gate)
```

The two publication jobs are intentionally skipped by the pull-request
workflow condition; no image publication was requested or performed. No
local C++ build, CTest run, or image build was used as a substitute for the
remote CI gate.
