#!/usr/bin/env python3
"""Deterministic, offline ablation metrics for diagnostic-gated replay rows."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

MODES = ("disabled", "report-only", "factored")
STRATEGIES = ("orderbook", "ml_enhanced_orderbook", "ml", "sma", "ema", "rsi", "bollinger", "macd", "stochastic", "fibonacci", "atr", "dca", "buy_and_hold")
DIRECTIONS = ("buy", "sell")
Z95 = 1.959963984540054


@dataclass(frozen=True)
class CostModel:
    fee_rate: float = 0.001
    spread_bps: float = 2.0
    slippage_bps: float = 1.0

    def __post_init__(self) -> None:
        if min(self.fee_rate, self.spread_bps, self.slippage_bps) < 0:
            raise ValueError("costs must be non-negative")

    def round_trip_cost(self) -> float:
        return 2 * self.fee_rate + 2 * (self.spread_bps + self.slippage_bps) / 10_000


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_hash(value: Any) -> str:
    return sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def load_rows(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    duplicate_keys: list[list[Any]] = []
    seen: set[tuple[Any, ...]] = set()
    required = {"timestamp", "strategy", "direction", "entry_price", "exit_price"}
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            row = json.loads(line)
            missing = required - row.keys()
            if missing:
                raise ValueError(f"{path}:{line_number}: missing {sorted(missing)}")
            if row["strategy"] not in STRATEGIES or row["direction"] not in DIRECTIONS:
                raise ValueError(f"{path}:{line_number}: unsupported strategy or direction")
            for field in ("entry_price", "exit_price"):
                price = float(row[field])
                if not math.isfinite(price) or price <= 0:
                    raise ValueError(f"{path}:{line_number}: {field} must be finite and positive")
            key = (row["timestamp"], row["strategy"], row["direction"])
            if key in seen:
                duplicate_keys.append(list(key))
            seen.add(key)
            rows.append(row)
    if not rows:
        raise ValueError(f"{path}: no replay rows")
    audit = {"row_count": len(rows), "duplicate_row_keys": duplicate_keys}
    return rows, audit


def diagnostic(row: dict[str, Any]) -> tuple[float | None, str]:
    if "diagnostic_score" not in row or row["diagnostic_score"] is None:
        return None, "missing"
    try:
        value = float(row["diagnostic_score"])
    except (TypeError, ValueError):
        return None, "invalid"
    if not math.isfinite(value) or not 0 <= value <= 1:
        return None, "invalid"
    return value, "available"


def gross_return(row: dict[str, Any]) -> float:
    sign = 1 if row["direction"] == "buy" else -1
    return sign * (float(row["exit_price"]) - float(row["entry_price"])) / float(row["entry_price"])


def confidence_interval(values: list[float], minimum_n: int = 2) -> dict[str, Any]:
    n = len(values)
    if n < minimum_n:
        return {"method": "normal_95_percent", "lower": None, "upper": None, "supported": False, "reason": f"requires n >= {minimum_n}"}
    mean = sum(values) / n
    variance = sum((value - mean) ** 2 for value in values) / (n - 1)
    margin = Z95 * math.sqrt(variance / n)
    return {"method": "normal_95_percent", "lower": mean - margin, "upper": mean + margin, "supported": True}


def metric_summary(values: list[float], *, ci: bool = True) -> dict[str, Any]:
    if not values:
        return {"value": None, "sample_count": 0, "ci95": confidence_interval([]) if ci else None}
    return {"value": sum(values) / len(values), "sample_count": len(values), "ci95": confidence_interval(values) if ci else None}


def replay(rows: Iterable[dict[str, Any]], mode: str, costs: CostModel, threshold: float) -> dict[str, Any]:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for source in rows:
        row = dict(source)
        score, status = diagnostic(row)
        if mode == "factored":
            blocked_reason = "diagnostic_missing" if status == "missing" else "diagnostic_invalid" if status == "invalid" else "diagnostic_below_threshold" if score is not None and score < threshold else None
        else:
            blocked_reason = None
        row.update(_diagnostic_score=score, _diagnostic_status=status, _blocked_reason=blocked_reason)
        groups[(row["strategy"], row["direction"])].append(row)

    results: list[dict[str, Any]] = []
    directional_pnls: dict[str, list[float]] = defaultdict(list)
    for strategy in STRATEGIES:
        for direction in DIRECTIONS:
            decisions = groups.get((strategy, direction), [])
            executed = [row for row in decisions if row["_blocked_reason"] is None]
            pnls = [gross_return(row) - costs.round_trip_cost() for row in executed]
            wins = [pnl for pnl in pnls if pnl > 0]
            losses = [pnl for pnl in pnls if pnl < 0]
            equity = peak = 1.0
            drawdown = 0.0
            for pnl in pnls:
                equity *= 1 + pnl
                peak = max(peak, equity)
                drawdown = max(drawdown, (peak - equity) / peak)
            blockers = Counter(row["_blocked_reason"] for row in decisions if row["_blocked_reason"])
            unavailable = sum(row["_diagnostic_status"] == "missing" for row in decisions)
            invalid = sum(row["_diagnostic_status"] == "invalid" for row in decisions)
            results.append({
                "strategy": strategy, "direction": direction, "mode": mode,
                "sample_count": len(decisions), "input_decisions": len(decisions),
                "executed_trades": len(executed), "blocked_executions": len(decisions) - len(executed),
                "wins": len(wins), "losses": len(losses),
                "average_win": metric_summary(wins), "average_loss": metric_summary(losses),
                "net_expectancy": metric_summary(pnls),
                "profit_factor": sum(wins) / abs(sum(losses)) if losses else ("infinite" if wins else None),
                "max_drawdown": drawdown if pnls else None,
                "trade_frequency": len(executed) / len(decisions) if decisions else None,
                "net_return": equity - 1.0 if pnls else None,
                "unavailable_diagnostics": unavailable, "invalid_diagnostics": invalid,
                "diagnostics_available": len(decisions) - unavailable - invalid,
                "blocker_attribution": dict(sorted(blockers.items())),
                "coverage_status": "covered" if decisions else "missing",
                "sample_quality": "missing" if not decisions else "sparse" if len(pnls) < 2 else "supported",
                "costs": asdict(costs),
            })
            directional_pnls[direction].extend(pnls)
    directional_summary = {direction: {"expected_return": metric_summary(directional_pnls[direction]), "sample_quality": "sparse" if len(directional_pnls[direction]) < 2 else "supported"} for direction in DIRECTIONS}
    return {"mode": mode, "diagnostic_threshold": threshold, "results": results, "directional_summary": directional_summary}


def compare(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    report_only = {(r["strategy"], r["direction"]): r for r in runs[1]["results"]}
    factored = {(r["strategy"], r["direction"]): r for r in runs[2]["results"]}
    changes = []
    for key in sorted(report_only):
        before, after = report_only[key], factored[key]
        old = before["net_expectancy"]["value"]
        new = after["net_expectancy"]["value"]
        delta = None if old is None or new is None else new - old
        meaningful = after["blocked_executions"] > before["blocked_executions"] or (delta is not None and old is not None and abs(delta) >= max(0.001, abs(old) * 0.10))
        if meaningful:
            changes.append({"strategy": key[0], "direction": key[1], "report_only_expectancy": old, "factored_expectancy": new, "expectancy_delta": delta, "blocked_delta": after["blocked_executions"] - before["blocked_executions"], "meaningful": True})
    return changes


def markdown(report: dict[str, Any]) -> str:
    def fmt(value: Any) -> str:
        return "—" if value is None else "∞" if value == "infinite" else f"{value:.6f}"

    lines = ["# Diagnostic ablation replay", "", f"Input: `{report['input']}`", f"Input SHA-256: `{report['input_sha256']}`", f"Configuration hash: `{report['configuration_hash']}`", "Modes: " + ", ".join(report["modes"]), "", "Missing and invalid diagnostics are counted separately and never treated as zero.", "", "| Strategy | Direction | Mode | Samples | Trades | Blocked | Missing | Invalid | Avg win | Avg loss | Expectancy | PF | Drawdown | Frequency |", "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for run in report["runs"]:
        for row in run["results"]:
            lines.append(f"| {row['strategy']} | {row['direction']} | {row['mode']} | {row['sample_count']} | {row['executed_trades']} | {row['blocked_executions']} | {row['unavailable_diagnostics']} | {row['invalid_diagnostics']} | {fmt(row['average_win']['value'])} | {fmt(row['average_loss']['value'])} | {fmt(row['net_expectancy']['value'])} | {fmt(row['profit_factor'])} | {fmt(row['max_drawdown'])} | {fmt(row['trade_frequency'])} |")
    lines += ["", "## Directional expected return", ""]
    for run in report["runs"]:
        for direction, summary in run["directional_summary"].items():
            lines.append(f"- {run['mode']} {direction}: {fmt(summary['expected_return']['value'])} (n={summary['expected_return']['sample_count']}, {summary['sample_quality']})")
    lines += ["", "## Audit", "", f"- Coverage: `{report['audit']['coverage_status']}`", f"- Duplicate row keys: `{len(report['audit']['duplicate_row_keys'])}`", f"- Sparse groups: `{report['audit']['sparse_group_count']}`", f"- Data identifier: `{report['provenance']['data_id']}`", f"- Seed: `{report['provenance']['seed']}`", "- Offline only: `true`; live orders enabled: `false`", "", "## Meaningful factored changes", ""]
    lines += ([f"- {item['strategy']} {item['direction']}: blocked delta {item['blocked_delta']}, expectancy {item['report_only_expectancy']} -> {item['factored_expectancy']}" for item in report["meaningful_changes"]] or ["- None"])
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
    parser.add_argument("--data-id", default="diagnostic_ablation_fixture")
    parser.add_argument("--seed", default="fixed-fixture-v1")
    args = parser.parse_args()
    costs = CostModel(args.fee_rate, args.spread_bps, args.slippage_bps)
    rows, row_audit = load_rows(args.input)
    config = {"cost_model": asdict(costs), "diagnostic_threshold": args.diagnostic_threshold, "modes": MODES, "strategies": STRATEGIES, "directions": DIRECTIONS, "data_id": args.data_id, "seed": args.seed}
    runs = [replay(rows, mode, costs, args.diagnostic_threshold) for mode in MODES]
    coverage = {(row["strategy"], row["direction"]) for row in rows}
    expected = {(strategy, direction) for strategy in STRATEGIES for direction in DIRECTIONS}
    report = {"schema_version": 2, "input": str(args.input), "input_sha256": sha256_bytes(args.input.read_bytes()), "configuration_hash": canonical_hash(config), "configuration": config, "modes": list(MODES), "offline_only": True, "live_orders_enabled": False, "provenance": {"data_id": args.data_id, "seed": args.seed, "code": "tools/replay_diagnostic_ablation.py"}, "runs": runs, "meaningful_changes": compare(runs), "audit": {**row_audit, "expected_group_count": len(expected), "observed_group_count": len(coverage), "missing_groups": [list(group) for group in sorted(expected - coverage)], "unexpected_groups": [list(group) for group in sorted(coverage - expected)], "sparse_group_count": sum(result["sample_quality"] == "sparse" for run in runs for result in run["results"]), "coverage_status": "complete" if coverage == expected and not row_audit["duplicate_row_keys"] else "incomplete"}}
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    args.markdown_out.write_text(markdown(report), encoding="utf-8")


if __name__ == "__main__":
    main()
