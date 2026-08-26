describe('execution reconciliation API failure contract', () => {
  afterEach(() => {
    jest.restoreAllMocks();
    jest.resetModules();
  });

  it('turns a reset/socket hang-up into a retryable actionable error', async () => {
    const fetchMock = jest
      .spyOn(global, 'fetch')
      .mockRejectedValue(new Error('socket hang up'));
    const { apiClient } = await import('./api');

    const response = await apiClient.getExecutionReconciliation({ hours: 24 });

    expect(response).toMatchObject({
      status: 'error',
      error: 'Execution reconciliation connection failed. Retry shortly.',
      errorCode: 'reconciliation_transport_error',
      retryable: true,
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toContain('/api/trading/execution-reconciliation?hours=24');
  });

  it('preserves the safe retryable backend diagnostic and request id', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({
        code: 'reconciliation_unavailable',
        error: 'Execution reconciliation is temporarily unavailable. Retry shortly.',
        retryable: true,
        request_id: 'reconciliation-7',
      }),
    } as Response);
    const { apiClient } = await import('./api');

    const response = await apiClient.getExecutionReconciliation({ hours: 24 });

    expect(response).toMatchObject({
      status: 'error',
      errorCode: 'reconciliation_unavailable',
      httpStatus: 503,
      requestId: 'reconciliation-7',
      retryable: true,
    });
    expect(response.data).toBeUndefined();
  });

  it('keeps a valid empty 200 response as successful reconciliation data', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        window_hours: 24,
        signal_rows: 0,
        outcome_rows: 0,
        by_strategy: [],
        overall: { strategy: 'overall' },
      }),
    } as Response);
    const { apiClient } = await import('./api');

    const response = await apiClient.getExecutionReconciliation({ hours: 24 });

    expect(response.status).toBe('success');
    expect(response.data).toMatchObject({ signal_rows: 0, outcome_rows: 0, by_strategy: [] });
  });
});
