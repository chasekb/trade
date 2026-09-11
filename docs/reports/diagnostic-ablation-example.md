# Diagnostic ablation replay

Input: `data/replay/diagnostic_ablation_fixture.jsonl`
Input SHA-256: `0e29a01a12321e3e3952703b7c62a1b7091f386ad0b53d3d2a10f0de68fec9b8`
Configuration hash: `c1de513b0d2ffaeb02033f1247bada48194f65047f5ca93c236a9a5c2419557a`
Modes: disabled, report-only, factored

Missing and invalid diagnostics are counted separately and never treated as zero.

| Strategy | Direction | Mode | Samples | Trades | Blocked | Missing | Invalid | Avg win | Avg loss | Expectancy | PF | Drawdown | Frequency |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| orderbook | buy | disabled | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| orderbook | sell | disabled | 1 | 1 | 0 | 1 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| ml_enhanced_orderbook | buy | disabled | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| ml_enhanced_orderbook | sell | disabled | 1 | 1 | 0 | 0 | 0 | 0.007400 | — | 0.007400 | ∞ | 0.000000 | 1.000000 |
| ml | buy | disabled | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| ml | sell | disabled | 1 | 1 | 0 | 0 | 0 | 0.007400 | — | 0.007400 | ∞ | 0.000000 | 1.000000 |
| sma | buy | disabled | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| sma | sell | disabled | 1 | 1 | 0 | 1 | 0 | 0.007400 | — | 0.007400 | ∞ | 0.000000 | 1.000000 |
| ema | buy | disabled | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| ema | sell | disabled | 1 | 1 | 0 | 0 | 0 | 0.007015 | — | 0.007015 | ∞ | 0.000000 | 1.000000 |
| rsi | buy | disabled | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| rsi | sell | disabled | 1 | 1 | 0 | 0 | 0 | 0.007400 | — | 0.007400 | ∞ | 0.000000 | 1.000000 |
| bollinger | buy | disabled | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| bollinger | sell | disabled | 1 | 1 | 0 | 0 | 0 | 0.007400 | — | 0.007400 | ∞ | 0.000000 | 1.000000 |
| macd | buy | disabled | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| macd | sell | disabled | 1 | 1 | 0 | 0 | 0 | 0.007400 | — | 0.007400 | ∞ | 0.000000 | 1.000000 |
| stochastic | buy | disabled | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| stochastic | sell | disabled | 1 | 1 | 0 | 1 | 0 | 0.007400 | — | 0.007400 | ∞ | 0.000000 | 1.000000 |
| fibonacci | buy | disabled | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| fibonacci | sell | disabled | 1 | 1 | 0 | 0 | 0 | 0.007400 | — | 0.007400 | ∞ | 0.000000 | 1.000000 |
| atr | buy | disabled | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| atr | sell | disabled | 1 | 1 | 0 | 0 | 0 | 0.007400 | — | 0.007400 | ∞ | 0.000000 | 1.000000 |
| dca | buy | disabled | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| dca | sell | disabled | 1 | 1 | 0 | 1 | 0 | 0.007400 | — | 0.007400 | ∞ | 0.000000 | 1.000000 |
| buy_and_hold | buy | disabled | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| buy_and_hold | sell | disabled | 1 | 1 | 0 | 0 | 0 | 0.007400 | — | 0.007400 | ∞ | 0.000000 | 1.000000 |
| orderbook | buy | report-only | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| orderbook | sell | report-only | 1 | 1 | 0 | 1 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| ml_enhanced_orderbook | buy | report-only | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| ml_enhanced_orderbook | sell | report-only | 1 | 1 | 0 | 0 | 0 | 0.007400 | — | 0.007400 | ∞ | 0.000000 | 1.000000 |
| ml | buy | report-only | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| ml | sell | report-only | 1 | 1 | 0 | 0 | 0 | 0.007400 | — | 0.007400 | ∞ | 0.000000 | 1.000000 |
| sma | buy | report-only | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| sma | sell | report-only | 1 | 1 | 0 | 1 | 0 | 0.007400 | — | 0.007400 | ∞ | 0.000000 | 1.000000 |
| ema | buy | report-only | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| ema | sell | report-only | 1 | 1 | 0 | 0 | 0 | 0.007015 | — | 0.007015 | ∞ | 0.000000 | 1.000000 |
| rsi | buy | report-only | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| rsi | sell | report-only | 1 | 1 | 0 | 0 | 0 | 0.007400 | — | 0.007400 | ∞ | 0.000000 | 1.000000 |
| bollinger | buy | report-only | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| bollinger | sell | report-only | 1 | 1 | 0 | 0 | 0 | 0.007400 | — | 0.007400 | ∞ | 0.000000 | 1.000000 |
| macd | buy | report-only | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| macd | sell | report-only | 1 | 1 | 0 | 0 | 0 | 0.007400 | — | 0.007400 | ∞ | 0.000000 | 1.000000 |
| stochastic | buy | report-only | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| stochastic | sell | report-only | 1 | 1 | 0 | 1 | 0 | 0.007400 | — | 0.007400 | ∞ | 0.000000 | 1.000000 |
| fibonacci | buy | report-only | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| fibonacci | sell | report-only | 1 | 1 | 0 | 0 | 0 | 0.007400 | — | 0.007400 | ∞ | 0.000000 | 1.000000 |
| atr | buy | report-only | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| atr | sell | report-only | 1 | 1 | 0 | 0 | 0 | 0.007400 | — | 0.007400 | ∞ | 0.000000 | 1.000000 |
| dca | buy | report-only | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| dca | sell | report-only | 1 | 1 | 0 | 1 | 0 | 0.007400 | — | 0.007400 | ∞ | 0.000000 | 1.000000 |
| buy_and_hold | buy | report-only | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| buy_and_hold | sell | report-only | 1 | 1 | 0 | 0 | 0 | 0.007400 | — | 0.007400 | ∞ | 0.000000 | 1.000000 |
| orderbook | buy | factored | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| orderbook | sell | factored | 1 | 0 | 1 | 1 | 0 | — | — | — | — | — | 0.000000 |
| ml_enhanced_orderbook | buy | factored | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| ml_enhanced_orderbook | sell | factored | 1 | 0 | 1 | 0 | 0 | — | — | — | — | — | 0.000000 |
| ml | buy | factored | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| ml | sell | factored | 1 | 0 | 1 | 0 | 0 | — | — | — | — | — | 0.000000 |
| sma | buy | factored | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| sma | sell | factored | 1 | 0 | 1 | 1 | 0 | — | — | — | — | — | 0.000000 |
| ema | buy | factored | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| ema | sell | factored | 1 | 0 | 1 | 0 | 0 | — | — | — | — | — | 0.000000 |
| rsi | buy | factored | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| rsi | sell | factored | 1 | 0 | 1 | 0 | 0 | — | — | — | — | — | 0.000000 |
| bollinger | buy | factored | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| bollinger | sell | factored | 1 | 0 | 1 | 0 | 0 | — | — | — | — | — | 0.000000 |
| macd | buy | factored | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| macd | sell | factored | 1 | 0 | 1 | 0 | 0 | — | — | — | — | — | 0.000000 |
| stochastic | buy | factored | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| stochastic | sell | factored | 1 | 0 | 1 | 1 | 0 | — | — | — | — | — | 0.000000 |
| fibonacci | buy | factored | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| fibonacci | sell | factored | 1 | 0 | 1 | 0 | 0 | — | — | — | — | — | 0.000000 |
| atr | buy | factored | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| atr | sell | factored | 1 | 0 | 1 | 0 | 0 | — | — | — | — | — | 0.000000 |
| dca | buy | factored | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| dca | sell | factored | 1 | 0 | 1 | 1 | 0 | — | — | — | — | — | 0.000000 |
| buy_and_hold | buy | factored | 1 | 1 | 0 | 0 | 0 | 0.017400 | — | 0.017400 | ∞ | 0.000000 | 1.000000 |
| buy_and_hold | sell | factored | 1 | 0 | 1 | 0 | 0 | — | — | — | — | — | 0.000000 |

## Directional expected return

- disabled buy: 0.017400 (n=13, supported)
- disabled sell: 0.008140 (n=13, supported)
- report-only buy: 0.017400 (n=13, supported)
- report-only sell: 0.008140 (n=13, supported)
- factored buy: 0.017400 (n=13, supported)
- factored sell: — (n=0, sparse)

## Audit

- Coverage: `complete`
- Duplicate row keys: `0`
- Sparse groups: `78`
- Data identifier: `diagnostic_ablation_fixture`
- Seed: `fixed-fixture-v1`
- Offline only: `true`; live orders enabled: `false`

## Meaningful factored changes

- atr sell: blocked delta 1, expectancy 0.007399999999999948 -> None
- bollinger sell: blocked delta 1, expectancy 0.007400000000000021 -> None
- buy_and_hold sell: blocked delta 1, expectancy 0.00740000000000004 -> None
- dca sell: blocked delta 1, expectancy 0.007399999999999995 -> None
- ema sell: blocked delta 1, expectancy 0.007015384615384616 -> None
- fibonacci sell: blocked delta 1, expectancy 0.0074000000000000316 -> None
- macd sell: blocked delta 1, expectancy 0.007399999999999936 -> None
- ml sell: blocked delta 1, expectancy 0.00739999999999996 -> None
- ml_enhanced_orderbook sell: blocked delta 1, expectancy 0.007400000000000051 -> None
- orderbook sell: blocked delta 1, expectancy 0.0174 -> None
- rsi sell: blocked delta 1, expectancy 0.007399999999999973 -> None
- sma sell: blocked delta 1, expectancy 0.007400000000000011 -> None
- stochastic sell: blocked delta 1, expectancy 0.007399999999999985 -> None
