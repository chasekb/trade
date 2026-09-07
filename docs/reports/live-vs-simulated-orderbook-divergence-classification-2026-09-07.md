# Live versus simulated order-book divergence classification

Date: 2026-09-07
Scope: Source-backed reconciliation of the completed live and simulated order-book contract audits. This report classifies behavior; it does not change runtime code, trading gates, selected universes, or frontend behavior.

## Evidence basis and terminology

The live evidence is the completed audit `docs/reports/live-orderbook-signal-contract-audit-2026-08-22.md`, verified at commit `7760cde70142883df6ff9b5fb42d9615ee2fa840` (source paths and line ranges below refer to that audit). The simulated evidence is the structured audit recorded on Kanban parent task `t_4562c42e`, comment 199, covering `src/trading/SimulatedTradingService.cpp`, `include/trading/SimulatedTradingService.hpp`, API handlers, and frontend consumers. The matched-universe baseline means the same selected symbols are supplied to both paths; it does not imply the same data source, account, or order authority.

Categories:

- Exchange/network/account safety: an intentional safety boundary caused by provider access, account authority, execution authority, or shutdown semantics. Parity is not required; the boundary must be explicit, fail-closed, and observable.
- Accidental drift: same contract should be equivalent, but implementation differs without a documented reason. Parity is required, or the contract must be deliberately split and documented.
- Frontend artifact: UI/local fallback/merge/type behavior that diverges from backend semantics. Backend parity is the source of truth; frontend behavior should either align or be explicitly labelled.
- Intentionally different but undocumented behavior: a legitimate simulation or paper-mode difference that is not currently stated in the contract. Parity is not required, but documentation and diagnostics are required.

## Executive classification

| Area | Classification | Parity required? | Impact |
| --- | --- | --- | --- |
| Selected universe and symbol coverage | Accidental drift / baseline contradiction | Yes for coverage; no silent shrinkage | Both paths intend every selected symbol, but live quote failure omits symbols while simulated synthetic mode produces them. The live diagnostics can therefore report incomplete coverage for the same universe. |
| Quote source and account authority | Intentionally different, with exchange/account safety boundary | No | Simulated and `live_parity` use synthetic session capital/cash; live uses Coinbase public books plus authenticated account snapshots. Treating parity as account parity would be unsafe. |
| Live quote fan-out, cadence, rotation | Exchange/network/account safety plus undocumented policy | No exact cadence parity; throughput contract required | Live requests the full selected universe sequentially each iteration with no enforced cap, cursor, or normal sleep. Simulated evaluates all selected symbols and sleeps one second. The difference changes freshness and provider load. |
| Signal math and gate structure | Mostly accidental drift risk; current C++ audits show near-equivalence | Yes for strategy semantics | Shared thresholds/fields appear similar, but implementation names and data availability differ. A future change must update both paths or document the split. |
| ML fallback and expected-return gates | Intentionally different but undocumented at the data-availability boundary | Gate safety parity required | Both expose heuristic fallback and profitability/ML gates, but simulated models may run without live model/account inputs. Never interpret equal signal counts as equal executable opportunities. |
| Latest-by-symbol aggregation and pagination | Accidental drift | Yes | In-memory paths count active signals over the full latest set; persisted fallback counts only returned page rows. This changes `active_signals` after restart or on small pages. |
| `total_signals` meanings | Intentionally different field meanings, undocumented | API semantics must be unified/documented | Per-row `total_signals` is a cumulative-looking generation ordinal; pagination `total_signals` is latest-symbol coverage. Consumers can confuse them. |
| Persistence/retention | Accidental drift plus undocumented lifecycle policy | Query semantics yes; retention policy must be decided | Both persist rows and read latest-by-symbol, but retention differs and neither has a clear durable retention contract. |
| Diagnostics/counts | Accidental drift and naming ambiguity | Yes for definitions, not necessarily values | `active_signals`, recent counts, executable intents, coverage, and failure counts are not interchangeable. |
| Frontend polling/chunking/local fallback | Frontend artifact | Backend response semantics yes | Three-second polling, 50-symbol chunks, merge arithmetic, and optional browser-local simulation can produce a different displayed contract. |
| Stop Trading | Exchange/network/account safety; frontend artifact for settling display | Safety semantics yes; UI shape no | Live must not submit new orders and may settle accepted orders. Simulated has no exchange orders. UI does not expose live settling as a dedicated state. |

## Detailed divergence register

### 1. Selected-universe coverage and missing symbols

Evidence:

- Live `startSession` accepts the selected `symbols` without a backend cap/dedupe (`src/trading/LiveTradingService.cpp:2810-2821`). `selectLiveQuoteBatchLocked` copies all symbols (`:1244-1263`), and a failed quote is skipped (`:1208-1241`). The live read path can add response-only missing HOLD placeholders (`:3280-3307`).
- Simulated `startSession` copies selected symbols and defaults to `BTC-USD, ETH-USD, SOL-USD` (`src/trading/SimulatedTradingService.cpp:2189-2200`). Synthetic `generateTickLocked` iterates each selected symbol (`:1732-1757`); `live_parity` skips a symbol when its public quote is absent (`:1748-1751`).

Classification: accidental drift for the matched-universe observable contract, with an exchange/network safety cause for missing live symbols. Ordinary simulated mode has a quote for every selected symbol by construction; live cannot safely fabricate one after a provider failure. `live_parity` intentionally follows live quote availability.

Impact: identical selected universes can have different row counts, coverage, freshness, and active counts. A missing live symbol must remain fail-closed, not be replaced by synthetic data. The API should make attempted, successful, skipped, and placeholder counts explicit.

Parity decision: require parity of universe accounting and fail-closed semantics, not parity of successful row counts. Proposed owner: live service/API diagnostics. Follow-up: document `selected`, `attempted`, `succeeded`, `missing`, and `generated` definitions and preserve the user-selected universe.

Question: Is a missing live quote supposed to produce a visible HOLD/missing row in every consumer, or may frontend chunk merging omit it while `coverage_complete=false`?

### 2. Cadence, batching, rotation, and request rate

Evidence:

- Live worker calls `fetchLiveQuotes` once per iteration (`src/trading/LiveTradingService.cpp:2309-2375`), sequentially requests every symbol (`:1208-1241`), has no cursor/rotation/cap, and has no normal post-tick sleep. The warning threshold is logging-only (`:41-53,2368-2372`).
- Simulated worker performs one generation pass and sleeps one second (`src/trading/SimulatedTradingService.cpp:1832-1908`). Ordinary synthetic generation covers all selected symbols per pass (`:1732-1757`); `live_parity` fetches selected symbols sequentially (`:879-937`).

Classification: exchange/network/account safety plus intentionally different but undocumented behavior. The live full-universe fan-out is a provider-load and freshness concern; simulated one-second cadence is a deterministic paper-mode scheduler. Exact cadence parity is not required, but both modes need an explicit throughput contract.

Impact: live sweep duration can exceed the nominal worker iteration, provider rate limits can reduce coverage, and live data age differs by symbol within a sweep. Simulated rows look regular even where live would be unavailable.

Parity decision: do not add a hard quote cap, silently rotate, or substitute symbols. Require per-symbol attempt/result and sweep-duration diagnostics. Proposed owner: live service and operations/runtime owner.

Question: Is full-universe live fan-out an approved operating policy for the selected universe, or should a documented bounded rotation policy be introduced with explicit approval?

### 3. Quote source, synthetic state, and account snapshot

Evidence:

- Live start loads Coinbase accounts/tickers and fails before activation if account valuation/recovery fails (`LiveTradingService.cpp:2767-2809`); each loop refreshes account state (`:2353-2395`). `can_trade` requires active credentials, account loaded, no snapshot error, and explicit live execution (`:2658-2764`).
- Simulated synthetic mode maintains session-local capital/cash/positions (`SimulatedTradingService.cpp:2142-2268`). `live_parity` uses public Coinbase quotes but retains session-local synthetic capital/cash and does not load an account snapshot (`:2177-2187,2241-2251`).

Classification: exchange/network/account safety, intentionally different and undocumented. Simulated and live-parity must not share account parity claims. This is a required safety boundary.

Impact: a live-parity signal can be generated with synthetic buying power and positions, while live can be blocked by authentication, account recovery, or snapshot health. The same signal does not imply the same order intent.

Parity decision: parity required for naming, payload disclosure, and fail-closed execution classification; not for balances, positions, or account-derived gates. Proposed owner: trading contract/API owner.

Question: Should `live_parity` be renamed or should its payload explicitly include `account_source=synthetic_session` and `execution_authority=none`?

### 4. Signal generation and payload fields

Evidence:

- Both audited C++ paths use order-book strength `min(1, abs(imbalance)*1.15)` and initial threshold `0.22` (`LiveTradingService.cpp:1516-1581`; `SimulatedTradingService.cpp:1114-1117`). Both serialize signal, price, timestamp, spread, volume, imbalance, criteria, ML, strength, and execution fields (`LiveTradingService.cpp:517-542`; `SimulatedTradingService.cpp:1151-1183`).
- Both emit `bid_ask_squeeze`, directional volume-imbalance criteria, but the squeeze criterion uses imbalance `0.2` while the field is named `threshold_spread` and reports `0.0025` (`LiveTradingService.cpp:1608-1631`; simulated `:1176-1199`).
- Simulated synthetic prices, depth, and volume are generated from deterministic state (`SimulatedTradingService.cpp:1082-1106,1138-1149`), while live values come from Coinbase level-2 aggregation (`CoinbaseAdvancedClient.cpp:514-560`).

Classification: strategy contract is mostly parity-required; data-generation differences are intentionally different but undocumented. The `threshold_spread` naming mismatch is accidental schema drift.

Impact: consumers can compare fields structurally while comparing different units or provenance. The same criterion may be displayed as a spread condition even though it is evaluated on imbalance.

Parity decision: align field names/units and preserve a data provenance field. Do not alter gate thresholds as part of this audit. Proposed owner: shared signal schema owner; follow-up child for schema compatibility and regression fixtures.

Question: Is `threshold_spread` a compatibility alias that must remain, or can it be replaced by an explicit imbalance threshold with a versioned schema migration?

### 5. ML availability, fallback, profitability, and execution gates

Evidence:

- Live model path uses ready ONNX classifier/regressor/transformer, with heuristic fallback and `fallback_to_baseline` behavior (`LiveTradingService.cpp:1633-1730,1805-1833`). Simulated path has corresponding model/heuristic handling (`SimulatedTradingService.cpp:1201-1315,1390-1420`).
- Both apply profitability using expected return, spread, fees, slippage, and minimum strength (`LiveTradingService.cpp:1733-1769`; simulated `:1318-1354`). Execution analysis separately classifies blockers (`LiveTradingService.cpp:1835-1931`; simulated `:518-613`).
- Live can additionally block on account, spot, cash, minimum notional, pending orders, and `live_order_execution`; simulated uses session-local constraints and never dispatches an exchange order.

Classification: intentionally different but undocumented at data and authority boundaries; safety gates must remain fail-closed and definitionally aligned. A signal-count mismatch alone is not accidental drift.

Impact: live may produce a non-HOLD display row but no executable intent. Simulated can exercise local positions without provider rejection, account reservation, or fill uncertainty.

Parity decision: require equal meaning for `signal_generated`, expected-return availability, `executable_intent`, and blocker categories. Do not require equal execution outcomes. Proposed owner: shared diagnostics/schema owner and live execution owner.

Question: Should a simulated sell/short blocker model live spot restrictions exactly, or should the payload state that simulated position mechanics are intentionally permissive?

### 6. Latest-by-symbol aggregation, pagination, and totals

Evidence:

- Live in-memory query deduplicates latest timestamp per symbol, adds missing placeholders, sorts, then paginates (`LiveTradingService.cpp:3242-3363`). `total_signals`, `total_analyzed`, and `active_signals` are computed from the full filtered latest set (`:3320-3353`).
- Simulated in-memory query applies the same latest-by-symbol model (`SimulatedTradingService.cpp:2375-2458`) and counts non-HOLD rows over the full filtered latest set.
- Both persisted fallback paths use `COUNT(DISTINCT symbol)` and `DISTINCT ON (symbol)`, but count `active_signals` while iterating page rows (`LiveTradingService.cpp:3366-3461`; simulated `:2500-2577`).

Classification: accidental drift. The cold-start/persisted path cannot change the meaning of an API field merely because pagination is applied earlier.

Impact: after restart, `active_signals` is page-size dependent and can be lower than the in-memory value for the same symbols. Frontend summary counts then differ based on process lifetime and selected page size.

Parity decision: require active count and total count to be computed over the same filtered latest-by-symbol set before slicing, with session scope explicitly decided. Proposed owner: backend persistence/query owner. Follow-up: add a contract test covering page 1/page 2 and cold-start/warm-start equivalence.

Question: Must historical rows from prior sessions be excluded by default? The current persisted queries are not session-scoped according to both audits.

### 7. Per-row versus pagination `total_signals`

Evidence:

- Per-row `SignalRecord.total_signals` is `tick * max(1, symbol_count) + symbol_index + 1` (`LiveTradingService.cpp:1580-1581`; simulated `:1149`).
- API pagination `total_signals` is latest filtered symbol count, not cumulative generated rows (`LiveTradingService.cpp:3320-3353`; simulated `:2426-2458`).

Classification: intentionally different implementation concepts but undocumented and collision-prone. The field names create accidental semantic drift for consumers.

Impact: dashboards or analytics can mistake a row ordinal for result-set size, especially when the same JSON object contains both fields.

Parity decision: preserve backward compatibility but document or rename the row ordinal; expose one canonical pagination total. Proposed owner: API schema owner.

Question: Is the row-level field consumed externally? If not, deprecate it; if yes, add an explicit `generation_sequence` alias and keep the old field temporarily.

### 8. Persistence, retention, and restart behavior

Evidence:

- Live retains 100 recent trades and `max(250, symbols_.size())` recent signals (`LiveTradingService.cpp:1934-1942`), while simulated keeps latest-by-symbol in memory and caps recent trades at 100 (`SimulatedTradingService.cpp:1423-1428`).
- Both persist `order_book_signals` with JSON payload and scalar fields, batch writes, and requeue failures (`LiveTradingService.cpp:332-353,1409-1513`; simulated `:314-369,940-1042`). Neither audit found a durable signal retention/delete policy.

Classification: accidental drift for in-memory retention semantics plus intentionally different but undocumented persistence lifecycle. Latest-by-symbol API behavior should be stable across restart; exact cache size need not be equal.

Impact: coverage diagnostics can become false when a large universe exceeds retained rows; old sessions can influence unscoped persisted reads; storage can grow without a policy.

Parity decision: require documented restart/session scope and API equivalence, not identical cache sizes. Proposed owner: persistence owner. Follow-up: retention decision must be approved before implementation; do not delete historical evidence opportunistically.

Question: Is durable order-book history intended for analytics, or is persistence only a restart cache? The answer changes retention and session-scoping requirements.

### 9. Diagnostics and count definitions

Evidence:

- Live diagnostics expose unique symbols, retained rows, non-HOLD rows, executable intents, blocker buckets, strength/return buckets, and `coverage_complete` (`LiveTradingService.cpp:2526-2579`). `active_recent_signal_records` includes all non-HOLD retained records, not strictly latest rows.
- Simulated status exposes selected/current/recent latest counts, cumulative evaluated/generated counters, executable intents, transformer counters, blocker counts, market-data status/failures, and coverage (`SimulatedTradingService.cpp:2012-2064`).
- Both API paths expose `active_signals`, but persisted fallback counts only the page rows as described above.

Classification: accidental drift and naming ambiguity. Different internal counters are legitimate, but shared names must have one definition.

Impact: operators can interpret active/non-HOLD as executable, compare cumulative generated with latest retained, or treat coverage false as a trading halt without knowing whether the cause is quote failure or retention.

Parity decision: define separate canonical fields: `latest_signal_count`, `latest_non_hold_count`, `executable_intent_count`, `retained_non_hold_count`, `selected_symbol_count`, `successful_quote_count`, and `coverage_complete`. Proposed owner: API/observability owner.

Question: Should `coverage_complete=false` be a display warning only or a hard execution gate? Current live execution gates are separate; do not change that without explicit approval.

### 10. Frontend polling, chunking, merging, and local fallback

Evidence:

- Frontend polls order-book signals every three seconds and chunks universes over 50 symbols (`frontend/hooks/useTrading.ts:257-269,375-445`). It merges rows, sets merged totals from row counts, sums `total_analyzed` and `active_signals`, and aggregates diagnostics (`:280-370`).
- Optional browser-local mode bypasses the backend and calls `buildSyntheticOrderBookSignals` (`frontend/lib/api.ts:1025-1034,432-548`). It advances one local tick per request, uses different sine-wave fields and a fixed hurdle, and has no backend persistence, blocker counters, or account coupling.
- Stop UI accepts `success`/`settling` and immediately marks local status inactive/invalidates queries (`frontend/hooks/useTrading.ts:187-210`); live generic stop does not expose a dedicated settling UI state (`frontend/lib/api.ts:882-913`).

Classification: frontend artifact. The chunking/polling can be an acceptable presentation concern, but local fallback is a separate simulator and must not be presented as backend/live parity. Merged `active_signals` is especially unsafe if backend chunks use persisted page-limited counts.

Impact: displayed totals can differ from direct API totals; a local fallback can show signals not produced by the backend; settling live orders may disappear from controls before account/order state is settled.

Parity decision: align normal frontend rendering with canonical backend semantics; label or disable local fallback outside development; preserve a visible `settling` state for accepted live orders. Proposed owner: frontend owner, coordinated with API schema owner.

Question: Is `NEXT_PUBLIC_FORCE_LOCAL_SIM_TRADING` still an approved operator mode? If yes, it needs a visibly separate mode label and its own contract; if no, remove it through a separate approved task.

## Matched-universe baseline contradictions

1. Same symbols do not imply same coverage: live can omit failed quotes while simulated synthetic mode generates every symbol. A count comparison without `successful_quote_count` and `missing_symbol_count` is invalid.
2. Same one-row-per-symbol display does not imply same history: both warm paths are latest-by-symbol, but persisted paths can be session-unscoped and active counts are page-limited.
3. Same `active_signals` label does not imply executable orders: non-HOLD includes blocked signals in both audited live paths; simulated has no exchange dispatch.
4. Same payload shape does not imply same provenance: live prices/depth/account gates are provider-derived; simulated values and balances are synthetic, including `live_parity` balances.
5. Same frontend page does not imply same backend result: frontend chunking and optional local fallback change cadence, totals, and state ownership.
6. Same Stop Trading label does not imply same side effect: live prevents new dispatch but may settle accepted Coinbase orders; simulated only stops its worker and flushes writes.

## Recommended follow-up ownership and acceptance gates

1. Backend/API owner: make warm-start and cold-start latest-by-symbol totals and active counts identical; decide session scoping; add page-independent count coverage.
2. Schema/observability owner: define canonical count names, provenance, quote outcome counts, freshness/stale age, and generation sequence; retain compatibility aliases only with deprecation notes.
3. Live execution owner: document full-universe fan-out policy and provider-rate safety evidence without silently shrinking the selected universe; preserve fail-closed quote/account behavior.
4. Frontend owner: stop treating local fallback as parity; correct chunk aggregation against canonical totals; represent live `settling` explicitly.
5. Strategy owner: document intentional synthetic quote/account differences and confirm gate definitions/units; add a regression fixture for `threshold_spread` versus imbalance semantics.
6. Runtime evidence owner: run a controlled read-only matched-universe observation (no orders) capturing per-symbol attempts/successes/failures, sweep duration/rate, model status, latest/non-HOLD/executable counts, persisted versus in-memory totals, and stop settlement. No runtime baseline was available in these audits.

## Verification and limitations

This is a read-only classification artifact. No live credentials, exchange orders, account mutations, runtime network session, local build, or local test was used. The report relies on the two completed source audits and their cited source locations. Exact provider response rates, latency, stale age, and runtime stop duration remain unverified and must not be inferred from this document. No repository code was changed by this report.
