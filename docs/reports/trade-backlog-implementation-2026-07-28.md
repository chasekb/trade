# Trade Backlog Implementation Report — 2026-07-28

## Scope implemented in this change

This change implements the safe, code-backed parts of the current trade backlog that can be shipped without placing live orders or building locally:

- Documents the project-wide objective: maximize risk-adjusted expectancy in the live trading environment by increasing average win and minimizing average loss after fees/spread/slippage and execution blockers.
- Adds a strategy-neutral profitability diagnostic helper that makes expected-return factoring explicit and fail-safe.
- Adds regression coverage for diagnostic factoring: missing expected return, weak strength, fee-negative edge, favorable buy edge, and favorable sell edge.
- Fixes the frontend local simulated fallback signal contract so `signal_type` is `buy`/`sell` instead of the strategy name.
- Removes repo-local recommendation markdown files after migrating them into the Hermes trade backlog.

No local Docker or CMake build was run. The requested verification path is remote GitHub Actions after push.

## Backlog item mapping

### TRADE-BL-0001 — Audit simulated trading statistics calculation accuracy

Prior implementation already centralized simulated stats behavior in `frontend/lib/simulatedTradingStats.ts` and adjacent tests. This change does not redo that prior work. The item remains covered by existing stats tests and the migrated backlog criteria.

### TRADE-BL-0002 — Review trade data and produce training optimization plan

The project objective documentation now requires training/model changes to report average win, average loss, expectancy, profit factor, drawdown, and trade frequency impact.

### TRADE-BL-0003 — Clean dashboard warning debt without trading regressions

Not directly changed in this slice except that deleted repo-local recommendation docs reduce stale backlog noise. Dashboard warning cleanup should remain a separate low-risk cleanup task if lint still reports warnings.

### TRADE-BL-0004 — Reconcile simulated trading portfolio cash and position totals

Prior implementation and tests cover simulated portfolio/stat normalization. This change keeps that as existing behavior and does not alter settlement accounting.

### TRADE-BL-0005 — Reconcile live and simulated order-book signal execution deltas

Prior implementation aligned order-book profitability gate diagnostics and live/simulated expected-return branches. This change adds a strategy-neutral diagnostic helper so future parity work can use the same expected-return classification outside order-book rows.

### TRADE-BL-0006 — Add live-parity simulated trading mode

This change does not implement full live-parity paper mode. It does fix one frontend simulated fallback contract bug: local synthetic rows now emit `signal_type: buy|sell` instead of `signal_type: <strategy>`. Full live-data paper execution remains larger backend/frontend work.

### TRADE-BL-0007 — Close ETH-USD dust with one-time explicit extra exposure

Not executed. This item requires a separate explicit user approval containing the exact quote buy amount, maximum acceptable cost, slippage tolerance, timeout, and abort criteria immediately before live orders are placed. This change does not place orders and does not add an automatic dust-sweeping path.

### TRADE-BL-0008 — Continue maximizing order-book signal strength for expectancy

The objective doc now states that signal/trade count can only be increased when it improves expectancy and does not worsen drawdown beyond risk tolerance. The strategy-neutral diagnostic helper provides a shared way to classify fee-adjusted expected edge.

### TRADE-BL-0009 — Document expectancy maximization as project decision objective

Implemented by `docs/STRATEGY_OBJECTIVE.md` and linked from `CLAUDE.md`.

### TRADE-BL-0010 — Code review every live and simulated trading strategy for objective alignment

The implementation adds explicit diagnostic factoring contracts and tests. A full fresh-context code review still needs to evaluate every strategy end-to-end before this backlog item should be marked fully closed.

### TRADE-BL-0011 — Add shared strategy expectancy evaluation harness

This change adds the first shared strategy profitability diagnostic primitive and unit coverage. A complete historical/replay harness remains future work.

### TRADE-BL-0012 — Extend profitability and expected-return diagnostics beyond order-book strategies

Partially implemented by the new strategy-neutral diagnostic helper in `StrategySignal.hpp/cpp`. It establishes explicit classifications for hold, weak strength, unavailable expected return, negative fee-adjusted edge, and passed fee-adjusted edge.

### TRADE-BL-0013 — Calibrate indicator strategy strength formulas to realized outcomes

Not fully implemented. The new diagnostic primitive is a prerequisite for calibrating strength together with expected-return/profitability diagnostics, but calibration requires historical/live-parity evidence.

### TRADE-BL-0014 — Attribute execution blockers and outcomes by strategy

Partially implemented at the diagnostic helper level by returning factor labels such as `expected_return_unavailable`, `weak_strength`, `negative_fee_adjusted_edge`, and `fee_adjusted_edge_passed`. Full runtime blocker persistence/reporting remains future work.

### TRADE-BL-0015 — Fix local simulated frontend fallback signal contract

Implemented in `frontend/lib/api.ts`: synthetic local simulated order-book rows now set `signal_type` to the generated buy/sell side instead of the strategy name.

### TRADE-BL-0016 — Optimize strategy factoring of profitability and expected-return diagnostics

Partially implemented by adding the shared factoring helper, tests, and objective documentation. Full optimization requires the evaluation harness and per-strategy calibration evidence.

## Files changed

- `CLAUDE.md`
- `docs/STRATEGY_OBJECTIVE.md`
- `docs/reports/trade-backlog-implementation-2026-07-28.md`
- `include/trading/StrategySignal.hpp`
- `src/trading/StrategySignal.cpp`
- `src/tests/test_strategy_signal.cpp`
- `frontend/lib/api.ts`
- deleted migrated repo-local recommendation docs under `.hermes/plans/`

## Verification plan

Local build is intentionally skipped per user instruction. Before commit/push, run non-build checks only:

- `git diff --check`
- targeted frontend Jest for the API/start payload path if available
- static added-line secret scan
- independent review for the live/strategy-affecting diff

After push, verify the exact pushed SHA through GitHub Actions Docker Build Validation.

## Remaining blockers that should not be hidden

- Full live-parity simulated trading mode is larger than this safe slice and is not complete here.
- One-time ETH-USD dust closure is not executed because it requires explicit live-order risk parameters immediately before execution.
- Full all-strategy historical expectancy calibration needs live/simulated datasets and replay harness work.
