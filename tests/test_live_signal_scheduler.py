"""Deterministic tests for bounded live signal scheduling."""

import asyncio
import unittest

from trade_bot.trading.live_signal_scheduler import (
    BoundedQuoteScheduler,
    IntentLedger,
    SchedulerConfig,
)


class BoundedQuoteSchedulerTests(unittest.IsolatedAsyncioTestCase):
    async def test_selected_universe_is_bounded_and_each_symbol_is_evaluated(self):
        scheduler = BoundedQuoteScheduler(SchedulerConfig(
            queue_capacity=3, max_concurrency=2, request_rate=100, request_burst=2,
        ))
        await scheduler.enqueue(["ETH-USD", "BTC-USD", "ETH-USD"])
        seen = []

        async def fetch(symbol):
            seen.append(symbol)
            return {"symbol": symbol, "observed_at": scheduler.budget._clock()}

        result = await scheduler.run(fetch)
        self.assertEqual({item["symbol"] for item in result}, {"ETH-USD", "BTC-USD"})
        self.assertEqual(len(seen), 2)
        self.assertEqual(scheduler.diagnostics()["queue_depth"], 0)

    async def test_queue_overflow_is_explicit(self):
        scheduler = BoundedQuoteScheduler(SchedulerConfig(queue_capacity=1))
        with self.assertRaises(OverflowError):
            await scheduler.enqueue(["BTC-USD", "ETH-USD"])
        self.assertEqual(scheduler.diagnostics()["metrics"]["queue_rejected"], 1)

    async def test_timeout_retry_and_stop_cancel(self):
        scheduler = BoundedQuoteScheduler(SchedulerConfig(
            queue_capacity=2, max_concurrency=1, request_rate=100, request_burst=1,
            max_attempts=1, request_timeout=0.01,
        ))
        await scheduler.enqueue(["BTC-USD"])

        async def slow_fetch(_):
            await asyncio.sleep(1)
            return {"symbol": "BTC-USD", "observed_at": scheduler.budget._clock()}

        task = asyncio.create_task(scheduler.run(slow_fetch))
        await asyncio.sleep(0)
        scheduler.cancel()
        self.assertEqual(await task, [])
        self.assertGreaterEqual(scheduler.diagnostics()["metrics"].get("cancelled", 0), 1)


class IntentLedgerTests(unittest.IsolatedAsyncioTestCase):
    async def test_reservation_is_atomic_per_session_and_symbol(self):
        ledger = IntentLedger()
        outcomes = await asyncio.gather(*(
            ledger.reserve_once("session", "BTC-USD") for _ in range(8)
        ))
        self.assertEqual(sum(outcomes), 1)
        await ledger.release("session", "BTC-USD")
        self.assertTrue(await ledger.reserve_once("session", "BTC-USD"))


if __name__ == "__main__":
    unittest.main()
