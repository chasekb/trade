\pset pager off
\pset footer off
\pset format csv
\pset tuples_only off
\set ON_ERROR_STOP on
\if :{?hours}
\else
\set hours 1
\endif
\if :{?max_signals}
\else
\set max_signals 200000
\endif

WITH signal_rows AS MATERIALIZED (
  SELECT
    s.symbol,
    s.timestamp,
    COALESCE(NULLIF(payload.a->>'strategy', ''), NULLIF(s.signal_type, ''), 'unknown') AS strategy,
    COALESCE(NULLIF(payload.a->>'model_branch', ''), NULLIF(payload.a->>'model_id', ''),
             NULLIF(payload.a->>'model_name', ''), NULLIF(payload.a->>'model_type', ''),
             'unknown') AS model_branch,
    COALESCE(NULLIF(payload.a->>'signal_strength', '')::double precision, s.strength, 0.0) AS signal_strength,
    COALESCE(NULLIF(payload.a->>'expected_return', '')::double precision, 0.0) AS expected_return,
    COALESCE(NULLIF(payload.a->>'fee_adjusted_expected_return', '')::double precision, 0.0) AS fee_adjusted_expected_return,
    COALESCE((payload.a->>'signal_generated')::boolean, s.signal_type <> 'hold') AS signal_generated,
    COALESCE((payload.a->>'executable_intent')::boolean, false) AS executable_intent,
    payload.a->>'blocker_reason' AS blocker_reason
  FROM order_book_signals s
  CROSS JOIN LATERAL (SELECT s.signal_data::jsonb -> 'execution_analysis' AS a) payload
  WHERE s.timestamp >= extract(epoch FROM now() - (:hours || ' hours')::interval)
  ORDER BY s.timestamp DESC
  LIMIT :max_signals
),
signal_metrics AS (
  SELECT
    symbol, strategy, model_branch,
    count(*)::bigint AS signals_evaluated,
    count(*) FILTER (WHERE signal_generated)::bigint AS signals_generated,
    count(*) FILTER (WHERE executable_intent)::bigint AS executable_intents,
    count(*) FILTER (WHERE signal_generated AND NOT executable_intent)::bigint AS blocked_intents,
    round(avg(signal_strength)::numeric, 10) AS avg_signal_strength,
    round(avg(expected_return) FILTER (WHERE signal_generated)::numeric, 10) AS avg_expected_return,
    round(avg(fee_adjusted_expected_return) FILTER (WHERE signal_generated)::numeric, 10) AS avg_fee_adjusted_expected_return,
    round((count(*) FILTER (WHERE signal_generated AND NOT executable_intent)::numeric /
      NULLIF(count(*) FILTER (WHERE signal_generated), 0)) * 100, 6) AS blocked_intent_rate_pct,
    round((count(*) FILTER (WHERE executable_intent)::numeric /
      NULLIF(count(*) FILTER (WHERE signal_generated), 0)) * 100, 6) AS intent_conversion_rate_pct
  FROM signal_rows
  GROUP BY 1,2,3
),
trade_rows AS MATERIALIZED (
  SELECT
    t.symbol,
    COALESCE(NULLIF(t.strategy_type, ''), 'unknown') AS strategy,
    COALESCE(NULLIF(sa.model_branch, ''), 'unattributed_trade') AS model_branch,
    t.timestamp,
    COALESCE(t.pnl, 0.0) - COALESCE(t.fees, 0.0) AS realized_pnl
  FROM individual_trades t
  LEFT JOIN LATERAL (
    SELECT COALESCE(NULLIF(payload.a->>'model_branch', ''), NULLIF(payload.a->>'model_id', ''),
                    NULLIF(payload.a->>'model_name', ''), NULLIF(payload.a->>'model_type', '')) AS model_branch
    FROM order_book_signals s
    CROSS JOIN LATERAL (SELECT s.signal_data::jsonb -> 'execution_analysis' AS a) payload
    WHERE s.symbol = t.symbol
      AND s.timestamp <= t.timestamp
      AND s.timestamp >= t.timestamp - 300
    ORDER BY s.timestamp DESC
    LIMIT 1
  ) sa ON true
  WHERE t.timestamp >= extract(epoch FROM now() - (:hours || ' hours')::interval)
    AND COALESCE(t.is_closing_leg, COALESCE(t.pnl, 0.0) <> 0.0)
),
trade_with_equity AS (
  SELECT tr.*, sum(realized_pnl) OVER (PARTITION BY symbol, strategy, model_branch ORDER BY timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS equity
  FROM trade_rows tr
),
trade_with_drawdown AS (
  SELECT twe.*,
    max(equity) OVER (PARTITION BY symbol, strategy, model_branch ORDER BY timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) - equity AS drawdown_value
  FROM trade_with_equity twe
),
trade_metrics AS (
  SELECT
    symbol, strategy, model_branch,
    count(*)::bigint AS closing_legs,
    round(sum(realized_pnl)::numeric, 10) AS realized_pnl,
    round(avg(realized_pnl) FILTER (WHERE realized_pnl > 0)::numeric, 10) AS average_win,
    round(abs(avg(realized_pnl) FILTER (WHERE realized_pnl < 0))::numeric, 10) AS average_loss,
    round(avg(realized_pnl)::numeric, 10) AS expectancy,
    round((sum(realized_pnl) FILTER (WHERE realized_pnl > 0) /
      NULLIF(abs(sum(realized_pnl) FILTER (WHERE realized_pnl < 0)), 0))::numeric, 10) AS profit_factor,
    round(max(drawdown_value)::numeric, 10) AS drawdown,
    count(*) FILTER (WHERE realized_pnl > 0)::bigint AS winners,
    count(*) FILTER (WHERE realized_pnl < 0)::bigint AS losers
  FROM trade_with_drawdown
  GROUP BY 1,2,3
),
keys AS (
  SELECT symbol, strategy, model_branch FROM signal_metrics
  UNION
  SELECT symbol, strategy, model_branch FROM trade_metrics
)
SELECT
  k.symbol,
  k.strategy,
  k.model_branch,
  COALESCE(sm.signals_evaluated, 0) AS signals_evaluated,
  COALESCE(sm.signals_generated, 0) AS signals_generated,
  COALESCE(sm.executable_intents, 0) AS executable_intents,
  COALESCE(sm.blocked_intents, 0) AS blocked_intents,
  sm.avg_signal_strength,
  sm.avg_expected_return,
  sm.avg_fee_adjusted_expected_return,
  COALESCE(tm.realized_pnl, 0.0) AS realized_pnl,
  tm.average_win,
  tm.average_loss,
  tm.expectancy,
  tm.profit_factor,
  COALESCE(tm.drawdown, 0.0) AS drawdown,
  COALESCE(tm.closing_legs, 0) AS closing_legs,
  sm.blocked_intent_rate_pct,
  sm.intent_conversion_rate_pct,
  COALESCE(tm.winners, 0) AS winners,
  COALESCE(tm.losers, 0) AS losers
FROM keys k
LEFT JOIN signal_metrics sm USING (symbol, strategy, model_branch)
LEFT JOIN trade_metrics tm USING (symbol, strategy, model_branch)
ORDER BY k.symbol, k.strategy, k.model_branch;
