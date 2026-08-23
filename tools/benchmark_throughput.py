#!/usr/bin/env python3
"""Bounded simulated trading throughput benchmark.

This benchmark never enables live order execution and never calls a live start
endpoint. It records raw status snapshots as JSONL and a summary JSON so a
remote runtime can be reproduced without a compiler or exchange credentials.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, quantiles
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def request(base: str, method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, float, Any]:
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(urllib.request.Request(base + path, data=body, headers=headers, method=method), timeout=15) as response:
            value = json.loads(response.read())
            return response.status, (time.perf_counter() - started) * 1000.0, value
    except urllib.error.HTTPError as error:
        raw = error.read().decode(errors="replace")
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = {"error": raw}
        return error.code, (time.perf_counter() - started) * 1000.0, value


def process_cpu_seconds() -> float | None:
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            comm = (entry / "comm").read_text().strip()
            if comm != "trading_bot_cpp":
                continue
            fields = (entry / "stat").read_text().split()
            return (int(fields[13]) + int(fields[14])) / float(os.sysconf("SC_CLK_TCK"))
        except (FileNotFoundError, PermissionError, ValueError, IndexError):
            continue
    return None


def compact(status: int, latency_ms: float, payload: Any, scenario: str, sample_at: str) -> dict[str, Any]:
    value = payload if isinstance(payload, dict) else {}
    diagnostics = value.get("order_book_signal_diagnostics", {})
    return {
        "sample_at": sample_at,
        "scenario": scenario,
        "http_status": status,
        "request_latency_ms": round(latency_ms, 3),
        "active": value.get("is_active"),
        "tick": value.get("tick"),
        "selected_symbols": len(value.get("symbols", [])),
        "signals_evaluated": diagnostics.get("signals_evaluated"),
        "signals_generated": diagnostics.get("signals_generated"),
        "latest_signals": diagnostics.get("current_latest_signal_count", diagnostics.get("recent_signal_record_count")),
        "pending_order_count": value.get("pending_order_count"),
        "pending_reserved_cash": value.get("pending_reserved_cash"),
        "blockers": diagnostics.get("execution_blocker_counts", value.get("execution_blocker_counts", {})),
        "cpu_seconds": process_cpu_seconds(),
        "raw": value,
    }


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return quantiles(values, n=100, method="inclusive")[int(p) - 1]


def rounded_percentile(values: list[float], p: float) -> float | None:
    value = percentile(values, p)
    return round(value, 3) if value is not None else None


def wait_for_stopped(base: str, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status, _, value = request(base, "GET", "/api/trading/simulated/status")
        if status < 300 and isinstance(value, dict) and not value.get("is_active", False):
            return
        time.sleep(0.25)
    raise RuntimeError("simulated worker did not settle within the benchmark timeout")


def run_scenario(base: str, scenario: str, symbols: list[str], duration: float, interval: float, out) -> list[dict[str, Any]]:
    request(base, "POST", "/api/trading/simulated/stop")
    wait_for_stopped(base)
    payload = {
        "session_id": f"bench-{scenario}-{int(time.time())}",
        "strategy": "orderbook",
        "symbols": symbols,
        "parameters": {
            "execution_mode": "simulated",
            "initial_capital": 10000,
            "live_order_execution": False,
        },
    }
    status, latency, value = request(base, "POST", "/api/trading/simulated/start", payload)
    for _ in range(20):
        if not (isinstance(value, dict) and value.get("status") == "settling"):
            break
        time.sleep(0.5)
        status, latency, value = request(base, "POST", "/api/trading/simulated/start", payload)
    if isinstance(value, dict) and value.get("status") == "settling":
        raise RuntimeError(f"simulated worker did not accept {scenario} after settling retries")
    samples = [compact(status, latency, value, scenario, utc_now())]
    out.write(json.dumps(samples[-1], separators=(",", ":")) + "\n")
    out.flush()
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        status, latency, value = request(base, "GET", "/api/trading/simulated/status")
        sample = compact(status, latency, value, scenario, utc_now())
        samples.append(sample)
        out.write(json.dumps(sample, separators=(",", ":")) + "\n")
        out.flush()
        time.sleep(interval)
    status, latency, value = request(base, "POST", "/api/trading/simulated/stop")
    sample = compact(status, latency, value, scenario, utc_now())
    samples.append(sample)
    out.write(json.dumps(sample, separators=(",", ":")) + "\n")
    out.flush()
    wait_for_stopped(base)
    return samples


def summarize(samples: list[dict[str, Any]]) -> dict[str, Any]:
    active = [x for x in samples if x.get("active")]
    latencies = [x["request_latency_ms"] for x in samples if isinstance(x.get("request_latency_ms"), (int, float))]
    ticks = [x["tick"] for x in active if isinstance(x.get("tick"), int)]
    symbols = [x["selected_symbols"] for x in active]
    pending = [x["pending_order_count"] for x in active if isinstance(x.get("pending_order_count"), int)]
    generated = [x["signals_generated"] for x in active if isinstance(x.get("signals_generated"), int)]
    return {
        "samples": len(samples),
        "active_samples": len(active),
        "selected_symbols": max(symbols, default=0),
        "tick_first_last": [ticks[0], ticks[-1]] if ticks else [],
        "ticks_per_active_second_estimate": round((ticks[-1] - ticks[0]) / max(1, len(active) - 1), 3) if len(ticks) > 1 else None,
        "request_latency_ms": {
            "min": round(min(latencies), 3) if latencies else None,
            "mean": round(mean(latencies), 3) if latencies else None,
            "p50": rounded_percentile(latencies, 50),
            "p95": rounded_percentile(latencies, 95),
            "max": round(max(latencies), 3) if latencies else None,
        },
        "max_pending_order_count": max(pending, default=0),
        "max_signals_generated_per_snapshot": max(generated, default=0),
        "all_samples_http_2xx": all(x.get("http_status", 500) < 300 for x in samples),
        "all_paper_execution": all(x.get("raw", {}).get("execution_is_paper") is True for x in samples),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8081")
    parser.add_argument("--duration", type=float, default=6.0)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--output", type=Path, default=Path("docs/benchmarks/throughput-samples.jsonl"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    normal = ["BTC-USD", "ETH-USD", "SOL-USD"]
    overload = [f"BENCH-{i:03d}-USD" for i in range(64)]
    all_samples: dict[str, list[dict[str, Any]]] = {}
    with args.output.open("w", encoding="utf-8") as out:
        for name, symbols in (("normal-3-symbol", normal), ("overload-64-symbol", overload)):
            all_samples[name] = run_scenario(args.base_url, name, symbols, args.duration, args.interval, out)
    summary = {
        "generated_at": utc_now(),
        "base_url": args.base_url,
        "duration_seconds": args.duration,
        "poll_interval_seconds": args.interval,
        "scenarios": {name: summarize(samples) for name, samples in all_samples.items()},
        "safety": {
            "live_start_called": False,
            "live_order_execution_enabled": False,
            "max_requested_symbols": 64,
            "unbounded_fanout_in_benchmark": False,
            "note": "The overload scenario is a bounded 64-symbol synthetic session; it is not evidence of Coinbase capacity or live rate-limit compliance.",
        },
    }
    summary_path = args.output.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
