# Trade Strategy Objective

The trade project objective is to maximize risk-adjusted expectancy in the live trading environment.

Operationally, future strategy, execution, ML, and dashboard decisions should optimize for:

1. Increase average realized win after fees, spread, and slippage.
2. Minimize average realized loss after fees, spread, and slippage.
3. Improve net expectancy and profit factor without increasing drawdown beyond the accepted risk budget.
4. Preserve enough trade frequency to validate the strategy, but never maximize raw signal count or trade count when the added executions worsen expectancy.
5. Keep live exchange execution fail-closed: account readiness, minimum notional, spot-only constraints, pending orders, explicit live-order enablement, and user-selected universe policy take priority over signal maximization.

## Required decision evidence

Every future change that affects strategy generation, signal strength, expected return, profitability gates, model selection, position sizing, exits, or execution blockers should state its expected impact on:

- generated signal count by strategy and symbol;
- signal strength distribution;
- expected return and fee-adjusted expected return;
- required edge / profitability gate pass rate;
- executed trades and blocked intents;
- average win;
- average loss;
- net expectancy;
- profit factor;
- maximum drawdown;
- live-only exchange blockers.

## Backlog and review contract

Every future strategy, ML, execution, dashboard, or backlog item that can change trading behavior should include an objective-impact note before implementation and closeout. The note should identify:

- the expected direction of average realized win, average realized loss, net expectancy, profit factor, drawdown, fees/spread/slippage drag, and blocked intents;
- the evidence source that will verify the impact, such as a fixed fixture, live-parity paper run, backtest window, captured live signal window, or post-change dashboard/API snapshot;
- the rollback or follow-up condition if the change increases raw signal/trade count without improving risk-adjusted expectancy;
- whether any missing expected-return or profitability diagnostics are `gate`, `size`, `exit`, `report`, or `unavailable` according to the diagnostics factoring contract below;
- whether live-account safety, explicit user universe selection, secret handling, fail-closed exchange behavior, and no-unapproved-liquidation rules are unchanged.

Review reports and backlog closeout evidence should treat a higher signal count, trade count, or widget throughput as supporting evidence only when it also improves or preserves expectancy after costs and blockers. If objective-impact evidence is unavailable, the backlog item should say so explicitly and leave measurement/calibration work open rather than claiming optimization.

## Diagnostics factoring contract

Strategy diagnostics should be factored explicitly, not treated as decorative metadata.

For each strategy, expected-return and profitability diagnostics must be classified as one of:

- `gate`: blocks or allows entry/exit;
- `size`: scales position sizing;
- `exit`: participates in close/add/hold decisions;
- `report`: appears in UI/reports but does not affect execution;
- `unavailable`: absent or unsupported and therefore fail-safe for any path that requires expected edge.

Directional expected-return semantics are required:

- buy signals need positive expected return;
- sell signals need negative expected return;
- both sides must clear fees, spread, and slippage before being considered profitable;
- unavailable expected return must never be interpreted as high confidence, zero risk, or automatic actionability.

## Review checklist

Before shipping live-affecting strategy work:

- [ ] Compare before/after average win, average loss, expectancy, and drawdown.
- [ ] Prove any increase in signal/trade count improves expectancy after costs.
- [ ] Confirm expected-return diagnostics are directional and fee-adjusted.
- [ ] Confirm missing diagnostics fail safe and remain visible to operators.
- [ ] Confirm live-only blockers are attributed separately from signal-quality failures.
- [ ] Run independent review for high-risk trading/accounting changes.
- [ ] Verify the exact pushed SHA with GitHub Actions Docker Build Validation before closeout.

## Review reports

- `docs/reports/trade-strategy-objective-review-2026-08-01.md` inventories every live/simulated strategy, classifies objective alignment, and maps remaining strategy findings to backlog items.
