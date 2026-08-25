# TRADE-BL-0027 baseline evidence manifest

- Evidence ID: `trade-bl-0027-live-orderbook-baseline-2026-08-22`
- Frozen at: `2026-08-23T03:37:51Z`
- Repository commit inspected: `8af7838c9112e4f88c0f358504877d054ce9eb0c`
- Time zone: UTC. Every runtime timestamp below is explicitly marked UTC; no local-time conversion was applied.
- Status: **incomplete for live-PnL closeout**. The available artifact is a reproducible runtime excerpt and code/schema manifest, not a qualifying live order-book outcome dataset.

## Frozen source artifact

Raw evidence is preserved at:

- `docs/evidence/trade-bl-0027-live-orderbook-baseline-2026-08-22/raw_tmux_excerpt.log`

The raw excerpt was obtained from the live host's attached tmux session and pane with:

```sh
tmux capture-pane -pt 0:7.0 -S -10000 | grep -E 'sim_[0-9]+|selected|symbols|strategy|execution_mode|live_parity|ml_enhanced|Transformer|Start Trading|Trading session|session started'
tmux capture-pane -pt 0:7.0 -S -10000 | grep -E 'individual_trades|order_book_signals|is_closing_leg|pnl|fees|trade|fill|blocked|execution_analysis'
```

The pane is ephemeral; the checked-in excerpt is the immutable copy used by downstream workers. It contains the strongest available runtime evidence found under `~/.hermes` and the active host tmux session, but it does not contain the original frontend request payload or a database export.

## Candidate time window

- Runtime observations begin: `2026-08-22T15:51:55.995Z` (repeated outcome-query failure).
- Transformer readiness observed: `2026-08-22T16:01:07.250Z` (lookback 60, 353 features).
- Simulated worker observed: `2026-08-22T16:08:43.785Z`, session `sim_17874`.
- First observed order-book fetch failure: `2026-08-22T16:09:46.632Z`, `YB-USD`.
- Last observed order-book fetch failure in the excerpt: `2026-08-23T03:24:09.281Z`, `ZK-USD`.
- Effective excerpt window: `2026-08-22T15:51:55.995Z` through `2026-08-23T03:24:09.281Z`.

This window is **not a live-session window**: the only identified worker is explicitly `Simulated trading worker`, and no live session ID or `live_order_execution` state was captured. It must not be used to claim live realized-PnL results.

## Universe and inclusion rules

- Selected universe: **unavailable**. No serialized Start Trading request, session-status payload, or selected-symbol list was present in the frozen runtime evidence.
- Symbols with observed failed order-book fetches (observations only, not proof of selection): `YB-USD`, `FIGHT-USD`, `ALGO-USD`, `SHIB-USD`, `MORPHO-USD`, `PNUT-USD`, `AUDIO-USD`, `AI-USD`, `RLS-USD`, `XYO-USD`, `LSETH-USD`, `NEX-USD`, `STX-USD`, `FOX-USD`, `JASMY-USD`, `STRK-USD`, `PYTH-USD`, `ZK-USD`.
- Inclusion rule for this freeze: retain only timestamped lines from the captured pane that identify the worker/session, model readiness, outcome-query failure, or an order-book fetch failure. Do not promote an observed failed-fetch symbol into the selected universe.
- Exclusion rules: exclude all synthetic simulated rows from live baseline claims; exclude all source-code-only fields from runtime metrics; exclude all rows without a captured symbol and timestamp; exclude secrets, cookies, credentials, and request headers.

## Runtime/configuration fields recovered

| Field | Value | Provenance |
|---|---|---|
| Worker mode | simulated worker (not live) | raw tmux excerpt |
| Session | `sim_17874` | raw tmux excerpt |
| Model | Transformer loaded; lookback `60`; features `353` | raw tmux excerpt |
| Exchange/order-book source | Not captured | no request/config payload in source artifact |
| Strategy name | Not captured | no request/config payload in source artifact |
| `execution_mode` | Not captured | no request/config payload in source artifact |
| `live_order_execution` | Not captured; do not assume enabled | no request/config payload in source artifact |
| Position sizing / capital | Not captured | no request/config payload in source artifact |
| Fee rate / spread / slippage buffer / required edge | Not captured | no signal payload or strategy config captured |
| Retry behavior | Runtime lines report `retries=1` for failed fetches | raw tmux excerpt |

## Expected schema and source-of-truth code

The order-book signal contract documented by the inspected repository includes, where available: `signal_id`, `session_id`, `symbol`, `signal_type`, `signal`, `signal_generated`, `signal_strength`, `price`, `timestamp`, `signal_reason`, `data_status`, `spread`, `volume`, bid/sell volume, imbalance ratio, prediction, criteria analysis, ML analysis, expected-return availability/value, fee-adjusted expected return, required edge, profitability-gate result/reason, and execution analysis.

Execution/outcome records are expected to include symbol, strategy type, PnL, fees, and closing-leg classification. The runtime attempted:

```sql
SELECT symbol, strategy_type, pnl, fees, is_closing_leg
FROM individual_trades
WHERE timestamp >= 1787327514;
```

The query failed because `individual_trades.is_closing_leg` was absent in the runtime database. Repeated failures continued through the observed window. Therefore no outcome rows are included in this freeze.

Primary code paths and immutable hashes at the inspected commit:

```text
1292699608f76484115ced5f2aa23db8b80af53882b4950099bb5f72a8959389  src/trading/LiveTradingService.cpp
15b37d3465666f853dd449b37c6741b8c66b3260f3ce3f8f140c7e79817a7fd8  src/trading/SimulatedTradingService.cpp
66f4d53d300f2e10a51ae9a6cd7f555741300e8cb8240732b6354d9dc0cacea6  src/api/PredictController.cpp
efd74b078f46f51c12d19166090dc600f20cb663e07f756219e55a3c9b6dfb45  docs/reports/live-orderbook-execution-attribution-closeout-2026-08-04.md
057f217b449b7de765a3d519909a1582ce4e20a39f406a1deebac889bb9a9c18  docs/reports/live-simulated-orderbook-throughput-normalization-closeout-2026-08-05.md
```

## Data availability and gaps

Unavailable from `~/.hermes`, the inspected tmux pane, and repository artifacts:

- selected symbol universe and exact serialized request;
- live session ID, live strategy name, and live configuration;
- successful quote/order-book snapshots, bid/ask/depth/imbalance values, and quote freshness;
- generated live signal rows and per-signal gate diagnostics;
- blocked intents, submitted orders, order IDs, fills, partial fills, and execution prices;
- fees, realized PnL, average win/loss, expectancy, profit factor, drawdown, and positive/negative/zero-PnL counts;
- a queryable/exported `order_book_signals` or `individual_trades` dataset for this window;
- reliable outcome reconciliation because `is_closing_leg` was missing in the runtime database.

The raw evidence supports only these bounded observations: a simulated worker ran with a Transformer configuration; repeated outcome queries failed on a missing column; and selected order-book fetch attempts (unproven universe membership) failed with TLS/network errors and one retry. It does not establish why the live universe had no positive-PnL trades.

## Rerun instructions for the next worker

1. From the trade repository/runtime host, capture the exact frontend or API start request without secrets, including selected symbols, strategy, `execution_mode`, model ID, and session ID.
2. Record the start and end timestamps in UTC and preserve the complete selected-symbol list separately from the display page.
3. Query the active signal endpoint and export the raw JSON for the same session/window; preserve schema and response timestamps.
4. Query the live outcome/reconciliation endpoint or database only after confirming the runtime schema includes the required closing-leg field. Use a bounded, timestamped query and export raw rows, including symbol, strategy, side, signal ID/intent ID where available, order ID, fill quantity/price, fees, and realized PnL.
5. Hash every raw export with `sha256sum`, append the hashes and exact commands to this manifest, and only then compute baseline metrics.
6. Keep live execution opt-in unchanged and do not submit orders merely to create evidence.
