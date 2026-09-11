# Simulated portfolio reconciliation closeout — 2026-08-04

Backlog item: `TRADE-BL-0004` — Reconcile simulated trading portfolio cash and position totals.

## Scope

This slice fixes and documents the simulated portfolio accounting convention used by the dashboard cards and the local browser fallback simulator. It does not change live trading execution, Coinbase account reads, backend live safety gates, signal generation thresholds, order submission, or exchange credentials.

## Canonical convention

The simulated portfolio uses one reconciliation identity:

```text
total_value = cash_balance + total_positions_value
```

Where:

- `cash_balance` is cash after transactional open/close deltas and fees.
- `total_positions_value` is signed mark-to-market position value:
  - long positions are positive;
  - short positions are negative.
- `total_positions_exposure` is gross absolute exposure and is reported separately.
- `total_value` is derived from `cash_balance + total_positions_value` in the frontend normalization layer so the displayed tiles cannot silently diverge.

This matches the backend helper contract in `include/trading/PortfolioAccounting.hpp` and `SimulatedTradingService::buildPortfolioJson()`.

## Reproduction and root cause

A deterministic short-position fixture reproduced the mismatch class:

```text
cash_balance = 1099
total_positions_value = +100   # legacy unsigned short exposure
total_value = 999              # cash plus signed short value
```

If the frontend trusts the unsigned `total_positions_value`, the cards show:

```text
1099 + 100 != 999
```

The local browser fallback had the same convention bug: `updateLocalPortfolioMarkToMarket()` stored absolute position exposure in `total_positions_value` while computing `total_value` from cash plus signed positions value.

## Changes

- `frontend/lib/api.ts`
  - Local fallback simulator now stores signed `total_positions_value`.
  - Local fallback simulator now reports gross `total_positions_exposure` separately.
  - Local fallback `total_value` remains `cash_balance + signed total_positions_value`.

- `frontend/lib/simulatedTradingStats.ts`
  - Normalization now derives signed position value from open positions.
  - If a backend/legacy `total_positions_value` conflicts with `total_value`, normalization repairs the display using the derived signed value.
  - `totalPositionsExposure` is exposed separately.
  - `totalValue` is derived from the canonical identity.

- `frontend/components/dashboard/SimulatedTradingPanel.tsx`
  - The simulated portfolio card label is now `Net Positions Value` so operators do not confuse signed position value with gross exposure.

- `frontend/lib/simulatedTradingStats.test.ts`
  - Added a regression fixture for the legacy unsigned short-value mismatch.
  - Added a deterministic buy/sell/open-position fixture covering cash, signed positions value, gross exposure, total value, and trade stats.

## Objective impact

This is a reporting/accounting reconciliation fix. It should improve operator interpretation of expectancy and drawdown by preventing mismatched portfolio tiles from hiding short exposure semantics. It does not increase signal count, trade count, position sizing, live order eligibility, or execution aggressiveness.

Expected impact:

- average realized win: unchanged;
- average realized loss: unchanged;
- net expectancy/profit factor/drawdown: unchanged mechanically, more accurately displayed;
- fees/spread/slippage drag: unchanged;
- blocked intents: unchanged;
- live-account safety: unchanged.

## Verification before push

Allowed local checks only; no local Docker/backend build:

- `npx jest lib/simulatedTradingStats.test.ts --runInBand` — passed, 9 tests.
- `npx eslint lib/simulatedTradingStats.ts lib/simulatedTradingStats.test.ts components/dashboard/SimulatedTradingPanel.tsx` — passed.
- `npx tsc --noEmit` — passed.
- `git diff --check` — passed.
- Independent review `deleg_838791b5` — approved with no blockers.

A broader lint command that included all of `frontend/lib/api.ts` still reports pre-existing `no-explicit-any` debt outside this slice; no new `any` usage was added by this change.

Backlog closeout still requires exact pushed SHA verification through GitHub Actions Docker Build Validation.
