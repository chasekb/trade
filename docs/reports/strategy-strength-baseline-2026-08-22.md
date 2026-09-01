# Strategy-strength baseline evaluation

Date: 2026-08-22
Status: analysis-only, evidence-limited

## Reproduction

This evaluation does not import or modify production trading code. It uses only Python 3's standard library.

```text
python3 tools/strategy_strength_baseline.py \
  --input data/strategy_expectancy_fixtures.jsonl \
  --output docs/reports/strategy-strength-baseline-2026-08-22.json
```

Inputs and outputs:

- Input: `data/strategy_expectancy_fixtures.jsonl`, a transparent JSONL projection of the deterministic fixtures in `src/trading/StrategyExpectancyHarness.cpp:172-198`.
- Evaluator: `tools/strategy_strength_baseline.py`.
- Machine-readable output: `docs/reports/strategy-strength-baseline-2026-08-22.json`.
- Dependencies: Python 3 standard library only; no package, database, exchange, or network access.

The projection preserves the fixture realized outcomes and deliberately leaves unavailable dimensions null. It is not historical, paper, or live trading evidence. The production formulas and harness source were not changed.

## Cohort rules

- Strength bins are `[0.0,0.2)`, `[0.2,0.4)`, `[0.4,0.6)`, `[0.6,0.8)`, and `[0.8,1.0]`. Values outside 0..1 and missing values are not assigned a bin.
- Missing values are retained as a `missing` cohort and never imputed.
- Exact canonical-JSON duplicate rows are excluded after the first occurrence. The run observed 11 input rows, zero invalid rows, and zero duplicates.
- Minimum cohort size is 5. Smaller cohorts are reported but labelled `insufficient evidence`.
- Net PnL is used only when the input row has `net_pnl`. Zero outcomes would remain in the sample denominator but not win/loss denominators.
- Gross PnL and fee scenarios require explicit gross and fee fields. They are not reconstructed from net outcomes or assumed fee rates.
- The confidence interval is exploratory: for the nine observed net outcomes the script uses a two-sided t critical value of 2.306 with 8 degrees of freedom. This is not a claim of independent identically distributed trades.

## Observed fixture-level result

| metric | result |
|---|---:|
| source rows | 11 |
| rows with net outcomes | 9 |
| net expectancy / mean | 13.2222 |
| average winning net outcome | 13.2222 |
| average losing net outcome | unavailable (no filled losing fixture) |
| win rate | 100.0% (9/(9+0)) |
| max drawdown | 0.0 |
| net expectancy 95% interval | [9.6627, 16.7818] |
| gross metrics | insufficient evidence |

The nine positive rows sum to 119.0 in the fixture PnL units. The two fee-negative regression fixtures are blocked and therefore have no realized outcome in the analysis denominator. These are deterministic harness fixtures, not a trade sample.

## Requested dimensions

| dimension | result | status |
|---|---|---|
| indicator strength | all 11 missing; no strength buckets | insufficient evidence |
| symbol | all 11 missing | insufficient evidence |
| market regime | all 11 missing | insufficient evidence |
| holding period | all 11 missing | insufficient evidence |
| fee scenario | all 11 missing; no gross/fee decomposition | insufficient evidence |

Consequently, monotonicity across strength buckets, saturation/clipping, and high-loss regimes cannot be measured. No unsupported inference is made. Per-strategy labels present in the source fixture set are `sma`, `ema`, `rsi`, `bollinger`, `macd`, `stochastic`, `fibonacci`, `dca`, and `buyandhold`, but each has fewer than the minimum cohort threshold when treated individually and lacks outcome dimensions needed for the requested stratification.

## Interpretation and follow-up contract

Observed: the checked-in harness provides deterministic signal/diagnostic regression coverage and nine positive realized fixture values, while two fee-negative cases are blocked before fill. It does not persist signal strength, symbol, regime, holding period, gross PnL, fees, or an explicit signal-to-outcome key.

Recommendation: do not calibrate or change production formulas from this baseline. A valid next evaluation needs an immutable, read-only export containing at least `signal_id`, `timestamp_utc`, `strategy`, `signal_strength`, `symbol`, `market_regime`, `holding_period`, `gross_pnl`, `fees`, `spread`, `slippage`, `net_pnl`, `filled`, and `blocked_reason`, with one-to-one signal attribution and duplicate audit fields. Re-run the unchanged evaluator against that export; retain the declared bins and minimum cohort threshold unless a later analysis pre-registers a different choice.

## Verification

- The evaluator was executed successfully with the exact command above and wrote the JSON result.
- No local CMake, compiler, Docker, frontend build, or test command was run.
- No production formula file was modified.
