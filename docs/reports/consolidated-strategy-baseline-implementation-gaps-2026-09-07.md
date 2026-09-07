# Consolidated strategy baseline and implementation gaps

Date: 2026-09-07
Status: analysis-only; implementation-ready follow-up specification

## Executive summary

The source inventory and deterministic baseline are consistent on one important point: the repository has useful strategy and profitability diagnostics, but it does not yet emit the fields required to evaluate indicator strength, symbol, regime, holding period, or fee scenarios. The baseline therefore reports nine positive synthetic net outcomes, not trading performance. No production formula, strategy, execution path, or configuration was changed by this report.

The principal implementation gap is contract inconsistency. Order-book signals have an actionable fee/spread/slippage hurdle and minimum-strength gate; SMA, EMA, RSI, Bollinger, MACD, stochastic, and Fibonacci signals expose strength but no expected-return producer and can continue through ordinary service entry paths. DCA and buy-and-hold intentionally use fixed-size entries without an expectancy diagnostic. Whether those are exemptions or defects is a product decision, not an inference from this evidence.

## 1. Indicator and decision-path inventory

Common contract: `StrategySignal` emits `buy`, `sell`, or `hold`; strength is intended to be in `[0, 1]` (`include/trading/StrategySignal.hpp:40-44`). The profitability hurdle is round-trip fees + spread + slippage (`src/trading/StrategySignal.cpp:344-399`); order-book evaluation additionally enforces minimum strength (`src/trading/StrategySignal.cpp:305-341`). Expected-return sign is directional: sell evaluates `-expected_return`.

| Indicator/strategy | Producer and exact location | Formula / thresholds observed | Inputs | Emitted range and action status |
|---|---|---|---|---|
| orderbook | `SimulatedTradingService.cpp:1108-1129`; live `LiveTradingService.cpp:1547-1569` | `strength = min(abs(imbalance) * 1.15, 1)`; signal at `abs(imbalance) >= 0.22`; imbalance sign selects buy/sell. Heuristic expected return is `imbalance * configured scale` (`SimulatedTradingService.cpp:1271-1287`; live `:1686-1702`). | Imbalance, spread, volume, depth, momentum; fees, spread, slippage; expected return. | Signal `buy/sell/hold`; strength `[0,1]`; actively gated by profitability and minimum strength (`SimulatedTradingService.cpp:1318-1354`; live `:1733-1770`). |
| ml_enhanced_orderbook | Same order-book producer; ML enrichment at simulated `SimulatedTradingService.cpp:1205-1267`, live `:1637-1684` | Confidence `= abs(win_probability - 0.5) * 2`; classifier gate requires buy probability `>= threshold` or sell probability `<= 1-threshold` (`SimulatedTradingService.cpp:1390-1420`; live `:1805-1832`). | Classifier win probability, regressor/transformer expected PnL, confidence, spread, order-book features, model readiness/fallback. | Signal `buy/sell/hold`; strength `[0,1]`; actively gated by order-book profitability and ML direction. Transformer warm-up fails closed; permitted baseline fallback can be fail-open to heuristic. |
| sma | `StrategySignal.cpp:148-160` | Short/long moving-average crossover after `long_window + 1` prices. Strength `= clamp(0.3 + abs(short-long)/price * 200, 0, 1)`. | Price history, short and long windows. | `buy/sell/hold`; strength `[0,1]`; expected-return diagnostic is unavailable/report-only in service producers (`SimulatedTradingService.cpp:1288-1315`; live `:1703-1730`). |
| ema | `StrategySignal.cpp:148-160` | EMA crossover; same crossover strength formula and warm-up shape as SMA. | Price history, EMA windows. | `buy/sell/hold`; strength `[0,1]`; unavailable/report-only profitability diagnostic. |
| rsi | `StrategySignal.cpp:162-180` | Oversold crossing generates buy; overbought crossing generates sell; strength reflects distance beyond configured thresholds. Requires `window + 1` prices. | Price history, RSI window, oversold/overbought thresholds. | `buy/sell/hold`; strength `[0,1]`; unavailable/report-only profitability diagnostic. |
| bollinger | `StrategySignal.cpp:183-206` | Rolling mean/stddev z-score; outside configured bands generates direction; zero volatility is HOLD; strength `= clamp(abs(z)/3, 0, 1)`. | Price history, window, band multiplier. | `buy/sell/hold`; strength `[0,1]`; insufficient history/zero volatility fail closed, but valid signals lack an actionable expected-return gate. |
| macd | `StrategySignal.cpp:209-225` | MACD/signal-line crossover after slow + signal history; crossover strength is clamped to `[0,1]`. | Price history, fast/slow/signal windows. | `buy/sell/hold`; strength `[0,1]`; unavailable/report-only profitability diagnostic. |
| stochastic | `StrategySignal.cpp:228-264` | Smoothed `%D`; oversold/overbought thresholds generate direction; threshold-distance strength is clamped. | High/low/close history, smoothing and thresholds. | `buy/sell/hold`; strength `[0,1]`; warm-up fail closed; no actionable profitability gate. |
| fibonacci | `StrategySignal.cpp:267-299` | Recent high/low retracement proximity; buy in uptrend or sell in downtrend; level-distance strength is clamped. | Recent high/low range, retracement levels, trend direction. | `buy/sell/hold`; strength `[0,1]`; no-range/between-levels/warm-up hold; no actionable profitability diagnostic. |
| dca | `StrategySignal.cpp:131-141` | Buy on first entry or after configured interval; otherwise hold; scheduled buy strength is `1.0`. | Position state, tick/time interval, configured amount. | `buy/hold`; strength `{1.0, absent/hold}`; fixed-size path bypasses confidence/performance multiplier (`SimulatedTradingService.cpp:396-403`; live `:409-479`) and has no expected-return producer. |
| buyandhold | `StrategySignal.cpp:120-129` | One buy when no position; hold thereafter; initial strength is `1.0`. | Position state, configured amount. | `buy/hold`; strength `{1.0, absent/hold}`; fixed-size path bypasses multiplier and has no automatic tick-path exit. |
| unknown strategy | `StrategySignal.cpp:301-302` | Falls through to `Unknown strategy: <name>` HOLD. | Strategy name. | HOLD only; unavailable and fail-closed at signal generation, but session-start validation does not reject the name. |

### Shared execution and sizing observations

- `PositionSizingPolicy.cpp:36-75` consumes strength, win probability, model confidence, expected return, spread, volatility, live performance, and cohort performance; `:78-84` caps the result at the configured base amount.
- Simulated minimum-trade sizing can fail closed on non-positive edge or insufficient expected net PnL (`PositionSizingPolicy.cpp:94-133`; call path `SimulatedTradingService.cpp:435-486`). Live uses the multiplier and exchange/account gates but does not call that minimum-trade helper (`LiveTradingService.cpp:1991-2048`).
- Live entry analysis is detailed at `LiveTradingService.cpp:1835-1931`; it distinguishes missing signal, profitability, ML confidence, position/account state, pending orders, max positions, size/notional, spot-side, cash, and execution enablement. `openPositionLocked` repeats safety checks at `:1991-2048`.
- The harness is not a production decision path. `StrategyExpectancyHarness.cpp:113-166` applies a stronger strategy-neutral diagnostic to fixtures; its indicator/DCA/buy-and-hold behavior is not yet parity with service behavior.

## 2. Deterministic baseline evaluation

Reproduction input is `data/strategy_expectancy_fixtures.jsonl`, a transparent projection of deterministic harness fixtures (`src/trading/StrategyExpectancyHarness.cpp:172-198`). The evaluator is `tools/strategy_strength_baseline.py`; output is `docs/reports/strategy-strength-baseline-2026-08-22.json`. Python 3 standard library is the only dependency.

| Metric | Observed result | Interpretation |
|---|---:|---|
| Input rows | 11 | Deterministic fixture projection |
| Invalid rows / exact duplicates | 0 / 0 | Canonical duplicates removed after first occurrence |
| Rows with net outcomes | 9 | Two fee-negative regression cases are blocked before fill |
| Net expectancy / average win | 13.2222 | Fixture PnL units; nine positive outcomes sum to 119.0 |
| Average loss | unavailable | No filled losing fixture |
| Win rate | 100.0% (9/(9+0)) | Synthetic sample, not a performance claim |
| Max drawdown | 0.0 | Synthetic sample has no negative realized outcome |
| Exploratory 95% interval | [9.6627, 16.7818] | t interval, df=8; not IID evidence |
| Gross / fee decomposition | insufficient evidence | `gross_pnl` and fee fields are absent |

Cohort rules are strength bins `[0.0,0.2)`, `[0.2,0.4)`, `[0.4,0.6)`, `[0.6,0.8)`, `[0.8,1.0]`; missing values remain a `missing` cohort; minimum cohort size is 5; zero outcomes remain in sample denominators but not win/loss denominators.

| Requested dimension | Available rows | Baseline result | Status |
|---|---:|---|---|
| Strength buckets | 0 with `signal_strength` | All 11 missing | Insufficient evidence |
| Symbols | 0 with `symbol` | All 11 missing | Insufficient evidence |
| Market regimes | 0 with `market_regime` | All 11 missing | Insufficient evidence |
| Holding periods | 0 with `holding_period` | All 11 missing | Insufficient evidence |
| Fee scenarios | 0 with `gross_pnl`/fees | No gross/fee decomposition | Insufficient evidence |
| Monotonicity | Not computable | No observed strength values | Insufficient evidence |
| Saturation/clipping | Not computable | No observed strength values | Insufficient evidence |
| High-loss regimes | Not computable | No losses and no regime/holding-period fields | Insufficient evidence |

Fixture provenance is deterministic and offline: 11 JSONL rows, derived from the C++ harness projection; no clock, random input, exchange, database, historical, paper, or live data. The separate harness manifest defines 18 partition fixtures across train/validation/test, symbols BTC-USD/ETH-USD/SOL-USD, nine strategy families, PCA/transformer model branches, and explicit cost-gate cases; that manifest is broader than the 11-row baseline projection and must not be conflated with its observed sample.

## 3. Implementation-ready gaps and recommendations

Observed facts and recommendations are intentionally separate.

1. Observed: expected-return diagnostics are unavailable for most indicator strategies and are report-only in service producers. Recommendation: decide and document a universal fee-adjusted entry gate, or explicitly specify DCA/buy-and-hold/investment-style exemptions with a horizon and return definition. Do not change formulas before this decision.
2. Observed: expected-return units and sell sign convention are not explicit across all producers. Recommendation: define units, direction, null semantics, and sign in a versioned shared contract.
3. Observed: live and simulated sizing/gating differ, and add/reopen paths do not consistently apply the same profitability checks. Recommendation: build parity fixtures covering entry, add, exit, reopen, and live-parity modes before implementation.
4. Observed: diagnostics are persisted mainly in JSON text and the baseline lacks attribution fields. Recommendation: add an immutable analysis-only export containing `signal_id`, `timestamp_utc`, `strategy`, `signal_strength`, `symbol`, `market_regime`, `holding_period`, `gross_pnl`, `fees`, `spread`, `slippage`, `net_pnl`, `filled`, and `blocked_reason`, with a one-to-one signal/outcome key and duplicate audit fields.
5. Observed: ordinary simulated blocker reporting can conflate profitability and position-size failures. Recommendation: define an ordered shared blocker taxonomy and test that every generated-but-unfilled signal has exactly one terminal explanation.
6. Observed: unknown strategy names silently produce HOLD. Recommendation: reject unknown names at session start or expose an explicit invalid/unavailable state.
7. Observed: no baseline supports monotonicity, saturation, high-loss regime, or fee-sensitivity conclusions. Recommendation: collect sufficient observations per declared cohort (minimum 5 is the current exploratory rule), preregister any changed bins, and rerun the unchanged evaluator.

No broad UI rewrite, universe cap, retry policy, sleep, or live execution behavior change is supported by this report alone.

## 4. Reproduction commands

From the repository root:

```text
# Inspect the strategy formulas and service call sites (read-only)
git grep -n -E 'evaluateStrategySignal|evaluateOrderBookProfitabilityGate|signalPassesMlGateLocked' -- src include
git grep -n -E 'PositionSizingPolicy|minimum_trade_size_decision|buildEntryExecutionAnalysisLocked' -- src include
git grep -n -E 'defaultStrategyExpectancyPartitions|evaluateStrategyExpectancy' -- src include

# Re-run the analysis-only baseline (standard library only)
python3 tools/strategy_strength_baseline.py \
  --input data/strategy_expectancy_fixtures.jsonl \
  --output docs/reports/strategy-strength-baseline-2026-08-22.json

# Review machine-readable and Markdown outputs
python3 -m json.tool docs/reports/strategy-strength-baseline-2026-08-22.json
```

The inspection commands do not build, test, access a database, contact an exchange, submit orders, or mutate production state.

## 5. Change and verification record

- Changed file: `docs/reports/consolidated-strategy-baseline-implementation-gaps-2026-09-07.md`.
- Production formulas changed: none.
- Production source/configuration changed: none.
- Baseline artifacts reviewed: `data/strategy_expectancy_fixtures.jsonl`, `tools/strategy_strength_baseline.py`, `docs/reports/strategy-strength-baseline-2026-08-22.json`, and the source-level strategy inventory.
- Prior exact-SHA evidence: PR #14 head `314e1c55dbfe9158bfee25e268a359d9b013f262`; Docker Build Validation run `32618398603` passed both required build jobs. This report is a new documentation change and requires its own exact-SHA CI verification before repository delivery.
- No local build or test command was run under the remote-CI policy. Static verification for this documentation-only change is `git diff --check`; the remote workflow remains the authoritative build gate.
