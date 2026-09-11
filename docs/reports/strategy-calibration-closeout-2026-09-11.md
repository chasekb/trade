# TRADE-BL-0013 calibration closeout evidence

Date: 2026-09-11
Status: EVIDENCE-GATED — preserve the implementation, defer production indicator remapping

## Decision

No production SMA, EMA, RSI, Bollinger, MACD, Stochastic, or Fibonacci strength formula is promoted by this evaluation. The available evidence contains deterministic regression fixtures and an offline diagnostic ablation replay, but not the historical/live-parity paper outcome population required for leakage-free walk-forward calibration. Therefore monotonicity, confidence intervals, per-regime stability, and baseline-versus-candidate objective improvement are recorded as unavailable, not as zero or as a positive result.

The safe closeout is to retain the backward-compatible raw signal behavior and the evidence-backed fail-closed diagnostic/calibration seam. DCA and Buy and Hold remain baselines, while Order Book and ML order-book paths remain separate families requiring their own outcome data.

## Exact formula and contract changes

The implementation lineage applies calibration only through the additive StrategySignal evaluation seam; the legacy evaluator remains source-compatible.

- Valid calibrated mappings are bounded by validated raw-strength bins and monotonic effective-strength values. Invalid, unsorted, non-monotonic, insufficient, or held mappings fall back to raw strength and are not promoted.
- Context selection is deterministic: strategy, side, holding-period interval, fee interval, and regime are matched explicitly; exact regime rules take precedence over the explicit `unknown` fallback. `unknown` is not a wildcard. Ambiguity remains fail-closed.
- Missing or unavailable diagnostics remain unavailable and do not become a zero or high-confidence score. The profitability gate remains separate and fee-aware.
- Diagnostic replay net return is `direction * (exit - entry) / entry - round_trip_cost`, where `round_trip_cost = 2 * fee_rate + 2 * (spread_bps + slippage_bps) / 10,000`.
- The replay default cost model is fee rate `0.001`, spread `2.0` bps, and slippage `1.0` bps. The factoring threshold is `0.60`.
- No frontend threshold/default change is supported by the evidence.

Implementation and regression lineage:

- Calibration contract repair: commit `6660ba893d054a5e380363938ffc36e5c4dbc835`; parent handoff reports exact-regime precedence, explicit unknown fallback, ambiguity handling, and retained boundary/held/missing-diagnostic coverage.
- Focused regression fixture lineage: commit `2aedbce2efce8459f70fbf034d8a909edfe9c9da`; parent handoff reports known-good versus known-bad ranking, held/identity fallback, thresholds, fees, directional profitability, missing diagnostics, and negative-expectancy protection.
- Offline ablation harness: commit `4ef9e2153c60a28935ed91f75d2624a2f3aa4d6b`, `tools/replay_diagnostic_ablation.py` and `data/replay/diagnostic_ablation_fixture.jsonl`.

## Reproduced offline ablation

Command reproduced from harness commit `4ef9e2153c60a28935ed91f75d2624a2f3aa4d6b` in an isolated temporary directory:

    python tools/replay_diagnostic_ablation.py --input data/replay/diagnostic_ablation_fixture.jsonl --json-out result.json --markdown-out result.md

Observed result:

- Input: 27 JSONL decisions, timestamp-ordered but synthetic; 13 strategy families, each with buy and sell cases.
- Modes: `disabled`, `report-only`, and `factored`; all used the same cost model.
- Buy cases: 13/13 executed in every mode; fee-adjusted expectancy was approximately `0.017400` per trade.
- Report-only sell cases: 13/13 executed; expectancy was approximately `0.007400`, except EMA at approximately `0.007015`.
- Factored sell cases: 13/13 blocked; factored expectancy, average win, average loss, and profit factor are null because there are no executed observations.
- Factored mode produced 13 meaningful block deltas, one for each sell case. This demonstrates the unavailable/under-threshold fail-closed contract, not predictive improvement.
- Maximum drawdown was `0.000000` in this one-observation-per-group fixture. This is not a market drawdown estimate.
- Average loss and profit factor were null in every group because the fixture contains no executed losing trade. This is insufficient to assess loss protection.
- The replay emitted `live_orders_enabled: false`; no exchange, account, order, or runtime path was invoked.

Generated replay output hashes for provenance:

- `result.json`: SHA-256 `144259bce450ed3d6490461a5e4f3a47f1d9c55817da6339e733ba7e4d20d590`
- `result.md`: SHA-256 `4e60b4cf865f6b5ffda26bea4a877053fc4c2cbef74aac8d441d9dfe02112931`

## Walk-forward acceptance matrix

| Criterion | Evidence | Decision |
|---|---|---|
| Chronological train/validation/test folds | No split-ready historical/live-parity outcome dataset | Unavailable; defer |
| Per-strategy and side monotonicity | One synthetic observation per strategy/side; no ordered outcome buckets | Unavailable; defer |
| Fee-adjusted expectancy improvement | Ablation shows cost arithmetic and blocking only; no candidate indicator mapping | Unavailable; defer |
| Average win and average loss | Average win is positive in the smoke rows; no executed losses exist | Insufficient; defer |
| Drawdown improvement | All groups contain one observation and report zero drawdown | Insufficient; defer |
| Combined strength plus profitability diagnostic | Factoring blocks unavailable/low-score sells but does not establish incremental predictive value | Safe gate demonstrated; predictive lift unavailable |
| Negative high-strength expectancy | No realized high-strength outcome bucket exists | Cannot certify; reject promotion |
| Objective improvement in at least 4 of 5 folds | No folds | Not run; reject promotion |
| 95% confidence interval / practical margin | No repeated outcome sample | Not estimable; reject promotion |
| Frontend/default consistency | No supported user-facing threshold change | Existing defaults retained |

## Per-strategy disposition

| Strategy | Formula disposition | Evidence disposition |
|---|---|---|
| SMA | Preserve current normalized-gap signal strength; no fitted remapping | Defer: no symbol/regime/holding-period outcome buckets |
| EMA | Preserve current normalized-gap signal strength; no fitted remapping | Defer: no outcome population; smoke sell expectancy differs slightly |
| RSI | Preserve threshold-distance semantics | Defer: no reversal/regime stability evidence |
| Bollinger | Preserve band-distance/z-score semantics | Defer: no volatility-regime evidence |
| MACD | Preserve crossover semantics | Defer: no trend/holding-period evidence |
| Stochastic | Preserve threshold/crossover semantics | Defer: no range/trend evidence |
| Fibonacci | Preserve level/proximity semantics; do not interpret ordinal level as probability | Defer: no level/proximity outcome evidence |
| DCA | No indicator-strength calibration | Baseline/deferred from this scope |
| Buy and Hold | No indicator-strength calibration | Baseline/deferred from this scope |
| Order Book | Keep separate from generic indicator mapping | Requires order-book/recent-trade outcome data |
| ML / ML enhanced order book | Keep separate from generic indicator mapping | Requires model/version and parity outcome data |

## Regression and CI evidence

The focused regression coverage is reported by the upstream implementation/verifier handoffs, including boundary values, fees, regimes, holding periods, missing diagnostics, held mappings, exact-versus-unknown fallback, ambiguity, and negative fee-adjusted expectancy protection. The latest reported exact-SHA remote Docker Build Validation for the focused fixture lineage is run `33022975990`, matching head SHA `2aedbce2efce8459f70fbf034d8a909edfe9c9da`, with all six required jobs successful:

- Build C++ Backend (amd64): success
- Build C++ Backend (arm64): success
- Build Frontend (amd64): success
- Build Frontend (arm64): success
- Publish C++ Backend manifest: success
- Publish Frontend manifest: success

This closeout task's assigned branch is the pre-artifact base (`ded76aa07dac3a44e17be3bc27e6b1354392cc48`); the report deliberately cites upstream immutable commit/run evidence rather than claiming that this branch executed those tests. The parent implementation handoffs also state that local builds/tests were not run under the repository's remote-CI-only policy. The offline Python replay above was run independently from the committed harness because it is a deterministic, non-build evidence probe and performs no live action.

## Required future rerun

A calibration promotion requires a new, versioned, read-only paper/live-parity dataset with signal and intent IDs; symbol and selected-universe provenance; raw indicator distance and emitted strength; strategy, side, regime, holding period; entry/exit timestamps; gross PnL; fees, spread, slippage; diagnostic availability and value; fill/block reason; and formula/version provenance. Freeze the bucket definitions and candidate before evaluation, fit only on train, select on validation, and report untouched test results over five chronological folds. Publish per-fold and aggregate expectancy, average win/loss, drawdown, profit factor, monotonicity, sample counts, confidence intervals, and incremental comparisons against raw distance. Keep a candidate rejected when high-strength fee-adjusted expectancy is systematically negative, average-loss magnitude is materially worse, or the combined diagnostic fails the pre-registered objective gates.

Safety: no live orders, account mutation, deployment, schema mutation, secret access, or selected-universe change was performed.
