# PostgreSQL checkpoint and query-latency evidence

Collection timestamp (host): 2026-08-23T02:32:12-05:00

## Scope and safety

Read-only inspection of running `trade_db_1` PostgreSQL and tmux pane `0:7.0`. No configuration changes, DDL, DML, or database writes were issued.

## Live container

```text
name=trade_db_1 status=Up 29 minutes (healthy) image=docker.io/library/postgres:15-alpine ports=0.0.0.0:5433->5432/tcp
```

## Server identity and checkpoint settings (2026-08-23T02:32:13-05:00)

```text
SET
SET
         observed_at          |                                         version                                          
------------------------------+------------------------------------------------------------------------------------------
 2026-08-23 07:32:18.16126+00 | PostgreSQL 15.19 on x86_64-pc-linux-musl, compiled by gcc (Alpine 15.2.0) 15.2.0, 64-bit
(1 row)

             name             | setting | unit |       source       
------------------------------+---------+------+--------------------
 checkpoint_completion_target | 0.9     |      | default
 checkpoint_flush_after       | 32      | 8kB  | default
 checkpoint_timeout           | 300     | s    | default
 max_wal_size                 | 1024    | MB   | configuration file
 min_wal_size                 | 80      | MB   | configuration file
 shared_buffers               | 16384   | 8kB  | configuration file
 track_io_timing              | off     |      | default
 wal_buffers                  | 512     | 8kB  | default
(8 rows)

```

## Checkpoint/WAL cumulative statistics (2026-08-23T02:32:26-05:00)

```text
SET
SET
          observed_at          | checkpoints_timed | checkpoints_req | checkpoint_write_time | checkpoint_sync_time | buffers_checkpoint | buffers_clean | maxwritten_clean | buffers_backend | buffers_backend_fsync | buffers_alloc |         stats_reset          
-------------------------------+-------------------+-----------------+-----------------------+----------------------+--------------------+---------------+------------------+-----------------+-----------------------+---------------+------------------------------
 2026-08-23 07:32:33.549191+00 |                 5 |               1 |                 41104 |                53576 |                955 |             0 |                0 |             318 |                     0 |           944 | 2026-08-23 07:06:12.25322+00
(1 row)

          observed_at          | wal_records | wal_fpi | wal_bytes |         stats_reset          
-------------------------------+-------------+---------+-----------+------------------------------
 2026-08-23 07:32:33.549191+00 |         615 |      36 |    194433 | 2026-08-23 07:06:12.25322+00
(1 row)

```

## Active/waiting backend activity (2026-08-23T02:32:42-05:00)

```text
SET
SET
          observed_at          | active | waiting | total 
-------------------------------+--------+---------+-------
 2026-08-23 07:32:46.360794+00 |      1 |       0 |     1
(1 row)

 pid | usename | application_name | state | wait_event_type | wait_event | query_age | query 
-----+---------+------------------+-------+-----------------+------------+-----------+-------
(0 rows)

```

## Locks (2026-08-23T02:32:52-05:00)

```text
SET
SET
         observed_at          | waiting_locks | total_locks 
------------------------------+---------------+-------------
 2026-08-23 07:32:57.56811+00 |             0 |           1
(1 row)

 pid | application_name | state  | locktype |      mode       | granted |     relation     |    query_age    |                                                                                        query                                                                                         
-----+------------------+--------+----------+-----------------+---------+------------------+-----------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 360 | psql             | active | relation | AccessShareLock | t       | pg_locks         | 00:00:00.00512  | SET statement_timeout='5000ms'; SET lock_timeout='1000ms'; SELECT now() AS observed_at, count(*) FILTER (WHERE NOT granted) AS waiting_locks, count(*) AS total_locks FROM pg_locks 
 360 | psql             | active | relation | AccessShareLock | t       | pg_stat_activity | 00:00:00.005131 | SET statement_timeout='5000ms'; SET lock_timeout='1000ms'; SELECT now() AS observed_at, count(*) FILTER (WHERE NOT granted) AS waiting_locks, count(*) AS total_locks FROM pg_locks 
(2 rows)

```

## Slow order-book baseline timings

Bounded `EXPLAIN (ANALYZE, BUFFERS, TIMING)` read probes use `LIMIT 100` and a 5-second statement timeout. They are read-only and workload-sensitive, not a production benchmark.

### Probe 1 (2026-08-23T02:33:04-05:00)

```text
SET
SET
```

### Probe 2 (2026-08-23T02:33:14-05:00)

```text
SET
SET
```

The probes returned no plan because the current `trading_db` schema has no `order_book_signals` relation (`ERROR: relation "order_book_signals" does not exist`). This is an environment/schema-availability finding, not a zero-latency result. The live database exposes `public.individual_trades` and `public.ml_training_inputs`; both currently report zero estimated live rows.

### Available read-only query timings from related tmux evidence

Pane `0:4.0` (a separate PostgreSQL session/database, not the trade container) showed:

| Timestamp context | Query | Result |
|---|---|---|
| historical pane capture | `select * from main_1d order by timestamp::date desc limit 5` | canceled by user after 5.759 s |
| historical pane capture | `select distinct(timestamp::date) from main_1d order by timestamp::date desc limit 5` | 738.385 ms |
| historical pane capture | same distinct-date query, repeat | 630.452 ms |

Pane `0:7.0` also records an exact-count UNION over `individual_trades`, `order_book_signals`, and `live_coinbase_orders` canceled by PostgreSQL statement timeout at `2026-08-23 05:07:41.276 UTC`; this is a slow-query/timeout observation, but not a valid elapsed-time measurement because the timeout bound is not shown in the pane line.

## Table statistics (2026-08-23T02:33:26-05:00)

```text
SET
SET
 schemaname |      relname      | n_live_tup | n_dead_tup | seq_scan | idx_scan | last_analyze | last_autoanalyze 
------------+-------------------+------------+------------+----------+----------+--------------+------------------
 public     | individual_trades |          0 |          0 |        7 |        0 |              | 
(1 row)

 schemaname |      relname      | total_size 
------------+-------------------+------------
 public     | individual_trades | 32 kB
(1 row)

```

## Historical tmux evidence

Captured from `tmux capture-pane -t 0:7.0 -p -S -1200`.

| Timestamp (UTC) | Event | Evidence |
|---|---|---|
| 2026-08-23 04:10:35.387 | checkpoint start | after Transformer training completed at 04:10:23.382 |
| 2026-08-23 04:10:51.104 | checkpoint complete | 10 buffers; write 7.231 s; sync 3.520 s; total 15.718 s; 0 WAL files; distance 460 kB |
| 2026-08-23 05:05:35.931 | checkpoint start | during `bench-normal-3-symbol-1787461523`; worker stopped 05:05:42.468 |
| 2026-08-23 05:06:21.724 | checkpoint complete | 44 buffers; write **36.152 s**; sync **5.388 s**; total **45.793 s**; 0 WAL files; distance 788 kB; estimate 788 kB |
| 2026-08-23 05:10:35.823 | checkpoint start | later periodic checkpoint |
| 2026-08-23 05:10:45.227 | checkpoint complete | 8 buffers; write 3.843 s; sync 0.622 s; total 9.405 s; 0 WAL files; distance 80 kB |
| 2026-08-23 05:15:35.327 | checkpoint start | periodic checkpoint with repeated order-book query errors |
| 2026-08-23 05:15:57.569 | checkpoint complete | 12 buffers; write 9.988 s; sync 2.170 s; total 22.243 s; 0 WAL files; distance 75 kB |
| 2026-08-23 05:37:55.323 | shutdown | fast shutdown; not a workload checkpoint |
| 2026-08-23 05:38:00.713 | shutdown checkpoint complete | 0 buffers; write 1.649 s; sync 0.001 s; total 4.837 s |

## Interpretation

- The requested 45.793-second checkpoint and its 36.152-second write/5.388-second sync components are directly observable in pane 0:7.0.
- 44 buffers and 788 kB are small, while write+sync consume 41.540 s (~90.7% of total): consistent with storage/fsync latency or checkpoint scheduling pressure, not a large dirty-buffer volume. No WAL files were added.
- The checkpoint overlapped the bounded 3-symbol benchmark; this is temporal correlation, not causal proof. Frontend connection resets and a later exact-count statement timeout are additional correlation evidence.
- Other workload checkpoints were 9.405 s, 15.718 s, 16.728 s, and 22.243 s, making 45.793 s an outlier.
- Live activity/lock snapshots and two bounded order-book timings above provide the current baseline. No waiting locks at snapshot time would argue against lock contention then, not during the historical outlier.
- The current stack was healthy at collection; the original database was later shut down at 05:37:55 UTC, so live catalog snapshots cannot reconstruct the original window.
