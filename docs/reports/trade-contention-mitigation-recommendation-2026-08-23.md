# Trade contention mitigation recommendation

Date: 2026-08-23
Task: `t_4b15449a`
Scope: read-only review of Compose, PostgreSQL access, worker lifecycle, and live-trading safeguards against the captured `tmux` pane `0:7.0` evidence.

## Decision

Do not change PostgreSQL checkpoint/WAL settings, storage mounts, connection handling, or trading worker lifecycle based on the current evidence. The observed failures have a stronger, already-addressed application cause: the running `dev` image issued PostgreSQL 15-incompatible `pg_input_is_valid(...)` queries, followed by failed API requests and a backend `SIGTERM`. The current source no longer contains that function or the legacy JSON casts, so the smallest safe repair is to deploy and verify the image containing the existing source fix—not to add speculative database tuning.

The checkpoint timings justify a storage/IO investigation, not an immediate configuration change. Changing `synchronous_commit`, checkpoint completion behavior, WAL durability, or the PostgreSQL data mount could conceal latency while weakening durability or changing operational semantics.

## Evidence and causal interpretation

The captured pane showed these checkpoint samples:

| UTC checkpoint completion | write | sync | total | buffers |
| --- | ---: | ---: | ---: | ---: |
| 03:46:03 | 5.152 s | 18.941 s | 29.707 s | 9 |
| 03:50:55 | 1.911 s | 16.113 s | 22.711 s | 1 |
| 03:55:50 | 2.534 s | 8.773 s | 16.693 s | 2 |
| 04:00:54 | 3.491 s | 12.738 s | 20.093 s | 3 |
| 04:05:52 | 2.639 s | 10.498 s | 17.217 s | 1 |
| 04:10:51 | 7.231 s | 3.520 s | 15.718 s | 10 |
| 04:35:52 | 12.904 s | 0.928 s | 16.728 s | 62 |
| 05:06:21 | 36.152 s | 5.388 s | 45.793 s | 44 |
| 05:10:45 | 3.843 s | 0.622 s | 9.405 s | 8 |
| 05:15:57 | 9.988 s | 2.170 s | 22.243 s | 12 |

The 05:06:21 outlier is real and should be retained as a storage-performance incident. However, the same capture contains repeated `pg_input_is_valid(text, unknown) does not exist` errors, `Database parameterized query failed` messages, and frontend `ECONNRESET`/socket-hang-up messages. At 05:07:53 the backend received `SIGTERM`; subsequent frontend errors include `ECONNREFUSED` and `ENOTFOUND cpp-backend`. This is consistent with service shutdown/restart and stale-image query failures, not proof that checkpoint writeback caused the transport failures or worker lifecycle transitions.

The capture also includes a statement timeout during a diagnostic count query at 05:07:41. It does not identify the application query or show that the timeout was caused by a checkpoint lock. No `pg_stat_activity`, wait-event, `EXPLAIN (ANALYZE, BUFFERS)`, WAL-volume, filesystem-latency, or container storage benchmark evidence was captured, so contention causality is unproven.

## Reviewed locations

- `docker-compose.yml:74-95`: PostgreSQL 15 Alpine, bind-mounted data directory `./data/databases/postgres:/var/lib/postgresql/data`, no custom checkpoint/WAL/shared-buffer settings, and a 30-second/10-second/3-retry healthcheck. The host port is configurable (`${POSTGRES_HOST_PORT:-5433}:5432`); container clients still use `db:5432`.
- `docker-compose.yml:4-43`: backend depends on healthy PostgreSQL and Redis, has a 60-second startup health period, and restarts unless stopped. Nothing here changes database durability or introduces an application request timeout.
- `src/db/DatabaseManager.cpp:10-74`: each operation opens a short-lived `pqxx::connection`, executes one transaction, commits, and converts exceptions to an empty result. This is inefficient under high request volume, but the capture does not establish connection exhaustion or connection contention. Replacing it with pooling or adding retries would be a broader behavior change and could duplicate writes unless designed carefully.
- `src/trading/SimulatedTradingService.cpp:2142-2305` and `src/trading/LiveTradingService.cpp:2767-2954`: lifecycle operations serialize with `lifecycle_mutex_`, reject a new start while the prior worker is settling, and expose `settling` rather than tearing down pending work. Stop marks the session inactive and requests worker shutdown. These are deliberate safety guards; no lifecycle change is justified by the transport evidence.
- `src/trading/SimulatedTradingService.cpp:575-599` and live start handling at `src/trading/LiveTradingService.cpp:2851-2911`: simulated live-parity gates remain fail-closed, and live mode requires explicit order execution confirmation, account initialization, pending-order recovery, and rejects synthetic capital parameters. These must remain unchanged.
- `src/trading/SimulatedTradingService.cpp:2513-2524` and `src/trading/LiveTradingService.cpp:3400-3411`: current source orders persisted signal rows without SQL JSON casts and parses payloads after retrieval. `pg_input_is_valid` is absent from the current worktree, confirming the runtime error came from an older image/source than this branch.

## Smallest reversible action

1. Push/deploy the existing application fix that removed `pg_input_is_valid` and unsupported PostgreSQL JSON casts.
2. Recreate the backend image/container from that exact commit; do not alter PostgreSQL durability or fail-closed trading settings.
3. Verify the running image identity before interpreting further runtime behavior.

This is operational deployment of an existing fix, not a new Compose/PostgreSQL mitigation. If the issue persists on the exact current image, open a separate investigation rather than adding a timeout/retry or database tuning workaround.

## Required evidence before any database/storage repair

Collect a matched before/after window while training and the same order-book/reconciliation workload run:

- `pg_stat_activity` query text, state, wait event, duration, and connection counts;
- `pg_stat_database` transaction/WAL-related counters and checkpoint statistics from `pg_stat_bgwriter`/`pg_stat_checkpointer` as supported by the installed PostgreSQL version;
- `EXPLAIN (ANALYZE, BUFFERS)` for the exact slow order-book and reconciliation queries, with row counts and indexes;
- checkpoint `write`, `sync`, `total`, buffers, and WAL volume over multiple checkpoint cycles;
- data-directory filesystem latency/throughput and mount/volume type, collected without changing the mount;
- API latency, HTTP status, connection-reset counts, backend restart/SIGTERM times, and worker `start/stop/settling` transitions correlated on one UTC timeline;
- confirmation that no live order was submitted and that fail-closed blockers/accounting outputs are unchanged.

A repair would be justified only if the same exact-image application query remains slow or times out while database wait/IO evidence establishes checkpoint/storage contention as the limiting factor. Any proposed setting must include a reversible change, an explicit durability rationale, and before/after checkpoint plus API measurements. Rollback is removal/reversion of that single setting or mount change, followed by the same verification window.

## Risks and limitations

- The current report uses captured logs and static source inspection; it does not prove current container image provenance or current database state.
- Checkpoint sync times up to 18.941 seconds and one 45.793-second total checkpoint indicate possible storage latency, but low buffer counts and missing wait/IO data prevent attribution to application query stalls.
- The stale-image incompatibility is a confirmed direct failure mode in the capture, while the source-level fix is confirmed only by absence of the old function/casts in this worktree. Exact-SHA remote CI and runtime image verification remain the deployment gate.
- No changes were made to trading, accounting, PostgreSQL, Compose, or connection behavior in this task.
