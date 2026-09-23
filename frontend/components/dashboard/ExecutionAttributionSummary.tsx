'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import {
  AttributionDimensionRow,
  AttributionRow,
  ExecutionAttributionReport,
} from '@/lib/executionAttribution';

const displayNumber = (value: number): string => value.toLocaleString();

const displayRate = (value: number | null): string =>
  value === null ? '—' : `${value.toFixed(1)}%`;

const displayPnl = (value: number | null): string => (value === null ? '—' : value.toFixed(4));

const DIMENSION_LABELS: Record<string, string> = {
  by_symbol: 'By symbol',
  by_side: 'By side',
  by_strength_bucket: 'By strength bucket',
  by_expected_return_bucket: 'By expected-return bucket',
};

function DimensionTable({
  rows,
  label,
}: {
  rows: Record<string, AttributionDimensionRow>;
  label: string;
}) {
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
                <td className="px-2 py-1">{displayNumber(row.blockedIntents)}</td>
                <td className="px-2 py-1">{displayNumber(row.explicitSkips)}</td>
                <td className="px-2 py-1">{displayNumber(row.executedCount)}</td>
                <td className="px-2 py-1">{displayRate(row.winRatePct)}</td>
                <td className="px-2 py-1">{displayPnl(row.averageRealizedPnl)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CountTable({ counts, label }: { counts: Record<string, number>; label: string }) {
  const entries = Object.entries(counts || {});
  if (entries.length === 0) return null;
  return (
    <div className="rounded border border-gray-100 px-3 py-2">
      <h5 className="text-xs font-semibold uppercase tracking-wide text-gray-600">{label}</h5>
      <ul className="mt-1 space-y-1 text-xs text-gray-700">
        {entries.map(([reason, count]) => (
          <li key={reason} className="flex justify-between gap-2">
            <span>{reason}</span>
            <span className="whitespace-nowrap">{displayNumber(count)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function SummaryRow({ row }: { row: AttributionRow }) {
  return (
    <div className="grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
      <span>Evaluated: <strong>{displayNumber(row.evaluated)}</strong></span>
      <span>Generated: <strong>{displayNumber(row.signalsGenerated)}</strong></span>
      <span>Executed: <strong>{displayNumber(row.executedCount)}</strong></span>
      <span>Blocked: <strong>{displayNumber(row.blockedIntents)}</strong></span>
      <span>Explicit skips: <strong>{displayNumber(row.explicitSkips)}</strong></span>
      <span>Win rate: <strong>{displayRate(row.winRatePct)}</strong></span>
      <span>Avg win: <strong>{displayPnl(row.averageWinPnl)}</strong></span>
      <span>Avg loss magnitude: <strong>{displayPnl(row.averageLossMagnitude)}</strong></span>
    </div>
  );
}

type Props = {
  report: ExecutionAttributionReport | null;
  title: string;
  isLoading?: boolean;
  error?: Error | null;
};

// Execution attribution is a read-only, `report`-classified diagnostic
// (docs/STRATEGY_OBJECTIVE.md): it never gates, sizes, or affects execution,
// and missing outcome evidence is rendered as "—", never as a fabricated 0.
export default function ExecutionAttributionSummary({ report, title, isLoading, error }: Props) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-gray-500">Loading execution attribution…</p>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-red-600">Execution attribution unavailable. Try refreshing this panel.</p>
        </CardContent>
      </Card>
    );
  }

  const strategies = report?.byStrategy ?? [];
  const factors = report?.byDiagnosticFactor ?? [];
  const overall = report?.overall;
  const hasRows = strategies.length > 0 || factors.length > 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {!hasRows && (
          <p className="text-sm text-gray-500">No attribution data is available for this runtime window.</p>
        )}
        {report && (!report.coverageComplete || report.signalRowsTruncated) && (
          <p className="rounded bg-amber-50 p-2 text-xs text-amber-800">
            Partial coverage: totals may not explain every observed signal. Refresh or narrow the runtime window.
          </p>
        )}
        {report?.warning && <p className="text-xs text-amber-700">{report.warning}</p>}
        {report && (report.sessionId || report.tradeType || report.bucketPolicyVersion) && (
          <p className="text-xs text-gray-500">
            Scope: {report.sessionId || 'unknown session'} · {report.tradeType || 'unknown mode'}
            {report.bucketPolicyVersion ? ` · bucket policy ${report.bucketPolicyVersion}` : ''}
          </p>
        )}
        {overall && <SummaryRow row={overall} />}
        {strategies.map((row) => (
          <section key={row.key} className="space-y-3 rounded border border-gray-200 p-3">
            <h4 className="font-semibold text-gray-800">{row.key}</h4>
            <SummaryRow row={row} />
            <CountTable counts={row.blockerCounts} label="Execution-policy blockers" />
            <CountTable counts={row.diagnosticFactorCounts} label="Signal-quality diagnostics" />
            {Object.entries(row.dimensions).map(([dimension, values]) => (
              <DimensionTable
                key={dimension}
                rows={values}
                label={DIMENSION_LABELS[dimension] || `By ${dimension.replace(/^by_/, '').replaceAll('_', ' ')}`}
              />
            ))}
          </section>
        ))}
        {factors.length > 0 && (
          <div className="space-y-2">
            <h5 className="text-sm font-semibold text-gray-700">Diagnostic-factor impact</h5>
            <p className="text-xs text-gray-500">
              A diagnostic factor only ever explains a blocked intent, so it never carries a win rate or
              realized-P&amp;L population.
            </p>
            <div className="overflow-x-auto">
              <table className="min-w-full text-xs">
                <thead className="bg-gray-50 text-left text-gray-500">
                  <tr>
                    <th className="px-2 py-1">Factor</th>
                    <th className="px-2 py-1">Evaluated</th>
                    <th className="px-2 py-1">Blocked</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {factors.map((row) => (
                    <tr key={row.key}>
                      <td className="px-2 py-1 font-medium">{row.key || 'unknown'}</td>
                      <td className="px-2 py-1">{displayNumber(row.evaluated)}</td>
                      <td className="px-2 py-1">{displayNumber(row.blockedIntents)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
