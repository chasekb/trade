# Reproducible diagnostic ablation replay

`tools/replay_diagnostic_ablation.py` is deterministic and offline. It compares diagnostics `disabled`, `report-only`, and `factored` modes over the same JSONL decisions and explicit fee, spread, and slippage assumptions for all strategy families.

Missing diagnostics are counted as `unavailable_diagnostics`, never zero. JSON and Markdown outputs include entries, exits, blocked executions, unavailable counts, average win/loss, net expectancy, profit factor, drawdown, trade frequency, and meaningful regressions by strategy and buy/sell direction. No exchange/order code is imported; output states `live_orders_enabled: false`.

Fresh checkout command (Python 3.11+):

    python tools/replay_diagnostic_ablation.py --input data/replay/diagnostic_ablation_fixture.jsonl --json-out docs/reports/diagnostic-ablation-example.json --markdown-out docs/reports/diagnostic-ablation-example.md

The fixture is synthetic deterministic smoke data, not a performance claim. Override cost or threshold arguments only when keeping values identical across modes. Required JSONL fields are `timestamp`, `strategy`, `direction`, `entry_price`, and `exit_price`; omitted `diagnostic_score` is the unavailable case. A meaningful regression is a new block or expectancy change >=10% (minimum absolute change 0.001) from report-only to factored.
