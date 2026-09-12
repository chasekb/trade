# Canonical simulated portfolio valuation contract

Status: normative decision for the simulated-trading backend, local browser simulator, and simulated-trading dashboard.

## Decision

The single source-of-truth identity is:

```text
total_value = cash_balance + total_positions_value
```

`total_positions_value` is a signed mark-to-market value. Long (`buy`) positions contribute positive current notional; short (`sell`) positions contribute negative current notional:

```text
total_positions_value = sum(
  (position.side == "buy" ? +1 : -1)
  * position.quantity
  * position.current_price
)
```

This contract is approved for all follow-up implementation and regression tasks. No consumer may add gross exposure, use an unsigned short value, or substitute an alias for `cash_balance`.

## Field contract

| Concept | Canonical field / boundary name | Meaning | Status of alternatives |
| --- | --- | --- | --- |
| Cash | `cash_balance` / `cashBalance` | Cash after every opening/closing transaction and its fee. It may be negative if the accounting state permits it; it is not spendable cash after reservations. | `current_capital`, `total_balance_usd`, and `available_balance_usd` are not cash source-of-truth fields. |
| Net open-position value | `total_positions_value` / `totalPositionsValue` | Signed sum of current position notionals. Longs are positive and shorts are negative. | A bare `positions_value` field is not emitted by the simulated service; do not invent or silently map one. |
| Gross open-position exposure | `total_positions_exposure` / `totalPositionsExposure` | Sum of absolute current notionals, useful for exposure display only. | Never use it in the total-value identity. |
| Equity | `total_value` / `totalValue` | `cash_balance + total_positions_value`, including unrealized mark-to-market value. | `current_capital` and `total_balance_usd` are legacy aliases emitted with the same numeric value by the backend, but are not independent sources. |
| Spendable cash | `available_balance_usd` | `max(0, cash_balance - pending_reserved_cash)`. | It is a reservation-aware execution gate, not portfolio cash. |
| Initial capital | `initial_capital` | Starting capital used for P&L comparison and sizing fallback. | It must not populate a missing live cash value. |

The simulated wire response is the `portfolio` object returned by `GET /api/simulated-trading/status` (the endpoint also has the legacy `/api/trading/simulated/status` alias). The response currently includes both canonical fields and compatibility aliases. Compatibility aliases may remain for older clients, but new code and tests must assert the canonical fields.

## Position valuation and event semantics

For an open position, use `quantity * current_price` at the latest mark. Apply the side sign only to `total_positions_value`; `total_positions_exposure` remains absolute. The position remains in `positions` while open and is removed after a complete close.

For notional `N` and fee `F`:

| Event | Cash transition | Position contribution while open | Total-value effect at entry/exit |
| --- | --- | --- | --- |
| Open long (`buy`) | `cash_balance -= N + F` | `+N` at the entry mark | Initial equity decreases by `F`; subsequent marks add/subtract long unrealized P&L. |
| Open short (`sell`) | `cash_balance += N - F` | `-N` at the entry mark | Initial equity decreases by `F`; subsequent marks add/subtract short unrealized P&L. |
| Close long (`sell`) | `cash_balance += exit_N - F` | Remove the long contribution | Equity becomes cash after realized P&L and both fees. |
| Close short (`buy`) | `cash_balance -= exit_N + F` | Remove the short contribution | Equity becomes cash after realized P&L and both fees. |

The ordinary spot `simulated` strategy currently rejects a new short entry (`spot_cannot_open_short`); the signed short rows below are therefore a contract/normalization fixture and are exercised through accounting helpers or live-parity paper semantics. A sell that closes a long is valid in ordinary simulated operation.

## Deterministic trace and mismatch reproduction

Use initial capital `$10,000`, fee rate `0.05%`, a long `LONG-USD` position, and a short `SHORT-USD` position. The trace contains both buy and sell events and leaves one open position at the end. Values are rounded here only for readability; assertions should use an appropriate floating-point tolerance.

1. Open long: `buy 5 @ 100` (`N=$500`, `F=$0.25`)
   - `cash_balance = $9,499.75`
   - signed positions value `= +$500`
   - `total_value = $9,999.75`
2. Open short in parity-paper/accounting fixture: `sell 2 @ 125` (`N=$250`, `F=$0.125`)
   - `cash_balance = $9,749.625`
   - signed positions value `= +$250` (`+$500 - $250`)
   - gross exposure `= $750`
   - `total_value = $9,999.625`
3. Close the long: `sell 5 @ 110` (`N=$550`, `F=$0.275`), leaving the short open
   - `cash_balance = $10,299.35`
   - signed positions value `= -$250`
   - gross exposure `= $250`
   - `total_value = $10,049.35`

The existing frontend fixture at `frontend/lib/simulatedTradingStats.test.ts:294-325` uses the equivalent final shape (`cash_balance=9400`, signed positions value `250`, gross exposure `750`, and `total_value=9650`) with buy-open, sell-open, and closed-trade rows. It is suitable for normalization coverage, but backend fixture coverage should also assert the event transitions rather than only the final snapshot.

Backend contract coverage uses the isolated `DeterministicSimulatedPortfolioFixture` in `include/trading/SimulatedTradingContract.hpp`. Construct it for the initial response, then call `advance()` once for each ordered state: `buy-open`, `sell-open`, and `sell-close-long`. `status()` returns a backend-shaped JSON response at the current state; after the last state `advance()` returns `false` and leaves the response unchanged. The fixture intentionally leaves `SHORT-USD` open and includes the legacy `current_capital` alias with equity semantics, so tests catch both unsigned short exposure and stale-cash substitution. The CTest target is `simulated_trading_contract`.

In task or product language, “positions value” refers to the canonical wire field `total_positions_value`; a bare `positions_value` field is intentionally not added to this response (see the field contract above).

The minimal stale-field mismatch is:

```text
cash_balance = 1099
current_capital = 999       # legacy/equity alias, not cash
(total_positions_value is a separate signed field)
```

A normalizer that falls back from missing `cash_balance` to `current_capital` renders `$999` as cash even though `$999` is equity. The current fallback at `frontend/lib/simulatedTradingStats.ts:259-262` and the legacy test at `frontend/lib/simulatedTradingStats.test.ts:100-158` must be treated as migration risk: remove the fallback for the canonical simulated path, or fail explicitly when the canonical cash field is absent. Do not make a stale alias authoritative merely because it is populated.

The prior signed/unsigned mismatch is also covered by `frontend/lib/simulatedTradingStats.test.ts:274-292`:

```text
cash_balance = 1099
total_positions_value = +100  # wrong unsigned short exposure
total_value = 999              # cash plus signed short value
```

The normalized result must be `totalPositionsValue=-100`, `totalPositionsExposure=100`, and `totalValue=999`; it must satisfy the identity rather than display `1099 + 100`.

## End-to-end data path

1. **HTTP route:** `include/api/PredictController.hpp:25-30` registers the simulated start/stop/status routes. `src/api/PredictController.cpp:1212-1217` reads an optional `session_id` and returns `SimulatedTradingService::getStatus()`.
2. **Backend response:** `src/trading/SimulatedTradingService.cpp:1997-2050` builds the portfolio. It computes signed position value using `signedPositionValue`, computes gross exposure separately, sets `cash_balance`, `total_value`, `current_capital`, `total_balance_usd`, and `total_positions_value`, and serializes open positions/trades.
3. **Backend accounting:** `src/trading/SimulatedTradingService.cpp:1508-1600` opens positions and applies `openCashDelta`; `:1681-1773` closes them and applies `closeCashDelta`. The reusable formulas and their identity are in `include/trading/PortfolioAccounting.hpp:10-40`.
4. **Browser API boundary:** `frontend/lib/api.ts:971-986` calls `/api/simulated-trading/status`. The local fallback starts at `:70-96`, mutates cash on events at `:276-430`, marks positions to market at `:149-183`, and returns the same portfolio shape from `buildLocalSimulatedTradingStatus`.
5. **Query boundary:** `frontend/hooks/useTrading.ts:531-547` polls the API response under `simulated-trading-stats`; the simulated WebSocket path updates that cache around `:700-730`.
6. **Normalization:** `frontend/lib/simulatedTradingStats.ts:253-325` unwraps `portfolio`, converts positions/trades, computes signed and gross position values, and derives `totalValue`. This is the only frontend place where portfolio valuation should be reconciled.
7. **Cards:** `frontend/components/dashboard/SimulatedTradingPanel.tsx:274-511` consumes the normalized snapshot. The three relevant cards are `:407-420`: Cash Balance, Total Value, and Net Positions Value. They must all render from the same normalized snapshot.

## Exact implementation and test seams

Follow-up implementation tasks should limit changes to these seams:

- Backend contract and accounting: `include/trading/PortfolioAccounting.hpp`, `src/trading/SimulatedTradingService.cpp`, and (if the response route shape changes) `include/api/PredictController.hpp` / `src/api/PredictController.cpp`.
- Backend unit coverage: `src/tests/test_portfolio_accounting.cpp:22-58` covers buy/sell cash transitions and signed identity; `src/tests/test_simulated_trading_contract.cpp` covers the deterministic response trace and is registered as `simulated_trading_contract` in `CMakeLists.txt`.
- Local simulator parity: `frontend/lib/api.ts:149-183` and `:276-430`; its mark-to-market and open/close transitions must emit the same signed fields as the C++ backend.
- Frontend normalization: `frontend/lib/simulatedTradingStats.ts:253-325`; remove stale cash fallback and preserve the canonical identity here, not in components.
- Frontend normalization tests: `frontend/lib/simulatedTradingStats.test.ts:258-325` for sign and fixture reconciliation, plus `:100-158` to replace the test that currently blesses `current_capital` as cash.
- Rendered-card regression: `frontend/components/dashboard/SimulatedTradingPanel.tsx:407-424` and `frontend/components/dashboard/SimulatedTradingPanel.test.tsx:39-124`; add initial, post-buy, and post-sell/open-position snapshots and assert all three values update together.

Out of scope for this contract: live Coinbase account valuation, signal generation, execution eligibility, P&L metric definitions unrelated to portfolio identity, and legacy archived vanilla-JS dashboards.

## Verification checklist

- [ ] Backend response contains canonical `cash_balance`, signed `total_positions_value`, `total_positions_exposure`, and `total_value`.
- [ ] Every response snapshot satisfies `total_value == cash_balance + total_positions_value` within tolerance.
- [ ] Buy/open, sell/open (where parity semantics allow it), sell/close-long, and buy/close-short apply the tabled cash deltas.
- [ ] Missing `cash_balance` cannot silently become `current_capital` or `total_value`.
- [ ] Frontend local fallback and backend response normalize to the same signed convention.
- [ ] Portfolio cards consume one normalized snapshot and update together across initial, post-buy, and post-sell states.
