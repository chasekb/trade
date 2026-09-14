"""Deterministic regression tests for simulated order ranking mappings."""

import sys
from pathlib import Path
from typing import Dict, List

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from src.trade_bot.trading.simulated_trading_manager import SimulatedTradingManager


@pytest.fixture
def manager() -> SimulatedTradingManager:
    """Return a manager with all external execution effects disabled."""
    trading_manager = SimulatedTradingManager(
        initial_balance=10_000.0,
        max_positions=10,
        position_size_percent=1.0,
        trading_fee=0.001,
    )
    trading_manager.start_trading(["GOOD-USD", "BAD-USD"])
    trading_manager._broadcast_signal = lambda signal: None
    return trading_manager


def _signal(symbol: str, **values: object) -> Dict[str, object]:
    """Build a complete, deterministic executable signal fixture."""
    return {
        "symbol": symbol,
        "signal": "buy",
        "signal_generated": True,
        "model_confidence": 0.95,
        "price": 100.0,
        "signal_strength": 0.0,
        "win_probability": 0.0,
        "expected_return": 0.0,
        # Keep fee inputs in the fixture: expected_return is net of this cost.
        "fee_rate": 0.001,
        "fees": 0.10,
        **values,
    }


async def _execution_order(
    trading_manager: SimulatedTradingManager,
    prioritization: str,
    signals: List[Dict[str, object]],
) -> List[str]:
    """Process fixtures while recording only the ranking order."""
    trading_manager.strategy_params = {
        "order_prioritization": prioritization,
        "confidence_threshold": 0.6,
    }
    order: List[str] = []

    async def record_buy(symbol, current_price, signal_strength, signal):
        order.append(symbol)
        return {"symbol": symbol}

    setattr(trading_manager, "_process_buy_signal", record_buy)
    result = await trading_manager.process_signals(signals)
    assert result["status"] == "processed"
    assert result["executed_trades"] == len(signals)
    return order


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mapping", "good_values", "bad_values"),
    [
        (
            "signal_strength",
            {"signal_strength": 0.90},
            {"signal_strength": 0.20},
        ),
        (
            "expected_return",
            {"expected_return": 0.08},
            {"expected_return": -0.01},
        ),
        (
            "win_probability",
            {"win_probability": 0.92},
            {"win_probability": 0.35},
        ),
    ],
)
async def test_approved_rankings_put_known_good_fixture_first(
    manager: SimulatedTradingManager,
    mapping: str,
    good_values: Dict[str, float],
    bad_values: Dict[str, float],
):
    """Approved mappings must rank the stronger fixture ahead of the weaker one."""
    signals = [
        _signal("BAD-USD", **bad_values),
        _signal("GOOD-USD", **good_values),
    ]

    assert await _execution_order(manager, mapping, signals) == ["GOOD-USD", "BAD-USD"]


@pytest.mark.asyncio
async def test_held_signal_is_not_promoted_by_ranking_mapping(manager):
    """A held/rejected signal remains excluded even with excellent metrics."""
    manager.strategy_params = {
        "order_prioritization": "expected_return",
        "confidence_threshold": 0.6,
    }
    setattr(manager, "_process_buy_signal", pytest.fail)
    held = _signal(
        "GOOD-USD",
        signal="hold",
        signal_strength=1.0,
        win_probability=1.0,
        expected_return=1.0,
    )

    result = await manager.process_signals([held])

    assert result["status"] == "processed"
    assert result["executed_trades"] == 0
    assert manager.signal_to_trade_statistics["filtered_signals"]["hold_signal"] == 1


@pytest.mark.asyncio
async def test_none_mapping_preserves_input_order(manager):
    """The explicitly unprioritized/held mapping must not sort its inputs."""
    signals = [
        _signal("BAD-USD", signal_strength=0.10, expected_return=-0.02),
        _signal("GOOD-USD", signal_strength=0.99, expected_return=0.20),
    ]

    assert await _execution_order(manager, "none", signals) == ["BAD-USD", "GOOD-USD"]
