Zero-trade order-book replay fixture

Purpose

`src/tests/fixtures/zero_trade_orderbook_run.json` is a deterministic, checked-in
replay of the simulated ML-enhanced order-book run. It preserves the observed
aggregate counts (401 selected symbols and 2,635 diagnosis evaluations) and
contains representative records for a valid HOLD, an ML-gated BUY, transformer
warm-up, and a quote/data failure negative control.

The fixture does not submit orders, create fills, write trades, or relax any
risk control. The dominant order-preventing blocker is
`ml_confidence_below_threshold` (1,115 candidate evaluations). The transformer
is configured, but classifier and regressor artifacts are absent, so the
neutral confidence value remains below the configured 0.6 threshold.

Execution

The replay test is registered as the CTest target
`zero_trade_orderbook_fixture` in `CMakeLists.txt`. It loads the fixture,
checks the aggregate stage counts and lifecycle markers, then feeds the
representative diagnosis records through `makeDiagnosisSummary`, the same
production reconciliation helper used by
`SimulatedTradingService::buildDiagnosisJson`. It runs that reconciliation
twice and requires identical summaries and dominant-blocker classification.

Use the repository's containerized C++ test toolchain (or the remote Docker
Build Validation workflow); do not run live trading or provider calls:

    cmake --build <configured-build-dir> --target test_zero_trade_orderbook_fixture
    ctest --test-dir <configured-build-dir> -R '^zero_trade_orderbook_fixture$' --output-on-failure

The test expects:

- 401 selected symbols, 2,635 diagnosis evaluations, and 401 warm-up events;
- 1,119 valid HOLDs and 1,115 generated candidates;
- profitability passing for candidates, ML blocking all 1,115 candidates;
- zero executable intents, fills, persisted trades, `trade_open`, or
  `trade_completed` events; and
- stable `ml_confidence_below_threshold` dominant-blocker classification.