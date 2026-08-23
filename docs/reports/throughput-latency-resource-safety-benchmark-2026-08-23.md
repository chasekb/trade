# Throughput, latency, and resource-safety benchmark

Date: 2026-08-23
Task: `t_afd315bc`

## Verdict

BLOCKED for a full live-trading performance sign-off. The controlled benchmark exercised bounded simulated sessions only and found a reproducible runtime degradation during stop/start and overload sequencing: status/start requests reached 12.50 seconds, and subsequent health/status requests timed out for at least five seconds. The run did not submit Coinbase orders. The evidence is sufficient to keep the implementation open for investigation, but not to claim live rate-limit, account-snapshot, or exchange-budget compliance.

## Reproduction

The benchmark harness is `tools/benchmark_throughput.py`. It calls only:

- `POST /api/trading/simulated/start`
- `GET /api/trading/simulated/status`
- `POST /api/trading/simulated/stop`

It never calls a live start or order endpoint and forces `execution_mode=simulated` and `live_order_execution=false`.

Run against a running backend image:

```bash
python3 tools/benchmark_throughput.py \
  --base-url http://127.0.0.1:8081 \
  --duration 5 \
  --interval 1 \
  --output docs/benchmarks/throughput-samples.jsonl
```

The command writes compact JSONL samples plus a `.summary.json` file. The checked-in sample dataset is `docs/benchmarks/throughput-samples.jsonl`; it includes the raw status payload under each sample for independent re-analysis.

## Scenarios and bounds

| Scenario | Universe | Duration | Execution | Purpose |
| --- | ---: | ---: | --- | --- |
| normal-3-symbol | 3 synthetic symbols | 5 s | paper only | baseline tick/status path |
| overload-64-symbol | 64 synthetic symbols | 5 s | paper only | bounded selected-universe stress; not exchange capacity evidence |

The overload is explicitly bounded at 64 symbols. It does not create an unbounded loop or fan-out in the harness.

## Observed measurements

The current checked-in JSONL and summary record the final repeat, while the earlier successful 64-symbol run was observed in the same session before the repeat and is reported below as session evidence. The important observations are:

- Normal 3-symbol run: 2 active status samples, tick advanced from 0 to 8, 9 evaluated signals by stop, no pending orders, all HTTP responses were 2xx, and paper execution remained true.
- Normal run request latency: minimum 24.422 ms, mean 5,531.913 ms, p50 4,075.518 ms, p95 11,653.771 ms, maximum 12,495.799 ms. The high values were caused by serialized stop/start/status behavior and are a regression signal, not a target threshold pass.
- The prior successful 64-symbol synthetic run reached tick 3 with 192 evaluated signals, 64 latest-by-symbol signals, zero pending orders, zero generated intents, and approximately 27–31 ms status latency while active. This shows bounded synthetic processing completed, but does not establish live exchange capacity.
- The repeat overload start was rejected while the previous worker was settling; subsequent status responses remained tied to the prior 3-symbol session. This is captured as a lifecycle/settling failure rather than misreported as a 64-symbol result.
- All benchmark samples had HTTP status 2xx and `execution_is_paper=true`.
- No account snapshot latency, Coinbase 429 rate, exchange request timeout rate, live quote latency, or live blocked-intent distribution was measured because this safe run did not enable credentials or live execution.
- The backend health endpoint timed out after the benchmark when queried with a 5-second timeout. The process remained present and low CPU (~0.8% at the inspection instant), so this is an HTTP responsiveness failure, not evidence of process exit.

## Source-backed resource and budget audit

- `LiveTradingService::workerLoop` fetches the selected universe before taking the state mutex, generates a tick under the mutex, then dispatches orders and flushes writes outside the mutex (`src/trading/LiveTradingService.cpp:2321-2403`).
- Live quote selection returns the full configured universe with no symbol cap (`src/trading/LiveTradingService.cpp:1244-1263`). Diagnostics explicitly report `live_quote_symbols_per_tick_cap=0` and `quote_fanout_limit_enforced=false` (`src/trading/LiveTradingService.cpp:2561-2581`).
- Live quote fetching is serial per symbol (`src/trading/LiveTradingService.cpp:1208-1241`), so the current implementation has no adaptive concurrent quote fan-out to verify. The client uses blocking calls with a bounded 15-second wait (`include/exchange/CoinbaseAdvancedClient.hpp:63-66`, `src/exchange/CoinbaseAdvancedClient.cpp:168-193`).
- Live account refresh is also performed in the worker after quote fetching (`src/trading/LiveTradingService.cpp:2374-2377`, `1266-1297`). Its latency and failure counters are not exposed as benchmark diagnostics.
- Simulated writes are batched outside the mutex, but failed persistence requeues the full batch (`src/trading/SimulatedTradingService.cpp:940-1042`). The observed long status/start latencies and settling rejection require a follow-up investigation of persistence and lifecycle join behavior before overload approval.
- Pending order count and reserved cash remained zero in the safe benchmark; no duplicate-order path was exercised.

## Thresholds and acceptance status

| Acceptance area | Evidence | Status |
| --- | --- | --- |
| Reproducible commands/dataset | Harness, JSONL, summary JSON | PASS |
| Normal synthetic sweep/tick behavior | Tick and signal samples | PARTIAL |
| Bounded overload/no unbounded benchmark fan-out | 64-symbol bounded scenario | PASS for harness only |
| Queue lag/depth and stale age | No public counters; pending order fields only | BLOCKED |
| Request latency/error/timeout distributions | HTTP samples; timeout observed after run | FAIL / regression |
| Flush/mutex bottlenecks | Source audit only; no lock/flush timers exposed | BLOCKED |
| Coinbase 429/rate-limit compliance | Live path not exercised | BLOCKED |
| Account snapshot latency | Live path not exercised | BLOCKED |
| Adaptive concurrency exchange-budget compliance | No adaptive-concurrency metric or implementation found | BLOCKED |
| Blocked intents/duplicate orders | Synthetic blockers observed; no live orders | PARTIAL |
| Baseline regression comparison | No comparable versioned runtime baseline available | BLOCKED |

## Required follow-up before closure

1. Reproduce the stop/start settling delay with a clean backend and database, recording worker join time, flush duration, pending-write depth, and API handler latency.
2. Add or expose bounded counters/timestamps for queue depth/age, tick duration, quote duration, account snapshot duration, flush duration, mutex wait, timeout/error/429 classification, stale age, and blocked/duplicate intents.
3. Run separate live-parity public-market-data tests with credentials absent and present as appropriate, but keep live order submission disabled until exchange-budget evidence exists.
4. Run a controlled live quote-universe test against a test-approved account/universe and record the provider's actual 429/timeout behavior; do not infer compliance from the synthetic 64-symbol run.
5. Compare against a versioned baseline using identical universe, duration, parameters, backend image, database state, and host resource limits.

No local Docker/CMake build or compiled test was run. The benchmark used the already-running backend container and made no live orders or destructive account changes.
