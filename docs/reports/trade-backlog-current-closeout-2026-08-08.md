# Trade backlog implementation closeout — 2026-08-08

## Scope

This report records the implementation state of the actionable trade backlog work present on `dev` at the time of this closeout. It does not claim that data-dependent optimization or live-account investigation work is complete without the required runtime/evaluation evidence.

Local Docker, CMake, C++ compilation, and production image builds were not run. No Coinbase order, liquidation, live-session restart, or account mutation was performed.

## Implemented and ready for exact-SHA CI closeout

### TRADE-BL-0006 — Add live-parity simulated trading mode

Implemented in commits `0209ca1` and `b7ebb9c`:

- `execution_mode=live_parity` is accepted by the simulated start endpoint.
- The mode uses Coinbase public order-book data and does not synthesize a tick when a quote is missing or invalid.
- Paper execution applies the live-relevant spot, minimum-notional, cash, holding, pending-order, max-position, and ML/profitability checks before a paper fill.
- Paper fills settle in the simulated service and never submit a Coinbase order.
- Synthetic simulation remains a separate mode.
- Status, portfolio, signal rows, and the dashboard identify live-data paper execution and blocker outcomes.

Source/report references:

- `src/api/PredictController.cpp`
- `src/trading/SimulatedTradingService.cpp`
- `include/trading/SimulatedTradingService.hpp`
- `frontend/components/dashboard/SimulatedTradingPanel.tsx`
- `frontend/lib/api.ts`
- `frontend/lib/startTradingPayload.test.ts`
- `docs/reports/live-parity-paper-and-blocker-attribution-progress-2026-08-08.md`

### Live-parity portion of TRADE-BL-0014 — Attribute execution blockers and outcomes by strategy

Implemented for live-parity paper sessions:

- Each generated signal receives `execution_analysis` with intended side, diagnostic factor, expected-return fields, allocation, blocker reason, and executable-intent status.
- Paper blocker counts are accumulated in session status and portfolio responses.
- The frontend renders blocker and executable-intent summaries in the order-book widget.
- Live execution attribution remains observational and downstream of the existing live safety gates; it does not authorize orders.

The broader item is not closed by this report because a representative runtime window reconciling every generated signal to a paper/live outcome by strategy and blocker bucket is still required.

### TRADE-BL-0021 — Normalize live and simulated order-book signal throughput safely

The current implementation and report normalize the read/diagnostic contract without removing live execution safety:

- latest-by-symbol totals are distinguished from cumulative history;
- active-signal and average-strength aggregates are computed before display pagination for active in-memory reads;
- selected-universe widget coverage is represented with explicit missing/stale rows;
- frontend chunking fetches all selected symbols before display-only pagination;
- live quote cadence/freshness and execution blockers remain explicit diagnostics;
- selected live symbols and retry behavior remain user-controlled.

This is throughput-contract normalization, not a claim of measured live profitability or exchange-rate-limit performance improvement. Those measurements remain open under the optimization backlog.

Primary report: `docs/reports/live-simulated-orderbook-throughput-normalization-closeout-2026-08-05.md`.

## Backlog work intentionally not claimed complete

The following items require evidence that cannot be fabricated from source inspection alone:

- `TRADE-BL-0007`: one-time ETH-USD dust cleanup requires a fresh dry run and explicit user approval of exact live-risk parameters before any order; no order was executed.
- `TRADE-BL-0008`: order-book strength/expectancy tuning requires a baseline and walk-forward or fixture-backed outcome data.
- `TRADE-BL-0013`: indicator-strength calibration requires realized outcomes by strength bucket and regime.
- `TRADE-BL-0014`: full runtime reconciliation of generated signals, blockers, and outcomes remains open beyond the live-parity instrumentation slice.
- `TRADE-BL-0016`: active diagnostic factoring and ablation evidence requires replay/evaluation data.
- `TRADE-BL-0022`: phantom ETH-USD investigation requires a reproducible live/API snapshot and must not be closed from stale source leads.
- `TRADE-BL-0027`: no-positive-PnL investigation requires a reproducible live order-book outcome window with fees, spread, slippage, fills, blockers, and realized PnL.

No backlog item above should be marked closed solely because this report exists. Implementation items are eligible for closure only after independent review and exact pushed-SHA GitHub Actions evidence; investigation and optimization items also require their stated runtime/data evidence.

## Verification contract

Before push, only non-build checks are permitted:

- `git diff --check`;
- targeted frontend tests/typecheck/source-contract checks;
- independent fresh-context safety review;
- no secret-bearing file access.

After push, the closeout gate is the `Docker Build Validation` run whose `headSha` exactly matches the pushed commit. Required push-run jobs are the C++ backend amd64/arm64 builds, frontend amd64/arm64 builds, and both manifest publication jobs. The final delivery record must include the exact SHA, run ID, URL, job conclusions, and verification timestamp.

## Latest exact-SHA delivery verification

The branch is currently at `dc9960123611f4126fdef50e9f8e7257fc5e5eb6`, which is
also `origin/dev`. The push-triggered Docker Build Validation run for that
exact SHA completed successfully:

- Run ID: `31298425045`
- URL: https://github.com/chasekb/trade/actions/runs/31298425045
- Event: `push`
- Conclusion: `success`
- Build C++ Backend (amd64): success
- Build C++ Backend (arm64): success
- Build Frontend (amd64): success
- Build Frontend (arm64): success
- Publish C++ Backend manifest: success
- Publish Frontend manifest: success

No local Docker, CMake, C++ backend, or production image build was run.
