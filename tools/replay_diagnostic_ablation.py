#!/usr/bin/env python3
"""Deterministic, offline diagnostic ablation/replay harness.

The input is JSONL with one candidate decision per line. No network, exchange,
or order-execution code is imported: this command is safe to run in CI and on a
fresh checkout.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

MODES = ("disabled", "report-only", "factored")
STRATEGIES = (
    "orderbook", "ml_enhanced_orderbook", "ml", "sma", "ema", "rsi",
    "bollinger", "macd", "stochastic", "fibonacci", "atr", "dca",
    "buy_and_hold",
)
DIRECTIONS = ("buy", "sell")


@dataclass(frozen=True)
class CostModel:
    fee_rate: float
    spread_bps: float
    slippage_bps: float

    def __post_init__(self) -> None:
        if min(self.fee_rate, self.spread_bps, self.slippage_bps) < 0:
            raise ValueError("fee, spread, and slippage must be non-negative")

    def round_trip_cost(self) -> float:
        return 2 * self.fee_rate + (self.spread_bps + self.slippage_bps) / 10_000 * 2


@dataclass
class Position:
    direction: str
    entry: float
    entry_ts: str


def _number(value: Any) -> float | None:
    return None if value is None else float(value)


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            row = json.loads(line)
            required = {"timestamp", "strategy", "direction", "entry_price", "exit_price"}
            missing = required - row.keys()
            if missing:
                raise ValueError(f"{path}:{line_no}: missing {sorted(missing)}")
            if row["strategy"] not in STRATEGIES:
                raise ValueError(f"{path}:{line_no}: unsupported strategy {row['strategy']}")
            if row["direction"] not in DIRECTIONS:
                raise ValueError(f"{path}:{line_no}: unsupported direction {row['direction']}")
            rows.append(row)
    if not rows:
        raise ValueError(f"{path}: no replay rows")
    return rows


def _diagnostic(row: dict[str, Any]) -> tuple[float | None, str]:
    value = _number(row.get("diagnostic_score"))
    if value is None:
        return None, "unavailable"
    return value, "available"


def _gross_return(row: dict[str, Any]) -> float:
    entry, exit_ = float(row["entry_price"]), float(row["exit_price"])
    sign = 1 if row["direction"] == "buy" else -1
    return sign * (exit_ - entry) / entry


def replay(rows: Iterable[dict[str, Any]], mode: str, costs: CostModel,
           threshold: float) -> dict[str, Any]:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        score, status = _diagnostic(row)
        blocked = mode == "factored" and (score is None or score < threshold)
        if blocked:
            row = {**row, "_blocked": True}
        row = {**row, "_diagnostic_status": status, "_diagnostic_score": score}
        grouped[(row["strategy"], row["direction"])].append(row)

    results: list[dict[str, Any]] = []
    for (strategy, direction), decisions in sorted(grouped.items()):
        executed = [r for r in decisions if not r.get("_blocked")]
        pnls = [_gross_return(r) - costs.round_trip_cost() for r in executed]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        equity, peak, drawdown = 1.0, 1.0, 0.0
        for pnl in pnls:
            equity *= 1 + pnl
            peak = max(peak, equity)
            drawdown = max(drawdown, (peak - equity) / peak)
        gross_loss = abs(sum(losses))
        unavailable = sum(r["_diagnostic_status"] == "unavailable" for r in decisions)
        result = {
            "strategy": strategy, "direction": direction, "mode": mode,
            "input_decisions": len(decisions), "entries": len(decisions),
            "exits": len(executed), "executed_trades": len(executed),
            "blocked_executions": len(decisions) - len(executed),
            "unavailable_diagnostics": unavailable,
            "diagnostics_available": len(decisions) - unavailable,
            "wins": len(wins), "losses": len(losses),
            "average_win": sum(wins) / len(wins) if wins else None,
            "average_loss": sum(losses) / len(losses) if losses else None,
            "net_expectancy": sum(pnls) / len(pnls) if pnls else None,
            "profit_factor": sum(wins) / gross_loss if gross_loss else (math.inf if wins else None),
            "max_drawdown": drawdown,
            "trade_frequency": len(executed) / len(decisions),
            "net_return": equity - 1.0,
            "costs": {"fee_rate": costs.fee_rate, "spread_bps": costs.spread_bps,
                      "slippage_bps": costs.slippage_bps},
        }
        results.append(result)
    return {"mode": mode, "diagnostic_threshold": threshold, "results": results}


def compare(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    baseline = {(r["strategy"], r["direction"]): r for r in runs[1]["results"]}
    factored = {(r["strategy"], r["direction"]): r for r in runs[2]["results"]}
    changes = []
    for key in sorted(baseline):
        before, after = baseline[key], factored[key]
        old, new = before["net_expectancy"], after["net_expectancy"]
        meaningful = before["blocked_executions"] != after["blocked_executions"] or (
            old is not None and new is not None and abs(new - old) >= max(0.001, abs(old) * 0.10)
        )
        if meaningful:
            changes.append({"strategy": key[0], "direction": key[1],
                            "report_only_expectancy": old, "factored_expectancy": new,
                            "blocked_delta": after["blocked_executions"] - before["blocked_executions"],
                            "meaningful": True})
    return changes


def markdown(report: dict[str, Any]) -> str:
    lines = ["# Diagnostic ablation replay", "", f"Input: `{report['input']}`",
             f"Modes: {', '.join(report['modes'])}",
             f"Cost model: fee={report['cost_model']['fee_rate']}, "
             f"spread={report['cost_model']['spread_bps']} bps, "
             f"slippage={report['cost_model']['slippage_bps']} bps",
             "", "Missing diagnostics are counted as `unavailable`, never as zero.", "",
             "| Strategy | Direction | Mode | Trades | Blocked | Unavailable | Avg win | Avg loss | Expectancy | PF | Drawdown | Frequency |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in report["runs"][0]["results"] + report["runs"][1]["results"] + report["runs"][2]["results"]:
        def fmt(value: Any) -> str:
            return "—" if value is None else ("∞" if value == math.inf else f"{value:.6f}")
        lines.append(f"| {r['strategy']} | {r['direction']} | {r['mode']} | {r['executed_trades']} | {r['blocked_executions']} | {r['unavailable_diagnostics']} | {fmt(r['average_win'])} | {fmt(r['average_loss'])} | {fmt(r['net_expectancy'])} | {fmt(r['profit_factor'])} | {r['max_drawdown']:.6f} | {r['trade_frequency']:.6f} |")
    lines += ["", "## Meaningful regressions", ""]
    lines += [f"- {c['strategy']} {c['direction']}: blocked delta {c['blocked_delta']}, "
              f"expectancy {c['report_only_expectancy']} -> {c['factored_expectancy']}" for c in report["meaningful_regressions"]] or ["- None"]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--markdown-out", type=Path, required=True)
    parser.add_argument("--fee-rate", type=float, default=0.001)
    parser.add_argument("--spread-bps", type=float, default=2.0)
    parser.add_argument("--slippage-bps", type=float, default=1.0)
    parser.add_argument("--diagnostic-threshold", type=float, default=0.60)
    args = parser.parse_args()
    costs = CostModel(args.fee_rate, args.spread_bps, args.slippage_bps)
    rows = load_rows(args.input)
    runs = [replay(rows, mode, costs, args.diagnostic_threshold) for mode in MODES]
    report = {"schema_version": 1, "input": str(args.input), "modes": list(MODES),
              "offline_only": True, "live_orders_enabled": False,
              "cost_model": {"fee_rate": costs.fee_rate, "spread_bps": costs.spread_bps,
                             "slippage_bps": costs.slippage_bps}, "runs": runs}
    report["meaningful_regressions"] = compare(runs)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    args.markdown_out.write_text(markdown(report), encoding="utf-8")


if __name__ == "__main__":
    main()
