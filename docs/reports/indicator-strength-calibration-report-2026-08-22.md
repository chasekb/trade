# Indicator strength calibration report

Date: 2026-08-22
Backlog: TRADE-BL-0013
Scope: `sma`, `ema`, `rsi`, `bollinger`, `macd`, `stochastic`, and `fibonacci`

## Executive decision

Do not ship a new indicator-strength mapping from this checkout. The repository contains deterministic expectancy fixtures and live-parity signal/diagnostic plumbing, but no persisted historical replay, captured live-parity paper outcome set, symbol-level outcome export, market-regime labels, holding-period labels, or fee-bearing trade ledger that can support calibration. Any numeric mapping fitted to the checked-in fixtures would be overfit and would violate the requirement that high-strength buckets must have positive fee-adjusted expectancy and no worse average loss.

The safe implementation handoff is therefore:

- preserve the current signal formulas and backward-compatible 0..1 output;
- treat strength as a ranking feature, not as calibrated probability or expected return;
- keep expected-return/profitability diagnostics as the independent fee/spread/slippage gate;
- add no regime filter, threshold change, or combined feature until walk-forward evidence exists;
- reject any candidate whose out-of-sample high-strength bucket is fee-adjusted negative or has a larger absolute average loss than the current mapping.

## Evidence inventory and limitations

The only outcome-bearing data found in the checkout is the deterministic fixture set in `src/trading/StrategyExpectancyHarness.cpp`. It has one positive fixture per strategy plus two SMA/EMA fee-negative fixtures. It does not contain symbol, timestamp, regime, holding period, fee, spread, slippage, entry/exit prices, or repeated observations per strength bucket. The fixture PnL is a test input, not an observed historical or live-parity result.

The harness does verify the safety boundary: positive-edge fixtures fill, while the two fee-negative fixtures are blocked by `evaluateStrategyProfitabilityDiagnostic`. This is useful regression evidence for the gate, not evidence that any indicator strength predicts realized returns.

Existing signal code confirms the calibration risk:

- SMA/EMA and MACD use a crossover gap normalized by current price, with `0.3 + distance * 200`, then clamp to 1.
- RSI and stochastic use threshold distance with a 0.3 floor and clamp to 1.
- Bollinger uses absolute z-score divided by 3.
- Fibonacci maps the selected level to `0.3 + level * 0.7`.

## Deterministic fixture audit

The following values are computed from the checked-in default fixtures and current formulas. They are diagnostic only.

| Strategy | Fixture | Signal | Current strength | Fixture net PnL | Calibration interpretation |
| --- | --- | ---: | ---: | ---: | --- |
| SMA | uptrend-positive-edge | buy | 1.000 | +18 | Saturated; cannot distinguish this case from a weaker crossover. Hold mapping. |
| EMA | uptrend-positive-edge | buy | 1.000 | +16 | Saturated. Hold mapping. |
| RSI | oversold-positive-edge | buy | 1.000 | +14 | Saturated at monotonic extreme. Hold mapping. |
| Bollinger | drop-positive-edge | buy | 1.000 | +12 | Saturated at a large z-score. Hold mapping. |
| MACD | uptrend-positive-edge | buy | 0.306 | +15 | Not saturated in this fixture, but one path cannot establish monotonicity. Defer. |
| Stochastic | low-positive-edge | buy | 1.000 | +10 | Saturated at an extreme. Hold mapping. |
| Fibonacci | support-positive-edge | buy | 0.650 | +8 | Level ordinal is not realized expectancy. Defer. |

The nine fee-positive default fixtures (including DCA and buy-and-hold baselines) have total fixture PnL of 119 and fixture expectancy of 13.2222 per filled fixture; the harness reports no drawdown for that ordering. These are synthetic assertions and must not be reported as market performance. The two fee-negative SMA/EMA fixtures are expected-return-gated before fill and therefore cannot establish realized loss buckets.

## Required outcome dataset

Implementation must first produce a replay/export table with one row per generated intent and, where applicable, its eventual outcome:

- signal timestamp and deterministic signal/intent identifier;
- symbol and selected universe provenance;
- strategy and side;
- raw indicator values and raw distance (`gap`, RSI distance, z-score, percent-D distance, Fibonacci proximity/level);
- emitted strength before and after any candidate mapping;
- expected-return availability, directional expected edge, required fee/spread/slippage hurdle, and diagnostic factor;
- entry/exit timestamp, holding period bucket, gross PnL, fees, spread, slippage, and fee-adjusted/net PnL;
- regime label computed without look-ahead (for example trend, range, high-volatility, low-volatility);
- fill/blocked status and blocker reason.

Use `live_parity` paper data only when its Coinbase public market-data source and paper-only execution mode are retained. Synthetic sell/short fixtures cannot be mixed with live-spot parity evidence.

## Calibration measurement contract

Use fixed, predeclared buckets: strength quintiles or `[0,.2), [.2,.4), [.4,.6), [.6,.8), [.8,1]`, with a minimum sample count per bucket. Stratify by strategy, symbol, regime, side, holding period (`<=5m`, `5m-1h`, `1h-1d`, `>1d`), and cost band. Report count, fill rate, blocked rate, mean/median fee-adjusted PnL, expectancy, average win, absolute average loss, profit factor, and max drawdown. Bootstrap confidence intervals should accompany bucket means.

For ordered-strength quality, report Spearman rank correlation and adjacent-bucket deltas for fee-adjusted expectancy, average win, and absolute average loss. A candidate is monotonic only if the direction is stable in every required walk-forward test, not merely in pooled data. A high-strength bucket is disqualifying when its fee-adjusted expectancy is systematically negative or its absolute average loss is worse than the incumbent high-strength bucket.

## Expected-return/profitability diagnostic value

Compare three nested models using identical time splits:

1. raw indicator distance only;
2. raw distance plus directional expected-return/profitability fields;
3. the combined candidate strength plus diagnostics, with the existing fee/spread/slippage gate.

Measure out-of-sample expectancy, average win, absolute average loss, drawdown, precision of the top-strength bucket, and blocked intents. Diagnostics add predictive value only if model 2 improves held-out objective metrics over model 1 and model 3 preserves that improvement after costs. Missing diagnostics remain `unavailable` and fail closed on paths requiring expected edge; they must not be treated as high confidence.

## Per-strategy recommendation

| Strategy | Proposed mapping | Regime/combination rule | Status |
| --- | --- | --- | --- |
| SMA | No formula change. Fit a monotone, bounded mapping from normalized gap only after replay data; test a low-slope linear or logistic candidate against the saturated incumbent. | Require trend/regime and cost-band stratification. Combine with diagnostics only through the existing directional fee-adjusted gate. | Deferred: no evidence. |
| EMA | Same as SMA; do not assume EMA is better because it reacts faster. | Same as SMA; separately validate symbol and holding-period stability. | Deferred: no evidence. |
| RSI | Do not alter oversold/overbought thresholds or threshold-distance mapping. Test separate buy and sell calibration because reversal outcomes can be asymmetric. | Require volatility/regime interaction; reject extremes that increase loss magnitude. | Deferred: no evidence. |
| Bollinger | Do not change z-score divisor or band threshold. Test winsorized/logistic z-score mapping to remove saturation only if high-z out-of-sample buckets improve loss/expectancy. | Require volatility regime and spread/cost band; avoid interpreting a large z-score as mean-reversion edge without diagnostic support. | Deferred: no evidence. |
| MACD | Preserve crossover semantics and test a bounded histogram/crossover-distance mapping. | Require trend regime and holding-period stratification; diagnostics remain a gate, not a replacement for crossover direction. | Deferred: no evidence. |
| Stochastic | Preserve threshold semantics. Test separate distance-to-oversold and distance-to-overbought mappings; do not share a symmetric curve without evidence. | Require range/trend regime filter and cost gate; reject high-strength reversals with worse absolute loss. | Deferred: no evidence. |
| Fibonacci | Preserve level detection and treat level ordinal as categorical, not inherently stronger. | Require trend direction, level, proximity tolerance, and holding period; combine with diagnostics only after out-of-sample lift. | Deferred: no evidence. |

DCA and buy-and-hold remain allocation/baseline strategies and are not candidates for indicator-strength calibration.

## Walk-forward methodology for the implementation worker

1. Freeze the candidate formulas and bucket definitions before reading the evaluation window.
2. Split chronologically into train, validation, and test windows; never randomly split bars or intents.
3. Fit mapping parameters on train only, select thresholds on validation only, and report test metrics untouched.
4. Roll the windows forward by a fixed interval and repeat for every symbol and regime with sufficient samples.
5. Compare candidate and incumbent on the same intents where possible, including blocked intents and cost assumptions.
6. Require minimum support per high-strength bucket and confidence intervals; otherwise mark the strategy `insufficient_evidence`.
7. Reject candidates with negative high-strength fee-adjusted expectancy, worse high-strength absolute average loss, unstable sign across folds, or materially higher drawdown.
8. Persist the report inputs, formula version, parameters, sample counts, and exact evaluation window so results are reproducible.

## Fixture cases for regression coverage

### Improved behavior candidate (gate, not indicator calibration)

Use a positive directional edge that clears fees/spread/slippage and a matched fee-negative edge with the same raw signal strength. The first must remain actionable/fillable; the second must remain blocked with factor `negative_fee_adjusted_edge`. This is the only improvement supported by current evidence: cost-aware diagnostics prevent a strong-looking intent from becoming a fill when expected edge is fee-negative. It must not be described as proof that the indicator mapping itself improved.

### Rejected/held indicator mapping

Use the current SMA and EMA uptrend fixtures alongside additional synthetic distances that produce strengths at 0.4, 0.7, and 1.0. Assert that the incumbent formula saturates the large-gap cases at 1.0 and that no new mapping is enabled without outcome evidence. A future candidate that maps all three to a stronger high bucket while its high-strength realized bucket is negative or has worse absolute average loss must be rejected. This fixture protects the held decision and saturation warning.

## Implementation handoff

No source or user-facing parameter changes are authorized by this report. The implementation worker should first add the outcome capture/replay fixture contract and calibration evaluation/reporting surface, then return with walk-forward evidence. Only after a candidate passes the rejection rules should `StrategySignal.cpp/.hpp`, defaults, or frontend labels change. Any implementation that changes strength now would be an unverified trading-behavior change and should remain blocked.

## Verification and safety

No live orders, account mutations, or production runtime actions were performed. No local Docker, CMake, compiler, or test build was run. Static source inspection and deterministic arithmetic were used only to characterize the existing formulas and fixtures. Remote CI is required for any subsequent repository change; green CI alone does not close the evidence gap for calibration.
