# Trading mode and execution data contract

Status: design artifact (backend audit; no runtime or live-account changes)
Date: 2026-08-23
Scope: simulated trading, live-parity paper trading, live Coinbase execution, persistence, and API payloads

## 1. Executive contract

The backend has three operational behaviors, but only two simulation modes should be exposed as simulation choices:

| Contract mode | Current accepted value | Market data | Fill authority | Coinbase order submission | Capital/accounting |
|---|---|---|---|---|---|
| `synthetic_simulated` | `simulated` | Synthetic AR(1) price/imbalance state | Local simulator | Never | Isolated synthetic starting capital |
| `live_parity_simulated` | `live_parity` | Coinbase public order books | Local paper ledger | Never | Isolated paper ledger; no Coinbase account mutation |
| `live` | `live` | Coinbase public order books | Coinbase fill response/account reconciliation | Only with explicit live confirmation | Coinbase account is authoritative |

`paper_live` is a compatibility/product alias for `live_parity_simulated`, not a fourth behavior. The canonical wire value should be `live_parity_simulated`; during migration accept `live_parity` and emit both canonical and legacy fields. The canonical synthetic wire value should be `synthetic_simulated`; during migration accept `simulated` and emit both canonical and legacy fields.

Safety invariant: a request carrying `live_parity_simulated`, `paper_live`, or legacy `live_parity` must never invoke `CoinbaseAdvancedClient::placeMarketOrder`. It may call only the unauthenticated public `getOrderBook` path. Any future code path that can submit an order must require `execution_mode=live`, an authenticated client, and `live_order_execution=true` after backend validation.

## 2. Current implementation map

### Service and mode selection

- `include/trading/SimulatedTradingService.hpp:29-37` exposes start/stop/status/portfolio/signal operations through one singleton service; `mode_` defaults to `simulated` (`:217`) and currently accepts `simulated`, `live_parity`, and the live-mode implementation path when called directly.
- `src/api/PredictController.cpp:1179-1201` handles `POST /api/trading/simulated/start`, reads top-level `execution_mode` or `parameters.execution_mode`, and currently rejects every value except `simulated` and `live_parity`.
- `src/trading/SimulatedTradingService.cpp:2142-2284` starts the synthetic/live-parity worker, accepts `parameters` and legacy `strategy_params`, carries synthetic capital, and builds status fields. It creates a Coinbase client for both live-data modes but does not require credentials for public order books.
- `include/trading/LiveTradingService.hpp:26-42` and `src/trading/LiveTradingService.cpp:2767-2927` implement the separate authenticated live service. Start requires a Coinbase account snapshot and explicit `live_order_execution=true`; synthetic capital fields are rejected (`:2832-2864`).

### Market data and Coinbase boundary

- `include/exchange/CoinbaseAdvancedClient.hpp:67-98` separates authenticated account/order methods from unauthenticated `getTicker`/`getOrderBook` methods.
- `src/exchange/CoinbaseAdvancedClient.cpp:230-294` lists authenticated accounts; `:297-394` submits authenticated market IOC orders and distinguishes acceptance from terminal fill; `:480-500` retrieves actual fills; public market-data methods begin at `:497`.
- `src/trading/SimulatedTradingService.cpp:879-937` fetches public Coinbase order books for `live` and `live_parity`; `:1732-1829` skips a live-data symbol when no quote exists, so live-data modes do not fall back to synthetic ticks.
- `src/trading/SimulatedTradingService.cpp:657-663` gates order dispatch on `mode_ == "live"`, configured credentials, and `live_order_execution`; `:781-835` is the only simulated-service dispatch loop and calls `placeMarketOrder` only when that gate is true. In live-parity mode `liveOrderExecutionEnabledLocked()` is false by construction.
- `src/trading/LiveTradingService.cpp:630-645`, `:3062-3147`, and `:3290`-related worker paths are the authenticated live order-intent and dispatch boundary. These must remain unreachable from any paper mode.

### Signals, gates, intents, and fills

- Signal state is held in `SignalRecord` (`include/trading/SimulatedTradingService.hpp:98-116` and the analogous live header) and includes signal id/session id/symbol/type/strength/price/timestamp, order-book fields, and opaque JSON payload.
- `src/trading/SimulatedTradingService.cpp:489-515` serializes signal identity, legacy aliases (`signal` and `signal_strength`), `data_status`, criteria, ML analysis, strength composition, and `execution_analysis`.
- `src/trading/SimulatedTradingService.cpp:518-601` builds the execution analysis. It records intended action/side, expected-return fields, diagnostic factor, allocation, `blocked`, `blocker_reason`, and `executable_intent`; live-parity additionally checks minimum notional, spot-only side, and available cash (`:575-600`).
- `src/trading/SimulatedTradingService.cpp:1732-1829` increments `signals_evaluated`, `signals_generated`, and `executable_order_intents`; live-parity increments `execution_blocker_counts` for generated but non-executable signals (`:1766-1775`).
- `src/trading/SimulatedTradingService.cpp:1470-1559`, `:1562-1637`, and `:1639-1729` create local paper/synthetic fills and closing legs. `trade_type` is currently overloaded: it becomes `simulated`, `live_parity`, `live_paper`, or `live` depending on mode and execution flag.
- `src/trading/LiveTradingService.cpp:654-850` applies Coinbase fills, records actual fees, separates inherited/account-managed rows (`live_account_managed_add`, `live_account_managed_close`, `live_liquidation`), and excludes those from session strategy stats (`:612-621`).

### Status, portfolio, and summary counters

- `src/trading/SimulatedTradingService.cpp:1944-2066` emits `mode`, `execution_mode`, `execution_is_paper`, `market_data_source`, cash/reserves, positions, recent trades/signals, execution blocker counts, market-data failure counts, and signal coverage counters.
- `src/trading/SimulatedTradingService.cpp:2069-2139` emits in-session stats from `session_trade_inputs_`, with a database fallback. The stats calculator (`src/trading/TradingStatsCalculator.cpp:81-153`) treats `pnl` as gross PnL, subtracts `fees` only for `net_pnl`, excludes zero-PnL legs from win/loss denominators, and reports win rate as 0–100 percent and drawdown in dollars.
- `src/trading/LiveTradingService.cpp:2446-2583` emits account/managed-position counters and live quote coverage/diagnostic counters. `:2585-2655` reads persisted live rows and excludes account-management/liquidation `trade_type` values from strategy stats.
- `include/trading/TradingStatsService.hpp:33-45` and `src/trading/TradingStatsService.cpp:94-150` support optional exact `trade_type` and `session_id` filters. This is insufficient for canonical mode grouping because `trade_type` currently mixes mode, provenance, and lifecycle classification.

## 3. Proposed wire contract

### Start request

`POST /api/trading/simulated/start` remains the endpoint for both simulation modes. The request should normalize to:

```json
{
  "execution_mode": "synthetic_simulated|live_parity_simulated",
  "strategy": "orderbook",
  "symbols": ["BTC-USD"],
  "parameters": {
    "position_size_percent": 1,
    "max_positions_per_session": 10,
    "confidence_threshold": 0.6,
    "live_order_execution": false
  },
  "max_positions": 10,
  "session_id": "optional-client-id"
}
```

Rules:

- `execution_mode` is required for new clients. If absent, normalize to `synthetic_simulated` for compatibility with existing synthetic clients.
- Accept legacy `simulated` as `synthetic_simulated`; accept legacy `live_parity` and product alias `paper_live` as `live_parity_simulated`.
- Reject `live` at the simulated endpoint with 400 and direct the caller to `/api/trading/live/start`.
- Ignore/reject `live_order_execution=true` for either simulation mode. Prefer reject with 400 rather than silently changing intent; the response must state that paper modes never submit Coinbase orders.
- Preserve selected symbols exactly. Do not add a backend universe cap or silently replace the requested list.
- Preserve `parameters` and `strategy_params` input aliases during migration. Do not accept synthetic capital fields in live mode; synthetic modes may use `initial_portfolio_size`, `initial_balance`, or `capital` under the existing compatibility rules.

`POST /api/trading/live/start` remains the only live start endpoint. It should normalize/emit `execution_mode=live`, require account snapshot success and explicit confirmation, reject synthetic capital, and never accept a paper alias.

### Common status/portfolio envelope

Every status and portfolio response should contain:

```json
{
  "session_id": "...",
  "execution_mode": "synthetic_simulated|live_parity_simulated|live",
  "mode": "simulated|live_parity|live",
  "execution_is_paper": true,
  "market_data_source": "synthetic|coinbase_public",
  "execution_authority": "local_simulator|paper_ledger|coinbase_account",
  "order_submission_enabled": false,
  "signals_evaluated": 0,
  "signals_generated": 0,
  "executable_order_intents": 0,
  "blocked_order_intents": 0,
  "execution_blocker_counts": {},
  "pending_order_count": 0,
  "pending_reserved_cash": 0,
  "stats": {}
}
```

`mode` remains as a legacy alias. New consumers use `execution_mode`, `execution_authority`, and `order_submission_enabled`. For paper modes `order_submission_enabled` must be false even if credentials happen to be configured.

### Signal contract

Each signal response and persisted signal payload should have stable top-level fields:

- Identity: `signal_id`, `session_id`, `symbol`, `timestamp`.
- Decision: `signal_type`/legacy `signal`, `signal_generated`, `signal_strength`/legacy `strength`, `signal_reason`, `data_status`.
- Market evidence: `price`, `mid_price`, `best_bid`, `best_ask`, `spread`, `volume`, `imbalance_ratio`, `order_book_depth`.
- Model evidence: `ml_analysis` with prediction-time values only (`win_probability`, `expected_return`, `fee_adjusted_expected_return`, `required_edge`, `confidence`, `model_version`, `inference_status`).
- Execution analysis: `intended_action`, `intended_side`, `executable_intent`, `blocked`, `blocker_reason`, `diagnostic_factor`, `allocated_usd`, `available_cash`, `estimated_fee`, and `minimum_notional` when applicable.
- Provenance: `execution_mode`, `market_data_source`, and `execution_authority`.

`data_status=insufficient` is reserved for missing history/warm-up. Valid market data with a no-trade strategy/profitability/ML decision remains `sufficient` and is represented by `blocked=true` plus a blocker reason.

### Intent and fill contract

A generated signal is not a fill. The normalized lifecycle is:

1. `signal`: strategy/model decision.
2. `order_intent`: proposed action after signal and preflight gates.
3. `blocked_intent`: durable non-submission record when a generated signal cannot proceed.
4. `paper_fill`: local fill for synthetic or live-parity paper modes.
5. `submitted_order`: Coinbase order request, live mode only.
6. `accepted_order`: Coinbase accepted an order id but fill is pending.
7. `fill`: terminal Coinbase fill with actual filled size, value, average price, and actual fees.
8. `rejected/cancelled/expired/failed`: terminal non-fill outcome with reason.

Required intent fields: `intent_id`, `signal_id`, `session_id`, `execution_mode`, `symbol`, `side`, `action`, `amount`, `amount_unit` (`quote` or `base`), `requested_at`, `preflight_passed`, `blocker_reason`, `execution_authority`, and `submission_status`.

Required fill fields: `fill_id`, `intent_id`, `trade_id`, `execution_mode`, `fill_kind` (`paper` or `coinbase`), `quantity`, `price`, `notional`, `fees`, `gross_pnl`, `net_pnl`, `is_closing_leg`, `filled_at`, and optional `exchange_order_id`. Paper fills must have `exchange_order_id=null` and `fill_kind=paper`; live fills must carry the Coinbase order id and actual fee.

A closing leg may have exactly zero gross PnL and nonzero fees. It remains a closing fill and must not be reclassified from lifecycle evidence based on PnL.

## 4. Persistence proposal

Current schema is created opportunistically in `ensureSchema()` rather than through versioned migrations:

- `order_book_signals` and `individual_trades` are created by both services (`SimulatedTradingService.cpp:314-365`, `LiveTradingService.cpp:332-402`).
- `individual_trades` currently has `trade_type` and nullable `is_closing_leg`, but no explicit execution mode, authority, intent id, fill kind, blocker, or exchange order id.
- `live_coinbase_orders` (`LiveTradingService.cpp:385-402`) stores submitted-order recovery state, including session, amount units, signal/position JSON, reservation, and status.

Recommended incremental schema (versioned migration preferred; if runtime `ensureSchema` remains, use idempotent `ADD COLUMN IF NOT EXISTS` and indexes):

```sql
CREATE TABLE trading_sessions (
  session_id TEXT PRIMARY KEY,
  execution_mode TEXT NOT NULL CHECK (execution_mode IN ('synthetic_simulated','live_parity_simulated','live')),
  market_data_source TEXT NOT NULL CHECK (market_data_source IN ('synthetic','coinbase_public')),
  execution_authority TEXT NOT NULL CHECK (execution_authority IN ('local_simulator','paper_ledger','coinbase_account')),
  symbols JSONB NOT NULL,
  strategy_type TEXT NOT NULL,
  initial_capital NUMERIC,
  started_at TIMESTAMPTZ NOT NULL,
  stopped_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE execution_intents (
  intent_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES trading_sessions(session_id),
  signal_id TEXT,
  execution_mode TEXT NOT NULL,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,
  action TEXT NOT NULL,
  amount NUMERIC NOT NULL,
  amount_unit TEXT NOT NULL,
  preflight_passed BOOLEAN NOT NULL,
  submission_status TEXT NOT NULL,
  blocker_reason TEXT,
  diagnostic_factor TEXT,
  exchange_order_id TEXT,
  requested_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE individual_trades
  ADD COLUMN execution_mode TEXT,
  ADD COLUMN execution_authority TEXT,
  ADD COLUMN fill_kind TEXT,
  ADD COLUMN intent_id TEXT,
  ADD COLUMN signal_id TEXT,
  ADD COLUMN exchange_order_id TEXT,
  ADD COLUMN gross_pnl DOUBLE PRECISION,
  ADD COLUMN net_pnl DOUBLE PRECISION,
  ADD COLUMN blocker_reason TEXT;

CREATE INDEX individual_trades_mode_session_time_idx
  ON individual_trades (execution_mode, session_id, timestamp);
CREATE INDEX execution_intents_session_status_idx
  ON execution_intents (session_id, submission_status, requested_at);
CREATE INDEX execution_intents_signal_idx ON execution_intents (signal_id);
CREATE INDEX order_book_signals_session_symbol_time_idx
  ON order_book_signals (session_id, symbol, timestamp DESC);
```

Backfill/compatibility rules:

- Existing `individual_trades.trade_type='simulated'` maps to `execution_mode='synthetic_simulated'`, `execution_authority='local_simulator'`, `fill_kind='paper'`.
- Existing `trade_type='live_parity'` maps to `execution_mode='live_parity_simulated'`, `execution_authority='paper_ledger'`, `fill_kind='paper'`.
- Existing `trade_type='live_paper'` maps to `execution_mode='live'`, `execution_authority='local_simulator'`, `fill_kind='paper'`; this is a legacy live-service paper state and must not be counted as Coinbase execution.
- Existing `trade_type='live'` maps to `execution_mode='live'`, `fill_kind='coinbase'` only when `exchange_order_id`/order recovery evidence exists; otherwise retain `fill_kind=NULL` and surface an audit warning rather than inventing provenance.
- Existing account-management and liquidation values remain `trade_type` compatibility values and map to `execution_mode='live'` with `fill_kind='coinbase'` when backed by an exchange order. They remain excluded from strategy performance unless explicitly requested as account-management accounting.
- Do not add `NOT NULL DEFAULT FALSE` to populated `is_closing_leg`; legacy NULL is meaningful. Keep legacy rows queryable and make new fields nullable until backfill evidence is complete.
- Stats queries must filter by `execution_mode` and explicitly exclude account-management rows from strategy stats. Keep `trade_type` filters as a deprecated compatibility path.

## 5. Endpoint and client compatibility matrix

| Endpoint | Current behavior | Contract change |
|---|---|---|
| `POST /api/trading/simulated/start` | Accepts `simulated`/`live_parity`; aliases legacy simulated route exists | Accept canonical `synthetic_simulated`/`live_parity_simulated`, legacy aliases; reject `live` and true order execution |
| `POST /api/simulated-trading/start` | Alias to same handler | Preserve alias and identical normalization |
| `GET /api/trading/simulated/status`, `GET /api/simulated-trading/status` | Returns mode/status/stats/diagnostics | Add canonical mode, authority, submission flag, intent counters; retain legacy aliases |
| `POST /api/trading/simulated/stop` | Stops local worker | Preserve; paper stops without exchange settlement |
| `GET /api/orderbook/simulated-signals` | Latest-by-symbol simulated service records | Add provenance and stable execution-analysis fields |
| `POST /api/trading/live/start` | Requires account snapshot and explicit confirmation | Emit canonical `execution_mode=live`; retain live mode field |
| `GET /api/trading/live/status` | Live account/session status and stats | Add canonical fields and separate intent/fill counters |
| `GET /api/live-portfolio/status` | Coinbase producer/readiness payload | Keep account authority explicit; never reuse paper portfolio as live account state |
| `POST /api/trading/live/execute` | Manual live order; backend checks active session, flag, cash/holdings | Include `intent_id`, explicit amount unit, and terminal/pending status |
| `POST /api/trading/live/close-position` | Live close endpoint | Persist as intent then fill; preserve inherited-position accounting |
| `POST /api/trading/live/liquidate-holdings` | Coinbase-only liquidation | Persist separate account-management intent/fill classification |
| `GET /api/trades/stats` | Exact `trade_type`/`session_id` filters | Add `execution_mode`, `fill_kind`, and `include_account_management`; retain aliases |
| `GET /api/trading/execution-reconciliation` | Reconciliation surface exists in controller | Scope both intents and outcomes by canonical mode/session; report blocked intents separately |

Frontend compatibility: `frontend/lib/api.ts:787-879` currently types only `live|simulated`, sends `execution_mode` inside the shared payload, uses a backend fallback for synthetic simulation, and bypasses local fallback for `live_parity`. Extend the type to include `synthetic_simulated`/`live_parity_simulated` or keep UI mode `simulated` while mapping its explicit execution selector to canonical values. `frontend/types/trading.ts:120-139` already has most execution-analysis fields but needs provenance, intent status, and fill-kind fields. Never enable local synthetic fallback when the requested mode is live-parity paper.

## 6. Open decisions for implementation

1. Use canonical name `live_parity_simulated` or public alias `paper_live` in UI labels. Recommendation: wire value `live_parity_simulated`, label “Paper live parity”; accept `paper_live` as alias.
2. Choose versioned SQL migrations versus continued startup DDL. Recommendation: add a migration/version table and keep startup DDL only as a defensive compatibility fallback.
3. Decide whether blocked intents are retained indefinitely or sampled/aggregated. Recommendation: persist every blocked intent for the session, with retention/partitioning defined separately; status counters may remain bounded in memory.
4. Decide whether synthetic and paper sessions can coexist. Current singleton service permits one simulated session and rejects cross-mode takeover (`SimulatedTradingService.cpp:2148-2157`). Recommendation: preserve one active simulated session until multi-session ownership is designed.
5. Decide whether a paper fill uses bid/ask instead of mid. Current parity signal uses Coinbase mid and spread; recommendation: buy at ask and sell at bid (with explicit slippage model) for execution realism, but make this a separate implementation decision and test it before changing accounting.
6. Define the runtime closeout evidence for parity: representative signals, blocker buckets, paper fills, reconciliation, and proof that Coinbase order-submit call count remains zero.

## 7. Acceptance criteria for implementation

- [ ] Start validation accepts only canonical modes plus documented aliases; `live` cannot enter the simulated service.
- [ ] Paper modes set `execution_is_paper=true`, `execution_authority=paper_ledger`, and `order_submission_enabled=false` in every status/portfolio response.
- [ ] A paper session with configured Coinbase credentials still makes no authenticated account/order request and no `placeMarketOrder` call.
- [ ] Live start remains fail-closed on missing credentials/account snapshot/explicit confirmation and rejects synthetic capital.
- [ ] Every generated signal has stable provenance and execution-analysis fields; insufficient data is distinct from valid-data strategy blockers.
- [ ] Every generated-but-blocked signal produces a durable or explicitly retained blocked intent with blocker reason and counter; no blocked signal is counted as a fill.
- [ ] Paper fills and Coinbase fills are distinguishable by `execution_mode`, `execution_authority`, `fill_kind`, and optional exchange order id; actual Coinbase fees are preserved.
- [ ] Existing synthetic/live/live-parity rows and clients remain readable through compatibility mappings without fabricating legacy provenance.
- [ ] Stats and reconciliation filters constrain both intents and fills by canonical mode/session and exclude inherited/account-management rows from strategy metrics by default.
- [ ] Closing legs are classified by lifecycle/action, including exactly-flat gross exits with fees.
- [ ] Requested symbol universes are preserved; diagnostics expose quote coverage/failures and no silent cap is introduced.
- [ ] Add unit/API contract tests for mode normalization, paper no-submit invariant, legacy mappings, blocked-intent accounting, and stats separation.
- [ ] Remote CI passes for the exact pushed SHA; runtime parity evidence and live-account evidence remain separate closeout gates.

## 8. Verification limits of this audit

This artifact is based on static source inspection and existing repository reports. No Coinbase credentials were read or used, no live order was submitted, no local build/test was run, and no claim is made about current production database contents or runtime profitability.
