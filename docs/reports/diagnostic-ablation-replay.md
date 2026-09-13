# Reproducible diagnostic ablation replay

This offline harness replays recorded candidate decisions for all strategy families
and compares the same dataset and explicit cost model in three modes:

- `disabled`: diagnostics are ignored.
- `report-only`: diagnostics are counted but never gate execution.
- `factored`: unavailable or below-threshold diagnostics block the candidate.

Missing diagnostics are represented by `unavailable_diagnostics`; they are never
converted to a zero score. Results are grouped by strategy and buy/sell direction.
The harness does not import exchange clients or order executors and always emits
`live_orders_enabled: false`.

Reproduce the checked-in example from a fresh checkout (Python 3.11+):

    python tools/replay_diagnostic_ablation.py \
      --input data/replay/diagnostic_ablation_fixture.jsonl \
      --json-out docs/reports/diagnostic-ablation-example.json \
      --markdown-out docs/reports/diagnostic-ablation-example.md

The fee rate, spread, slippage, and factoring threshold can be overridden, but
must remain identical across the three modes within one invocation. The JSON
contains `schema_version`, cost assumptions, all three runs, and
`meaningful_regressions`. A regression is reported when factoring blocks an
execution or changes expectancy by at least 10% (with a 0.001 minimum absolute
change). `—` in Markdown/`null` in JSON means that a metric has no observations;
it does not mean zero.

Input contract (JSONL): `timestamp`, `strategy`, `direction`, `entry_price`, and
`exit_price` are required. `diagnostic_score` is optional; omission is the
unavailable case. Prices and scores are numeric. This fixture is synthetic and
versioned specifically for deterministic smoke/replay checks, not a performance
claim or a live-trading dataset.
