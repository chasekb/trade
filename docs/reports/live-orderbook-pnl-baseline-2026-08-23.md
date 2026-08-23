# Live order-book PnL baseline — TRADE-BL-0027

Snapshot: 2026-08-23T03:53:55Z (UTC)
Repository evidence commit inspected: `8af7838` plus the evidence commits in this branch

## Determination

The available recent window confirms a **zero-executable-intent and zero-closing-outcome condition**, but it does **not** confirm that live trading produced no profitable trades. The rows are predominantly `live_parity` paper signals, and the captured live runtime evidence identifies no live session, selected-universe payload, fills, or live order-submission state. Missing outcome data is not treated as zero profitability.

## Reproduced window and sources

The canonical reproducible report is `scripts/orderbook_signal_baseline.sql`; the captured result is `artifacts/orderbook-signal-baseline-1h.csv`; the aggregation check is `scripts/summarize_orderbook_baseline.py`.

Run from the trade worktree with the read-only PostgreSQL container available:

```bash
mkdir -p artifacts
podman exec -i trade_db_1 psql -q \
  -v hours=1 -v max_signals=200000 \
  -U trading_user -d trading_db \
  -f - < scripts/orderbook_signal_baseline.sql \
  > artifacts/orderbook-signal-baseline-1h.csv
python scripts/summarize_orderbook_baseline.py
```

Primary tables:

- `order_book_signals`: epoch-second signal rows and JSON `signal_data.execution_analysis`.
- `individual_trades`: epoch-second trade rows; closing legs use `is_closing_leg` when present and the documented historical fallback only when it is null.
- Frozen runtime evidence: `docs/evidence/trade-bl-0027-live-orderbook-baseline-2026-08-22/{manifest.md,raw_tmux_excerpt.log}`.

The frozen runtime excerpt spans `2026-08-22T15:51:55.995Z` through `2026-08-23T03:24:09.281Z`. It shows a `sim_17874` simulated worker and repeated order-book fetch failures, not a qualifying live execution session. The selected universe and live request configuration were unavailable.

## Objective baseline (trailing one hour)

| Measure | Result |
| --- | ---: |
| Symbol/strategy/model groups | 398 |
| Signals evaluated | 15,519 |
| Signals generated | 5,990 |
| Executable intents | 0 |
| Blocked intents | 5,990 |
| Blocked intent rate | 100.000% |
| Intent conversion | 0.000% |
| Weighted signal strength | 0.227069 |
| Weighted expected return | 0.117118 |
| Weighted fee-adjusted expected return | 0.321068 |
| Closing legs | 0 |
| Realized PnL | unavailable — no closing legs |
| Average win / average loss | unavailable — no closing legs |
| Expectancy | unavailable — no closing legs |
| Profit factor | unavailable — no closing legs |
| Drawdown | 0.0 observed, with no realized-equity observations |
| Positive / negative / zero-PnL trades | unavailable — no closing legs |

A separate coverage query identified 14,723 rows as `live_parity`; 796 bounded rows lacked an explicit trade-type marker and remain `unknown`. No rows were guessed into live or synthetic simulation. Older outcomes are excluded rather than mixed into this one-hour window.

## Grouping and bucket contract

The checked-in CSV is grouped by symbol, strategy, and model branch. The current rows expose no model branch, so it is reported as `unknown`. `scripts/orderbook_signal_bucket_baseline.sql` adds reproducible signal-strength and expected-return buckets when rerun against the source database:

- signal strength: `<0.10`, `0.10–<0.25`, `0.25–<0.50`, `0.50–<0.75`, `>=0.75`;
- expected return: `<0`, `0–<0.10`, `0.10–<0.25`, `0.25–<0.50`, `>=0.50`;
- fee-adjusted expected return uses the same breakpoints.

The bucket query reports evaluated/generated/executable/blocked intents and averages, while preserving nulls for missing values. It cannot manufacture trade outcomes absent from `individual_trades`.

## Failure-mode classification

| Failure mode | Classification | Evidence / missing source |
| --- | --- | --- |
| Insufficient freshness/coverage | Confirmed for observed fetch failures; not quantified for selected universe | Raw excerpt records repeated TLS/network fetch failures for 18 observed symbols. No selected-symbol list or quote-age distribution captured. |
| Signal calibration | Unknown | Signal values are present, but no labeled forward outcomes or model branch metadata. |
| Expected-return/profitability hurdle | Unknown | Generated signals have expected-return fields, but all intents are blocked and blocker mix was not included in the bounded CSV. |
| Spread/slippage/fee economics | Unknown | No executable fills or per-signal spread/slippage/final fee observations in the window. |
| Position sizing/min-notional/cash/max-position blockers | Unknown | No per-row blocker distribution in the captured result; no live session state. |
| Pending-order suppression | Unknown | No selected live session or pending-order snapshot. |
| Live-fill slippage/adverse selection/timing | Not observable | No live orders or closing fills. |
| Accounting/attribution error | Unknown; schema drift is confirmed | Runtime query failed because `individual_trades.is_closing_leg` was absent. This prevents a complete outcome classification and must not be interpreted as zero PnL. |
| Frontend/reporting artifact | Partially ruled out | Backend persistence and API contracts expose execution attribution, but widget coverage is not proof of executable intents. |
| Legitimate market outcome | Unknown | Requires a qualifying live or live-parity session with closing outcomes. |

## Code paths traced

- Selected universe/start request and live routes: `include/api/PredictController.hpp`, `src/api/PredictController.cpp`.
- Live worker, order-book polling, signal construction, profitability and execution analysis: `include/trading/LiveTradingService.hpp`, `src/trading/LiveTradingService.cpp`.
- Live-parity paper data source and blocker attribution: `src/trading/SimulatedTradingService.cpp`.
- Signal persistence and outcome/report serialization: `src/api/PredictController.cpp` and `src/db/DatabaseManager.cpp`.
- After-fee accounting contract: `src/trading/TradingStatsCalculator.cpp`, `src/trading/ExecutionReconciliation.cpp`, and `include/trading/TradingStatsCalculator.hpp`.
- Frontend widget consumers: `frontend/components/dashboard/OrderBookSignalsTable.tsx`, `frontend/hooks/useTradingData.ts`, and `frontend/types/trading.ts`.

The execution-attribution implementation records `execution_analysis` and distinguishes generated signals from executable intents. Therefore 15,519 widget/coverage rows must not be read as 15,519 order intents.

## Required next evidence

1. Capture a serialized Live Trading start/status payload containing the exact selected universe, strategy parameters, fees, slippage buffer, required edge, session ID, and `live_order_execution` state.
2. Export bounded signal rows including `execution_analysis.blocker_reason`, quote timestamp/age, spread, expected-return bucket, and signal-strength bucket.
3. Export order submission and fill records with client/order IDs, fill price/quantity, fees, and timestamps.
4. Repair or migrate the runtime schema so the closing-leg field is present, then rerun the same bounded query and calculate after-fee realized PnL, average win/loss, expectancy, profit factor, drawdown, and positive/negative/zero counts.
5. Compare a qualifying live window with a `live_parity` paper window; do not change live parameters until the evidence identifies a root cause and an independently reviewed implementation item.

No production parameters were changed, no live order was submitted, and no local package/container build was run for this evidence task. Any future code/configuration fix must pass Docker Build Validation for its exact pushed SHA before closure.
