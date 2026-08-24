# Database Read Safeguard Decision — 2026-08-24

## Decision

No database index, query-plan rewrite, pagination change, timeout change, or database-manager error-propagation change is justified by the captured evidence. This implementation task therefore makes a documentation-only change and deliberately does not alter production read behavior.

## Evidence reviewed

The completed bounded read-only measurements and path trace reported:

- `order_book_signals` was absent from the captured runtime, so a representative populated order-book query could not be measured.
- `individual_trades` was present but empty (0 rows; relation size approximately 32 KiB).
- The runtime `individual_trades` schema lacked `is_closing_leg`, so the exact reconciliation projection failed immediately rather than exhibiting a slow read.
- Successful bounded probes completed in approximately 0.041–0.080 ms; the failed exact reconciliation projection returned in approximately 0.496 ms.
- Repeated missing-column errors were observed about once per minute.
- No lock wait, statement timeout, sort spill, or 30–120 second completion was captured.

These observations establish schema/runtime drift and insufficient populated data for a performance fix; they do not establish a slow access path or justify a speculative index. They also do not justify a hidden row cap, symbol cap, trade cap, or semantics-changing pagination strategy.

## Safeguards intentionally not changed

- Malformed, empty, and non-object `signal_data` handling remains unchanged.
- Signal filtering and outcome reconciliation remain unchanged, including strategy attribution, blocker counts, after-fee realized PnL, exact-flat closing-leg semantics, and outcome-coverage diagnostics.
- Existing deterministic response behavior and selected-universe completeness remain unchanged.
- `DatabaseManager` still requires a separately designed error/degraded-response contract before callers can distinguish an empty result from a failed read. Adding a timeout or changing empty-result behavior without representative endpoint tests would risk changing API semantics broadly.

## Required follow-up evidence before implementation

1. Capture a representative populated runtime containing both `order_book_signals` and `individual_trades` with schema versions matching the deployed executable.
2. Re-run bounded timings, query plans, relation/index inventory, lock/wait state, and payload-size measurements for status, stats, latest/count, and reconciliation paths.
3. Reproduce the missing-column failure and classify whether deployment schema migration, image skew, or query/schema contract drift owns the fault.
4. Define and test an explicit API degraded/error contract before changing shared database-manager failure propagation.
5. Only then consider an index, query rewrite, semantics-preserving keyset pagination, or scoped statement timeout, with before/after correctness and completeness evidence.

No local Docker, CMake, or C++ build was run, as required by the task.
