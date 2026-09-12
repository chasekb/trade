# Live Order-Book Widget Coverage Closeout

Date: 2026-08-03

## Backlog scope

This report closes the code-backed implementation slice for:

- TRADE-BL-0024 — Remove live order-book widget per-tick symbol cap
- TRADE-BL-0025 — Review order-book signal widgets for artificial limitations
- TRADE-BL-0026 — Investigate why live order-book widget still shows a per-tick cap

No local Docker/CMake build was run, per user instruction. No Coinbase orders, liquidation, position changes, account-management changes, or live trading restarts were performed.

## Root cause classification

The remaining visible cap was a mixed widget/API contract issue, not an execution-safety change:

1. `LiveTradingService::getOrderBookSignals()` returned only latest signals already present in the live in-memory cache. Because live Coinbase quote fetches are intentionally capped and rotated per tick (`kMaxLiveQuoteSymbols = 10`), a freshly-started large universe could make widget totals look capped to the current batch instead of representing the selected universe.
2. `useOrderBookSignals()` chunked large selected universes, but requested only `page * perPage` rows from each chunk. That made widget page size influence fetch coverage for large universes, even though page size should be display-only after chunk merging.
3. The UI already surfaced the live per-tick quote cap as Coinbase/API cadence diagnostics, but it did not distinguish selected-universe widget coverage from latest quote freshness for not-yet-fetched symbols.

Required live-exchange safety remains intentionally separate: the backend still bounds per-tick Coinbase quote fetch cadence and rotates the selected universe. The fix does not increase live order submission, bypass profitability gates, bypass max-position checks, or alter account authority.

## Implemented changes

### Backend widget coverage contract

`src/trading/LiveTradingService.cpp`

- Keeps the Coinbase/API cadence cap visible and unchanged.
- When a request includes selected symbols, returns response-only placeholder rows for selected symbols that do not have a latest live quote/signal yet.
- Placeholder rows are `hold`, `data_status=missing`, zero strength, and explicitly explain that the live quote cadence is rotating across the selected universe.
- Placeholder rows are not persisted and do not create `OrderIntent`s.
- `total_analyzed`, pagination totals, `active_signals`, and `average_strength` now describe the full requested/returned selected-universe population rather than only the current display page.
- Diagnostics now include:
  - `selected_symbol_count`
  - `missing_latest_signal_count`
  - `missing_latest_signal_symbols`
  - `widget_coverage_contract`

### Frontend fetch and diagnostics

`frontend/hooks/useTrading.ts`

- For selected universes larger than a single request chunk, each backend chunk now requests `per_page = chunk.length` and then performs display pagination after merging.
- Page size/page number no longer reduce chunk fetch coverage.
- Per-chunk diagnostics are merged so selected counts, quote attempts/successes/skips, missing latest rows, current batch symbols, and retained signal counts describe the full selected universe rather than only the first request chunk.

`frontend/components/dashboard/OrderBookSignalsTable.tsx`

- Coverage diagnostics now label selected symbol count, missing latest rows, and the first missing symbols waiting for quote rotation.
- The widget displays the explicit contract that missing rows are response-only and do not submit orders.

`frontend/types/trading.ts`

- Added typed diagnostics fields for selected count, missing latest row count/symbols, and widget coverage contract.

`frontend/components/dashboard/LiveTradingPanel.tsx`
`frontend/components/dashboard/SimulatedTradingPanel.tsx`

- Updated stale comments to match the restored fetch/merge behavior.

## Safety checks preserved

This change does not modify:

- `live_order_execution` opt-in semantics
- Coinbase order dispatch
- pending order duplicate prevention
- max-position gating
- minimum notional checks
- cash/holding availability checks
- fee/spread/slippage profitability gates
- account-position-management authority gates
- liquidation flow
- selected universe values or retry/blacklisting behavior

The only backend rows added by this change are response-only placeholder rows for widget coverage/freshness visibility.

## Verification performed locally

Allowed non-build checks only:

- PASS: targeted frontend Jest: `npx jest components/dashboard/__tests__/dashboard-tables.test.tsx --runInBand` — 7 tests passed.
- PASS: TypeScript no-emit: `npx tsc --noEmit`.
- PASS: Git whitespace check: `git diff --check`.
- PASS with expected literals only: static secret scan over touched files found no secret values; it flagged existing placeholder/config key names such as `COINBASE_API_KEY` and `COINBASE_API_SECRET`, not credentials.
- PASS: independent live-trading safety review `deleg_c8d05fd0` approved the uncommitted diff with no live-trading safety blockers; reviewer confirmed added missing-symbol rows are read-response placeholders and do not touch order dispatch, order intents, or execution gates.
- BLOCKED by pre-existing lint debt: targeted ESLint on touched frontend files still reports existing `no-explicit-any`, `set-state-in-effect`, and unused-symbol findings in `frontend/hooks/useTrading.ts`, `frontend/types/trading.ts`, and dashboard components. The changed lines add no new `any`, set-state-in-effect, or unused import pattern; this remains covered by TRADE-BL-0003.

Remote verification required before backlog closure:

- Commit and push to `dev`
- Verify GitHub Actions Docker Build Validation for the exact pushed SHA

## Closeout criteria mapping

- Full selected-universe widget coverage: satisfied by response-only missing rows plus chunk-wide fetching.
- Display pagination is display-only: satisfied for chunked frontend requests by fetching every symbol in each chunk before merge/page slicing.
- Remaining live quote cap is explicit: preserved as `live_quote_symbols_per_tick_cap` and documented in the UI; it is Coinbase/API cadence safety, not a hidden widget cap.
- No live-order behavior changes: satisfied; only signal read API response shape and frontend display/fetch behavior changed.
- Remote CI: pending until exact pushed SHA is verified green.
