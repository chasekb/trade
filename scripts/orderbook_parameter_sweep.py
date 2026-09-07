#!/usr/bin/env python3
"""Fixture-backed, fail-closed walk-forward sweep for order-book gates.

This is an offline research harness. It never imports live trading code, reads
credentials, or writes configuration consumed by the bot.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Candidate:
    min_orderbook_signal_strength: float
    orderbook_expected_return_scale_percent: float
    round_trip_fee_percent: float
    slippage_buffer_percent: float
    max_spread_percent: float
    imbalance_weight: float
    position_size_percent: float


@dataclass(frozen=True)
class Observation:
    timestamp: int
    symbol: str
    branch: str
    imbalance: float
    spread_percent: float
    raw_strength: float
    expected_return_percent: float
    future_return_percent: float
    directional_gate: str


def fixture(seed: int = 20260907, symbols: tuple[str, ...] = ("BTC-USD", "ETH-USD", "SOL-USD")) -> list[Observation]:
    """Create a deterministic fixture with train/test-separated timestamps."""
    rng = random.Random(seed)
    rows: list[Observation] = []
    for i in range(240):
        symbol = symbols[i % len(symbols)]
        branch = "ml" if i % 4 == 0 else "baseline"
        imbalance = rng.choice((0.48, 0.62, 0.78, 1.22, 1.38, 1.62, 2.05))
        direction = "buy" if imbalance > 1 else "sell"
        strength = min(abs(math.log(imbalance)), 1.0)
        spread = rng.choice((0.025, 0.05, 0.09, 0.16, 0.28))
        # A few deliberately adverse observations ensure negative expectancy
        # candidates are rejected rather than rewarded for count.
        edge = (strength * 0.34) - (spread * 0.22)
        if i % 17 == 0:
            edge = -0.20
        noise = rng.uniform(-0.08, 0.08)
        future = edge + noise if direction == "buy" else -(edge + noise)
        expected = strength * 0.60 - spread * 0.18
        rows.append(Observation(i, symbol, branch, imbalance, spread, strength, expected, future, direction))
    return rows


def read_rows(path: Path) -> list[Observation]:
    rows: list[Observation] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for item in csv.DictReader(handle):
            rows.append(Observation(
                int(item["timestamp"]), item["symbol"], item.get("branch", "unknown"),
                float(item["imbalance"]), float(item["spread_percent"]),
                float(item["raw_strength"]), float(item["expected_return_percent"]),
                float(item["future_return_percent"]), item["directional_gate"],
            ))
    if not rows:
        raise ValueError("input contains no observations")
    return rows


def write_fixture(path: Path, rows: Iterable[Observation]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(Observation.__dataclass_fields__)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)


def evaluate(candidate: Candidate, rows: list[Observation], split: int) -> dict:
    test_rows = [row for row in rows if row.timestamp >= split]
    accepted: list[float] = []
    rejected = blocked = 0
    by_segment: dict[tuple[str, str], list[float]] = {}
    for row in test_rows:
        directional_strength = row.raw_strength * candidate.imbalance_weight
        estimated = row.expected_return_percent * candidate.orderbook_expected_return_scale_percent / 100
        cost = candidate.round_trip_fee_percent + candidate.slippage_buffer_percent + row.spread_percent
        qualifies = directional_strength >= candidate.min_orderbook_signal_strength
        qualifies = qualifies and row.spread_percent <= candidate.max_spread_percent
        # Preserve direction: a buy must have positive estimated edge and a sell
        # must have negative raw return before costs; no absolute-value shortcut.
        directional_edge = estimated if row.directional_gate == "buy" else -estimated
        if not qualifies:
            blocked += 1
        elif directional_edge <= cost:
            rejected += 1
        else:
            result = (row.future_return_percent if row.directional_gate == "buy" else -row.future_return_percent)
            result -= candidate.round_trip_fee_percent + candidate.slippage_buffer_percent
            result *= candidate.position_size_percent / 100
            accepted.append(result)
            by_segment.setdefault((row.symbol, row.branch), []).append(result)
    wins = [x for x in accepted if x > 0]
    losses = [x for x in accepted if x < 0]
    total = sum(accepted)
    equity = 0.0
    peak = 0.0
    drawdown = 0.0
    for value in accepted:
        equity += value
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    segments = {}
    for key, values in sorted(by_segment.items()):
        seg_exp = sum(values) / len(values)
        segments[f"{key[0]}::{key[1]}"] = {"trades": len(values), "expectancy": round(seg_exp, 8), "negative_expectancy": seg_exp < 0}
    expectancy = total / len(accepted) if accepted else 0.0
    return {
        "trades": len(accepted), "wins": len(wins), "losses": len(losses),
        "average_win": sum(wins) / len(wins) if wins else 0.0,
        "average_loss": sum(losses) / len(losses) if losses else 0.0,
        "expectancy": expectancy,
        "profit_factor": sum(wins) / abs(sum(losses)) if losses else (None if wins else 0.0),
        "max_drawdown": drawdown, "trade_frequency": len(accepted) / len(test_rows),
        "rejected_intent_rate": rejected / len(test_rows), "blocked_intent_rate": blocked / len(test_rows),
        "negative_expectancy": expectancy < 0, "segments": segments,
    }


def sweep(rows: list[Observation], grid: dict[str, list[float]], split: int) -> tuple[dict, list[dict]]:
    baseline = Candidate(0.20, 100.0, 0.10, 0.05, 0.20, 1.0, 2.0)
    candidates: list[dict] = []
    names = list(grid)
    for values in itertools.product(*(grid[name] for name in names)):
        candidate = Candidate(**dict(zip(names, values)))
        metrics = evaluate(candidate, rows, split)
        # Fail closed: negative expectancy candidates cannot win due to count.
        eligible = not metrics["negative_expectancy"] and all(not s["negative_expectancy"] for s in metrics["segments"].values() if s["trades"] >= 8)
        candidates.append({"parameters": asdict(candidate), "eligible": eligible, "metrics": metrics})
    base_metrics = evaluate(baseline, rows, split)
    eligible = [item for item in candidates if item["eligible"]]
    eligible.sort(key=lambda item: (item["metrics"]["expectancy"], item["metrics"]["profit_factor"], -item["metrics"]["max_drawdown"], item["metrics"]["trades"]), reverse=True)
    selected = eligible[0] if eligible else {"parameters": asdict(baseline), "eligible": False, "metrics": base_metrics}
    return {"baseline": {"parameters": asdict(baseline), "metrics": base_metrics}, "selected": selected, "eligible_count": len(eligible)}, candidates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="CSV observations; omitted uses deterministic fixture")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/orderbook-sweep"))
    parser.add_argument("--seed", type=int, default=20260907)
    args = parser.parse_args()
    rows = read_rows(args.input) if args.input else fixture(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    fixture_path = args.output_dir / "fixture.csv"
    if not args.input:
        write_fixture(fixture_path, rows)
    else:
        fixture_path = args.input
    grid = {
        "min_orderbook_signal_strength": [0.15, 0.20, 0.30, 0.40],
        "orderbook_expected_return_scale_percent": [80.0, 100.0, 120.0],
        "round_trip_fee_percent": [0.10, 0.20], "slippage_buffer_percent": [0.03, 0.08],
        "max_spread_percent": [0.10, 0.20, 0.35], "imbalance_weight": [0.8, 1.0, 1.2],
        "position_size_percent": [1.0, 2.0, 4.0],
    }
    summary, candidates = sweep(rows, grid, max(1, int(len(rows) * 0.5)))
    with (args.output_dir / "candidates.jsonl").open("w", encoding="utf-8") as handle:
        for item in candidates:
            handle.write(json.dumps(item, sort_keys=True) + "\n")
    manifest = {"schema": "orderbook-parameter-sweep/v1", "input": str(fixture_path), "rows": len(rows), "train_rows": len(rows) // 2, "test_rows": len(rows) - len(rows) // 2, "grid": grid, "summary": summary, "safety": {"offline_only": True, "live_defaults_changed": False, "negative_expectancy_candidates_rejected": True}}
    manifest["input_sha256"] = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output_dir": str(args.output_dir), "rows": len(rows), "candidates": len(candidates), "selected": summary["selected"]}, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
