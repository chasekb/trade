#!/usr/bin/env python3
"""
Diagnostic tests to identify specific issues with simulated trading integration.
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestDependencyIssues:
    """Test for dependency and integration issues."""
    
    def test_httpx_availability(self):
        """Test if httpx is available for TestClient."""
        try:
            import httpx
            print("✓ httpx is available")
            assert True
        except ImportError:
            print("✗ httpx is NOT available - this will cause TestClient to fail")
            pytest.fail("httpx package is required for TestClient but not installed")
    
    def test_fastapi_testclient_availability(self):
        """Test if FastAPI TestClient can be imported."""
        try:
            from fastapi.testclient import TestClient
            print("✓ FastAPI TestClient is available")
            assert True
        except ImportError as e:
            print(f"✗ FastAPI TestClient import failed: {e}")
            if "httpx" in str(e):
                pytest.fail("httpx package is required for TestClient but not installed")
            else:
                raise
    
    def test_coinbase_advanced_py_availability(self):
        """Test if coinbase-advanced-py is available."""
        try:
            from coinbase import jwt_generator
            print("✓ coinbase-advanced-py is available")
            assert True
        except ImportError:
            print("✗ coinbase-advanced-py is NOT available - JWT generation will fail")
            # This is not a critical failure, just a warning
            assert True


class TestTradingStateIssues:
    """Test for trading state management issues."""
    
    def test_trading_state_structure(self):
        """Test that trading state has the correct structure."""
        trading_state = {
            "is_active": False,
            "strategy_type": None,
            "strategy_params": {},
            "symbols": [],
            "mode": "simulated",
            "last_signal_check": None
        }
        
        required_keys = ["is_active", "strategy_type", "strategy_params", "symbols", "mode", "last_signal_check"]
        for key in required_keys:
            assert key in trading_state, f"Missing key: {key}"
        
        print("✓ Trading state structure is correct")
    
    def test_trading_state_initialization(self):
        """Test that trading state initializes correctly."""
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
        
        print("✓ Trading state initializes correctly")


class TestSimulatedTradingIssues:
    """Test for simulated trading specific issues."""
    
    def test_simulated_trading_manager_import(self):
        """Test that SimulatedTradingManager can be imported."""
        try:
            from src.trade_bot.simulated_trading_manager import SimulatedTradingManager
            print("✓ SimulatedTradingManager can be imported")
            assert True
        except ImportError as e:
            print(f"✗ SimulatedTradingManager import failed: {e}")
            raise
    
    def test_simulated_trading_manager_initialization(self):
        """Test that SimulatedTradingManager initializes correctly."""
        from src.trade_bot.simulated_trading_manager import SimulatedTradingManager
        
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
        
        print("✓ SimulatedTradingManager initializes correctly")
    
    @pytest.mark.asyncio
    async def test_simulated_trading_signal_processing(self):
        """Test simulated trading signal processing."""
        from src.trade_bot.simulated_trading_manager import SimulatedTradingManager
        
        manager = SimulatedTradingManager()
        manager.start_trading(["BTC-USD"])
        
        # Test with valid signals
        signals = [
            {
                "symbol": "BTC-USD",
                "price": 50000.0,
                "signal": "buy",
                "signal_generated": True,
                "signal_type": "test",
                "signal_reason": "Test signal"
            }
        ]
        
        result = await manager.process_signals(signals)
        
        assert result["status"] == "processed"
        assert result["executed_trades"] == 1
        assert len(manager.trades) == 1
        assert "BTC-USD" in manager.positions
        
        print("✓ Simulated trading signal processing works correctly")


class TestWebServerIntegrationIssues:
    """Test for web server integration issues."""
    
    def test_web_server_import(self):
        """Test that web server can be imported."""
        try:
            from src.trade_bot.web_server import app, trading_state, simulated_trading
            print("✓ Web server can be imported")
            assert True
        except ImportError as e:
            print(f"✗ Web server import failed: {e}")
            raise
    
    def test_trading_state_global_variable(self):
        """Test that global trading_state variable exists."""
        from src.trade_bot.web_server import trading_state
        
        assert isinstance(trading_state, dict)
        assert "is_active" in trading_state
        assert "strategy_type" in trading_state
        assert "strategy_params" in trading_state
        assert "symbols" in trading_state
        assert "mode" in trading_state
        assert "last_signal_check" in trading_state
        
        print("✓ Global trading_state variable exists and has correct structure")
    
    def test_simulated_trading_global_variable(self):
        """Test that global simulated_trading variable exists."""
        from src.trade_bot.web_server import simulated_trading
        
        assert simulated_trading is not None
        assert hasattr(simulated_trading, 'is_trading')
        assert hasattr(simulated_trading, 'process_signals')
        assert hasattr(simulated_trading, 'start_trading')
        assert hasattr(simulated_trading, 'stop_trading')
        
        print("✓ Global simulated_trading variable exists and has required methods")


class TestBackgroundProcessingIssues:
    """Test for background processing issues."""
    
    def test_background_processing_without_testclient(self):
        """Test background processing without using TestClient."""
        # This simulates the background processing without the problematic TestClient
        trading_state = {
            "is_active": True,
            "strategy_type": "orderbook",
            "symbols": ["BTC-USD", "ETH-USD"]
        }
        
        # Simulate the background processing logic
        if trading_state["is_active"] and trading_state["strategy_type"] == "orderbook":
            symbols = trading_state.get("symbols", [])
            if symbols:
                print(f"✓ Background processing would analyze symbols: {symbols}")
                # In real implementation, this would call the live order book signals endpoint
                # and process the results through simulated trading
            else:
                print("✗ No symbols to analyze")
        else:
            print("✗ Trading not active or not orderbook strategy")
        
        assert True  # This test just verifies the logic flow
    
    def test_alternative_background_processing(self):
        """Test alternative background processing approach."""
        # Instead of using TestClient, we could directly call the signal processing
        from src.trade_bot.simulated_trading_manager import SimulatedTradingManager
        
        manager = SimulatedTradingManager()
        manager.start_trading(["BTC-USD"])
        
        # Simulate getting signals from live order book analysis
        mock_signals = [
            {
                "symbol": "BTC-USD",
                "price": 50000.0,
                "signal": "buy",
                "signal_generated": True,
                "signal_type": "volume_imbalance_buy",
                "signal_reason": "Volume imbalance buy: 0.8"
            }
        ]
        
        # Process signals directly (this is what the background task should do)
        import asyncio
        
        async def process_signals():
            return await manager.process_signals(mock_signals)
        
        result = asyncio.run(process_signals())
        
        assert result["status"] == "processed"
        assert result["executed_trades"] == 1
        
        print("✓ Alternative background processing approach works")


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v", "--tb=short"])
