import React, { useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import {
  buildOrderBookSignalRows,
  formatOrderBookLabel,
  getOrderBookSignalCounts,
  OrderBookGroupBy,
  OrderBookSignalOutcome,
  OrderBookSignalViewRow,
  OrderBookSignalsViewModel,
} from '@/lib/orderBookSignalsViewModel';
import { OrderBookSignal, OrderBookSignalDiagnostics } from '@/types/trading';

type Pagination = {
  current_page?: number;
  page?: number;
  per_page?: number;
  limit?: number;
  total_pages: number;
  total_signals?: number;
  total?: number;
  has_next: boolean;
  has_prev: boolean;
};

type Summary = {
  total_analyzed?: number;
  active_signals?: number;
  average_strength?: number;
  last_updated?: string;
  diagnostics?: OrderBookSignalDiagnostics;
};

export interface OrderBookSignalsTableProps {
  signals?: OrderBookSignal[];
  diagnosis?: OrderBookSignalDiagnostics | undefined;
  viewModel?: OrderBookSignalsViewModel | undefined;
  selectedSymbols?: string[] | undefined;
  pagination?: Pagination | undefined;
  currentPage?: number;
  pageSize?: number;
  onPageChange?: (page: number) => void;
  onPageSizeChange?: (pageSize: number) => void;
  summary?: Summary | undefined;
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
}

const OUTCOME_OPTIONS: Array<{ value: '' | OrderBookSignalOutcome; label: string }> = [
  { value: '', label: 'All outcomes' },
  { value: 'request_failed', label: 'Request failed' },
  { value: 'executable', label: 'Executable' },
  { value: 'hold', label: 'Valid HOLD' },
  { value: 'gates_blocked', label: 'Gate blocked' },
  { value: 'intent_not_executable', label: 'Intent blocked' },
  { value: 'trade_open', label: 'Trade open' },
  { value: 'trade_completed', label: 'Trade completed' },
  { value: 'execution_failed', label: 'Execution failed' },
  { value: 'data_unavailable', label: 'Data unavailable' },
  { value: 'quote_invalid', label: 'Invalid quote' },
  { value: 'quote_stale', label: 'Stale quote' },
  { value: 'transformer_not_ready', label: 'Transformer warming' },
  { value: 'feature_shape_mismatch', label: 'Rejected model input' },
  { value: 'pending', label: 'Pending evaluation' },
];

const GROUP_OPTIONS: Array<{ value: OrderBookGroupBy; label: string }> = [
  { value: 'outcome', label: 'Outcome' },
  { value: 'blocker', label: 'Blocker' },
  { value: 'modelState', label: 'Model state' },
  { value: 'quoteState', label: 'Quote state' },
];

const OUTCOME_CLASSES: Record<OrderBookSignalOutcome, string> = {
  pending: 'border-slate-200 bg-slate-50 text-slate-700',
  data_unavailable: 'border-red-200 bg-red-50 text-red-800',
  request_failed: 'border-red-200 bg-red-50 text-red-800',
  quote_invalid: 'border-red-200 bg-red-50 text-red-800',
  quote_stale: 'border-amber-200 bg-amber-50 text-amber-800',
  transformer_not_ready: 'border-amber-200 bg-amber-50 text-amber-800',
  feature_shape_mismatch: 'border-red-200 bg-red-50 text-red-800',
  hold: 'border-slate-200 bg-slate-100 text-slate-800',
  gates_blocked: 'border-orange-200 bg-orange-50 text-orange-800',
  intent_not_executable: 'border-orange-200 bg-orange-50 text-orange-800',
  execution_failed: 'border-red-200 bg-red-50 text-red-800',
  trade_open: 'border-blue-200 bg-blue-50 text-blue-800',
  trade_completed: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  executable: 'border-emerald-200 bg-emerald-50 text-emerald-800',
};

function formatTime(timestamp?: string): string {
  if (!timestamp) return '—';
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? timestamp : date.toLocaleString();
}

function formatNumber(value?: number, digits = 2): string {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : '—';
}

function displayError(error: unknown): string {
  return error instanceof Error ? error.message : typeof error === 'string' ? error : 'Unknown request error';
}

function groupValue(row: OrderBookSignalViewRow, groupBy: OrderBookGroupBy): string {
  if (groupBy === 'outcome') return row.outcomeLabel;
  const value = row[groupBy];
  return value ? formatOrderBookLabel(value) : 'None reported';
}

function Details({ row }: { row: OrderBookSignalViewRow }) {
  const diagnosis = row.diagnosis;
  const signal = row.signal;
  const reason = diagnosis?.status?.reason;
  const ml = signal?.ml_analysis;
  const execution = diagnosis?.execution || signal?.execution_analysis;
  const trade = diagnosis?.trade;
  const cadence = signal?.cadence || diagnosis?.cadence;

  return (
    <div id={`order-book-details-${row.key.replace(/[^a-zA-Z0-9_-]/g, '-')}`} className="border-t border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-700">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <p className="font-semibold text-slate-900">Signal</p>
          <p>Final side: {row.finalSide ? row.finalSide.toUpperCase() : '—'}</p>
          <p>Candidate side: {row.candidateSide ? row.candidateSide.toUpperCase() : '—'}</p>
          <p>Strength: {formatNumber(row.strength)}</p>
          <p>Edge: {row.edge === undefined ? '—' : `${(row.edge * 100).toFixed(2)}%`}</p>
        </div>
        <div>
          <p className="font-semibold text-slate-900">Market data</p>
          <p>Quote: {formatOrderBookLabel(row.quoteState)}</p>
          <p>Price: {row.price === undefined ? '—' : `$${formatNumber(row.price)}`}</p>
          <p>Reason: {row.reason}</p>
        </div>
        <div>
          <p className="font-semibold text-slate-900">Model and gates</p>
          <p>Model: {formatOrderBookLabel(row.modelState)}</p>
          <p>Gate reason: {signal?.ml_analysis?.profitability_gate_reason || '—'}</p>
          <p>Diagnostic factor: {ml?.diagnostic_factor || '—'}</p>
          <p>Confidence: {ml?.confidence === undefined ? '—' : `${(ml.confidence * 100).toFixed(2)}%`}</p>
        </div>
        <div>
          <p className="font-semibold text-slate-900">Execution and trade</p>
          <p>Intent: {formatOrderBookLabel(row.executionState)}</p>
          <p>Blocker: {row.blocker || '—'}</p>
          <p>Trade: {formatOrderBookLabel(row.tradeState)}</p>
          <p>Updated: {formatTime(row.updatedAt)}</p>
        </div>
      </div>
      {(reason?.message || diagnosis?.status?.evaluated_at || diagnosis?.sequence || signal?.event_id) && (
        <div className="mt-3 border-t border-slate-200 pt-2 text-slate-600">
          <span className="font-semibold text-slate-900">Diagnostic metadata: </span>
          {reason?.message || 'No status message'}
          {diagnosis?.status?.evaluated_at && ` · evaluated ${formatTime(diagnosis.status.evaluated_at)}`}
          {diagnosis?.sequence !== undefined && ` · sequence ${diagnosis.sequence}`}
          {signal?.event_id && ` · event ${signal.event_id}`}
        </div>
      )}
      {cadence && (
        <p className="mt-2 break-words text-slate-600">
          <span className="font-semibold text-slate-900">Cadence: </span>
          {cadence.state || 'unclassified'}
          {cadence.tick_id !== undefined && ` · tick ${cadence.tick_id}`}
          {cadence.batch_id && ` · batch ${cadence.batch_id}`}
          {cadence.attempts !== undefined && ` · attempts ${cadence.attempts}`}
        </p>
      )}
      {execution && typeof execution === 'object' && 'error' in execution && (
        <p className="mt-2 break-words text-red-700">Execution error: {String((execution as { error?: unknown }).error || 'Unknown error')}</p>
      )}
      {trade && typeof trade === 'object' && 'realized_pnl' in trade && (
        <p className="mt-2">Realized P&amp;L: {String((trade as { realized_pnl?: unknown }).realized_pnl ?? '—')}</p>
      )}
    </div>
  );
}

function SignalRow({ row, expanded, onToggle }: { row: OrderBookSignalViewRow; expanded: boolean; onToggle: () => void }) {
  const detailsId = `order-book-details-${row.key.replace(/[^a-zA-Z0-9_-]/g, '-')}`;
  return (
    <React.Fragment>
      <tr className="border-t border-slate-200 align-top hover:bg-slate-50">
        <td className="px-3 py-3 font-semibold text-slate-900">
          <span className="block max-w-[11rem] truncate" title={row.symbol}>{row.symbol}</span>
        </td>
        <td className="px-3 py-3">
          <span className={`inline-flex max-w-[12rem] items-center rounded-full border px-2 py-1 text-xs font-medium ${OUTCOME_CLASSES[row.outcome]}`}>
            {row.outcomeLabel}
          </span>
          {row.retryable && <span className="ml-2 text-xs text-slate-500">retryable</span>}
        </td>
        <td className="px-3 py-3 text-slate-600">
          <span className="block max-w-[10rem] truncate" title={row.quoteState}>{formatOrderBookLabel(row.quoteState)}</span>
        </td>
        <td className="px-3 py-3 font-medium text-slate-700">
          {row.finalSide ? row.finalSide.toUpperCase() : '—'}
          {row.candidateSide && row.candidateSide.toLowerCase() !== row.finalSide?.toLowerCase() && (
            <span className="ml-1 text-xs text-slate-500">from {row.candidateSide.toUpperCase()}</span>
          )}
        </td>
        <td className="px-3 py-3 text-slate-600">
          <span>{row.strength === undefined ? '—' : formatNumber(row.strength)}</span>
          <span className="ml-2 text-xs">{row.edge === undefined ? '' : `${(row.edge * 100).toFixed(2)}% edge`}</span>
        </td>
        <td className="px-3 py-3 text-slate-600"><span className="block max-w-[10rem] truncate" title={row.modelState}>{formatOrderBookLabel(row.modelState)}</span></td>
        <td className="px-3 py-3 text-slate-600"><span className="block max-w-[14rem] break-words line-clamp-2" title={row.blocker || row.reason}>{row.blocker || row.reason}</span></td>
        <td className="whitespace-nowrap px-3 py-3 text-slate-500">{formatTime(row.updatedAt)}</td>
        <td className="px-3 py-3">
          <button
            type="button"
            className="inline-flex items-center rounded-md px-2 py-1 text-xs font-medium text-blue-700 underline-offset-2 hover:bg-blue-50 hover:underline focus:outline-none focus:ring-2 focus:ring-blue-500"
            aria-expanded={expanded}
            aria-controls={detailsId}
            aria-label={`${expanded ? 'Hide' : 'Show'} details for ${row.symbol}`}
            onClick={onToggle}
          >
            {expanded ? <ChevronDown className="mr-1 h-3.5 w-3.5" aria-hidden="true" /> : <ChevronRight className="mr-1 h-3.5 w-3.5" aria-hidden="true" />}
            Details
          </button>
        </td>
      </tr>
      {expanded && <tr><td colSpan={9}><Details row={row} /></td></tr>}
    </React.Fragment>
  );
}

export function OrderBookSignalsTable({
  signals = [],
  diagnosis,
  viewModel,
  selectedSymbols,
  pagination,
  currentPage = pagination?.current_page || pagination?.page || 1,
  pageSize = pagination?.per_page || pagination?.limit || 25,
  onPageChange,
  onPageSizeChange,
  summary,
  loading = false,
  error,
  onRetry,
}: OrderBookSignalsTableProps) {
  const [search, setSearch] = useState('');
  const [outcome, setOutcome] = useState<'' | OrderBookSignalOutcome>('');
  const [modelState, setModelState] = useState('');
  const [groupBy, setGroupBy] = useState<OrderBookGroupBy>('outcome');
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const canonicalDiagnosis = diagnosis ?? summary?.diagnostics;
  const rows = useMemo(() => {
    if (viewModel) return viewModel.rows;
    return buildOrderBookSignalRows({
      signals,
      ...(canonicalDiagnosis ? { diagnosis: canonicalDiagnosis } : {}),
      ...(selectedSymbols ? { selectedSymbols } : {}),
      ...(error && !canonicalDiagnosis && selectedSymbols ? { failedSymbols: selectedSymbols } : {}),
    });
  }, [canonicalDiagnosis, error, selectedSymbols, signals, viewModel]);
  const counts = useMemo(() => getOrderBookSignalCounts(rows), [rows]);
  const diagnosisSummary = canonicalDiagnosis?.summary;
  const stageCounts = diagnosisSummary?.stage_counts ?? canonicalDiagnosis?.stage_counts;
  const aggregateCounts = [
    ['Selected symbols', stageCounts?.selected_symbols ?? diagnosisSummary?.selected_count ?? counts.total],
    ['Quote successes', stageCounts?.quote_success_evaluations ?? 0],
    ['Quote failures', stageCounts?.quote_failures ?? 0],
    ['Transformer ready', stageCounts?.transformer_ready_evaluations ?? 0],
    ['Transformer warming-up', stageCounts?.transformer_warmup_events ?? 0],
    ['Generated candidates', stageCounts?.generated_candidates ?? 0],
    ['HOLDs', stageCounts?.signal_holds ?? 0],
    ['Profitability passed', stageCounts?.profitability_gate_passed ?? 0],
    ['Profitability blocked', stageCounts?.profitability_gate_blocked ?? 0],
    ['ML passed', stageCounts?.ml_gate_passed ?? 0],
    ['ML blocked', stageCounts?.ml_gate_blocked ?? 0],
    ['Executable intents', stageCounts?.executable_intents ?? 0],
    ['Simulated fills', stageCounts?.simulated_fills ?? 0],
    ['Persisted trades', stageCounts?.persisted_trades ?? diagnosisSummary?.trade_count ?? 0],
    ['Persistence failures', stageCounts?.persistence_failures ?? 0],
  ] as const;
  const dominantBlocker = diagnosisSummary?.dominant_blocker ?? canonicalDiagnosis?.dominant_blocker;
  const terminalOutcomes = Object.entries(diagnosisSummary?.by_primary_status ?? {})
    .map(([status, count]) => `${status} (${count})`)
    .join(', ');
  const filteredRows = useMemo(() => {
    const query = search.trim().toLowerCase();
    return rows.filter((row) => {
      const matchesSearch = !query || [row.symbol, row.reason, row.blocker, row.modelState, row.outcomeLabel].some((value) => value.toLowerCase().includes(query));
      return matchesSearch && (!outcome || row.outcome === outcome) && (!modelState || row.modelState === modelState);
    });
  }, [modelState, outcome, rows, search]);
  const activePageSize = Math.max(1, pageSize);
  const totalPages = Math.max(1, Math.ceil(filteredRows.length / activePageSize));
  const safePage = Math.min(Math.max(1, currentPage), totalPages);
  const pagedRows = filteredRows.slice((safePage - 1) * activePageSize, safePage * activePageSize);
  const groups = useMemo(() => {
    const grouped = new Map<string, OrderBookSignalViewRow[]>();
    pagedRows.forEach((row) => {
      const key = groupValue(row, groupBy);
      const values = grouped.get(key) || [];
      values.push(row);
      grouped.set(key, values);
    });
    return Array.from(grouped.entries());
  }, [groupBy, pagedRows]);
  const modelOptions = useMemo(() => Array.from(new Set(rows.map((row) => row.modelState))).sort(), [rows]);

  useEffect(() => {
    if (currentPage > totalPages) onPageChange?.(totalPages);
  }, [currentPage, onPageChange, totalPages]);

  const resetPage = () => {
    if (currentPage !== 1) onPageChange?.(1);
  };

  if (loading && !canonicalDiagnosis && !viewModel && signals.length === 0) {
    return <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-600" role="status" aria-live="polite">Loading order-book signal coverage…</div>;
  }

  return (
    <div className="space-y-4">
      {Boolean(error) && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
          <span>Unable to refresh all order-book signals: {displayError(error)} {rows.length > 0 ? 'Showing the last known coverage.' : ''}</span>
          {onRetry && <Button type="button" size="sm" variant="secondary" onClick={onRetry}><RefreshCw className="mr-1 h-4 w-4" />Retry</Button>}
        </div>
      )}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8" aria-label="Order-book signal coverage summary">
        {[
          ['Selected', counts.total], ['Ready', counts.ready], ['HOLD', counts.hold], ['Blocked', counts.blocked],
          ['Executable', counts.executable], ['Unavailable', counts.unavailable], ['Pending', counts.pending], ['Traded', counts.traded],
        ].map(([name, value]) => <div key={String(name)} className="rounded-md border border-slate-200 bg-white px-3 py-2"><p className="text-xs text-slate-500">{name}</p><p className="text-lg font-semibold text-slate-900">{value}</p></div>)}
      </div>
      <div className="rounded-lg border border-slate-200 bg-white p-3" aria-label="Reconciliation counts">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
          {aggregateCounts.map(([name, value]) => (
            <div key={name} className="rounded-md border border-slate-100 bg-slate-50 px-3 py-2">
              <p className="text-xs text-slate-500">{name}</p>
              <p className="text-base font-semibold text-slate-900">{value}</p>
            </div>
          ))}
        </div>
        <div className="mt-3 grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
          <div className="rounded-md border border-orange-100 bg-orange-50 px-3 py-2 text-orange-900">
            <span className="font-semibold">Dominant blocker</span><span>: </span>
            {dominantBlocker?.code ? (
              <>
                <span>{dominantBlocker.code} ({dominantBlocker.count ?? 0})</span>
                {dominantBlocker.category && <span className="ml-2 text-xs">category: {formatOrderBookLabel(dominantBlocker.category)}</span>}
              </>
            ) : 'None reported'}
          </div>
          <div className="rounded-md border border-slate-100 bg-slate-50 px-3 py-2 text-slate-700">
            <span className="font-semibold">Terminal outcomes</span><span>: </span>
            {terminalOutcomes || 'None reported'}
          </div>
        </div>
      </div>
      <div className="rounded-lg border border-slate-200 bg-white p-3">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-[minmax(14rem,2fr)_repeat(3,minmax(9rem,1fr))]">
          <Input aria-label="Search symbols and diagnostics" placeholder="Search symbols or reasons…" value={search} onChange={(event) => { setSearch(event.target.value); resetPage(); }} />
          <label className="text-xs font-medium text-slate-600">Outcome<select aria-label="Filter by outcome" className="mt-1 block h-10 w-full rounded-md border border-gray-300 bg-white px-3 text-sm" value={outcome} onChange={(event) => { setOutcome(event.target.value as '' | OrderBookSignalOutcome); resetPage(); }}>{OUTCOME_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
          <label className="text-xs font-medium text-slate-600">Model state<select aria-label="Filter by model state" className="mt-1 block h-10 w-full rounded-md border border-gray-300 bg-white px-3 text-sm" value={modelState} onChange={(event) => { setModelState(event.target.value); resetPage(); }}><option value="">All model states</option>{modelOptions.map((option) => <option key={option} value={option}>{formatOrderBookLabel(option)}</option>)}</select></label>
          <label className="text-xs font-medium text-slate-600">Group by<select aria-label="Group signals by" className="mt-1 block h-10 w-full rounded-md border border-gray-300 bg-white px-3 text-sm" value={groupBy} onChange={(event) => setGroupBy(event.target.value as OrderBookGroupBy)}>{GROUP_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
        </div>
        <p className="mt-2 text-xs text-slate-500">Showing {pagedRows.length} of {filteredRows.length} matching rows; counts include all {counts.total} selected symbols.</p>
      </div>
      {rows.length === 0 ? (
        <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-sm text-slate-600" role="status">No selected symbols have been reported for this session yet.</div>
      ) : filteredRows.length === 0 ? (
        <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-sm text-slate-600" role="status">No symbols match the current search and filters.</div>
      ) : (
        <div className="space-y-4">
          {groups.map(([group, groupRows]) => (
            <section key={group} aria-labelledby={`order-book-group-${group.replace(/[^a-zA-Z0-9_-]/g, '-')}`} className="overflow-hidden rounded-lg border border-slate-200 bg-white">
              <div className="flex items-center justify-between bg-slate-50 px-4 py-2"><h4 id={`order-book-group-${group.replace(/[^a-zA-Z0-9_-]/g, '-')}`} className="text-sm font-semibold text-slate-800">{group}</h4><span className="text-xs text-slate-500">{groupRows.length} on this page</span></div>
              <div className="overflow-x-auto"><table className="min-w-[980px] w-full text-left text-sm"><caption className="sr-only">Order-book signals grouped by {GROUP_OPTIONS.find((option) => option.value === groupBy)?.label}</caption><thead className="text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-3 py-2">Symbol</th><th className="px-3 py-2">Outcome</th><th className="px-3 py-2">Quote</th><th className="px-3 py-2">Side</th><th className="px-3 py-2">Strength / edge</th><th className="px-3 py-2">Model</th><th className="px-3 py-2">Blocker / reason</th><th className="px-3 py-2">Updated</th><th className="px-3 py-2">Details</th></tr></thead><tbody>{groupRows.map((row) => <SignalRow key={row.key} row={row} expanded={expandedKey === row.key} onToggle={() => setExpandedKey(expandedKey === row.key ? null : row.key)} />)}</tbody></table></div>
            </section>
          ))}
        </div>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-slate-600">
        <label className="flex items-center gap-2">Rows per page<select aria-label="Rows per page" className="rounded-md border border-gray-300 bg-white px-2 py-1" value={activePageSize} onChange={(event) => { onPageSizeChange?.(Number(event.target.value)); onPageChange?.(1); }}><option value={10}>10</option><option value={25}>25</option><option value={50}>50</option><option value={100}>100</option></select></label>
        <span>Page {safePage} of {totalPages} · {filteredRows.length} matching symbols</span>
        <div className="flex gap-2"><Button type="button" size="sm" variant="secondary" disabled={safePage <= 1} onClick={() => onPageChange?.(safePage - 1)}>Previous</Button><Button type="button" size="sm" variant="secondary" disabled={safePage >= totalPages} onClick={() => onPageChange?.(safePage + 1)}>Next</Button></div>
      </div>
      {summary?.diagnostics?.coverage_complete === false && <p className="text-xs text-amber-700" role="status">Some selected symbols are represented by explicit coverage or request-failure rows and are awaiting a successful refresh.</p>}
    </div>
  );
}