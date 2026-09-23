# TRADE-BL-0027 live order-book baseline metrics

Status: evidence-gated, analysis-only. This artifact does not establish live profitability.

## Dataset identity

- Evidence ID: `trade-bl-0027-live-orderbook-baseline-2026-08-22`
- Frozen source: `raw_tmux_excerpt.log` in this directory.
- Source capture: tmux pane `0:7.0`, captured 2026-08-23T03:37:51Z; timestamps are UTC.
- Effective excerpt window: 2026-08-22T15:51:55.995Z through 2026-08-23T03:24:09.281Z.
- Worker/session observed: simulated worker, `sim_17874`; no live session ID or selected-symbol payload was captured.
- Derivation: `python3 tools/trade_bl_0027_baseline.py --input docs/evidence/trade-bl-0027-live-orderbook-baseline-2026-08-22/raw_tmux_excerpt.log --output docs/evidence/trade-bl-0027-live-orderbook-baseline-2026-08-22/derived_metrics.json`

## Computed observations

| Metric | Result | Denominator / definition |
|---|---:|---|
| Order-book fetch failures | 18 | Timestamped `Failed to fetch order book` lines in the excerpt |
| Unique symbols with failed fetch | 18 | Distinct symbols among those failure lines |
| Retry count distribution | 18 at `retries=1` | Failure lines only |
| Failure category distribution | 18 TLS/network | Logged `category=tls` lines |
| Successful quote/order-book responses | unavailable | The excerpt has no success rows |
| Quote freshness / age | unavailable | No successful quote timestamps or selected universe |
| Coverage rate | unavailable | Selected-symbol denominator is absent; failed symbols must not be treated as the selected universe |
| Database outcome-query failures | 1 observed event | Query failed because `individual_trades.is_closing_leg` was absent |
| Transformer readiness events | 1 | Lookback 60, 353 features |
| Generated signals | unavailable | No signal rows or signal IDs |
| Signal strength / expected return | unavailable | No signal payloads |
| Fee-adjusted expected return / spread / slippage / required edge | unavailable | No signal or configuration payloads |
| Blocked intents / submitted orders / fills | unavailable | No execution rows or order IDs |
| Fees / realized PnL | unavailable | No joined terminal outcome rows |
| Positive / negative / zero-PnL counts | unavailable | No terminal outcomes; query failure cannot be converted to zero |
| Average win / average loss / expectancy | unavailable | No realized-PnL sample |
| Profit factor / drawdown | unavailable | No realized-PnL sample |

The 18 observed symbols are `YB-USD`, `FIGHT-USD`, `ALGO-USD`, `SHIB-USD`, `MORPHO-USD`, `PNUT-USD`, `AUDIO-USD`, `AI-USD`, `RLS-USD`, `XYO-USD`, `LSETH-USD`, `NEX-USD`, `STX-USD`, `FOX-USD`, `JASMY-USD`, `STRK-USD`, `PYTH-USD`, and `ZK-USD`. They are failed-fetch observations only, not a reconstructed selected universe.

## Denominator and missingness policy

- Do not calculate fetch-failure rate, quote coverage, signal rate, fill rate, or blocker rate without a captured selected-universe list and request-attempt denominator.
- Do not infer successful quotes, HOLDs, blocked intents, orders, fills, or zero-PnL trades from missing rows.
- The missing `is_closing_leg` schema field prevents reliable terminal-outcome reconciliation; all PnL distribution metrics remain unavailable.
- Symbol and signal-strength/expected-return cohorts cannot be computed because no signal rows and no confirmed selected-symbol universe are present.

## Reproducibility and validation

The parser is standard-library-only and preserves raw evidence separately from derived output. It validates that the frozen excerpt yields exactly 18 order-book failure rows and 18 distinct failure symbols; JSON syntax validation and `git diff --check` passed. No live session was started, no order was submitted, no account or production state was mutated, and no local build/test was run.

## Interpretation boundary

This is a bounded simulated-worker/log baseline, not a live order-book performance window. It supports the observations above and identifies the missing data dependency, but it does not confirm that the live order-book universe had no positive-PnL trades or identify the cause. A qualifying follow-up requires an immutable selected-symbol payload, successful and failed quote rows, signal/diagnostic rows, intent/order/fill linkage, fees, closing-leg classification, and realized PnL in one UTC-bounded session.
