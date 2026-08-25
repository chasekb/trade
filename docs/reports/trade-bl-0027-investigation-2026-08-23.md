# TRADE-BL-0027 investigation — live order-book universe and no-positive-PnL claim

Date: 2026-08-23 (synthesis updated 2026-08-25)
Scope: read-only source and evidence classification. No live session, order, account change, production configuration change, or behavior change was made.

## Executive determination

The observation that the live order-book universe produced no positive-PnL trades is **not confirmed**. The available material contains source traces, deterministic fixtures, and an immutable runtime excerpt, but no qualifying bounded live or live-parity-paper dataset joining selected symbols, quotes, signals, intents, orders, terminal fills, fees, and realized PnL. Missing data is reported as unavailable, not zero.

Confirmed by source/evidence: signals may be generated and blocked; accepted orders are distinct from terminal fills; live submission is explicitly gated; quote fan-out and worker cadence create observable coverage/latency risks; and legacy exact-flat closing-leg attribution has a known limitation. Ruled out by source: widget display pagination alone silently caps the selected universe, missing widget rows create intents, simulated fallback directly drives live orders, and accepted orders equal filled trades. Runtime contribution of provider failures, stale quotes, adverse selection, round-trip costs, model calibration, blocker mix, and accounting remains unknown.

## Immutable evidence and reproduced window

Primary manifest: `docs/evidence/trade-bl-0027-live-orderbook-baseline-2026-08-22/manifest.md`.
Raw excerpt: `docs/evidence/trade-bl-0027-live-orderbook-baseline-2026-08-22/raw_tmux_excerpt.log`.

The frozen excerpt spans `2026-08-22T15:51:55.995Z` through `2026-08-23T03:24:09.281Z` UTC. It identifies Transformer readiness (lookback 60, 353 features), a **simulated** worker/session `sim_17874`, repeated `individual_trades.is_closing_leg` query failures, and failed order-book fetch attempts. It is not a live-session outcome window. The selected universe, live session ID, exact request/configuration, successful quote rows, signal rows, orders, fills, fees, and PnL are unavailable. Observed failed-fetch symbols are not promoted to the selected universe.

| Required runtime evidence | Status | Meaning |
|---|---|---|
| UTC session/time window | Partial | Excerpt window exists; no qualifying live session. |
| Selected symbol payload | Unavailable | Do not substitute current UI default/fallback. |
| Live configuration and execution gate | Unavailable | Current UI defaults are not historical evidence. |
| Quote status, latency, age, and successful snapshots | Unavailable | Cannot quantify coverage, staleness, or rate limits. |
| Signals, intents, blockers, orders, terminal fills | Unavailable | Accepted orders cannot stand in for fills. |
| Gross PnL, fees, net realized PnL, closing legs | Unavailable | Query failed on missing `is_closing_leg`. |
| Symbol/signal-bucket cohorts | Unavailable | No runtime rows or reconciled response. |

The runtime query attempted `SELECT symbol, strategy_type, pnl, fees, is_closing_leg FROM individual_trades ...`; it failed because the deployed database lacked `is_closing_leg`. This is missing evidence, not evidence of zero trades or zero PnL.

## Universe, configuration, and exact code paths

The current UI default is `BTC-USD`; the static fallback is `BTC-USD, ETH-USD, ADA-USD, SOL-USD, DOT-USD, XRP-USD` (`frontend/components/dashboard/LiveTradingPanel.tsx:560`, `frontend/lib/symbolUniverse.ts:3`). These values are not asserted as the historical selection. The start payload sends selected symbols, strategy, parameters, `max_positions`, and explicit `live_order_execution` (`frontend/components/dashboard/LiveTradingPanel.tsx:607-630`); no production cap is inferred from the display.

The relevant flow is:

1. `frontend/hooks/useTrading.ts:257-444` requests selected symbols in chunks of 50, merges settled responses, and then paginates display rows. Failed chunks can leave partial coverage; diagnostic aggregation can overlap populations.
2. `src/api/PredictController.cpp:1230-1248` parses order-book signal requests. `src/trading/LiveTradingService.cpp:2810-2821` copies the start symbols; `:1208-1242` fetches them serially and omits failed quotes; `:1244-1263` selects the full vector.
3. `src/trading/LiveTradingService.cpp:2309-2403` reconciles pending orders, fetches quotes/account state, generates a tick, dispatches orders, and flushes writes. The inspected normal path has no cadence sleep after a tick; the fan-out threshold is diagnostic, not a request cap.
4. `src/trading/LiveTradingService.cpp:1840-1931` records execution analysis and blocker order: profitability/signal, ML confidence, account authority, position/pending/max-position, sizing/minimum-notional, spot short, cash, and explicit live-execution opt-in.
5. `src/trading/LiveTradingService.cpp:1162-1188` waits for terminal exchange fills before applying/persisting them. `src/api/PredictController.cpp:1710-1786` reads bounded signal/trade data and computes closing-leg realized PnL as gross PnL minus fees, with a legacy NULL fallback.
6. `src/trading/LiveTradingService.cpp:1266-1297` refreshes account balances; failure can leave prior state in use. `:2286-2298` covers close/reopen policy but does not prove that the affected run reached it.

## Deterministic objective baseline (not live evidence)

Source: `src/trading/StrategyExpectancyHarness.cpp:169-199`, `src/tests/test_strategy_expectancy_harness.cpp:26-67`.

The synthetic fixture has 11 rows: nine fee-positive rows expected to fill and two fee-negative rows expected to block. It contains one fixture each for `sma`, `ema`, `rsi`, `bollinger`, `macd`, `stochastic`, `fibonacci`, `dca`, and `buyandhold`, plus two blocked edge cases.

| Metric | Fixture result | Limitation |
|---|---:|---|
| Fixtures/signals | 11 / 11 | Synthetic rows, not exchange events. |
| Filled / blocked | 9 / 2 | Harness actionability, not terminal exchange fills. |
| Total realized PnL | 119.00 | Synthetic units. |
| Average realized win | 13.2222 | 119 / 9; no filled losers. |
| Average realized loss | Unavailable | No filled losing row exists. |
| Net expectancy | 13.2222 per filled row | Not live expectancy. |
| Profit factor | Undefined/infinite | No gross-loss denominator. |
| Max drawdown | 0.00 | Ordered positive fixture only. |
| Blocked-intent rate | 18.1818% (2/11) | Not a live blocker rate. |

`src/trading/StrategySignal.cpp:305-400` confirms the fee/spread/slippage hurdle and strictly positive fee-adjusted expected-edge gate. The fixture does not model quote age, depth, latency, partial fills, adverse selection, or live fees.

## Runtime symbol and signal-bucket results

Symbol-level results: unavailable. Signal-strength and expected-return bucket results: unavailable. The backend emits per-row fields at `src/trading/LiveTradingService.cpp:1852-1853` and serializes aggregate bucket maps at `:2575-2576`; no populated runtime aggregate is present. The synthetic harness is grouped by strategy fixture name, not symbol, strength, expected return, blocker, or time window.

## Failure-mode classification

| Suspected failure mode | Classification | Evidence / limitation |
|---|---|---|
| Widget pagination silently truncates selected universe | Ruled out as sole source cause | 50-symbol chunks are merged before display pagination (`useTrading.ts:257-444`). Failed chunks/upstream selection remain possible. |
| Frontend fallback narrowed historical universe | Unknown runtime; source risk confirmed | Historical payload/response absent. |
| Missing widget rows create intents | Ruled out | Display placeholders are not signal records. |
| Serial quote fan-out / provider failures | Source risk confirmed; runtime impact unknown | Serial fetch skips failed quotes (`LiveTradingService.cpp:1208-1242`); no per-symbol runtime status/latency dataset. |
| Unbounded request cadence | Source behavior confirmed; impact unknown | Normal tick path lacks post-tick sleep (`:2309-2403`); no provider rate trace. |
| Stale quote used for signal | Unknown | No exchange quote timestamp/max-age evidence. |
| Adverse selection / timing / slippage | Unknown | No decision-price, submission, fill-price, or latency join. |
| Round-trip fees/spread/slippage exceed edge | Formula confirmed; realized contribution unknown | Hurdle is explicit; realized costs are unavailable. |
| Weak signal/model or expected-return calibration | Unknown runtime | Synthetic gate tests exist; no live/out-of-sample cohort. |
| Profitability/ML/position/cash/min-notional blockers | Mechanism confirmed; prevalence unknown | Classifier exists; affected-window counts absent. |
| Spot-only sell/short restriction | Mechanism confirmed; prevalence unknown | `spot_cannot_open_short` is classified; side counts absent. |
| Accepted orders counted as fills | Ruled out by source contract | Pending orders require terminal fill evidence. |
| Simulated fallback drives live orders | Ruled out by source boundary | Separate endpoints/services and explicit live opt-in; no cross-path leak found. |
| Account refresh failure | Source behavior confirmed; runtime impact unknown | Failure may preserve prior state; affected logs absent. |
| Legacy exact-flat closing-leg accounting | Confirmed limitation | NULL `is_closing_leg` falls back to nonzero gross PnL (`PredictController.cpp:1778-1785`). |
| Frontend diagnostic overcount | Source/reporting defect confirmed; PnL impact unknown | Chunk diagnostics are additively merged and may overlap. |
| No-positive-PnL observation | Unknown / not confirmed | No bounded reconciled outcome dataset. |

## Objective metrics and contribution analysis

Affected-window average win, average loss, expectancy, profit factor, dollar drawdown, fees/spread/slippage drag, positive/negative/zero counts, and blocked-intent rate are unavailable. They must be computed from terminal closing legs, with net realized PnL after fees; average loss negative; zero-PnL open legs excluded; profit factor gross-positive divided by absolute gross-negative PnL; and drawdown in dollars. The synthetic table above must not be used as live baseline.

Entries and exits cannot yet be separated because no signal-to-fill lifecycle join exists. Entry admission and exit policy are source-traced, but their contribution is unknown. Round-trip cost, stale-quote exposure, adverse selection, timing, and blocker prevalence all require quote-at-decision, intent/order/fill identifiers, timestamps, prices, fees, and closing-leg classification. Accounting is source-covered but not runtime-reconciled; the missing legacy schema prevents distinguishing missing data from zero outcomes.

## Validation and regression/replay coverage

Static inspection found existing targets for strategy signal, strategy expectancy, execution reconciliation, portfolio accounting, trading statistics, position sizing, Coinbase order/portfolio/auth, and frontend symbol/start-payload contracts. Their useful assertions include fee-negative blocking, blocker buckets, net-fee accounting, cash/position identity, drawdown/win-rate conventions, malformed fill fail-closed behavior, and selected-universe payload preservation. No local build/test was run under the remote-only policy.

Required follow-up acceptance matrix:

| Area | Required replay/regression coverage |
|---|---|
| Quote/coverage | Malformed, missing, stale quotes; per-symbol status/latency; no silent universe cap; truncation diagnostics. |
| Signal/intents | Every evaluated tick; holds vs generated vs executable vs blocked; strength/expected-return cohorts. |
| Execution | Accepted/pending/partial/filled/rejected fixtures; decision-to-fill timing and adverse-price attribution. |
| Accounting | Gross/net/fees, exact-flat closing legs, partial-fill rollback, cash/position identity, no double-counted fees. |
| Safety | No credentials/no snapshot start failure; disabled live execution rejection; spot-short block; pending-stop settlement; restart recovery; account-managed exits-only. |
| Frontend contract | Exact custom universe survives payload, service state, quote iterations, signals, diagnostics, and fills. |

A deterministic persisted-row replay adapter is still absent. It must fail closed on missing required fields, never call exchange submission or mutate an account, and reconcile source rows exactly. Any account-management, liquidation, live execution, sizing, or accounting change requires independent high-risk financial review and exact-SHA Docker Build Validation.

## Ranked next actions and backlog links

1. **P0 — TRADE-BL-0028** (`proposed/open`): add bounded read-only order-book execution reconciliation with legacy-schema compatibility, per-symbol quote evidence, and accepted-order-versus-fill semantics. Expected impact: reduce unexplained outcomes and blocked-intent attribution gaps; no direct expectancy lift claimed. Link: `docs/reports/execution-reconciliation-closeout-2026-08-08.md` and the immutable manifest above.
2. **P0 — TRADE-BL-0029** (`proposed/open`, dependent on 0028): build deterministic signal-to-fill replay/cohort harness covering entries, exits, stale quotes, adverse fills, costs, blockers, and accounting. Expected impact: make average win/loss, expectancy, profit factor, drawdown, and blocked-intent cohorts measurable; no direct trading lift claimed.
3. **P1 — TRADE-BL-0030** (`proposed/open`, dependent on 0027/0029): run report-only expected-return cost-cohort calibration on reconciled live-parity data. Expected impact: potentially reduce average loss and improve expectancy/profit factor, but parameter tuning is not closure and must not change live settings without evidence and review.

The verified durable backlog is `/home/kahlil/.hermes/backlog/backlog.json`. `TRADE-BL-0027` remains `in_progress`/open because its bounded reconciled runtime window is missing. Its closeout requires this checked-in report, the immutable manifest, explicit unavailable metrics, open linked items, independent review for high-risk changes, and exact-SHA CI evidence for any code change. The backlog item is not closed by this report.

## Change and verification record

- Production code/configuration: unchanged.
- Live account/session/orders: untouched; no live execution, account mutation, liquidation, or automatic replay.
- Repository change: this report only.
- Local builds/tests: not run; remote-only policy followed.
- Static verification: report reviewed for factual consistency; source paths and manifest links cross-checked; `git diff --check` required before commit.
- CI: no production code/configuration change was made, so no new Docker Build Validation run is claimed. Historical exact-SHA runs in upstream handoffs validated prior documentation artifacts only and are not evidence of this missing runtime window.

## Sources

- `docs/evidence/trade-bl-0027-live-orderbook-baseline-2026-08-22/manifest.md`
- `docs/reports/live-orderbook-execution-attribution-closeout-2026-08-04.md`
- `docs/reports/execution-reconciliation-closeout-2026-08-08.md`
- `docs/reports/live-simulated-orderbook-throughput-normalization-closeout-2026-08-05.md`
- `docs/STRATEGY_OBJECTIVE.md`
- `src/trading/LiveTradingService.cpp:1162-1297,1691-1753,1840-1931,2286-2403,2575-2576,2810-2821`
- `src/api/PredictController.cpp:1230-1248,1710-1786`
- `src/trading/StrategySignal.cpp:305-400`
- `src/trading/StrategyExpectancyHarness.cpp:169-199`
- `src/tests/test_strategy_expectancy_harness.cpp:26-67`
- `frontend/components/dashboard/LiveTradingPanel.tsx:560-630`
- `frontend/hooks/useTrading.ts:257-444`
- `frontend/lib/symbolUniverse.ts:3`
