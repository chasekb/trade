# Storage, WAL, API, and worker correlation

Date: 2026-08-23
Scope: read-only runtime inspection; no service restart, workload change, live order, or source change was performed.

## Decision

The evidence supports **storage/writeback contention as a material contributor to database availability and request latency**, but it does not prove that checkpoint writeback alone caused every API reset or simulated-worker lifecycle transition.

The strongest direct failure boundary is a backend/service lifecycle event: after the 45.793-second checkpoint completed, the frontend recorded repeated `ECONNRESET`, the backend logged `Transport endpoint is not connected`, then received `SIGTERM`; subsequent frontend errors included `ECONNREFUSED` and `ENOTFOUND`. Separately, the database emitted a statement-timeout error and repeated SQL/schema incompatibility errors. These provide more direct explanations for the transport failures than checkpoint timing alone.

No remediation is recommended from this evidence alone. First repair/align the runtime image/schema and collect an isolated before/after run with request timing and database wait telemetry. Do not tune PostgreSQL durability settings speculatively.

## Timestamped correlation timeline

Times below preserve the runtime log's UTC timestamps.

- 04:08:45–04:10:22: Transformer pass-2 batches 510–563 progressed from offset 2,545,000 to 2,810,000. This confirms sustained training load during the observed period.
- 04:33:03–04:35:38: simulated session `sim_1787459583` started/stopped three times. The transitions were explicit worker lifecycle events, not database checkpoint messages.
- 04:35:35: checkpoint started; 04:35:52 completed with `total=16.728 s`, `write=12.904 s`, `sync=0.928 s`, 62 buffers.
- 05:03:33–05:04:54: normal and 64-symbol benchmark sessions started/stopped.
- 05:05:27: benchmark session `bench-normal-20260823` (3 symbols) started.
- 05:05:35: checkpoint started while the benchmark was active.
- 05:05:42: that benchmark session stopped, before checkpoint completion.
- 05:06:21: checkpoint completed after `45.793 s`: `write=36.152 s`, `sync=5.388 s`, 44 buffers, 17 files. This is the clearest writeback/storage-latency outlier.
- 05:06:21–05:07:30: frontend logged multiple proxy `ECONNRESET`/socket-hang-up failures for reconciliation, ML config, products, and models. The log does not include per-request start/end timestamps, so an exact request duration cannot be reconstructed.
- 05:07:41: PostgreSQL logged a statement timeout for an unbounded three-table `COUNT(*)` diagnostic query.
- 05:07:46–05:08:03: backend logged eight `Transport endpoint is not connected` shutdown-write failures around the transport failure burst.
- 05:07:47: another simulated benchmark worker started.
- 05:07:53: backend received `SIGTERM`.
- 05:08:04: simulated benchmark worker stopped; frontend then observed `ECONNREFUSED`, followed by `ENOTFOUND cpp-backend` and further connection refusals. This sequence is consistent with backend shutdown/recreation/network-DNS churn, not a checkpoint-only failure.
- 05:08:52 onward: repeated `pg_input_is_valid` errors occurred on the legacy runtime SQL. This is a PostgreSQL-version/query compatibility defect, independent of storage pressure.
- 05:10:35: a much smaller checkpoint still took `9.405 s` total (`write=3.843 s`, `sync=0.622 s`), showing elevated fixed checkpoint overhead but not the 45.793-second outlier.
- 05:15:35–05:15:57: checkpoint total was `22.243 s` (`write=9.988 s`, `sync=2.170 s`).
- 05:37:55–05:38:00: the database received a fast shutdown request and completed an immediate shutdown checkpoint in `4.837 s`; this confirms a later lifecycle shutdown distinct from ordinary checkpoint timing.

## Quantified evidence

### Checkpoint samples from the runtime log

| Start (UTC) | Total | Write | Sync | Buffers | Interpretation |
|---|---:|---:|---:|---:|---|
| 04:10:35 | 15.718 s | 7.231 s | 3.520 s | 10 | slow despite tiny buffer count |
| 04:35:35 | 16.728 s | 12.904 s | 0.928 s | 62 | write-heavy |
| 05:05:35 | **45.793 s** | **36.152 s** | **5.388 s** | 44 | outlier; writeback and sync dominated |
| 05:10:35 | 9.405 s | 3.843 s | 0.622 s | 8 | lower-load comparison |
| 05:15:35 | 22.243 s | 9.988 s | 2.170 s | 12 | still elevated |
| 07:26:16 | 28.615 s | 18.145 s | 7.592 s | 37 | later elevated sample |

The 45.793-second checkpoint spent 41.540 seconds (90.7%) in write plus sync. The 36.152-second write component alone is sufficient to make concurrent request latency and connection backlog plausible, but the log does not show a request waiting on a PostgreSQL backend during that exact interval.

### API timing probe after the runtime had recovered

Three read-only host probes were run against port 8081 after recovery:

- `/health`: 0.540–0.621 s total (approximately 0.56 ms average).
- `/api/products`: 0.402–0.456 s total (approximately 0.42 ms average).
- `/api/trading/execution-reconciliation?hours=24`: 17.115–18.309 ms total (approximately 17.7 ms average).
- `/api/ml/config`: 0.499–0.573 s total (approximately 0.53 ms average).

These are recovery-state samples, not before/after measurements around the 05:05 checkpoint. They cannot disprove a transient stall.

### Current storage and database state

- Host filesystem containing the trade worktree: ext4 `/dev/md127`, 7.3 TB total, 2.6 TB used, 4.4 TB available (37%). No capacity-pressure signal was observed.
- Container data directory usage: 45.7 MB; the container reports the same ext4 filesystem with ample free blocks. Host-side direct `du` was permission denied for the PostgreSQL directory, so the container measurement is authoritative for the mounted path.
- Current `pg_stat_bgwriter` snapshot: 5 timed checkpoints, 1 requested checkpoint, 41,104 ms cumulative checkpoint write time, 53,576 ms cumulative sync time; no clean buffers or maxwritten-clean events.
- Current `pg_stat_database` snapshot for `trading_db`: 419 commits, 38 rollbacks, 0 temp files, 0 temp bytes, 0 deadlocks, 0.016 ms cumulative block-read time, 0 block-write time.
- No active database waits were present at probe time.
- The running `trade_db_1` container mounts a PostgreSQL directory from a different worktree (`t_bee966e2`), not this task worktree. The current database has no `order_book_signals` relation and only empty/minimal `individual_trades` and `ml_training_inputs` tables. Therefore current query/table-size results are not a valid representation of the populated dataset that produced the historical checkpoint evidence.

## Causation classification

### Observed causation

- PostgreSQL checkpoint writeback was objectively slow: the 05:05 checkpoint took 45.793 seconds, with 36.152 seconds writing and 5.388 seconds syncing.
- Transport/service disruption objectively occurred near the checkpoint episode: frontend resets, backend shutdown-write failures, SIGTERM, then refusals/DNS failures.
- A statement timeout objectively occurred at 05:07:41.
- The backend was explicitly terminated/restarted during the broader failure window; worker stop/start events track that lifecycle.
- SQL compatibility/schema failures (`pg_input_is_valid`, missing `is_closing_leg`, missing `order_book_signals` in the current mounted database) are independently observed defects.

### Plausible contribution, not proven

- The checkpoint's 41.540 seconds of write+sync time could have increased I/O latency, delayed database-backed handlers, and contributed to proxy socket resets if request or shutdown deadlines were crossed.
- Transformer training load may have increased concurrent database/read or filesystem pressure; the logs establish temporal overlap, not resource attribution. Current transformer CPU was approximately 49.5% and memory 4.76 GB, but that is a post-event snapshot.
- Checkpoint sync contention may have amplified the statement-timeout risk, but the timed-out query was also an unbounded multi-table count and therefore has an independent query-shape explanation.

### Unrelated or separate coincidence

- `ECONNREFUSED`, `ENOTFOUND`, and the final `SIGTERM` are more directly explained by backend/container lifecycle and network-DNS changes than by ordinary checkpoint completion.
- `pg_input_is_valid` failures are a PostgreSQL/runtime SQL compatibility problem, not evidence of storage latency.
- Missing-column errors and the current empty schema indicate image/schema/worktree skew and invalidate current populated-table query comparisons.
- The host filesystem had substantial free capacity; capacity exhaustion is not supported.

## Exact acceptance measurements for any future repair

Keep this investigation open until an isolated, populated runtime can provide both before and after windows with:

1. At least 3 comparable checkpoints under the same Transformer workload, recording total/write/sync times, buffers, WAL distance, and checkpoint cadence.
2. At least 20 samples each of health, products, reconciliation, and the order-book baseline query during non-checkpoint and checkpoint windows, with client total time, HTTP status, timeout/reset/refusal counts, and backend request timestamps.
3. PostgreSQL `pg_stat_activity` wait-event snapshots and `pg_stat_bgwriter` deltas captured at the same boundaries; do not rely only on cumulative counters.
4. Query timing for the exact order-book query on the populated schema, with bounded statement and lock timeouts; avoid unbounded exact counts in the measurement path.
5. Transformer batch rate/CPU/I/O and simulated-worker start/stop timestamps in the same UTC timeline.
6. Zero live-order or accounting-semantic changes, no durability downgrade, and fail-closed behavior preserved.
7. Rollback as a configuration/image revert, with a second measurement window proving the revert restores the prior behavior.

Until those measurements exist, the safe conclusion is evidence collection only: investigate runtime/image/schema alignment and request/shutdown observability before changing checkpoint or concurrency settings.
