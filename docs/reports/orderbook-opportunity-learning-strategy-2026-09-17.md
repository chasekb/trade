# Order-Book Opportunity-Learning Strategy

Date: 2026-09-17

## Motivation

`ml_enhanced_orderbook`'s training data is restricted to order-book states that
(a) crossed the legacy raw-imbalance strength floor (`strength =
min(1, |imbalance| * 1.15) >= 0.22`) and (b) were matched to an executed trade
within a 300-second window (`DataCollector::sync_training_inputs`,
`fn_upsert_ml_training_inputs_from_trade` trigger). Every `order_book_signals`
row that did not clear that floor, or that cleared it but never led to a
trade (blocked intent, no capital, gate failure, etc.), is logged but never
becomes a training example. The model never sees the majority of order-book
states it operates over, including states that were, in hindsight, genuine
profit opportunities.

This report introduces `ml_orderbook_opportunity`, a new selectable strategy
(`frontend/types/trading.ts`, `StrategySelector.tsx`) trained on a
self-supervised label computed for **every** logged order-book state,
independent of whether a strategy would have signaled on it or whether a
trade followed.

## What changed

- `DataCollector::sync_opportunity_labels` (`src/ml/DataCollector.cpp`)
  labels every `order_book_signals` row using its own forward-looking
  mid-price return (observed from a later same-symbol row at least
  `horizon_seconds` ahead) minus the same fee/spread/slippage hurdle used by
  `trading::evaluateOrderBookProfitabilityGate`. The label computation itself
  (`compute_opportunity_label`, `include/ml/DataCollector.hpp`) takes only
  price/spread/fee inputs — no `signal_type` or `strength` — so it cannot be
  gated by whether a signal fired. Persisted to a new `ml_opportunity_labels`
  table, populated incrementally like `ml_training_inputs`.
- `ModelTrainer::train` (`src/ml/ModelTrainer.cpp`) accepts
  `TrainingConfig.training_source = "opportunity_labels"` and switches its
  sync/count/extract calls to the opportunity path; every existing call site
  (`train_random_forest`/`train_xgboost`/`train_transformer`, walk-forward
  folds, cohort metrics) is unchanged and consumes the same
  `(OrderBookFeatures, TradeOutcome)` pair shape it always has. Default
  (`"trade_outcomes"`) behavior for `ml_enhanced_orderbook`/`orderbook` is
  untouched.
- `/api/ml/train` (`src/api/PredictController.cpp`) accepts
  `training_source` and `opportunity_horizon_seconds` request fields.
  `ModelMetrics.training_source` is serialized so training runs/reports can
  tell the two populations apart.
- `LiveTradingService`/`SimulatedTradingService`: `ml_orderbook_opportunity`
  is an order-book strategy (`isOrderBookStrategy`) whose candidate
  admission does **not** require raw imbalance to clear the legacy 0.22
  strength floor — every tick is a candidate, with direction from imbalance
  sign. It shares the existing single active ONNX model manager with
  `ml_enhanced_orderbook` (train with `training_source=opportunity_labels`
  and activate that package to use it) rather than a second always-on model
  slot. The unchanged fee/spread/slippage profitability gate
  (`DiagnosticsContract::normalizeDiagnostics`,
  `evaluateOrderBookProfitabilityGate`) is the only thing that decides
  whether a candidate becomes an executable buy/sell — a lower/removed
  strength floor never bypasses that gate. `DiagnosticsContract.cpp`'s
  strategy allowlist (`resolveDiagnosticsMode`, `known_strategy`) was
  extended to recognize the new name; without that it would have failed
  closed as an unsupported strategy.
- Frontend: `StrategyConfigForm.tsx`'s ML Configuration panel (model
  select/train/activate) now also renders for `ml_orderbook_opportunity`,
  and its "Train New Model" action always requests
  `training_source=opportunity_labels` for that strategy so the UI path
  produces a model trained on the intended population without extra manual
  steps.

## Diagnostics factoring classification

Per `docs/STRATEGY_OBJECTIVE.md`'s diagnostics factoring contract,
`ml_orderbook_opportunity`'s expected-return diagnostic is `gate`: it blocks
or allows entry exactly like `orderbook`/`ml_enhanced_orderbook` today,
through the same shared `evaluateOrderBookProfitabilityGate` /
`DiagnosticsContract` path, unchanged fee/spread/slippage semantics,
directional (buy needs positive expected return, sell needs negative).

## Expected objective impact

- **Signal count**: expected to increase for this strategy specifically,
  because raw-imbalance-weak states are no longer discarded before the
  model/gate ever sees them. Per `docs/STRATEGY_OBJECTIVE.md`, that increase
  is not itself evidence of improvement — see evidence source below. It has
  **no effect** on `orderbook`/`ml_enhanced_orderbook` signal counts, which
  keep their existing threshold unchanged.
- **Average win / average loss / expectancy / profit factor / drawdown**:
  unknown direction until a model is actually trained on
  `ml_opportunity_labels` and evaluated — this report does not claim a
  result, only that the pipeline now makes the comparison possible. The
  hypothesis this strategy tests is that some of the states filtered out by
  the raw-imbalance floor have a genuine, model-detectable, cost-clearing
  edge from other features (spread, volume split, momentum) even without a
  strong imbalance; the opposite (those states are net noise) is an
  equally-expected outcome and would show as flat-or-worse expectancy on the
  opportunity-trained model relative to the trade-outcome-trained one on the
  same window.
- **Blocked intents / live-only exchange blockers**: unaffected — those
  checks (account readiness, minimum notional, spot-only, explicit
  live-order enablement, universe policy) sit downstream of signal
  generation and are untouched by this change.

## Evidence source

A fixed backtest/live-parity window comparing, on the same symbols and
capital: (a) `ml_enhanced_orderbook` with its existing trade-outcome-trained
model, against (b) `ml_orderbook_opportunity` with a model trained via
`training_source=opportunity_labels` over the same historical window,
reporting the full `docs/STRATEGY_OBJECTIVE.md` metric set (avg win/loss,
expectancy, profit factor, drawdown, blocked-intent counts) plus the
`ExecutionCohorts` segmentation already produced by `ModelTrainer`. Per the
training review's stop/rollback rule
(`docs/reports/trade-training-optimization-review.md`), reject or hold back
any model whose walk-forward metrics improve on paper but do not hold up
fee-adjusted on the live-parity/backtest evidence.

## Rollback / follow-up condition

- If `ml_orderbook_opportunity`'s trained model increases trade/signal count
  without improving or preserving expectancy, profit factor, and drawdown
  relative to `ml_enhanced_orderbook` on the same evidence window, do not
  promote it to a default and leave it available only as an explicit
  opt-in strategy for further data collection.
- The opportunity labels reuse the existing lazy-default convention for
  secondary features (walls, previous-ML lag features, `price_momentum`,
  `volatility` default to their table defaults rather than being parsed
  from `signal_data`), the same simplification `ml_training_inputs` already
  makes. `bid_ask_imbalance`, `spread_percent`, `bid_volume`/`ask_volume`
  (split from imbalance), `mid_price`, and `order_book_depth` are populated
  from the real `order_book_signals` columns, which is strictly better
  coverage than the existing trade-matched path's hardcoded defaults for
  those same fields. A follow-up item to parse `signal_data` for the
  remaining secondary features would improve both paths equally and is not
  required for this change to be safe to evaluate.
- Live-account safety, explicit user universe selection, secret handling,
  fail-closed exchange behavior, and no-unapproved-liquidation rules are
  unchanged: this change only affects order-book signal admission and
  training data source, never the exchange-blocker or account-safety paths.

## Verification performed

- `frontend`: `npx tsc --noEmit` and `npm run lint` show no new errors from
  this change; existing Jest suites touching order-book strategy behavior
  (`localSimulatedFallbackSignals`, `startTradingPayload`,
  `useTradingStrategyParameters`, `useLiveTrading`, `useTradingRefresh`)
  pass unchanged.
- C++: this sandbox has no access to the pinned vcpkg toolchain image (no
  outbound registry access), so `docker compose -f docker-compose.test.yml`
  could not run here. Instead, `DataCollector.cpp`,
  `src/tests/test_opportunity_label.cpp`, `DiagnosticsContract.cpp`, and
  `src/tests/test_diagnostics_contract.cpp` were compiled and linked
  standalone against apt-installed nlohmann-json/libpqxx/spdlog/xtensor
  packages (C++17, to match that package's ABI) and executed directly; all
  assertions passed, including new coverage for
  `compute_opportunity_label`'s cost-hurdle boundary behavior and for
  `ml_orderbook_opportunity`'s admission through the shared diagnostics
  gate. The exact-SHA GitHub Actions Docker Build Validation run against the
  real pinned toolchain is still required before closeout per
  `docs/STRATEGY_OBJECTIVE.md`'s review checklist.
