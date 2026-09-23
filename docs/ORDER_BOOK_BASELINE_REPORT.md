# Order-book baseline report

This document describes the reproducible report contract implemented by
`trade::trading::generateOrderBookBaselineReport`. The report is a diagnostic
view over already-captured intent and outcome rows. It does not re-run a gate,
place an order, or change trading configuration.

## Source and build target

The implementation consists of:

- `include/trading/OrderBookBaselineReport.hpp`
- `src/trading/OrderBookBaselineReport.cpp`
- the `src/trading/OrderBookBaselineReport.cpp` entry in `CMakeLists.txt`

Start from a checkout containing those files (the initial implementation is
commit `b31df4c21fc743dafa7750d5ef9ad0d172642442`, or a later commit that
contains it). From the repository root, the compile/readiness check is:

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build --target trading_bot_cpp
```

There is intentionally no report-specific command-line mode or database write.
The callable API is the C++ function below. A producer or diagnostic harness
constructs a fixed `std::vector<OrderBookBaselineRow>` snapshot and invokes it:

```cpp
const auto report = trade::trading::generateOrderBookBaselineReport(
    rows,                         // captured rows, not live execution requests
    "config-2026-08-22",          // configuration_version
    "snapshot-2026-08-22T12:00Z"   // source_snapshot_id
);
```

The function takes the rows by value, sorts its local copy, and returns an
`OrderBookBaselineReport`. Consequently, the same input rows and the same two
provenance strings produce the same intent order and metric maps. The source
snapshot should be an immutable export/query identifier (or content-derived
snapshot ID), not the current wall-clock time.

## Required input row

Each `OrderBookBaselineRow` records one captured order-book intent:

| Field | Meaning |
|---|---|
| `source_row_id` | Stable identifier for the source row; required for an executable record. |
| `snapshot_timestamp` | Timestamp in the source snapshot; retained for audit and ordering. |
| `population` | `live`, `live_parity_paper`, or `simulated`. |
| `symbol` | Instrument identifier; required. |
| `strategy` | Strategy identifier; required. |
| `model_branch` | Model/fallback branch label; retained in grouping. |
| `signal_type` | Normally `buy`, `sell`, or `hold`. |
| `signal_strength` | Captured signal strength, unchanged. |
| `expected_return_available` | Whether the expected-return value is usable. |
| `expected_return_fraction` | Expected return as a fraction, before directional adjustment. |
| `fee_fraction` | Captured directional fee input. |
| `spread_fraction` | Captured directional spread input. |
| `slippage_fraction` | Captured directional slippage input. |
| `gate_decision` | `accepted`, `rejected`, `blocked`, or `insufficient`. |
| `gate_reason` | Captured decision explanation. |
| `requested_notional`, `requested_quantity`, `sizing_fraction` | Optional sizing inputs. |
| `realized_outcome`, `pnl` | Optional post-intent outcome fields. |

`configuration_version` and `source_snapshot_id` are report-level provenance,
while `source_row_id` and `snapshot_timestamp` provide row-level provenance.
Use the same configuration/version that produced the captured rows; do not
silently substitute the process's current defaults.

## Selecting the three populations

The report does not query or infer populations. The producer selects rows from
the fixed source snapshot and sets `population` on each row:

- `OrderBookRowPopulation::live` for recent live rows.
- `OrderBookRowPopulation::live_parity_paper` for paper rows generated from the
  live-parity path.
- `OrderBookRowPopulation::simulated` for simulated rows.

A recent-live selection belongs in the source query/export before the API call,
for example, by applying the repository's approved timestamp window and
recording that query/export ID as `source_snapshot_id`. Do not use a fallback
fixture, a different universe, or a newly fetched live row to fill a missing
population. An empty vector is valid and returns an empty report with zeroed
metrics.

## Returned schema

`OrderBookBaselineReport` contains:

- `report_version`: currently `order_book_baseline_v1`.
- `configuration_version`: caller-supplied configuration/version identifier.
- `source_snapshot_id`: caller-supplied immutable source snapshot identifier.
- `intents`: one `OrderBookBaselineIntent` for every input row, including rows
  that are incomplete.
- `by_population`: metrics keyed by each population present in the input.
- `grouped`: metrics keyed by `(population, symbol, strategy, model_branch)`.
- `overall`: metrics across all returned intents.

Each `OrderBookBaselineIntent` retains its complete `source` row and adds:

- `status`: normalized decision status;
- `directional_expected_edge_fraction`: expected return unchanged for `buy`,
  negated for `sell`, and zero for other signal types;
- `required_edge_fraction`: `max(0, fee) + max(0, spread) + max(0, slippage)`;
- `fee_adjusted_expected_return_fraction`: directional expected edge minus the
  required edge.

The directional transformation is report arithmetic only. It preserves the
existing fee, spread, and slippage semantics and does not modify live defaults
or execution decisions.

Each `OrderBookBaselineMetrics` value contains counts for `intents`,
`accepted`, `rejected`, `blocked`, and `insufficient`; outcome counts for
`realized_outcomes`, `wins`, and `losses`; and grouped numeric values for
`total_pnl`, `average_win`, `average_loss` (positive loss magnitude),
`expectancy`, `profit_factor`, `max_drawdown`,
`total_required_edge_fraction`, `total_fee_fraction`,
`total_spread_fraction`, and `total_slippage_fraction`.

## Population separation and missing data

Accepted, rejected, and blocked are separate populations in every metrics
summary. They are not collapsed into a success rate, and rejected or blocked
rows are not discarded. A row with an unknown decision is normalized to
`insufficient`. A row is also marked `insufficient` when any of these are true:

- `source_row_id`, `symbol`, or `strategy` is empty;
- `gate_decision` is empty;
- `expected_return_available` is false;
- expected return, fee, spread, or slippage is non-finite.

Incomplete rows remain visible in `intents`, `by_population`, and `grouped` so
the missing source data is auditable. Optional sizing/outcome values may be
absent. Metrics count only finite `pnl` values as realized outcomes; absent or
non-finite PnL contributes no outcome, win, loss, expectancy, or drawdown. No
exception is raised for empty or insufficient input.

## Deterministic fixture and expected shape

A minimal fixed fixture should include one row from each population and at
least one incomplete row, for example:

```text
source_row_id | population           | signal | expected | fee | spread | slip | decision | pnl
live-001      | live                 | buy    | 0.010     | .001| .002   | .001 | accepted | 0.004
paper-001     | live_parity_paper   | sell   | 0.008     | .001| .001   | .001 | rejected | -0.002
sim-001       | simulated            | buy    | 0.006     | .001| .001   | .001 | blocked  | <absent>
missing-001   | simulated            | buy    | <absent>  | .001| .001   | .001 | accepted | <absent>
```

For configuration `config-fixture-v1` and snapshot `fixture-snapshot-1`, the
shape must be equivalent to:

```text
report_version: order_book_baseline_v1
configuration_version: config-fixture-v1
source_snapshot_id: fixture-snapshot-1
intents: 4
statuses: accepted=1, rejected=1, blocked=1, insufficient=1
by_population: live=1, live_parity_paper=1, simulated=2
groups: one per (population, symbol, strategy, model_branch)
overall.realized_outcomes: 2
overall.total_pnl: 0.002
overall.wins: 1, overall.losses: 1
```

The sell row's directional expected edge is `-0.008`; its required edge is
`.003`, so its fee-adjusted expected return is `-.011`. The buy row's required
edge is `.004`, so its fee-adjusted expected return is `.006`. These values are
illustrative deterministic arithmetic from the fixture, not a new trading
threshold.

Rows are ordered by population (`live`, `live_parity_paper`, then `simulated`),
source row ID, timestamp, symbol, strategy, model branch, and remaining source
fields. Group keys use the same population/symbol/strategy/model values. This
ordering, together with explicit configuration and snapshot identifiers, is
the reproducibility contract.
