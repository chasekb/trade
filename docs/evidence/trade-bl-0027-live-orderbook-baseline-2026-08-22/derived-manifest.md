# TRADE-BL-0027 derived baseline manifest (derived-metrics phase)

Evidence ID: `trade-bl-0027-live-orderbook-baseline-2026-08-22`
Frozen source capture: 2026-08-23T03:37:51Z
Source timezone: UTC
Effective log window: 2026-08-22T15:51:55.995Z through 2026-08-23T03:24:09.281Z

## Files and SHA-256

- `raw_tmux_excerpt.log`: `d406d4018bfe9e88f681c2cbc7a1729ba7e65e416f9ce4464400a29b02d5126d`
- `derived_metrics.json`: `d89918def2371c8f2e64057328f6f6486c3b56bb19a27a317d49295a8bee2151`
- `metrics_report.md`: `47bc9464dae6d9657ee5bdcdd7de32ef5587698b8931f77d47ebb64fac5448f1`

## Reproduction

From repository root:

```sh
python3 tools/trade_bl_0027_baseline.py \
  --input docs/evidence/trade-bl-0027-live-orderbook-baseline-2026-08-22/raw_tmux_excerpt.log \
  --output docs/evidence/trade-bl-0027-live-orderbook-baseline-2026-08-22/derived_metrics.json
python3 -m json.tool docs/evidence/trade-bl-0027-live-orderbook-baseline-2026-08-22/derived_metrics.json >/dev/null
sha256sum docs/evidence/trade-bl-0027-live-orderbook-baseline-2026-08-22/*
```

The derivation is standard-library-only and analysis-only. It counts 18 timestamped order-book fetch failures across 18 distinct observed symbols, all logged with one retry and `category=tls`. It deliberately leaves quote coverage, signal, execution, fill, fee, and PnL metrics unavailable because the selected universe and joined terminal outcome rows are absent; the runtime outcome query failed on missing `individual_trades.is_closing_leg`.

No live session was started, no order was submitted, no account or production state was changed, and no profitability claim is made.
