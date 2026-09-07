import React from 'react';
import {
  ExecutionReconciliationSnapshot,
  StrategyReconciliation,
  formatBlockerMix,
  rankStrategiesByExpectancyRisk,
} from '@/lib/executionReconciliation';

const formatUsd = (value: number) => `${value < 0 ? '-' : ''}$${Math.abs(value).toFixed(2)}`;
const formatPercent = (fraction: number) => `${(fraction * 100).toFixed(1)}%`;

const formatProfitFactor = (row: StrategyReconciliation) => {
  if (row.profitFactorUndefined) return 'n/a (no losses)';
  if (row.closingLegs === 0) return '—';
  return row.profitFactor.toFixed(2);
};

const unavailableDimensions = ['Symbol', 'Side', 'Diagnostic factor', 'Strength bucket', 'Expected-return bucket'];
const qualityBlockerPattern = /(signal|strength|expected.?return|insufficient.?history|warming|rejected.?input|low.?activity|imbalance|ml|profitability|no.?trade)/i;
const classifyBlocker = (reason: string): 'Signal quality' | 'Execution policy / account / exchange' =>
  qualityBlockerPattern.test(reason) ? 'Signal quality' : 'Execution policy / account / exchange';

// Signal-to-outcome reconciliation is read-only: eligible intents are not
// presented as fills, and unavailable persisted dimensions are not fabricated.
export function ExecutionReconciliationTable({
  reconciliation,
  isLoading,
  error,
  modeLabel = 'Filtered execution mode',
}: {
  reconciliation: ExecutionReconciliationSnapshot | null;
  isLoading?: boolean;
  error?: Error | null;
  modeLabel?: string;
}) {
  if (isLoading) {
    return <div className="bg-white rounded-lg shadow p-4 text-sm text-gray-500">Loading execution reconciliation…</div>;
  }

  if (error) {
    return <div className="bg-white rounded-lg shadow p-4 text-sm text-red-600">Execution reconciliation unavailable. Try refreshing this panel.</div>;
  }

  if (!reconciliation) return null;

  const rows = rankStrategiesByExpectancyRisk(reconciliation.byStrategy);
  const { overall } = reconciliation;
  const notGenerated = Math.max(overall.signalsEvaluated - overall.signalsGenerated, 0);
  const blockerGroups = reconciliation.byStrategy.flatMap((strategy) =>
    strategy.blockers.map((blocker) => ({ ...blocker, category: classifyBlocker(blocker.reason) })),
  );

  return (
    <div className="bg-white rounded-lg shadow p-4 space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-base font-semibold text-gray-900">Execution reconciliation</h3>
        <span className="text-xs text-gray-500">
          {modeLabel} · trailing {reconciliation.windowHours}h · {reconciliation.signalRows} signal rows · {reconciliation.outcomeRows} outcome rows
        </span>
      </div>

      <p className="text-xs text-gray-600">
        Eligible intents are not proof of submission; realized closing outcomes are the only execution evidence available here.
      </p>

      {reconciliation.error && <p className="text-xs text-red-600">Partial data is available; some backend fields were unavailable.</p>}
      {reconciliation.signalRowsTruncated && (
        <p className="text-xs text-amber-600">Signal rows were truncated by the query limit; blocker shares cover recent rows only.</p>
      )}
      {overall.outcomesUnexplained && (
        <p className="text-xs text-amber-600">Some outcomes are not explained by the filtered signal window.</p>
      )}
      {overall.outcomeCoverage !== 1 && (
        <p className="text-xs text-amber-600">
          Runtime reconciliation coverage: {formatPercent(overall.outcomeCoverage)}; signal and outcome rows do not fully reconcile.
        </p>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Metric label="Generated signals" value={String(overall.signalsGenerated)} />
        <Metric label="Hold / skip unresolved" value={`${notGenerated} (not explicit)`} />
        <Metric label="Eligible intents (not fills)" value={`${overall.executableIntents} (${formatPercent(overall.intentConversionRate)})`} />
        <Metric label="Blocked intents" value={String(overall.blockedIntents)} />
        <Metric label="Realized closing outcomes" value={String(overall.closingLegs)} />
        <Metric label="Expectancy / trade" value={overall.closingLegs > 0 ? formatUsd(overall.expectancy) : '—'} negative={overall.negativeExpectancyFlag} />
      </div>

      {rows.length === 0 ? (
        <p className="text-sm text-gray-500">No signals or outcomes recorded in this window.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead><tr className="text-left text-xs uppercase tracking-wide text-gray-500">
              <th className="px-2 py-2">Strategy</th><th className="px-2 py-2">Signals</th><th className="px-2 py-2">Intents</th><th className="px-2 py-2">Blocked</th><th className="px-2 py-2">Closed</th><th className="px-2 py-2">Win rate</th><th className="px-2 py-2">Avg win</th><th className="px-2 py-2">Avg loss</th><th className="px-2 py-2">Expectancy</th><th className="px-2 py-2">Profit factor</th><th className="px-2 py-2">Net PnL</th><th className="px-2 py-2">Blocker mix</th>
            </tr></thead>
            <tbody>{rows.map((row) => (
              <tr key={row.strategy} className="border-t border-gray-100">
                <td className="px-2 py-2 font-medium text-gray-900">{row.strategy}</td><td className="px-2 py-2">{row.signalsGenerated}</td><td className="px-2 py-2">{row.executableIntents}</td><td className="px-2 py-2">{row.blockedIntents}</td><td className="px-2 py-2">{row.closingLegs}</td>
                <td className="px-2 py-2">{row.winners + row.losers > 0 ? `${row.winRate.toFixed(1)}%` : '—'}</td><td className="px-2 py-2 text-green-700">{formatUsd(row.averageWin)}</td><td className="px-2 py-2 text-red-700">{formatUsd(row.averageLoss)}</td>
                <td className={`px-2 py-2 ${row.negativeExpectancyFlag ? 'text-red-700' : 'text-gray-900'}`}>{row.closingLegs > 0 ? formatUsd(row.expectancy) : '—'}</td><td className="px-2 py-2">{formatProfitFactor(row)}</td><td className={`px-2 py-2 ${row.totalPnl < 0 ? 'text-red-700' : 'text-gray-900'}`}>{formatUsd(row.totalPnl)}</td><td className="px-2 py-2 text-xs text-gray-600">{formatBlockerMix(row)}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        <DiagnosticGroup title="Signal-quality blockers" blockers={blockerGroups.filter((b) => b.category === 'Signal quality')} />
        <DiagnosticGroup title="Execution policy / account / exchange blockers" blockers={blockerGroups.filter((b) => b.category === 'Execution policy / account / exchange')} />
      </div>

      <div className="rounded border border-dashed border-gray-200 bg-gray-50 px-3 py-2 text-xs text-gray-600">
        <span className="font-semibold text-gray-700">Unavailable from reconciliation endpoint:</span>{' '}
        {unavailableDimensions.join(', ')}. Explicit skipped status and submitted/filled counts are also unavailable; do not infer them from eligible intents.
      </div>
    </div>
  );
}

function DiagnosticGroup({ title, blockers }: { title: string; blockers: Array<ExecutionReconciliationSnapshot['overall']['blockers'][number] & { category: string }> }) {
  return (
    <div className="rounded border border-gray-100 px-3 py-2">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-600">{title}</h4>
      {blockers.length === 0 ? <p className="mt-1 text-xs text-gray-500">No buckets returned.</p> : (
        <ul className="mt-1 space-y-1 text-xs text-gray-700">{blockers.map((blocker, index) => (
          <li key={`${blocker.reason}-${index}`} className="flex justify-between gap-2"><span>{blocker.reason}</span><span className="whitespace-nowrap">{blocker.count} ({formatPercent(blocker.share)})</span></li>
        ))}</ul>
      )}
    </div>
  );
}

function Metric({ label, value, negative }: { label: string; value: string; negative?: boolean }) {
  return <div className="rounded border border-gray-100 px-3 py-2"><div className="text-xs text-gray-500">{label}</div><div className={`text-sm font-semibold ${negative ? 'text-red-700' : 'text-gray-900'}`}>{value}</div></div>;
}

export default ExecutionReconciliationTable;
