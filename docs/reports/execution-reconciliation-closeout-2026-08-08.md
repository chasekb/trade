# Execution reconciliation closeout — 2026-08-08

## Scope

This report covers the remaining *code* contract for `TRADE-BL-0014 — Attribute
execution blockers and outcomes by strategy`, and the diagnostic surface that
`TRADE-BL-0027` (no positive-PnL live order-book trades) needs in order to be
investigated from data rather than from source reading.

It does not claim that any data-dependent backlog item is closed. No Coinbase
order, liquidation, live-session restart, or account mutation was performed, and
no Docker or production image build was run locally.

## What the previous state was missing

`docs/reports/trade-backlog-current-closeout-2026-08-08.md` left
`TRADE-BL-0014` open because blocker accounting was per-session and global:
`SimulatedTradingService::execution_blocker_counts_` is a flat `reason → count`
map for the running session only, with no link from blocked intents to realized
outcomes and no per-strategy split. There was no way to ask "for strategy X over
the last N hours, how many generated signals became executable intents, which
blockers absorbed the rest, and what did the fills actually realize after fees?"

## Implemented in this change

### Reconciliation module

`include/trading/ExecutionReconciliation.hpp`, `src/trading/ExecutionReconciliation.cpp`

A pure aggregation over two inputs — `SignalAttribution` (one row per evaluated
signal, carrying the `execution_analysis` fields the trading services already
emit) and `OutcomeAttribution` (one row per trade leg) — producing, per strategy
and overall:

- signals evaluated / generated, executable intents, blocked intents;
- blocker buckets sorted by count, each with its share of blocked intents and
  the sum of fee-adjusted expected return that the bucket absorbed (so a blocker
  that is discarding positive-edge intents is visible, not just frequent);
- winners/losers, `win_rate` (0–100), average win, average loss (positive
  magnitude), expectancy per decided trade, profit factor, total PnL, total fees;
- `intent_conversion_rate` (executable intents / generated signals) and
  `outcome_coverage` (closing legs / executable intents);
- `outcomes_unexplained`, set when a window has closing legs but no executable
  intent behind them, so a clipped or mismatched window is not silently reported
  as a clean reconciliation.

The module deliberately carries no JSON or database types, so it is unit tested
without the server toolchain.

### API surface

`GET /api/trading/execution-reconciliation?hours=&session_id=&trade_type=&max_signals=`
in `src/api/PredictController.cpp`. It reads `order_book_signals.signal_data`
(for `execution_analysis`) and `individual_trades` over a trailing window and
serializes the report. Notes on the read:

- `individual_trades` has no explicit leg flag; entries are written with zero
  PnL and exits with the round trip's gross PnL, so a non-zero PnL identifies a
  closing leg. Realized PnL is reported **net of fees**, matching the objective's
  after-fee expectancy definition, while the stored `pnl` column stays gross.
- Query parameters are sanitized to identifier characters before interpolation.
- Signal rows are capped (`max_signals`) with an explicit
  `signal_rows_truncated` flag rather than a silent partial answer.
- An infinite profit factor (winners, no losers) serializes as `0` plus
  `profit_factor_undefined: true`, because jsoncpp cannot represent it.

This endpoint is read-only. It does not start, stop, size, or authorize trading.

### Frontend

- `frontend/lib/executionReconciliation.ts` — canonical normalizer, following
  the `simulatedTradingStats.ts` convention. It preserves the backend unit
  contract (`win_rate` never rescaled, `??`-style zero preservation), derives a
  blocker share when the backend omits one, and ranks strategies by expectancy
  risk (worst realized PnL first, then largest blocked backlog).
- `frontend/hooks/useExecutionReconciliation.ts` — React Query wrapper.
- `frontend/components/dashboard/ExecutionReconciliationTable.tsx` — per-strategy
  table plus overall metrics, rendered in the Simulated Trading tab. It surfaces
  truncation and `outcomes_unexplained` as explicit warnings.

## Objective impact

This change adds no execution path and does not alter sizing, gating, or order
submission, so it changes average win, average loss, expectancy, profit factor,
and drawdown by construction: not at all. Its purpose is to make the *blocked
intent* population measurable per strategy, which is the input the open
optimization items (`TRADE-BL-0008`, `TRADE-BL-0013`, `TRADE-BL-0016`) and the
open investigation items (`TRADE-BL-0022`, `TRADE-BL-0027`) require before any
expectancy claim can be made.

## Verification

Non-build checks only, per the standing verification contract:

- `src/tests/test_execution_reconciliation.cpp` — compiled and run standalone
  with `g++ -std=c++17` (the module has no toolchain dependencies): all
  assertions pass. It is registered as the `execution_reconciliation` CTest
  target and added to the `ctest -R` list the `Dockerfile.cpp` build stage runs,
  so CI executes it.
- `npm test` (frontend): 10 suites / 58 tests pass, including the 11 new
  `lib/executionReconciliation.test.ts` cases.
- `npx tsc --noEmit`: clean.
- `npx eslint` on every new file: clean. The repository-wide lint error count is
  unchanged (pre-existing `no-explicit-any` debt in `lib/api.ts` and others).
- The C++ controller and service code were **not** compiled locally; no host
  toolchain exists for them. Backend compilation is verified only by the pushed
  `Docker Build Validation` run.

## CI evidence

Closeout gate: the `Docker Build Validation` run whose `headSha` exactly matches
the pushed commit.

- Commit: `d5a21160f24fe1ea6b6729a1bbac7611d12f20f2` on `dev`
- Run ID: `31274960164` (event: `push`)
- URL: https://github.com/chasekb/trade/actions/runs/31274960164
- Conclusion: `success`
- Job conclusions:
  - Build C++ Backend (amd64): success
  - Build C++ Backend (arm64): success
  - Build Frontend (amd64): success
  - Build Frontend (arm64): success
  - Publish C++ Backend manifest: success
  - Publish Frontend manifest: success
- Verified: 2026-08-09T06:13:44Z

The backend build stage runs `ctest -R`, which now includes the
`execution_reconciliation` target, so the new C++ test executed on both
architectures as part of this run. A second run on the same SHA
(`31274961701`, event `pull_request`) also succeeded but builds amd64 only and
skips manifest publication; it does not satisfy the gate on its own.

## Still open

Unchanged from the prior closeout, and not claimed here: `TRADE-BL-0007`,
`TRADE-BL-0008`, `TRADE-BL-0013`, `TRADE-BL-0016`, `TRADE-BL-0022`,
`TRADE-BL-0027`, and the runtime-window half of `TRADE-BL-0014`. Each requires
live or replay evidence that cannot be produced by source changes. The
reconciliation endpoint is the instrument for capturing that evidence; running
it against a representative window is the next step, and it needs a live or
paper session plus explicit user authorization for anything touching the live
account.
