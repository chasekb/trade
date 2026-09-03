# Order-book optimization methodology and evaluation contract

Status: design-only handoff. This document changes no production behavior. It is the contract for a later implementation and documentation pass.

## 1. Scope, populations, and provenance

Evaluate three mutually exclusive populations:

* `live`: broker/exchange rows produced by the live service. These are observational and must never be mixed with simulated fills.
* `live_parity_paper`: paper decisions replayed against the same timestamped live market inputs, with the same strategy/model configuration and a deterministic execution simulator. This is the parity population, not a second live population.
* `simulated`: historical or fixture inputs generated independently of live execution. Synthetic rows must carry `data_origin=fixture` and must not be presented as observed performance.

Every input row and report must preserve: `run_id`, `data_origin`, `source_dataset_id`, source commit/config/model artifact hashes, exchange/symbol, event timestamp in UTC, ingestion timestamp, strategy name/version, model branch/version (including `baseline`), parameter vector, starting cash/equity, quote currency, horizon and label definition, cost assumptions, and code version. Do not infer a missing value as zero. Invalid timestamps, non-finite prices/sizes, crossed books, duplicate event IDs, and rows outside the declared time window are rejected and counted.

A decision lifecycle is the primary unit: one `decision_id` per eligible market observation and strategy evaluation. An intent/fill may have many lifecycle events, but aggregation must deduplicate by `decision_id`; never count a partial fill as another signal. Preserve `intent_id`, `order_id`, `fill_id`, and `position_id` when available.

## 2. Grouping and comparisons

The report must provide rows at these grains:

1. population × symbol × strategy × model branch × split;
2. population × symbol × strategy × model branch (pooled splits only for display);
3. population × strategy × model branch (pooled symbols only when a predeclared macro decision is required).

`symbol`, `strategy`, and `model_branch` are mandatory dimensions, not free-form report labels. At minimum use `baseline`, candidate branch name/version, and `fallback` where the ML strategy delegates to the baseline. Compare branches on the identical decision set (or publish an explicit coverage difference); never compare a high-coverage branch to a selectively filtered subset without reporting denominators.

Live and live-parity paper may be compared only over identical event timestamps and symbol sets. Simulated results are a separate evidence tier. A return, PnL, or gate conclusion is not transferable between tiers without a stated assumption and high-risk review.

## 3. Labels, costs, and metric definitions

For a decision at time t, define side s (+1 buy, -1 sell), quantity q, reference mid m_t, entry execution p_in, exit execution p_out, and holding horizon H. The forward mark label is `r_gross = s * (p_{t+H} - p_t) * q` in quote currency. If a configured label is percentage-based, report it separately as `s*(p_{t+H}/p_t - 1)`; do not mix currency and percentage labels.

Costs are explicit per round trip: exchange fees `fee_in + fee_out`, half-spread paid on each side, and adverse slippage in quote currency. Use a deterministic cost scenario ID (base, stressed, or exchange-observed). For a buy, a conservative fill is `p_in = ask_t + slip_in`; for a sell, `p_in = bid_t - slip_in`; reverse the side at exit. If a side of the book is absent, the fill is unavailable, not zero-cost.

* Signal strength: the value emitted by the strategy, on its declared scale. For the current order-book baseline, retain the emitted normalized [0,1] strength and report mean/median/quantiles by action. For imbalance diagnostics also report `abs(log(bid_volume/ask_volume))`; do not call the two measures interchangeable.
* Expected return: model-predicted forward return at decision time, in quote currency per intended quantity and, separately, percent of notional. Record the model horizon and whether it is gross or net; never substitute realized PnL.
* Fee-adjusted expected return: `expected_return_net = expected_return_gross - fee_estimate - spread_estimate - slippage_estimate`, all in the same currency/unit. For percentage form divide by intended notional only when notional > 0.
* Realized PnL gross: `pnl_gross = s*(p_out-p_in)*q` for a completed round trip. Mark open positions at the declared horizon and label them `unrealized`; do not silently treat them as realized.
* Realized PnL net: `pnl_net = pnl_gross - fees - spread_cost - slippage_cost`. Use `net` for gates and selection. `total_fees`, spread, and slippage must be separately reported.
* Average win: mean `pnl_net` over completed trades with `pnl_net > 0`; average loss: mean `pnl_net` over completed trades with `pnl_net < 0` (negative value). Also report counts and medians. If a side has no observations, value is unavailable (`null`).
* Expectancy: `E = (n_win/n) * avg_win + (n_loss/n) * avg_loss`, per completed trade in quote currency net of all costs. Break out win rate and payoff ratio so a zero-trade or one-sided sample cannot look favorable.
* Profit factor: `sum(pnl_net where pnl_net>0) / abs(sum(pnl_net where pnl_net<0))`. If gross loss is zero, publish `null` (not infinity) unless the report explicitly includes the numerator and denominator and marks it degenerate.
* Drawdown: with positive starting equity E0 and chronological equity curve E_t, `peak_t=max(E_0..E_t)`, `dd_t=(peak_t-E_t)/peak_t`; max drawdown is `max(dd_t)` as a fraction and percent. Include peak/trough timestamps and recovery status. Exposure or notional is not a denominator for drawdown.
* Trade frequency: completed plus open intents divided by elapsed eligible observation time, reported as trades/day and intents/1,000 eligible decisions. State whether canceled/rejected intents are included; use elapsed UTC time, never row count alone.
* Rejected/blocked intent rate: `(n_rejected + n_blocked) / n_intent_attempts`, where intent attempts include every eligible decision that requested an order or was blocked by a risk/execution gate. Report rejected and blocked numerators separately, reason codes, and the eligible-decision denominator. Missing lifecycle outcomes are `unknown`, not accepted or rejected.

All metrics include `n_decisions`, `n_intents`, `n_completed`, `n_open`, `n_unknown`, and coverage. Bootstrap 95% confidence intervals (decision-clustered; trade-clustered for trade metrics) are required where sample size permits. State that intervals are descriptive, not proof of causality.

## 4. Eligibility, missingness, and sample gates

A symbol/strategy/branch/split row is eligible for a performance gate only if it has at least 200 completed round trips, at least 50 wins and 50 losses, at least 30 calendar days, and at least 10,000 eligible decisions. A parity row additionally needs 95% matching decision coverage and 99% matching event timestamps within the declared tolerance. If these thresholds are not met, status is `insufficient_data` and all gate fields are false/null.

For model selection metrics, require at least 1,000 labeled decisions per split, at least 100 positive and 100 negative labels, and no missing feature/label rate above 1%. For any metric, missingness above 1% or unknown lifecycle outcomes above 2% is a data-quality failure; report it and fail closed. Deduplicate exact event IDs and flag conflicting duplicates; never silently choose one.

Do not impute market prices, fills, fees, outcomes, or blockers. Feature-only imputation must be fit on training data and recorded. A failed model request, unavailable book side, stale quote, or risk block is an operational outcome and remains in the denominator.

## 5. Chronological experiment design and leakage controls

Use an expanding-window walk-forward design, selected before inspecting outcomes. Default boundaries for a dataset with at least 180 days are 60% train, 20% validation, 20% test by timestamp, with a purge gap equal to the maximum label horizon plus the maximum execution/holding overlap. For shorter datasets use 5 chronological folds with the same purge/embargo rule; do not random-shuffle time series.

* Fit scalers, feature selectors, thresholds, parameter choices, and symbol overrides on train only.
* Select a candidate on validation only. Test is touched once for the locked candidate and is never used to retune.
* If labels overlap, purge all training observations whose label window intersects validation/test; embargo at least H after each boundary.
* Model artifacts, configurations, and dataset snapshots are immutable and hashed. A later timestamp may not influence an earlier decision through caches, rolling aggregates, normalization, or override lookup.
* For live-parity paper, replay market data in timestamp order and forbid future book levels, future fills, and live account state. Keep a separate paper run ID.

The primary decision is the median net expectancy across test windows subject to gates, not the best window. Report window dispersion, worst-window result, bootstrap interval, and degradation from validation to test.

## 6. Parameters and bounded search space

The implementation must expose and record every optimized knob. Unless a venue or strategy contract narrows it, use these predeclared ranges (inclusive endpoints; values outside are invalid):

| Knob | Search values/range |
|---|---|
| `min_volume_ratio` | 1.25–4.00, step 0.25 |
| `max_spread_percent` | 0.02%–0.50%, step 0.01 percentage points |
| `order_book_level` | integers 1–10 |
| `trade_history_limit` | integers 50–2,000 (log-spaced candidates) |
| `bid_ask_spread_threshold` | 0.0005–0.0100, step 0.0005 (fraction) |
| `volume_imbalance_threshold` | 0.20–0.90, step 0.05 |
| `large_trade_threshold` | quote notional 500–25,000, log-spaced candidates |
| `data_analysis_mode` | `recent` or `all` |
| `recent_data_limit` | integers 25–500 |
| `sampling_ratio` | 0.05–1.00, step 0.05 |
| `confidence_threshold` (ML branch) | 0.50–0.95, step 0.05 |
| `fallback_to_baseline` | explicit boolean; evaluate both only in paper/simulation |
| stop-loss/take-profit enable flags | explicit booleans; no optimization in live without approval |
| position-size percent | 1%–25%, step 1%; dollar sizing must be separately constrained by risk limits |

Use a fixed random seed only for deterministic fixture generation and bootstrap resampling. Limit the total search budget and publish all tried configurations, not just the winner. Enforce structural constraints such as `order_book_level <= available_levels`; an invalid candidate is `invalid_config`, not a zero return.

## 7. Cost and directional invariants

For the same decisions and fills, increasing any nonnegative fee, spread, or adverse-slippage assumption must weakly decrease every net trade PnL, cumulative net equity, and net expectancy. It must weakly increase cost totals and cannot increase net profit factor. A cost increase may reduce executed intents if a pre-trade economics gate blocks them; that is a coverage change and must be reported, never used to manufacture a better return.

Required deterministic metamorphic tests over fixtures:

1. zero-cost and positive-cost replay have identical signals and gross PnL;
2. positive costs satisfy `net <= gross` trade-by-trade;
3. cost-stressed net expectancy <= base net expectancy when the decision set is unchanged;
4. widening spread or increasing adverse slippage cannot improve a fill price for the trader;
5. if a candidate passes a net gate under stressed costs, it passes under any lower-cost scenario; if it fails under base costs, higher costs cannot make it pass;
6. cost changes cannot reverse a gate from fail to pass. If execution filtering changes coverage, gate status is `not_comparable` unless both the fixed-decision and executable-decision analyses are published;
7. adding a fee cannot turn a losing completed trade into a winning net trade.

Any invariant violation is a protocol/implementation failure and blocks promotion, regardless of aggregate performance.

## 8. Defaults and per-symbol overrides without leakage

Start with the checked-in baseline configuration, not an optimized value. A global default is chosen using train/validation walk-forward results pooled across the predeclared symbol universe, with symbol-balanced weighting. A per-symbol override is allowed only when that symbol has its own eligible train/validation evidence, improves median net expectancy by at least 10% and does not worsen stress max drawdown by more than 10% relative to the global default, with the 95% interval for the improvement reported.

Require stability: the selected parameter must be among the top 20% by net expectancy in at least 3 independent validation windows, have no validation window with negative expectancy worse than the baseline by 25%, and have a neighboring-parameter plateau (at least two adjacent candidates within 5% of the winner). Otherwise use the global default and mark the override `unstable`.

Freeze defaults and overrides before the untouched test. Never select a symbol override using test data, current live results, or a symbol-specific subset discovered after seeing outcomes. Revalidate on a rolling schedule using only data available at the revalidation timestamp; changes create a new configuration version and require the same gates.

## 9. Report contract (JSONL plus human summary)

Emit one JSON object per report row, followed by a manifest object. Required fields:

```json
{
  "schema_version": "ob-optimization-1",
  "run_id": "...", "population": "live|live_parity_paper|simulated",
  "split": "train|validation|test|window-YYYYMMDD-YYYYMMDD",
  "symbol": "BTC-USD", "strategy": "order_book",
  "model_branch": "baseline", "config_hash": "...",
  "source_dataset_id": "...", "code_commit": "...",
  "start_time_utc": "...", "end_time_utc": "...",
  "starting_cash": 10000.0, "starting_equity": 10000.0,
  "label_definition": "forward_mid_return:H=...",
  "cost_scenario": {"fee_bps": 0, "spread_bps": 0, "slippage_bps": 0},
  "parameters": {},
  "n_decisions": 0, "n_intents": 0, "n_submitted": 0,
  "n_rejected": 0, "n_blocked": 0, "n_unknown": 0,
  "n_completed": 0, "n_open": 0,
  "signal_strength": {"mean": null, "median": null, "p05": null, "p95": null},
  "expected_return_gross_quote": null, "expected_return_net_quote": null,
  "realized_pnl_gross_quote": null, "realized_pnl_net_quote": null,
  "avg_win_net_quote": null, "avg_loss_net_quote": null,
  "expectancy_net_quote_per_trade": null, "profit_factor_net": null,
  "max_drawdown_percent": null, "trade_frequency_per_day": null,
  "intent_reject_rate": null, "intent_block_rate": null,
  "coverage_percent": null, "ci95": {},
  "eligibility": "eligible|insufficient_data|data_quality_failure|not_comparable",
  "gates": {"sample": false, "net_expectancy": false, "drawdown": false,
             "cost_invariants": false, "parity": false, "overall": false}
}
```

The manifest must list schema version, source and artifact hashes, split boundaries/purge gap, random seeds, cost scenarios, parameter grid, missingness/duplicate counts, and the exact gate thresholds. The human summary must include baseline-vs-candidate deltas, confidence intervals, worst-window values, coverage, failure reasons, and a clear `insufficient_evidence` conclusion when any gate is unavailable.

## 10. Promotion and high-risk review

This protocol is report-only. No optimization result may alter live configuration, model activation, order sizing, routing, or execution behavior automatically. Any live-affecting change requires an independent high-risk review covering data leakage, cost modeling, operational failure modes, rollback, and exposure limits; reviewer approval must be recorded before merge or deployment. A green backtest, paper result, or CI run is not approval for live trading. When diagnostics are absent, the correct decision is fail closed: do not promote and do not describe the result as low risk.
