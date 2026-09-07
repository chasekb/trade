Order-book parameter sweep (offline research artifact)

Purpose

This report records a reproducible, fixture-backed walk-forward sweep. It is not a deployment recommendation and does not alter live-affecting defaults. The harness is scripts/orderbook_parameter_sweep.py.

Method

- Input: deterministic 240-row fixture, seed 20260907, three symbols (BTC-USD, ETH-USD, SOL-USD), and baseline/ML branch labels.
- Split: first 120 rows are historical/train context; last 120 rows are evaluation rows. No row after the evaluation timestamp is used to decide a signal.
- Sweep size: 1,296 combinations across min_orderbook_signal_strength, orderbook_expected_return_scale_percent, round_trip_fee_percent, slippage_buffer_percent, max_spread_percent, imbalance_weight, and position_size_percent.
- Candidate acceptance: directional expected return must exceed fee, slippage, and observed spread. Buy and sell directions are evaluated separately; no absolute-value shortcut is used.
- Fail-closed rule: a candidate with negative overall expectancy is ineligible. A segment with at least eight trades and negative expectancy also makes it ineligible, so a larger count cannot win by admitting losing trades.
- Metrics: average win, average loss, expectancy, profit factor, maximum drawdown, trade frequency, rejected intent rate, blocked intent rate, and symbol/branch segments.

Evidence

Manifest: artifacts/orderbook-sweep/manifest.json
Candidate records: artifacts/orderbook-sweep/candidates.jsonl
Input fixture: artifacts/orderbook-sweep/fixture.csv

The manifest records the input SHA-256, grid, row counts, safety flags, baseline, selected candidate, and eligible-candidate count. The run produced 1,296 candidates from 240 rows; 450 candidates passed the fail-closed eligibility rule.

Before/after evaluation summary

Baseline parameters: minimum strength 0.20, expected-return scale 100%, round-trip fee 0.10%, slippage buffer 0.05%, max spread 0.20%, imbalance weight 1.0, position size 2%.

Baseline evaluation: 21 trades; average win 0.00123390; average loss -0.00167419; expectancy 0.00040302; profit factor 1.8425; max drawdown 0.00725108; trade frequency 0.1750; rejected intent rate 0.5000; blocked intent rate 0.3250. ETH-USD baseline had negative expectancy (-0.00127341) on six trades, which is a warning and not a basis for a per-symbol override.

Selected global fixture candidate: minimum strength 0.40, expected-return scale 80%, round-trip fee 0.10%, slippage buffer 0.03%, max spread 0.10%, imbalance weight 0.8, position size 4%.

Selected evaluation: 11 trades; average win 0.00372121; no losses; expectancy 0.00372121; profit factor is null because there were no losses; max drawdown 0; trade frequency 0.0917; rejected intent rate 0.1083; blocked intent rate 0.8000.

Recommendation and limits

Use the selected candidate only as an offline research default for a future, separately approved validation run. Do not copy it into live configuration. The apparent improvement is accompanied by a much lower trade count and a high blocked-intent rate, and the selected candidate has fewer than eight trades in every symbol/branch segment. Therefore no per-symbol override is justified. The fixture is synthetic and deliberately small; it cannot establish production profitability, confidence intervals, execution quality, or model-branch stability. A real follow-up must use timestamped, read-only historical observations with closing-leg/PnL attribution and a pre-registered holdout period, then repeat the same fail-closed eligibility and sample-size gates.

Reproduction

python scripts/orderbook_parameter_sweep.py --output-dir artifacts/orderbook-sweep
python scripts/orderbook_parameter_sweep.py --input path/to/observations.csv --output-dir artifacts/orderbook-sweep-real

CSV input columns are: timestamp, symbol, branch, imbalance, spread_percent, raw_strength, expected_return_percent, future_return_percent, directional_gate. The harness writes only research artifacts and never reads credentials or live configuration.
