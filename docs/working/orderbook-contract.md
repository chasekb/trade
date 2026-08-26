# Live and Simulated Trading Order-Book Contract

Status: normative, implementation-ready v1 contract
Scope: equivalent read semantics for Live Trading and Simulated Trading order-book signal endpoints
Routes: `/api/orderbook/live-signals` and `/api/orderbook/simulated-signals`

## 1. Contract decision record

Both routes return the same envelope, field names, units, ordering, status vocabulary, error behavior, and pagination semantics. `mode` is the only required mode distinction (`live` or `simulated`); `source` records provenance and does not change interpretation. Existing legacy signal fields may remain during migration, but the fields in this document are canonical. A consumer that cannot understand the declared major version MUST fail closed with a visible unsupported-schema state.

The service boundary owns request normalization, source reads, latest-by-symbol reduction, malformed-row rejection, coverage classification, freshness calculation, snapshot creation, and pagination. The frontend owns rendering, transport retry policy, and merging concurrently fetched pages/chunks; it MUST apply the same identity and winner rules and MUST never use arrival order.

### 1.1 Normative terms

`MUST`, `MUST NOT`, `REQUIRED`, `SHALL`, and `SHALL NOT` are normative. `SHOULD` identifies a recommended default that may be deviated from only with an explicit operational reason. `MAY` is optional.

### 1.2 Compatibility and versioning

Success envelopes use `schema_version: "orderbook-coverage.v1"`; error envelopes use `schema_version: "orderbook-error.v1"`. v1 is additive: unknown fields MUST be ignored, while existing fields retain their meaning, unit, and nullability. Required fields MUST NOT be removed, renamed, or repurposed within v1. A breaking change requires a new major version, route/media-type negotiation, and a documented migration period. During migration, legacy aliases may be emitted, but canonical fields are authoritative and both routes MUST serialize the same v1 semantics.

## 2. Request contract

### 2.1 Symbol selection

- Omitted `symbols` resolves to the source's configured current universe.
- Present `symbols=` or an explicitly empty JSON selection means an explicitly empty universe; it MUST NOT fall back to the configured universe.
- For comma-separated input, trim ASCII surrounding whitespace, reject empty tokens, uppercase ASCII, validate the source's supported instrument spelling, and deduplicate after canonicalization while preserving first-seen order in `coverage.requested_symbols`.
- Syntactically valid but unsupported symbols are retained in the requested universe and represented as `unavailable` diagnostics; they are never silently dropped. Malformed symbols, empty tokens, and invalid encoding are request errors (HTTP 400).
- Response symbol arrays other than `requested_symbols` are sorted by canonical UTF-8 byte order. Canonical symbol identity is case-insensitive at input and uppercase at the wire boundary.

### 2.2 Numeric pagination

`page` is 1-based. Missing `page` defaults to `1`; missing `per_page` defaults to `10`. Supplied values MUST match unsigned decimal ASCII `^[1-9][0-9]*$`; signs, whitespace, decimal points, exponents, leading-zero forms, empty values, overflow, and language-parser coercion are invalid. `page` is limited to `1..2147483647`; `per_page` to `1..100`. Invalid supplied values return HTTP 400 with error code `INVALID_PAGINATION` and no snapshot.

`page_token` is optional continuation. `page` and `page_token` are mutually exclusive. A continuation request MAY supply `per_page` only if it equals the token value. Invalid, expired, tampered, unknown-version, wrong-mode, request-mismatched, or page-size-mismatched tokens return HTTP 400 with `INVALID_PAGE_TOKEN`; the server MUST NOT silently restart from page 1.

## 3. Processing pipeline and invariants

The backend MUST perform this pipeline atomically for a new request:

1. Normalize and validate request parameters.
2. Read source chunks for the selected universe.
3. Reject malformed rows at the row boundary.
4. Canonicalize symbols and reduce candidates to one latest row per canonical symbol.
5. Add deterministic response-only placeholders for requested symbols with no usable row.
6. Sort the complete population by canonical symbol byte order.
7. Compute totals, coverage, freshness, and diagnostics over the complete population.
8. Freeze the resulting population and diagnostics in a five-minute snapshot.
9. Slice the frozen population for the requested page and mint an opaque continuation token when needed.

Population-wide fields MUST be identical on every page of one snapshot. A source update after snapshot creation MUST NOT alter later pages. A snapshot eviction is an invalid/expired token outcome, not a mixed fresh page.

### 3.1 Latest-row winner tuple

The identity key is canonical `symbol`. For candidates of one symbol, the greatest tuple wins:

1. `event_timestamp` descending: `order_book.exchange_at` when non-null, otherwise `order_book.ingested_at`.
2. `version` descending: `order_book.sequence` parsed as an unsigned 64-bit integer; missing legacy sequence is `0`.
3. `record_key` ascending: producer-issued UUID string compared as ASCII/UTF-8 bytes.

`record_key` is required for new rows and is the stable cross-mode tie-breaker. A legacy row without one receives `legacy:<sha256>` from canonical UTF-8 JSON of source, canonical symbol, event timestamp, version, and normalized payload. Exact duplicates collapse. Conflicting payloads with the same tuple select the lexicographically smallest canonical JSON and add a `duplicate_conflict` diagnostic. Storage insertion identity, arrival order, pointer identity, locale collation, and database row order MUST NOT be used.

The frontend MUST apply this same tuple when deduplicating or merging page/chunk data. Older or out-of-order arrivals cannot replace a winner. A later arrival replaces it only when its tuple wins.

### 3.2 Stable ordering and pagination

After reduction, rows (including placeholders) are sorted by canonical `symbol` ascending using UTF-8 byte order. This order is independent of strength, signal, source, and arrival time. `total_analyzed`, `pagination.total_signals`, and `coverage.row_count` equal the frozen population size, including placeholders. `total_pages = ceil(total_analyzed / per_page)`, or `0` for an empty population. A page beyond range is valid HTTP 200 with `signals: []`, unchanged population-wide fields, and `next_page_token: null`.

The continuation token is an opaque URL-safe base64url value containing an authenticated versioned envelope with snapshot ID, mode/source, canonical request hash, per-page size, next index, expiry, and MAC. Clients MUST treat it as opaque. Tokens expire five minutes after snapshot creation and MUST not expose records, credentials, or implementation secrets.

## 4. Canonical success envelope

All fields below are present in every HTTP 200 response. JSON `null` means unknown/not applicable and MUST NOT be replaced by zero, an empty string, or a fabricated timestamp.

| Field | Type | Definition and unit |
|---|---|---|
| `schema_version` | string | Exactly `orderbook-coverage.v1`. |
| `signals` | array | Current page of normalized rows, including placeholders for requested symbols without usable rows. |
| `total_analyzed` | integer | Complete frozen population count; real rows plus placeholders; non-negative. |
| `active_signals` | integer | Pre-pagination count of real rows whose `signal_generated` is true; placeholders never count. |
| `average_strength` | number | Pre-pagination arithmetic mean of real-row `signal_strength`, unitless; `0.0` when none. |
| `last_updated` | RFC 3339 UTC string or null | Newest real row's `timestamp`; null when no real row exists. |
| `as_of` | RFC 3339 UTC string | Server response creation time, UTC `Z`; used for envelope age calculations. |
| `mode` | string | Exactly `live` or `simulated`. |
| `pagination` | object | Fields in section 5; totals are pre-pagination and authoritative. |
| `coverage` | object | Fields in section 6; counts reconcile with the frozen population. |
| `freshness` | object | Fields in section 7; metrics are population-wide. |
| `diagnostics` | object | Fields in section 8; operator-safe, no secrets or SQL/provider internals. |

### 4.1 Signal row

A real row contains existing compatible signal fields plus the following canonical fields. `signal` and `signal_type` are retained aliases and MUST have the same lowercase value.

| Field | Type | Definition and unit |
|---|---|---|
| `record_key` | string | Required stable producer UUID, or deterministic `legacy:<sha256>` for legacy data. |
| `signal_id` | string | Required opaque signal-decision ID; unique after normalization. |
| `session_id` | string or null | Trading session identity; null means no session. |
| `symbol` | string | Canonical uppercase instrument ID. |
| `signal` / `signal_type` | string | `buy`, `sell`, or `hold`; unitless decision. |
| `signal_generated` | boolean | True exactly for `buy` or `sell`; false for `hold` and placeholders. |
| `signal_strength` | number | Finite unitless value in `[0,1]`; `0.0` for placeholders. |
| `price` | number or null | Quote-currency per base unit; null when no usable market price. |
| `timestamp` | RFC 3339 UTC string or null | Exact alias of real row `order_book.ingested_at`; null for placeholders. |
| `data_status` | string | `sufficient`, `insufficient`, or `missing`; stale/delay is represented in freshness fields. |
| `signal_reason` | string | Operator-safe explanation. |
| `response_only` | boolean | False for real rows; true for placeholders. |
| `order_book` | object or null | Normalized book for real rows, including empty books; null only for placeholders. |
| `execution_analysis` | object | Includes `executable_intent`, `blocked`, and `intended_action`; placeholders MUST be blocked and non-executable. |

A placeholder has `record_key: "missing:<canonical-symbol>"`, `signal_id: "missing:<canonical-symbol>"`, `session_id: null`, `signal: "hold"`, `signal_type: "hold"`, `signal_generated: false`, `signal_strength: 0.0`, `price: null`, `timestamp: null`, `data_status: "missing"`, `response_only: true`, `order_book: null`, and `execution_analysis: {"executable_intent": false, "blocked": true, "intended_action": null}`. Placeholder IDs are unique because symbols are deduplicated; they participate in totals, ordering, and pagination but never in active counts, averages, freshness, or execution.

### 4.2 Normalized `order_book`

| Field | Type | Definition and unit |
|---|---|---|
| `instrument` | string | Same canonical value as enclosing `symbol`. |
| `source` | string | Provenance: `coinbase_public_l2`, `simulated_fixture`, or `simulated_live_parity`; not a freshness state. |
| `bids` | array | Level objects sorted by descending price; may be empty. |
| `asks` | array | Level objects sorted by ascending price; may be empty. |
| `depth` | integer | `min(len(bids), len(asks))`; non-negative usable level count. |
| `best_bid` / `best_ask` | number or null | Quote currency per base unit; null iff that side is empty. |
| `mid_price` | number or null | `(best_bid + best_ask)/2` when both exist; otherwise null. |
| `spread` | number or null | `best_ask - best_bid` in quote currency per base unit when both exist; otherwise null. |
| `spread_bps` | number or null | `spread / mid_price * 10000` basis points when mid is positive; otherwise null. |
| `bid_quantity` / `ask_quantity` | number | Aggregate base-asset quantity across returned levels; zero for an empty side. |
| `imbalance` | number or null | `(bid_quantity - ask_quantity)/(bid_quantity + ask_quantity)` unitless; null for zero denominator. |
| `sequence` | string | Unsigned decimal producer version, opaque except for numeric winner comparison; never a timestamp. |
| `snapshot_id` | string | Stable opaque ID for the exact normalized snapshot. |
| `exchange_at` | RFC 3339 UTC string or null | Source/exchange event time; never fabricated. |
| `ingested_at` | RFC 3339 UTC string | Producer normalization/acceptance time. |
| `observed_at` | RFC 3339 UTC string | v1 alias exactly equal to `ingested_at`. |
| `lag_ms` | integer or null | `max(0, ingested_at - exchange_at)` in milliseconds when both exist; null otherwise. |
| `freshness_threshold_ms` | integer or null | Positive producer threshold in milliseconds; null means unavailable. |
| `freshness_state` | string | `fresh`, `stale`, or `unknown`; producer-computed. |

A level is exactly `{ "price": number, "quantity": number }`. Both values MUST be finite and strictly positive. Levels MUST obey the configured/documented maximum. Crossed or inconsistent books (`best_bid >= best_ask`), malformed arrays, non-finite values, and invalid derived values invalidate the complete source snapshot; they MUST NOT be serialized as partial trusted data.

Empty books are valid covered rows: both sides empty, `depth=0`, best/mid/spread/spread_bps null, quantities zero, imbalance null, `data_status="insufficient"`, `signal="hold"`, and no executable intent. They are not missing symbols.

## 5. Pagination object

| Field | Type | Definition |
|---|---|---|
| `page` | integer | Requested 1-based page. |
| `per_page` | integer | Effective page size, 1..100. |
| `total_signals` | integer | Exact frozen population size; equals `total_analyzed`. |
| `total_pages` | integer | Ceiling of total signals/per_page; zero when population empty. |
| `has_next` / `has_prev` | boolean | Whether adjacent page exists; `has_prev` is false on page 1. |
| `next_page_token` | string or null | Opaque continuation token when another page exists; null otherwise. |

## 6. Coverage object

| Field | Type | Definition |
|---|---|---|
| `requested_symbols` | array[string] | Unique canonical selected universe; omitted input is resolved universe. |
| `requested_symbol_count` | integer | Length of requested_symbols. |
| `covered_symbols` | array[string] | Symbols with a real usable row, sorted. |
| `covered_symbol_count` | integer | Length of covered_symbols; placeholders excluded. |
| `missing_symbols` | array[string] | Union of unavailable and errored symbols, sorted. |
| `missing_symbol_count` | integer | Length of missing_symbols. |
| `unavailable_symbols` | array[string] | Source answered successfully but supplied no usable row, sorted. |
| `errored_symbols` | array[string] | Source/validation failures, sorted. |
| `symbol_diagnostics` | array[object] | Exactly one object per requested symbol, in requested_symbols order; authoritative per-symbol status. |
| `row_count` | integer | Frozen population count, including placeholders; equals total_analyzed. |
| `complete` | boolean | True only for a non-empty universe where every symbol has a real row and no source error; false for empty, partial, or degraded coverage. |
| `state` | string | `complete`, `partial`, `degraded`, or `empty`. |

Each `symbol_diagnostics` object has `symbol`, `status` (`healthy`, `stale`, `delayed`, `unavailable`, or `errored`), operator-safe `message`, `age_seconds` (non-negative number or null), `lag_seconds` (non-negative number or null), `retryable` (boolean), and `source` (`backend`, `frontend`, or `none`). Real rows use healthy/stale/delayed; unavailable and errored rows use null ages. Aggregate arrays/counts are projections, not an alternate authority.

`empty` means no symbols were selected or no real rows exist for the selected population and is HTTP 200. `partial` means some requested symbols have real rows and some are unavailable/errored. `degraded` means at least one source/chunk explicitly reports known incomplete data; it may have real rows and placeholders. `failed` is not a successful coverage state: if all reads fail, return an HTTP error instead.

## 7. Freshness object

| Field | Type | Definition and unit |
|---|---|---|
| `latest_signal_at` | RFC 3339 UTC string or null | Newest real `timestamp`, population-wide. |
| `oldest_population_signal_at` | RFC 3339 UTC string or null | Oldest real `timestamp`, population-wide and unchanged across pages. |
| `max_age_seconds` | number or null | Maximum `max(0, as_of - timestamp)` over real rows; seconds. |
| `max_lag_seconds` | number or null | Maximum source-reported lag; seconds; null if unavailable. |
| `state` | string | `healthy`, `stale`, `delayed`, `unknown`, or `empty`. |

Freshness is computed before pagination. A producer-supplied non-negative `freshness_threshold_seconds` and optional `delay_threshold_seconds` appear in diagnostics. With real rows, any age over the freshness threshold makes state `stale`; source lag over the delay threshold makes state `delayed` and takes display precedence. With no threshold, state is `unknown` unless the producer explicitly declares healthy. With no real rows, state is `empty`. The frontend MUST NOT infer status from its wall clock or replace null with a local threshold. A negative source time difference is clamped to zero for display and recorded as `clock_skew_detected`.

## 8. Diagnostics object and errors

Success diagnostics contains `status` (`healthy`, `stale`, `delayed`, `partial`, `degraded`, or `empty`), operator-safe `message`, `freshness_threshold_seconds`, `delay_threshold_seconds`, `failed_chunk_count`, `failed_symbol_count`, `failed_chunks`, `failed_symbols`, `source_error`, `validation_error`, `incomplete_source`, and `failure_origin` (`backend`, `frontend`, `mixed`, or null). `failed_chunks` entries contain `chunk_id`, `requested_symbols`, `failure_class` (`retryable` or `permanent`), `retryable`, and safe `message`. Counts and arrays MUST reconcile. No credentials, SQL, stack traces, or sensitive provider detail may be returned.

A failed read uses this envelope:

```json
{
  "schema_version": "orderbook-error.v1",
  "status": "error",
  "error": {
    "code": "ORDERBOOK_READ_FAILED",
    "message": "Order-book signal data is temporarily unavailable.",
    "retryable": true
  },
  "as_of": "2026-08-26T18:00:05.000Z"
}
```

HTTP outcomes:

| Condition | HTTP | Code/state |
|---|---:|---|
| Invalid symbol syntax, empty token, or pagination | 400 | `INVALID_PARAMETERS` or `INVALID_PAGINATION` |
| Invalid, mismatched, tampered, or expired token | 400 | `INVALID_PAGE_TOKEN` |
| Valid empty selection/no usable rows | 200 | `coverage.state=empty` |
| Usable partial or explicitly incomplete source | 200 | `coverage.state=partial` or `degraded` |
| All source chunks fail or timeout | 502/503/504 | error envelope; no snapshot/token |
| Internal database/serialization failure | 500 | error envelope; no partial success |

Malformed upstream rows are rejected and recorded as validation/chunk errors. If at least one valid chunk remains, the response is degraded/partial HTTP 200; if none remains, the request is an HTTP error. A transport failure MUST NOT be converted into a synthetic HOLD row.

## 9. Canonical JSON examples

All example timestamps are RFC 3339 UTC with `Z`. Prices are USD per BTC; quantities are BTC; strength is unitless; ages/lags are seconds unless a field explicitly ends in `_ms`.

### 9.1 Healthy single-page response

```json
{
  "schema_version": "orderbook-coverage.v1",
  "signals": [{
    "record_key": "550e8400-e29b-41d4-a716-446655440000",
    "signal_id": "sig-btc-001",
    "session_id": "live-2026-08-26",
    "symbol": "BTC-USD",
    "signal": "buy",
    "signal_type": "buy",
    "signal_generated": true,
    "signal_strength": 0.82,
    "price": 65001.0,
    "timestamp": "2026-08-26T18:00:04.500Z",
    "data_status": "sufficient",
    "signal_reason": "Positive order-book imbalance.",
    "response_only": false,
    "order_book": {
      "instrument": "BTC-USD",
      "source": "coinbase_public_l2",
      "bids": [{"price":65000.0,"quantity":1.2},{"price":64999.0,"quantity":0.8}],
      "asks": [{"price":65002.0,"quantity":0.7},{"price":65003.0,"quantity":1.1}],
      "depth": 2,
      "best_bid": 65000.0,
      "best_ask": 65002.0,
      "mid_price": 65001.0,
      "spread": 2.0,
      "spread_bps": 0.307687574,
      "bid_quantity": 2.0,
      "ask_quantity": 1.8,
      "imbalance": 0.052631579,
      "sequence": "981234",
      "snapshot_id": "snap-btc-981234",
      "exchange_at": "2026-08-26T18:00:04.400Z",
      "ingested_at": "2026-08-26T18:00:04.500Z",
      "observed_at": "2026-08-26T18:00:04.500Z",
      "lag_ms": 100,
      "freshness_threshold_ms": 5000,
      "freshness_state": "fresh"
    },
    "execution_analysis": {"executable_intent": true,"blocked": false,"intended_action":"buy"}
  }],
  "total_analyzed": 1,
  "active_signals": 1,
  "average_strength": 0.82,
  "last_updated": "2026-08-26T18:00:04.500Z",
  "as_of": "2026-08-26T18:00:05.000Z",
  "mode": "live",
  "pagination": {"page":1,"per_page":10,"total_signals":1,"total_pages":1,"has_next":false,"has_prev":false,"next_page_token":null},
  "coverage": {"requested_symbols":["BTC-USD"],"requested_symbol_count":1,"covered_symbols":["BTC-USD"],"covered_symbol_count":1,"missing_symbols":[],"missing_symbol_count":0,"unavailable_symbols":[],"errored_symbols":[],"symbol_diagnostics":[{"symbol":"BTC-USD","status":"healthy","message":"Current order-book signal is available.","age_seconds":0.5,"lag_seconds":0.1,"retryable":false,"source":"backend"}],"row_count":1,"complete":true,"state":"complete"},
  "freshness": {"latest_signal_at":"2026-08-26T18:00:04.500Z","oldest_population_signal_at":"2026-08-26T18:00:04.500Z","max_age_seconds":0.5,"max_lag_seconds":0.1,"state":"healthy"},
  "diagnostics": {"status":"healthy","message":"All requested symbols are covered.","freshness_threshold_seconds":5,"delay_threshold_seconds":2,"failed_chunk_count":0,"failed_symbol_count":0,"failed_chunks":[],"failed_symbols":[],"source_error":null,"validation_error":null,"incomplete_source":false,"failure_origin":null}
}
```

### 9.2 Stale/lagging response with diagnostics

A stale or delayed valid read remains HTTP 200. The row is retained; it is never silently dropped or converted to a transport error.

```json
{
  "schema_version":"orderbook-coverage.v1","signals":[{"record_key":"7c1e5a1e-9b23-4f10-8e52-111111111111","signal_id":"sig-eth-old","session_id":null,"symbol":"ETH-USD","signal":"hold","signal_type":"hold","signal_generated":false,"signal_strength":0.2,"price":3500.0,"timestamp":"2026-08-26T17:58:00.000Z","data_status":"sufficient","signal_reason":"Signal retained while source is delayed.","response_only":false,"order_book":{"instrument":"ETH-USD","source":"coinbase_public_l2","bids":[{"price":3499.0,"quantity":3.0}],"asks":[{"price":3501.0,"quantity":2.0}],"depth":1,"best_bid":3499.0,"best_ask":3501.0,"mid_price":3500.0,"spread":2.0,"spread_bps":5.714285714,"bid_quantity":3.0,"ask_quantity":2.0,"imbalance":0.2,"sequence":"4400","snapshot_id":"snap-eth-4400","exchange_at":"2026-08-26T17:57:59.000Z","ingested_at":"2026-08-26T17:58:00.000Z","observed_at":"2026-08-26T17:58:00.000Z","lag_ms":1000,"freshness_threshold_ms":5000,"freshness_state":"stale"},"execution_analysis":{"executable_intent":false,"blocked":true,"intended_action":null}}],
  "total_analyzed":1,"active_signals":0,"average_strength":0.2,"last_updated":"2026-08-26T17:58:00.000Z","as_of":"2026-08-26T18:00:05.000Z","mode":"live",
  "pagination":{"page":1,"per_page":10,"total_signals":1,"total_pages":1,"has_next":false,"has_prev":false,"next_page_token":null},
  "coverage":{"requested_symbols":["ETH-USD"],"requested_symbol_count":1,"covered_symbols":["ETH-USD"],"covered_symbol_count":1,"missing_symbols":[],"missing_symbol_count":0,"unavailable_symbols":[],"errored_symbols":[],"symbol_diagnostics":[{"symbol":"ETH-USD","status":"delayed","message":"Source observation exceeds freshness threshold.","age_seconds":125,"lag_seconds":1,"retryable":true,"source":"backend"}],"row_count":1,"complete":true,"state":"complete"},
  "freshness":{"latest_signal_at":"2026-08-26T17:58:00.000Z","oldest_population_signal_at":"2026-08-26T17:58:00.000Z","max_age_seconds":125,"max_lag_seconds":1,"state":"delayed"},
  "diagnostics":{"status":"delayed","message":"Order-book data is stale and source lag is above the delay threshold.","freshness_threshold_seconds":5,"delay_threshold_seconds":0.5,"failed_chunk_count":0,"failed_symbol_count":0,"failed_chunks":[],"failed_symbols":[],"source_error":null,"validation_error":null,"incomplete_source":false,"failure_origin":null}
}
```

### 9.3 Multi-page response with continuation token

The token is intentionally opaque. Both pages use the same frozen population totals, coverage, and freshness values; rows are ordered `ADA-USD`, `BTC-USD`, `ETH-USD`.

```json
{
  "schema_version":"orderbook-coverage.v1",
  "signals":[{"record_key":"00000000-0000-0000-0000-000000000001","signal_id":"sig-ada","session_id":null,"symbol":"ADA-USD","signal":"hold","signal_type":"hold","signal_generated":false,"signal_strength":0.0,"price":0.4,"timestamp":"2026-08-26T18:00:01.000Z","data_status":"insufficient","signal_reason":"No executable imbalance.","response_only":false,"order_book":{"instrument":"ADA-USD","source":"simulated_fixture","bids":[],"asks":[],"depth":0,"best_bid":null,"best_ask":null,"mid_price":null,"spread":null,"spread_bps":null,"bid_quantity":0,"ask_quantity":0,"imbalance":null,"sequence":"1","snapshot_id":"sim-ada-1","exchange_at":null,"ingested_at":"2026-08-26T18:00:01.000Z","observed_at":"2026-08-26T18:00:01.000Z","lag_ms":null,"freshness_threshold_ms":5000,"freshness_state":"fresh"},"execution_analysis":{"executable_intent":false,"blocked":true,"intended_action":null}},{"record_key":"00000000-0000-0000-0000-000000000002","signal_id":"sig-btc","session_id":null,"symbol":"BTC-USD","signal":"hold","signal_type":"hold","signal_generated":false,"signal_strength":0.1,"price":65000,"timestamp":"2026-08-26T18:00:02.000Z","data_status":"sufficient","signal_reason":"No action.","response_only":false,"order_book":{"instrument":"BTC-USD","source":"simulated_fixture","bids":[{"price":64999,"quantity":1}],"asks":[{"price":65001,"quantity":1}],"depth":1,"best_bid":64999,"best_ask":65001,"mid_price":65000,"spread":2,"spread_bps":0.307692308,"bid_quantity":1,"ask_quantity":1,"imbalance":0,"sequence":"2","snapshot_id":"sim-btc-2","exchange_at":"2026-08-26T18:00:01.900Z","ingested_at":"2026-08-26T18:00:02.000Z","observed_at":"2026-08-26T18:00:02.000Z","lag_ms":100,"freshness_threshold_ms":5000,"freshness_state":"fresh"},"execution_analysis":{"executable_intent":false,"blocked":false,"intended_action":null}}],
  "total_analyzed":3,"active_signals":0,"average_strength":0.1,"last_updated":"2026-08-26T18:00:03.000Z","as_of":"2026-08-26T18:00:05.000Z","mode":"simulated","pagination":{"page":1,"per_page":2,"total_signals":3,"total_pages":2,"has_next":true,"has_prev":false,"next_page_token":"eyJ2IjoxLCJzbmFwc2hvdF9pZCI6Im9wYXF1ZSIsIm5leHRfaW5kZXgiOjJ9"},
  "coverage":{"requested_symbols":["ADA-USD","BTC-USD","ETH-USD"],"requested_symbol_count":3,"covered_symbols":["ADA-USD","BTC-USD","ETH-USD"],"covered_symbol_count":3,"missing_symbols":[],"missing_symbol_count":0,"unavailable_symbols":[],"errored_symbols":[],"symbol_diagnostics":[{"symbol":"ADA-USD","status":"healthy","message":"Current order-book signal is available.","age_seconds":4,"lag_seconds":null,"retryable":false,"source":"backend"},{"symbol":"BTC-USD","status":"healthy","message":"Current order-book signal is available.","age_seconds":3,"lag_seconds":0.1,"retryable":false,"source":"backend"},{"symbol":"ETH-USD","status":"healthy","message":"Current order-book signal is available.","age_seconds":2,"lag_seconds":null,"retryable":false,"source":"backend"}],"row_count":3,"complete":true,"state":"complete"},
  "freshness":{"latest_signal_at":"2026-08-26T18:00:03.000Z","oldest_population_signal_at":"2026-08-26T18:00:01.000Z","max_age_seconds":4,"max_lag_seconds":0.1,"state":"healthy"},
  "diagnostics":{"status":"healthy","message":"All requested symbols are covered.","freshness_threshold_seconds":5,"delay_threshold_seconds":2,"failed_chunk_count":0,"failed_symbol_count":0,"failed_chunks":[],"failed_symbols":[],"source_error":null,"validation_error":null,"incomplete_source":false,"failure_origin":null}
}
```

The continuation response MUST contain only `ETH-USD`, `page=2`, `has_next=false`, `has_prev=true`, and `next_page_token=null`, with all population-wide fields unchanged.

### 9.4 Degraded partial-coverage response

```json
{
  "schema_version":"orderbook-coverage.v1","signals":[{"record_key":"missing:SOL-USD","signal_id":"missing:SOL-USD","session_id":null,"symbol":"SOL-USD","signal":"hold","signal_type":"hold","signal_generated":false,"signal_strength":0.0,"price":null,"timestamp":null,"data_status":"missing","signal_reason":"No latest signal is available for this symbol.","response_only":true,"order_book":null,"execution_analysis":{"executable_intent":false,"blocked":true,"intended_action":null}},{"record_key":"00000000-0000-0000-0000-000000000011","signal_id":"sig-xrp","session_id":null,"symbol":"XRP-USD","signal":"hold","signal_type":"hold","signal_generated":false,"signal_strength":0.0,"price":0.52,"timestamp":"2026-08-26T18:00:04.000Z","data_status":"insufficient","signal_reason":"Book is empty.","response_only":false,"order_book":{"instrument":"XRP-USD","source":"simulated_live_parity","bids":[],"asks":[],"depth":0,"best_bid":null,"best_ask":null,"mid_price":null,"spread":null,"spread_bps":null,"bid_quantity":0,"ask_quantity":0,"imbalance":null,"sequence":"77","snapshot_id":"parity-xrp-77","exchange_at":null,"ingested_at":"2026-08-26T18:00:04.000Z","observed_at":"2026-08-26T18:00:04.000Z","lag_ms":null,"freshness_threshold_ms":5000,"freshness_state":"fresh"},"execution_analysis":{"executable_intent":false,"blocked":true,"intended_action":null}}],
  "total_analyzed":2,"active_signals":0,"average_strength":0.0,"last_updated":"2026-08-26T18:00:04.000Z","as_of":"2026-08-26T18:00:05.000Z","mode":"simulated","pagination":{"page":1,"per_page":10,"total_signals":2,"total_pages":1,"has_next":false,"has_prev":false,"next_page_token":null},
  "coverage":{"requested_symbols":["SOL-USD","XRP-USD"],"requested_symbol_count":2,"covered_symbols":["XRP-USD"],"covered_symbol_count":1,"missing_symbols":["SOL-USD"],"missing_symbol_count":1,"unavailable_symbols":["SOL-USD"],"errored_symbols":[],"symbol_diagnostics":[{"symbol":"SOL-USD","status":"unavailable","message":"Source returned no usable row.","age_seconds":null,"lag_seconds":null,"retryable":true,"source":"backend"},{"symbol":"XRP-USD","status":"healthy","message":"Book is available but empty.","age_seconds":1,"lag_seconds":null,"retryable":false,"source":"backend"}],"row_count":2,"complete":false,"state":"degraded"},
  "freshness":{"latest_signal_at":"2026-08-26T18:00:04.000Z","oldest_population_signal_at":"2026-08-26T18:00:04.000Z","max_age_seconds":1,"max_lag_seconds":null,"state":"healthy"},
  "diagnostics":{"status":"degraded","message":"One source chunk reported incomplete coverage.","freshness_threshold_seconds":5,"delay_threshold_seconds":2,"failed_chunk_count":1,"failed_symbol_count":1,"failed_chunks":[{"chunk_id":"chunk-02","requested_symbols":["SOL-USD"],"failure_class":"retryable","retryable":true,"message":"Upstream data was incomplete."}],"failed_symbols":["SOL-USD"],"source_error":null,"validation_error":null,"incomplete_source":true,"failure_origin":"backend"}
}
```

## 10. Conformance checklists

### 10.1 Backend

- [ ] Both live and simulated routes emit the same v1 envelope, fields, units, nullability, and status vocabulary; only mode/source provenance differs.
- [ ] Omitted symbols, explicit empty selection, whitespace/case normalization, duplicate symbols, malformed symbols, and unsupported symbols follow section 2.
- [ ] Missing, signed, fractional, exponent, leading-zero, overflowing, zero, and out-of-range `page`/`per_page` values return HTTP 400 without coercion.
- [ ] Empty universe returns HTTP 200, `coverage.state=empty`, `complete=false`, empty signals, zero pages, and no token.
- [ ] Valid non-empty complete, empty-book, stale, delayed, partial, degraded, and page-beyond-range cases preserve HTTP 200 semantics.
- [ ] Every real row has finite levels, valid ordering, consistent derived prices, RFC 3339 UTC timestamps, and explicit units; malformed rows are rejected fail-closed.
- [ ] Placeholder rows are deterministic, non-executable, included in population totals/order/pages, and excluded from covered/active/strength/freshness metrics.
- [ ] Latest selection uses event timestamp, numeric sequence/version, and record_key exactly; duplicates, conflicting duplicates, and out-of-order arrivals are deterministic.
- [ ] Population is frozen before pagination; page totals, coverage, timestamps, and diagnostics remain identical across continuation pages.
- [ ] Continuation tokens are opaque, authenticated, request/mode/page-size bound, five-minute expiring, and reject tamper/mismatch/expiry with 400.
- [ ] Source chunk failure, malformed upstream payload, timeout, database failure, and all-chunks-failed cases return the specified error class; no synthetic success is emitted.
- [ ] Error bodies are schema-versioned and operator-safe; no credentials, SQL, stack traces, or sensitive provider details leak.
- [ ] Contract fixtures exercise positive, empty, stale, partial, malformed, pagination, duplicate, out-of-order, and failure cases for both modes.

### 10.2 Frontend

- [ ] Accepts both routes and consumes canonical v1 fields without requiring legacy aliases; unknown additive fields are ignored.
- [ ] Rejects/visibly reports unsupported major schema versions and preserves HTTP error versus valid degraded/empty 200 distinctions.
- [ ] Treats null as unknown/not applicable, never as zero; does not infer freshness, lag, coverage, or health from the browser clock or HTTP 200 alone.
- [ ] Displays coverage state and per-symbol diagnostics, including unavailable/error placeholders; never creates execution intents from placeholders, stale/unknown books, or malformed data.
- [ ] Preserves backend population totals, active counts, averages, freshness, and diagnostics across pages; does not recompute them from the visible page.
- [ ] Treats page tokens as opaque, sends no page/token combination, discards invalid/expired tokens, and does not silently restart pagination.
- [ ] Merges concurrent pages/chunks by canonical symbol and the exact backend winner tuple, never by arrival order; deduplicates exact and conflicting duplicates deterministically.
- [ ] Preserves canonical UTF-8 symbol ordering and does not resort by signal strength, timestamp, or response arrival.
- [ ] Handles first-page empty, beyond-range empty, single-page, multi-page, stale/delayed, partial/degraded, malformed, duplicate, out-of-order, timeout, 4xx, 5xx, and network-failure states.
- [ ] Keeps live and simulated rendering interchangeable except for explicitly displayed mode/source provenance.
- [ ] Maintains legacy-field compatibility only as a migration fallback; canonical `order_book`, coverage, freshness, diagnostics, and schema version remain authoritative.

## 11. Rejected alternatives

- Arrival-order or database-insertion latest selection: divergent under out-of-order exchange events and simulated scheduling.
- Page-by-page re-querying: permits duplicates, omissions, and changing totals between pages.
- Client-decoded or offset-only tokens: permits request substitution and cannot guarantee snapshot consistency.
- Clamping malformed pagination: hides client defects and may return an unintended dataset.
- Treating stale, delayed, partial, or empty valid reads as transport errors: loses actionable diagnostics and makes safe UI behavior impossible.
- Fabricating timestamps, zero prices, or synthetic HOLD market rows for missing data: confuses unknown with valid market state and risks execution.
