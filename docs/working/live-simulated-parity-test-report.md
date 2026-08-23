# Live/Simulated parity verification

Status: in progress until the exact pushed-SHA remote workflows complete.

## Scope

The parity scenario uses the same strategy, selected universe, and strategy parameters in both tabs. The comparison covers:

- start payload symbols, strategy, parameters, and position sizing;
- signal fields, criteria analysis, ML diagnostics, and profitability-gate fields;
- latest-by-symbol coverage, total/active counts, pagination, retention, and freshness;
- account/portfolio totals, active positions, and widget labels.

Live execution remains fail-closed; this verification does not submit live orders or use credentials.

## Source-backed scenario

The frontend's canonical simulated fallback generates one row per selected symbol and returns `total`, `total_pages`, `active_signals`, and `last_updated` from the same ordered set (`frontend/lib/api.ts`). The shared start payload builder preserves the selected symbols and strategy parameters for both modes (`frontend/lib/api.ts:618-672`, `frontend/lib/startTradingPayload.test.ts`). Live snapshot normalization keeps account-readiness blockers and execution flags explicit (`frontend/lib/liveTabProducer.ts`). Simulated snapshot normalization keeps signed positions value separate from gross exposure and replaces, rather than adds, portfolio-level fees (`frontend/lib/simulatedTradingStats.ts`).

Representative deterministic fixture: strategy `ml_enhanced_orderbook`, universe `BTC-USD`, `ETH-USD`, initial portfolio size `10000`, maximum positions `4`, and execution mode `live_parity`. The frontend tests assert payload preservation and simulated signal response shape; dashboard table fixtures assert criteria analysis, gate diagnostics, selected-universe coverage, pagination, and summary labels.

## Remote execution evidence

Commands are run by GitHub Actions, not on the worker host. The worker intentionally does not run local Docker, CMake, npm, Jest, or Playwright commands.

| Check | Workflow/job | Commit SHA | Duration | Result | Evidence |
|---|---|---|---:|---|---|
| Complete backend CTest set | Docker Build Validation / Build C++ Backend | pending | pending | pending | pending |
| Complete frontend Jest set | Frontend Test Suite / Frontend Jest | pending | pending | pending | pending |
| Frontend production build | Docker Build Validation / Build Frontend | pending | pending | pending | pending |

## Findings

No live-vs-simulated runtime request/response capture is claimed here because no authenticated backend runtime was available to this worker. Any mismatch discovered by remote tests or source comparison will be recorded below with reproduction, expected/actual behavior, and severity.

## Closeout checklist

- [ ] Both complete suites finished on the exact pushed SHA.
- [ ] All failures triaged with reproducible evidence.
- [ ] Parity scenario and unavailable runtime evidence are explicitly reported.
- [ ] Required remote workflow jobs are green.
