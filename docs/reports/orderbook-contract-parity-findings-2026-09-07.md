# Order-book contract parity findings

Date: 2026-09-07
Status: implementation-ready findings; no code changes proposed in this task
Scope: reconcile the simulated audit, live audit, matched-universe baseline, and divergence classification into one contract and acceptance document.

## Executive summary

The repository has three materially different order-book surfaces:

1. The live backend consumes Coinbase public order-book data, refreshes an authenticated account snapshot, evaluates the selected universe, and may dispatch exchange orders.
2. The simulated backend evaluates synthetic state on a deterministic worker cadence. Its `live_parity` mode uses public Coinbase quotes but retains synthetic session capital, positions, and execution authority.
3. The frontend local fallback synthesizes browser-local signals and portfolio state. It is not a backend simulation and must not be presented as live/simulated parity evidence.

Live and simulated backend signal rows are structurally close: both expose strength, price, order-book fields, `criteria_analysis`, ML analysis, profitability, and execution analysis. That shape similarity does not establish semantic parity. Source data, account authority, quote availability, retention, persistence fallback, diagnostics, frontend aggregation, and execution outcomes differ.

The strongest accidental drifts are: missing live symbols versus synthetic coverage; page-dependent `active_signals` and related aggregates in persisted fallbacks; ambiguous `total_signals`; retention that can under-represent a large selected universe; frontend chunk merge arithmetic; and undocumented units/provenance for criteria and thresholds. The strongest intentional safety differences are account snapshots, exchange order authority, provider failures/rate limits, Stop Trading settlement, and synthetic balances. These boundaries must remain fail-closed and observable rather than being forced into numeric parity.

The matched-universe baseline is not a successful parity measurement. It used the source fallback fixture `BTC-USD, ETH-USD, SOL-USD`; the runtime was stopped, signal/status reads timed out after ten seconds, and no live or simulated order was submitted. Runtime latency, freshness, queue depth, rate-limit, account coupling, and execution measurements remain unavailable. No value marked unavailable or unobserved below may be treated as zero.

### Decisions required before implementation

- Define one canonical latest-by-symbol response population and count scope, independent of page slicing.
- Define selected-universe accounting (`selected`, `attempted`, `succeeded`, `missing`, `generated`) without silently shrinking the user-selected universe.
- Decide whether persisted reads are session-scoped and whether persistence is a restart cache or durable analytics history.
- Define provider budget/backpressure policy before adding concurrency, caps, rotation, or retries.
- Define the `live_parity` name/payload boundary and explicitly state that it has synthetic account state and no exchange execution authority.
- Define retention and stale-data semantics for a selected universe larger than the live recent-record capacity.
- Decide whether the frontend local fallback remains an approved operator mode; if so, label it as a separate simulator contract.

## Evidence basis and evidence labels

Evidence was reconciled from these artifacts and exact source references:

- Live audit: `docs/reports/live-orderbook-signal-contract-audit-2026-08-22.md`, verified at source commit `7760cde70142883df6ff9b5fb42d9615ee2fa840`.
- Simulated/live contract audit: `docs/reports/live-simulated-orderbook-contract-audit-2026-08-22.md`, source-backed audit commit `5f47e62f609fea372d2c13230119d432cb0f3168`.
- Matched-universe baseline: `docs/reports/matched-universe-signal-baseline-2026-08-23.md`, verified report commit `35364576d68d7b3f317ce4dfba2a05e2d49f7bbe`.
- Divergence classification: `docs/reports/live-vs-simulated-orderbook-divergence-classification-2026-09-07.md`.
- Current implementation references below use the paths/line ranges recorded by those audits; line numbers must be revalidated against the implementation SHA before coding.

Labels used throughout:

- **Observed fact**: directly present in checked-in source or captured read-only runtime evidence.
- **Hypothesis/risk**: a consequence that requires runtime measurement or an explicit product decision.
- **Proposed change/target**: implementation or contract work proposed for parity; not an assertion about current behavior.
- **Unavailable**: requested runtime evidence was not captured; never interpret as zero.

## Separately documented contracts

### Live backend contract

Observed source contract:

- `startSession` accepts the selected symbol list without an imposed backend cap or deduplication (`src/trading/LiveTradingService.cpp:2810-2821`). Quote selection copies the selected list (`:1244-1263`). Account-exit management may expand the working symbols with held assets (`:1317-1325`); this expansion must be visible in diagnostics.
- Each worker iteration fetches the selected quote universe sequentially, refreshes account state, generates a tick, evaluates execution, dispatches eligible orders, and flushes persistence (`src/trading/LiveTradingService.cpp:2309-2409`). The audited path has no normal post-tick sleep, cursor, rotation, or hard quote cap; the threshold warning is logging-only (`:41-53,2352-2377`).
- A failed live quote is skipped rather than replaced with fabricated market data (`:1208-1241`). The API can add response-only missing/HOLD placeholders when request symbols are supplied (`:3280-3307`).
- Live data comes from Coinbase level-2 aggregation (`src/trading/CoinbaseAdvancedClient.cpp:514-560`). The service refreshes authenticated accounts and requires credentials, a loaded account, a healthy snapshot, and explicit live execution before trading (`LiveTradingService.cpp:2658-2764`).
- Live signal serialization includes signal, price, timestamp, spread, volume, imbalance, criteria, ML, strength, and execution fields (`LiveTradingService.cpp:517-542`). Profitability uses expected return, spread, fees, slippage, and minimum strength (`:1733-1769`); additional account, spot-side, cash, minimum-notional, pending-order, and live-execution gates may block an intent (`:1835-1931`).
- In-memory reads deduplicate latest timestamps per symbol, add missing placeholders, sort, and paginate (`:3242-3363`). Full filtered latest-set counts are available in this path. Persisted fallback uses `COUNT(DISTINCT symbol)`/`DISTINCT ON` but audits found page-row-dependent active counting (`:3366-3461`).
- Recent trades are capped at 100 and recent signals at `max(250, symbols_.size())` (`:1934-1942`). A durable retention/delete policy was not found.
- Stop Trading sets inactive, clears undispatched intents/reserves, and reports `settling` while accepted Coinbase orders remain pending (`:2930-2954`). It prevents new dispatch; it does not prove accepted-order cancellation or zero eventual fills.

Safety meaning: live may produce a signal row that is not an executable intent. Provider, account, stale-data, rate-limit, and order-settlement failures must remain explicit blockers and must fail closed.

### Simulated backend contract

Observed source contract:

- `startSession` copies the selected symbols and defaults to `BTC-USD, ETH-USD, SOL-USD` (`src/trading/SimulatedTradingService.cpp:2189-2200`). Ordinary synthetic generation iterates each selected symbol (`:1732-1757`). `live_parity` uses public quotes but retains session-local synthetic capital/cash/positions (`:2177-2187,2241-2251`).
- The worker performs a generation pass and sleeps one second (`SimulatedTradingService.cpp:1832-1908`). It does not dispatch exchange orders. Paper fills and state are session-local.
- Synthetic prices, depth, and volume are generated from deterministic state (`:1082-1106,1138-1149`). Signal strength uses the same audited formula and initial threshold as live (`:1114-1117`).
- Signal rows carry the shared top-level and nested fields (`:489-515`), and the strategy applies ML/fallback and profitability gates (`:1201-1354,1390-1420`). Execution analysis represents simulated constraints, not exchange acceptance or fill certainty.
- In-memory latest-by-symbol reads are backed by a map and count the full filtered latest set (`:2375-2458`). Persisted fallback uses latest-by-symbol selection but audits found page-row-dependent active counting (`:2500-2577`).
- Simulated status exposes selected/current/recent latest counts, cumulative evaluated/generated counters, executable intents, transformer counters, blocker counts, market-data status/failures, and coverage (`:2012-2064`).
- Stop marks the worker inactive and drains pending simulated work; it has no external exchange settlement obligation (`:2220-2305`).

Safety meaning: simulated results can exercise local portfolio mechanics, but equal signal counts or equal payload shape do not imply equal live opportunities, balances, order acceptance, fills, or realized edge.

### Frontend local fallback contract

Observed source contract:

- `frontend/lib/api.ts:432-548` generates a separate local signal stream using browser-local formulas, every selected symbol, local pagination, and local portfolio state.
- Backend endpoint selection and local short-circuit are in `frontend/lib/api.ts:1011-1071`. The fallback does not expose the backend diagnostics, persistence, account snapshot, or exchange blocker contract.
- The widget consumes `pagination.total_signals`/`total` and diagnostics (`frontend/components/dashboard/OrderBookSignalsTable.tsx:51-54,355-430`). Normal polling and chunk merge behavior is in `frontend/hooks/useTrading.ts:257-269,280-445`; it polls every three seconds and chunks universes over 50 symbols.
- Stop UI can immediately clear local state; live generic stop does not currently expose accepted-order settlement as a dedicated UI state (`frontend/hooks/useTrading.ts:187-210`, `frontend/lib/api.ts:882-913`).

Proposed contract boundary: local fallback is either visibly labeled as a distinct development simulator with its own schema, or removed/disabled through a separately approved task. It must not be used as parity evidence.

## Side-by-side contract table

| Area | Live backend | Simulated backend | Classification | Parity target |
| --- | --- | --- | --- | --- |
| Selected symbols | Selected list; account holdings may expand working symbols | Selected list; synthetic fallback is BTC/ETH/SOL | Intentional account boundary plus drift risk | Preserve requested universe; report requested/working/expanded sets explicitly |
| Successful coverage | Failed quotes skipped; placeholders may be returned | Synthetic mode can generate every selected symbol | Safety boundary with accidental observable drift | Equal accounting and fail-closed missing-data semantics, not equal successful-row counts |
| Quote source | Coinbase public L2 | Synthetic; `live_parity` public quotes | Intentionally different | Include `market_data_source` and provenance |
| Cadence | Full sequential fan-out per worker iteration; no normal sleep/cap in audited path | One-second worker sleep | Undocumented intentional difference | Exact cadence need not match; expose tick/sweep timing and policy |
| Batching/rotation | No cursor/rotation; current batch is full selected set | No quote queue/rotation | Policy risk | Any future bound requires approved budget, backpressure, lag, and coverage fields |
| Signal math | Strength, criteria, ML, profitability, and execution analysis | Near-equivalent audited logic | Parity-required semantics | Shared definitions, units, and regression fixtures |
| `criteria_analysis` | Provider-derived features | Synthetic-derived features | Source difference, schema drift risk | Shared names/units plus provenance; preserve optional criteria safely |
| ML gate | ONNX/heuristic fallback; live model/account availability may block | Corresponding model/heuristic path | Intentional data/authority difference | Same gate meaning; report availability/fallback rather than collapsing to HOLD |
| Profitability gate | Expected return less fees/slippage/spread/minimum strength | Same formula against synthetic inputs | Mostly parity-required | Same formula/units; separate expected from realized edge |
| Account snapshot | Authenticated and refreshed; execution authority | Session-local synthetic account | Safety-required difference | Explicit account source, age, health, and execution authority |
| Latest-by-symbol | In-memory latest set; persisted fallback | In-memory map; persisted fallback | Accidental fallback drift | Compute counts before page slicing, same population definition |
| Pagination `total_signals` | Latest selected-symbol population, not generated history | Same intended meaning | Ambiguous naming | Canonical `latest_by_symbol_selected_universe` scope; never cumulative rows |
| Per-row `total_signals` | Cumulative-looking generation ordinal | Same pattern | Naming drift | Rename/alias to `generation_sequence`; deprecate ambiguity |
| Retention | Recent signals capped at `max(250, symbols_.size())`; trades 100 | Latest map; trades 100 | Undocumented lifecycle | Define session scope, retention, oldest age, and large-universe behavior |
| Diagnostics | Quote, latest, retained, executable, blocker, strength/edge buckets, coverage | Evaluation/generated/warming/rejected, market-data status, blockers, coverage | Different useful dimensions | Shared canonical envelope plus mode-specific extensions |
| Queue/rate limits | Network/account/order paths; no structured queue/rate metrics found | No exchange queue; local pending work | Safety/observability gap | Expose bounded queue depth, request/error/429 counts, and ages |
| Stop Trading | Stops new intents; accepted orders may settle; response can be `settling` | Stops worker and drains local work | Safety-required difference | Explicit state machine; never claim cancellation from stop acknowledgement |
| Execution outcomes | Exchange accepted/rejected/fill/pending outcomes | Paper fills/local outcomes | Safety-required difference | Separate intent, acceptance, fill, settlement, and realized edge |
| Frontend rendering | Poll/chunk/merge of backend responses | Same widget or local fallback | Frontend artifact | Render canonical totals; label local simulator and preserve settling |

## Exact file and symbol reference map

| Concern | Live references | Simulated/frontend references |
| --- | --- | --- |
| Routes and pagination defaults | `include/api/PredictController.hpp:32-33`; `src/api/PredictController.cpp:1230-1266` | Same route handler selects simulated endpoint |
| Worker lifecycle | `src/trading/LiveTradingService.cpp:2309-2409` | `src/trading/SimulatedTradingService.cpp:1832-1935` |
| Quote selection/fan-out | `LiveTradingService.cpp:1208-1263,2309-2377` | `SimulatedTradingService.cpp:879-937,1732-1757` |
| Account coupling | `LiveTradingService.cpp:2353-2395,2658-2764` | Synthetic state `SimulatedTradingService.cpp:2142-2268` |
| Shared payload | `LiveTradingService.cpp:517-542` | `SimulatedTradingService.cpp:489-515` |
| Signal math/gates | `LiveTradingService.cpp:1516-1931` | `SimulatedTradingService.cpp:1082-1420` |
| Latest/pagination/total | `LiveTradingService.cpp:3242-3467` | `SimulatedTradingService.cpp:2375-2577` |
| Diagnostics | `LiveTradingService.cpp:2526-2582` | `SimulatedTradingService.cpp:2006-2064` |
| Retention/persistence | `LiveTradingService.cpp:332-353,1409-1513,1934-1942` | `SimulatedTradingService.cpp:314-369,940-1042,1423-1428` |
| Stop behavior | `LiveTradingService.cpp:2930-2954,2383-2398` | `SimulatedTradingService.cpp:1884-1896,2220-2305` |
| Frontend client/fallback | `frontend/lib/api.ts:432-548,882-913,1011-1071` | Same local/backend selection paths |
| Frontend polling/merge/widget | `frontend/hooks/useTrading.ts:187-210,257-445` | `frontend/components/dashboard/OrderBookSignalsTable.tsx:51-54,355-430`; `frontend/types/trading.ts:45-170` |

## Matched-universe baseline methodology and reproducibility

### What was intended

Compare live and backend simulated order-book contracts using one ordered fixture universe (`BTC-USD, ETH-USD, SOL-USD`), the `ml_enhanced_orderbook` strategy, identical explicitly recorded parameters, read-only GET requests, and no live or simulated order submission. Compare warm/in-memory and cold/persisted reads, page sizes, diagnostics, freshness, gates, and stop state separately.

### What actually occurred

The 2026-08-23 baseline queried a rootless Podman Compose stack read-only. Health returned 200; live status returned stopped with `symbols=[]`, no session, zero activity, and `coverage_complete=false`. The live signal endpoint, simulated signal endpoint, and simulated status endpoint each timed out after approximately ten seconds with no payload. No live session was started, no session was restarted, no credentials were recorded, and no order was submitted.

The fallback fixture was source-derived, not observed as a selected live universe. Source-only defaults recorded were: round-trip fee 1.5%, slippage buffer 0.2%, minimum order-book strength 0.22, and expected-return scale default 2.4% clamped to 0–5%. Runtime model assets were unavailable and built-in/neutral fallbacks were logged. These facts limit any inference about ML gate outcomes.

### Reproduction instructions

1. Use the repository's approved guarded runtime procedure; the prior baseline recorded `TAG=dev podman-compose up --no-build`. Do not start live execution or mutate account state.
2. Confirm `GET /health` and `GET /api/trading/live/status` before signal reads.
3. Use the exact ordered universe `BTC-USD,ETH-USD,SOL-USD` for both modes and record repository SHA, mode, session IDs, parameter JSON excluding secrets, start/stop timestamps, and image revisions.
4. Sample page 1 with `per_page=3`, then page 2 and a smaller page size. Preserve raw JSON and request timestamps. Repeat for warm and cold/persisted paths only through an approved read-only procedure.
5. Capture at least 20 complete ticks per mode for p50/p95 timing; capture per-symbol quote outcomes and logs for the same interval. If an endpoint times out, record timeout class/duration and stop the comparison rather than substituting source values.
6. For stop behavior, use paper/sandbox or a separately approved read-only lifecycle probe. Never submit live orders to benchmark parity. If accepted orders exist, record settlement until terminal; a stop acknowledgement is insufficient.
7. Join signal rows, diagnostics, persistence records, and execution outcomes by session and generation identity. Redact secrets and account identifiers.

### Measurement rules

- `unavailable`, `unobserved`, and `timed out` are distinct from numeric zero.
- Percentiles require raw timestamp samples and a declared sample count.
- Compare the same ordered symbols, strategy parameters, page size, source SHA, and mode; otherwise classify the run as non-comparable.
- Measure expected edge, realized net edge after authoritative fees, blocked intents, accepted orders, fills, rejects, pending settlement, and account snapshot age separately.
- Do not infer rate limits from lack of errors, freshness from a row timestamp alone, or execution success from `signal_generated=true`.

## Recorded measurements and limitations

| Measurement | Recorded baseline | Status/limitation |
| --- | --- | --- |
| Fixture symbols | `BTC-USD, ETH-USD, SOL-USD` | Source fallback only; no active live selection observed |
| Live status | stopped; empty symbols/session; zero activity | Read-only response; not a signal parity result |
| Health | HTTP 200 | Service health only |
| Live signal read | timeout at ~10s, HTTP 000 | No payload; read-path blocker |
| Simulated signal read | timeout at ~10s, HTTP 000 | No payload; read-path blocker |
| Simulated status read | timeout at ~10s, HTTP 000 | No payload; read-path blocker |
| Quote attempts/successes | 0 in stopped live status | No worker tick; not a throughput measurement |
| Generated/latest/active signals | 0 in stopped live status; simulated unavailable | Not evidence of strategy output |
| Sweep/tick duration | unavailable | No active worker sample |
| Freshness/stale age | unavailable | No signal timestamps |
| Queue depth | live pending orders 0; simulated unavailable | No active session; not a queue-capacity result |
| Rate-limit/error counts | no rate-limit response observed | No signal requests completed |
| Blocked intents | live 0 in stopped status; simulated unavailable | No active signals |
| Account snapshot | no active live session | No account mutation or credential read |
| Execution outcomes | live trades/pending 0 in stopped status; simulated unavailable | No orders submitted |
| CI/build/test | no local build/test run for source audits/baseline | Documentation/runtime evidence only |

Limitations: runtime/provider latency, rate limits, stale age, queue depth, account snapshot coupling, and Stop Trading settlement duration remain unverified. The audit evidence is source-grounded and read-only; it does not authorize implementation choices that affect live throughput, execution, retention deletion, or selected universes.

## Divergence register and required disposition

| ID | Divergence | Classification | Observed impact | Required disposition |
| --- | --- | --- | --- | --- |
| D1 | Live failed quotes can omit symbols; ordinary simulation fabricates a row for every selected symbol | Safety boundary plus accidental observable drift | Same requested universe yields different row/coverage counts | Preserve universe; expose selected/attempted/succeeded/missing/generated and `coverage_complete`; never fabricate live data |
| D2 | Live full-universe sequential fan-out/no normal sleep versus simulated one-second loop | Intentionally different but undocumented; provider risk | Freshness and provider load vary by mode | Document throughput policy; measure sweep duration/request rate; do not silently cap or rotate |
| D3 | Live account snapshot and exchange authority versus synthetic account state | Safety-required intentional difference | Same signal does not imply same buying power or executable intent | Add account source/age/health and `execution_authority`; fail closed on live snapshot failure |
| D4 | `threshold_spread` name is used for an imbalance criterion/threshold | Accidental schema drift | Consumers may compare wrong units | Add explicit units/field semantics and compatibility migration; preserve thresholds until approved |
| D5 | ML/model availability and fallback inputs differ | Intentionally different data boundary | Equal signal counts do not imply equal model confidence | Expose model status, fallback reason, and gate result separately |
| D6 | Persisted fallback counts active/strength over page rows rather than full latest population | Accidental drift | Page size, restart, and warm/cold state change summary values | Count before pagination; test page 1/page 2 and warm/cold equivalence |
| D7 | Per-row `total_signals` is generation ordinal while pagination `total_signals` is latest-symbol coverage | Undocumented semantic collision | Consumers may confuse row sequence with result-set size | Canonical pagination scope; alias/deprecate row field as `generation_sequence` |
| D8 | Retention differs and durable lifecycle is undefined | Accidental/undocumented drift | Large universes can lose latest coverage; storage policy unclear | Decide cache versus history, session scope, capacity, oldest age, and deletion ownership |
| D9 | Diagnostic names mix latest, retained, generated, non-HOLD, and executable populations | Naming ambiguity plus accidental drift | Operators may treat visible signals as executable | Define canonical count fields with population and scope |
| D10 | Frontend polls/chunks/merges and local fallback changes semantics | Frontend artifact | Display totals can differ from direct API; local rows look live | Render canonical backend totals; label/disable local fallback; do not sum page-dependent totals |
| D11 | Live Stop Trading can settle accepted orders; simulated stop has no exchange settlement | Safety-required difference | UI may disappear before external orders settle | Explicit `running/stopping/settling/stopped` state and terminal settlement evidence |
| D12 | Runtime signal/status endpoints timed out in baseline | Runtime blocker, not parity result | No measurements can be claimed | Reproduce with guarded read-only observation before acceptance |

## Unresolved questions

1. Is full-universe live fan-out an approved operating policy for every selected universe, or is bounded rotation acceptable only after an explicit provider budget decision?
2. Does account-holding expansion belong in the selected universe, a separate working universe, or an execution-only set?
3. Should missing live quotes produce visible HOLD/missing rows for every consumer, or may a consumer omit them while exposing `coverage_complete=false`?
4. Should `live_parity` be renamed, or must every payload state `account_source=synthetic_session` and `execution_authority=none`?
5. Is `threshold_spread` externally consumed and therefore a compatibility alias, or can a versioned explicit imbalance threshold replace it?
6. Must persisted rows be scoped to the current session by default? Is history intended for analytics or only restart recovery?
7. Is `active_signals` intended to mean latest non-HOLD rows, retained non-HOLD rows, or executable intents? These must not share one name.
8. Is `coverage_complete=false` a display diagnostic only or an execution gate? No change should be inferred from this audit.
9. Is `NEXT_PUBLIC_FORCE_LOCAL_SIM_TRADING` approved for operations? If yes, what separate contract and visible mode label are required?
10. What is the authoritative definition of realized edge, including fees, slippage, partial fills, rejected orders, and settlement timing?
11. What account snapshot age is safe for signal display, intent generation, and live dispatch separately?
12. Which provider errors count as rate limits, transient retries, permanent symbol failures, or a hard fail-closed stop?

## Safety and shutdown implications

- Preserve the user-selected universe. Never silently shrink it to fit a hard quote cap, frontend chunk, retention capacity, or provider response.
- Do not turn a live quote failure into synthetic data. Report the missing symbol and keep execution fail-closed.
- Keep account authority separate from signal generation. A non-HOLD row is not permission to trade; account snapshot health, credentials, spot restrictions, cash, notional, pending orders, and explicit execution mode remain independent gates.
- Keep expected edge, realized edge, signal generation, executable intent, order acceptance, fill, and settlement as separate states.
- Stop Trading must prevent new intents after the stop boundary, clear only undispatched reservations, and continue reconciliation for already accepted external orders. `settling` is not `stopped`, and a successful stop response is not cancellation evidence.
- Queue depth, provider rate limits, stale age, and sweep duration are safety inputs for any future throughput change. Do not add adaptive concurrency or retries without bounded budgets, cancellation semantics, duplicate-order protection, and operator-visible diagnostics.
- Persisted reads must not resurrect stale signals as current without an explicit session/freshness contract. Deletion or retention changes require separate approval because durable rows are audit evidence.
- Frontend local simulation must never be used to make live readiness, account health, or execution claims.

## Implementation-ready acceptance targets

These are testable targets for a future parity implementation. They are not claims that current code satisfies them.

### A. Universe and quote coverage

- Given an ordered selected universe of N symbols, both backend modes report `selected_symbol_count=N` and preserve the requested symbols exactly, except for an explicitly reported account-holding expansion field.
- Every symbol has a per-sweep outcome: attempted, succeeded, skipped/error, missing/stale, or not scheduled with a documented reason. No symbol disappears without diagnostics.
- Live quote failure never produces fabricated price/depth/volume. The API exposes `missing_latest_symbols` and `coverage_complete=false` when any required symbol lacks acceptable data.
- Tests cover empty, one-symbol, three-symbol, 50-symbol, and greater-than-retention-cap universes.

### B. Cadence, batching, rotation, and provider budget

- A 20-tick paper/read-only observation records per-tick `tick_duration_ms`, `sweep_duration_ms`, request count, and per-symbol outcome; the report includes sample count and p50/p95.
- Any batching or rotation policy declares batch size, cursor/order, maximum lag, queue/backpressure behavior, and expected coverage; no frontend page size is treated as a provider batch limit.
- The implementation enforces or explicitly documents a provider request budget and records rate-limit, timeout, retry, and cancellation counts. A rate-limit response cannot silently increase fan-out.
- A stop during an in-flight quote fetch prevents generation and dispatch for that completed fetch, and no post-stop intent is emitted.

### C. Latest-by-symbol and pagination semantics

- For a fixed filtered selected universe, `pagination.total_signals` means exactly the count of latest rows per symbol, not cumulative generated rows, and includes an explicit scope such as `latest_by_symbol_selected_universe`.
- `active_signals`, average strength, coverage counts, and all summary aggregates are computed over the complete latest population before page slicing. Page 1/page 2 and page sizes 1/3/50 return identical population totals.
- Warm/in-memory and cold/persisted reads return equivalent latest-by-symbol totals and aggregate semantics for the same session and source data.
- Per-row generation sequence is not named `total_signals`; if backward compatibility requires the old field, an explicit `generation_sequence` alias and deprecation note are present.

### D. Payload and `criteria_analysis`

- Live and backend simulated rows preserve the common fields: signal/session identity, symbol, signal type, generated flag, strength, price, timestamp, reason, data status, spread, volume, buy/sell volume, imbalance, prediction, `criteria_analysis`, ML analysis, strength composition, and execution analysis.
- Every numeric criterion declares units and semantic meaning. The imbalance criterion is not serialized under an unexplained spread threshold name; compatibility aliases are versioned.
- `data_status=sufficient` means inputs were usable even when the strategy chooses HOLD; missing/warming data is not conflated with a profitability rejection.
- Payloads expose `market_data_source`, account source, execution authority, model status/fallback, and schema version sufficiently to distinguish live, backend synthetic, and `live_parity` rows.

### E. ML and profitability gates

- Tests cover model ready, model unavailable, heuristic fallback, transformer warming/rejected, insufficient data, expected-return unavailable, below-strength, fee/slippage-negative, and profitable-but-account-blocked cases.
- Both backend modes use the same documented expected-return, spread, fee, slippage, minimum-strength, and minimum-net-PnL units and formulas where the inputs exist.
- `signal_generated`, `profitability_gate`, `executable_intent`, and blocker categories are independently reported; no gate failure is hidden by changing the row into an indistinguishable no-data state.
- Live account/exchange blockers and simulated local blockers are distinguishable, and simulated results never claim live acceptance/fill authority.

### F. Active signals, retention, and persistence

- The contract separately reports `latest_signal_count`, `latest_non_hold_count`, `retained_non_hold_count`, `executable_intent_count`, and `selected_symbol_count`.
- Retention capacity, oldest retained timestamp/age, session scope, and durable deletion policy are documented. A selected universe larger than capacity yields an explicit incomplete-retention diagnostic rather than silent parity.
- A cold-start/persisted read cannot include prior sessions unless session scope is explicitly requested and reported.
- Persistence failures, retries, queue depth, and dropped/requeued writes are observable and do not change count semantics silently.

### G. Diagnostics and freshness/staleness

- Diagnostics include selected, attempted, successful, missing, generated, latest, retained, non-HOLD, executable, blocker buckets, model/fallback status, API errors, rate-limit errors, and coverage.
- Every latest row has a source timestamp and the response exposes oldest/latest age or a declared unavailable value. Freshness thresholds are explicit per display, signal evaluation, and execution authority.
- A stale row cannot be treated as a fresh quote. Tests cover stale data, clock skew/invalid timestamp, missing timestamp, and recovery to fresh data.
- Unavailable measurements remain null/unknown with reason; zero is reserved for an observed zero.

### H. Account snapshot coupling

- Live status exposes account snapshot loaded/healthy/error, source, age, and the timestamp used for gate evaluation without exposing credentials or sensitive balances.
- Snapshot failure, age over the execution threshold, missing credentials, and inconsistent account state fail closed for new live intents while preserving a distinct signal/data diagnostic.
- `live_parity` explicitly reports synthetic account source and no exchange execution authority.
- Tests prove that a non-HOLD signal with an unhealthy account cannot become an executable live intent.

### I. Stop Trading and shutdown

- Stop transitions are explicit: `running -> stopping -> settling` when accepted orders remain, otherwise `running -> stopping -> stopped`; terminal `stopped` is only reported after worker exit and required persistence/reconciliation.
- After the stop boundary, no new signal-generated execution intent or exchange dispatch occurs. In-flight accepted orders continue reconciliation.
- Undispatched reservations are released exactly once; accepted orders are not falsely marked canceled. Duplicate stop requests are idempotent.
- The API/UI preserves `settling` until external outcomes are terminal and displays accepted, filled, rejected, canceled, and unresolved counts separately.

### J. Queue depth and rate limits

- Quote, persistence, and execution queues expose bounded depth, oldest age, enqueue/dequeue/drop/retry counts, and cancellation state where applicable.
- Provider responses classify success, timeout, rate limit, transient, permanent symbol, and authentication failures. Rate-limit backoff is bounded and observable.
- Tests cover queue saturation, rate-limit storms, shutdown with queued work, retry exhaustion, and duplicate prevention. No unbounded queue or retry loop is accepted.

### K. Blocked intents and execution outcomes

- Every non-executable row has machine-readable blocker categories and a human-readable safe explanation; blockers are not collapsed into `active_signals`.
- Execution outcomes distinguish generated intent, risk/account approval, provider submission, exchange acceptance, rejection, partial fill, complete fill, cancellation, pending settlement, and reconciliation failure.
- Expected edge and realized net edge are separately calculated from authoritative fills/fees; no realized outcome is inferred from an expected-return prediction or paper fill.
- Simulated/paper outcomes are labeled `simulation` and cannot be joined as live execution evidence without an explicit mode/source key.

## Verification and closeout boundary

This document is documentation-only and does not implement code changes, change selected universes, start sessions, submit orders, alter account state, or modify frontend behavior. Local builds/tests were not run. Before implementation is accepted, the owning lanes must provide source-level tests, a read-only or paper matched-universe observation, exact-SHA remote CI evidence for the changed repository, and independent review of the final contract. Runtime evidence must remain separate from static source evidence, and any target above lacking a measured value must remain open rather than being inferred.
