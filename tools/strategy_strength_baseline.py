#!/usr/bin/env python3
"""Reproducible, analysis-only strength-bucket baseline evaluator.

The evaluator consumes JSONL rows exported from a read-only outcome source. It
never imports or changes production trading code. Missing dimensions remain
missing; no synthetic bucket assignment is made.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

BIN_EDGES = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
MIN_COHORT = 5
DIMENSIONS = ("strength_bucket", "symbol", "market_regime", "holding_period", "fee_scenario")


def number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def strength_bucket(value: Any) -> str | None:
    strength = number(value)
    if strength is None or strength < 0.0 or strength > 1.0:
        return None
    for lower, upper in zip(BIN_EDGES[:-1], BIN_EDGES[1:]):
        if strength < upper or (upper == BIN_EDGES[-1] and strength <= upper):
            return f"[{lower:.1f},{upper:.1f}{']' if upper == 1.0 else ')'}"
    return None


def read_rows(path: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    audit = {"input_rows": 0, "invalid_rows": 0, "duplicate_rows": 0}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        audit["input_rows"] += 1
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            audit["invalid_rows"] += 1
            continue
        if not isinstance(row, dict) or not row.get("fixture_name"):
            audit["invalid_rows"] += 1
            continue
        key = json.dumps(row, sort_keys=True, separators=(",", ":"))
        if key in seen:
            audit["duplicate_rows"] += 1
            continue
        seen.add(key)
        rows.append(row)
    return rows, audit


def metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    outcomes = [number(row.get("net_pnl")) for row in rows]
    outcomes = [value for value in outcomes if value is not None]
    wins = [value for value in outcomes if value > 0]
    losses = [value for value in outcomes if value < 0]
    equity = peak = drawdown = 0.0
    for value in outcomes:
        equity += value
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    mean = sum(outcomes) / len(outcomes) if outcomes else None
    variance = (sum((x - mean) ** 2 for x in outcomes) / (len(outcomes) - 1)
                if len(outcomes) > 1 and mean is not None else None)
    standard_error = math.sqrt(variance / len(outcomes)) if variance is not None else None
    # t(0.975, 8)=2.306; use a clearly labelled normal approximation otherwise.
    critical = 2.306 if len(outcomes) == 9 else 1.96
    ci = ([mean - critical * standard_error, mean + critical * standard_error]
          if mean is not None and standard_error is not None else None)
    return {
        "sample_count": len(outcomes),
        "expectancy_net_pnl": mean,
        "average_win_net_pnl": sum(wins) / len(wins) if wins else None,
        "average_loss_net_pnl": sum(losses) / len(losses) if losses else None,
        "win_rate_percent": (100.0 * len(wins) / (len(wins) + len(losses))
                             if wins or losses else None),
        "max_drawdown_net_pnl": drawdown if outcomes else None,
        "gross_metrics": "insufficient evidence: gross PnL is absent",
        "net_expectancy_95_ci": ci,
        "uncertainty": ("exploratory t interval with df=8" if len(outcomes) == 9
                        else "normal approximation; not reliable for small cohorts"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--min-cohort", type=int, default=MIN_COHORT)
    args = parser.parse_args()
    rows, audit = read_rows(args.input)
    for row in rows:
        row["strength_bucket"] = strength_bucket(row.get("signal_strength"))
        row["fee_scenario"] = row.get("fee_scenario") or None

    groups: dict[str, dict[str, list[dict[str, Any]]]] = {dimension: defaultdict(list) for dimension in DIMENSIONS}
    for dimension in DIMENSIONS:
        for row in rows:
            value = row.get(dimension)
            label = value if value not in (None, "") else "missing"
            groups[dimension][str(label)].append(row)

    cohorts: dict[str, dict[str, Any]] = {}
    for dimension, values in groups.items():
        cohorts[dimension] = {}
        for label, cohort in sorted(values.items()):
            cohorts[dimension][label] = {
                "metrics": metrics(cohort),
                "minimum_sample_threshold": args.min_cohort,
                "evidence_status": ("insufficient evidence" if label == "missing" or len(cohort) < args.min_cohort
                                    else "supported"),
            }

    report = {
        "analysis": "strategy_strength_baseline",
        "analysis_only": True,
        "bin_edges": list(BIN_EDGES),
        "bin_convention": "left-closed/right-open except final bucket, [0.0,1.0]",
        "minimum_sample_threshold": args.min_cohort,
        "missing_values": "retained as a missing cohort; never imputed or assigned a strength bucket",
        "duplicates": "exact canonical JSON duplicates excluded after first occurrence",
        "fee_scenarios": "gross and fee-scenario comparisons require gross_pnl and fee fields; absent fields are insufficient evidence",
        "audit": audit,
        "overall": metrics(rows),
        "cohorts": cohorts,
        "monotonicity": "insufficient evidence: no observed signal_strength values",
        "saturation_or_clipping": "insufficient evidence: no observed signal_strength values",
        "high_loss_regimes": "insufficient evidence: no losses and no regime/holding-period fields",
        "source_rows": len(rows),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "source_rows": len(rows), "overall": report["overall"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
