# Simulated Trading Tab Test Rollout Plan

Date: 2026-06-21

## Purpose
Turn the simulated trading tab backlog into a single dependency-aware rollout that verifies each calculation, then each table column, then the full widget surfaces using the live evidence captured from `http://localhost:3000`.

## Source of truth
- Live evidence report: `docs/reports/simulated-trading-tab-evidence-2026-06-21.md`
- Original trade recommendation plan has been migrated into the Hermes backlog at `/home/kahlil/.hermes/backlog/backlog.json` (`project_id=trade`, including `TRADE-BL-0001` and `TRADE-BL-0002`).

## Rollout order

### Phase 1 — Calculation coverage
1. `HERMES-BL-0038` — Total Net P&L
2. `HERMES-BL-0039` — Win Rate
3. `HERMES-BL-0040` — Total Trades
4. `HERMES-BL-0041` — Winning Trades
5. `HERMES-BL-0042` — Losing Trades
6. `HERMES-BL-0043` — Cash Balance
7. `HERMES-BL-0044` — Total Value
8. `HERMES-BL-0045` — Positions Value
9. `HERMES-BL-0046` — Active Positions
10. `HERMES-BL-0047` — Unrealized P&L
11. `HERMES-BL-0048` — Realized P&L
12. `HERMES-BL-0049` — Total Fees
13. `HERMES-BL-0050` — Average Win
14. `HERMES-BL-0051` — Average Loss
15. `HERMES-BL-0052` — Best Trade
16. `HERMES-BL-0053` — Worst Trade
17. `HERMES-BL-0054` — Profit Factor
18. `HERMES-BL-0055` — Total Volume
19. `HERMES-BL-0056` — Avg Trade Size

### Phase 2 — Open Positions column coverage
20. `HERMES-BL-0060` — SYMBOL
21. `HERMES-BL-0061` — SIDE
22. `HERMES-BL-0062` — QUANTITY
23. `HERMES-BL-0063` — ENTRY
24. `HERMES-BL-0064` — CURRENT
25. `HERMES-BL-0065` — UNREALIZED P&L
26. `HERMES-BL-0066` — OPENED
27. `HERMES-BL-0067` — ACTION

### Phase 3 — Recent Trades column coverage
28. `HERMES-BL-0068` — TIME
29. `HERMES-BL-0069` — SYMBOL
30. `HERMES-BL-0070` — SIDE
31. `HERMES-BL-0071` — QUANTITY
32. `HERMES-BL-0072` — PRICE
33. `HERMES-BL-0073` — P&L

### Phase 4 — Order Book Signals column coverage
34. `HERMES-BL-0074` — TIME
35. `HERMES-BL-0075` — SYMBOL
36. `HERMES-BL-0076` — PRICE
37. `HERMES-BL-0077` — SIGNAL
38. `HERMES-BL-0078` — STRENGTH
39. `HERMES-BL-0079` — SPREAD
40. `HERMES-BL-0080` — VOLUME
41. `HERMES-BL-0081` — CRITERIA
42. `HERMES-BL-0082` — ML ANALYSIS
43. `HERMES-BL-0083` — DETAILS

### Phase 5 — Widget-level integration coverage
44. `HERMES-BL-0057` — Open Positions widget end-to-end validation
45. `HERMES-BL-0058` — Recent Trades widget end-to-end validation
46. `HERMES-BL-0059` — Order Book Signals widget end-to-end validation

## Execution checkpoints
- Finish each phase before moving to the next phase.
- Keep the live evidence report open as the reference fixture during implementation.
- Prefer one spec per calculation/column so failures are isolated.
- Treat the widget-level items as integration checks that depend on the column-level coverage already passing.

## Closeout checkpoints
- Every calculation card has a dedicated regression test.
- Every visible table column has a dedicated regression test.
- Each widget-level test confirms the end-to-end table still renders correctly after the column checks pass.
- The final suite covers the live evidence shapes, empty-state fixtures, and at least one alternate-row fixture where relevant.
- The rollout can be executed in order without ambiguity about which test owns which displayed value.
