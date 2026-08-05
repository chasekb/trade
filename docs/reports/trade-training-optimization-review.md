# Trade Training Optimization Review

Date: 2026-08-05
Backlog item: `TRADE-BL-0002 — Review trade data and produce training optimization plan`

## Scope and closeout position

This report reviews the current C++ ML/training and trade-outcome data paths and turns the remaining training-improvement work into prioritized, measurable experiments. It is a planning/review closeout artifact, not a local training run.

No local Docker/backend build was run. No live orders were placed. No credentials or local `.env` values were read.

Primary source paths inspected:

- `src/ml/DataCollector.cpp`
- `src/ml/ModelTrainer.cpp`
- `src/ml/ExecutionCohorts.cpp`
- `src/ml/FeatureEngineer.cpp`
- `include/ml/ModelTrainer.hpp`
- `include/ml/Types.hpp`
- `src/api/PredictController.cpp`
- `docs/STRATEGY_OBJECTIVE.md`
- `docs/reports/trade-strategy-objective-review-2026-08-01.md`
- `docs/reports/non-orderbook-diagnostics-closeout-2026-08-05.md`

The objective used for all recommendations is the repository objective: maximize risk-adjusted expectancy in the live trading environment, not raw signal count.

## Optimization metrics

Every proposed experiment must report the following before/after metrics on the same time window and symbol universe:

1. Net PnL after fees.
2. Profit factor.
3. Sharpe ratio.
4. Max drawdown in dollars.
5. Win rate as a 0–100 percentage.
6. Trade expectancy: `net_pnl / closed_trade_count`.
7. Trade frequency and fill/blocked-intent counts.
8. Average realized win.
9. Average realized loss.
10. Total fees and fee share of gross profit.
11. Spread/slippage hurdle where available.
12. Positive/negative/zero PnL trade counts.
13. Cohort metrics by spread/liquidity/imbalance/volatility/session regime.

Stop/rollback rule for all experiments: reject or roll back any change that improves classification accuracy while worsening net expectancy, average loss, max drawdown, or profit factor after fees/spread/slippage.

## Current data path inventory

### Trade and signal sources

`DataCollector::ensure_training_inputs_table()` creates or verifies:

- `individual_trades` with trade-level `pnl`, `fees`, `win_probability`, `expected_return`, `model_confidence`, and `trade_type` (`src/ml/DataCollector.cpp:41-60`).
- `ml_training_inputs` with signal/trade timestamps, order-book features, previous ML diagnostics, side, size, price, PnL, and fees (`src/ml/DataCollector.cpp:69-100`).

`DataCollector` also installs a trigger that joins each new trade to the most recent same-symbol order-book signal in the prior 300 seconds when no intervening trade exists (`src/ml/DataCollector.cpp:130-204`). `sync_training_inputs()` performs the same general matching in batch mode (`src/ml/DataCollector.cpp:217-356`).

### Training/evaluation path

The old June report said non-batch evaluation used a shuffled split. The current code has since improved:

- `ModelTrainer::train()` sorts paired samples chronologically before non-batch evaluation (`src/ml/ModelTrainer.cpp:377`).
- It creates walk-forward folds via `build_walk_forward_folds(...)` and records `validation_strategy` as `walk_forward` or `chronological_holdout` (`src/ml/ModelTrainer.cpp:379-435`).
- It records `feature_set_version`, `walk_forward_folds`, `feature_importance`, and `cohort_metrics` (`include/ml/ModelTrainer.hpp:39-52`, `src/ml/ModelTrainer.cpp:429-435`).
- Streaming batch training records `validation_strategy = streaming_batch` and cohort metrics while consuming all rows in batches (`src/ml/ModelTrainer.cpp:96-194`, `206-258`, `270-347`).

### Cohort path

`ExecutionCohorts.cpp` already buckets validation outcomes by:

- liquidity bucket;
- spread bucket;
- order-book imbalance bucket;
- volatility bucket;
- UTC session bucket.

It reports sample count, winners/losers, win rate, average PnL, profit factor, Sharpe, max drawdown, average spread, and average volatility (`src/ml/ExecutionCohorts.cpp:83-211`).

## Data validation findings and required checks

The code now has a durable training-input table and time-aware validation, but training jobs still need explicit data-quality gates before their metrics should drive live strategy decisions.

### Leakage checks

Current risk:

- Matching uses a 300-second future trade window after a signal. That is appropriate for supervised label construction, but validation must never allow later signals/trades from the same period into the training side of a fold.
- Walk-forward splitting reduces this risk, but the closeout report for each training experiment must verify fold boundaries by timestamp.

Required experiment check:

- For every fold: `max(train.trade_timestamp) < min(test.signal_timestamp)` or an explicitly documented embargo/gap around the label horizon.
- Stop condition: reject a model if validation metrics degrade materially when an embargo equal to the 300-second matching horizon is added.

### Duplicate and stale-match checks

Current risk:

- `signal_id` is the primary key in `ml_training_inputs`; conflict handling updates to the earliest trade timestamp. This protects against duplicate signal rows, but a training report should still quantify duplicate candidate matches.
- The trigger and batch sync both use the same-symbol 300-second window. A stale signal can still be paired with a trade if no fresher signal exists.

Required experiment check:

- Count candidate signal→trade matches by age bucket: `0–30s`, `31–120s`, `121–300s`.
- Segment validation metrics by match-age bucket.
- Stop condition: if `121–300s` matches have materially worse expectancy or dominate the sample, either add a freshness feature/gate or exclude them from training.

### Missing/invalid value checks

Current risk:

- `ml_training_inputs` defaults many feature columns to zero. Zero can mean a real value or missing data, especially for volume, walls, previous ML diagnostics, and volatility.

Required experiment check:

- Report missing/default rates for every feature column.
- Add missingness indicators for columns where zero is ambiguous.
- Stop condition: reject feature additions where missing/default rows dominate model importance but do not improve walk-forward expectancy.

### Timestamp/regime coverage checks

Current risk:

- Cohort labels cover session/regime, but training run artifacts need sample-count thresholds so sparse regimes are not overfit.

Required experiment check:

- Report sample counts by symbol, liquidity, spread, volatility, imbalance, session, and trade_type.
- Mark cohorts below a minimum sample threshold as insufficient evidence.
- Stop condition: do not promote strategy/risk changes based on cohorts with insufficient sample counts.

## Performance segmentation plan

Each model-training experiment should publish a table with these segments:

| Segment | Why it matters | Required metrics |
| --- | --- | --- |
| Symbol | Avoid one asset dominating or masking losses | sample count, net PnL, avg win/loss, expectancy, profit factor, drawdown |
| Strategy | Distinguish order-book alpha from indicator/DCA/baseline rows | same as above plus diagnostic factor counts |
| Trade type | Separate live, simulated, and future live-parity-paper evidence | same as above; live claims require live/live-parity only |
| Spread bucket | Fees/spread can erase small edge | net expectancy after required edge |
| Imbalance bucket | Order-book model currently leans heavily on imbalance | monotonicity of imbalance vs realized PnL |
| Volatility bucket | High volatility can raise average win and average loss | avg win/loss, drawdown, blocked intents |
| UTC session | Crypto liquidity/regime varies intraday | expectancy and slippage by session |
| Match age | Stale signal labels may be noisy | expectancy by signal→trade delay |
| Expected-return bucket | Model edge should be directional and monotonic | avg win/loss and pass/fail gate outcomes |
| Diagnostic factor | Connect training to execution blockers | no-signal, weak, missing expected return, negative fee-adjusted edge, account/exchange blockers |

## Prioritized training/model recommendations

### P0 — Add an embargo/freshness validation mode to walk-forward training

Current state:

- Chronological/walk-forward validation exists.
- Label matching uses a 300-second post-signal horizon.

Recommendation:

- Add a fold embargo at least as large as the label horizon between train and test periods.
- Add a training-run field such as `validation_embargo_seconds`.
- Report metrics with and without embargo for the same dataset.

Expected lift/risk reduction:

- Reduces lookahead leakage risk and makes validation less likely to overstate live expectancy.
- Expected effect is lower but more trustworthy validation performance.

Experiment plan:

1. Add embargo-aware fold construction.
2. Run the same model config with current walk-forward and embargoed walk-forward.
3. Compare net expectancy, profit factor, Sharpe, drawdown, and cohort stability.

Rollback/stop condition:

- Do not promote models that only pass without embargo.
- If embargo leaves too few samples, leave the model inactive and collect more live/live-parity data.

Traceable follow-up:

- New implementation task against `src/ml/ModelTrainer.cpp` and tests around fold construction.

### P0 — Add a training data-quality audit artifact before every model package is accepted

Current state:

- Training inputs are persisted, but quality checks are not surfaced as an acceptance artifact.

Recommendation:

- Emit a JSON or markdown audit artifact per training run with counts for rows, duplicates, missing/default feature rates, stale match buckets, symbol/regime coverage, class balance, PnL distribution, and fee share.

Expected lift/risk reduction:

- Prevents deploying models trained on stale, sparse, duplicate, or missing-heavy data.
- Improves rollback decisions because bad data and bad model behavior are separated.

Experiment plan:

1. Add a `TrainingDataAudit` structure.
2. Compute it from `ml_training_inputs` before model training.
3. Fail or warn based on thresholds.
4. Surface audit results in `/api/ml/performance` or model metadata.

Rollback/stop condition:

- Do not activate a model if required audit gates fail.
- Treat a missing audit artifact as a failed training run for live deployment.

Traceable follow-up:

- New implementation task against `src/ml/DataCollector.cpp`, `src/ml/ModelTrainer.cpp`, `include/ml/ModelTrainer.hpp`, and API serialization in `src/api/PredictController.cpp`.

### P1 — Calibrate order-book expected-return scale by realized fee-adjusted outcomes

Current state:

- Order-book strategies have directional fee/spread/slippage gates.
- Heuristic fallback uses an expected-return scale parameter and the tests prove strong fallback signals can clear the default hurdle.

Recommendation:

- Fit/calibrate the heuristic expected-return scale from realized outcomes by strength and spread bucket rather than using one global fixed scale.

Expected lift/risk reduction:

- Reduces false-positive trades where strength looks high but net fee-adjusted expectancy is weak.
- Expected to improve average loss and profit factor more than raw win rate.

Experiment plan:

1. Bucket historical/live-parity order-book rows by strength, spread, and expected-return bucket.
2. Estimate realized average PnL and fee-adjusted expectancy per bucket.
3. Choose a conservative scale that only clears the profitability gate where realized net expectancy is positive.
4. Validate on walk-forward folds.

Rollback/stop condition:

- Reject if trade count increases but profit factor, average loss, or drawdown worsens.
- Reject if a positive expected-return bucket is not monotonic with realized expectancy.

Traceable follow-up:

- Existing `TRADE-BL-0008` and `TRADE-BL-0016`.

### P1 — Use cohort metrics to tune position sizing, not only signal admission

Current state:

- `PositionSizingPolicy` accepts signal strength, win probability, expected return, confidence, spread, volatility, and drawdown inputs.
- Cohort metrics are computed but not yet used as a first-class sizing feedback loop.

Recommendation:

- Add a report-only cohort risk multiplier first, then test active sizing only after it improves walk-forward objective metrics.

Expected lift/risk reduction:

- Should reduce average loss and drawdown in high-spread/high-volatility/low-liquidity cohorts without disabling all trading.

Experiment plan:

1. Compute suggested multiplier per cohort from profit factor, average PnL, drawdown, and sample count.
2. Run report-only comparisons against actual fills.
3. Promote only cohorts with enough samples and stable improvement.

Rollback/stop condition:

- Reject if the multiplier increases concentration risk or worsens drawdown.
- Reject if a sparse cohort drives a large sizing change.

Traceable follow-up:

- Existing `TRADE-BL-0016`; likely code paths `src/trading/PositionSizingPolicy.cpp`, `src/ml/ExecutionCohorts.cpp`, and strategy execution services.

### P1 — Separate live, simulated, and live-parity-paper training populations

Current state:

- `individual_trades.trade_type` exists.
- Simulated trading can include synthetic behavior that is not Coinbase spot live parity.

Recommendation:

- Make `trade_type` a mandatory training/reporting segment.
- Do not train live-deployment models from synthetic simulated rows unless they are explicitly labeled and weighted as auxiliary data.
- Prefer future live-parity-paper rows for Coinbase-safe strategy tuning.

Expected lift/risk reduction:

- Prevents synthetic short or unrealistic fill behavior from contaminating live model validation.

Experiment plan:

1. Report metrics separately for `live`, `simulated`, and future `live_parity_paper` rows.
2. Train/evaluate with live-only, live+live-parity, and all-data variants.
3. Compare objective metrics and blocker rates.

Rollback/stop condition:

- Reject any model whose live/live-parity subset underperforms despite all-data validation looking good.

Traceable follow-up:

- Existing `TRADE-BL-0006`.

### P2 — Add feature ablation and stable importance reporting

Current state:

- `compute_feature_importance(...)` exists and training metrics expose `feature_importance`.
- The trainer baselines are still simple in several paths: random forest is a majority-class baseline, transformer path is a linear regression over imbalance, and XGBoost-style path predicts by imbalance sign.

Recommendation:

- Treat feature importance as a stability and ablation artifact, not as proof of predictive quality.
- Add walk-forward ablations for the strongest feature families: imbalance, spread, volume/walls, momentum/volatility, previous ML diagnostics.

Expected lift/risk reduction:

- Removes noisy features and identifies whether the current imbalance-heavy baseline is actually sufficient.

Experiment plan:

1. Train with all features.
2. Drop one feature family at a time.
3. Compare expectancy/profit factor/drawdown, not just accuracy/MSE.
4. Keep features only if they improve objective metrics across folds.

Rollback/stop condition:

- Reject a feature family if it improves accuracy while worsening expectancy or drawdown.

Traceable follow-up:

- New task under ML training/model evaluation.

### P2 — Promote baseline-vs-active strategy benchmarking

Current state:

- DCA and buy-and-hold are now explicitly diagnostic-unavailable rather than misrepresented as alpha forecasts.

Recommendation:

- Use DCA and buy-and-hold as benchmark curves, not high-confidence model targets.
- Every active strategy report should compare against those baselines on the same capital, time window, and symbols.

Expected lift/risk reduction:

- Prevents active strategies from being accepted when they underperform simple allocation after fees and drawdown.

Experiment plan:

1. Use the strategy expectancy harness to produce baseline rows for DCA/buy-and-hold and active strategies.
2. Compare risk-adjusted expectancy and drawdown.
3. Promote active strategies only when they beat baselines on the target objective.

Rollback/stop condition:

- Reject active strategy parameter changes that underperform baselines after fees/spread/slippage.

Traceable follow-up:

- Existing `TRADE-BL-0013` and `TRADE-BL-0016`.

## Recommended backlog follow-ups

The current report closes the review/planning item. Implementation should be split into these runnable tasks:

1. Embargo-aware walk-forward validation and tests.
2. Training data-quality audit artifact and API/report serialization.
3. Order-book expected-return scale calibration from realized fee-adjusted outcomes.
4. Report-only cohort risk multiplier before active position-sizing changes.
5. Live/live-parity/simulated training population separation.
6. Feature-family ablation report.
7. Baseline-vs-active strategy benchmark report.

Each task should require exact pushed-SHA Docker Build Validation before closeout if it changes code.

## Final closeout summary

`TRADE-BL-0002` asked for a written report with prioritized training optimizations and rationale, expected lift/risk reduction, experiment plans, rollback/stop conditions, and traceability to current code/data paths.

This report satisfies that review/planning closeout by:

- defining the optimization metrics;
- reviewing current training/evaluation data paths;
- checking the current code against stale/leakage/missing/duplicate/timestamp/regime concerns;
- segmenting performance requirements by symbol, strategy, regime, time, holding/match age, and fee/slippage impact;
- providing prioritized P0/P1/P2 recommendations;
- adding expected lift/risk reduction, experiment plan, rollback/stop condition, and code/backlog traceability for each recommendation.
