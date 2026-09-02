# PostgreSQL read-performance evidence — 2026-08-23

## Scope and safety

This is a read-only, bounded runtime investigation. All PostgreSQL inspection commands ran inside `trade_db_1` against `trading_db` as `trading_user` with a session `statement_timeout` of 5000 ms. No rows, schema objects, indexes, statistics, locks, or runtime configuration were changed. No local Docker/CMake/C++ build or test was run.

Capture time was 2026-08-23 07:23–07:25 UTC (02:23–02:25 CDT). Runtime container: `trade_cpp-backend_1`, host port 8081.

## Executive finding

The reported 30–120 second reads cannot be reproduced against the currently running database because the relevant baseline table is absent and `individual_trades` is empty. The measured read plans completed in 0.041–0.080 ms, with 0 rows and 32 kB total table size. This is not evidence that the production-sized query is fast; it is evidence that this runtime contains no order-book baseline data to scan.

A separate, actionable schema-drift failure is present: `individual_trades` lacks `is_closing_leg`, while the deployed backend repeatedly issues a reconciliation query selecting it. The exact query fails in 0.496 ms, and backend logs show the same error recurring about once per minute. This is a correctness/availability problem, not a slow-query problem.

## Current database state

- `current_database()`: `trading_db`
- PostgreSQL: 15.19
- `to_regclass('public.order_book_signals')`: NULL (relation absent)
- `to_regclass('public.individual_trades')`: `individual_trades`
- `individual_trades`: `n_live_tup=0`, `n_dead_tup=0`, `pg_total_relation_size=32768` bytes
- `last_analyze` and `last_autoanalyze`: NULL (the table has no analyzed runtime data)
- `individual_trades` columns do not include `is_closing_leg`
- Existing indexes:
  - `individual_trades_pkey (trade_id)`
  - `idx_individual_trades_timestamp (timestamp)`
  - `idx_individual_trades_symbol_timestamp (symbol, timestamp)`
- No active sessions other than the diagnostic connection were waiting on a lock or running a query at capture time.
- Database defaults reported: `statement_timeout=0`, `lock_timeout=0`, `idle_in_transaction_session_timeout=0`, `track_io_timing=off`. The 5000 ms timeout and I/O timing used above were session-local diagnostic settings.

## Query measurements

### Reconciliation-shaped trade read

Representative current-code shape (`src/api/PredictController.cpp:1762-1772`):

```sql
SELECT symbol, strategy_type, pnl, fees, is_closing_leg
FROM individual_trades
WHERE timestamp >= :window_start
  [AND session_id = :session_id]
  [AND trade_type = :trade_type];
```

The exact query failed immediately because `is_closing_leg` is absent:

- PostgreSQL error: `column "is_closing_leg" does not exist`
- elapsed time: 0.496 ms
- no lock wait or timeout occurred

A safe projection without that missing column was measured with `EXPLAIN (ANALYZE, BUFFERS, TIMING)` for a 24-hour window:

- sequential scan on `individual_trades`
- estimated 83 rows; actual 0 rows
- shared buffers hit: 3
- sort: quicksort, 25 kB
- planning: 1.164 ms
- execution: 0.080 ms

The sequential scan is expected for a 0-row/32 kB table and does not justify an index change by itself.

### PnL top-trades read

Representative current-code shape (`src/api/PredictController.cpp:1531-1538`):

```sql
SELECT symbol, side, size, price, timestamp, pnl
FROM individual_trades
WHERE pnl IS NOT NULL AND pnl <> 0
ORDER BY pnl DESC
LIMIT 10;
```

Measured plan:

- sequential scan, estimated 248 rows; actual 0 rows
- sort: quicksort, 25 kB
- shared buffers hit: 3
- planning: 0.125 ms
- execution: 0.058 ms

Again, this is too little data to evaluate production sorting cost or justify a `pnl` index.

### Order-book baseline relation check

`EXPLAIN (ANALYZE)` for `SELECT to_regclass('public.order_book_signals')` completed in 0.041 ms. The relation is absent, so no order-book scan, latest-per-symbol plan, row count, index inventory, or lock behavior can be measured in this runtime.

The current latest-signal query shape (`src/trading/SimulatedTradingService.cpp:2500-2526`, duplicated in `LiveTradingService.cpp:3387-3413`) uses `COUNT(DISTINCT symbol)` followed by `DISTINCT ON (symbol) ... ORDER BY symbol, timestamp DESC`, then an outer strength/timestamp sort with `LIMIT/OFFSET`. It was not executed because the source relation does not exist.

## Runtime/API and query-frequency evidence

- `GET /api/trading/execution-reconciliation?hours=24` returned HTTP 200 in 0.019063 s at capture time, with zero signal/outcome rows and no visible error field because `order_book_signals` is absent and no outcome rows were returned.
- `GET /api/ml/pnl-trades?sort_by=pnl` returned HTTP 200 in 0.024756 s with empty top/bottom arrays.
- `frontend/hooks/useExecutionReconciliation.ts:21-32` refetches reconciliation every 60 seconds.
- `frontend/hooks/useMLAnalytics.ts:31-42` refetches PnL trades every 60 seconds (and the dashboard query every 30 seconds).
- `trade_cpp-backend_1` logs from 02:21:27 through 02:25:24 show repeated `Database query failed: ERROR: column "is_closing_leg" does not exist` messages. The failures occur at roughly one-minute intervals, with additional requests around 02:25:24. The logged SQL is the reconciliation-shaped projection above.
- No log evidence in the captured 24-hour container window showed a PostgreSQL statement timeout, lock wait, sort spill, or 30–120 second query completion.

## Recommendations, narrowly justified

1. **Resolve schema drift before performance tuning.** Ensure the runtime database used by `trade_cpp-backend_1` executes the existing `is_closing_leg` schema migration/compatibility path, or deploy a compatible image/database migration. Verify the column and its nullable legacy semantics with read-only catalog checks before relying on reconciliation output. Do not silently remove the column from the query: that would lose exact-flat closing-leg accounting.
2. **Re-run this measurement against a populated, representative database.** The absent `order_book_signals` relation and empty trades table make index, pagination, stale-statistics, and frequency conclusions about 30–120 second reads non-determinable. Preserve the selected symbol/trade universe; do not introduce hidden caps.
3. **Candidate index only after populated-plan evidence:** if a populated reconciliation workload filters materially by `timestamp`, `session_id`, and `trade_type`, compare plans for a composite index shaped to the actual predicate (likely timestamp-leading or session/trade-type-leading based on selectivity). Existing timestamp and symbol/timestamp indexes are the only evidence-backed indexes currently present; adding another index now would be speculative.
4. **Candidate order-book index only after relation/data restoration:** validate a `(symbol, timestamp DESC)` index for the `DISTINCT ON (symbol) ... ORDER BY symbol, timestamp DESC` query, then measure the outer ordering and count query. Do not add it based on this empty runtime.
5. **Timeout/degradation handling:** the database defaults have no statement timeout. A bounded per-request/database statement timeout with an explicit visible degraded/error response is justified as a safety measure for the reported read class, but its value and implementation should be validated against a populated workload. The current frontend already surfaces query errors (`ExecutionReconciliationTable.tsx:40-45`) and partial-data diagnostics (`:66-73`); preserve that behavior rather than converting failures into empty successful results.
6. **Pagination:** the current reconciliation signal loop and latest-signal API use `OFFSET` (`PredictController.cpp:1712-1759`, `SimulatedTradingService.cpp:2512-2526`). Keyset pagination may reduce deep-page cost, but changing it without populated ordering/uniqueness evidence risks completeness or ordering regressions. Treat it as a follow-up measurement, not an immediate change.

## Closeout status

This report provides before-state evidence only. No performance fix or schema change is claimed. The primary blocker for a valid slow-query reproduction is the runtime state: missing `order_book_signals`, empty `individual_trades`, and schema drift on `is_closing_leg`.
