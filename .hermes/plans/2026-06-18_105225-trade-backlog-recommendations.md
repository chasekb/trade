# Trade Backlog Recommendations: Statistics Accuracy and Training Optimization

> **For Hermes:** Use subagent-driven-development skill to implement these tasks task-by-task if the backlog items are approved.

**Goal:** Create two prioritized trade-project backlog recommendations: (1) verify simulated trading statistics widget calculations for trades and portfolios are accurate, and (2) review trade data to recommend training optimizations that improve trading performance.

**Architecture:** Treat these as two separate backlog items under the Trade project so they can be executed independently but validated against a shared source of truth for trade history and portfolio state. The first item is a correctness audit of backend calculations and frontend rendering contracts. The second item is a data/ML analysis effort that produces measurable training recommendations, evaluation criteria, and experiment proposals.

**Tech Stack:** C++ backend trading services, React/Next.js dashboard components, JSON API contracts, ML/training metrics, trade-history datasets, regression tests, and browser-based UI verification.

---

## Recommendation 1: Simulated Trading Statistics Calculation Audit

**Priority:** P0 / high

**Why this is first:** If statistics are wrong, the trading dashboard cannot be trusted. This is a foundation-level correctness issue that should be resolved before any downstream analysis or optimization work.

**Objective:** Review and validate every simulated trading statistic shown in the widget, including trade-level and portfolio-level calculations, so the UI reflects accurate values from the backend and remains stable across active, empty, and partially populated states.

**Likely files / areas to inspect:**
- `src/trading/SimulatedTradingService.cpp`
- `include/trading/SimulatedTradingService.hpp`
- `src/trading/TradingStatsService.cpp`
- `include/trading/TradingStatsService.hpp`
- `src/ml/Metrics.hpp`
- `frontend/components/dashboard/SimulatedTradingPanel.tsx`
- Any regression tests covering simulated trading status, stats, or portfolio summaries

### Execution Checklist

#### Discovery and reconciliation
- [ ] Inventory every displayed metric in the simulated trading widget.
- [ ] Trace each metric back to the backend function or API response field that produces it.
- [ ] Confirm the widget source for trade counts, total PnL, net PnL, win rate, average win/loss, best/worst trade, profit factor, Sharpe ratio, drawdown, portfolio value, open positions, and recent trades.
- [ ] Compare trade-level calculations against a known-good sample of historical trades.
- [ ] Compare portfolio-level calculations against a reference portfolio snapshot or replayable dataset.
- [ ] Identify any frontend fallbacks that could hide a backend mismatch.
- [ ] Identify any backend defaults that could produce misleading zeros or blank values.

#### Calculation validation
- [ ] Verify that the sign conventions for PnL, fees, losses, and drawdown are consistent across backend and frontend.
- [ ] Verify that all averaging logic uses the correct denominator and excludes/ includes zero-values intentionally.
- [ ] Verify that portfolio totals, recent trades, and summary statistics are derived from the same time window or document the intended difference.
- [ ] Verify that time-based metrics such as "trades today" and "last trade time" are computed in a clearly defined timezone.
- [ ] Verify that the widget does not double-count trades when both `trades` and `recent_trades` fields are present.

#### Test coverage
- [ ] Add or update backend tests for metric calculations using a fixed trade fixture.
- [ ] Add or update backend tests for portfolio summary generation.
- [ ] Add frontend tests for widget rendering with `trades`, `recent_trades`, and empty portfolio states.
- [ ] Add a regression test for the exact response shape the widget expects.
- [ ] Validate the UI against seeded data and confirm the displayed values match the reference calculations.

#### Verification and review
- [ ] Recompute key metrics independently on the same trade fixture and compare results.
- [ ] Confirm the dashboard renders consistently after refresh and after switching tabs.
- [ ] Confirm that no metric silently disappears when one upstream field is missing.
- [ ] Confirm that visible loading or empty states exist when no data is available.

### Closeout Criteria
- [ ] Every displayed simulated trading statistic matches a documented source-of-truth calculation.
- [ ] Trade-level metrics and portfolio-level metrics are internally consistent.
- [ ] The frontend no longer depends on ambiguous field names without an explicit fallback policy.
- [ ] Regression tests cover the main calculation paths and pass in CI.
- [ ] The widget shows accurate values, clear empty states, or explicit loading states rather than misleading blanks.
- [ ] Any formula assumptions are documented in code comments or a short design note.

---

## Recommendation 2: Trade Data Review and Training Optimization Plan

**Priority:** P1 / high, after stats correctness is verified

**Why this is second:** Training recommendations are only useful if the underlying trade data and performance metrics are trustworthy. Once the stats audit is complete, the same validated data can support actionable model or strategy improvements.

**Objective:** Review recent and historical trade data to identify performance bottlenecks, data quality issues, and model/training changes that could improve trading performance in a measurable way.

**Likely files / areas to inspect:**
- Trade history tables / datasets used by the strategy or training pipeline
- ML feature generation code under `src/ml/` or adjacent analysis utilities
- Any evaluation scripts, notebooks, or batch jobs that compute strategy metrics
- Any experiment-tracking or reporting artifacts used by the project
- Backend trade export or summary endpoints that feed analysis workflows

### Execution Checklist

#### Data review and baseline definition
- [ ] Define the performance metrics that matter most for optimization: net PnL, profit factor, Sharpe ratio, max drawdown, win rate, expectancy, and trade frequency.
- [ ] Verify the training/evaluation dataset covers the intended market regimes and time periods.
- [ ] Check for data leakage, look-ahead bias, and label contamination.
- [ ] Check for missing values, duplicate rows, stale prices, or inconsistent timestamps.
- [ ] Segment results by symbol, strategy, market regime, time of day, and holding period.
- [ ] Establish a baseline performance report from the current model or strategy.

#### Diagnostic analysis
- [ ] Identify which trade cohorts are consistently profitable and which are consistently losing.
- [ ] Identify whether poor performance is driven by entry timing, exit timing, position sizing, or regime mismatch.
- [ ] Analyze whether fees, slippage, or oversized positions are eroding raw edge.
- [ ] Compare live or recent performance against backtest performance to spot overfitting.
- [ ] Review feature importance or model signals to find weak or redundant predictors.
- [ ] Check whether the current label definition aligns with the desired trading objective.

#### Optimization recommendations
- [ ] Recommend concrete feature changes: remove noisy features, add regime features, normalize unstable inputs, or add volatility/liquidity context.
- [ ] Recommend target changes if the current label does not correlate with realized profit.
- [ ] Recommend validation changes such as walk-forward evaluation, time-series cross-validation, or regime-aware splits.
- [ ] Recommend hyperparameter or loss-function changes if the current model is underfitting or overfitting.
- [ ] Recommend position-sizing or risk-control adjustments if raw signals are decent but drawdown is excessive.
- [ ] Prioritize the recommendations by estimated impact and implementation cost.

#### Output and review
- [ ] Produce a concise analysis report that names the highest-value changes first.
- [ ] Include the expected lift or risk reduction for each recommendation, even if approximate.
- [ ] Include a clear "do next" experiment list so the team can execute in order.
- [ ] Include a rollback or stop condition for experiments that worsen performance.
- [ ] Review the recommendations with the stats audit results so the analysis uses the corrected source of truth.

### Closeout Criteria
- [ ] A written report exists with prioritized training optimizations and rationale.
- [ ] The report includes the baseline performance and the metrics used to judge improvement.
- [ ] Data quality and leakage checks are explicitly documented.
- [ ] The top recommendations are specific enough to implement as follow-up backlog items.
- [ ] At least one recommended experiment has a measurable success criterion.
- [ ] The review is grounded in verified trade statistics, not unvalidated dashboard values.

---

## Recommended Delivery Order

1. Complete Recommendation 1 first so trade and portfolio statistics are trustworthy.
2. Use the corrected data and metric definitions from Recommendation 1 to inform Recommendation 2.
3. Convert the highest-value training optimizations into smaller implementation backlog items once the analysis is complete.

## Risk Notes

- If the widget is reading from multiple overlapping fields, it can silently display plausible-but-wrong values.
- If the training analysis uses a different metric definition than the dashboard, the team may optimize the wrong objective.
- If data quality issues are found, fix those before trusting any optimization conclusions.

## Tags

`trade`, `backlog`, `simulated-trading`, `statistics`, `portfolio`, `metrics`, `ml`, `training`, `performance`, `analysis`
