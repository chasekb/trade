"""Bounded, cancellation-safe scheduling primitives for live signal generation.

The scheduler is deliberately provider agnostic: quote fetching and signal
calculation remain owned by the caller, while this module owns capacity,
ordering, retries, freshness, and observability.
"""

from __future__ import annotations

import asyncio
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class SchedulerConfig:
    """Explicit limits for one live signal scheduler."""

    queue_capacity: int = 500
    max_concurrency: int = 4
    request_rate: float = 20.0
    request_burst: int = 4
    max_attempts: int = 2
    request_timeout: float = 10.0
    max_quote_age: float = 5.0
    retention: int = 1000

    def __post_init__(self) -> None:
        if self.queue_capacity < 1:
            raise ValueError("queue_capacity must be positive")
        if self.max_concurrency < 1:
            raise ValueError("max_concurrency must be positive")
        if self.request_rate <= 0 or self.request_burst < 1:
            raise ValueError("request budget must be positive")
        if self.max_attempts < 1 or self.request_timeout <= 0:
            raise ValueError("retry and timeout settings must be positive")


class ExchangeBudget:
    """Async token bucket shared by all quote requests for a provider."""

    def __init__(self, rate: float, burst: int, clock: Callable[[], float] = time.monotonic):
        if rate <= 0 or burst < 1:
            raise ValueError("rate and burst must be positive")
        self.rate = float(rate)
        self.burst = int(burst)
        self._tokens = float(burst)
        self._updated = clock()
        self._clock = clock
        self._lock = asyncio.Lock()
        self.denied = 0
        self.acquired = 0

    async def acquire(self, cost: float = 1.0) -> None:
        if cost <= 0 or cost > self.burst:
            raise ValueError("cost must be within the burst capacity")
        while True:
            async with self._lock:
                now = self._clock()
                self._tokens = min(self.burst, self._tokens + (now - self._updated) * self.rate)
                self._updated = now
                if self._tokens >= cost:
                    self._tokens -= cost
                    self.acquired += 1
                    return
                wait_for = (cost - self._tokens) / self.rate
                self.denied += 1
            await asyncio.sleep(wait_for)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "rate_per_second": self.rate,
            "burst": self.burst,
            "acquired": self.acquired,
            "denied": self.denied,
            "available_tokens": max(0.0, self._tokens),
        }


@dataclass(order=True)
class _WorkItem:
    priority: tuple = field(compare=True)
    sequence: int = field(compare=True)
    symbol: str = field(compare=False)
    attempt: int = field(default=0, compare=False)
    enqueued_at: float = field(default_factory=time.monotonic, compare=False)


class BoundedQuoteScheduler:
    """Run a full selected universe with bounded, freshness-first work."""

    def __init__(self, config: SchedulerConfig | None = None):
        self.config = config or SchedulerConfig()
        self.budget = ExchangeBudget(self.config.request_rate, self.config.request_burst)
        self._queue: asyncio.PriorityQueue[_WorkItem] = asyncio.PriorityQueue(self.config.queue_capacity)
        self._sequence = 0
        self._cancelled = asyncio.Event()
        self._inflight: set[str] = set()
        self._metrics = Counter()
        self._latest: Dict[str, Dict[str, Any]] = {}
        self._retained: deque[Dict[str, Any]] = deque(maxlen=self.config.retention)
        self._workers: set[asyncio.Task[Any]] = set()

    async def enqueue(self, symbols: Iterable[str], freshness: Optional[Dict[str, float]] = None) -> int:
        """Enqueue each selected symbol once; reject overflow explicitly."""
        freshness = freshness or {}
        unique = list(dict.fromkeys(str(s) for s in symbols))
        if len(unique) > self.config.queue_capacity:
            self._metrics["queue_rejected"] += len(unique) - self.config.queue_capacity
            raise OverflowError("selected universe exceeds bounded quote queue capacity")
        for symbol in unique:
            age = float(freshness.get(symbol, float("inf")))
            # Older data receives lower priority; universe order breaks ties.
            item = _WorkItem(priority=(-age, self._sequence), sequence=self._sequence, symbol=symbol)
            self._sequence += 1
            await self._queue.put(item)
            self._metrics["enqueued"] += 1
        return len(unique)

    async def run(
        self,
        fetch: Callable[[str], Awaitable[Dict[str, Any]]],
        *,
        generation: int = 0,
        now: Callable[[], float] = time.monotonic,
    ) -> List[Dict[str, Any]]:
        """Drain one sweep and return only current-generation fresh results."""
        self._cancelled.clear()
        results: List[Dict[str, Any]] = []
        lock = asyncio.Lock()

        async def worker() -> None:
            while not self._cancelled.is_set():
                try:
                    item = self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                if item.symbol in self._inflight:
                    self._queue.task_done()
                    self._metrics["duplicate_skipped"] += 1
                    continue
                self._inflight.add(item.symbol)
                try:
                    self._metrics["attempted"] += 1
                    await self.budget.acquire()
                    value = await asyncio.wait_for(fetch(item.symbol), self.config.request_timeout)
                    if self._cancelled.is_set() or value.get("generation", generation) != generation:
                        self._metrics["cancelled"] += 1
                    elif now() - float(value.get("observed_at", now())) > self.config.max_quote_age:
                        self._metrics["stale_dropped"] += 1
                    else:
                        async with lock:
                            self._latest[item.symbol] = value
                            self._retained.append(value)
                            results.append(value)
                        self._metrics["succeeded"] += 1
                except asyncio.CancelledError:
                    raise
                except (asyncio.TimeoutError, OSError, ConnectionError) as exc:
                    if item.attempt + 1 < self.config.max_attempts and not self._cancelled.is_set():
                        retry = _WorkItem(item.priority, self._sequence, item.symbol, item.attempt + 1)
                        self._sequence += 1
                        await self._queue.put(retry)
                        self._metrics["retried"] += 1
                    else:
                        self._metrics["dropped"] += 1
                        self._metrics[type(exc).__name__.lower()] += 1
                except Exception:
                    self._metrics["dropped"] += 1
                    self._metrics["error"] += 1
                finally:
                    self._inflight.discard(item.symbol)
                    self._queue.task_done()

        workers = [asyncio.create_task(worker()) for _ in range(self.config.max_concurrency)]
        self._workers.update(workers)
        try:
            await asyncio.gather(*workers, return_exceptions=True)
        finally:
            self._workers.difference_update(workers)
        return sorted(results, key=lambda item: item.get("symbol", ""))

    def cancel(self) -> Dict[str, Any]:
        """Stop accepting work; in-flight fetches are ignored on completion."""
        self._cancelled.set()
        for worker in tuple(self._workers):
            worker.cancel()
        self._metrics["cancelled"] += len(self._inflight)
        cancelled = 0
        while True:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
                cancelled += 1
            except asyncio.QueueEmpty:
                break
        self._metrics["cancelled"] += cancelled
        return {"cancelled": cancelled, "inflight": len(self._inflight)}

    def diagnostics(self) -> Dict[str, Any]:
        counts = dict(self._metrics)
        return {
            "queue_depth": self._queue.qsize(),
            "inflight": len(self._inflight),
            "max_concurrency": self.config.max_concurrency,
            "configured_exchange_budget": self.budget.snapshot(),
            "latest_symbols": len(self._latest),
            "retained_signals": len(self._retained),
            "normalized_contract": "bounded-live-equivalent",
            "backing_off": bool(counts.get("retried") or counts.get("stale_dropped")),
            "metrics": counts,
        }


class IntentLedger:
    """Atomic per-symbol reservation preventing duplicate live intents."""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._reserved: set[tuple[str, str]] = set()

    async def reserve_once(self, session_id: str, symbol: str) -> bool:
        key = (session_id, symbol)
        async with self._lock:
            if key in self._reserved:
                return False
            self._reserved.add(key)
            return True

    async def release(self, session_id: str, symbol: str) -> None:
        async with self._lock:
            self._reserved.discard((session_id, symbol))
