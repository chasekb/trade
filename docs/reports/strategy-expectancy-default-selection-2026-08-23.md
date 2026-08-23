# Strategy Expectancy Default Selection Decision

Date: 2026-08-23

## Decision status

**No tuning candidate is selected. Production configuration must remain
unchanged.** This is an evidence-gated decision, not an assertion that the
current settings are optimal.

The required candidate sweep and its gate-regression evidence are not present
in this worktree. The available checked-in harness evidence is a deterministic
baseline/regression fixture only; it does not compare alternative parameter
sets, symbols, strategies, or model branches. Applying a new global default or
per-symbol override without that comparison would violate the project's
expectancy and fail-closed requirements.

## Available baseline evidence

Source: `docs/reports/strategy-expectancy-harness-closeout-2026-08-03.md`,
`include/trading/StrategyExpectancyHarness.hpp`, and the corresponding harness
implementation/test.

| Metric | Available baseline result | Interpretation |
| --- | ---: | --- |
| Fixtures | 11 | Deterministic strategy fixtures; not historical/live sample size |
| Filled trades | 9 | Positive-edge fixtures only |
| Blocked intents | 2 | Fee-negative regression fixtures |
| Average realized win | 13.2222 | 9 positive synthetic outcomes |
| Average realized loss | 0.0000 | No losing fill is admitted by this baseline fixture |
| Net expectancy | 13.2222 | Synthetic realized PnL per filled fixture |
| Profit factor | +infinity | No admitted losing fill in this fixture set |
| Maximum drawdown | 0.0000 | Ordered positive synthetic outcomes only |
| Rejection rate | Not reported | Harness baseline reports blocked intents, not the required candidate rejection-rate comparison |

The baseline numbers above are arithmetic summaries of the 11 checked-in
fixtures (nine positive fills and two fee-negative blocked rows). They are not
sufficient to establish production performance, confidence intervals, or a
parameter ranking. In particular, the zero average loss and zero drawdown are
selection-bias artifacts of the synthetic fixture composition, not evidence
that losses are absent in live trading.

## Candidate comparison

No viable candidate result is available to compare against the baseline. The
required sweep dimensions are therefore intentionally marked unresolved:

- `min_orderbook_signal_strength`
- `orderbook_expected_return_scale_percent`
- round-trip fee
- slippage buffer
- spread filters
- imbalance weighting
- position-sizing inputs

| Candidate | Avg win | Avg loss | Expectancy | Profit factor | Drawdown | Frequency | Rejection rate | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Baseline harness fixture | 13.2222 | 0.0000* | 13.2222 | +infinity* | 0.0000* | 9 fills / 11 fixtures | 2 blocked / 11 fixtures; rejection not separately measured | Retain only as evaluation baseline |
| Any tuned global candidate | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | Do not select |
| Any per-symbol override | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | Do not select |

`*` These values are fixture artifacts and must not be interpreted as live
risk metrics.

## Selected defaults and overrides

### Global default

Retain the existing production/configuration values exactly as they are. No
new default is authorized by this report, and no production configuration file
is changed by this task.

### Per-symbol overrides

None. No symbol-specific override is justified without per-symbol sample
counts and candidate-versus-baseline results.

### Rejected alternatives

No alternative is rejected on performance evidence because no candidate sweep
result is available. All unmeasured alternatives are **deferred**, not
silently accepted or rejected. A later decision must list each tested
alternative and its metrics before changing defaults.

## Safety and gate requirements

Any future selection must preserve the existing directional and cost gates:

- Buy expected edge must be positive; sell expected edge must be negative.
- Both directions must clear round-trip fees, spread, and slippage.
- Missing expected-return diagnostics remain fail-safe and cannot become
  actionable by a tuning change.
- Blocked/rejected intents remain separately attributable from signal-quality
  outcomes.
- No live-affecting value may be activated until the documented approval and
  high-risk review gates pass.

## Evidence required to reopen selection

Before selecting a global default or per-symbol override, the sweep must
provide, for the baseline and every viable candidate:

1. Chronological train/validation/test or walk-forward partition identifiers.
2. Sample counts by symbol, strategy, and model branch.
3. Average win, average loss, expectancy, profit factor, maximum drawdown,
   filled-trade frequency, and accepted/rejected/blocked intent rates.
4. Fee-, spread-, and slippage-adjusted results with directional gate
   regression coverage.
5. Deterministic ranking/reproducibility metadata and confidence limitations.
6. An explicit rejection reason for every candidate not selected.

The selection task remains open pending those artifacts. The only safe interim
implementation is to preserve the existing configuration and avoid production
mutation.
