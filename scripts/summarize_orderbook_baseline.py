import csv
import json
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "artifacts/orderbook-signal-baseline-1h.csv"
rows = list(csv.DictReader(path.open()))

def number(row, key):
    value = row[key]
    return float(value) if value else 0.0

keys = ["signals_evaluated", "signals_generated", "executable_intents", "blocked_intents", "realized_pnl", "closing_legs", "winners", "losers"]
sums = {key: sum(number(row, key) for row in rows) for key in keys}
summary = {
    "groups": len(rows),
    "symbols": len({row["symbol"] for row in rows}),
    "sums": sums,
    "weighted_avg_signal_strength": sum(number(row, "avg_signal_strength") * number(row, "signals_evaluated") for row in rows) / sums["signals_evaluated"],
    "weighted_avg_expected_return_generated": sum(number(row, "avg_expected_return") * number(row, "signals_generated") for row in rows) / sums["signals_generated"],
    "weighted_avg_fee_adjusted_expected_return_generated": sum(number(row, "avg_fee_adjusted_expected_return") * number(row, "signals_generated") for row in rows) / sums["signals_generated"],
    "blocked_rate_pct": 100 * sums["blocked_intents"] / sums["signals_generated"],
    "intent_conversion_rate_pct": 100 * sums["executable_intents"] / sums["signals_generated"],
}
print(json.dumps(summary, indent=2))
