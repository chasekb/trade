# Live-parity generated/blocked signal attribution contract

`live_parity` and `live` mode evaluation share the same signal, profitability,
spot-side, minimum-notional, cash, position, and pending-order gates. The
only execution difference is settlement: live may dispatch Coinbase orders
after the explicit live-order gate; live-parity settles paper fills locally.

## Required behavior

- A generated signal rejected by a downstream gate (profitability,
  ML-confidence, account/exchange preflight) remains distinguishable from a
  genuine no-signal HOLD. Its public `signal_type` may be `hold` after a
  gate rejects it, but `signal_generated` and `execution_analysis`
  (`signal_generated`, `intended_side`, `blocker_reason`) preserve the
  originally-generated intent and side.
- `SimulatedTradingService::buildSignalRecordLocked` records the pre-gate
  decision on every signal via `signal.payload["generated_before_gate"]`
  (whether the strategy elected a buy/sell candidate before any gate could
  veto it) and `signal.payload["candidate_signal_type"]` (the elected side).
  These fields are set once, from the raw strategy/order-book decision,
  before any later code path may rewrite the displayed `signal_type`.
- `SimulatedTradingService::signalToJson` and
  `SimulatedTradingService::buildExecutionAnalysisLocked` must derive
  `signal_generated` and `intended_side` from those pre-gate payload fields
  (via `trade::trading::resolvePreGateSignalState`,
  `include/trading/PreGateSignalAttribution.hpp`), never by re-deriving them
  from the (possibly downgraded) `signal.signal_type`. A signal that was
  never generated (`generated_before_gate == false`) always reports
  `signal_generated: false` and `intended_side: "none"`.
- Paper fills are outcomes, not Coinbase submissions. A paper run must
  produce zero calls to `placeMarketOrder` and must not mutate the live
  account state.
- Generated, filled, and blocked counts are separate. Blocked intents do not
  count as fills; open paper legs are not closing outcomes.

## Coverage

`src/tests/test_pre_gate_signal_attribution.cpp` unit-tests
`resolvePreGateSignalState` directly: a generated-then-blocked buy/sell
candidate resolves to `signal_generated: true` with its original side, a
genuine never-generated hold resolves to `signal_generated: false` with
`intended_side: "none"`, and a malformed input (generated without a
buy/sell candidate) fails closed to `intended_side: "none"` rather than
fabricating a side.
