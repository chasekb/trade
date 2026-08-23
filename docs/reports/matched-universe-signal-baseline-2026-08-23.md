# Matched-universe live/simulated order-book signal baseline

Timestamp: 2026-08-23T03:39:26Z (2026-08-22 22:39:26 CDT, UTC-05:00)
Task: `t_01b15a9e`

## Result and safety boundary

This is a read-only baseline. No production source behavior was changed, no live session was started or restarted, and no live or simulated order was submitted. The running stack was queried only through GET endpoints. The live and simulated signal endpoints did not return within the 10-second read-only timeout, so measurements unavailable at runtime are explicitly marked unavailable rather than inferred from source or older evidence.

The supported deterministic fixture/configuration was identified from checked-in source but was not started because doing so would mutate runtime/session state and the current signal read handlers were already timing out. The reproduction command below is therefore the safest repeatable path.

## Exact source and files

- Worktree branch: `wt/t_01b15a9e`
- Repository commit: `8af7838c9112e4f88c0f358504877d054ce9eb0c`
- Commit subject: `feat(trade): remove live quote cadence enforcement`
- Files in the exact commit:
  - `docs/reports/live-simulated-orderbook-throughput-normalization-closeout-2026-08-05.md`
  - `include/trading/LiveTradingService.hpp`
  - `src/trading/LiveTradingService.cpp`
- This baseline adds only this report: `docs/reports/matched-universe-signal-baseline-2026-08-23.md`.

## Matched universe and strategy parameters

The runtime `GET /api/trading/live/status` response reported `status=stopped`, `symbols=[]`, and an empty `session_id`; therefore no active selected universe was available to claim as a live session universe. The source fallback universe, used here as the explicitly labeled matched fixture universe, is:

`BTC-USD, ETH-USD, SOL-USD`

Evidence: `src/trading/LiveTradingService.cpp:111-113` and `src/trading/SimulatedTradingService.cpp:112-114`. This is a configured fallback, not proof that a live session selected these symbols.

Strategy fixture: `ml_enhanced_orderbook` (the order-book signal path also accepts `orderbook`). Source defaults/controls recorded without inventing runtime overrides:

| Parameter | Value | Evidence |
| --- | ---: | --- |
| `round_trip_fee_percent` | 1.5% | `src/trading/LiveTradingService.cpp:39`, `SimulatedTradingService.cpp:35` |
| `slippage_buffer_percent` | 0.2% | `LiveTradingService.cpp:40`, `SimulatedTradingService.cpp:36` |
| `min_orderbook_signal_strength` | 0.22 | `LiveTradingService.cpp:41`, `SimulatedTradingService.cpp:37` |
| `orderbook_expected_return_scale_percent` | 2.4% default, clamped 0–5% | `LiveTradingService.cpp:1690-1698`, `SimulatedTradingService.cpp:1275-1283` |
| `minimum_net_pnl_usd` | 0.0 default | service profitability diagnostic path |
| live quote cap | 0 (not enforced) | live status diagnostics |
| normal cadence sleep | not enforced by current commit | commit subject and live diagnostics contract |
| execution mode | live status `mode=live`, `is_active=false`; no start attempted | runtime response |

## Environment

- Host: Linux `archbtw`, kernel `7.1.8-arch1-3`, x86_64
- CPU visible: 32 logical CPUs
- Memory at capture: 125 GiB total, 99 GiB available; swap 8 GiB total
- Runtime: rootless Podman Compose, no image/build command run by this task
- Containers at capture:
  - `trade_cpp-backend_1` — `ghcr.io/chasekb/trade/cpp-backend:dev`, healthy, host `8081 -> 8080`
  - `trade_frontend_1` — `ghcr.io/chasekb/trade/frontend:dev`, healthy, host `3000 -> 3000`
  - `trade_db_1` — `postgres:15-alpine`, healthy, host `5433 -> 5432`
  - `trade_redis_1` — `redis:7-alpine`, healthy, host `6379 -> 6379`
- Backend startup logs reported PostgreSQL and Redis connected. They also reported missing `data/cpp_assets/feature_params.json` and no usable ONNX models, with built-in/neutral fallback parameters.
- No credentials, `.env` contents, or secret-bearing files were read or recorded.

## Normalized baseline table

`Unavailable` means the endpoint timed out or the runtime had no active session. `Not observed` means the metric is not exposed in the stopped-session response. `Source-only` means a contract/default was verified from checked-in source, not measured at runtime.

| Measurement | Live | Simulated | Basis / interpretation |
| --- | --- | --- | --- |
| selected universe | unavailable; status returned `symbols=[]` | unavailable; no session started | fallback fixture is BTC/ETH/SOL, source-only |
| symbols attempted | 0 reported in stopped status (`quote_attempted_symbol_count=0`) | unavailable | no live worker tick and no simulated session |
| generated signals | 0 recent records; `current_latest_signal_count=0` | unavailable | live status only; signal endpoints timed out |
| latest signals | `recent_signals=[]`; latest count 0 | unavailable | live status only |
| sweep duration | unavailable | unavailable | not returned by stopped status |
| tick duration | unavailable | unavailable | no worker tick observed |
| stale age | unavailable | unavailable | no signal timestamp |
| freshness | `coverage_complete=false` | unavailable | no active live quote/signal coverage |
| queue depth | `pending_order_count=0` | unavailable | no start/order activity |
| API errors | none in `/health` or live status; signal reads timed out (`HTTP 000`) | signal read timed out (`HTTP 000`) | timeout is a read-path/runtime availability finding, not an API payload error |
| rate limits | no rate-limit response observed | unavailable | no signal fetch completed |
| blocked intents | 0; `execution_blocker_counts={}` | unavailable | no active live signals |
| active signals | 0 | unavailable | no session |
| signal strength | no rows; strength buckets `{}` | unavailable | no signal response |
| expected edge | no rows; expected-return buckets `{}` | unavailable | models unavailable and no active rows |
| realized edge / PnL | realized PnL `0.0`; no trades | unavailable | stopped live status |
| execution outcomes | executable intents 0; trades 0; pending orders 0 | unavailable | no execution was initiated |

## Raw API evidence

Commands were run from a neutral shell against `127.0.0.1:8081`; every request below was read-only:

```text
curl --max-time 10 -sS -w '\nHTTP %{http_code} TIME %{time_total}\n' http://127.0.0.1:8081/health
{"service":"trading-bot-cpp-backend","status":"healthy","version":"0.1.0"}
HTTP 200

curl --max-time 10 -sS -w '\nHTTP %{http_code} TIME %{time_total}\n' http://127.0.0.1:8081/api/trading/live/status
HTTP 200
status=stopped, is_active=false, mode=live, strategy_type=orderbook, symbols=[], session_id=""
order_book_signal_diagnostics={requested_symbol_count:0, quote_attempted_symbol_count:0, quote_success_symbol_count:0, quote_skipped_symbol_count:0, current_latest_signal_count:0, recent_signal_record_count:0, executable_order_intent_count:0, execution_blocker_counts:{}, execution_strength_bucket_counts:{}, execution_expected_return_bucket_counts:{}, active_recent_signal_records:0, coverage_complete:false, live_quote_symbols_per_tick_cap:0, quote_fanout_limit_enforced:false}
recent_signals=[], recent_trades=[], trades=[], realized_pnl=0.0, pending_order_count=0

curl --max-time 10 -sS -w '\nHTTP %{http_code} TIME %{time_total}\n' 'http://127.0.0.1:8081/api/orderbook/live-signals?per_page=50'
curl: (28) Operation timed out after 10002 milliseconds with 0 bytes received
HTTP 000 TIME 10.002315

curl --max-time 10 -sS -w '\nHTTP %{http_code} TIME %{time_total}\n' 'http://127.0.0.1:8081/api/orderbook/simulated-signals?per_page=50'
curl: (28) Operation timed out after 10002 milliseconds with 0 bytes received
HTTP 000 TIME 10.002855

curl --max-time 10 -sS -w '\nHTTP %{http_code} TIME %{time_total}\n' http://127.0.0.1:8081/api/simulated-trading/status
curl: (28) Operation timed out after 10002 milliseconds with 0 bytes received
HTTP 000 TIME 10.002307
```

## Raw backend log evidence

The backend container log at capture contained:

```text
[2026-08-23 03:36:11.139] [trading_bot] [info] Trading Bot C++ Backend starting...
[2026-08-23 03:36:11.148] [trading_bot] [info] Successfully connected to PostgreSQL database: trading_db
[2026-08-23 03:36:11.149] [trading_bot] [info] Successfully connected to Redis at redis://redis:6379
[2026-08-23 03:36:11.294] [trading_bot] [warning] Could not open feature parameters file: data/cpp_assets/feature_params.json; using built-in fallback parameters
[2026-08-23 03:36:11.307] [trading_bot] [warning] No usable ONNX models found in data/onnx; using neutral fallbacks
[2026-08-23 03:36:11.307] [trading_bot] [warning] No usable ONNX models loaded from data/onnx; continuing with neutral prediction fallbacks
[2026-08-23 03:36:11.307] [trading_bot] [info] Server listening on port 8080
```

## Reproduction and next measurement gate

1. Start the checked-in stack using the existing safe runtime procedure: `TAG=dev podman-compose up --no-build`.
2. Confirm `GET /health` and `GET /api/trading/live/status` return.
3. Re-run the three signal/status GET commands above with the matched explicit universe query: `symbols=BTC-USD,ETH-USD,SOL-USD&per_page=3`.
4. Do not start live trading or enable live order execution as part of this baseline. A separate approved runtime session is required to measure worker tick/sweep timing, quote attempts, freshness, generated signals, blockers, and execution outcomes.

Current baseline conclusion: health and stopped live status are available and show zero activity; both order-book signal read paths and simulated status are unavailable due to reproducible 10-second read timeouts. This is evidence of a runtime read-path blocker, not evidence of signal parity, signal quality, or profitable execution.
