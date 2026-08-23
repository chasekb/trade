# Order-book strategy sweep and walk-forward contract

Status: design-only contract for a future evaluation harness

This document defines an offline, deterministic evaluation contract for bounded
parameter sweeps. It does not authorize a production configuration change and
must not be used by a live or simulated trading session to mutate its
parameters.

## 1. Existing contract and boundaries

The harness must call the same pure strategy/profitability boundaries used by
current code, or an explicitly equivalent adapter:

- `evaluateStrategySignal` emits `buy`, `sell`, or `hold` with strength in
  `[0, 1]` for indicator strategies. `orderbook` and
  `ml_enhanced_orderbook` are handled by the order-book caller.
- `evaluateOrderBookProfitabilityGate` computes directional edge and requires
  `edge > round_trip_fee + spread + slippage`; equality is rejected.
- `evaluateStrategyProfitabilityDiagnostic` classifies missing expected return
  as `expected_return_unavailable` and never treats it as actionable.
- `PositionSizingInputs` and `MinimumTradeSizeInputs` provide the sizing and
  minimum-net-P&L seams. The configured notional is a hard ceiling.
- Current order-book model branches are `orderbook` and
  `ml_enhanced_orderbook`. A model branch is identified by strategy plus the
  selected model name/version; fallback-to-baseline is a separate branch, not
  silently mixed into the model result.

The current defaults used as the baseline are: round-trip fee `1.5%`, slippage
buffer `0.2%`, minimum signal strength `0.22`, heuristic edge scale `2.4%`,
and the existing spread/imbalance/order-book defaults from the active fixture.
The baseline must be captured in the report rather than read from or rewritten
to a running session.

## 2. Sweep dimensions and bounded candidates

All values are percentages unless marked fraction or dollars. The harness
rejects NaN, infinity, values outside these bounds, and duplicate candidates.
The ranges are deliberately narrower than the UI's permissive controls where
an extreme value would make the result a throughput experiment rather than an
edge experiment.

| dimension | candidate values | justification |
| --- | --- | --- |
| `min_orderbook_signal_strength` | `0.15, 0.22, 0.30, 0.40, 0.60` | Covers the existing very-aggressive/default/moderate/conservative presets; `[0,1]` is the signal contract, but zero is excluded because it removes the strength gate. |
| `orderbook_expected_return_scale_percent` | `1.2, 1.8, 2.4, 3.0` | The existing regression identifies `1.2%` as unable to clear the normal hurdle and `2.4%` as the aligned fallback; `3.0%` tests a bounded optimistic calibration without allowing arbitrary edge inflation. |
| `round_trip_fee_percent` | `0.10, 0.16, 0.50, 1.00, 1.50, 2.00` | Includes the low default seen by generic simulated sizing (`0.16%`), the current order-book baseline (`1.50%`), and conservative stress; bounded to `0.10–2.00%` and never negative. |
| `slippage_buffer_percent` | `0.00, 0.10, 0.20, 0.40, 0.80` | Includes current default and stress cases; bounded to a plausible execution-cost envelope and never negative. |
| `bid_ask_spread_threshold_percent` | `0.10, 0.20, 0.50, 1.00` | Exactly covers the existing conservative through very-aggressive presets. A candidate is a filter threshold, not a waiver of the profitability spread hurdle. |
| `imbalance_weight` | `0.00, 0.25, 0.50, 0.75, 1.00` | Sweep-only coefficient for the order-book imbalance contribution. `1.00` preserves the existing heuristic; zero is the control. It must be applied before clamping and must not alter raw captured imbalance. |
| `position_size_base_usd` | `25, 50, 100, 250, 500, 1000` | Bounded notional inputs for fixtures; the evaluated notional remains capped by the candidate and account/fixture budget. |
| `position_size_multiplier` | `0.35, 0.55, 0.75, 1.00` | Covers the production sizing floor, weak-signal reduction, moderate deployment, and full configured cap. Values above `1.00` are excluded because the configured maximum is a hard ceiling. |
| `minimum_net_pnl_usd` | `0.00, 0.10, 0.25, 0.50, 1.00` | Covers current presets and a bounded absolute hurdle; it cannot be negative. |

Position sizing inputs (`signal_strength`, `win_probability`, expected return,
model confidence, spread, volatility, live/cohort performance) are recorded
from the fixture/model prediction. They are not independently optimized in the
first sweep. If a later sweep adds them, it must use the same finite bounds as
the corresponding production normalizers (`signal_strength` and confidence
`[0,1]`, win probability `[0,1]`, expected return `[-0.02,0.04]`) and remain
capped by `base_usd`.

## 3. Deterministic candidate generation

Candidate order is lexicographic in this exact dimension order:

1. `min_orderbook_signal_strength`
2. `orderbook_expected_return_scale_percent`
3. `round_trip_fee_percent`
4. `slippage_buffer_percent`
5. `bid_ask_spread_threshold_percent`
6. `imbalance_weight`
7. `position_size_base_usd`
8. `position_size_multiplier`
9. `minimum_net_pnl_usd`
10. model branch (`baseline`, then each selected model name/version in bytewise
    lexical order)

Within each dimension, use the table order. Generate the Cartesian product,
then assign a zero-based `candidate_index` in generation order. Do not sample,
shuffle, parallel-order, or deduplicate after assigning indices. The baseline is
always candidate index zero and is evaluated before any alternative. The
selected symbol universe is sorted bytewise only for deterministic iteration;
its membership is never changed by the harness.

## 4. Fixture and walk-forward evaluation

The harness supports two input modes with one report schema:

- **Deterministic fixture mode:** checked-in fixtures contain timestamp,
  symbol, strategy, model branch, order-book features, prices, prediction
  fields, and realized net outcome. Fixtures must include at least 30 completed
  opportunities per `(symbol, strategy, model_branch)` cell for exploratory
  output; cells below 30 are reported but cannot be admitted.
- **Walk-forward mode:** sort observations by `(timestamp, symbol, stable_id)`.
  Use expanding training windows of 70% of the ordered history, a 10% purge /
  embargo gap, and the following 20% as evaluation. Repeat with five sequential
  folds when enough history exists. No observation may occur in both train and
  evaluation, and no future-derived feature, fee, or outcome may enter a
  training row. A fold needs at least 30 evaluation opportunities per cell and
  at least 100 total evaluation opportunities; otherwise it is `insufficient_data`.

Training is optional for a pre-trained model branch. If training is used, the
seed is the fixed unsigned 64-bit value `0x5EED5EED`, recorded in metadata;
model fitting and row ordering must be deterministic. No random seed is used
for pure rule/fixture branches. Missing seed or nondeterministic model metadata
is a reproducibility failure, not a passing result.

The baseline is the existing parameter set and the same model branch, symbol
universe, fixtures, folds, and cost assumptions as the candidate. Candidates
are compared only with their paired baseline cells; no cross-fold or cross-
symbol pooling may hide a failing cell.

## 5. Directional gate and admission rules

For a buy, directional edge is `expected_return_fraction`; for a sell it is
`-expected_return_fraction`. For hold, no intent exists. Required edge is:

`max(0, fee) + max(0, spread) + max(0, slippage)`

A candidate may fill only when signal is buy/sell, strength is strictly above
the minimum, expected return is available, directional edge is strictly above
required edge, spread is within the candidate filter, and sizing is positive.
A sell with positive expected return, or a buy with negative expected return,
is a directional-gate violation and must be rejected. Missing expected return,
non-finite inputs, negative costs, `allow_unprofitable_trades=true`, or a
notional above the configured cap are also rejection conditions. The harness
records the first stable blocker reason and never converts a rejected intent
into a fill merely to increase sample count.

An admission requires all of:

- no directional-gate violation and no safety-contract violation;
- at least 30 completed evaluation opportunities in every reported
  `(symbol,strategy,model_branch)` cell (or the cell is explicitly marked
  insufficient and the candidate is not admitted);
- aggregate and every eligible cell have non-negative net expectancy;
- aggregate profit factor is at least `1.0` and maximum drawdown does not
  exceed the configured evaluation budget;
- candidate does not increase filled trades while lowering fee-adjusted
  expectancy versus its paired baseline; a higher signal count alone is never
  an admission reason.

Negative expectancy, a negative fee-adjusted edge, a failing required cell, or
any gate-semantics violation produces `rejected` with machine-readable reasons.
No “best effort” admission is allowed.

## 6. Metrics and minimum-sample handling

Each completed fill uses realized net P&L after fees, spread, and slippage.
For a cell and for the overall report:

- `sample_count`: completed evaluation opportunities;
- `signals_generated`: non-hold signals;
- `filled_count`: admitted/fillable opportunities;
- `blocked_count`: generated intents rejected by a gate or safety rule;
- `win_rate`: `wins / (wins + losses)` as a 0–100 percentage; zero-P&L rows
  are excluded;
- `average_win`: sum of positive net P&L / winning count;
- `average_loss`: sum of negative net P&L / losing count (negative value);
- `expectancy`: total net P&L / completed fills;
- `profit_factor`: gross positive net P&L / absolute gross negative net P&L;
  if there are no losses, report `null` unless at least one fill exists;
- `max_drawdown`: peak-to-trough drawdown of cumulative net P&L in dollars;
- `fee_adjusted_expected_return`: directional expected edge minus required edge;
- `blocked_intent_rate`: blocked count / generated signals.

Metrics with zero denominator are `null`, never zero-filled. A cell below the
minimum sample count remains visible with `status: insufficient_data` and is
excluded from admission comparisons. Report both pooled totals and the
unweighted median across eligible cells so a dominant symbol cannot mask a
losing symbol.

## 7. Machine-readable result schema

The canonical artifact is JSON (UTF-8, stable key order, no NaN/Infinity):

```json
{
  "schema_version": "sweep.v1",
  "status": "admitted|rejected|insufficient_data|error",
  "candidate_index": 0,
  "candidate": {
    "min_orderbook_signal_strength": 0.22,
    "orderbook_expected_return_scale_percent": 2.4,
    "round_trip_fee_percent": 1.5,
    "slippage_buffer_percent": 0.2,
    "bid_ask_spread_threshold_percent": 0.5,
    "imbalance_weight": 1.0,
    "position_size_base_usd": 100,
    "position_size_multiplier": 1.0,
    "minimum_net_pnl_usd": 0.0,
    "model_branch": {"kind": "baseline", "name": "", "version": ""}
  },
  "baseline_candidate_index": 0,
  "reproducibility": {
    "input_fixture_sha256": "...",
    "code_revision": "...",
    "config_schema_version": "...",
    "mode": "fixture|walk_forward",
    "folds": [1, 2, 3, 4, 5],
    "seed": 1592653581,
    "universe": ["BTC-USD", "ETH-USD"],
    "generated_at_utc": "..."
  },
  "counts": {
    "sample_count": 0,
    "signals_generated": 0,
    "filled_count": 0,
    "blocked_count": 0
  },
  "metrics": {
    "pooled": {},
    "median_by_cell": {},
    "by_symbol": {},
    "by_strategy": {},
    "by_model_branch": {}
  },
  "cells": [
    {
      "symbol": "BTC-USD",
      "strategy": "ml_enhanced_orderbook",
      "model_branch": {"kind": "baseline", "name": "", "version": ""},
      "fold": 1,
      "status": "eligible|insufficient_data|rejected",
      "sample_count": 0,
      "metrics": {},
      "rejection_reasons": []
    }
  ],
  "rejection_reasons": [],
  "gate_violations": []
}
```

Each metrics object uses the names and null semantics in section 6. Each row
may additionally include `timestamp`, `signal_type`, `signal_strength`,
`directional_expected_edge_fraction`, `required_edge_fraction`,
`fee_adjusted_expected_return_fraction`, `realized_net_pnl_usd`, and
`blocker_reason`; raw secrets, credentials, and account identifiers are never
part of the artifact.

## 8. Human-readable report

The companion Markdown report must contain, in order:

1. run identity: schema version, code revision, input hash, UTC time, mode,
   folds, seed, universe, and explicit `production_mutation: false`;
2. baseline candidate and the exact candidate-generation order;
3. candidate outcome table with status, sample count, signals, fills, blocked
   intents, average win/loss, expectancy, profit factor, drawdown, and the
   baseline deltas after costs;
4. per-symbol, per-strategy, and per-model-branch tables, including an
   insufficient-data marker rather than omitted rows;
5. gate audit: directional violations, unavailable expected-return rows,
   spread/fee/slippage blockers, and sizing-cap blockers;
6. admission decision and every rejection reason; and
7. reproducibility and safety statement confirming that no live/simulated
   session, account, selected universe, or production configuration was
   changed.

## 9. Implementation safety contract

The future harness may read checked-in fixtures, immutable exported history, or
an explicit caller-supplied snapshot. It must not call start/stop trading,
update strategy parameters, set an active model, submit/cancel orders, write
session parameters, or silently expand the selected universe. Candidate
configuration is an in-memory value object or an isolated temporary artifact;
the process must fail closed if an adapter would touch a live configuration
path. A test should assert that production/live configuration mutation is not
invoked and that a directional sell/buy mismatch is rejected.