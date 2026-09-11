import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path
import sys


SCRIPT = Path(__file__).parents[1] / "scripts" / "orderbook_parameter_sweep.py"
spec = importlib.util.spec_from_file_location("orderbook_parameter_sweep", SCRIPT)
assert spec is not None and spec.loader is not None
harness = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = harness
spec.loader.exec_module(harness)


class OrderbookParameterSweepTests(unittest.TestCase):
    def test_repeated_runs_are_byte_stable_except_output_location(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_path = Path(first)
            second_path = Path(second)
            rows = harness.fixture()
            harness.write_fixture(first_path / "fixture.csv", rows)
            harness.write_fixture(second_path / "fixture.csv", rows)
            grid = {
                "min_orderbook_signal_strength": [0.15, 0.20, 0.30, 0.40],
                "orderbook_expected_return_scale_percent": [80.0, 100.0, 120.0],
                "round_trip_fee_percent": [0.10, 0.20],
                "slippage_buffer_percent": [0.03, 0.08],
                "max_spread_percent": [0.10, 0.20, 0.35],
                "imbalance_weight": [0.8, 1.0, 1.2],
                "position_size_percent": [1.0, 2.0, 4.0],
            }
            summary_a, candidates_a = harness.sweep(rows, grid, 120)
            summary_b, candidates_b = harness.sweep(rows, grid, 120)
            self.assertEqual(candidates_a, candidates_b)
            self.assertEqual(summary_a, summary_b)

    def test_directional_gate_violation_is_blocked(self):
        row = harness.Observation(1, "BTC-USD", "baseline", 2.0, 0.01, 1.0, 1.0, 1.0, "sell")
        metrics = harness.evaluate(harness.Candidate(.2, 100, .1, .01, .2, 1, 1), [row], 1)
        self.assertEqual(metrics["trades"], 0)
        self.assertEqual(metrics["directional_gate_violations"], 1)
        self.assertEqual(metrics["blocked_intent_rate"], 1.0)

    def test_missing_branch_data_fails_closed(self):
        with tempfile.NamedTemporaryFile("w", newline="", suffix=".csv") as handle:
            writer = csv.DictWriter(handle, fieldnames=["timestamp", "symbol", "branch", "imbalance", "spread_percent", "raw_strength", "expected_return_percent", "future_return_percent", "directional_gate"])
            writer.writeheader()
            writer.writerow({"timestamp": 1, "symbol": "BTC-USD", "branch": "", "imbalance": 2, "spread_percent": .01, "raw_strength": 1, "expected_return_percent": 1, "future_return_percent": 1, "directional_gate": "buy"})
            handle.flush()
            with self.assertRaises(ValueError):
                harness.read_rows(Path(handle.name))

    def test_zero_trades_and_zero_losses_have_defined_metrics(self):
        rows = harness.fixture()
        empty = harness.evaluate(harness.Candidate(99, 100, .1, .05, .01, 1, 2), rows, 120)
        self.assertEqual((empty["trades"], empty["wins"], empty["losses"]), (0, 0, 0))
        self.assertEqual(empty["profit_factor"], 0.0)
        no_losses = harness.evaluate(harness.Candidate(.4, 80, .1, .03, .1, .8, 4), rows, 120)
        self.assertGreater(no_losses["trades"], 0)
        self.assertEqual(no_losses["losses"], 0)
        self.assertIsNone(no_losses["profit_factor"])


if __name__ == "__main__":
    unittest.main()
