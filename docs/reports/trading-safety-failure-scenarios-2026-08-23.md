# Trading safety and failure-scenario exercise

## Scope and evidence boundary

This exercise is source-backed and fail-closed. No live Coinbase credentials, exchange sandbox endpoint, or injectable exchange mock is configured in this worktree, so no real order or destructive operation was submitted. The repository's remote-CI-only policy also prohibits local package/container builds and tests. Results marked `PASS (static)` are verified from the implementation paths and existing test fixtures; results marked `FAIL` identify a missing safety contract and include reproduction details.

Evidence paths use this worktree and line numbers from the inspected revision.

## Scenario results

| Scenario | Result | Severity | Evidence / reproduction |
|---|---|---:|---|
| Overload / large selected universe | PASS (static) | Medium | `LiveTradingService::selectLiveQuoteBatchLocked` preserves the selected universe and processes it sequentially (`src/trading/LiveTradingService.cpp:1244-1263`); the worker emits request/failure timing and a fan-out warning (`2310-2373`). There is no concurrent request storm or silent truncation. Reproduction: start with N selected symbols and inspect `requested`, `attempted`, `succeeded`, `skipped`, `fetch_ms`, and `quote_requests_per_second` in the worker log. The warning is observability only, not a throughput limiter. |
| HTTP 429 response | PASS (static) | High | `CoinbaseAdvancedClient::request` converts every non-2xx status, including 429, to an error and returns null (`src/exchange/CoinbaseAdvancedClient.cpp:203-220`). `placeMarketOrder` therefore cannot mark the order accepted (`297-393`); dispatch retains an inconclusive submission with its durable client id for recovery (`src/trading/LiveTradingService.cpp:1071-1089`). No blind duplicate POST is issued. |
| Request timeout | PASS (static) | High | The HTTP request has a 10-second client timeout and a 15-second future ceiling (`src/exchange/CoinbaseAdvancedClient.cpp:168-200`). An inconclusive create is retained as a pending client-order record rather than treated as a fill (`src/trading/LiveTradingService.cpp:1075-1085`). Reproduction: inject a delayed response beyond 15 seconds and verify no fill/trade is emitted and the pending record remains recoverable. |
| Stale quote | FAIL | High | `MarketQuote` contains price/book values but no source timestamp or age (`include/trading/LiveTradingService.hpp:135-146`). `fetchLiveQuotes` accepts a successful order-book response as valid without age validation (`src/trading/LiveTradingService.cpp:1208-1241`), and `generateTickLocked` consumes it. Reproduction: return an otherwise valid book whose exchange timestamp is older than the configured freshness budget; there is no timestamp field or freshness gate to reject it. Unsafe outcome: a delayed but valid-looking quote can produce an intent. |
| Partial market-data failure | PASS (static) | Medium | A failed symbol is logged and omitted rather than reused or converted into an order (`src/trading/LiveTradingService.cpp:1215-1239`). Diagnostics expose refreshed/failed counts and failed symbols; the simulated path documents the same contract (`src/trading/SimulatedTradingService.cpp:2029-2059`). Reproduction: fail one symbol while returning valid books for others; only successful symbols reach signal generation. |
| Stop Trading during queued work | PASS (static) | High | `stopSession` sets `stop_requested_`, marks the service inactive, removes queued symbols, refunds queued reservations, and clears `pending_orders_` (`src/trading/LiveTradingService.cpp:2930-2954`). `dispatchOrders` checks the stop flag before persisting/submitting each remaining intent and refunds unsubmitted work (`1035-1061`). Reproduction: queue at least two intents, stop before dispatch reaches the second, and verify only already-submitted work remains pending. |
| Stop Trading during active work | FAIL | High | Stop prevents later dispatch and tick generation, but the cancellation callback passed to the exchange checks `shutdown_requested_`, not `stop_requested_` (`src/trading/LiveTradingService.cpp:1041-1050`). Thus an in-flight network request/fill-poll can continue after `stopSession`; accepted orders intentionally remain settling (`2319-2321`, `2948-2953`). Reproduction: block the exchange call, call stop, and measure return/worker settlement time. Safety is fail-closed (no new order), but prompt cancellation is not demonstrated. |
| API polling under load | PASS (static) | Medium | Worker network calls and persistence are outside the service mutex (`src/trading/LiveTradingService.cpp:2328-2403`), while status/portfolio reads take the mutex only. Reproduction: poll status concurrently during blocked quote/account calls and verify handlers remain responsive; no local load execution was permitted. |
| Blocked intents | PASS (static) | High | Live execution requires configured credentials and explicit `live_order_execution` confirmation (`src/trading/LiveTradingService.cpp:2832-2864`). Per-symbol pending state prevents another intent while an exchange order is pending (`src/trading/LiveTradingService.cpp:2172-2174`); diagnostics serialize `blocked_intents` (`src/api/PredictController.cpp:98-102`). |
| Duplicate-order attempt | PASS (static) | Critical | Every intent is persisted with a generated client id and `ON CONFLICT (client_order_id) DO NOTHING RETURNING`; an empty result refuses submission (`src/trading/LiveTradingService.cpp:859-914`). Recovery searches by client id before assigning an exchange order id (`963-1027`, `1132-1152`). Reproduction: replay the same client id against the persistence gate and verify zero second exchange submission. |
| Execution outcomes / partial or delayed fill | PASS (static) | Critical | Acceptance and fill are separate. Accepted orders remain pending until `getOrderFill` succeeds; fill application is guarded by `fill_applied`, persists settlement, then marks the order terminal (`src/trading/LiveTradingService.cpp:1100-1103`, `1162-1194`). No zero-fee or synthetic fill is invented on timeout. |

## Acceptance assessment

- Unauthorized order submission: PASS (static). Live start fails closed without account initialization, credentials, and explicit confirmation (`startSession`, lines 2790-2864).
- Duplicate execution prevention: PASS (static). Durable client-order uniqueness plus recovery-by-client-id are present.
- Queued stop behavior: PASS (static). Queued intents are removed and reservations released.
- Partial failures: PASS (static). Failed market-data symbols are excluded and observable.
- Retry/timeout limits: PASS (static), with bounded HTTP/fill polling and bounded recovery lookup. There is no automatic POST retry after an inconclusive create; this is safer than blind retry.
- Stale-quote safety: FAIL. No quote timestamp/age or freshness budget is represented or enforced.
- Prompt active-stop behavior: FAIL. Stop does not propagate to the exchange cancellation callback; it waits for the active blocking call/fill polling path.
- Real controlled execution evidence: NOT AVAILABLE in this environment. No live/sandbox exchange mock seam or credentials were present, and local test/build execution is prohibited by task policy.

## Severity and required follow-up

1. **High — stale quote acceptance.** Add an exchange/source timestamp and a configured freshness budget to the quote contract; reject missing, non-finite, or over-age quotes before signal generation and expose the rejection reason in diagnostics. Add a deterministic mocked test.
2. **High — active stop is not prompt.** Make the stop token part of the exchange call cancellation predicate (or add a bounded cancellation mechanism) while preserving accepted-order settlement/reconciliation. Add a deterministic blocked-request test asserting stop latency and zero new submissions.
3. **Medium — overload evidence.** The current implementation preserves the requested universe and avoids concurrent fan-out, but only logs a warning. A controlled benchmark should be run in a sandbox/mock environment to record queue lag, request latency, and error rates before claiming runtime performance evidence.

## Verification limitations

- No live account, sandbox account, or exchange mock was available; no order was submitted.
- No local Docker/CMake/npm build or test command was run, per the remote-CI-required task policy.
- This report is an evidence-backed safety exercise, not approval for live trading. The two `FAIL` findings block a claim that every requested safety scenario passes.
