# Coinbase live-data paper zero-trade investigation

Status: evidence reconciliation; no production behavior change
Capture date: 2026-09-19 UTC
Scope: rendered Simulated Trading widget, Coinbase public market data, paper execution only

## Executive conclusion

The one-minute-looking widget state is display/startup behavior, not an intentional one-minute frontend poll. The frontend polls simulated status, signals, and diagnosis every 3 seconds (`frontend/hooks/useTrading.ts:855-894`); the simulated worker targets one-second sleeps but each tick includes sequential Coinbase order-book requests, retries, signal generation, and persistence (`src/trading/SimulatedTradingService.cpp:2560-2629`). The source therefore permits a long observed interval when a tick is slow, but neither source nor the fresh browser capture proves a one-minute exchange/provider cadence.

The fresh browser reproduction showed an initial genuine zero-trade/pending snapshot, then 27 completed ticks, 189/189 quote successes, 102 generated signals, and changed balance/capital before Stop Trading. It did not reproduce a terminal zero-trade outcome. A separate prior API window did show all seven symbols refreshed, Transformer warming at 20/60, all signals held, and zero intents/fills. That prior no-trade result is explained by model warm-up plus the profitability/no-signal gates—not by missing Coinbase data, sizing, cash, pending orders, or a proven one-minute UI cadence.

No live Coinbase order mode was enabled and no Coinbase authenticated order was submitted. Both paper sessions were stopped through the rendered Stop Trading control.

## Reproduction context and exact browser evidence

Frontend: `http://localhost:3000/`, rendered `Trading Dashboard` → `Simulated Trading`.

Steps:

1. Select `Coinbase live-data paper mode` (`execution_mode=live_parity`).
2. Select `Universe` → `Custom` and enter `BTC-USD,ETH-USD,SOL-USD,ADA-USD,DOT-USD,XRP-USD,LTC-USD`.
3. Keep `ML-Enhanced Order Book` (`ml_enhanced_orderbook`).
4. Select the current Transformer model shown by the UI: `transformer_model_1789834654`, model type `Transformer`.
5. Click Start Trading at `2026-09-19T16:54:30.018Z`.
6. Observe the widget and HTTP polling state.
7. Click Stop Trading at `2026-09-19T16:55:46.146Z`; stop returned HTTP 200 and the UI became inactive.

Start request: `POST /api/trading/simulated/start`, HTTP 200.
Session: `sim_1789836871_5`.
The selected model ID is frontend state; the serialized request carried `training_model_type=transformer`, not the model ID.

The exact payload and request transcript are preserved in the checked-in browser artifact from commit `3795276cb975fefc89508c1615d37b848629d168`:
`docs/evidence/coinbase-paper-session-browser-2026-09-19/README.md` (remote branch `origin/wt/t_ca8e5b29-browser-evidence`).

## Runtime identifiers, timestamps, and measurements

Fresh browser session `sim_1789836871_5`:

- Start: `16:54:30.018Z`; stop request: `16:55:46.146Z`.
- Last completed tick: `16:55:45.786Z`.
- Selected symbols: 7.
- Quote requests/successes/failures: `189 / 189 / 0`.
- Signals evaluated/generated/not generated: `189 / 102 / 87`.
- Ticks completed/started: `27 / 27`; last tick outcome `completed`.
- Cadence target: 1000 ms; observed worker-tick maximum: 5885.93 ms.
- Worker-tick mean from response histogram: approximately 1769.25 ms (`47769.80891 / 27`).
- Final available balance: `$9818.10`; current capital: `$9999.37`.
- Initial rendered state: seven pending symbols, zero generated signals, zero intents, zero fills, zero trades, `$0.00` P&L. This was an early state, not the terminal session result.
- Browser WebSocket attempted `ws://cpp-backend:8080/ws`, then emitted error and close `1006`; no WebSocket event payload was observed. HTTP polling and diagnosis remained the evidence source.

Prior API runtime window used for per-symbol blocker attribution:

- Snapshot: `2026-08-23 04:34:31Z`, session `sim_1787459668`.
- Fresh polls: `04:34:47`, `04:34:52`, `04:34:57`; ticks `8`, `10`, `11`; evaluations `56`, `70`, `77`.
- Seven-symbol `last_success_at` timestamps advanced approximately every 1–2 seconds.
- Reconciliation: `market_data_refreshed=7`, `market_data_failed=0`, `signals_evaluated=14`, `signals_generated=0`, `paper_intents=0`, `fills=0`, `positions=0`, `pending_orders=0`, `execution_is_paper=true`, `mode=live_parity`, `cash_usd=10000`.
- Transformer state: 14 symbols warming at `20/60` history rows; current signal rows exposed feature width `353` rather than an actual zero-width input.
- Historical panes: tmux `0:7.0`; Transformer reload `2026-08-23 04:10:23`; historical `is_closing_leg` schema-error window `2026-08-22 15:51:55–16:08:38`; historical YB-USD TLS lead began `2026-08-22 16:09:46`.

## Per-symbol reconciliation

The table below uses the prior API window because it contains complete symbol-level diagnostics. The fresh browser artifact provides complete aggregate counts but does not serialize a per-symbol quote timestamp or per-symbol signal count; it must not be treated as stronger per-symbol evidence.

| Symbol | Data freshness / fetch result | Signal | Model/readiness | Gate or blocker | Paper intent | Fill / no-fill |
| --- | --- | --- | --- | --- | --- | --- |
| BTC-USD | Coinbase public quote refreshed; last-success advanced with the seven-symbol set (~1–2 s poll progression) | Hold / no executable signal | Transformer warming, `20/60` | profitability gate; warm-up context | 0 | 0 fills |
| ETH-USD | Coinbase public quote refreshed; no fetch failure | Hold / no executable signal | Transformer warming, `20/60` | profitability gate; warm-up context | 0 | 0 fills |
| SOL-USD | Coinbase public quote refreshed; no fetch failure | Hold / no signal | Transformer warming, `20/60` | no-signal gate | 0 | 0 fills |
| ADA-USD | Coinbase public quote refreshed; no fetch failure | Hold / no executable signal | Transformer warming, `20/60` | profitability gate; warm-up context | 0 | 0 fills |
| DOT-USD | Coinbase public quote refreshed; no fetch failure | Hold / no signal | Transformer warming, `20/60` | no-signal gate | 0 | 0 fills |
| XRP-USD | Coinbase public quote refreshed; no fetch failure | Hold / no signal | Transformer warming, `20/60` | no-signal gate | 0 | 0 fills |
| LTC-USD | Coinbase public quote refreshed; no fetch failure | Hold / no executable signal | Transformer warming, `20/60` | profitability gate; warm-up context | 0 | 0 fills |

The fresh browser run later generated 102 signals in aggregate and changed simulated balance/capital, so the table is intentionally labeled to the earlier zero-trade API window rather than incorrectly projecting its per-symbol gate state onto the later session.

## Source trace: widget versus producer cadence

Display and request path:

- `frontend/components/dashboard/SimulatedTradingPanel.tsx:575-601` prefers the canonical diagnosis snapshot and treats pagination as display-only.
- `frontend/hooks/useTrading.ts:855-894` polls simulated status, signals, and diagnosis every 3 seconds while enabled; stale times are 2 seconds for the simulated status/diagnosis queries.
- `frontend/hooks/useTrading.ts:899-1213` attempts WebSocket delivery and merges events into the canonical cache, but the browser capture saw immediate error/1006 close and no payload.
- `frontend/hooks/useTrading.ts:903-905,947-980` applies incoming events to the complete canonical model before projecting a visible page. A pending/zero row can therefore be a display snapshot while the producer continues running.
- `src/trading/SimulatedTradingService.cpp:3368` documents that live-data sessions fetch every selected symbol each worker tick and that response pagination controls display rows only.

Producer and exchange path:

- `src/trading/SimulatedTradingService.cpp:1001-1035` iterates selected symbols sequentially, permits up to two order-book attempts, and stops retries early for TLS, DNS, exchange-response, or cancellation classes.
- `src/trading/SimulatedTradingService.cpp:2568-2588` selects the live quote batch, fetches it, and records quote-batch duration/coverage before signal generation.
- `src/trading/SimulatedTradingService.cpp:2600-2615` generates the tick and flushes writes/orders outside the state mutex.
- `src/trading/SimulatedTradingService.cpp:2625-2629` finishes diagnostics and sleeps one second. The one-second sleep is not a one-minute scheduler; request latency, retries, persistence, and signal work can stretch total tick duration.
- `src/exchange/CoinbaseAdvancedClient.cpp:164-168` reuses the connection/TLS session between calls, avoiding a fresh handshake per request.

Classification: confirmed display/polling behavior plus sequential producer work; not confirmed as a one-minute Coinbase cadence. The browser's WebSocket failure is a separate transport/display-path observation. HTTP polling remained active and the worker produced successful quotes and signals, so WebSocket absence is not established as the cause of the early zero-trade view.

## Lead reconciliation

| Lead | Classification | Evidence and owner/action |
| --- | --- | --- |
| Coinbase TLS/network (especially historical YB-USD) | Separate open transport-reliability follow-up; ruled out for the current seven-symbol zero-trade window | Historical YB-USD TLS errors began `2026-08-22 16:09:46`. The current seven-symbol API window had `7/7` refreshed and `0` failures; the fresh browser run had `189/189` successes. Owner: runtime/exchange operator should collect a fresh symbol-level transport sample if the lead recurs. No Coinbase account mutation was performed. |
| Transformer readiness/input shape | Confirmed explanation for the earlier zero-trade window; the old “expected input dimension zero” interpretation is ruled out by current diagnostics | Earlier API evidence reported `20/60` warming and width `353`; current source emits explicit `warming_up`, expected lookback, and expected feature width (`src/trading/SimulatedTradingService.cpp:1574-1595,1890-1938`). Owner: model/runtime operator must allow warm-up or provide a fresh run with ready state before attributing no-trade to execution gates. |
| `is_closing_leg` schema mismatch | Source-side remediation present; deployed-schema/runtime verification remains a separate open gate, not a current cause of the zero-trade window | Both simulated and live services use idempotent `ADD COLUMN IF NOT EXISTS`, nullable/default cleanup, and historical-row correction (`src/trading/SimulatedTradingService.cpp:382-392`; `src/trading/LiveTradingService.cpp:391-401`). The historical error window was `2026-08-22 15:51:55–16:08:38`. Owner: deployment/database operator must verify the deployed schema and read-side behavior. |

## Confirmed causes versus hypotheses

Confirmed:

- The initial browser zero-trade state occurred before the worker had produced signals; it was a real early pending snapshot.
- The earlier API zero-trade interval had fresh Coinbase data, no fetch failures, Transformer warm-up, and hold/no-signal outcomes; no order-intent or execution gate beyond signal/model/profitability decisions was reached.
- Frontend polling is 3 seconds, not one minute. Pagination is display-only and does not cap the selected universe.
- The fresh browser worker executed 27 ticks and produced successful quotes/signals before stop.
- Live Coinbase orders were not enabled or submitted; execution remained paper/live-parity.

Not proven:

- A terminal zero-trade invariant for the current runtime.
- That the WebSocket close caused the early pending widget state; HTTP polling and diagnosis supplied the observed data.
- That historical YB-USD TLS or `is_closing_leg` errors affected the seven-symbol sessions.
- That any exchange/provider cadence was exactly one minute.

## Verification and safety record

- Parent exact-SHA remote CI evidence: commit `a88988c80067fa1bb5155b6d26e20a2d69817596`, Docker Build Validation run `32618486554`; required amd64 backend/frontend image jobs passed and focused CTest reported `10/10` passing, including `strategy_signal` and `execution_reconciliation`.
- This report commit `347a4b38f832dd2c78437d93f0ff8e563d6c57bd` was verified by Docker Build Validation run `35456826191` (`workflow_dispatch`); all six jobs passed: C++ backend amd64/arm64, frontend amd64/arm64, and both published manifest jobs. The run head SHA exactly matches the report commit.
- Browser artifact verification: commit `3795276cb975fefc89508c1615d37b848629d168` is present on `origin/wt/t_ca8e5b29-browser-evidence`; no CI run was triggered for that evidence branch.
- No local build or test command was run for this report task, consistent with the remote-only project policy.
- Both paper sessions were stopped cleanly. No live Coinbase order endpoint was called, no live order was enabled, and no credentials or secrets are included here.
