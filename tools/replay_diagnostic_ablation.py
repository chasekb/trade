#!/usr/bin/env python3
"""Offline deterministic diagnostic ablation/replay harness (no live orders)."""
from __future__ import annotations
import argparse, json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

MODES = ("disabled", "report-only", "factored")
STRATEGIES = ("orderbook", "ml_enhanced_orderbook", "ml", "sma", "ema", "rsi", "bollinger", "macd", "stochastic", "fibonacci", "atr", "dca", "buy_and_hold")
DIRECTIONS = ("buy", "sell")

@dataclass(frozen=True)
class CostModel:
    fee_rate: float = .001
    spread_bps: float = 2.0
    slippage_bps: float = 1.0
    def __post_init__(self):
        if min(self.fee_rate, self.spread_bps, self.slippage_bps) < 0: raise ValueError("costs must be non-negative")
    def round_trip_cost(self) -> float:
        return 2 * self.fee_rate + 2 * (self.spread_bps + self.slippage_bps) / 10_000

def load_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if not line.strip() or line.lstrip().startswith("#"): continue
            row = json.loads(line)
            required = {"timestamp", "strategy", "direction", "entry_price", "exit_price"}
            if missing := required - row.keys(): raise ValueError(f"{path}:{n}: missing {sorted(missing)}")
            if row["strategy"] not in STRATEGIES: raise ValueError(f"{path}:{n}: unsupported strategy")
            if row["direction"] not in DIRECTIONS: raise ValueError(f"{path}:{n}: unsupported direction")
            rows.append(row)
    if not rows: raise ValueError(f"{path}: no replay rows")
    return rows

def diagnostic(row):
    value = row.get("diagnostic_score")
    return (None, "unavailable") if value is None else (float(value), "available")

def gross_return(row):
    sign = 1 if row["direction"] == "buy" else -1
    return sign * (float(row["exit_price"]) - float(row["entry_price"])) / float(row["entry_price"])

def replay(rows: Iterable[dict[str, Any]], mode: str, costs: CostModel, threshold: float):
    if mode not in MODES: raise ValueError(f"mode must be one of {MODES}")
    groups = defaultdict(list)
    for source in rows:
        row = dict(source); score, status = diagnostic(row)
        row.update(_diagnostic_score=score, _diagnostic_status=status,
                   _blocked=mode == "factored" and (score is None or score < threshold))
        groups[(row["strategy"], row["direction"])].append(row)
    results = []
    for (strategy, direction), decisions in sorted(groups.items()):
        executed = [r for r in decisions if not r["_blocked"]]
        pnls = [gross_return(r) - costs.round_trip_cost() for r in executed]
        wins, losses = [p for p in pnls if p > 0], [p for p in pnls if p < 0]
        equity = peak = 1.0; drawdown = 0.0
        for pnl in pnls:
            equity *= 1 + pnl; peak = max(peak, equity); drawdown = max(drawdown, (peak - equity) / peak)
        unavailable = sum(r["_diagnostic_status"] == "unavailable" for r in decisions)
        results.append({"strategy": strategy, "direction": direction, "mode": mode,
            "input_decisions": len(decisions), "entries": len(decisions), "exits": len(executed), "executed_trades": len(executed),
            "blocked_executions": len(decisions) - len(executed), "unavailable_diagnostics": unavailable,
            "diagnostics_available": len(decisions) - unavailable, "wins": len(wins), "losses": len(losses),
            "average_win": sum(wins) / len(wins) if wins else None, "average_loss": sum(losses) / len(losses) if losses else None,
            "net_expectancy": sum(pnls) / len(pnls) if pnls else None,
            "profit_factor": sum(wins) / abs(sum(losses)) if losses else None, "max_drawdown": drawdown,
            "trade_frequency": len(executed) / len(decisions), "net_return": equity - 1.0,
            "costs": {"fee_rate": costs.fee_rate, "spread_bps": costs.spread_bps, "slippage_bps": costs.slippage_bps}})
    return {"mode": mode, "diagnostic_threshold": threshold, "results": results}

def compare(runs):
    before = {(r["strategy"], r["direction"]): r for r in runs[1]["results"]}; after = {(r["strategy"], r["direction"]): r for r in runs[2]["results"]}
    out = []
    for key in sorted(before):
        old, new = before[key], after[key]; a, b = old["net_expectancy"], new["net_expectancy"]
        meaningful = old["blocked_executions"] != new["blocked_executions"] or (a is not None and b is not None and abs(b-a) >= max(.001, abs(a)*.10))
        if meaningful: out.append({"strategy": key[0], "direction": key[1], "report_only_expectancy": a, "factored_expectancy": b, "blocked_delta": new["blocked_executions"]-old["blocked_executions"], "meaningful": True})
    return out

def fmt(v): return "—" if v is None else f"{v:.6f}"
def markdown(report):
    c = report["cost_model"]
    lines = ["# Diagnostic ablation replay", "", f"Input: `{report['input']}`", "Modes: " + ", ".join(report["modes"]), f"Cost model: fee={c['fee_rate']}, spread={c['spread_bps']} bps, slippage={c['slippage_bps']} bps", "", "Missing diagnostics are counted as `unavailable`, never as zero.", "", "| Strategy | Direction | Mode | Trades | Blocked | Unavailable | Avg win | Avg loss | Expectancy | PF | Drawdown | Frequency |", "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for run in report["runs"]:
        for r in run["results"]: lines.append(f"| {r['strategy']} | {r['direction']} | {r['mode']} | {r['executed_trades']} | {r['blocked_executions']} | {r['unavailable_diagnostics']} | {fmt(r['average_win'])} | {fmt(r['average_loss'])} | {fmt(r['net_expectancy'])} | {fmt(r['profit_factor'])} | {r['max_drawdown']:.6f} | {r['trade_frequency']:.6f} |")
    lines += ["", "## Meaningful regressions", ""] + ([f"- {x['strategy']} {x['direction']}: blocked delta {x['blocked_delta']}, expectancy {x['report_only_expectancy']} -> {x['factored_expectancy']}" for x in report["meaningful_regressions"]] or ["- None"])
    return "\n".join(lines) + "\n"

def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("--input", type=Path, required=True); p.add_argument("--json-out", type=Path, required=True); p.add_argument("--markdown-out", type=Path, required=True); p.add_argument("--fee-rate", type=float, default=.001); p.add_argument("--spread-bps", type=float, default=2.0); p.add_argument("--slippage-bps", type=float, default=1.0); p.add_argument("--diagnostic-threshold", type=float, default=.60); a = p.parse_args()
    costs = CostModel(a.fee_rate, a.spread_bps, a.slippage_bps); rows = load_rows(a.input); runs = [replay(rows, mode, costs, a.diagnostic_threshold) for mode in MODES]
    report = {"schema_version": 1, "input": str(a.input), "modes": list(MODES), "offline_only": True, "live_orders_enabled": False, "cost_model": costs.__dict__, "runs": runs}; report["meaningful_regressions"] = compare(runs)
    a.json_out.parent.mkdir(parents=True, exist_ok=True); a.markdown_out.parent.mkdir(parents=True, exist_ok=True); a.json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"); a.markdown_out.write_text(markdown(report), encoding="utf-8")
if __name__ == "__main__": main()
