# Simulated Trading Statistics Audit - 2026-08-02

## Scope

This report closes the implementation slice for `TRADE-BL-0001`: audit Simulated Trading statistics calculation accuracy and keep the frontend, backend, and dashboard contracts aligned.

No live orders were placed. No local Docker, CMake, backend, or production build was run. Backend compilation remains gated by exact-SHA GitHub Actions Docker Build Validation after push.

## Source-of-truth formulas

The canonical simulated statistics boundary is `frontend/lib/simulatedTradingStats.ts` for the dashboard and `src/trading/TradingStatsCalculator.cpp` for backend aggregate stats. The two paths now share the same fixed-fixture expectations in tests.

| Metric | Source-of-truth formula / semantics | Guardrail |
| --- | --- | --- |
| `total_pnl` | Sum of trade `pnl` values. | Includes zero-PnL open legs in total trade count but they do not count as wins/losses. |
| `total_fees` | Backend aggregate sums per-trade fees; frontend uses portfolio-level `total_fees` when provided and otherwise sums per-trade fees. | Portfolio-level fees replace per-trade fee sum to avoid double counting. |
| `net_pnl` | `total_pnl - total_fees` for trade-derived stats; portfolio tile net PnL uses `realized_pnl + unrealized_pnl - total_fees`. | Do not add portfolio fees twice. |
| `win_rate` | `winning_trades / (winning_trades + losing_trades) * 100`. | This is a 0-100 percentage; zero-PnL open legs are excluded from the denominator. |
| `winning_trades` / `losing_trades` | Count positive and negative trade `pnl` values. | Zero-PnL open legs count toward `total_trades` only. |
| `avg_win` | Mean positive `pnl`. | Returns 0 when no winners. |
| `avg_loss` | Mean negative `pnl`. | Remains negative; callers should not take absolute value unless explicitly labeling gross loss. |
| `best_trade` / `worst_trade` | Max/min trade `pnl`. | Empty input returns 0. |
| `profit_factor` | Gross positive PnL divided by absolute gross negative PnL. | Returns 999 for profit with no losses, otherwise 0 when undefined/no gross profit. |
| `sharpe_ratio` | Per-trade mean/stddev of trade PnL. | No annualization; this is not a daily return series. |
| `max_drawdown` | Largest peak-to-trough drawdown of cumulative trade PnL in dollars. | Not a percentage. |
| `total_volume` | Sum of `quantity * price`. | Used for average trade size only. |
| `avg_trade_size` | `total_volume / total_trades`. | Zero-quantity open legs remain counted if they are present as trades. |
| `trades_today` | Count trades whose timestamp begins with current UTC day or supplied test day. | Date comparison is UTC string based. |
| `last_trade_time` | Latest non-empty ISO timestamp in the trade set. | Fixed backend calculator so unsorted inputs cannot report an older last trade. |
| `cashBalance` | `cash_balance`, `current_capital`, or `available_balance_usd`. | Uses nullish numeric fallback, preserving legitimate zero values. |
| `totalPositionsValue` | Backend `total_positions_value`, or signed current notional from open positions. | Short positions are negative so `Total Value = Cash + Positions Value` holds. |
| `totalValue` | Backend `total_value`, or `cashBalance + totalPositionsValue`. | Keeps portfolio tiles internally consistent. |
| `activePositions` | Backend open-position count fields, falling back to normalized positions length. | Display count is not derived from trade count. |
| `recentTrades` | Merge of `recent_trades` and `trades`, de-duped by trade id/fallback key, sorted by newest timestamp, capped to the dashboard recent-trades display. | Recent table display cap does not change aggregate statistics. |

## Code paths audited

- `frontend/lib/simulatedTradingStats.ts` normalizes several backend/local fallback snapshot shapes and derives stats when backend stats are absent.
- `frontend/components/dashboard/SimulatedTradingPanel.tsx` consumes the normalized snapshot for Simulated Trading tiles, metrics, positions, and recent trades.
- `frontend/lib/api.ts` local simulated fallback maintains portfolio cash, realized/unrealized PnL, total fees, total value, net PnL, positions, and trade rows used by the normalizer.
- `src/trading/TradingStatsCalculator.cpp` computes backend aggregate stats and is exercised by `src/tests/test_trading_stats_calculator.cpp`.
- `src/trading/TradingStatsService.cpp` reads `individual_trades` ordered by timestamp before passing rows to the shared calculator.

## Implementation notes

- Added a comprehensive frontend fixture test that asserts total PnL, fees, net PnL, win rate, average win/loss, best/worst trade, profit factor, Sharpe, drawdown, volume, average trade size, last trade time, cash, positions value, total value, and portfolio net PnL.
- Updated backend calculator behavior so `last_trade_time` is the latest non-empty ISO timestamp, not merely the final input row. This keeps the backend robust even when callers supply unsorted fixtures or runtime snapshots.
- Extended backend calculator fixture expectations to cover zero-PnL open legs, per-trade Sharpe including open legs, and latest timestamp behavior.

## Remaining boundaries

- This slice does not add a new live data replay harness or database integration test. Those broader runtime verification paths remain better scoped to `TRADE-BL-0011` and live/sim parity items.
- This slice does not change live trading order placement, execution blockers, account management, or strategy decision logic.
- Remote Docker Build Validation is the required compile/build gate for the backend changes.
