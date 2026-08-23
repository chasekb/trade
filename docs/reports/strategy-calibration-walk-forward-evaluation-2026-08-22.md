# Strategy calibration walk-forward evaluation

Date: 2026-08-22
Status: BLOCKED — no calibration mappings or outcome dataset are present in this checkout

## Executive result

No strategy has enough evidence for a mapping change. The requested baseline-versus-implemented walk-forward comparison cannot be executed honestly because the repository contains neither (a) a fitted/implemented ranking mapping distinct from the current signal-strength formulas nor (b) historical or live-parity paper outcomes with timestamps, symbols, regimes, holding periods, and fee assumptions.

All nine supported indicator-family strategies are therefore deferred: `sma`, `ema`, `rsi`, `bollinger`, `macd`, `stochastic`, `fibonacci`, `dca`, and `buyandhold`. The `orderbook` path is also not evaluable through this harness because it is handled by the caller rather than `evaluateStrategySignal`.

No objective delta, monotonicity score, fee-adjusted expectancy improvement, or incremental predictive-value claim is reported. A missing measurement is not treated as a zero improvement.

## Repository evidence

- `src/trading/StrategySignal.cpp` emits strength from indicator distance/threshold heuristics. The visible formulas include normalized moving-average gap, RSI threshold distance, Bollinger z-score, MACD crossover gap, stochastic threshold distance, and fixed strength for DCA/buy-and-hold.
- `include/trading/StrategySignal.hpp` defines profitability diagnostics, but the signal evaluator does not emit an outcome-calibrated ranking mapping or a strategy-specific fitted coefficient set.
- `src/trading/StrategyExpectancyHarness.cpp` provides deterministic smoke fixtures and aggregate expectancy metrics. Its default fixture set has one positive-edge fixture per supported strategy plus two fee-negative SMA/EMA regression fixtures; it is not a chronological replay dataset and has no symbol, regime, holding-period, or split metadata.
- `docs/reports/strategy-expectancy-harness-closeout-2026-08-03.md` explicitly describes the current fixtures as deterministic contract/regression fixtures and states that historical/live-parity replay is future work.
- `docs/reports/trade-strategy-objective-review-2026-08-01.md` classifies the indicator strategies as needing calibration and notes that realized outcome evidence is absent.

## Required evaluation versus available evidence

| Requirement | Available | Result |
|---|---:|---|
| Strictly ordered walk-forward splits | No timestamped replay rows or split builder for strategy outcomes | Not run |
| Baseline mapping | Current heuristic signal strength only | Inventory only |
| Implemented ranking mapping | No distinct fitted/implemented mapping found | Not available |
| Buckets by emitted strength | One or a few synthetic rows, no outcome distribution | Insufficient |
| Buckets by symbol | No symbol field in `StrategyExpectancyFixture` | Not possible |
| Buckets by market regime | No regime field or labeling contract | Not possible |
| Buckets by holding period | No entry/exit timestamps or holding-period field | Not possible |
| Fee assumptions | Fixed fixture-level fee/slippage inputs exist | Smoke-gate only |
| Average win/loss, drawdown, expectancy | Harness aggregate metrics exist | Not walk-forward evidence |
| Monotonicity | No ordered strength/outcome buckets | Not computable |
| Incremental value over raw indicator distance | No paired ablation dataset/mapping | Not computable |

## Strategy disposition

| Strategy | Evidence status | Decision | Reason |
|---|---|---|---|
| sma | Smoke fixture only | Defer | No realized outcome buckets or fitted mapping |
| ema | Smoke fixture only | Defer | No realized outcome buckets or fitted mapping |
| rsi | Smoke fixture only | Defer | No realized outcome buckets or fitted mapping |
| bollinger | Smoke fixture only | Defer | No realized outcome buckets or fitted mapping |
| macd | Smoke fixture only | Defer | No realized outcome buckets or fitted mapping |
| stochastic | Smoke fixture only | Defer | No realized outcome buckets or fitted mapping |
| fibonacci | Smoke fixture only | Defer | No realized outcome buckets or fitted mapping |
| dca | Smoke fixture only | Defer | No holding-period/outcome replay evidence |
| buyandhold | Smoke fixture only | Defer | No holding-period/outcome replay evidence |
| orderbook | Outside harness scope | Defer | Requires separate live/simulated order-book outcome dataset |

## Strength versus profitability diagnostics

The safe decision is to keep indicator strength and expected-return/profitability diagnostics separate until paired out-of-sample evidence exists. Strength describes the signal's technical-distance magnitude; the diagnostic applies fees, spread, slippage, and expected return to determine actionability. Combining them now would create an unsupported ranking change and could increase live execution without evidence that average win, average loss, drawdown, or expectancy improves.

The existing harness's fee-negative fixtures support only the narrow safety behavior that generated signals can be blocked when the fee-adjusted expected edge is negative. They do not establish calibration quality, monotonicity, or predictive lift.

## Reproducibility artifact

Machine-readable evaluation status is saved at:

- `docs/reports/artifacts/strategy-calibration-walk-forward-evaluation-2026-08-22.json`

The artifact records the supported strategy inventory, unavailable dimensions, disposition, and exact source paths used for this assessment. Once timestamped live-parity paper or historical rows and a distinct candidate mapping exist, the same report contract should be rerun with chronological train/test folds and paired baseline/candidate rows.

## Closeout criteria for a future rerun

Before any strategy is promoted, the rerun must provide:

1. A timestamp-ordered dataset with strategy, symbol, emitted strength, raw indicator-distance value, regime, entry/exit timestamps, realized gross PnL, fees, spread, slippage, and blocker/action fields.
2. A declared minimum sample threshold per strategy and bucket, plus out-of-sample chronological folds with no future leakage.
3. Paired baseline and candidate mapping outputs on identical rows.
4. Monotonicity, fee-adjusted expectancy, average win, average loss, max drawdown, profit factor, and combined-objective results per fold and aggregate.
5. An ablation comparing raw indicator distance with profitability diagnostics, including sample counts and stability/confidence notes.
6. Deterministic regression fixtures and remote CI evidence for any mapping or test changes.

## Verification note

No local build or test command was run. This task was limited to repository inspection and evidence/artifact generation under the remote-CI-only policy. `git diff --check` passed before the report was written.
