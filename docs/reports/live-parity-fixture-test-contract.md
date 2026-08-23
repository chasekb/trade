# Live-parity captured-market-data fixture contract

The checked-in fixture `tests/fixtures/live_parity_market_data.json` is the deterministic input contract for live-parity paper evaluation. It deliberately contains every quote field consumed by the strategy: mid, best bid, best ask, spread, imbalance, aggregate volume, and depth, plus an explicit timestamp for each tick.

## Required behavior

- `execution_mode: live_parity` consumes the captured quotes and never creates a synthetic quote when a selected symbol is missing.
- A missing or invalid quote is an explicit `market_data_unavailable` blocker. It must not create a HOLD row that looks like a valid market-data evaluation.
- Live and live-parity evaluation use the same signal, profitability, spot-side, minimum-notional, cash, position, and pending-order gates. The only execution difference is settlement: live may dispatch Coinbase orders after the explicit live-order gate; live-parity settles paper fills locally.
- A generated signal rejected by a gate remains distinguishable from a genuine no-signal HOLD. Its public signal type may be HOLD after profitability rejection, but `signal_generated` and `execution_analysis.blocker_reason` preserve the generated intent.
- Paper fills are outcomes, not Coinbase submissions. A paper run must produce zero calls to `placeMarketOrder` and must not mutate the live account state.
- Generated, filled, and blocked counts are separate. Blocked intents do not count as fills; open paper legs are not closing outcomes.

The fixture is intentionally small and reproducible. Any test that changes quote fields or strategy parameters must update the fixture version and record why the parity contract changed.
