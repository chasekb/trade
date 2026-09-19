# Browser evidence: Coinbase live-data paper session

Capture date: 2026-09-19 UTC. Dashboard: `http://localhost:3000/` (`Trading Dashboard`). Backend was reached through the running local Compose/runtime stack. This was a browser reproduction using the rendered Simulated Trading controls; no live order mode or Coinbase order submission was enabled.

## Reproduction steps

1. Opened the dashboard and clicked the rendered `Simulated Trading` tab.
2. Selected `Coinbase live-data paper mode` (`execution_mode=live_parity`).
3. Selected `Universe`, then `Custom`, and entered: `BTC-USD,ETH-USD,SOL-USD,ADA-USD,DOT-USD,XRP-USD,LTC-USD`.
4. Kept strategy `ML-Enhanced Order Book` (`ml_enhanced_orderbook`).
5. Selected the first/current most recent Transformer model shown by the UI: `transformer_model_1789834654` (dated 2026-09-19), and `Model Type=Transformer`.
6. Clicked the rendered `Start Trading` button at 2026-09-19T16:54:30.018Z.
7. Observed the widget and API state window, then clicked `Stop Trading` at 2026-09-19T16:55:46.146Z. The stop response was HTTP 200 and the browser returned to inactive controls.

## Exact serialized start payload

```json
{
  "symbols": ["BTC-USD", "ETH-USD", "SOL-USD", "ADA-USD", "DOT-USD", "XRP-USD", "LTC-USD"],
  "strategy": "ml_enhanced_orderbook",
  "strategy_type": "ml_enhanced_orderbook",
  "parameters": {
    "position_size_mode": "percent",
    "position_size_value": 1,
    "initial_portfolio_size": 10000,
    "training_model_type": "transformer",
    "execution_mode": "live_parity",
    "diagnostics_enabled": true
  },
  "strategy_params": {
    "position_size_mode": "percent",
    "position_size_value": 1,
    "initial_portfolio_size": 10000,
    "training_model_type": "transformer",
    "execution_mode": "live_parity",
    "diagnostics_enabled": true
  },
  "max_positions": 100,
  "position_size_percent": 1,
  "position_size": 0.01,
  "position_update_interval": 5,
  "immediate_start": true,
  "batch_size": 3,
  "initial_balance": 10000,
  "capital": 10000,
  "initial_portfolio_size": 10000
}
```

The start request was `POST /api/trading/simulated/start`, HTTP 200. The returned session ID was `sim_1789836871_5`. The selected model ID is frontend state; it was not serialized into the start request, which carried `training_model_type=transformer`.

## Observed results

The initial UI snapshot shortly after start showed a genuine zero-trade state: seven selected/pending symbols, zero generated signals, zero executable intents, zero fills, zero trades, and $0.00 P&L. That was an early/startup snapshot, not a terminal outcome.

The session continued long enough for the backend worker to complete 27 ticks. The HTTP 200 stop response reported:

- selected symbols: 7
- quote requests: 189; quote successes: 189; quote failures: 0
- signals evaluated: 189; signals generated: 102; signals not generated: 87
- ticks completed/started: 27/27; last tick outcome: `completed`
- last tick: 2026-09-19T16:55:45.786Z; stop request: 2026-09-19T16:55:46.146Z
- cadence target: 1000 ms; observed worker tick max: 5885.93 ms; mean worker-tick duration from response histogram: approximately 1769.25 ms (`sum_ms=47769.80891 / count=27`)
- final available balance: $9818.10; current capital: $9999.37

Therefore this fresh browser run did **not** reproduce a terminal zero-trade result. It reproduced an early zero-trade/pending widget state, followed by generated signals and a changed balance/capital before stop. The prior API evidence window on the branch recorded a separate seven-symbol zero-trade session; this browser evidence supersedes the previous browser blocker but does not prove that zero-trade behavior is stable.

## Frontend request/query/WebSocket evidence

The browser instrumentation observed:

- `POST /api/trading/simulated/start` at 16:54:30.018Z.
- repeated `GET /api/simulated-trading/status` and `GET /api/orderbook/simulated-signals?...session_id=sim_1789836871_5` requests, with the signal request carrying all seven symbols and display pagination (`page=1&per_page=10`).
- `GET /api/simulated-trading/sim_1789836871_5/diagnosis` requests.
- `POST /api/trading/simulated/stop` at 16:55:46.146Z, HTTP 200, followed by a final status readback.
- The React WebSocket attempted `ws://cpp-backend:8080/ws` and immediately emitted `error` then close code `1006` in this browser context. No WebSocket event payload was observed. HTTP polling/diagnosis remained the evidence source.

The order-book widget displayed seven selected symbols. At the initial snapshot it showed `Pending evaluation` for all seven and zero signals/trades; after the worker progressed, the stop response showed 102 generated signals. No Coinbase authenticated order endpoint was called, and the UI explicitly displayed that live-parity paper mode never submits Coinbase orders.

## Safety and closeout

Both paper sessions started during this investigation were stopped through the rendered `Stop Trading` control. The final seven-symbol session returned HTTP 200 from the stop endpoint and was inactive afterward. No source code was changed and no local build/test command was run.

This artifact records the browser flow, exact request payload, identifiers, timestamps, polling/WebSocket behavior, and the failed terminal-zero-trade reproduction honestly. It should not be interpreted as evidence that the requested zero-trade invariant holds for the current runtime.
