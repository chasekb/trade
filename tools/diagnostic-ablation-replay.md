# Reproducible diagnostic ablation replay

`tools/replay_diagnostic_ablation.py` is a deterministic, offline replay harness
for all live/simulated strategy families. It compares diagnostics `disabled`,
`report-only`, and `factored` modes against the same JSONL decisions and the same
explicit fee, spread, and slippage model.

Missing diagnostics are counted as `unavailable_diagnostics`, never as zero. The
JSON report also distinguishes null metrics (no executed observations) from zero,
and includes entries, exits, blocked executions, wins/losses, average win/loss,
net expectancy, profit factor, drawdown, trade frequency, and regression flags by
strategy and buy/sell direction. The harness imports no exchange or order code and
always emits `live_orders_enabled: false`.

Fresh-checkout command (Python 3.11+):

    python tools/replay_diagnostic_ablation.py \
      --input data/replay/diagnostic_ablation_fixture.jsonl \
      --json-out docs/reports/diagnostic-ablation-example.json \
      --markdown-out docs/reports/diagnostic-ablation-example.md

The committed fixture is synthetic deterministic smoke data, not a performance
claim. Override `--fee-rate`, `--spread-bps`, `--slippage-bps`, or
`--diagnostic-threshold` only when comparing runs with the same values.

Input JSONL requires `timestamp`, `strategy`, `direction`, `entry_price`, and
`exit_price`; `diagnostic_score` is optional and omission is the unavailable case.
A meaningful regression is any new block or an expectancy change >=10% (minimum
absolute change 0.001) between report-only and factored modes.
