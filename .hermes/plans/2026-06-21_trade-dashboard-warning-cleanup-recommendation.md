# Trade Backlog Recommendation: Dashboard Warning Cleanup

> **For Hermes:** Use a small, warning-by-warning implementation slice for this item so the dashboard stays stable while the remaining lint noise is removed.

**Goal:** Clean up the remaining dashboard warnings in the trade frontend without regressing the simulated trading or live trading flows.

**Why this is needed:** The frontend build is green, but the dashboard panels still carry warning-level cleanup debt. Those warnings make it harder to spot new regressions and increase the chance that real issues get buried in noise.

**Primary scope:**
- `frontend/components/dashboard/LiveTradingPanel.tsx`
- `frontend/components/dashboard/StrategyConfigForm.tsx`
- `frontend/components/dashboard/SimulatedTradingPanel.tsx`
- Any adjacent dashboard helper or shared type file needed to eliminate the warnings cleanly

**Current warning themes observed in lint output:**
- Unused imports in `LiveTradingPanel.tsx`
- Unused local variables in `LiveTradingPanel.tsx`
- Unused `useEffect` import in `StrategyConfigForm.tsx`
- Leftover type guards / helpers that are no longer needed after the config cleanup
- Any remaining dashboard-only warning that can be removed by tightening types or deleting dead code rather than suppressing lint

---

## Execution Checklist

### 1) Audit the current warning set
- [ ] Run targeted lint on the dashboard files only.
- [ ] Record every warning and map it to the exact file and symbol.
- [ ] Group warnings into three buckets:
  - dead imports / dead variables
  - type-shape mismatches
  - UI behavior that still depends on old fallback code

### 2) Remove dead code first
- [ ] Delete unused imports rather than keeping them as placeholders.
- [ ] Remove unused locals, derived values, and stale helper functions.
- [ ] If a value is still needed for future behavior, wire it into the UI instead of leaving it dormant.

### 3) Tighten types instead of suppressing warnings
- [ ] Narrow dashboard panel props to the real config shapes used by the forms.
- [ ] Replace broad unions or `any`-style fallbacks with explicit local types where the warning is caused by type ambiguity.
- [ ] Keep normalization helpers local to the component or shared utility only if they are used by more than one panel.

### 4) Re-verify dashboard behavior
- [ ] Confirm the simulated trading panel still renders live stats, open positions, and recent trades.
- [ ] Confirm the live trading panel still exposes strategy configuration, symbols, and order-book signals.
- [ ] Confirm the strategy form still updates the active config without requiring warning-prone fallback code.

### 5) Re-run verification
- [ ] Re-run targeted ESLint on the dashboard files.
- [ ] Re-run the frontend production build.
- [ ] If any warning remains, fix the root cause rather than suppressing it.

---

## Closeout Criteria
- [ ] Targeted dashboard lint runs with zero warnings and zero errors.
- [ ] Frontend build remains green after the cleanup.
- [ ] No new `any` usage or broad suppressions were introduced to silence the warnings.
- [ ] The remaining dashboard code is easier to read because dead imports and dead locals were removed.
- [ ] A short note exists documenting any intentional helper or fallback that was kept and why.

---

## Recommended delivery order
1. Start with `LiveTradingPanel.tsx`, because it currently carries the most warning noise.
2. Clean `StrategyConfigForm.tsx` next so the shared config flow stays typed consistently.
3. Finish with `SimulatedTradingPanel.tsx` and any helper files needed to keep the warning count at zero.
4. End with lint + build verification.

---

## Risk notes
- Do not silence warnings with blanket disables unless there is a documented reason and a follow-up ticket.
- Avoid refactors that change dashboard behavior while cleaning warnings.
- Prefer deleting dead code over preserving it for hypothetical reuse.

---

## Tags
`trade`, `backlog`, `dashboard`, `lint`, `warnings`, `frontend`, `cleanup`, `typescript`, `react`
