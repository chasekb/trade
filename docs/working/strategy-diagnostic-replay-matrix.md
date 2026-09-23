# Strategy Diagnostic Replay Matrix

Status: design contract for downstream replay implementation and analysis.

## 1. Scope and safety boundary

The replay evaluates the complete configured strategy universe. It is an offline diagnostic and must never submit an exchange order, mutate a live session, change a live configuration, or turn a report into an execution decision. `actively_factored` means that the diagnostic is applied to the replay's paper decision (gate/size/exit as specified below); it does not authorize live execution.

The canonical strategy IDs are:

| Strategy ID | Family | Live/sim invocation | Replay treatment |
| --- | --- | --- | --- |
| `ml_enhanced_orderbook` | order-book + ML/heuristic | order-book branch in both services; live has the same spot/order/account gates | directional gate; ML diagnostic availability is an explicit input |
| `orderbook` | order-book | order-book branch in both services; live spot/order/account gates | directional gate |
| `sma` | indicator crossover | `evaluateStrategySignal` in both services | directional diagnostic; no short live entry |
| `ema` | indicator crossover | `evaluateStrategySignal` in both services | directional diagnostic; no short live entry |
| `rsi` | oscillator | `evaluateStrategySignal` in both services | directional diagnostic; no short live entry |
| `bollinger` | volatility/band | `evaluateStrategySignal` in both services | directional diagnostic; no short live entry |
| `macd` | indicator crossover | `evaluateStrategySignal` in both services | directional diagnostic; no short live entry |
| `stochastic` | oscillator | `evaluateStrategySignal` in both services | directional diagnostic; no short live entry |
| `fibonacci` | retracement | `evaluateStrategySignal` in both services | directional diagnostic; no short live entry |
| `dca` | accumulation | `evaluateStrategySignal` in both services; scheduled buy-only live path | buy-only allocation baseline; diagnostics report/size only unless explicitly supplied |
| `buyandhold` | allocation baseline | `evaluateStrategySignal` in both services; initial buy-only live path | buy-only benchmark; diagnostics report only by default |

A replay run is invalid if any of these 11 IDs is absent from its manifest, even if that strategy generated no signal. Unknown strategy IDs are rejected, not silently added.

## 2. Deterministic run identity and approved datasets

Every run writes a manifest before evaluation and includes:

- `schema_version`, `run_id`, UTC `created_at`, `git_sha`, executable/build identifier, and runner version;
- complete ordered strategy list (the table above), ordered symbol list, and mode (`disabled`, `report_only`, or `actively_factored`);
- dataset IDs, source type, source revision, time range, timezone, row count, and SHA-256 for every input file;
- canonical serialized strategy parameters, fee/spread/slippage policy, decision policy, and random seed;
- software/compiler/container identifiers where available.

Approved input sources, in priority order:

1. **Checked-in deterministic fixtures** from `defaultStrategyExpectancyFixtures()` and any versioned replay fixture committed with the implementation. These are the baseline and regression set and contain no exchange dependency.
2. **Versioned historical candles/order-book snapshots** in an approved replay bundle. The bundle must be immutable for the run, include timestamped bid/ask/depth/imbalance and candle fields needed by the selected strategy, and have a recorded SHA-256. A public exchange download is not approved merely because it is reachable; it must first be frozen into a versioned bundle with provenance.
3. **Captured live-parity paper/replay data** exported without order submission. It is allowed only when the capture records the selected universe, UTC timestamps, source response status, and all quote/account inputs needed to distinguish market-data blockers from execution blockers.

Live endpoints, current account balances, unpinned files, wall-clock randomness, or a missing dataset hash are never accepted as replay inputs. If a source is unavailable or malformed, the run records `dataset_unavailable`/`dataset_invalid` and remains non-actionable; it must not substitute another dataset.

Default fixture configuration is the exact `StrategyExpectancyFixture` cost policy: round-trip fee `0.015`, spread `0.0`, slippage buffer `0.002`, minimum signal strength `0.2`, oldest-to-newest prices, and the fixture's explicit expected return/PnL. Production replay must use an explicit fee schedule, observed or approved spread source, and slippage model; absent values are invalid for active factoring. Fees, spread, and slippage are fractions of notional and are applied in both directions.

`seed` is mandatory even for strategies that currently do not draw random values. The deterministic fixture seed is `0`; historical/replay seed is recorded and used for any bootstrap, resampling, synthetic fill, or order-book perturbation. Parameters are canonicalized with sorted object keys and full numeric precision; no implicit defaults may be omitted from the manifest.

## 3. Three-mode experiment matrix

For every strategy ID, run all three modes against the same dataset, seed, parameters, and cost policy. A mode comparison is valid only when the input manifest hashes match except for `mode`.

| Mode | Signal evaluation | Diagnostic handling | Paper decision | Live effect |
| --- | --- | --- | --- | --- |
| `disabled` | Generate and count the native signal | Do not call diagnostics for decision-making; availability/invalidity is still recorded if present | No strategy intent is filled; emits baseline signal/hold rows and `disabled` blocker for generated intents | none; live fail-closed behavior unchanged |
| `report_only` | Generate native signal | Evaluate diagnostics and record directional edge, hurdle, factor, and missing/invalid status | Fill using the unchanged replay baseline only; diagnostics cannot gate, resize, open, add, or close | none; diagnostics are informational |
| `actively_factored` | Generate native signal | Diagnostics are required for any edge-dependent decision | Apply the strategy's matrix role below. Missing/invalid diagnostics fail closed rather than becoming zero/high confidence | none; this is still paper/replay only |

The matrix roles for `actively_factored` are:

- `ml_enhanced_orderbook`, `orderbook`: `gate` for entry and eligible exit/add decisions. Buy edge must be positive; sell edge must be negative; `abs(directionally signed edge)` must exceed fee + spread + slippage hurdle.
- `sma`, `ema`, `rsi`, `bollinger`, `macd`, `stochastic`, `fibonacci`: `gate` for any replay entry/add/exit whose decision requires expected edge. A missing diagnostic blocks that intent. Strength alone is never an expected edge.
- `dca`: `size`/`report` only by default. The scheduled buy remains the allocation baseline, but non-finite or missing diagnostics cannot increase size; an explicitly configured gate must be named in the manifest and fail closed when unavailable.
- `buyandhold`: `report` only. It is the allocation benchmark and cannot be rejected or promoted based on diagnostic output in the default matrix.

## 4. Directional and cost evaluation

Each generated non-hold signal produces a directional row, including both an entry interpretation and (when a position exists) an exit interpretation. For a buy, `directional_expected_edge = expected_return_fraction`; for a sell, it is `-expected_return_fraction`. The required hurdle is:

`required_edge = max(0, round_trip_fee) + max(0, spread) + max(0, slippage_buffer)`.

`fee_adjusted_expected_return = directional_expected_edge - required_edge`.

A factored buy or sell is actionable only when the signal type is supported, strength is at least the configured minimum, diagnostics are available and finite, costs are finite and non-negative, and fee-adjusted expected return is strictly positive. A sell signal in a Coinbase spot live-path comparison may be evaluated as an eligible-position exit, but opening a synthetic short is always a `spot_cannot_open_short` blocker and is never live-parity evidence. DCA and buy-and-hold have no short side; a sell-side diagnostic row for either is `unsupported_direction` and cannot be filled.

Realized PnL is net of fees, spread, and slippage. Zero-PnL fills remain in fill/coverage counts but are excluded from average-win and average-loss denominators, matching the existing accounting contract. Report at minimum: signal count, actionable count, fill count, blocked intents, average win, average loss, expectancy per filled trade, profit factor, total fees, total PnL, maximum drawdown in dollars, and live-only blocker counts.

## 5. Required schemas

### Input manifest (JSON)

```json
{
  "schema_version": "strategy-replay/v1",
  "run_id": "stable identifier",
  "git_sha": "40-hex",
  "dataset": [{"id": "...", "source": "fixture|historical|paper_capture", "sha256": "64-hex", "from_utc": "...", "to_utc": "...", "rows": 0}],
  "strategies": ["ml_enhanced_orderbook", "orderbook", "sma", "ema", "rsi", "bollinger", "macd", "stochastic", "fibonacci", "dca", "buyandhold"],
  "mode": "disabled|report_only|actively_factored",
  "symbols": ["..."],
  "parameters": {},
  "costs": {"fee_fraction": 0.0, "spread_fraction": 0.0, "slippage_fraction": 0.0},
  "seed": 0,
  "bootstrap": {"replicates": 0, "confidence_level": 0.95}
}
```

Input validation rejects missing fields, duplicate/unknown strategies, empty selected universe, non-finite or negative costs, invalid seed, unverified dataset hashes, timestamps out of order, and mode values outside the matrix.

### Per-decision output row (JSONL)

```json
{
  "run_id": "...", "dataset_id": "...", "strategy": "sma", "symbol": "BTC-USD",
  "timestamp_utc": "...", "mode": "actively_factored", "signal_type": "buy|sell|hold",
  "signal_strength": 0.0, "position_state": "flat|long|ineligible|unknown",
  "expected_return_available": true, "expected_return_fraction": 0.0,
  "directional_expected_edge_fraction": 0.0, "required_edge_fraction": 0.0,
  "fee_adjusted_expected_return_fraction": 0.0,
  "diagnostic_factor": "hold|weak_strength|expected_return_unavailable|invalid_input|negative_fee_adjusted_edge|fee_adjusted_edge_passed|unsupported_signal",
  "decision": "hold|report|fill|blocked", "blocker_category": null,
  "realized_pnl_net": 0.0, "fees": 0.0, "spread_cost": 0.0, "slippage_cost": 0.0
}
```

### Summary output (JSON)

The summary contains the manifest hash, one row for every strategy and mode (including zero-signal rows), counts and metrics listed in section 4, blocker counts by category, and confidence intervals. It also contains `live_safety_invariants` with boolean pass/fail assertions; any false assertion makes the run `non_actionable`.

## 6. Blocker taxonomy and invalid diagnostics

Use stable categories, not free-form strings alone:

- `disabled_by_experiment`
- `report_only`
- `expected_return_unavailable`
- `diagnostic_invalid` (NaN, infinity, malformed schema, contradictory direction)
- `cost_input_invalid`
- `fee_negative_edge`
- `weak_signal`
- `warming_up_insufficient_history`
- `unsupported_strategy` / `unsupported_direction`
- `spot_cannot_open_short`
- `insufficient_cash`
- `minimum_notional`
- `maximum_positions`
- `existing_position` / `position_not_eligible`
- `pending_order`
- `market_data_unavailable` / `market_data_invalid`
- `dataset_unavailable` / `dataset_invalid`
- `universe_invalid`
- `unknown_execution_error`

A missing or invalid diagnostic is never reclassified as `hold` without preserving the original blocker, never treated as zero cost, and never treated as positive confidence. Unknown blocker values fail schema validation.

## 7. Sample counts, uncertainty, and comparability

A strategy/mode summary must report `n_decisions`, `n_signals`, `n_actionable`, `n_fills`, `n_wins`, `n_losses`, and `n_zero_pnl`. Do not claim a strategy recommendation from fewer than 30 filled closing outcomes; mark it `insufficient_sample`. A confidence interval is required for every metric that has at least one outcome; with fewer than 30 outcomes it is descriptive only.

Use a deterministic, seeded percentile bootstrap over timestamp-ordered closing outcomes (minimum 2,000 replicates when `n >= 30`, otherwise 1,000), with the manifest's seed and confidence level (default 95%). Report the interval method, replicate count, seed, and effective sample count. For win rate use a Wilson interval; for average win/loss, expectancy, profit factor, and total PnL use bootstrap intervals. Maximum drawdown is computed per ordered path and bootstrapped by resampled outcome paths. Do not compare modes or strategies when dataset, universe, cost policy, parameters, seed, or sample eligibility differs; emit `comparison_invalid` instead.

## 8. Fail-closed invariants

The replay and any downstream recommendation must assert all of the following:

1. It has no exchange client, order-submission capability, live-session mutation, or live configuration write path.
2. User-selected symbols are preserved exactly; no hidden cap, blacklist, retry substitution, or implicit universe expansion is permitted.
3. Live spot semantics remain unchanged: no synthetic short opening, minimum-notional/cash/pending-order/max-position/account-readiness gates are bypassed, and explicit live-order enablement is still required.
4. Missing, malformed, non-finite, or directionally contradictory diagnostics cannot produce an actively factored fill.
5. `report_only` output cannot be consumed as an execution approval; recommendations are advisory artifacts only.
6. A positive signal count, fill count, or profit factor based on insufficient/invalid coverage cannot become a recommendation.
7. Dataset, configuration, cost, seed, and git identity are captured and hash-verified before metrics are emitted.
8. Any failed invariant marks the run `non_actionable` and suppresses recommendations; it does not silently downgrade to a less restrictive mode.

A downstream implementation may add strategies only by updating this manifest, its inventory table, schemas, tests, and coverage checks together. Until then, this matrix is the closed set and no strategy may be omitted from replay reporting.
