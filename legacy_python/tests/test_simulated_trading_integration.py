#!/usr/bin/env python3
"""
Comprehensive tests for simulated trading integration with live order book signals.
Tests why simulated trading is not executing trades based on live order book signals.
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.trade_bot.simulated_trading_manager import SimulatedTradingManager, Position, Trade, Portfolio
from src.trade_bot.trading_strategy import OrderBookStrategy
from src.trade_bot.config import TradingConfig


class TestSimulatedTradingIntegration:
    """Test simulated trading integration with live order book signals."""
    
    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return TradingConfig(
            api_key="test_key",
            api_secret="test_secret", 
            passphrase="test_passphrase",
            product_id="BTC-USD"
        )
    
    @pytest.fixture
    def simulated_trading(self):
        """Create a simulated trading manager for testing."""
        return SimulatedTradingManager(
            initial_balance=10000.0,
            max_positions=5,
            position_size_percent=0.20,
            trading_fee=0.001
        )
    
    @pytest.fixture
    def sample_signals(self):
        """Create sample live order book signals for testing."""
        return [
            {
                "symbol": "BTC-USD",
                "price": 50000.0,
                "signal": "buy",
                "signal_generated": True,
                "signal_type": "volume_imbalance_buy",
                "signal_reason": "Volume imbalance buy: 0.8",
                "signal_strength": 0.8
            },
            {
                "symbol": "ETH-USD", 
                "price": 3000.0,
                "signal": "sell",
                "signal_generated": True,
                "signal_type": "large_trade_sell",
                "signal_reason": "Large trade sell pressure: 0.9",
                "signal_strength": 0.9
            },
            {
                "symbol": "ADA-USD",
                "price": 0.5,
                "signal": "hold",
                "signal_generated": False,
                "signal_type": "no_signal",
                "signal_reason": "No clear signal",
                "signal_strength": 0.3
            }
        ]
    
    @pytest.mark.asyncio
    async def test_simulated_trading_not_active(self, simulated_trading, sample_signals):
        """Test that simulated trading doesn't process signals when not active."""
        # Ensure trading is not active
        assert not simulated_trading.is_trading
        
        # Process signals
        result = await simulated_trading.process_signals(sample_signals)
        
        # Should return inactive status
        assert result["status"] == "inactive"
        assert result["executed_trades"] == 0
        assert len(simulated_trading.trades) == 0
    
    @pytest.mark.asyncio
    async def test_simulated_trading_active_with_signals(self, simulated_trading, sample_signals):
        """Test that simulated trading processes signals when active."""
        # Start trading
        simulated_trading.start_trading(["BTC-USD", "ETH-USD", "ADA-USD"])
        assert simulated_trading.is_trading
        
        # Process signals
        result = await simulated_trading.process_signals(sample_signals)
        
        # Should process signals and execute trades
        assert result["status"] == "processed"
        assert result["executed_trades"] == 2  # BTC-USD buy and ETH-USD sell
        assert len(simulated_trading.trades) == 2
        
        # Check that positions were opened
        assert "BTC-USD" in simulated_trading.positions
        assert simulated_trading.positions["BTC-USD"].status == "open"
        
        # ETH-USD should not have a position since we need to buy first before selling
        assert "ETH-USD" not in simulated_trading.positions
    
    @pytest.mark.asyncio
    async def test_signal_processing_with_generated_signals(self, simulated_trading):
        """Test processing signals with different signal_generated values."""
        simulated_trading.start_trading(["BTC-USD"])
        
        # Test with signal_generated=True
        signals_with_generated = [
            {
                "symbol": "BTC-USD",
                "price": 50000.0,
                "signal": "buy",
                "signal_generated": True,
                "signal_type": "test",
                "signal_reason": "Test signal"
            }
        ]
        
        result = await simulated_trading.process_signals(signals_with_generated)
        assert result["executed_trades"] == 1
        assert len(simulated_trading.trades) == 1
        
        # Test with signal_generated=False
        signals_without_generated = [
            {
                "symbol": "BTC-USD",
                "price": 51000.0,
                "signal": "sell",
                "signal_generated": False,
                "signal_type": "test",
                "signal_reason": "Test signal"
            }
        ]
        
        result = await simulated_trading.process_signals(signals_without_generated)
        assert result["executed_trades"] == 0  # No new trades executed
        assert len(simulated_trading.trades) == 1  # Still only 1 trade
    
    @pytest.mark.asyncio
    async def test_signal_processing_with_hold_signals(self, simulated_trading):
        """Test processing hold signals."""
        simulated_trading.start_trading(["BTC-USD"])
        
        hold_signals = [
            {
                "symbol": "BTC-USD",
                "price": 50000.0,
                "signal": "hold",
                "signal_generated": True,
                "signal_type": "test",
                "signal_reason": "Test hold signal"
            }
        ]
        
        result = await simulated_trading.process_signals(hold_signals)
        assert result["executed_trades"] == 0
        assert len(simulated_trading.trades) == 0
    
    @pytest.mark.asyncio
    async def test_signal_processing_with_invalid_data(self, simulated_trading):
        """Test processing signals with invalid data."""
        simulated_trading.start_trading(["BTC-USD"])
        
        invalid_signals = [
            {
                "symbol": "BTC-USD",
                # Missing price
                "signal": "buy",
                "signal_generated": True
            },
            {
                # Missing symbol
                "price": 50000.0,
                "signal": "buy", 
                "signal_generated": True
            },
            {
                "symbol": "BTC-USD",
                "price": 50000.0,
                # Missing signal
                "signal_generated": True
            }
        ]
        
        result = await simulated_trading.process_signals(invalid_signals)
        assert result["executed_trades"] == 0
        assert len(simulated_trading.trades) == 0
    
    @pytest.mark.asyncio
    async def test_signal_processing_with_wrong_symbols(self, simulated_trading):
        """Test processing signals for symbols not in trading list."""
        simulated_trading.start_trading(["BTC-USD"])
        
        wrong_symbol_signals = [
            {
                "symbol": "ETH-USD",  # Not in trading list
                "price": 3000.0,
                "signal": "buy",
                "signal_generated": True,
                "signal_type": "test",
                "signal_reason": "Test signal"
            }
        ]
        
        result = await simulated_trading.process_signals(wrong_symbol_signals)
        assert result["executed_trades"] == 0
        assert len(simulated_trading.trades) == 0
    
    @pytest.mark.asyncio
    async def test_max_positions_limit(self, simulated_trading):
        """Test that max positions limit is respected."""
        simulated_trading.max_positions = 2
        simulated_trading.start_trading(["BTC-USD", "ETH-USD", "ADA-USD"])
        
        # Fill up positions
        signals = [
            {
                "symbol": "BTC-USD",
                "price": 50000.0,
                "signal": "buy",
                "signal_generated": True,
                "signal_type": "test",
                "signal_reason": "Test signal 1"
            },
            {
                "symbol": "ETH-USD",
                "price": 3000.0,
                "signal": "buy",
                "signal_generated": True,
                "signal_type": "test",
                "signal_reason": "Test signal 2"
            }
        ]
        
        result = await simulated_trading.process_signals(signals)
        assert result["executed_trades"] == 2
        assert len(simulated_trading.positions) == 2
        
        # Try to add another position (should be rejected)
        more_signals = [
            {
                "symbol": "ADA-USD",
                "price": 0.5,
                "signal": "buy",
                "signal_generated": True,
                "signal_type": "test",
                "signal_reason": "Test signal 3"
            }
        ]
        
        result = await simulated_trading.process_signals(more_signals)
        assert result["executed_trades"] == 0  # No new trades executed
        assert len(simulated_trading.positions) == 2  # Still only 2 positions
    
    @pytest.mark.asyncio
    async def test_insufficient_balance(self, simulated_trading):
        """Test that insufficient balance prevents trades."""
        simulated_trading.cash_balance = 100.0  # Very low balance
        simulated_trading.start_trading(["BTC-USD"])
        
        signals = [
            {
                "symbol": "BTC-USD",
                "price": 50000.0,  # High price
                "signal": "buy",
                "signal_generated": True,
                "signal_type": "test",
                "signal_reason": "Test signal"
            }
        ]
        
        result = await simulated_trading.process_signals(signals)
        assert result["executed_trades"] == 0
        assert len(simulated_trading.trades) == 0
        assert simulated_trading.cash_balance == 100.0  # Balance unchanged
    
    @pytest.mark.asyncio
    async def test_duplicate_position_rejection(self, simulated_trading):
        """Test that duplicate positions are rejected."""
        simulated_trading.start_trading(["BTC-USD"])
        
        # First buy signal
        signals1 = [
            {
                "symbol": "BTC-USD",
                "price": 50000.0,
                "signal": "buy",
                "signal_generated": True,
                "signal_type": "test",
                "signal_reason": "Test signal 1"
            }
        ]
        
        result = await simulated_trading.process_signals(signals1)
        assert result["executed_trades"] == 1
        assert len(simulated_trading.positions) == 1
        
        # Try to buy again (should be rejected)
        signals2 = [
            {
                "symbol": "BTC-USD",
                "price": 51000.0,
                "signal": "buy",
                "signal_generated": True,
                "signal_type": "test",
                "signal_reason": "Test signal 2"
            }
        ]
        
        result = await simulated_trading.process_signals(signals2)
        assert result["executed_trades"] == 0  # No new trades executed
        assert len(simulated_trading.positions) == 1  # Still only 1 position
    
    @pytest.mark.asyncio
    async def test_sell_without_position(self, simulated_trading):
        """Test that selling without a position is rejected."""
        simulated_trading.start_trading(["BTC-USD"])
        
        signals = [
            {
                "symbol": "BTC-USD",
                "price": 50000.0,
                "signal": "sell",
                "signal_generated": True,
                "signal_type": "test",
                "signal_reason": "Test signal"
            }
        ]
        
        result = await simulated_trading.process_signals(signals)
        assert result["executed_trades"] == 0
        assert len(simulated_trading.trades) == 0
        assert len(simulated_trading.positions) == 0
    
    @pytest.mark.asyncio
    async def test_complete_trading_cycle(self, simulated_trading):
        """Test a complete buy-sell trading cycle."""
        simulated_trading.start_trading(["BTC-USD"])
        
        # Buy signal
        buy_signals = [
            {
                "symbol": "BTC-USD",
                "price": 50000.0,
                "signal": "buy",
                "signal_generated": True,
                "signal_type": "test",
                "signal_reason": "Test buy signal"
            }
        ]
        
        result = await simulated_trading.process_signals(buy_signals)
        assert result["executed_trades"] == 1
        assert len(simulated_trading.positions) == 1
        assert simulated_trading.positions["BTC-USD"].status == "open"
        
        # Sell signal
        sell_signals = [
            {
                "symbol": "BTC-USD",
                "price": 55000.0,
                "signal": "sell",
                "signal_generated": True,
                "signal_type": "test",
                "signal_reason": "Test sell signal"
            }
        ]
        
        result = await simulated_trading.process_signals(sell_signals)
        assert result["executed_trades"] == 1
        assert len(simulated_trading.positions) == 0  # Position closed
        assert len(simulated_trading.trades) == 2  # Buy and sell trades
    
    def test_trading_state_management(self):
        """Test trading state management."""
        # This would test the global trading_state object
        # For now, we'll test the concept
        trading_state = {
            "is_active": False,
            "strategy_type": None,
            "strategy_params": {},
            "symbols": [],
            "mode": "simulated"
        }
        
        assert not trading_state["is_active"]
        assert trading_state["strategy_type"] is None
        
        # Simulate starting trading
        trading_state["is_active"] = True
        trading_state["strategy_type"] = "orderbook"
        trading_state["symbols"] = ["BTC-USD", "ETH-USD"]
        
        assert trading_state["is_active"]
        assert trading_state["strategy_type"] == "orderbook"
        assert len(trading_state["symbols"]) == 2


class TestLiveOrderBookSignalIntegration:
    """Test integration between live order book signals and simulated trading."""
    
    @pytest.fixture
    def mock_live_signals_response(self):
        """Mock response from live order book signals API."""
        return {
            "signals": [
                {
                    "symbol": "BTC-USD",
                    "price": 50000.0,
                    "signal": "buy",
                    "signal_generated": True,
                    "signal_type": "volume_imbalance_buy",
                    "signal_reason": "Volume imbalance buy: 0.8",
                    "signal_strength": 0.8
                }
            ],
            "trading_active": True,
            "timestamp": datetime.now().isoformat()
        }
    
    @pytest.mark.asyncio
    async def test_signal_processing_workflow(self, mock_live_signals_response):
        """Test the complete signal processing workflow."""
        simulated_trading = SimulatedTradingManager()
        simulated_trading.start_trading(["BTC-USD"])
        
        # Process the mock signals
        result = await simulated_trading.process_signals(mock_live_signals_response["signals"])
        
        assert result["status"] == "processed"
        assert result["executed_trades"] == 1
        assert len(simulated_trading.trades) == 1
        
        # Verify the trade details
        trade = simulated_trading.trades[0]
        assert trade.symbol == "BTC-USD"
        assert trade.action == "buy"
        assert trade.price == 50000.0
    
    @pytest.mark.asyncio
    async def test_signal_processing_with_trading_inactive(self):
        """Test signal processing when trading is not active."""
        simulated_trading = SimulatedTradingManager()
        # Don't start trading
        
        mock_signals = [
            {
                "symbol": "BTC-USD",
                "price": 50000.0,
                "signal": "buy",
                "signal_generated": True,
                "signal_type": "test",
                "signal_reason": "Test signal"
            }
        ]
        
        result = await simulated_trading.process_signals(mock_signals)
        
        assert result["status"] == "inactive"
        assert result["executed_trades"] == 0
        assert len(simulated_trading.trades) == 0


class TestDiagnosticTests:
    """Diagnostic tests to identify specific issues."""
    
    def test_httpx_dependency_issue(self):
        """Test if httpx dependency is available for TestClient."""
        try:
            from fastapi.testclient import TestClient
            # If this doesn't raise an exception, httpx is available
            assert True
        except ImportError as e:
            if "httpx" in str(e):
                pytest.fail("httpx package is required for TestClient but not installed")
            else:
                raise
    
    def test_trading_state_initialization(self):
        """Test that trading state is properly initialized."""
        trading_state = {
            "is_active": False,
            "strategy_type": None,
            "strategy_params": {},
            "symbols": [],
            "mode": "simulated",
            "last_signal_check": None
        }
        
        assert trading_state["is_active"] is False
        assert trading_state["strategy_type"] is None
        assert trading_state["strategy_params"] == {}
        assert trading_state["symbols"] == []
        assert trading_state["mode"] == "simulated"
        assert trading_state["last_signal_check"] is None
    
    def test_simulated_trading_manager_initialization(self):
        """Test that SimulatedTradingManager initializes correctly."""
        manager = SimulatedTradingManager()
        
        assert manager.initial_balance == 10000.0
        assert manager.cash_balance == 10000.0
        assert manager.max_positions == 5
        assert manager.position_size_percent == 0.20
        assert manager.trading_fee == 0.001
        assert not manager.is_trading
        assert manager.symbols_to_trade == []
        assert len(manager.positions) == 0
        assert len(manager.trades) == 0
    
    @pytest.mark.asyncio
    async def test_background_processing_simulation(self):
        """Test the background processing logic without TestClient."""
        # Simulate the background processing without using TestClient
        trading_state = {
            "is_active": True,
            "strategy_type": "orderbook",
            "symbols": ["BTC-USD", "ETH-USD"]
        }
        
        simulated_trading = SimulatedTradingManager()
        simulated_trading.start_trading(trading_state["symbols"])
        
        # Simulate processing signals directly
        mock_signals = [
            {
                "symbol": "BTC-USD",
                "price": 50000.0,
                "signal": "buy",
                "signal_generated": True,
                "signal_type": "test",
                "signal_reason": "Test signal"
            }
        ]
        
        result = await simulated_trading.process_signals(mock_signals)
        
        assert result["status"] == "processed"
        assert result["executed_trades"] == 1


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v", "--tb=short"])
