# Live-parity fixture comparison

Date: 2026-09-21
Backlog context: `TRADE-BL-0027`

## Scope and safety boundary

This is an offline comparison of checked-in simulated, replay, and paper-parity artifacts. It does not submit orders, access exchange credentials, mutate an account, or establish live profitability. Simulated, replay, and paper observations are not evidence of profitable live execution.

## Discovery and source inventory

Discovery commands run from the repository root:

    git status --short --branch
    search files for `*fixture*`, `*manifest*`, `*replay*`, and `TRADE-BL-0027|frozen|manifest|fixture|parity`

Relevant artifacts found:

| Artifact | Role | Time coverage/schema | SHA-256 |
|---|---|---|---|
| `src/tests/fixtures/zero_trade_orderbook_run.json` | Deterministic simulated ML-enhanced order-book lifecycle fixture | `2026-09-01T17:00:00Z`; `zero_trade_orderbook_replay.v1` | `214ed8a1e17836d19c36f0b755a1dc1a8da504c7d63e5241737c9ae1430e4009` |
| `docs/reports/strategy-expectancy-fixtures-2026-08-23.md` plus `src/trading/StrategyExpectancyHarness.cpp` | Deterministic strategy expectancy partitions | 18 rows across `2026-01-05` through `2026-03-05`; C++ fixture structs, not a persisted row file | `635a66e573b7c9c1343e51df9dce27df358b286fccae13fdd91b6a1192b0cdaa` |
| `data/replay/diagnostic_ablation_fixture.jsonl` | Offline diagnostic-factor replay input | 26 rows, `2026-01-01` through `2026-01-13`; JSONL candidate decisions | `230182fa2de0ae956d76003b925aa814f03fb01b56fd12be7c5df37ece90786b` |
| `docs/reports/live-parity-paper-and-blocker-attribution-progress-2026-08-08.md` | Contract/report for Coinbase public-data paper mode | Describes mode and code paths; no captured live-parity run included | report only |

The strategy-fixture report's SHA-256 above is the hash of the manifest document. The C++ constructors are the executable source of the 18 rows; no separate CSV/JSON export was found.

## Alignment decisions

1. No exact cross-fixture join was performed. The artifacts use different schemas, symbols, and time windows.
2. For the diagnostic replay, the aligned comparison key is `(strategy, direction)` because the input has no symbol and no order-book quote fields.
3. For the strategy expectancy harness, the aligned comparison key would be `(partition, event_time, symbol, strategy, model_branch)`, but no corresponding rows exist in the zero-trade or diagnostic-ablation artifacts.
4. For the zero-trade order-book fixture, only aggregate lifecycle counts and representative symbol records are comparable. Its `as_of` time is not present in either replay input.
5. Decimal-return convention is preserved for the strategy manifest and diagnostic replay. The zero-trade fixture uses `confidence` and `predicted_return` fields, but does not provide realized PnL, fee, spread, slippage, or fill rows.

## Reproducible comparison: diagnostic ablation replay

Command attempted:

    python tools/replay_diagnostic_ablation.py \
      --input data/replay/diagnostic_ablation_fixture.jsonl \
      --json-out /home/kahlil/.hermes/cache/scratch/diagnostic-ablation-comparison.json \
      --markdown-out /home/kahlil/.hermes/cache/scratch/diagnostic-ablation-comparison.md

The replay computation itself completed, but the checked-in exporter failed while serializing `Infinity` profit-factor values with `allow_nan=False`:

    ValueError: Out of range float values are not JSON compliant: inf

To preserve the comparison evidence without changing the repository, the replay functions were invoked directly with the same defaults (`fee_rate=0.001`, `spread_bps=2.0`, `slippage_bps=1.0`, threshold `0.60`). Results:

| Mode | Groups | Executed trades | Blocked executions | Unavailable diagnostics |
|---|---:|---:|---:|---:|
| `disabled` | 26 | 26 | 0 | 4 |
| `report-only` | 26 | 26 | 0 | 4 |
| `factored` | 26 | 13 | 13 | 4 |

The factored mode blocks the 13 sell rows (all below threshold or unavailable), while all 13 buy rows execute in this synthetic replay. Report-only net expectancy for sell groups is approximately `0.0074` before factoring; factored expectancy is `null` because those groups have no executions. The replay's meaningful-regression list contains 13 sell groups. This demonstrates diagnostic gating behavior only; it is not a live-fill or profitability claim.

The replay input covers 13 strategy labels (`orderbook`, `ml_enhanced_orderbook`, `ml`, `sma`, `ema`, `rsi`, `bollinger`, `macd`, `stochastic`, `fibonacci`, `atr`, `dca`, `buy_and_hold`) and both directions. It has no symbol, quote age, bid/ask, order intent, fill ID, or exchange response fields, so execution and PnL parity cannot be established from it.

## Reproducible comparison: zero-trade order-book fixture

Parsed values from `src/tests/fixtures/zero_trade_orderbook_run.json`:

- Mode: `simulated`; `as_of`: `2026-09-01T17:00:00Z`.
- Selected-symbol aggregate: 401; representative symbols: `BTC-USD`, `ETH-USD`, `SOL-USD`, `ADA-USD`.
- Diagnosis evaluations: 2,635; quote-success evaluations: 2,635; quote failures: 0.
- Signal holds: 1,119; generated candidates: 1,115.
- Profitability gate passed: 1,115; ML gate blocked: 1,115.
- Executable intents, simulated fills, persisted trades, `trade_open`, and `trade_completed`: all 0.
- Dominant blocker: `ml_confidence_below_threshold`, count 1,115.

The representative records exercise HOLD, ML-gated BUY, transformer warm-up, and invalid-market-data negative-control paths. They do not contain a completed execution, a fee calculation, or realized PnL. Therefore the fixture is useful for lifecycle/blocker parity, not profitability or fill parity.

## Reproducible comparison: strategy expectancy partitions

The manifest documents three chronological partitions with six rows each:

| Partition | Window | Symbols | Purpose |
|---|---|---|---|
| `train-2026-01` | 2026-01-05T00:00:00Z–00:05:00Z | BTC/ETH/SOL | Calibration |
| `validation-2026-02` | 2026-02-05T00:00:00Z–00:05:00Z | BTC/ETH/SOL | Candidate validation |
| `test-2026-03` | 2026-03-05T00:00:00Z–00:05:00Z | BTC/ETH/SOL | Chronological holdout |

The C++ harness applies shared signal generation and profitability diagnostics, records expected-return/fee/spread/slippage fields, and then uses fixture `realized_pnl` only for actionable rows. Its rows are deterministic and evaluation-only. There is no overlapping timestamp, symbol-plus-strategy row, or common execution identifier with the zero-trade fixture or diagnostic JSONL; numerical PnL comparisons would therefore be misleading.

## Live-parity availability and gaps

The checked-in paper-mode report states that `execution_mode=live_parity` uses Coinbase public order-book data, preserves missing/invalid quote failures, applies live-like policy checks, and settles paper fills without Coinbase order submission. It explicitly says a complete runtime parity closeout still requires a representative runtime window reconciling generated signals to paper/live outcomes. No such captured window, provider response archive, fill ledger, or live account evidence was found in this worktree.

Consequently:

- Signal-generation contract: partially comparable through shared diagnostic field names and deterministic fixtures.
- Expected-return and fee treatment: comparable only within the deterministic harness/replay contracts; not aligned to the zero-trade fixture.
- Execution/fill behavior: zero-trade fixture proves no fill; diagnostic replay models abstract executions; no shared fill records exist.
- PnL measures: strategy harness has fixture net PnL, diagnostic replay computes synthetic gross-return-minus-cost, zero-trade has no PnL. These are non-comparable measures.
- Live profitability: unavailable and not inferred.

## Caveats and follow-up evidence needed

1. The diagnostic exporter needs a separate remediation for infinite profit factor before its JSON/Markdown artifacts can be produced through the documented CLI; this task did not alter that tool.
2. A valid parity comparison needs one captured paper/live-parity window with common symbol, event timestamp, quote, signal, gate, intent, fill, fee, and realized-PnL identifiers.
3. The 401 selected-symbol aggregate in the zero-trade fixture is not a 401-row symbol list; only four representative symbols are present. It must not be treated as complete universe coverage.
4. All results above are simulated, deterministic replay, or paper-mode contract evidence. None is proof of live profitability, exchange execution quality, or account readiness.
