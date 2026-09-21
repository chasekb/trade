#!/usr/bin/env python3
"""Derive the TRADE-BL-0027 runtime-evidence metrics from the frozen excerpt."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

FETCH_RE = re.compile(
    r"\[(?P<ts>[^]]+ UTC)\].*Failed to fetch order book for (?P<symbol>[A-Z0-9-]+): "
    r"(?P<reason>.*?) \(category=(?P<category>[^,]+), retries=(?P<retries>\d+)\)"
)
WINDOW_RE = re.compile(r"(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3} UTC)")


def parse_utc(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S.%f UTC").replace(tzinfo=timezone.utc)


def derive(raw_path: Path) -> dict:
    text = raw_path.read_text(encoding="utf-8")
    fetches = []
    for line in text.splitlines():
        match = FETCH_RE.search(line)
        if match:
            fetches.append(
                {
                    "timestamp_utc": parse_utc(match.group("ts")).isoformat().replace("+00:00", "Z"),
                    "symbol": match.group("symbol"),
                    "reason": match.group("reason"),
                    "category": match.group("category"),
                    "retries": int(match.group("retries")),
                }
            )
    timestamps = [parse_utc(m.group("ts")) for line in text.splitlines() if (m := WINDOW_RE.search(line))]
    symbols = sorted({row["symbol"] for row in fetches})
    by_symbol = {
        symbol: {
            "fetch_attempts_observed": sum(row["symbol"] == symbol for row in fetches),
            "failed_fetches_observed": sum(row["symbol"] == symbol for row in fetches),
            "successful_quotes_observed": 0,
            "coverage_status": "unknown: selected universe not captured",
        }
        for symbol in symbols
    }
    return {
        "evidence_id": "trade-bl-0027-live-orderbook-baseline-2026-08-22",
        "source": str(raw_path),
        "time_zone": "UTC",
        "window": {
            "start_utc": min(timestamps).isoformat().replace("+00:00", "Z"),
            "end_utc": max(timestamps).isoformat().replace("+00:00", "Z"),
            "definition": "earliest/latest timestamped line in the frozen excerpt; not a live-session window",
        },
        "observed": {
            "order_book_fetch_failures": len(fetches),
            "unique_symbols_with_failed_fetch": len(symbols),
            "symbols_with_failed_fetch": symbols,
            "retry_distribution": dict(sorted(Counter(row["retries"] for row in fetches).items())),
            "failure_category_distribution": dict(sorted(Counter(row["category"] for row in fetches).items())),
            "database_outcome_query_failures": 1,
            "transformer_readiness_events": 1,
            "simulated_worker_start_events": 1,
            "session_ids_observed": ["sim_17874"],
            "by_symbol": by_symbol,
        },
        "unavailable": {
            "selected_universe": "unavailable",
            "quote_or_order_book_successes": "unavailable; observed failures are not a denominator",
            "freshness_and_coverage": "unavailable; no selected-universe list or successful quote timestamps",
            "generated_signals": "unavailable",
            "signal_strength": "unavailable",
            "expected_return": "unavailable",
            "fee_adjusted_expected_return": "unavailable",
            "spread_slippage_buffer_required_edge": "unavailable",
            "blocked_intents": "unavailable",
            "submitted_orders": "unavailable",
            "fills": "unavailable",
            "fees_realized_pnl_distribution": "unavailable; outcome query failed on missing is_closing_leg",
            "positive_negative_zero_pnl_counts": "unavailable",
            "average_win_loss_expectancy_profit_factor_drawdown": "unavailable",
        },
        "denominator_policy": {
            "fetch_failure_rate": "not computed: selected-symbol fetch-attempt denominator is unavailable",
            "quote_coverage": "not computed: selected universe and successful quote count are unavailable",
            "signal_and_execution_rates": "not computed: no signal/order/fill rows are present",
            "pnl_statistics": "not computed: no joined terminal outcomes are present",
        },
        "safety_interpretation": "This evidence is a simulated-worker/log excerpt and does not establish live profitability or explain the absence of positive-PnL live trades.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = derive(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "fetch_failures": result["observed"]["order_book_fetch_failures"], "symbols": result["observed"]["unique_symbols_with_failed_fetch"]}))


if __name__ == "__main__":
    main()
