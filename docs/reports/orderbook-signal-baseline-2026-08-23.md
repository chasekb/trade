# Order-book signal baseline — TRADE-BL-0008

Snapshot: 2026-08-23T03:53:55Z (UTC)
Database: local `trade_db_1` PostgreSQL 15, database `trading_db`
Window: trailing 1 hour at query execution; signal cap 200,000 rows
Scope: `order_book_signals` plus closing legs from `individual_trades`

## Reproducible command

From the trade worktree, with the read-only project database available:

```bash
mkdir -p artifacts
podman exec -i trade_db_1 psql -q \
  -v hours=1 -v max_signals=200000 \
  -U trading_user -d trading_db \
  -f - < scripts/orderbook_signal_baseline.sql \
  > artifacts/orderbook-signal-baseline-1h.csv
python scripts/summarize_orderbook_baseline.py
```

The SQL is the canonical query. It can be run against another PostgreSQL connection by replacing the `podman exec ... psql` wrapper. `hours` is bounded by the caller; `max_signals` prevents an unbounded materialization. The query is read-only and does not start, stop, size, or submit trading.

## Observed result

The generated artifact is `artifacts/orderbook-signal-baseline-1h.csv` (398 symbol/strategy/model groups plus the header).

| Measure | Result |
|---|---:|
| Symbols/groups | 398 |
| Signals evaluated | 15,519 |
| Signals generated | 5,990 |
| Executable intents | 0 |
| Blocked intents | 5,990 |
| Blocked intent rate | 100.000% of generated signals |
| Intent conversion | 0.000% |
| Weighted average signal strength | 0.227069 |
| Weighted average expected return | 0.117118 |
| Weighted average fee-adjusted expected return | 0.321068 |
| Closing legs in window | 0 |
| Realized PnL / expectancy | unavailable (no closing legs) |
| Average win / average loss | unavailable (no closing legs) |
| Profit factor | unavailable (no closing legs) |
| Drawdown | 0.0 in this window; no realized equity observations |

The signal data explicitly identifies all 1-hour rows as `live_parity` (14,723 rows in a separate coverage query). The remaining 796 rows in the bounded baseline have no explicit trade-type marker in their stored JSON and are retained as legacy/unknown rather than guessed into live or simulated. No live or synthetic-simulated signal rows were explicitly identified in this 1-hour window.

The table contains older trade outcomes, but none fall in the 1-hour outcome window. A 30-day trade-type inventory observed `live` (129 rows), `live_account_managed_close` (7), `live_liquidation` (6), `live_parity` (2,321), and `simulated` (173,266) trade rows; those older outcomes are not silently mixed into this recent baseline.

## Grouping and metric contract

Rows are grouped by `symbol`, strategy from `execution_analysis.strategy` (falling back to `signal_type`), and model branch. Model branch uses the first non-empty value among `model_branch`, `model_id`, `model_name`, and `model_type`; current rows expose none of these, so the artifact reports `unknown`. Closing-leg outcomes are grouped through the nearest same-symbol signal no more than 300 seconds before the trade; if no model branch can be attributed, they use `unattributed_trade`.

- Signal strength, expected return, and fee-adjusted expected return are averages over the group; expected-return averages use generated signals.
- Generated signals use `execution_analysis.signal_generated`, falling back to `signal_type <> 'hold'`.
- Executable intents use `execution_analysis.executable_intent`; blocked intents are generated but not executable.
- Blocked intent rate is blocked/generated. Intent conversion is executable/generated.
- Realized PnL is `COALESCE(pnl, 0) - COALESCE(fees, 0)` for closing legs. This preserves the project's after-fee objective and excludes opening legs.
- Average loss is reported as a positive magnitude. Expectancy is mean net realized PnL per closing leg. Profit factor is gross winning PnL divided by absolute gross losing PnL.
- Drawdown is the maximum peak-to-trough decline of cumulative net realized PnL within each group, in dollars.

## Data sources and filtering

1. `order_book_signals`: signal timestamp is epoch seconds; JSON `signal_data.execution_analysis` supplies execution attribution and model fields.
2. `individual_trades`: trade timestamp is epoch seconds; `is_closing_leg` is preferred, with the historical fallback `pnl <> 0` for rows where the flag is null.
3. Time filter is `timestamp >= extract(epoch FROM now() - (:hours || ' hours')::interval)`.
4. Signals are ordered newest first and capped at `max_signals`; a capped run is a deliberate bounded sample and should be called out in its report metadata.
5. Null or malformed attribution is preserved as `unknown`; no missing model branch, trade type, or outcome is imputed.
6. No production parameters or code paths were changed, and no live account mutation was performed.

## Limitations and next evidence

This snapshot is a blocker/coverage baseline, not a profitability claim. It has no recent closing outcomes, no explicit model-branch metadata, and no explicit live/synthetic-simulated signal populations in the trailing hour. TRADE-BL-0008 still needs a representative runtime window that emits explicit trade type and model branch on every signal and captures subsequent closing legs. The artifact is suitable for identifying the current zero-intent/zero-outcome condition without treating missing data as zero performance.
