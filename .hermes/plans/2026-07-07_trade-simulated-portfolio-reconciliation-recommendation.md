# Trade Backlog Recommendation: Simulated Trading Portfolio Reconciliation

> **For Hermes:** Treat this as a backlog recommendation item with a small, fixture-backed implementation slice. Use subagents if the item is approved and you choose to implement it.

**Goal:** Create a trade-project backlog recommendation that proves the simulated trading cash balance, positions value, and total value update in unison after buys and sells, and that the dashboard does not silently mix incompatible field semantics.

**Why this is needed:** The simulated trading tab should present one internally consistent portfolio view. Right now, the cash balance, positions value, and total value cards can appear plausible while still disagreeing about whether positions are signed or absolute, which makes it hard to trust the widget after a purchase or sale.

**Primary suspicion to validate:**
- The backend and frontend may be using different formulas for total value and positions value.
- The frontend may be displaying absolute positions value while the backend total uses signed directional exposure.
- The panel may be falling back to `current_capital` or another field when `cash_balance` is present but not the intended source of truth.
- Buy/sell and open/close flows may be updating one portfolio field but not the one the dashboard actually renders.

**Likely files / areas to inspect:**
- `src/trading/SimulatedTradingService.cpp`
- `include/trading/SimulatedTradingService.hpp`
- `frontend/lib/simulatedTradingStats.ts`
- `frontend/lib/simulatedTradingStats.test.ts`
- `frontend/components/dashboard/SimulatedTradingPanel.tsx`
- `frontend/components/dashboard/LiveTradingPanel.tsx`
- Any dashboard or backend tests that already assert portfolio totals or trade settlement behavior

---

## Execution Checklist

### 1) Reproduce and trace the mismatch
- [ ] Reproduce the simulated trading tab with a deterministic fixture or captured session that includes at least one buy, one sell, and one open position.
- [ ] Trace where the dashboard gets `cash_balance`, `positions value`, and `total value` from the backend response.
- [ ] Trace the same fields through the frontend normalization layer and the final rendered cards.
- [ ] Identify whether positions value is intended to be absolute notional, signed exposure, or a mixture of both.
- [ ] Confirm whether the UI is comparing signed and unsigned values in a way that breaks the expected invariant.

### 2) Reconcile the calculation contract
- [ ] Decide the canonical formula for total value and document it in one place.
- [ ] Decide whether `positions value` should represent absolute market value or signed exposure.
- [ ] If short positions are supported, document the exception path explicitly so the dashboard does not imply a long-only formula.
- [ ] Remove any fallback that hides a missing or stale field behind a different semantic field.
- [ ] Make buy and sell settlement behavior update the same source-of-truth fields the widget reads.

### 3) Tighten regression coverage
- [ ] Add or update a backend-side test for portfolio settlement after a buy and after a sell.
- [ ] Add or update a frontend normalization test for the mixed portfolio snapshot shape.
- [ ] Add a dashboard regression test that checks the three values move together after a purchase and after a sale.
- [ ] Include empty-state and partial-state coverage so the UI cannot silently reuse stale numbers.
- [ ] Make the test fail if the widget computes total value from one convention and positions value from another.

### 4) Verify the user-visible behavior
- [ ] Confirm the cash balance changes in the expected direction after opening and closing positions.
- [ ] Confirm positions value changes with open position notional, not with an unrelated fallback field.
- [ ] Confirm total value equals the documented formula for the chosen portfolio convention.
- [ ] Confirm the dashboard updates all three cards in the same refresh cycle.
- [ ] Confirm the UI shows a clear error or empty state instead of misleading zeros if data is missing.

---

## Closeout Criteria
- [ ] The simulated trading tab has a documented, canonical formula for cash balance, positions value, and total value.
- [ ] A deterministic regression test proves the portfolio cards stay in sync after both buy and sell events.
- [ ] The dashboard no longer mixes signed and unsigned position semantics without documenting the choice.
- [ ] The backend and frontend agree on the same source-of-truth fields for portfolio settlement.
- [ ] The fix is verified against a fixture or live session that reproduces the original mismatch.
- [ ] Future changes to the simulated trading path cannot silently break the cash/positions/total invariant again.

---

## Recommended delivery order
1. Reproduce the mismatch with a fixed fixture.
2. Decide the canonical portfolio semantics.
3. Add the regression coverage.
4. Update the backend/frontend contract and verify the three values move together.

---

## Tags
`trade`, `simulated-trading`, `portfolio`, `cash-balance`, `positions-value`, `total-value`, `frontend`, `backend`, `regression`
