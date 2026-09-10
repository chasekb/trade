import React from 'react';
import {
  ExecutionReconciliationSnapshot,
  StrategyReconciliation,
  formatBlockerMix,
  rankStrategiesByExpectancyRisk,
} from '@/lib/executionReconciliation';

const formatUsd = (value: number) =>
  `${value < 0 ? '-' : ''}$${Math.abs(value).toFixed(2)}`;

const formatPercent = (fraction: number) => `${(fraction * 100).toFixed(1)}%`;

const formatProfitFactor = (row: StrategyReconciliation) => {
  if (row.profitFactorUndefined) return 'n/a (no losses)';
  if (row.closingLegs === 0) return '—';
  return row.profitFactor.toFixed(2);
};

// Signal-to-outcome reconciliation by strategy and blocker bucket. Read-only:
// this view explains why generated signals did or did not become fills, and
// what the fills realized after fees. It never triggers an order.
export function ExecutionReconciliationTable({
  reconciliation,
  isLoading,
  error,
}: {
  reconciliation: ExecutionReconciliationSnapshot | null;
  isLoading?: boolean;
  error?: Error | null;
}) {
  if (isLoading) {
    return (
      <div className="bg-white rounded-lg shadow p-4 text-sm text-gray-500">
        Loading execution reconciliation…
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow p-4 text-sm text-red-600">
        Execution reconciliation unavailable: {error.message}
      </div>
    );
  }

  if (!reconciliation) {
    return null;
  }

  const rows = rankStrategiesByExpectancyRisk(reconciliation.byStrategy);
  const { overall } = reconciliation;

  return (
    <div className="bg-white rounded-lg shadow p-4 space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-base font-semibold text-gray-900">Execution reconciliation</h3>
        <span className="text-xs text-gray-500">
          Trailing {reconciliation.windowHours}h · {reconciliation.signalRows} signal rows ·{' '}
          {reconciliation.outcomeRows} trade rows
          {reconciliation.sessionId ? ` · session ${reconciliation.sessionId}` : ''}
        </span>
      </div>

      {reconciliation.error && (
        <p className="text-xs text-red-600">Partial data: {reconciliation.error}</p>
      )}
      {reconciliation.signalRowsTruncated && (
        <p className="text-xs text-amber-600">
          Signal rows were truncated by the query limit; blocker shares cover the most recent rows
          only.
        </p>
      )}
      {overall.outcomesUnexplained && (
        <p className="text-xs text-amber-600">
          This window contains closed trades with no executable intent behind them — the signal
          window does not explain every outcome.
        </p>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="Generated signals" value={String(overall.signalsGenerated)} />
        <Metric
          label="Executable intents"
          value={`${overall.executableIntents} (${formatPercent(overall.intentConversionRate)})`}
        />
        <Metric label="Blocked intents" value={String(overall.blockedIntents)} />
        <Metric
          label="Expectancy / trade"
          value={overall.closingLegs > 0 ? formatUsd(overall.expectancy) : '—'}
          negative={overall.negativeExpectancyFlag}
        />
      </div>

      {rows.length === 0 ? (
        <p className="text-sm text-gray-500">
          No signals or outcomes recorded in this window.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-gray-500">
                <th className="px-2 py-2">Strategy</th>
                <th className="px-2 py-2">Signals</th>
                <th className="px-2 py-2">Intents</th>
                <th className="px-2 py-2">Blocked</th>
                <th className="px-2 py-2">Closed</th>
                <th className="px-2 py-2">Win rate</th>
                <th className="px-2 py-2">Avg win</th>
                <th className="px-2 py-2">Avg loss</th>
                <th className="px-2 py-2">Expectancy</th>
                <th className="px-2 py-2">Profit factor</th>
                <th className="px-2 py-2">Net PnL</th>
                <th className="px-2 py-2">Blocker mix</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.strategy} className="border-t border-gray-100">
                  <td className="px-2 py-2 font-medium text-gray-900">{row.strategy}</td>
                  <td className="px-2 py-2">{row.signalsGenerated}</td>
                  <td className="px-2 py-2">{row.executableIntents}</td>
                  <td className="px-2 py-2">{row.blockedIntents}</td>
                  <td className="px-2 py-2">{row.closingLegs}</td>
                  {/* win_rate arrives as a 0-100 percentage; never rescale it. */}
                  <td className="px-2 py-2">
                    {row.winners + row.losers > 0 ? `${row.winRate.toFixed(1)}%` : '—'}
                  </td>
                  <td className="px-2 py-2 text-green-700">{formatUsd(row.averageWin)}</td>
                  <td className="px-2 py-2 text-red-700">{formatUsd(row.averageLoss)}</td>
                  <td
                    className={`px-2 py-2 ${row.negativeExpectancyFlag ? 'text-red-700' : 'text-gray-900'}`}
                  >
                    {row.closingLegs > 0 ? formatUsd(row.expectancy) : '—'}
                  </td>
                  <td className="px-2 py-2">{formatProfitFactor(row)}</td>
                  <td
                    className={`px-2 py-2 ${row.totalPnl < 0 ? 'text-red-700' : 'text-gray-900'}`}
                  >
                    {formatUsd(row.totalPnl)}
                  </td>
                  <td className="px-2 py-2 text-xs text-gray-600">{formatBlockerMix(row)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
  negative,
}: {
  label: string;
  value: string;
  negative?: boolean;
}) {
  return (
    <div className="rounded border border-gray-100 px-3 py-2">
      <div className="text-xs text-gray-500">{label}</div>
      <div className={`text-sm font-semibold ${negative ? 'text-red-700' : 'text-gray-900'}`}>
        {value}
      </div>
    </div>
  );
}

export default ExecutionReconciliationTable;
