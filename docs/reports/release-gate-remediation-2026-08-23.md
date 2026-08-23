# Release-gate remediation — 2026-08-23

Status: implementation complete, exact-SHA CI verification pending.

## Corrections

- The live worker now enforces a one-second inter-request cadence without changing the selected symbol universe.
- Quote fan-out diagnostics distinguish attempted, successful, and skipped symbols. A partial quote response or failed account/ticker snapshot blocks the tick before signal generation or live order dispatch.
- The expectancy harness includes both `orderbook` and `ml_enhanced_orderbook` producer fixtures. They use direct producer signals and are evaluated through the directional expected-return gate after fees, spread, and slippage.
- Indicator-family fixtures remain visible as `report-only-unavailable` until a real expected-return producer is present in both live and simulated execution. They cannot fabricate fills.

## After-cost fixture comparison

The synthetic fixture comparison is:

| Metric (after fixture costs) | Before remediation | Remediated contract |
| --- | ---: | ---: |
| Signals generated | 11 | 13 |
| Filled trades | 9 | 2 |
| Blocked intents | 2 | 11 |
| Average win | $13.22 | $23.00 |
| Average loss | $0.00 | $0.00 |
| Expectancy | $13.22 | $23.00 |
| Profit factor | infinite (no losses) | infinite (no losses) |
| Maximum drawdown | $0.00 | $0.00 |

The existing positive indicator fixtures supplied nine synthetic fills totaling $119 net after the fixture's fees/spread/slippage assumptions. The remediation removes those unsupported fills from actionable expectancy and adds two order-book producer fixtures totaling $46 net. This is not a live performance claim: it is a regression-fixture contract showing that unsupported diagnostics are excluded and supported order-book diagnostics remain cost-gated.

The report continues to require average win, average loss, expectancy, profit factor, drawdown, signal count, and blocked-intent counts from runtime/backtest evidence before any production optimization claim. No live orders were submitted for this remediation.

## Verification and release gate

- `git diff --check`: required before push.
- Local builds/tests: not run; this repository uses remote-only build verification for this task.
- Docker Build Validation: pending for the final pushed SHA; approval remains blocked until the exact head SHA matches a completed successful run across all required jobs and the full declared CTest set is confirmed.
- Residual risk: the one-second cadence is a safety backpressure floor, not a provider quota guarantee. Operators must continue to monitor provider errors, request-rate diagnostics, and blocked ticks.
