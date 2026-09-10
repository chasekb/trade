# Deterministic Strategy Expectancy Fixture Manifest

Date: 2026-08-23

## Scope

This manifest is evaluation-only. It is consumed by
`defaultStrategyExpectancyPartitions()` and does not load, write, or override
live trading configuration.

## Partitions

| Partition | Samples | Time range | Purpose |
| --- | ---: | --- | --- |
| `train-2026-01` | 6 | 2026-01-05T00:00:00Z–00:05:00Z | Calibration window |
| `validation-2026-02` | 6 | 2026-02-05T00:00:00Z–00:05:00Z | Candidate validation |
| `test-2026-03` | 6 | 2026-03-05T00:00:00Z–00:05:00Z | Final chronological holdout |

The complete manifest contains 18 unique fixture identifiers. Partitions and
fixtures are returned in stable vector order; timestamps are strictly
increasing across the complete manifest. No fixture identifier or outcome is
reused between partitions.

## Coverage

- Symbols: `BTC-USD`, `ETH-USD`, and `SOL-USD`.
- Strategies: SMA, EMA, RSI, Bollinger, MACD, stochastic, Fibonacci, DCA,
  and buy-and-hold.
- Model branches: `pca` and `transformer`.
- Accepted intents: positive directional edge above the configured hurdle.
- Rejected intents: weak signal strength and unavailable expected-return data.
- Blocked intents: explicit fixture risk hold and fee-negative edge.
- Directional gates: positive expected return for buys and negative expected
  return for sells are both included.
- Cost gates: round-trip fee, spread, and slippage are applied as decimal
  fractions by the shared profitability diagnostic.

## Normalization assumptions

Prices are ordered oldest-to-newest and the last value is the current value.
Expected returns, fees, spread, and slippage are decimal fractions (for
example, `0.015` means 1.5%). `realized_pnl` is already net of execution costs
and is used only after the shared diagnostic marks an intent actionable.
Zero-PnL blocked/rejected rows are excluded from win/loss denominators.

## Reproducibility

The fixture constructors are deterministic and contain no clock, random-number,
exchange, database, or environment input. Repeated calls return the same
partition names, fixture IDs, timestamps, prices, metadata, and sample counts.