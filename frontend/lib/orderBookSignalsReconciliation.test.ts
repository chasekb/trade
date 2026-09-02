import {
  mergeOrderBookSignalEvent,
  reconcileOrderBookSignalDiagnostics,
  reconcileOrderBookSignals,
  projectOrderBookSignalPage,
} from './orderBookSignalsViewModel';
import { OrderBookSignal } from '@/types/trading';

const signal = (symbol: string, timestamp: string, overrides: Partial<OrderBookSignal> = {}): OrderBookSignal => ({
  symbol,
  timestamp,
  price: 100,
  signal: 'hold',
  signal_generated: false,
  signal_strength: 0.5,
  data_status: 'sufficient',
  spread: 0.01,
  volume: 1,
  ...overrides,
});

test('reconciles newer WebSocket state and ignores stale or repeated events', () => {
  const initial = reconcileOrderBookSignals({
    sessionId: 's1',
    selectedSymbols: ['BTC-USD', 'ETH-USD'],
    signals: [signal('BTC-USD', '2026-09-01T12:00:00Z')],
  });
  const updated = mergeOrderBookSignalEvent(initial, {
    sessionId: 's1',
    sequence: 2,
    eventId: 'event-2',
    signal: signal('BTC-USD', '2026-09-01T12:00:02Z', { signal: 'buy', signal_generated: true }),
  });
  const stale = mergeOrderBookSignalEvent(updated, {
    sessionId: 's1',
    sequence: 1,
    eventId: 'event-1',
    signal: signal('BTC-USD', '2026-09-01T12:00:03Z', { signal: 'sell', signal_generated: true }),
  });
  const repeated = mergeOrderBookSignalEvent(updated, {
    sessionId: 's1',
    sequence: 2,
    eventId: 'event-2',
    signal: signal('BTC-USD', '2026-09-01T12:00:02Z', { signal: 'buy', signal_generated: true }),
  });

  expect(updated.rows.find((row) => row.symbol === 'BTC-USD')?.signal?.signal).toBe('buy');
  expect(stale).toBe(updated);
  expect(repeated).toBe(updated);
  expect(updated.rows).toHaveLength(2);
});

test('keeps a newer local event when an older HTTP snapshot refreshes', () => {
  const initial = reconcileOrderBookSignals({
    sessionId: 's1',
    selectedSymbols: ['BTC-USD'],
    signals: [signal('BTC-USD', '2026-09-01T12:00:00Z')],
  });
  const live = mergeOrderBookSignalEvent(initial, {
    sessionId: 's1',
    sequence: 9,
    signal: signal('BTC-USD', '2026-09-01T12:00:09Z', { signal: 'buy', signal_generated: true }),
  });
  const refreshed = reconcileOrderBookSignals({
    sessionId: 's1',
    selectedSymbols: ['BTC-USD'],
    signals: [signal('BTC-USD', '2026-09-01T12:00:01Z', { signal: 'sell', signal_generated: true })],
    previous: live,
  });

  expect(refreshed.rows[0].signal?.signal).toBe('buy');
});

test('represents partial request failures as rows without changing the selected universe', () => {
  const model = reconcileOrderBookSignals({
    sessionId: 's1',
    selectedSymbols: ['BTC-USD', 'ETH-USD'],
    signals: [signal('BTC-USD', '2026-09-01T12:00:00Z')],
    failedSymbols: ['ETH-USD'],
  });

  expect(model.selectedSymbols).toEqual(['BTC-USD', 'ETH-USD']);
  expect(model.rows.find((row) => row.symbol === 'ETH-USD')).toMatchObject({ outcome: 'request_failed', retryable: true });
  expect(model.coverageComplete).toBe(false);
});

test('does not turn a prior failed symbol into pending when a refresh has no replacement', () => {
  const failed = reconcileOrderBookSignals({
    sessionId: 's1',
    selectedSymbols: ['BTC-USD', 'ETH-USD'],
    signals: [signal('BTC-USD', '2026-09-01T12:00:00Z')],
    failedSymbols: ['ETH-USD'],
  });
  const refreshed = reconcileOrderBookSignals({
    sessionId: 's1',
    selectedSymbols: ['BTC-USD', 'ETH-USD'],
    signals: [signal('BTC-USD', '2026-09-01T12:00:01Z')],
    previous: failed,
  });

  expect(refreshed.rows.find((row) => row.symbol === 'ETH-USD')).toMatchObject({ outcome: 'request_failed' });
  expect(refreshed.coverageComplete).toBe(false);
});

test('lets a sequenced WebSocket update replace an unsequenced HTTP snapshot even with an older timestamp', () => {
  const initial = reconcileOrderBookSignals({
    sessionId: 's1',
    selectedSymbols: ['BTC-USD'],
    signals: [signal('BTC-USD', '2026-09-01T12:00:10Z', { signal: 'sell' })],
  });
  const websocket = mergeOrderBookSignalEvent(initial, {
    sessionId: 's1',
    sequence: 1,
    eventId: 'event-1',
    signal: signal('BTC-USD', '2026-09-01T12:00:01Z', { signal: 'buy', signal_generated: true }),
  });
  const staleRefresh = reconcileOrderBookSignals({
    sessionId: 's1',
    selectedSymbols: ['BTC-USD'],
    signals: [signal('BTC-USD', '2026-09-01T12:00:11Z', { signal: 'sell' })],
    previous: websocket,
  });

  expect(websocket.rows[0].signal?.signal).toBe('buy');
  expect(staleRefresh.rows[0].signal?.signal).toBe('buy');
});

test('resets canonical rows when a new trading session reuses symbols', () => {
  const oldSession = reconcileOrderBookSignals({
    sessionId: 'old',
    selectedSymbols: ['BTC-USD'],
    signals: [signal('BTC-USD', '2026-09-01T12:00:10Z', { signal: 'buy', signal_generated: true })],
  });
  const newSession = reconcileOrderBookSignals({
    sessionId: 'new',
    selectedSymbols: ['BTC-USD'],
    signals: [],
    previous: oldSession,
  });

  expect(newSession.sessionId).toBe('new');
  expect(newSession.rows[0].outcome).toBe('pending');
  expect(newSession.rows[0].signal).toBeUndefined();
});

test('merges diagnosis snapshots by per-symbol sequence instead of poll arrival order', () => {
  const current = reconcileOrderBookSignalDiagnostics({
    session_id: 's1',
    selected_symbols: ['BTC-USD'],
    symbols: [{ symbol: 'BTC-USD', sequence: 8, status: { primary: 'trade_open' } }],
  }, {
    session_id: 's1',
    selected_symbols: ['BTC-USD'],
    symbols: [{ symbol: 'BTC-USD', sequence: 7, status: { primary: 'hold' } }],
  });

  expect(current.symbols?.[0].status?.primary).toBe('trade_open');
});

test('projects all signal pages with a stable strength, timestamp, symbol order', () => {
  const model = reconcileOrderBookSignals({
    selectedSymbols: ['ZED-USD', 'BTC-USD', 'ETH-USD'],
    signals: [
      signal('ZED-USD', '2026-09-01T12:00:00Z', { signal_strength: 0.9 }),
      signal('ETH-USD', '2026-09-01T12:00:00Z', { signal_strength: 0.8 }),
      signal('BTC-USD', '2026-09-01T12:00:00Z', { signal_strength: 0.8 }),
    ],
  });

  const page = projectOrderBookSignalPage(model, 2, 1);
  expect(page.signals.map(({ symbol }) => symbol)).toEqual(['BTC-USD']);
  expect(page.pagination).toMatchObject({ total: 3, totalPages: 3, page: 2, hasNext: true, hasPrevious: true });
});
