# Live and simulated order-book API contract

Status: implementation specification
Scope: `GET /api/orderbook/live-signals` and `GET /api/orderbook/simulated-signals`

This is the smallest shared read contract for the Live Trading and Simulated Trading order-book widgets. It normalizes the read model only. It does not make Coinbase quotes synthetic, turn simulated fills into exchange orders, remove live account/risk gates, or treat a display row as an order intent.

## 1. Request

Both routes accept the same query parameters:

| Parameter | Required | Contract |
| --- | --- | --- |
| `symbols` | no | Comma-separated selected symbols. Each item is trimmed, converted to the canonical uppercase `BASE-QUOTE` form, and empty items are discarded. Invalid symbols are rejected with HTTP 400. Duplicates are removed after canonicalization, preserving first-seen order. The server must not silently substitute a smaller universe. Omitted/empty means the service's current universe. |
| `page` | no | One-based display page. Default `1`; values below `1` are normalized to `1`. |
| `per_page` | no | Positive display-row count. Default `10`; values below `1` are normalized to `1`; values above the documented maximum `100` are normalized to `100`. The value never reduces selected-universe fetch coverage. |

The canonical symbol grammar is one or more uppercase ASCII letters/digits for each asset, separated by one hyphen (for example `BTC-USD`). Input is trimmed and uppercased before validation against `^[A-Z0-9]+-[A-Z0-9]+$`; anything else is rejected with HTTP 400. The frontend may split a large selected universe into request chunks. Each chunk request must fetch all latest-by-symbol rows for that chunk before the frontend merges, deduplicates, sorts, and applies display pagination. A page is never a coverage limit.

## 2. Normalized response envelope

The endpoint returns HTTP 200 for a valid read, including an empty, stale, or partially covered result. It returns a non-2xx response only when the request cannot be processed (for example, a database/service failure); the body must still use the error shape in section 7.

```json
{
  "signals": [],
  "total_analyzed": 0,
  "active_signals": 0,
  "average_strength": 0.0,
  "last_updated": null,
  "as_of": "2026-08-22T18:00:05.000Z",
  "mode": "live",
  "pagination": {
    "page": 1,
    "per_page": 10,
    "total_signals": 0,
    "total_pages": 0,
    "has_next": false,
    "has_prev": false
  },
  "coverage": {
    "requested_symbol_count": 0,
    "covered_symbol_count": 0,
    "missing_symbol_count": 0,
    "row_count": 0,
    "requested_symbols": [],
    "missing_symbols": [],
    "complete": true,
    "state": "complete"
  },
  "freshness": {
    "latest_signal_at": null,
    "oldest_returned_signal_at": null,
    "max_age_seconds": null,
    "max_lag_seconds": null,
    "state": "empty"
  },
  "diagnostics": {
    "status": "empty",
    "message": "No latest signal is available for the requested universe.",
    "freshness_threshold_seconds": null,
    "failed_chunk_count": 0,
    "failed_symbol_count": 0,
    "failed_chunks": [],
    "failed_symbols": [],
    "incomplete_source": false,
    "failure_origin": null
  }
}
```

Required top-level fields are `signals`, `total_analyzed`, `active_signals`, `average_strength`, `last_updated`, `as_of`, `mode`, `pagination`, `coverage`, `freshness`, and `diagnostics`. `last_updated` is the newest real signal timestamp and is null when there are no real rows. `as_of` is the server response time, not market time. All timestamps are UTC RFC 3339 strings with `Z`; epoch seconds must not be exposed in this contract.

`signals.length` is only the number of rows on the requested page. Define `R` as the number of real latest-by-symbol rows and `P` as the number of selected symbols represented by response-only placeholders. For a selected universe, `total_analyzed = pagination.total_signals = R + P`; `coverage.covered_symbol_count = R`; and `coverage.missing_symbol_count = P`. Thus placeholders are included in the population and in `signals` pagination, while coverage's covered count means real data only. For an omitted universe, `P` is zero unless the service explicitly reports a selected universe and missing symbols.

## 3. Signal row schema

Every returned row is a normalized latest record for exactly one symbol. Required fields:

```json
{
  "signal_id": "sig-123",
  "session_id": "session-abc",
  "symbol": "BTC-USD",
  "signal_type": "buy",
  "signal": "buy",
  "signal_generated": true,
  "signal_strength": 0.72,
  "price": 64250.10,
  "timestamp": "2026-08-22T18:00:01.000Z",
  "data_status": "sufficient",
  "signal_reason": "positive fee-adjusted order-book edge",
  "spread": 0.80,
  "volume": 1250000.0,
  "best_bid": 64249.70,
  "best_ask": 64250.50,
  "mid_price": 64250.10,
  "imbalance": 0.34,
  "order_book_depth": 20,
  "response_only": false,
  "execution_analysis": {
    "executable_intent": true,
    "blocked": false,
    "intended_action": "buy"
  }
}
```

Field semantics and units:

- `signal_id`, `symbol`, `signal_type`, `signal`, and `signal_reason` are strings. `session_id` is a string for producer rows and is `null` for a response-only placeholder. `signal_type` and `signal` are identical normalized values: `buy`, `sell`, or `hold`.
- `signal_generated`: boolean. It is true only for `buy` or `sell`; a valid strategy HOLD is false.
- `signal_strength`: normalized unitless value in `[0, 1]`.
- `price`, `best_bid`, `best_ask`, `mid_price`, `spread`: decimal quote-currency units per base unit. `spread` is absolute ask minus bid, not a percentage.
- `volume`: decimal base-asset units for the snapshot/strategy volume definition. It is not USD unless explicitly named otherwise.
- `imbalance`: unitless signed order-book imbalance. Positive is bid-dominant; negative is ask-dominant. `imbalance_ratio` may remain as a legacy alias but is not required by new consumers.
- `order_book_depth`: integer number of levels represented.
- `timestamp`: UTC time at which the signal/snapshot was produced, not response time.
- `data_status`: `sufficient`, `insufficient`, or `missing`. `sufficient` includes a strategy HOLD caused by profitability or strategy gates. `insufficient` means the data cannot support a decision. `missing` is reserved for a response-only coverage placeholder.
- `response_only`: boolean. It is false for persisted/generated records and true only for a missing-coverage placeholder. Response-only rows never persist and never create an order intent.

The required-field placeholder schema is exact (no producer values are copied into it): `signal_id="missing:<canonical-symbol>"`, `session_id=null`, `symbol` is the canonical requested symbol, `signal_type="hold"`, `signal="hold"`, `signal_generated=false`, `signal_strength=0`, `price=null`, `timestamp=null`, `data_status="missing"`, `signal_reason="No latest signal is available for this symbol."`, `spread=null`, `volume=null`, `best_bid=null`, `best_ask=null`, `mid_price=null`, `imbalance=null`, `order_book_depth=0`, `response_only=true`, and `execution_analysis={"executable_intent":false,"blocked":true,"intended_action":null}`. All market/timestamp fields above are JSON null, not zero or a response timestamp. `criteria_analysis`, `ml_analysis`, and `strength_composition` are omitted for placeholders. The deterministic ID is unique within a response because canonical symbols are deduplicated; placeholder rows are never persisted.

Optional diagnostic objects (`criteria_analysis`, `ml_analysis`, `strength_composition`, and `execution_analysis`) are passed through with their existing field names. Numeric expected-return fields are quote-currency PnL per unit/order according to their existing producer definition; they must not be interpreted as percentages. If ML expected return is unavailable, the producer sets `expected_return_available=false`; consumers display `Unavailable`, not zero.

## 4. Latest-by-symbol and ordering rules

1. Filter by the requested symbol set before selecting latest rows.
2. Select one row per symbol using greatest `timestamp`. If timestamps tie, use greatest stable record identity (`signal_id` or database insertion identity) so selection is deterministic.
3. A live or active simulated response uses the in-memory latest record. A cold/stopped response may use persisted history, but applies the same one-row-per-symbol rule.
4. Sort the complete selected set before pagination: `signal_strength DESC`, then `timestamp DESC`, then `symbol ASC`. The final symbol tie-breaker is mandatory.
5. Apply `page` and `per_page` after selection and sorting. `total_analyzed`, active counts, average strength, coverage, and freshness are computed before slicing.
6. `active_signals` counts rows whose normalized `signal_generated` is true, including rows not on the requested page. It never counts response-only placeholders.
7. `average_strength` is the arithmetic mean of real latest rows before pagination. It is `0.0` when there are no real rows; placeholders are excluded.

`pagination.total_pages = 0` when `total_signals=0`; otherwise it is `ceil(total_signals / per_page)`. A page greater than `total_pages` is valid and returns `signals=[]` with the same population-wide counts, `has_prev=true`, and `has_next=false`; page 1 is the only page with `has_prev=false`. An empty result therefore has `page=1`, `total_pages=0`, `has_prev=false`, and `has_next=false`.

## 5. Selected-universe coverage

When `symbols` is provided, `coverage.requested_symbols` is the normalized, de-duplicated request list in first-seen order. `requested_symbol_count` is its length. `covered_symbol_count` counts real latest rows, and `missing_symbols` contains requested symbols with no usable latest row. `missing_symbol_count = requested_symbol_count - covered_symbol_count` and `coverage.row_count = covered_symbol_count + missing_symbol_count`; `row_count` is the number of real rows plus placeholders before pagination.

`coverage.state` is:

- `complete`: all requested symbols have a real latest row;
- `partial`: at least one requested symbol has a real row and at least one is missing;
- `empty`: the request is empty or no real row exists;
- `degraded`: the service/read failed for one or more chunks or returned a known incomplete source result.

`coverage.complete` is true only for `complete` (or an omitted/empty universe with no known selected symbols). A missing live quote due to cadence/rotation is not silently omitted: the response includes the exact placeholder defined in section 3. Placeholder rows participate in `total_analyzed`, pagination, and `row_count`; they do not participate in `covered_symbol_count`, `active_signals`, `average_strength`, or execution.

For simulated active sessions, the worker is expected to update every selected symbol each tick; a missing row therefore indicates warm-up or producer failure. For live, Coinbase quote cadence and account/exchange availability are intentional live-only differences and must be visible in diagnostics, never converted into a false complete state.

## 6. Freshness and lag

Freshness is measured against `as_of`:

- `age_seconds = max(0, as_of - signal.timestamp)` for each real row;
- `max_age_seconds` is the maximum age across real rows, null when there are none;
- `latest_signal_at` is the newest real row timestamp;
- `oldest_returned_signal_at` is the oldest real row timestamp;
- `max_lag_seconds` is the producer lag supplied by the source when known: `as_of - source_observed_at`. It is null when source-observed time is unavailable. It must not be inferred from a placeholder timestamp.

`freshness.state` is `empty` when there are no real rows; with real rows it is `fresh` when every real row is at or below the threshold, `stale` when any exceeds it, and `unknown` when no threshold is supplied. Missing producer lag does not make freshness unknown when a threshold is available. `diagnostics.freshness_threshold_seconds` is always present and is either a non-negative number or null. It is producer-owned: a producer-supplied threshold is authoritative; the frontend may display a configured fallback only if it labels it `frontend`, does not rewrite the API state, and records that fallback in its own diagnostics. The frontend must never label a row fresh merely because the HTTP request succeeded.

## 7. Empty, error, and degraded behavior

An empty valid read is HTTP 200 with the full envelope, `signals=[]`, zero counts, null signal timestamps, and `diagnostics.status=empty`. It is not an exception and must not fabricate a current timestamp as `last_updated`.

A total read failure is a non-2xx response:

```json
{
  "status": "error",
  "error": {
    "code": "ORDERBOOK_READ_FAILED",
    "message": "Order-book signal data is temporarily unavailable.",
    "retryable": true
  },
  "as_of": "2026-08-22T18:00:05.000Z"
}
```

Error messages must be operator-safe and contain no credentials, SQL, or account secrets. A frontend transport failure must remain an error state; it must not be converted into a successful zero-row response.

A partial/chunk failure is HTTP 200 only when at least one chunk returned a valid envelope. It returns the successful rows plus placeholders for failed/missing selected symbols, `coverage.state=degraded`, `complete=false`, and `diagnostics.status=degraded`. `diagnostics` always contains `failed_chunk_count` (integer), `failed_symbol_count` (integer), `failed_symbols` (canonical strings, sorted), and `failed_chunks` (sorted objects `{chunk_id:string, requested_symbols:string[], failure_class:"retryable"|"permanent", retryable:boolean, message:string}`); `retryable` must agree with `failure_class`. `failure_origin` is `backend`, `frontend`, `mixed`, or null: backend means the source returned a known partial result, frontend means a chunk request failed locally/in transit, and mixed means both. `incomplete_source` is true when the backend itself reports a known partial source, false for a complete source, and is OR-merged across frontend chunks. Frontend merging canonicalizes and deduplicates rows by symbol after all successful chunks; latest timestamp, then signal ID, wins. Failed-symbol lists and chunk objects are unioned/deduplicated by ID, and placeholders are added once per requested symbol not represented by a real row. If every chunk fails, use the total error response instead.

## 8. Frontend widget diagnostics

The shared widget must display, or expose in an accessible details section, these facts:

- mode (`live` or `simulated`) and `as_of`;
- `covered_symbol_count / requested_symbol_count` and `coverage.state`;
- first missing symbols, if any;
- `freshness.state`, `max_age_seconds`, `max_lag_seconds`, and `diagnostics.freshness_threshold_seconds` (or an explicitly labelled frontend fallback);
- whether rows are response-only and therefore cannot submit orders;
- active signal count and average strength across the complete population, not the visible page;
- degraded/failed chunk count and retry guidance when present;
- live producer cadence/fan-out warnings separately from selected-universe coverage.

The widget must distinguish `data_status=insufficient` (cannot evaluate), `data_status=missing` (no row for coverage), and a `sufficient` `hold` (evaluated but no trade). It must never show a missing placeholder as an actionable signal and must never infer live execution readiness from signal availability.

## 9. Worked examples

### Successful complete response

A selected five-symbol universe has five real latest rows, page 1 of 2, and all rows are fresh. `coverage.state=complete`, `freshness.state=fresh`, `total_analyzed=5`, `pagination.total_signals=5`, and `active_signals` counts all five-row results even if only three are visible.

### Stale response

The newest row is 42 seconds old and the producer threshold is 10 seconds. Return the rows normally, set `freshness.state=stale`, `max_age_seconds=42`, include `freshness_threshold_seconds=10` in diagnostics, and show a stale warning. Do not turn stale data into an error or an actionable-ready state.

### Paginated response

For 23 latest rows and `page=2&per_page=10`, return rows 11–20 after the required sort, `total_analyzed=23`, `pagination.total_signals=23`, `total_pages=3`, `has_prev=true`, and `has_next=true`. Counts and averages remain population-wide.

### Degraded partial response

For a requested 100-symbol universe where 96 real rows arrive and four symbols fail in one frontend chunk, return 100 rows before pagination: 96 real rows plus four exact placeholders. Set `total_analyzed=100`, `pagination.total_signals=100`, `coverage.requested_symbol_count=100`, `covered_symbol_count=96`, `missing_symbol_count=4`, `coverage.row_count=100`, `coverage.state=degraded`, `complete=false`, `failed_chunk_count=1`, and `failed_symbol_count=4`. Do not report 100 covered symbols or silently retry forever. If no chunk succeeds, return HTTP error instead.

## 10. Implementation acceptance checklist

- Both routes serialize the same envelope and row field names; only `mode` and source-specific diagnostics differ.
- Latest-by-symbol selection, tie-breaking, ordering, and population-wide metrics are identical in live and simulated reads.
- Display pagination occurs after complete selected-universe collection/merge.
- Coverage distinguishes real, missing, and degraded data and never fabricates execution capability.
- Timestamps, units, empty behavior, error behavior, and response-only placeholders follow this document.
- Frontend types, normalizer, hook merge logic, and widget diagnostics consume the contract without mode-specific field guesses.
- Backend, frontend, and contract tests cover complete, stale, paginated, empty, and degraded responses.
