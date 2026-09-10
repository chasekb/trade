# Order-book optimization protocol and report schema

Status: report-only specification. This document does not change runtime behavior. It is the contract for a worker implementing an offline evaluator over captured live signals, live-parity paper fills, and synthetic simulation rows.

## 1. Scope and source contract

The evaluator must trace one signal/intent lifecycle from market observation through signal generation, profitability diagnostics, execution attempt, fill/settlement, and realized outcome. It must preserve the source mode and never merge simulated capital or outcomes into live account state.

The current source contract is:

- `src/trading/LiveTradingService.cpp` and `src/trading/SimulatedTradingService.cpp` persist order-book observations/signals with symbol, session, bid/ask/depth/volume, signal strength, model fields, expected return, and trade type. Live uses `live`; simulator uses `simulated`; simulator also supports `live` and `live_parity` market-data modes.
- `include/trading/StrategySignal.hpp` defines `signal_type` (`buy`, `sell`, `hold`), strength in `[0,1]`, expected return, spread, round-trip fee, slippage buffer, and minimum strength. Order-book strategies are `orderbook` and `ml_enhanced_orderbook`.
- The profitability gate is directional: a buy requires positive expected edge; a sell requires negative expected edge. The absolute directional edge must exceed the positive fee + spread + slippage hurdle; equality fails closed. Missing expected return is unavailable and is never actionable.
- `src/trading/StrategyExpectancyHarness.cpp` is a deterministic fixture reference. It counts generated non-hold signals, blocked intents, filled rows, net realized PnL, average win/loss, expectancy, profit factor, and dollar drawdown.

A row is an immutable observation of one lifecycle grain. Do not count a signal, intent, order submission, fill, and close as separate trades. Store their counts separately and define the outcome unit as a completed entry-to-exit round trip (or explicitly label an unfinished/censored row).

## 2. Evaluation populations and leakage controls

Run all candidates against three separately reported populations:

1. **live**: read-only captured production rows and actual exchange outcomes. Never replay orders or mutate an account.
2. **live_parity**: the same live market-data capture and clock/order-book features, but paper settlement using the declared fee, spread, slippage, latency, and fill model. `n_submitted` means local settlement attempts, including paper fills; it is not an exchange-submission count.
3. **simulated**: deterministic historical/fixture replay with synthetic capital and an explicitly declared fill model. It must not be presented as live evidence.

Every row must carry `population`, `session_id`, `symbol`, `strategy`, `model_branch`, `signal_id`, `observation_ts`, `intent_ts`, `fill_ts` (nullable), `close_ts` (nullable), and `data_source_id`. Sort by event time and use only information available at or before `observation_ts` for signal features and labels. Do not fit thresholds, model branches, fee assumptions, or symbol overrides on the evaluation window.

Use a chronological walk-forward split for captured data: 60% train/calibration, 20% validation, 20% final holdout, with a purge gap at least the maximum label horizon plus the maximum measured decision/fill latency between adjacent partitions. Keep sessions intact where practical; otherwise group by session and prevent one lifecycle from crossing partitions. Synthetic fixtures are unit/regression evidence, not a substitute for the holdout.

The run manifest must record dataset hashes, query/filter, timezone, start/end timestamps, split boundaries, label definition, matching horizon, starting capital/equity, fee/spread/slippage assumptions, random seed, code/config revision, and optimizer search space.

## 3. Required row dimensions and labels

Group and report every metric at minimum by:

- population (`live`, `live_parity`, `simulated`);
- symbol;
- strategy (`orderbook`, `ml_enhanced_orderbook`, and any comparator strategy);
- model branch (for example `heuristic`, `regressor`, `transformer`, or a stable model/version identifier);
- signal side (`buy`, `sell`, `hold`), strength bucket (`none`, `weak`, `medium`, `strong` using existing 0/0.45/0.75 boundaries), and expected-return bucket;
- parameter set/default versus symbol override;
- time split and session.

The primary forward label is signed, mark-to-market return over a declared horizon from the decision price, using the first eligible executable price after decision latency. For buys, `label_return = (exit_mark - entry_mark) / entry_mark`; for sells, `label_return = (entry_mark - exit_mark) / entry_mark`. A row without a valid horizon endpoint is censored and excluded from realized outcome metrics but remains in signal, intent, blocker, and coverage counts. Never use post-decision prices, fills, or realized PnL as features.

## 4. Baseline and candidate protocol

The baseline is the checked-in/default configuration, evaluated unchanged on the same rows and split boundaries as every candidate. Record a baseline row even when it produces no fills. Candidate selection is a bounded grid or predeclared seeded search; no adaptive search on holdout data.

For each row evaluate, in order: signal output; expected-return availability; directional edge; profitability gate; size/minimum-notional gate; execution/settlement attempt; fill; close/outcome. Preserve every rejection/block reason rather than dropping it. A candidate is eligible only if it has no fatal data/leakage violation, positive net expectancy on validation and holdout, and passes all safety gates below. Selection priority is: (1) fail-closed correctness and no fatal blocker regression, (2) holdout fee-adjusted expectancy, (3) profit factor, (4) lower drawdown, (5) stable symbol/session performance, then (6) frequency. Higher signal or trade count alone never wins.

### Parameters and bounded ranges

The implementation must expose the exact candidate values in the manifest. Unless a narrower exchange/data-supported range is documented, use these inclusive ranges:

| knob | values/range | default/reference |
|---|---:|---:|
| `min_signal_strength` | 0.00 to 1.00, step 0.05 | 0.22 |
| expected-return threshold / minimum directional edge | 0.00% to 10.00%, step 0.10% | gate requires strictly positive net edge |
| `round_trip_fee_percent` | 0.00% to 2.00%, step 0.05% | live source 0.05% where applicable; simulator parameter default 0.16% |
| `spread_percent` | 0.00% to 5.00%, step 0.05% | observed bid/ask spread; never replace observed spread with zero |
| `slippage_buffer_percent` | 0.00% to 5.00%, step 0.05% | live order-book reference 0.20%; simulator parameter default may be 0 |
| `horizon_seconds` | 1 to 86,400, log-spaced or declared fixed values | must match label manifest |
| `decision_latency_ms` | 0 to 10,000, step 50 | measured value or declared conservative bound |
| `minimum_net_pnl_usd` | 0 to 100, step 0.50 | 0 unless the run declares another guard |
| `position_size_percent` | 0.1% to 100%, step 0.1% | use source/session default |
| `position_value_usd` | positive exchange-valid range; cap at declared capital | source/session default |

Strategy comparator knobs must also be bounded when used: SMA/EMA short window 2–100 and long 3–500 (long > short); RSI window 2–100 with overbought 50–95 and oversold 5–50 (oversold < overbought); Bollinger window 2–200 and standard deviation 0.5–5; MACD fast 2–100, slow 3–300 (slow > fast), signal 2–100; stochastic K 2–100, D 1–50, overbought 50–99, oversold 1–50; Fibonacci lookback 2–500 with levels in (0,1); DCA interval 1–10,080 ticks. Invalid combinations are rejected, not silently repaired during optimization; any runtime normalization must be reported as a separate effective parameter set.

## 5. Non-negotiable cost and safety invariants

For every side, use nonnegative costs:

`required_edge = fee_fraction + spread_fraction + slippage_buffer_fraction`

`directional_edge = buy ? expected_return : -expected_return`

`fee_adjusted_expected_return = directional_edge - required_edge`

A candidate is actionable only when expected return is available, signal strength is at least the threshold, and `fee_adjusted_expected_return > 0` (strict inequality). A missing, non-finite, or malformed cost/return value is unavailable and blocks. Do not clamp a negative expected return into a buy edge or use an unsigned absolute return for side selection. For sell rows the expected return is allowed to be negative and favorable only after the same positive hurdle. Actual realized net PnL must subtract fees, spread, and slippage exactly once; gross PnL and each cost component remain separately reportable.

Live-only blockers (credentials/readiness, selected-universe policy, exchange response, minimum notional, spot/account constraints, pending-order conflicts, explicit live enablement, and rate limits) must never be optimized away or counted as signal-quality wins. Any candidate that increases attempted live execution while weakening a blocker or changes live behavior requires independent high-risk financial review and explicit approval before implementation. This document alone authorizes no live change.

## 6. Minimum samples and uncertainty

Report counts and eligibility separately. A group is **decision-eligible** only when it has at least 100 completed round trips, at least 30 winners and 30 losers when those classes exist, at least 20 sessions or five independent time blocks, and at least 20 generated intents when measuring blocker rate. A symbol/model branch with fewer observations is `insufficient_sample`, not a zero or a winning override. The global candidate may use pooled data only when every population and symbol is reported and no symbol has a material safety regression.

Use bootstrap confidence intervals over sessions (not individual correlated rows) for expectancy, average win/loss, profit factor, and drawdown. Require the holdout confidence interval for expectancy to be above zero for a promoted candidate; otherwise retain baseline. Report the number of candidate comparisons and use a declared multiple-comparison correction or mark the result exploratory.

## 7. Metrics and exact denominators

For each group report:

- `n_observations`: all valid observation rows;
- `n_signals_generated`: non-hold signals;
- `n_intents`: executable-intent decisions after signal generation;
- `n_blocked`: intents rejected before submission, with reason counts;
- `n_submitted`: exchange submissions for live; local settlement attempts for live-parity/simulated;
- `n_filled`: completed entry fills (and separately partial fills);
- `n_completed_round_trips`: rows with both entry and exit outcome;
- `signal_rate = n_signals_generated / n_observations`;
- `trade_frequency_per_hour = n_submitted / observed_hours` and `fills_per_hour`;
- `rejected_or_blocked_intent_rate = (n_blocked + n_rejected) / max(1, n_intents)`; keep rejection and blocker numerators distinct;
- `expected_return_mean` and `fee_adjusted_expected_return_mean` on rows where diagnostics are available, plus unavailable count;
- `realized_pnl_gross`, `total_fees`, `total_spread_cost`, `total_slippage_cost`, and `realized_pnl_net = gross - fees - spread - slippage`;
- `average_win = sum(net PnL > 0) / count(net PnL > 0)` and `average_loss = abs(sum(net PnL < 0) / count(net PnL < 0))`; zero PnL is neither;
- `expectancy = mean(net PnL)` over completed round trips;
- `profit_factor = gross positive net PnL / abs(gross negative net PnL)`; null when no losses, never fabricate infinity as a comparable score;
- `max_drawdown_usd` from the chronological cumulative net-PnL/equity curve, and `max_drawdown_percent` only when positive `starting_equity` is explicitly present: drawdown dollars divided by the prior equity peak (or declared starting equity baseline);
- `win_rate_percent = winners / (winners + losers) * 100`, excluding zero-PnL rows.

Include latency, partial-fill, censored-label, and blocker-reason distributions. A group with no denominator is null, not zero.

## 8. Machine-readable report schema

Emit one JSON object per group as JSONL plus one run-manifest object. The following is the minimum contract; additional fields are allowed only when documented:

```json
{
  "record_type": "order_book_optimization_group",
  "run_id": "string",
  "population": "live|live_parity|simulated",
  "split": "train|validation|holdout|fixture",
  "symbol": "BTC-USD",
  "strategy": "orderbook",
  "model_branch": "heuristic|regressor|transformer|versioned-id",
  "parameter_set": "baseline|candidate|symbol-override",
  "parameters": {},
  "dataset_hash": "sha256:...",
  "source_query_or_fixture": "string",
  "window": {"start": "ISO-8601", "end": "ISO-8601", "timezone": "UTC"},
  "starting_capital_usd": 10000.0,
  "starting_equity_usd": 10000.0,
  "matching_horizon_seconds": 300,
  "label_definition": "signed forward mark return after decision latency",
  "decision_latency_ms": 250,
  "fee_assumption_fraction": 0.0005,
  "spread_assumption_fraction": 0.001,
  "slippage_assumption_fraction": 0.002,
  "n_observations": 0,
  "n_signals_generated": 0,
  "n_intents": 0,
  "n_blocked": 0,
  "n_rejected": 0,
  "n_submitted": 0,
  "n_filled": 0,
  "n_completed_round_trips": 0,
  "n_censored": 0,
  "signal_rate": null,
  "trade_frequency_per_hour": null,
  "rejected_or_blocked_intent_rate": null,
  "expected_return_mean_fraction": null,
  "fee_adjusted_expected_return_mean_fraction": null,
  "realized_pnl_gross_usd": 0.0,
  "total_fees_usd": 0.0,
  "total_spread_cost_usd": 0.0,
  "total_slippage_cost_usd": 0.0,
  "realized_pnl_net_usd": 0.0,
  "average_win_usd": null,
  "average_loss_usd": null,
  "expectancy_usd": null,
  "profit_factor": null,
  "max_drawdown_usd": null,
  "max_drawdown_percent": null,
  "win_rate_percent": null,
  "blocker_counts": {},
  "rejection_counts": {},
  "sample_status": "eligible|insufficient_sample|invalid|exploratory",
  "confidence_intervals": {},
  "selection_status": "baseline|candidate|promoted|rejected|no_override"
}
```

The manifest must additionally include `code_revision`, `config_revision`, all split boundaries, `random_seed`, `candidate_count`, `search_space`, `cost_model_version`, `fill_model_version`, `minimum_sample_rules`, and `review_gate: "independent_high_risk_review_required_for_live_affecting_change"`. Before recommending a default or symbol override, the report must contain baseline-vs-candidate deltas for net expectancy, average win/loss, profit factor, drawdown, frequency, cost drag, and blocked/rejected rates, with confidence intervals and the reason for promotion or rejection.

## 9. Worked consistency examples

These are schema examples, not performance claims. In a live-parity group with 20 local fills, `n_submitted` is 20 even though exchange submissions are zero; the distinction is represented by `population` and the denominator definition. In a live group, do not report a drawdown percentage unless `starting_equity_usd` is known and positive. Exposure is not starting equity. A group with 20 fills and no losses has `profit_factor: null` for comparability, not an invented infinite score.

## 10. Implementation and closeout gate

A future implementation must add tests for signed buy/sell edge, exact-neutral cost rejection, missing/non-finite diagnostics, each denominator, zero-PnL handling, censored labels, drawdown prerequisites, profit-factor nullability, and sample eligibility. It must first run fixture and offline/live-parity validation; no production behavior is changed by this protocol.

Any code or configuration change that affects live signal generation, expected return, fees/spread/slippage, profitability gating, sizing, exchange submission, or blocker handling is high-risk financial work. Independent review is mandatory, explicit approval is mandatory, exact pushed-SHA remote CI is mandatory, and live runtime/account evidence must be captured before closeout. Without those gates, the only acceptable status is `report_only` or `blocked`; never promote a candidate into live defaults from this report alone.
