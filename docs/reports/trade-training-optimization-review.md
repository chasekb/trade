# Trade Training Optimization Review

Date: 2026-06-19

## Scope
This review covers the trade ML and execution path that feeds simulated trading recommendations and model training:
- `src/ml/ModelTrainer.cpp`
- `src/ml/DataCollector.cpp`
- `src/ml/FeatureEngineer.cpp`
- `src/ml/Metrics.cpp`
- `src/trading/TradingStatsService.cpp`

The goal is to turn the executed-trade review backlog item into concrete training optimizations that can be actioned in follow-up work.

## What the current implementation is doing well
- Training data is persisted and batched via `DataCollector::sync_training_inputs()` and `extract_training_pairs_batch()`.
- `FeatureEngineer` maintains a transformer-ready rolling sequence window and feature history.
- `ModelTrainer` already records trading-oriented metrics such as Sharpe ratio and profit factor.
- `TradingStatsService` computes the same core P&L metrics for trade evaluation.

## Gaps found in the current training path

### 1) Evaluation is not time-aware
`ModelTrainer::train()` shuffles the full paired dataset before the train/test split (`src/ml/ModelTrainer.cpp:362-370`).
That is fine for i.i.d. data, but trade signal data is time series data. Random splitting can leak future regimes into the training set and make the reported metrics look better than live performance.

### 2) Training data is label-driven, but regime segmentation is absent
`DataCollector` batches matched signals and trades, but the trainer currently treats the result as a single population. There is no explicit regime segmentation by volatility, liquidity, spread, symbol class, or session time.

### 3) Feature engineering is strong but not yet tuned by outcome cohort
`FeatureEngineer` builds a wide rolling feature stack and transformer sequence window, but there is no visible feedback loop tying feature usefulness back to executed trade cohorts.

### 4) Metrics are computed, but not used for optimization feedback
`Metrics.cpp` provides the core P&L and classification metrics, yet there is no documented optimization loop that uses these metrics to prune features, adjust thresholds, or tune position sizing.

## Recommended optimizations

### P0: Switch model validation to walk-forward / time-series splits
Replace the random train/test split with a chronological split or rolling walk-forward validation.
Benefits:
- Prevents lookahead bias
- Produces live-like validation numbers
- Makes model comparisons across runs more trustworthy

Suggested implementation steps:
1. Keep the existing batch extraction logic.
2. Sort or preserve samples by timestamp.
3. Split by time blocks instead of shuffling the entire dataset.
4. Report per-fold metrics, then average them.

### P1: Add execution-regime cohorts
Bucket training samples by simple execution regimes, then compare metrics by cohort:
- spread percentile
- order-book imbalance buckets
- symbol liquidity tier
- volatility bucket
- session/time-of-day bucket

This will show which trade patterns are actually profitable and which ones should be suppressed or down-weighted.

### P1: Use executed trade feedback to tune position sizing
Use realized trade outcomes and fees to tune the position sizing policy instead of only the classification threshold. In practice this means:
- reducing size on low-confidence or high-spread setups
- increasing size only when recent cohort-level Sharpe/profit factor is stable
- capping risk when drawdown in the current regime is widening

### P2: Add feature ablation / importance tracking
Run periodic ablation or importance tracking on the current feature stack so that the wide `FeatureEngineer` output can be pruned over time.
Target outcomes:
- fewer noisy features
- lower inference latency
- more stable retraining

### P2: Persist cohort-level metrics alongside model metrics
Store the following with each training run:
- regime bucket
- feature set version
- validation split strategy
- profit factor
- Sharpe ratio
- win rate
- max drawdown

That makes later optimization and rollback decisions much easier.

## Recommended next implementation slice
1. Add a time-aware validation mode to `ModelTrainer`.
2. Emit cohort metrics per regime bucket.
3. Save a feature importance / ablation artifact with each training run.
4. Tune position sizing rules using the cohort metrics instead of a single global threshold.

## Notes
These recommendations are deliberately scoped to the code paths that already exist in the repo. They do not require a new ML stack; they just make the current pipeline more trustworthy and more responsive to actual executed-trade outcomes.
