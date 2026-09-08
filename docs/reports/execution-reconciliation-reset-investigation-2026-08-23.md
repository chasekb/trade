# Execution reconciliation reset investigation — 2026-08-23

## Scope and safety

This is a read-only investigation of `GET /api/trading/execution-reconciliation?hours=24` while the C++ backend is unavailable or returns a database failure. No live order, simulated order, replay, start/stop action, account mutation, or local build/test command was performed.

## Deterministic reproduction and live probes

The supported stack was already running with the published `dev` images:

- `trade_cpp-backend_1`: `ghcr.io/chasekb/trade/cpp-backend:dev`, healthy, host `8081 -> 8080`.
- `trade_frontend_1`: healthy, host `3000 -> 3000`, configured with `BACKEND_URL=http://cpp-backend:8080`.

Read-only probes at 2026-08-23 07:16:43 UTC:

```text
curl --max-time 5 -sS -D - \
  'http://localhost:3000/api/trading/execution-reconciliation?hours=24'
HTTP/1.1 200 OK
content-type: application/json; charset=utf-8
server: drogon/1.9.11
```

The same request to `http://localhost:8081/...` also returned `200 OK`. Both bodies were valid reconciliation JSON with `by_strategy: []`, `signal_rows: 0`, `outcome_rows: 0`, and an `overall` object whose counters and PnL metrics were all zero. This is a valid empty response shape, but it is indistinguishable from a data outage unless the caller checks the response's provenance and freshness; it must not be treated as evidence that no signals or outcomes existed.

The control probe `GET http://localhost:8081/health` returned `200 OK` with `{"service":"trading-bot-cpp-backend","status":"healthy","version":"0.1.0"}`. Health only proves process availability, not reconciliation data availability.

A deterministic outage reproduction, without touching the trading API, is to make the configured `cpp-backend:8080` target unavailable (for example, reproduce against an isolated disposable frontend proxy or a stopped local backend only after an operator approves the operational interruption), then issue the same browser-facing GET and capture the frontend container log. Do not stop a shared/live trading service merely to run this test. The existing captured stack evidence already provides the failure boundary: Next logged `Failed to proxy http://cpp-backend:8080/...` followed by `read ECONNRESET`, `connect ECONNREFUSED`, and `getaddrinfo ENOTFOUND` during backend restart/disconnection. The exact reconciliation route was not present in that historical scrollback, but Next's rewrite target is route-independent.

## Backend contract and failure path

`src/api/PredictController.cpp:1673-1804` implements the read-only route. It initializes a response with zero counters and an empty `by_strategy`, reads signals and trades, then catches any database exception at lines 1789-1792:

```text
resp["error"] = e.what();
```

The catch does not set an HTTP error status. The route still serializes the partially initialized response through `HttpResponse::newHttpJsonResponse(resp)` at line 1803. Therefore a database/query failure can be returned as HTTP 200 with zero or partial metrics plus an `error` field. The frontend must classify the non-empty `error` field as unavailable/partial data, not as a successful empty window. The current source also queries `individual_trades.is_closing_leg` (line 1764); the captured runtime database log showed repeated PostgreSQL errors for unsupported `pg_input_is_valid(...)` in another dashboard query, confirming that runtime schema/query incompatibilities are plausible and can occur while the process remains healthy.

## Frontend path and observed state transitions

The current checked-out source has one consumer of this route:

```text
SimulatedTradingPanel.tsx:635-642
  useExecutionReconciliation({ hours: 24 })
SimulatedTradingPanel.tsx:795-807
  ExecutionReconciliationTable(...)
useExecutionReconciliation.ts:18-40
  React Query queryFn -> apiClient.getExecutionReconciliation -> normalize...
api.ts:675-709
  ApiClient.request
next.config.ts:21-32
  /api/:path* rewrite -> BACKEND_URL/api/:path*
```

`ApiClient.request` catches both non-2xx responses and thrown fetch errors (`ECONNRESET`, socket hang-up, refused connection, DNS failure, or a browser timeout) and returns `{status: 'error', error: message}`. It does not retry itself and does not impose an AbortController/request timeout. `useExecutionReconciliation` converts that error response into a thrown `Error` at lines 24-26. React Query's global defaults (`QueryProvider.tsx:11-21`) retry failed queries three times; the reconciliation hook additionally refetches every 60 seconds after success/failure state settles (`refetchInterval: 60000`, `staleTime: 55000`). These are read-only GETs, so the retries have no order side effect, but they can prolong a loading/error transition and add load while the backend is recovering.

`ExecutionReconciliationTable.tsx:32-50` has distinct states:

- `isLoading`: “Loading execution reconciliation…”
- `error`: “Execution reconciliation unavailable: <error message>”
- `reconciliation === null` without error: renders nothing
- a successful response with `error` in its JSON: renders the normalized snapshot and a red “Partial data” warning at lines 66-68, but still displays all zero/partial metrics.

`normalizeExecutionReconciliation` preserves the backend `error` string, while missing/malformed payloads normalize to an empty snapshot (`executionReconciliation.ts:149-168`). The hook currently rejects a transport/non-success response before normalization, so a transport reset does not become an empty zero snapshot in this path. The misleading case is an HTTP-200 backend error/partial payload: it is accepted as data, and its zero defaults are rendered alongside a warning. A valid empty window and a failed query therefore share the same zero metrics; only the optional warning distinguishes the latter, and a proxy reset has no response body to preserve.

The current `LiveTradingPanel.tsx` does not import or call `useExecutionReconciliation`; the route is presently mounted in the simulated panel only. Any claim that the live tab currently renders this table is not supported by the checked-out source and should be verified against the deployed frontend/image separately.

## Relevant runtime logs

Freshly captured pane `0:7.0` contained these historical restart/disconnect boundaries:

- cpp-backend: `FATAL Transport endpoint is not connected (errno=107) sockets::shutdownWrite`.
- frontend: `Failed to proxy http://cpp-backend:8080/api/products Error: read ECONNRESET`.
- frontend: `connect ECONNREFUSED 10.89.1.4:8080` and later `10.89.1.6:8080` / `10.89.1.7:8080`.
- frontend: `getaddrinfo ENOTFOUND cpp-backend`.
- PostgreSQL: repeated `function pg_input_is_valid(text, unknown) does not exist` errors.

The pane later showed database/Redis shutdown messages. These logs establish transport and runtime restart behavior, but the route-specific request should be captured during a future approved isolated reproduction to bind the errors to reconciliation rather than to the adjacent dashboard requests shown in that scrollback.

## Findings and acceptance implications

1. **Transport reset/refusal/DNS failure:** Next's proxy logs the error; `fetch` rejects; `ApiClient.request` returns `status: 'error'`; the hook throws; the table displays an actionable unavailable message. It does not silently fabricate zero reconciliation data.
2. **Backend HTTP 4xx/5xx:** the API client discards the response body and reports only `HTTP error! status: N`; the hook/table show unavailable but lose any safe backend diagnostic/error code. This is actionable only at status level.
3. **Backend HTTP 200 with `error`:** the API client marks it successful; normalization preserves the error; the table shows “Partial data” but still renders zero/partial counters. This is the misleading empty/zero path and should be changed so the UI makes failure/partial availability primary and does not present zero metrics as a clean result.
4. **Valid empty result:** HTTP 200 with no `error` and zero rows is a legitimate “no signals or outcomes recorded” response. It should remain distinct from failure and continue to render the existing empty-window message.
5. **Retries:** global React Query retry=3 applies to this read-only query. Acceptance should require bounded, observable read retries only; no mutation retry or live-order side effect.
6. **Live tab scope:** no current source consumer was found in `LiveTradingPanel.tsx`; acceptance should cover the actual simulated consumer and separately verify any deployed/live-tab integration if the product requirement expects both tabs.

Recommended implementation seam for the dependent change: treat a non-empty backend `error` as a failed/partial query contract before rendering zero metrics; preserve safe status/body diagnostics for non-2xx responses; add deterministic fixtures for transport error, HTTP error, HTTP-200 `{error, zero metrics}`, and clean empty success; retain successful non-empty rendering. Do not change order/execution code.
