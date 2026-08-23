# TRADE-BL-0027 objective evidence

Date: 2026-08-23
Status: evidence compilation; investigation remains open

## Bottom line

The checked-in evidence does **not** reproduce a live/paper outcome window, so it cannot confirm or refute the historical observation that the live order-book universe had no positive-PnL trades. It does establish the deterministic objective baseline and the source-level signal-to-intent accounting contract. Runtime metrics, symbol cohorts, signal buckets, and realized execution economics remain unavailable until a timestamped live-parity/paper window is captured.

No production code, live configuration, account state, session, order, or external trading system was changed or touched by this evidence task.

## Dataset and time window

- Runtime dataset: unavailable in the checked-in repository artifacts.
- Runtime time window: unavailable; no session ID, start/end timestamps, database export, or `/api/trading/execution-reconciliation` response was supplied.
- Selected universe for the affected run: unavailable. The UI's current default is `BTC-USD` (`frontend/components/dashboard/LiveTradingPanel.tsx:560`); the static fallback universe is `BTC-USD, ETH-USD, ADA-USD, SOL-USD, DOT-USD, XRP-USD` (`frontend/lib/symbolUniverse.ts:3`). A user-selected universe is passed through without a production cap; this is not evidence of what the historical run selected.
- Live configuration: no historical snapshot is available. Current UI defaults are strategy `ml_enhanced_orderbook`, position sizing `1%`, stop-loss/take-profit disabled, `account_position_management=disabled`, and `live_order_execution=false` (`frontend/components/dashboard/LiveTradingPanel.tsx:548-560`). The start payload excludes synthetic `initial_portfolio_size` and sends the selected symbols and `max_positions` (`:607-630`). These defaults must not be substituted for the historical run's configuration.

## Objective baseline (deterministic fixture only)

Source: `src/trading/StrategyExpectancyHarness.cpp:169-199`, assertions in `src/tests/test_strategy_expectancy_harness.cpp:26-67`, and closeout `docs/reports/strategy-expectancy-harness-closeout-2026-08-03.md`.

The fixture set contains 11 rows: nine fee-positive fixtures expected to fill and two fee-negative regression fixtures expected to be blocked. The nine positive fixtures are one each for `sma`, `ema`, `rsi`, `bollinger`, `macd`, `stochastic`, `fibonacci`, `dca`, and `buyandhold`; the two blocked rows are `sma-uptrend-fee-negative-edge` and `ema-uptrend-fee-negative-edge`.

| Metric | Fixture result | Interpretation |
|---|---:|---|
| Fixtures | 11 | Fixed synthetic price paths, not exchange data |
| Signals generated | 11 | All rows generate a non-HOLD signal in this harness |
| Filled | 9 | Fixture actionability, not exchange fills |
| Blocked intents | 2 | Both are fee-negative expected-edge regressions |
| Total realized PnL | 119.00 | Sum of fixture PnL values; synthetic units |
| Average realized win | 13.2222 | 119 / 9; all filled rows are winners |
| Average realized loss | unavailable / no losses | No filled losing row exists in this fixture |
| Net expectancy | 13.2222 per filled row | Synthetic fixture result, not live expectancy |
| Profit factor | undefined/infinite | No gross loss denominator; do not serialize as a live numeric PF |
| Max drawdown | 0.00 | Positive rows are ordered without a drawdown |
| Blocked-intent rate | 18.1818% of generated signals | 2 / 11; not a live blocker rate |

The harness tests that fee-negative rows still generate signals but are blocked before fills. It does not provide per-symbol or time-series evidence, and it does not model exchange latency, quote age, order-book depth, partial fills, adverse selection, or live fees.

## Evidence tables and source trace

### Signal and profitability path

`src/trading/StrategySignal.cpp:305-341` computes the order-book hurdle as round-trip fees + spread + slippage buffer. Buy expected edge is positive expected return; sell expected edge is negated. A candidate passes only when net expected return is strictly positive. The shared diagnostic path (`:344-400`) labels a failed candidate `negative_fee_adjusted_edge` and leaves it non-actionable.

`src/trading/LiveTradingService.cpp:1691-1753` supplies the expected-return, spread, round-trip-fee, and slippage inputs and serializes fee-adjusted expected return and required edge. `:1840-1931` annotates each signal with `execution_analysis` and classifies blockers in order: no signal/profitability, ML confidence, account-management authority, existing position, pending order, max positions, size/price, minimum notional, spot short prohibition, cash, and explicit live execution opt-in.

### Runtime evidence surface (available but not populated here)

`GET /api/trading/execution-reconciliation?hours=&session_id=&trade_type=&max_signals=` reads `order_book_signals.signal_data` and `individual_trades`; the contract and fields are documented in `docs/reports/execution-reconciliation-closeout-2026-08-08.md:26-67`. It can report signals, executable intents, blocked intents and blocker shares, winners/losers, average win/loss, expectancy, profit factor, total PnL, fees, intent conversion, and outcome coverage. A real response is required for this investigation's objective claims.

The reconciliation contract treats `individual_trades.pnl` as gross and reports realized PnL net of fees; zero-PnL opening legs are not closing outcomes. It explicitly warns on truncated signals and unexplained outcomes. No response or export is present in this worktree.

## Symbol-level and signal-bucket results

- Symbol-level results: unavailable. No runtime signal/outcome rows, selected-symbol snapshot, or reconciliation response exists.
- Signal-strength buckets: unavailable. The backend emits `execution_strength_bucket_counts` and per-row `strength_bucket` (`src/trading/LiveTradingService.cpp:1852`), but no populated runtime aggregate is checked in.
- Expected-return buckets: unavailable. The backend emits `execution_expected_return_bucket_counts` and per-row `expected_return_bucket` (`:1853`), but no populated runtime aggregate is checked in.
- The deterministic harness is grouped by strategy fixture name, not by symbol, strength bucket, expected-return bucket, blocker bucket, or time window. Its rows must not be presented as symbol/bucket performance.

## Failure-mode classification

| Suspected cause | Classification | Evidence / missing evidence |
|---|---|---|
| Weak or fee-negative expected edge | Confirmed as an intentional gate in source/tests; runtime contribution unknown | Shared gate and regression fixtures prove arithmetic, but no live pass/block counts |
| Signal-to-intent blocker suppression | Contract confirmed; runtime rate unknown | Live blocker classifier is source-backed; no session aggregate |
| Entries versus exits | Unknown | No runtime entry/exit/fill join |
| Round-trip fees, spread, slippage | Formula confirmed; realized contribution unknown | Hurdle is explicit; no realized fill prices/costs |
| Stale quotes / provider latency / rate limits | Unknown | Source has no exchange quote age evidence in the supplied artifacts; need per-symbol timestamps, status, latency, and headers |
| Adverse selection / timing | Unknown | Requires quote-at-signal, submission, fill, and mark timestamps |
| Accounting / attribution | Contract covered, runtime reconciliation unknown | Reconciliation defines net-of-fee outcome semantics; no runtime rows to validate |
| Frontend universe artifact | Possible source-level risk, historical impact unknown | Fallback/default paths are inspectable; actual browser response and selected symbols are missing |
| Legitimate market outcome | Unknown | No representative runtime outcome window |

## Reproducibility commands

Read-only commands used or sufficient to reproduce this evidence:

```text
rg -n "TRADE-BL-0027|execution-reconciliation|orderbook_expected_return_scale_percent" docs src frontend
sed -n '169,205p' src/trading/StrategyExpectancyHarness.cpp
sed -n '26,67p' src/tests/test_strategy_expectancy_harness.cpp
sed -n '305,400p' src/trading/StrategySignal.cpp
sed -n '1840,1931p' src/trading/LiveTradingService.cpp
```

The harness arithmetic above was independently checked from the fixture values. Per the remote-only verification policy, no local Docker, CMake, C++, frontend package test, or production build was run for this evidence task. Historical verification is recorded in the cited closeout reports; it is not evidence for an unobserved runtime window.

## Required next evidence

Capture a representative **paper/live-parity** window with explicit authorization and no live order submission, recording: session ID; UTC start/end; exact selected symbols; complete live parameters; per-symbol request status/latency/quote timestamp; signal rows; execution-analysis blocker rows; executable intents; orders/fills; gross PnL; fees; spread/slippage estimates and realized prices. Then call the reconciliation endpoint with a sufficiently high `max_signals` and retain the raw response plus checksum. Only that artifact can quantify average win, average loss, expectancy, profit factor, drawdown, and blocked-intent rate by symbol and signal bucket.

Until that evidence exists, TRADE-BL-0027 remains open. Parameter changes are not closure, and any live-account or execution-path change requires independent high-risk review plus exact-SHA remote CI verification.
