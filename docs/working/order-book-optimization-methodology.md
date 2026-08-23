# Order-book and strategy optimization methodology

Status: experimental protocol only. This document defines an offline, report-only method for choosing defaults and per-symbol overrides. It does not change production parameters, submit orders, alter the selected universe, or authorize deployment. Any live-affecting implementation requires independent high-risk trading/accounting review and explicit approval.

## 1. Objective and baseline

The primary objective is risk-adjusted net expectancy after all costs, not signal count. A candidate is eligible only if it preserves fail-closed account, exchange, notional, pending-order, universe, and explicit-live-enable blockers.

The baseline is the current configuration captured at the start of an experiment, evaluated on the identical rows, symbols, timestamps, capital, and execution assumptions as every candidate. The baseline artifact must include the effective parameter JSON, source revision, data snapshot identifier, fee schedule, spread/slippage assumptions, and model branch. Do not compare a candidate with a different universe, data window, or fill policy.

Use the deterministic `StrategyExpectancyHarness` fixtures as a smoke/regression baseline. They verify signal generation, directional profitability diagnostics, and blocked fee-negative intents, but are not evidence of live profitability. Historical/live-parity evidence is required for promotion.

## 2. Populations and row contract

Every input row has a stable `row_id`, `timestamp_utc`, `symbol`, `strategy`, `model_branch`, `mode`, `side`, `signal_strength`, expected-return fields, cost fields, intent/fill status, and realized outcome fields. `mode` is exactly one of:

- `live`: authoritative exchange observations and fills; never backfilled with simulated fills.
- `live_parity_paper`: live market/order-book observations passed through the same signal, sizing, cost, and blocker logic, with no exchange submission. This is the preferred safe tuning population.
- `simulated`: replay or synthetic rows. They may be used for coverage and sensitivity, but cannot support a live claim by themselves.

Normalize timestamps to UTC, symbols to the exchange's exact product identifier, fractions to decimal units (0.015, not 1.5), PnL to USD, and prices/quantities to the recorded precision. Preserve raw values and a normalization-warning column. Reject impossible rows (non-positive price/notional, non-finite numeric fields, unknown side/mode, duplicate `row_id`) rather than silently repairing them.

A signal row is generated when the strategy emits buy or sell; hold/warming-up/unknown rows remain in the denominator for coverage diagnostics but not signal success. An intent is generated after signal and sizing decisions. A fill is a completed entry/round trip with a realized outcome. A rejected or blocked intent is retained with one primary reason and optional secondary reasons; blockers are not treated as strategy losses.

For live-parity paper, use captured market data and the same fee, spread, slippage, minimum-net-PnL, position-limit, account-readiness, and pending-order rules as live, but assert that the dispatch path is disabled. For simulated rows, label synthetic assumptions explicitly and never merge them into live claims.

## 3. Splits, fixtures, and leakage controls

Prefer chronological walk-forward evaluation. Sort by event time and construct, for each fold, a train/tune interval followed by an embargo and an untouched evaluation interval. The embargo is at least the maximum label/match horizon (currently 300 seconds where signal-to-trade matching uses that window), plus any holding-period look-ahead used by the outcome label. Require:

`max(train event time) < min(test signal time) - embargo`.

Use three chronological roles: calibration/tuning (60%), selection/validation (20%), and final evaluation (20%), subject to enough observations; never inspect final metrics while selecting parameters. Better still, use at least three rolling walk-forward folds with expanding train windows and fixed validation/test horizons. Fit thresholds, expected-return calibration, scaling, and imputation only on the train portion of each fold.

A row, signal, trade, or order-book snapshot may occur in only one role. Group all rows belonging to one round trip and its label horizon together. Do not let the same signal or trade appear in both modes or folds. Do not shuffle time series, interpolate future prices, use future spread/fees to gate a past signal, or select a symbol override because of its final evaluation result.

Fixtures must include: positive and negative buy/sell outcomes; zero-PnL outcomes; missing expected return; weak signal; fee-negative edge; spread and slippage stress; no-volatility/warming-up indicators; blocked account/exchange intents; duplicate and stale matches; and sparse symbols. Fixtures are deterministic, versioned, and used for contract tests only. Any candidate that fails a directional or fail-closed fixture is rejected regardless of aggregate metrics.

## 4. Grouping and aggregation

Report every metric at these levels, with `n_rows`, `n_signals`, `n_intents`, `n_fills`, and `n_blocked` alongside it:

1. overall and mode (`live`, `live_parity_paper`, `simulated`);
2. symbol;
3. strategy;
4. model branch (baseline, heuristic, regressor, transformer, or exact configured branch name);
5. symbol × strategy × model branch × mode;
6. side (buy/sell);
7. spread, volatility, liquidity, imbalance, UTC session, and signal-strength buckets;
8. expected-return and signal-to-fill-age buckets;
9. blocker reason and execution outcome.

Aggregate PnL by summing monetary outcomes; never average per-symbol ratios into an overall ratio. For pooled metrics, recompute from pooled numerators/denominators. Include exposure and elapsed time so frequency comparisons are fair.

## 5. Exact metric definitions

Let `i` denote a filled, closed round trip unless stated otherwise. Let `pnl_i` already be net realized USD PnL after trading fees, modeled spread, and modeled slippage. Let `gross_pnl_i` be before those costs, and `cost_i = gross_pnl_i - pnl_i`.

- **Signal strength:** the strategy output `s_i`, clamped to [0, 1] by the existing contract. Report mean, median, quantiles, and bucket counts; do not interpret it as a probability unless calibrated.
- **Directional expected return:** `e_i = expected_return_fraction` for buy and `e_i = -expected_return_fraction` for sell. Hold has no directional edge. Missing/non-finite expected return is unavailable, not zero and not high confidence.
- **Required edge:** `h_i = max(0, fee_fraction) + max(0, spread_fraction) + max(0, slippage_buffer_fraction)`. All are round-trip fractions using the same notional convention.
- **Fee-adjusted expected return:** `faer_i = e_i - h_i`. A signal is profitability-actionable only when `faer_i > 0` and it clears the strength threshold. Equality is a failure.
- **Realized PnL:** `pnl_i = exit proceeds - entry cost - actual/modelled fees - spread cost - slippage cost`, in USD. Report gross PnL, each cost component, and net PnL separately.
- **Average win:** `sum(pnl_i where pnl_i > 0) / count(pnl_i > 0)`. Zero PnL is excluded.
- **Average loss:** `sum(abs(pnl_i) where pnl_i < 0) / count(pnl_i < 0)`. Report as a positive magnitude; also report signed mean loss separately when useful. Zero PnL is excluded.
- **Expectancy:** `sum(pnl_i) / n_filled_closed`. This is net USD per closed trade; also report return expectancy `sum(pnl_i / entry_notional_i) / n`.
- **Profit factor:** `gross_winning_pnl / abs(gross_losing_pnl)`. If losses are zero and wins are positive, report `infinity` plus a `no_losses` warning; if both are zero, report `null` with `degenerate_no_pnl`.
- **Drawdown:** order fills by timestamp, build cumulative net PnL from zero (or explicitly reported starting equity), track the running peak, and take `max(peak - equity)`. Report maximum drawdown in USD and, when starting equity is known and positive, as a percentage. Do not reset at group boundaries unless the report says so.
- **Trade frequency:** `n_filled_closed / elapsed_days` for a fixed UTC window, plus signals/intents per day. Never substitute raw signal count for executed frequency.
- **Rejected/blocked intent rate:** `n_blocked / n_intents`. Also report `n_blocked / n_signals` and a reason distribution. Separate strategy-quality blockers (weak strength, unavailable edge, negative fee-adjusted edge) from live-only blockers (account, exchange, pending order, min notional, position/session limit).
- **Win rate:** `100 * n_positive_pnl / (n_positive_pnl + n_negative_pnl)`, excluding zero PnL and expressed as 0–100 percent.
- **Cost drag:** `sum(cost_i) / sum(abs(gross_pnl_i))` when the denominator is positive; report null otherwise. Costs must never be negative in a gate calculation.

Confidence intervals should use a block bootstrap by day or trade cluster, preserving time dependence. Report a 95% interval for expectancy, average win/loss, profit factor where defined, and drawdown; do not claim significance from independent-row assumptions.

## 6. Minimum evidence and degenerate groups

A group is `eligible` only when it has at least 100 closed fills, at least 30 winners and 30 losers, at least 20 distinct UTC days, and at least 10 observations in each required side/mode slice. The overall live/live-parity combined promotion population must have at least 300 closed fills and 30 distinct days. These are evidence gates, not targets for increasing trading.

Groups with 30–99 fills are `sparse`: report them, use them for diagnosis, and inherit the global/default setting; never select a symbol override. Groups below 30 fills, missing a side, missing a cost component, or containing only wins/losses are `insufficient` or `degenerate`. Null is the correct value for undefined ratios. Missing rows cannot be counted as zero PnL or successful blockers. If a mode has no fills, report signal/intent/blocker counts and mark outcome metrics unavailable.

Use hierarchical shrinkage only for reporting or ranking support; a sparse symbol cannot override the global decision. A symbol override must independently pass the final untouched evaluation and be stable in at least two walk-forward folds.

## 7. Candidate parameter ranges

Search only the following bounded ranges. Values are inclusive and must respect semantic ordering (short < long, oversold < overbought, MACD fast < slow). The current UI defaults are the baseline; these bounds are an experiment contract, not permission to widen production inputs.

| Strategy/branch | Parameter | Search range and step |
|---|---|---|
| SMA/EMA | short_window | 2–100, integer |
| SMA/EMA | long_window | 5–200, integer; greater than short |
| RSI | window | 5–50, integer |
| RSI | overbought / oversold | overbought 60–90; oversold 10–40; integer; oversold < overbought |
| Bollinger | window | 5–100, integer |
| Bollinger | std_dev | 1.0–3.0, step 0.1 |
| MACD | fast_window / slow_window / signal_window | fast 5–50; slow 10–100; signal 5–30; integer; fast < slow |
| Stochastic | k_window / d_window | k 5–50; d 2–10; integer |
| Stochastic | overbought / oversold | overbought 70–90; oversold 10–30; integer; oversold < overbought |
| Fibonacci | fib_lookback_period | 10–100, integer |
| Fibonacci | fib_levels | fixed candidate sets from {0.236, 0.382, 0.5, 0.618, 0.786}; no arbitrary post-hoc levels |
| Fibonacci | fib_confirmation_candles | 1–5, integer; report-only until the backend implements the field |
| DCA | interval_hours | 1–168, integer |
| DCA | amount | $10–$10,000, step $10; report-only sizing comparison |
| Buy-and-hold | amount | $100–$100,000, step $100; benchmark only |
| Order book / ML | confidence_threshold | 0–1, step 0.1 |
| Order book / ML | fallback_to_baseline | `true` or `false`; `true` is the fail-safe candidate |
| Order book / ML | order_book_level | 1–3, integer |
| Order book / ML | trade_history_limit | 10–1,000, integer; data-coverage control, not an alpha knob |
| Order book | bid_ask_spread_threshold | 0.01%–1.00%, step 0.01% |
| Order book | volume_imbalance_threshold | 0.1–0.9, step 0.1 |
| Order book | large_trade_threshold | $1,000–$100,000, step $1,000 |
| Order book | data_analysis_mode | `recent`, `all`, or `sampled`; fixed before evaluation |
| Order book | recent_data_limit | 10–1,000, integer; data-coverage control, not an alpha knob |
| Order book | sampling_ratio | 0.01–1.0, step 0.01; must be seeded and fixed before splitting |
| Order book | max_symbols_per_request | 10–10,000, integer; request fan-out diagnostic only |
| Order book | max_universe_size | 1–5,000, integer; do not use to change the user-selected universe |
| Order book | round_trip_fee_percent | 0–5%, step 0.1%; stress only, never lower than authoritative fee schedule |
| Order book | slippage_buffer_percent | 0–5%, step 0.1%; stress only, never lower than measured conservative slippage |
| Order book | min_orderbook_signal_strength | 0–1, step 0.01 |
| Order book | minimum_net_pnl_usd | $0–$100, step $0.01 |
| Position/session | max_positions_per_session | 1–1,000, integer; safety cap comparison only |
| Position sizing | position_size_mode | `dollar` or `percent`; report-only comparison |
| Position sizing | position_size_value / position_size_percent | $10–$10,000 or 0.1%–100%, respectively; preserve configured cap and never optimize live exposure without risk review |

`ml_server_url`, fallback enablement, data mode, sampling ratio, recent/trade-history limits, max symbols per request, max universe size, and `allow_unprofitable_trades` are not alpha knobs. They are either infrastructure, sampling, universe, or safety controls. Do not optimize them against PnL. Keep the user-selected universe unchanged; never add a universe cap as an experimental convenience. `allow_unprofitable_trades=true` is prohibited for live and live-parity promotion and may be used only in an explicitly labeled diagnostic simulation.

## 8. Cost and directional gate invariants

For every candidate and every side:

1. Buy requires `expected_return_fraction > 0`; sell requires `expected_return_fraction < 0`.
2. `directional_edge = buy ? expected_return : -expected_return`.
3. `required_edge = fee + spread + slippage`, with each negative input clamped to zero and each component reported.
4. The candidate may pass only when `directional_edge - required_edge > 0` and strength meets its threshold.
5. Increasing fee, spread, or slippage must never increase fills, net expected return, expectancy, or selected risk. A monotonicity test evaluates a low-cost and higher-cost copy of every fixture.
6. Unavailable/non-finite expected return, missing cost, or unknown side fails closed and is attributed as unavailable, not profitable.
7. Reported realized PnL must include costs exactly once. Portfolio-level total fees replace, rather than add to, any per-trade fee sum.
8. A candidate cannot win by removing blocked intents, changing the universe, or counting blocked intents as losses.

## 9. Selection rules

Select the global default by the median walk-forward validation result, then confirm on untouched evaluation. Primary ordering is: (1) positive net expectancy with the entire 95% interval above zero where sample size permits; (2) no worse profit factor and no worse maximum drawdown than baseline; (3) no worse average loss; (4) cost and blocked-intent invariants pass; (5) stable direction across folds and modes. Use higher trade frequency only as a tie-breaker after these conditions.

A per-symbol override additionally requires eligible symbol evidence, two or more stable folds, live/live-parity evaluation not worse than baseline, and a minimum practical frequency of one closed fill per 7 UTC days. Prefer the global default when the improvement is within the bootstrap interval or is not stable across sides. Never select from simulated-only evidence.

Record the chosen candidate, runner-up, baseline, tie-break reason, and every failed gate. A candidate that raises signal or trade count while worsening expectancy, average loss, profit factor, drawdown, or cost-adjusted outcomes is rejected even if accuracy or raw PnL improves in one slice.

## 10. Report schema

Produce one machine-readable row per evaluation group with these fields:

| Field | Type/unit | Meaning |
|---|---|---|
| `experiment_id`, `source_revision`, `data_snapshot` | string | Reproducibility identifiers |
| `mode`, `symbol`, `strategy`, `model_branch`, `side` | string | Group dimensions |
| `fold`, `window_start_utc`, `window_end_utc`, `embargo_seconds` | string/int | Time split and leakage controls |
| `parameter_json` | object | Exact candidate parameters |
| `n_rows`, `n_signals`, `n_intents`, `n_fills`, `n_blocked` | integer | Denominators and coverage |
| `signal_rate`, `trade_frequency_per_day`, `blocked_intent_rate` | number | Rates defined above |
| `mean_signal_strength`, `mean_directional_edge_fraction`, `mean_fee_adjusted_expected_return_fraction` | number/fraction | Signal diagnostics |
| `gross_pnl_usd`, `fees_usd`, `spread_cost_usd`, `slippage_cost_usd`, `net_pnl_usd` | number/USD | Outcome and cost decomposition |
| `average_win_usd`, `average_loss_usd`, `expectancy_usd`, `profit_factor` | number/USD or null | Objective metrics |
| `win_rate_percent`, `max_drawdown_usd`, `max_drawdown_percent` | number | Risk metrics; win rate is 0–100 |
| `ci95_expectancy`, `ci95_profit_factor`, `ci95_drawdown` | two-number arrays | Block-bootstrap intervals |
| `sample_status`, `warnings`, `gate_status`, `blocker_counts` | enum/array/object | Eligibility, missingness, and safety evidence |

The human summary must state baseline versus selected values for net expectancy, average win/loss, profit factor, drawdown, frequency, fees/spread/slippage drag, signals, fills, and blocked/rejected intent rate. It must list sparse/degenerate groups, leakage checks, failed invariants, and the explicit decision (`promote_global`, `promote_symbol_override`, or `no_change`).

Example interpretation: “Candidate B raised BTC-USD signals 18% and fills 7%, but median live-parity expectancy fell from $4.10 to $3.20, average loss worsened from $8.00 to $9.40, and the higher-spread fold failed the cost monotonicity gate. Decision: no change. ETH-USD had 42 fills and is sparse, so no symbol override is eligible.” This is a rejection, not an optimization success.

## 11. Reproducibility and approval checklist

Before any result is considered complete:

- [ ] Baseline and candidate use the same selected universe, rows, capital, timestamps, and fill model.
- [ ] Exact source revision, configuration, data snapshot, random seed, code version, fee schedule, and cost assumptions are recorded.
- [ ] Walk-forward boundaries and embargo are recorded; no train/evaluation overlap exists.
- [ ] Live, live-parity-paper, and simulated results are separate; live claims use live/live-parity evidence.
- [ ] All metrics use the formulas in this document and null handling is explicit.
- [ ] Minimum sample and sparse/degenerate warnings are present.
- [ ] Fee/spread/slippage directional and monotonicity fixtures pass.
- [ ] Blocked intents are attributed separately from signal-quality and live-only blockers.
- [ ] No production code, live parameter, exchange account, or user universe was changed by the experiment.
- [ ] Independent high-risk review approves any proposed live-affecting code or configuration change before deployment.
