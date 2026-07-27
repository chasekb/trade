# Trade Backlog Recommendation: Live vs Simulated Signal and Execution Delta Reconciliation

> **For Hermes:** Treat this as a high-risk live-trading backlog recommendation. Use the live-trading-systems and requesting-code-review skills before implementation. Do not change live order execution, symbol universe policy, or automatic fail-closed behavior without explicit approval; this item is first an evidence and contract-reconciliation task.

**Goal:** Determine and explain every material delta between the Live Trading tab and Simulated Trading tab for order-book strategy signals, displayed signal state, generated buy/sell decisions, and actual execution outcomes.

**Implementation report:** See `docs/reports/live-simulated-signal-execution-delta-2026-07-27.md` for the completed reconciliation evidence, implemented parity fix, and post-commit closeout evidence.

**Why this is needed:** The live and simulated tabs can show different signal and execution behavior even when they appear to use the same strategy and symbols. Some deltas are expected because live trading uses exchange quotes, account state, pending orders, credentials, minimum order constraints, and explicit live-order gating. Other deltas can indicate bugs: mismatched default parameters, stale persisted signal rows, frontend fallback differences, inconsistent API response shapes, or a strategy path that produces actionable simulated signals but only HOLD rows in live.

**Recent context to preserve:**
- Live order-book rows previously showed `WAITING` because backend `hold` rows were incorrectly surfaced as `data_status: insufficient`; that was fixed in `d90f26a` lineage and verified by GitHub Actions.
- Live order-book strategy later produced no buy signals because no usable ONNX models were loaded and the heuristic fallback edge could not clear the default fee/spread/slippage profitability gate; the fallback scale fix was pushed as `d90f26a9f06ffb2583cf8eccc9ed1a5ee9f0c66a` and verified by the `Docker Build Validation` workflow run `30195476727`.
- Existing persisted rows can still reflect old behavior until the fixed backend image is deployed and fresh live/simulated rows are generated.

**Primary question:** For the same strategy intent and symbol universe, where exactly do live and simulated paths diverge: market data input, strategy parameters, signal generation, ML/heuristic fallback, profitability gating, data-status semantics, frontend normalization, execution eligibility, order submission, or settlement/accounting?

**Likely files / areas to inspect:**
- `src/trading/LiveTradingService.cpp`
- `src/trading/SimulatedTradingService.cpp`
- `src/trading/StrategySignal.cpp`
- `include/trading/StrategySignal.hpp`
- `src/api/PredictController.cpp`
- `frontend/lib/api.ts`
- `frontend/hooks/useTrading.ts`
- `frontend/lib/simulatedTradingStats.ts`
- `frontend/components/dashboard/LiveTradingPanel.tsx`
- `frontend/components/dashboard/SimulatedTradingPanel.tsx`
- `frontend/components/dashboard/OrderBookSignalsTable.tsx`
- Backend tables containing signal/trade/order records, especially `order_book_signals`, live orders, simulated trades, and position/account snapshots
- Docker/GitHub Actions artifacts that identify which backend image SHA is actually deployed

---

## Execution Checklist

### 1) Establish the exact runtime and deployment baseline
- [ ] Record the current git SHA, `origin/dev` SHA, and GitHub Actions build status for the image intended to run.
- [ ] Record the running `cpp-backend` image digest/tag and confirm whether it contains the target SHA/fix markers.
- [ ] Capture tmux logs from the current stack start marker, especially `TAG=dev podman-compose up --no-build`.
- [ ] Record backend startup warnings that affect signal parity: missing ONNX models, missing feature parameters, exchange/network errors, stale database state, or fallback-mode warnings.
- [ ] Record whether live trading is active, whether live order execution is explicitly enabled, and which strategy/symbol universe/parameters are active.
- [ ] Confirm whether the simulated tab is using the same strategy and symbol universe, or document intentional differences.

### 2) Define the canonical comparison matrix
- [ ] Create a side-by-side matrix for live vs simulated with one row per symbol and one timestamp window.
- [ ] Include raw inputs: bid, ask, mid, spread fraction, depth/volume, imbalance, recent price history availability, and data timestamp/freshness.
- [ ] Include strategy config: `strategy`, symbols, thresholds, `round_trip_fee_percent`, `slippage_buffer_percent`, `min_orderbook_signal_strength`, and `orderbook_expected_return_scale_percent` if present.
- [ ] Include model state: ONNX loaded/not loaded, model version, heuristic fallback usage, win probability, confidence, expected return, and expected-return sign.
- [ ] Include signal decision fields: `signal_type`, `signal_generated`, `strength`, `signal_reason`, `data_status`, criteria analysis, strength composition, profitability-gate pass/fail, required edge, and net expected edge.
- [ ] Include execution fields: live-order-enabled, account snapshot readiness, cash/holding availability, pending order status, min-notional/product constraints, order submission status, exchange rejection reason, simulated fill status, and resulting position/trade record.
- [ ] Mark each delta as `expected`, `configuration mismatch`, `data mismatch`, `contract mismatch`, `frontend rendering mismatch`, or `bug`.

### 3) Trace backend producer contracts end to end
- [ ] Trace live endpoints from `PredictController.cpp` into `LiveTradingService.cpp` for status, order-book signals, positions, trades, and pending orders.
- [ ] Trace simulated endpoints from `PredictController.cpp` into `SimulatedTradingService.cpp` for the equivalent signal and execution/state payloads.
- [ ] Verify both producers use the same `evaluateOrderBookProfitabilityGate` semantics for order-book buy/sell eligibility.
- [ ] Verify `data_status` means the same thing in both paths: true warm-up/insufficient-history only, not generic HOLD/no-trade.
- [ ] Verify historical DB fallback rows preserve payload `data_status` and do not infer misleading readiness from `signal_type` alone.
- [ ] Verify live execution adds only live-specific blockers after signal generation, not silent signal mutation.
- [ ] Verify simulated execution/fill behavior is documented wherever it intentionally differs from live exchange submission.

### 4) Trace frontend normalization and rendering
- [ ] Trace API client methods in `frontend/lib/api.ts` for live and simulated trading status, order-book signals, trades, and positions.
- [ ] Trace React Query hooks in `frontend/hooks/useTrading.ts` and verify the Live and Simulated tabs consume the intended endpoint payloads.
- [ ] Trace `OrderBookSignalsTable.tsx` and confirm identical fields render identically across live/simulated contexts unless the mode label explicitly differs.
- [ ] Confirm frontend fallbacks use `??`, not `||`, for numeric fields so legitimate zeros are preserved.
- [ ] Identify any tab-specific normalizer that renames, slices, filters, or overwrites `signal_type`, `data_status`, `reason`, `expected_return`, or execution status.
- [ ] Add explicit UI labels/tooltips for expected live-only execution blockers such as credentials, live-order toggle, pending order, insufficient cash, minimum notional, or exchange rejection.

### 5) Build deterministic evidence fixtures
- [ ] Capture or synthesize a fixed order-book fixture that should produce a strong buy, a strong sell, and a HOLD below threshold.
- [ ] Run the same fixture through the shared profitability gate and both service-level serialization paths.
- [ ] Include cases where ONNX is unavailable and heuristic fallback is used.
- [ ] Include cases where data is truly insufficient/warming up.
- [ ] Include live-only execution blockers: live order disabled, insufficient quote balance, below exchange minimum notional, pending order already open, and exchange preview rejection.
- [ ] Include simulated-only assumptions: immediate fill, synthetic capital, and any configured simulated slippage/fee behavior.

### 6) Add regression and contract coverage
- [ ] Add backend tests proving live and simulated order-book signals produce the same `signal_type`, `strength`, expected return sign, profitability-gate result, and `data_status` for the same valid market-data fixture.
- [ ] Add backend tests proving live-only execution blockers do not rewrite an actionable signal into an unexplained HOLD.
- [ ] Add backend tests for true insufficient-data rows in both services.
- [ ] Add frontend normalizer/table tests proving the same payload renders the same signal/status/reason in both tabs.
- [ ] Add a fixture-backed test that distinguishes `signal generated but execution blocked` from `no signal generated`.
- [ ] Add a regression assertion for heuristic fallback expected edge clearing the default hurdle for strong imbalances while weak signals remain blocked.

### 7) Produce the reconciliation report
- [ ] Produce a short report with one table of observed live vs simulated deltas and one paragraph of root cause per non-expected delta.
- [ ] For every expected delta, document the invariant that makes it safe: e.g. live requires account readiness and explicit order enablement; simulated may fill immediately against synthetic capital.
- [ ] For every bug delta, create a follow-up implementation task with a minimal fix scope and a test requirement.
- [ ] For every ambiguous product/risk-policy delta, pause for user approval rather than silently adding symbol caps, blacklists, auto-sizing, or retry suppression.

---

## Closeout Criteria

- [ ] A checked-in or durable report exists that names the exact backend image SHA, GitHub Actions run, tmux capture window, API snapshots, and database query windows used as evidence.
- [ ] The report includes a live-vs-simulated comparison matrix for at least one strong buy candidate, one strong sell candidate, one HOLD below activity threshold, and one true insufficient-data/warm-up case.
- [ ] Every observed delta is classified as expected, configuration mismatch, data mismatch, contract mismatch, frontend rendering mismatch, or bug.
- [ ] Expected live-only execution blockers are visible to the operator as blockers or execution status, not hidden as generic signal waiting/HOLD rows.
- [ ] Valid order-book HOLD/no-trade rows show `data_status: sufficient`; only warm-up/insufficient-history rows show `data_status: insufficient`.
- [ ] A generated actionable signal can be distinguished from an execution-blocked signal in both backend payloads and frontend rendering.
- [ ] Live and simulated paths use one documented order-book profitability gate contract, including directional expected edge, required hurdle, fees, spread, slippage buffer, and minimum signal strength.
- [ ] Tests cover the canonical parity fixtures and pass locally or in the smallest available focused build path.
- [ ] Frontend tests cover the rendering/normalization contract and pass.
- [ ] For live-trading/execution changes, a fresh-context independent review passes before merge.
- [ ] Any code changes are committed and pushed to `dev`, and the exact pushed SHA is verified by a successful `Docker Build Validation` GitHub Actions run before the backlog item is closed.
- [ ] If deployment verification is part of the implementation scope, the fixed image is pulled/recreated, fresh live and simulated rows are generated, and the same API/DB queries prove the user-visible tabs now reflect the documented contract.

---

## Recommended Delivery Order

1. Evidence-only reconciliation first: capture runtime, API, DB, and frontend payloads without changing behavior.
2. Contract documentation second: write the canonical comparison matrix and identify which deltas are expected.
3. Add parity fixtures and tests before fixing any bug delta.
4. Fix only one bug class per implementation slice: backend contract, frontend normalization, execution-status surfacing, or deployment/stale-row handling.
5. Verify each slice with focused tests, independent review for live execution changes, push to `dev`, and exact-SHA GitHub Actions success.
6. Only after the contract is proven should optional operator controls, such as exposing `orderbook_expected_return_scale_percent`, be added to the UI.

---

## Risk Notes

- Do not mask backend contract bugs in the frontend; fix the producer semantics when the API payload is wrong.
- Do not silently add symbol caps, order blacklists, auto-raised order sizes, or retry suppression as part of reconciliation; those are separate risk-policy decisions.
- Do not treat old persisted rows as proof of current behavior unless the backend image SHA and row timestamp show they were generated by the fixed runtime.
- Do not compare live and simulated execution outcomes without accounting for live-only account state, pending orders, exchange minimums, fees, slippage, and explicit live-order enablement.
- Avoid using dashboard screenshots alone as evidence; pair every UI observation with backend API payloads and, when relevant, database rows.

---

## Tags

`trade`, `backlog`, `live-trading`, `simulated-trading`, `orderbook`, `signals`, `execution`, `frontend-backend-contract`, `profitability-gate`, `regression`, `github-actions`
