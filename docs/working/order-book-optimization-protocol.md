# Order-book optimization protocol and report schema

Status: experimental, report-only, and non-production. This protocol is the definitive contract for offline comparison of order-book and related strategy parameters. Running it must not alter production code, live configuration, the selected user universe, exchange-account state, order submission, or deployment behavior. An optimization result is evidence only; it is not approval to change a live parameter. Any live-affecting implementation or configuration change requires independent high-risk trading/accounting review and explicit approval before deployment.

This document reconciles the signal-path inventory in `docs/reports/order-book-signal-path-inventory.md` and the methodology in `docs/working/order-book-optimization-methodology.md`. Where runtime names differ, the report contract uses the canonical names below.

## 1. Objective and baseline

The objective is risk-adjusted net expectancy after fees, spread, and slippage. Signal count, raw trade count, accuracy, or gross PnL cannot win a selection by themselves. Every comparison must report average realized win, average realized loss, expectancy, profit factor, drawdown, cost drag, frequency, and blocked/rejected intents.

The baseline is the effective current configuration captured before extraction:

- the exact selected symbol universe, in its original order;
- effective strategy, model branch, sizing, gate, capacity, and exit parameters;
- starting capital and account/session assumptions;
- identical source rows, timestamps, fill/label policy, and evaluation windows used by every candidate;
- authoritative fee schedule, modeled spread/slippage assumptions, and exchange precision/minimum-notional rules;
- source revision, model artifact/version, and data snapshot identifier.

The baseline is not a UI default unless the effective runtime configuration is identical. The baseline and every candidate must use the same universe and observations. A candidate that changes universe size, removes symbols, changes account safety gates, or changes fill semantics is invalid, not an improvement.

Deterministic unit fixtures are a contract smoke baseline only. They are not profitability or live evidence. Historical/live-parity evidence is required for any promotion recommendation.

## 2. Canonical populations and lifecycle rows

Every normalized row has a stable `row_id` and represents one observed lifecycle stage. The canonical `mode` values are:

- `live`: authoritative exchange observations, accepted/rejected orders, fills, fees, and account state. Never backfill missing exchange facts with simulated values.
- `live_parity_paper`: live public market/order-book observations passed through the same signal, sizing, cost, and blocker logic as live, with dispatch disabled and local paper settlement. Runtime `mode_ == "live_parity"` maps to this report value. It does not prove exchange acceptance, partial-fill behavior, exchange fees, or account reconciliation.
- `simulated`: replay or synthetic observations and local fills. Synthetic evidence may test sensitivity and coverage but cannot support a live claim by itself.

A lifecycle must preserve these statuses separately:

`observed quote -> signal/hold -> generated candidate -> pre-submit intent -> blocked or submitted -> exchange accepted/rejected/pending/non-fill -> fill -> closing outcome`.

A hold, model warm-up, missing expected return, or unknown strategy remains in coverage denominators but is not a successful signal. A pre-submit blocker is not a strategy loss. An exchange rejection, pending order, expired/non-fill, and closing loss are distinct outcomes. Each row has one `primary_blocker_or_outcome` and optional secondary details.

A closed fill is one completed round trip with an attributable entry and closing outcome. Opening legs, closing legs, exchange fills, and round trips are not interchangeable metrics. The protocol's objective metrics use closed round trips; coverage metrics use lifecycle rows and their explicit denominators.

## 3. Extraction and normalization

Extract, without changing production behavior:

1. Selected universe, effective parameters, session/run identifiers, mode, source revision, model artifact/version, and starting capital.
2. `order_book_signals` fields: session, symbol, signal id, side/type, signal strength, prediction timestamp, price/mid, spread, imbalance, best bid/ask, depth, volume, payload, and tick counters.
3. Execution analysis: generated candidate, expected-return availability, required edge, fee-adjusted edge, model status, sizing decision, and every blocker count/reason.
4. Order lifecycle: intent id or attribution key, submission time, acceptance/rejection, pending/non-fill state, fill time/price/quantity, partial-fill status, and exchange error classification.
5. `individual_trades`: entry/closing-leg marker, strategy, side, size, price, timestamp, gross PnL, fees, prediction fields, trade type, and session.
6. Account/portfolio snapshots needed to distinguish available cash/quantity, pending reservations, inherited holdings, and live-only safety blockers.

Use the strongest available join key. Prefer an explicit lifecycle/intent id; otherwise join by session, exact symbol, side, and prediction-to-order window, with the configured maximum signal-to-trade matching horizon of 300 seconds plus any declared holding-period label horizon. Ambiguous or duplicate matches are retained as `unmatched`/`ambiguous`, never silently assigned.

Normalize while preserving raw values and a `normalization_warnings` array:

- timestamps to UTC ISO-8601 plus epoch seconds;
- symbols to the exact exchange product identifier, without collapsing distinct products;
- percentage inputs to decimal fractions (`0.015`, not `1.5`), while retaining the source unit;
- PnL and costs to USD; prices, quantities, and notional at recorded precision;
- side to `buy` or `sell`, mode to the canonical values above, and status to the lifecycle enums;
- finite numeric fields and positive price/notional checks.

Reject the row from metric denominators with an explicit `invalid_input` warning for non-finite numbers, non-positive price/notional, unknown side/mode, missing required identity, or duplicate `row_id`. Do not repair, interpolate, or convert missing expected return or cost to zero. Quote failures remain `quote_unavailable` coverage outcomes and retain the selected symbol in universe coverage denominators.

## 4. Time splits, leakage controls, and fixtures

Use chronological walk-forward evaluation. For each fold, use expanding train/calibration data, a selection/validation interval, an embargo, and an untouched final evaluation interval. The hard boundary is:

`max(train_event_time) < min(test_signal_time) - embargo_seconds`.

Set `embargo_seconds` to at least 300 seconds plus the maximum holding-period/look-ahead used by the outcome label. Never shuffle. Fit thresholds, calibration, scaling, and imputation only on train data. Keep all rows for one round trip and its label horizon in one role. A signal, trade, snapshot, or row may occur in only one fold/mode role. Do not use final evaluation results to select a symbol override.

Use 60% calibration/tune, 20% validation/selection, and 20% final evaluation when the window supports it; otherwise use at least three expanding walk-forward folds with fixed validation/test horizons and mark the reduced design in `warnings`. Selection uses validation results only; final evaluation is read once for confirmation.

Versioned deterministic fixtures must cover:

- positive and negative buy and sell outcomes, including exact-zero PnL;
- missing/non-finite expected return, weak strength, fee-negative edge;
- spread/slippage and higher-cost monotonicity stress;
- no-volatility, stale quote, model warming-up, inference exception, and unavailable edge;
- account, pending-order, minimum-notional, position/session, and disabled-live blockers;
- exchange rejection, partial fill, pending/non-fill, duplicate/ambiguous match, and sparse symbols.

A candidate failing a directional, cost monotonicity, accounting, universe-preservation, or fail-closed fixture is rejected regardless of aggregate performance.

## 5. Comparison and grouping contract

Compare baseline and candidate on identical rows and split boundaries. Report each mode separately; report combined live and live-parity only as a clearly labeled promotion population. Never merge simulated outcomes into a live claim. Live-parity can validate signal/gate behavior against live quotes, but only live can validate authoritative exchange fills and actual fees.

Every report includes these grouping dimensions:

1. overall;
2. mode (`live`, `live_parity_paper`, `simulated`);
3. symbol;
4. strategy;
5. model branch (exact configured branch, including `heuristic-fallback`, ready classifier/regressor/transformer, `transformer-warming-up`, inference exception, or unavailable);
6. symbol × strategy × model branch × mode;
7. side (`buy`, `sell`);
8. spread, volatility, liquidity/depth, imbalance, UTC session, and signal-strength buckets;
9. expected-return and signal-to-fill-age buckets;
10. primary blocker reason and execution outcome.

Every group carries `n_rows`, `n_quotes`, `n_signals`, `n_intents`, `n_blocked`, `n_rejected`, `n_submitted`, `n_fills`, `n_closed_round_trips`, and elapsed UTC window. Pool monetary numerators before calculating ratios; never average per-symbol ratios to obtain an overall ratio. Include exposure and elapsed time so frequency comparisons are fair.

## 6. Cost, accounting, and metric formulas

For closed round trip `i`, `gross_pnl_i` is before costs and `net_pnl_i` is after all applicable costs. Costs are reported separately:

`net_pnl_i = gross_pnl_i - fee_i - spread_cost_i - slippage_cost_i`.

For live, use actual exchange fees and realized fill prices where available; missing actual components make the corresponding claim unavailable, not zero. For live-parity and simulation, use the declared modeled schedule and assumptions. Apply costs exactly once. Portfolio-level `total_fees` replaces a sum of per-trade fees; it is never added to that sum.

For side-normalized expected return, preserve `raw_expected_return_fraction`, then compute:

- buy: `directional_edge_i = raw_expected_return_fraction`;
- sell: `directional_edge_i = -raw_expected_return_fraction`.

A missing/non-finite expected return is unavailable. Required edge is:

`required_edge_i = max(0, fee_fraction_i) + max(0, spread_fraction_i) + max(0, slippage_buffer_fraction_i)`.

`fee_adjusted_expected_return_i = directional_edge_i - required_edge_i`.

A candidate is actionable only when directional edge is positive, fee-adjusted edge is strictly greater than zero (equality fails), and strength clears the configured threshold. Negative cost inputs are clamped to zero for gating and reported as data warnings.

For closed round trips only:

- `average_win_usd = sum(net_pnl_i where net_pnl_i > 0) / count(net_pnl_i > 0)`;
- `average_loss_usd = sum(abs(net_pnl_i) where net_pnl_i < 0) / count(net_pnl_i < 0)` (positive magnitude; also report signed loss when useful);
- `expectancy_usd = sum(net_pnl_i) / n_closed_round_trips`;
- `return_expectancy = mean(net_pnl_i / entry_notional_i)`;
- `profit_factor = sum(gross winning net_pnl) / abs(sum(gross losing net_pnl))`; if no losses and wins exist, use `infinity` plus `no_losses`; if both are zero, use `null` plus `degenerate_no_pnl`;
- `win_rate_percent = 100 * positive_count / (positive_count + negative_count)`, excluding exact-zero PnL;
- `max_drawdown_usd`: timestamp-order cumulative net PnL from zero (or explicit starting equity), running peak minus equity, maximum; report percent only with known positive starting equity;
- `trade_frequency_per_day = n_closed_round_trips / elapsed_days`; also report signals, intents, and fills per day;
- `blocked_intent_rate = n_blocked / n_intents`, plus `blocked_per_signal = n_blocked / n_signals`; report rejected separately as `n_rejected / n_submitted`;
- `cost_drag = sum(fee + spread + slippage) / sum(abs(gross_pnl))` when the denominator is positive, otherwise null.

Use null for undefined ratios. Zero-PnL rows are not wins or losses and must not be silently converted to losses. Use day/trade-cluster block bootstrap for 95% intervals, preserving time dependence, and report intervals for expectancy, average win/loss, profit factor when defined, and drawdown.

Increasing fee, spread, or slippage in a fixture must never increase fills, net expected return, expectancy, or selected risk. Blocked intents are not losses, and a candidate cannot win by removing blockers, changing the universe, or counting blocked intents as unsuccessful trades.

## 7. Evidence eligibility and parameter search contract

A group is `eligible` only with at least 100 closed round trips, at least 30 winners and 30 losers, at least 20 distinct UTC days, and at least 10 observations in each required side/mode slice. The combined live/live-parity promotion population additionally requires at least 300 closed round trips and 30 distinct days. These are evidence gates, not reasons to increase trading.

Groups with 30–99 closed round trips are `sparse`: report them for diagnosis but inherit the global/default choice and cannot produce a symbol override. Groups below 30, missing a side, missing a required cost component, or containing only wins/losses are `insufficient` or `degenerate`; outcome metrics are null. A mode with no fills still reports coverage, signal, intent, and blocker metrics.

Search only these inclusive bounded ranges; semantic ordering constraints are mandatory:

| Family | Knob | Range |
|---|---|---|
| SMA/EMA | short_window | 2–100 integer |
| SMA/EMA | long_window | 5–200 integer, greater than short |
| RSI | window | 5–50 integer |
| RSI | overbought / oversold | 60–90 / 10–40 integer, oversold < overbought |
| Bollinger | window / std_dev | 5–100 integer / 1.0–3.0 step 0.1 |
| MACD | fast / slow / signal | 5–50 / 10–100 / 5–30 integer, fast < slow |
| Stochastic | k / d | 5–50 / 2–10 integer |
| Stochastic | overbought / oversold | 70–90 / 10–30 integer, oversold < overbought |
| Fibonacci | lookback / levels / confirmation_candles | 10–100 integer / fixed set {0.236,0.382,0.5,0.618,0.786} / 1–5 integer (confirmation report-only) |
| DCA | interval_hours / amount | 1–168 integer / $10–$10,000 step $10 (sizing comparison only) |
| Buy-and-hold | amount | $100–$100,000 step $100 (benchmark only) |
| Order-book/ML | confidence_threshold | 0–1 step 0.1 |
| Order-book/ML | fallback_to_baseline | true or false; true is fail-safe |
| Order-book/ML | order_book_level | 1–3 integer |
| Order-book/ML | trade_history_limit | 10–1,000 integer; coverage control |
| Order-book | bid_ask_spread_threshold | 0.01%–1.00% step 0.01% |
| Order-book | volume_imbalance_threshold | 0.1–0.9 step 0.1 |
| Order-book | large_trade_threshold | $1,000–$100,000 step $1,000 |
| Order-book | data_analysis_mode | recent, all, or sampled; fixed before evaluation |
| Order-book | recent_data_limit / sampling_ratio | 10–1,000 integer / 0.01–1.0 step 0.01, seeded |
| Order-book | max_symbols_per_request | 10–10,000 integer; fan-out diagnostic only |
| Order-book | max_universe_size | 1–5,000 integer; never changes selected universe |
| Order-book | round_trip_fee_percent / slippage_buffer_percent | 0–5% step 0.1%; stress only, never below authoritative values |
| Order-book | min_orderbook_signal_strength | 0–1 step 0.01 |
| Order-book | minimum_net_pnl_usd | $0–$100 step $0.01 |
| Capacity | max_positions_per_session | 1–1,000 integer; safety comparison only |
| Sizing | position_size_mode | dollar or percent; report-only comparison |
| Sizing | position_size_value / position_size_percent | $10–$10,000 / 0.1%–100%; preserve configured exposure cap |

`ml_server_url`, fallback enablement, data mode, sampling/recent/history limits, request/universe limits, and `allow_unprofitable_trades` are infrastructure, sampling, universe, or safety controls, not alpha knobs. `allow_unprofitable_trades=true` is prohibited for live/live-parity promotion and allowed only in explicitly labeled diagnostic simulation. No experiment may add a cap or reduce the requested universe.

## 8. Selection and override rules

Select the global default using the median walk-forward validation result, then confirm it on untouched evaluation. In order, require:

1. positive net expectancy with the entire 95% interval above zero where sample size permits;
2. no worse profit factor and no worse maximum drawdown than baseline;
3. no worse average loss;
4. all cost, directional, accounting, universe, and fail-closed fixtures pass;
5. stable direction across folds, modes, and sides.

Use higher frequency only after these gates as a tie-breaker. If still tied, choose (a) lower average loss, then (b) lower drawdown, then (c) fewer blocked/rejected live intents only when strategy quality and safety coverage are unchanged, then (d) the simpler/current baseline configuration. Record baseline, winner, runner-up, tie-break reason, and every failed gate.

A per-symbol override additionally requires eligible symbol evidence, at least two stable walk-forward folds, live/live-parity result not worse than baseline, and at least one closed round trip per seven UTC days. Improvement within the bootstrap interval, instability across sides/modes, or simulated-only evidence selects the global default instead. Sparse symbols always inherit the global default.

Allowed decisions are exactly `promote_global`, `promote_symbol_override`, and `no_change`. `promote_*` is a recommendation for review, never an automatic write or deployment.

## 9. Machine-readable report schema

Emit one JSON object per evaluation group (JSONL is preferred). Fields below are required; nullable fields must be `null`, never omitted. Arrays/objects use JSON types shown.

| Field | JSON type | Unit/allowed values | Aggregation level |
|---|---|---|---|
| `experiment_id`, `source_revision`, `data_snapshot`, `model_artifact`, `code_version` | string | reproducibility identifiers | report |
| `mode` | string | `live`, `live_parity_paper`, `simulated` | group |
| `symbol`, `strategy`, `model_branch`, `side` | string/null | exact identifiers; side `buy`/`sell`/`all` | group |
| `group_dimensions` | object | bucket labels and grouping keys | group |
| `fold` | string | `train`, `validation`, `evaluation`, or fold id | group |
| `window_start_utc`, `window_end_utc` | string | ISO-8601 UTC | group |
| `embargo_seconds` | integer | seconds | fold |
| `parameter_json` | object | exact effective candidate parameters | candidate |
| `baseline_parameter_json` | object | exact effective baseline | candidate |
| `random_seed` | integer/null | seed, required for sampled/bootstrap runs | experiment |
| `fee_schedule_id`, `cost_assumptions` | string/object | authoritative/model schedule and assumptions | experiment |
| `n_rows`, `n_quotes`, `n_signals`, `n_intents`, `n_blocked`, `n_rejected`, `n_submitted`, `n_fills`, `n_closed_round_trips`, `distinct_utc_days` | integer | explicit denominators | group |
| `elapsed_days`, `exposure_usd` | number | days/USD | group |
| `signal_rate`, `signals_per_day`, `intents_per_day`, `fills_per_day`, `trade_frequency_per_day`, `blocked_intent_rate`, `blocked_per_signal`, `rejection_rate` | number/null | rates; percentages are decimal fractions except named `_percent` | group |
| `mean_signal_strength`, `mean_directional_edge_fraction`, `mean_fee_adjusted_expected_return_fraction` | number/null | decimal fractions | group |
| `gross_pnl_usd`, `fees_usd`, `spread_cost_usd`, `slippage_cost_usd`, `net_pnl_usd` | number/null | USD; null when required cost/outcome evidence is unavailable | group |
| `average_win_usd`, `average_loss_usd`, `signed_average_loss_usd`, `expectancy_usd`, `return_expectancy`, `profit_factor` | number/null | USD or ratio; infinity serialized as `null` with warning if strict JSON | group |
| `win_rate_percent`, `max_drawdown_usd`, `max_drawdown_percent`, `cost_drag` | number/null | percent is 0–100; drawdown USD/percent; cost ratio | group |
| `ci95_expectancy_usd`, `ci95_average_win_usd`, `ci95_average_loss_usd`, `ci95_profit_factor`, `ci95_drawdown_usd` | two-number array/null | lower/upper bootstrap interval | group |
| `sample_status` | string | `eligible`, `sparse`, `insufficient`, `degenerate` | group |
| `warnings` | array[string] | null/cost/leakage/sample warnings | group |
| `gate_status` | string | `pass` or `fail` | candidate/group |
| `blocker_counts`, `outcome_counts` | object | reason -> integer | group |
| `decision` | string | `promote_global`, `promote_symbol_override`, `no_change` | report |

Example JSONL rows (illustrative values, not evidence):

```json
{"experiment_id":"ob-2026-08-24-001","source_revision":"9e33e60","data_snapshot":"coinbase-utc-2026-08-01-2026-08-23","model_artifact":"heuristic-fallback","code_version":"trade-2026.08.24","mode":"live_parity_paper","symbol":"BTC-USD","strategy":"orderbook","model_branch":"heuristic-fallback","side":"buy","group_dimensions":{"spread_bucket":"0.10%-0.20%","volatility_bucket":"medium","utc_session":"14-16","signal_strength_bucket":"0.40-0.60"},"fold":"evaluation","window_start_utc":"2026-08-15T00:00:00Z","window_end_utc":"2026-08-23T23:59:59Z","embargo_seconds":300,"parameter_json":{"min_orderbook_signal_strength":0.22,"round_trip_fee_percent":1.5,"slippage_buffer_percent":0.2},"baseline_parameter_json":{"min_orderbook_signal_strength":0.22},"random_seed":null,"fee_schedule_id":"coinbase-public-schedule-v1","cost_assumptions":{"spread":"observed","slippage":"0.002"},"n_rows":1800,"n_quotes":1750,"n_signals":220,"n_intents":120,"n_blocked":100,"n_rejected":0,"n_submitted":0,"n_fills":20,"n_closed_round_trips":20,"distinct_utc_days":9,"elapsed_days":9.0,"exposure_usd":50000.0,"signal_rate":0.1222,"signals_per_day":24.44,"intents_per_day":13.33,"fills_per_day":2.22,"trade_frequency_per_day":2.22,"blocked_intent_rate":0.8333,"blocked_per_signal":0.4545,"rejection_rate":null,"mean_signal_strength":0.47,"mean_directional_edge_fraction":0.0041,"mean_fee_adjusted_expected_return_fraction":0.0019,"gross_pnl_usd":120.0,"fees_usd":30.0,"spread_cost_usd":18.0,"slippage_cost_usd":12.0,"net_pnl_usd":60.0,"average_win_usd":12.0,"average_loss_usd":6.0,"signed_average_loss_usd":-6.0,"expectancy_usd":3.0,"return_expectancy":0.0006,"profit_factor":2.0,"win_rate_percent":60.0,"max_drawdown_usd":18.0,"max_drawdown_percent":null,"cost_drag":0.5,"ci95_expectancy_usd":[-1.0,7.0],"ci95_average_win_usd":[8.0,16.0],"ci95_average_loss_usd":[3.0,9.0],"ci95_profit_factor":[0.8,3.4],"ci95_drawdown_usd":[10.0,28.0],"sample_status":"insufficient","warnings":["fewer_than_100_closed_round_trips","fewer_than_20_utc_days","live_parity_does_not_prove_exchange_fill"],"gate_status":"fail","blocker_counts":{"negative_fee_adjusted_edge":50,"pending_order":20,"minimum_net_pnl":30},"outcome_counts":{"closed":20,"zero_pnl":2},"decision":"no_change"}
{"experiment_id":"ob-2026-08-24-001","source_revision":"9e33e60","data_snapshot":"coinbase-utc-2026-08-01-2026-08-23","model_artifact":"model-42","code_version":"trade-2026.08.24","mode":"live","symbol":"BTC-USD","strategy":"ml_enhanced_orderbook","model_branch":"classifier-regressor-ready","side":"all","group_dimensions":{"spread_bucket":"all","volatility_bucket":"all","utc_session":"all"},"fold":"evaluation","window_start_utc":"2026-08-15T00:00:00Z","window_end_utc":"2026-08-23T23:59:59Z","embargo_seconds":300,"parameter_json":{"confidence_threshold":0.6},"baseline_parameter_json":{"confidence_threshold":0.6},"random_seed":null,"fee_schedule_id":"coinbase-account-schedule-v1","cost_assumptions":{"fees":"actual_exchange","spread":"fill_attribution","slippage":"fill_attribution"},"n_rows":9000,"n_quotes":8900,"n_signals":1200,"n_intents":700,"n_blocked":500,"n_rejected":20,"n_submitted":200,"n_fills":180,"n_closed_round_trips":150,"distinct_utc_days":23,"elapsed_days":23.0,"exposure_usd":400000.0,"signal_rate":0.1333,"signals_per_day":52.17,"intents_per_day":30.43,"fills_per_day":7.83,"trade_frequency_per_day":6.52,"blocked_intent_rate":0.7143,"blocked_per_signal":0.4167,"rejection_rate":0.1,"mean_signal_strength":0.55,"mean_directional_edge_fraction":0.006,"mean_fee_adjusted_expected_return_fraction":0.002,"gross_pnl_usd":2400.0,"fees_usd":300.0,"spread_cost_usd":180.0,"slippage_cost_usd":120.0,"net_pnl_usd":1800.0,"average_win_usd":25.0,"average_loss_usd":12.0,"signed_average_loss_usd":-12.0,"expectancy_usd":12.0,"return_expectancy":0.003,"profit_factor":2.08,"win_rate_percent":66.67,"max_drawdown_usd":140.0,"max_drawdown_percent":1.4,"cost_drag":0.25,"ci95_expectancy_usd":[5.0,19.0],"ci95_average_win_usd":[19.0,31.0],"ci95_average_loss_usd":[9.0,15.0],"ci95_profit_factor":[1.5,2.7],"ci95_drawdown_usd":[100.0,190.0],"sample_status":"eligible","warnings":[],"gate_status":"pass","blocker_counts":{"negative_fee_adjusted_edge":220,"insufficient_cash":180,"max_positions":100},"outcome_counts":{"accepted":190,"rejected":20,"closed":150},"decision":"no_change"}
```

## 10. Human summary and reproducibility checklist

The human summary must show baseline versus selected candidate for net expectancy, average win/loss, profit factor, drawdown, frequency, gross PnL, each fee/spread/slippage component and total cost drag, signals, fills, blocked intent rate, rejected/submitted rate, and mode. It must explicitly list sparse/degenerate groups, quote coverage failures, unmatched/ambiguous rows, leakage/split checks, failed invariants, confidence intervals, and sample warnings. It must state one decision: `promote_global`, `promote_symbol_override`, or `no_change`.

Required reproducibility metadata:

- experiment id, source revision/commit, code version, model artifact/version;
- exact raw data snapshot/query and extraction timestamp;
- selected universe and effective parameter JSON for baseline and candidates;
- UTC window boundaries, fold assignments, embargo, matching horizon, and label definition;
- fee schedule id, actual/modelled cost components, precision/minimum-notional rules, starting capital, and fill policy;
- random seed, sampler/bootstrap method, software/runtime versions, and command/config digest;
- counts for every lifecycle stage, invalid/duplicate/unmatched rows, and blocker/outcome reason maps;
- fixture version and pass/fail result, plus report schema version.

Closeout requires a clean report-only diff, `git diff --check`, and (when changes are delivered) exact pushed-SHA remote CI evidence. Compilation does not establish strategy quality or fill parity. No production behavior may change. Any live-affecting follow-up remains blocked until independent high-risk review and explicit approval are recorded.
