'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';

export interface AttributionRow {
  strategy?: string;
  factor?: string;
  key?: string;
  evaluated?: number;
  signals_generated?: number;
  explicit_skips?: number;
  executable_intents?: number;
  blocked_intents?: number;
  executed_count?: number;
  impact_population?: number;
  pnl_population?: number;
  win_count?: number;
  loss_count?: number;
  win_rate_pct?: number | null;
  average_realized_pnl?: number | null;
  average_win_pnl?: number | null;
  average_loss_magnitude?: number | null;
  outcome_coverage?: number | null;
  insufficient_data?: boolean;
  blocker_counts?: Record<string, number>;
  diagnostic_factor_counts?: Record<string, number>;
  dimensions?: Record<string, Record<string, AttributionRow>>;
}

export interface ExecutionAttributionReport {
  contract_version?: number;
  session_id?: string;
  trade_type?: string;
  coverage_complete?: boolean;
  signal_rows?: number;
  outcome_rows?: number;
  signal_rows_truncated?: boolean;
  bucket_policy_version?: string;
  warning?: string;
  by_strategy?: AttributionRow[];
  by_diagnostic_factor?: AttributionRow[];
  overall?: AttributionRow;
}

type Props = {
  report?: ExecutionAttributionReport | null;
  title: string;
};

const numberValue = (value: unknown): number =>
  typeof value === 'number' && Number.isFinite(value) ? value : 0;

const displayNumber = (value: unknown): string => numberValue(value).toLocaleString();

const displayRate = (value: unknown): string =>
  typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(1)}%` : '—';

const displayPnl = (value: unknown): string =>
  typeof value === 'number' && Number.isFinite(value) ? value.toFixed(4) : '—';

function MetricTable({ rows, label }: { rows: Record<string, AttributionRow>; label: string }) {
  const entries = Object.entries(rows || {});
  if (entries.length === 0) return null;

  return (
    <div className="space-y-2">
      <h5 className="text-sm font-semibold text-gray-700">{label}</h5>
      <div className="overflow-x-auto">
        <table className="min-w-full text-xs">
          <thead className="bg-gray-50 text-left text-gray-500">
            <tr>
              <th className="px-2 py-1">Bucket</th>
              <th className="px-2 py-1">Evaluated</th>
              <th className="px-2 py-1">Blocked</th>
              <th className="px-2 py-1">Skipped</th>
              <th className="px-2 py-1">Executed</th>
              <th className="px-2 py-1">Win rate</th>
              <th className="px-2 py-1">Avg net P&amp;L</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {entries.map(([key, row]) => (
              <tr key={key}>
                <td className="px-2 py-1 font-medium">{key || 'unknown'}</td>
                <td className="px-2 py-1">{displayNumber(row.evaluated)}</td>
                <td className="px-2 py-1">{displayNumber(row.blocked_intents)}</td>
                <td className="px-2 py-1">{displayNumber(row.explicit_skips)}</td>
                <td className="px-2 py-1">{displayNumber(row.executed_count)}</td>
                <td className="px-2 py-1">{displayRate(row.win_rate_pct)}</td>
                <td className="px-2 py-1">{displayPnl(row.average_realized_pnl)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SummaryRow({ row }: { row: AttributionRow }) {
  return (
    <div className="grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
      <span>Evaluated: <strong>{displayNumber(row.evaluated)}</strong></span>
      <span>Generated: <strong>{displayNumber(row.signals_generated)}</strong></span>
      <span>Executed: <strong>{displayNumber(row.executed_count)}</strong></span>
      <span>Blocked: <strong>{displayNumber(row.blocked_intents)}</strong></span>
      <span>Explicit skips: <strong>{displayNumber(row.explicit_skips)}</strong></span>
      <span>Win rate: <strong>{displayRate(row.win_rate_pct)}</strong></span>
      <span>Avg win: <strong>{displayPnl(row.average_win_pnl)}</strong></span>
      <span>Avg loss magnitude: <strong>{displayPnl(row.average_loss_magnitude)}</strong></span>
    </div>
  );
}

export default function ExecutionAttributionSummary({ report, title }: Props) {
  const strategies = Array.isArray(report?.by_strategy) ? report!.by_strategy! : [];
  const factors = Array.isArray(report?.by_diagnostic_factor) ? report!.by_diagnostic_factor! : [];
  const overall = report?.overall;
  const hasRows = strategies.length > 0 || factors.length > 0 || !!overall;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {!hasRows && <p className="text-sm text-gray-500">No attribution data is available for this runtime window.</p>}
        {report && (report.coverage_complete === false || report.signal_rows_truncated) && (
          <p className="rounded bg-amber-50 p-2 text-xs text-amber-800">
            Partial coverage: totals may not explain every observed signal. Refresh or narrow the runtime window.
          </p>
        )}
        {report?.warning && <p className="text-xs text-amber-700">{report.warning}</p>}
        {report && (report.session_id || report.trade_type || report.bucket_policy_version) && (
          <p className="text-xs text-gray-500">
            Scope: {report.session_id || 'unknown session'} · {report.trade_type || 'unknown mode'}
            {report.bucket_policy_version ? ` · bucket policy ${report.bucket_policy_version}` : ''}
          </p>
        )}
        {overall && <SummaryRow row={overall} />}
        {strategies.map((row, index) => {
          const strategy = row.strategy || 'unknown';
          const dimensions = row.dimensions || {};
          return (
            <section key={`${strategy}-${index}`} className="space-y-3 rounded border border-gray-200 p-3">
              <h4 className="font-semibold text-gray-800">{strategy}</h4>
              <SummaryRow row={row} />
              {row.blocker_counts && <MetricTable rows={Object.fromEntries(Object.entries(row.blocker_counts).map(([key, value]) => [key, { evaluated: value, blocked_intents: value }]))} label="Execution-policy blockers" />}
              {row.diagnostic_factor_counts && <MetricTable rows={Object.fromEntries(Object.entries(row.diagnostic_factor_counts).map(([key, value]) => [key, { evaluated: value, blocked_intents: value }]))} label="Signal-quality diagnostics" />}
              {Object.entries(dimensions).map(([dimension, values]) => (
                <MetricTable key={dimension} rows={values} label={`By ${dimension.replaceAll('_', ' ')}`} />
              ))}
            </section>
          );
        })}
        {factors.length > 0 && (
          <MetricTable
            label="Diagnostic-factor impact"
            rows={Object.fromEntries(factors.map((row, index) => [row.factor || `unknown-${index}`, row]))}
          />
        )}
      </CardContent>
    </Card>
  );
}
