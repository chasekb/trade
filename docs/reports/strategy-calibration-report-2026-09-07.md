# Strategy calibration report

Date: 2026-09-07
Status: EVIDENCE-GATED — no promotion or mapping improvement is supported

## Executive decision

The completed walk-forward evaluation did not produce a measurable candidate-versus-baseline result. The available repository evidence contains deterministic smoke/regression fixtures, but no timestamped historical or live-parity paper outcome rows with symbol, regime, holding-period, split, and fee context, and no distinct fitted ranking mapping for comparison.

Accordingly, every evaluated strategy is deferred. This is not a claim of no improvement: the requested metrics are unavailable and are recorded as null rather than inferred as zero. No strategy should be promoted to a new calibrated mapping from this evidence.

## Scope and evaluated strategies

The evaluation inventory covers SMA, EMA, RSI, Bollinger Bands, MACD, Stochastic, Fibonacci Retracement, DCA, Buy and Hold, and Order Book. The current Python strategy implementations are present under `src/trade_bot/trading/strategies/`; Order Book additionally requires order-book/trade inputs and is not represented by the generic historical fixture path.

Disposition for every strategy: DEFER.

| Strategy | Baseline/implemented formula inventory | Evidence | Decision |
|---|---|---|---|
| SMA | Strategy-specific signal generation; universe ranking defaults to emitted `signal_strength` | Smoke fixture only; no paired outcome rows | Defer |
| EMA | Strategy-specific signal generation; ranking defaults to `signal_strength` | Smoke fixture only; no paired outcome rows | Defer |
| RSI | RSI threshold signal logic; strength is an emitted signal field, not a fitted outcome mapping | Smoke fixture only; no paired outcome rows | Defer |
| Bollinger Bands | Band-distance signal logic; no fitted profitability coefficient set | Smoke fixture only; no paired outcome rows | Defer |
| MACD | Crossover/signal-line logic; no fitted profitability coefficient set | Smoke fixture only; no paired outcome rows | Defer |
| Stochastic | Threshold/crossover signal logic; no fitted outcome mapping | Smoke fixture only; no paired outcome rows | Defer |
| Fibonacci Retracement | Retracement-level signal logic; no fitted outcome mapping | Smoke fixture only; no paired outcome rows | Defer |
| DCA | Scheduled/parameterized accumulation behavior; holding-period outcomes unavailable | Smoke fixture only; no chronological outcomes | Defer |
| Buy and Hold | Entry/hold behavior; holding-period outcomes unavailable | Smoke fixture only; no chronological outcomes | Defer |
| Order Book | Requires separate order-book and recent-trades inputs; generic harness is out of scope | No suitable timestamped order-book outcome dataset | Defer |

These are formula/inventory descriptions, not evidence that any formula is profitable. Exact implementations remain the source of truth at the paths listed in Reproducibility.

## Methodology and evidence gate

The requested methodology was baseline versus implemented mapping over chronological walk-forward splits, with buckets by emitted strength, symbol, regime, holding period, and fees. It also required monotonicity, fee-adjusted expectancy, average win, average loss, drawdown, combined-objective delta, and incremental predictive value beyond raw indicator distance.

The completed evaluation found:

| Requirement | Available evidence | Result |
|---|---|---|
| Timestamp-ordered replay rows | None with required outcome metadata | Not run |
| Distinct candidate/fitted mapping | Not found | Not available |
| Walk-forward splits | No split-ready dataset | Not run |
| Strength buckets | Only synthetic smoke rows | Insufficient |
| Symbol/regime/holding-period buckets | Missing fixture fields | Not possible |
| Fee treatment | Fee-bearing deterministic fixtures exist | Smoke/regression gate only |
| Average win/loss and drawdown | Aggregate harness concepts exist | Not walk-forward evidence |
| Monotonicity | No ordered outcome buckets | Null |
| Fee-adjusted expectancy delta | No paired baseline/candidate outcomes | Null |
| Combined objective delta | No paired baseline/candidate outcomes | Null |
| Incremental predictive value | No paired ablation dataset | Null |

No metric is converted to a zero or a positive result. Data insufficiency is the reason for deferral, not a rejection of the underlying strategies.

## Regression-test evidence

The ranking regression artifact adds deterministic, fee-bearing fixtures for three explicit mappings:

- `signal_strength`: known-good strength 0.90 ranks ahead of known-bad strength 0.20.
- `expected_return`: known-good expected return 0.08 ranks ahead of known-bad -0.01.
- `win_probability`: known-good probability 0.92 ranks ahead of known-bad 0.35.
- A held signal remains filtered even when its ranking values are excellent.
- `order_prioritization="none"` preserves input order.

These tests demonstrate ordering and safety contracts only. They do not demonstrate predictive accuracy, profitability, monotonicity over realized outcomes, or improvement over a baseline. The focused test file is `tests/test_ranking_mappings_regression.py` on commit `2e47b7428f6fa55a6de99a0c6d84a7e1ec6e873e`. Per the handoff, the focused suite was not run locally under the remote-CI-only policy and no exact-SHA Actions run was reported for that commit; this report therefore records test design/static evidence, not a passing CI claim.

## Strength versus expected-return diagnostics

Keep strength and profitability diagnostics separate for now. `signal_strength` represents technical signal magnitude or ranking priority. `expected_return` and `win_probability` represent profitability diagnostics with different units and assumptions, including fees and execution effects. Combining them without paired out-of-sample calibration would create an unsupported score, obscure which diagnostic caused a decision, and could increase execution on signals whose realized expectancy has not been established.

The safe current contract is therefore:

1. Preserve the explicit mapping selected by configuration.
2. Keep held/rejected signals filtered before ranking.
3. Permit deterministic ranking tests to protect ordering semantics.
4. Defer any combined score until paired, timestamped, out-of-sample evidence shows stable incremental value after fees, spread, and slippage.

## Reproducibility and provenance

Primary source paths inspected:

- `src/trade_bot/core/universe_selector.py` — signal-strength calculation and universe selection.
- `src/trade_bot/trading/simulated_trading_manager.py:536-602` — prioritization selection, filtering, and descending ranking.
- `src/trade_bot/trading/strategies/` — SMA, EMA, RSI, Bollinger, MACD, Stochastic, Fibonacci, DCA, Buy and Hold, Order Book, and related implementations.
- `docs/API_REFERENCE.md:253-276` — documented `signal_strength`, `win_probability`, and `expected_return` prioritization options and default.
- `tests/test_ranking_mappings_regression.py` — deterministic regression fixtures (available on the upstream implementation commit cited above).
- `docs/reports/artifacts/strategy-calibration-walk-forward-evaluation-2026-08-22.json` — machine-readable evidence-gate artifact on upstream calibration commit `c0c8c3ddaf44ea6ae51d23f5caf206cb83dc6ff1`.
- `docs/reports/artifacts/strategy-calibration-walk-forward-evaluation-2026-08-22.json` records the unavailable dimensions, null metrics, and all-strategy defer disposition.

The upstream calibration artifact's exact-SHA workflow evidence was run `32618280684`, terminal success, with required jobs `Build C++ Backend (amd64)` and `Build Frontend (amd64)` successful. That CI result validates the artifact commit only; it is not evidence for the separate regression-test commit.

## Limits and future rerun contract

A future calibration rerun requires timestamped rows containing strategy, symbol, emitted strength, raw indicator distance, regime, entry and exit timestamps, holding period, realized gross PnL, fees, spread, slippage, and action/blocker fields. It must declare per-strategy and per-bucket sample thresholds, use chronological leakage-free folds, run paired baseline/candidate outputs on identical rows, and publish fold-level plus aggregate metrics with sample counts and stability intervals. The ablation must compare raw indicator distance against profitability diagnostics and preserve enough provenance to reproduce each bucket.

No local build or test command was run. `git diff --check` is the permitted static hygiene gate for this documentation change; remote CI remains the required execution gate for repository delivery.
