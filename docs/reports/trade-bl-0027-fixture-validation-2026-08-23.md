# TRADE-BL-0027 fixture and replay validation

Date: 2026-08-23 UTC
Repository: `chasekb/trade`
Scope: simulated, deterministic replay, live-parity paper, and order-book fixture coverage

## Determination

The checkout contains deterministic strategy and execution-reconciliation fixtures, but no persisted historical replay dataset, captured live-parity paper outcome set, or order-book market-data fixture. The deterministic fixtures validate signal/gate/accounting contracts only. They do **not** establish live or live-parity profitability and cannot confirm the reported live no-positive-PnL observation.

The strongest available runtime evidence is the frozen artifact referenced in the prior investigation work:
`docs/evidence/trade-bl-0027-live-orderbook-baseline-2026-08-22/{manifest.md,raw_tmux_excerpt.log}`.
That evidence identifies a simulated worker (`sim_17874`), repeated order-book fetch failures, no selected-universe payload, and no qualifying live fills/outcomes. It therefore remains diagnostic evidence, not a live-PnL dataset.

## Fixture inventory

| Fixture / harness | Source | Coverage | Result available without local build |
|---|---|---|---|
| Deterministic expectancy fixtures | `defaultStrategyExpectancyFixtures()` in `src/trading/StrategyExpectancyHarness.cpp:169-199` | 9 positive-edge strategy cases plus 2 fee-negative SMA/EMA cases | Source assertions inspected; executable not present in the worktree |
| Expectancy harness test | `src/tests/test_strategy_expectancy_harness.cpp:26-95` | Counts generated signals, fills, blocked intents, average win/loss, expectancy, profit factor, drawdown, and negative-expectancy flag | Source assertions inspected; not run locally under remote-CI policy |
| Execution reconciliation fixture | `src/tests/test_execution_reconciliation.cpp:90-191` | Hold rows, blocked intents, executable intents, opening/closing legs, exact-flat fee-negative close, unexplained outcomes, blocker buckets, and unknown strategy labels | Source assertions inspected; not run locally under remote-CI policy |
| Strategy signal implementation | `src/trading/StrategySignal.cpp:113-260` | Deterministic indicator signal generation and warm-up behavior | Static inspection only |
| Live-parity paper fixture | None found | No captured Coinbase order-book input, live/sim parity row pair, paper-fill ledger, or replay adapter | Missing dependency |
| Order-book fixture | None found | No checked-in bid/ask/depth/timestamp fixture suitable for replay | Missing dependency |

Searches performed:

```text
search_files repo: *replay*       -> no matches
search_files repo: *fixture*      -> no matches
search_files repo: *paper*        -> report-only matches; no fixture data
search_files ~/.hermes: *replay*  -> Hermes-agent replay tooling only; no trade-market replay
search_files ~/.hermes: *fixture* -> Hermes-agent test fixtures only; no trade-market fixture
```

The `~/.hermes` matches named `replay` belong to Hermes Agent internals, not this trading strategy, and were excluded from the comparison.

## Deterministic economics and accounting comparison

The deterministic expectancy harness applies the following contract:

- signal generation is produced by `evaluateStrategySignal()`;
- profitability diagnostics use expected return, spread, round-trip fee, slippage buffer, and minimum signal strength;
- a non-hold signal is blocked when the fee-adjusted edge is not actionable;
- `realized_pnl` is attached only to a filled fixture;
- average loss is reported as a positive magnitude;
- expectancy is total realized PnL divided by filled trades;
- drawdown is calculated in dollars from cumulative realized PnL;
- fee-negative fixture rows are generated but blocked before fill.

The default fixture IDs are:

```text
sma-uptrend-positive-edge
ema-uptrend-positive-edge
rsi-oversold-positive-edge
bollinger-drop-positive-edge
macd-uptrend-positive-edge
stochastic-low-positive-edge
fibonacci-support-positive-edge
dca-positive-edge
buyandhold-positive-edge
sma-uptrend-fee-negative-edge
ema-uptrend-fee-negative-edge
```

The reconciliation fixture separately verifies:

- generated versus executable versus blocked intent counts;
- blocker aggregation and blocked expected-return sums;
- opening fees retained while only closing legs enter outcome denominators;
- exact-flat gross close remains a closing leg and becomes a fee-negative loser;
- outcomes without executable intents are flagged unexplained;
- missing strategy labels are retained in an `unknown` bucket.

These are useful regression contracts for signal/gate/fill/PnL attribution, but they use hand-authored prices and realized outcomes. They contain no symbol/time-series market regime, quote age, bid/ask spread, actual fill price, exchange fee, holding period, or model output history.

## Live-parity comparison matrix

| Dimension | Deterministic fixture | Required live-parity evidence | Status |
|---|---|---|---|
| Signal generation | Hand-authored price deque | Same captured order-book input through live and paper paths | Partial: deterministic only |
| Profitability gate | Configured expected return, fee, spread, slippage values | Per-signal live-parity diagnostic fields and blocker reason | Partial: contract only |
| Fill assumptions | Fixture directly supplies realized PnL | Paper fill price/quantity/timestamp and fee-bearing ledger | Missing |
| Fees/spread/slippage | Inputs exist, but no exchange observations | Actual bid/ask, slippage, and charged fee per fill | Missing |
| Exits | Closing-leg helper including exact-flat fee case | Entry-to-exit sequence from a paper session | Missing |
| PnL attribution | Synthetic realized PnL attached to fixture fills | Persisted signal-to-intent-to-fill-to-closing-leg linkage | Missing |
| Selected universe and coverage | Not represented | Serialized start/status request and per-symbol quote freshness | Missing |
| Live safety gates | Reconciliation blocker taxonomy only | Same spot/minimum-notional/cash/pending/max-position checks in paper mode | Source contract exists; parity fixture missing |

## Validation commands and results

Commands used for read-only discovery and source inspection:

```text
read_file CLAUDE.md                                      PASS
search_files repo *replay*, *fixture*, *paper*, *test*   PASS
search_files ~/.hermes *replay*, *fixture*, *paper*      PASS
read_file StrategyExpectancyHarness.cpp/.hpp             PASS
read_file test_strategy_expectancy_harness.cpp           PASS
read_file test_execution_reconciliation.cpp              PASS
read_file StrategySignal.cpp                             PASS
read_file SimulatedTradingService.cpp                    PASS
```

The C++ harness executables were not present in the worktree. Local CMake/Docker builds and local test execution were intentionally not run because this Kanban task requires remote-only verification. No live account, order, paper session, or external trading state was changed.

The relevant executable test targets are registered in `CMakeLists.txt` and included by the Docker test image's CTest filter:

```text
test_strategy_expectancy_harness
test_execution_reconciliation
```

They must be run by GitHub Actions Docker Build Validation for a code-changing follow-up; this documentation-only validation task does not claim a fresh exact-SHA CI run.

## Coverage gaps and targeted regression recommendations

1. Add a deterministic order-book replay fixture containing timestamped bid/ask/depth for at least one buy, one sell/spot-short rejection, one stale/missing quote, and one spread/slippage edge case.
2. Add a live-versus-live-parity fixture test that feeds identical order-book rows through both signal paths and compares signal type, strength, expected return, fee-adjusted edge, required edge, and blocker reason.
3. Add a paper-fill ledger fixture covering entry, profitable exit, losing exit, exact-flat gross exit with fees, and an unexplained outcome; reconcile every row by session, symbol, and signal ID.
4. Add a selected-universe fixture that proves all requested symbols are evaluated, while display pagination remains separate from backend evaluation and no hidden cap truncates executable intents.
5. Add a quote-age/fetch-failure fixture that distinguishes insufficient market data from a valid-data profitability hold.

No parameter change is recommended from these fixtures. Any implementation or configuration follow-up must preserve fail-closed live gates, receive independent high-risk review, and pass Docker Build Validation for the exact pushed SHA before closure.
