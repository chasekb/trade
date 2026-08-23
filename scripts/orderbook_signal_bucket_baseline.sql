\pset pager off
\pset footer off
\pset format csv
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
    COALESCE(NULLIF(payload.a->>'strategy', ''), NULLIF(s.signal_type, ''), 'unknown') AS strategy,
    COALESCE(NULLIF(payload.a->>'model_branch', ''), NULLIF(payload.a->>'model_id', ''),
             NULLIF(payload.a->>'model_name', ''), NULLIF(payload.a->>'model_type', ''), 'unknown') AS model_branch,
    COALESCE(NULLIF(payload.a->>'signal_strength', '')::double precision, s.strength) AS signal_strength,
    NULLIF(payload.a->>'expected_return', '')::double precision AS expected_return,
    NULLIF(payload.a->>'fee_adjusted_expected_return', '')::double precision AS fee_adjusted_expected_return,
    COALESCE((payload.a->>'signal_generated')::boolean, s.signal_type <> 'hold') AS signal_generated,
    COALESCE((payload.a->>'executable_intent')::boolean, false) AS executable_intent
  FROM order_book_signals s
  CROSS JOIN LATERAL (SELECT s.signal_data::jsonb -> 'execution_analysis' AS a) payload
  WHERE s.timestamp >= extract(epoch FROM now() - (:hours || ' hours')::interval)
  ORDER BY s.timestamp DESC
  LIMIT :max_signals
), bucketed AS (
  SELECT *,
    CASE
      WHEN signal_strength < 0.10 THEN '<0.10'
      WHEN signal_strength < 0.25 THEN '0.10-<0.25'
      WHEN signal_strength < 0.50 THEN '0.25-<0.50'
      WHEN signal_strength < 0.75 THEN '0.50-<0.75'
      WHEN signal_strength >= 0.75 THEN '>=0.75'
      ELSE 'unknown'
    END AS signal_strength_bucket,
    CASE
      WHEN expected_return < 0 THEN '<0'
      WHEN expected_return < 0.10 THEN '0-<0.10'
      WHEN expected_return < 0.25 THEN '0.10-<0.25'
      WHEN expected_return < 0.50 THEN '0.25-<0.50'
      WHEN expected_return >= 0.50 THEN '>=0.50'
      ELSE 'unknown'
    END AS expected_return_bucket,
    CASE
      WHEN fee_adjusted_expected_return < 0 THEN '<0'
      WHEN fee_adjusted_expected_return < 0.10 THEN '0-<0.10'
      WHEN fee_adjusted_expected_return < 0.25 THEN '0.10-<0.25'
      WHEN fee_adjusted_expected_return < 0.50 THEN '0.25-<0.50'
      WHEN fee_adjusted_expected_return >= 0.50 THEN '>=0.50'
      ELSE 'unknown'
    END AS fee_adjusted_expected_return_bucket
  FROM signal_rows
)
SELECT
  symbol,
  strategy,
  model_branch,
  signal_strength_bucket,
  expected_return_bucket,
  fee_adjusted_expected_return_bucket,
  count(*)::bigint AS signals_evaluated,
  count(*) FILTER (WHERE signal_generated)::bigint AS signals_generated,
  count(*) FILTER (WHERE executable_intent)::bigint AS executable_intents,
  count(*) FILTER (WHERE signal_generated AND NOT executable_intent)::bigint AS blocked_intents,
  round(avg(signal_strength)::numeric, 10) AS avg_signal_strength,
  round(avg(expected_return) FILTER (WHERE signal_generated)::numeric, 10) AS avg_expected_return,
  round(avg(fee_adjusted_expected_return) FILTER (WHERE signal_generated)::numeric, 10) AS avg_fee_adjusted_expected_return,
  round((count(*) FILTER (WHERE signal_generated AND NOT executable_intent)::numeric /
    NULLIF(count(*) FILTER (WHERE signal_generated), 0)) * 100, 6) AS blocked_intent_rate_pct
FROM bucketed
GROUP BY 1,2,3,4,5,6
ORDER BY 1,2,3,4,5,6;
