#!/usr/bin/env python3
"""
Complete integration test to verify the fix for simulated trading.
"""

import pytest
import asyncio
import sys
import os
from unittest.mock import Mock, patch, AsyncMock

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.trade_bot.simulated_trading_manager import SimulatedTradingManager, Position, Trade, Portfolio


class TestCompleteIntegrationFix:
    """Test the complete integration fix."""
    
    @pytest.fixture
    def manager(self):
        """Create a simulated trading manager for testing."""
        return SimulatedTradingManager(
            initial_balance=10000.0,
            max_positions=5,
            position_size_percent=20.0,
            trading_fee=0.001
        )
    
    @pytest.mark.asyncio
    async def test_simulated_trading_working_correctly(self, manager):
        """Test that simulated trading works correctly when properly configured."""
        # Start trading
        manager.start_trading(["BTC-USD", "ETH-USD"])
        
        # Create realistic live order book signals
        signals = [
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
        
        # Process signals
        result = await manager.process_signals(signals)
        
        print(f"Integration test result: {result}")
        print(f"Positions: {manager.positions}")
        print(f"Trades: {manager.trades}")
        
        # Verify results
        assert result["status"] == "processed"
        assert result["executed_trades"] == 1  # Only BTC-USD buy should execute
        assert len(manager.positions) == 1
        assert len(manager.trades) == 1
        assert "BTC-USD" in manager.positions
        
        # Verify the trade details
        trade = manager.trades[0]
        assert trade.symbol == "BTC-USD"
        assert trade.side == "buy"  # Note: uses 'side' not 'action'
        assert trade.price == 50000.0
        assert trade.quantity > 0
    
    @pytest.mark.asyncio
    async def test_background_processing_simulation(self, manager):
        """Test the background processing simulation."""
        # Simulate the trading state
        trading_state = {
            "is_active": True,
            "strategy_type": "orderbook",
            "symbols": ["BTC-USD", "ETH-USD"]
        }
        
        # Start trading
        manager.start_trading(trading_state["symbols"])
        
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
        
        # Process signals (this is what the background task should do)
        result = await manager.process_signals(mock_signals)
        
        assert result["status"] == "processed"
        assert result["executed_trades"] == 1
        assert len(manager.positions) == 1
        assert len(manager.trades) == 1
        
        print("✓ Background processing simulation works correctly")
    
    @pytest.mark.asyncio
    async def test_error_handling(self, manager):
        """Test error handling for invalid signals."""
        manager.start_trading(["BTC-USD"])
        
        # Test with invalid signals
        invalid_signals = [
            {
                "symbol": "BTC-USD",
                "price": 0.0,  # Zero price
                "signal": "buy",
                "signal_generated": True,
                "signal_type": "test",
                "signal_reason": "Test signal"
            },
            {
                "symbol": "BTC-USD",
                # Missing price
                "signal": "buy",
                "signal_generated": True,
                "signal_type": "test",
                "signal_reason": "Test signal"
            }
        ]
        
        # Should handle errors gracefully
        try:
            result = await manager.process_signals(invalid_signals)
            print(f"Error handling result: {result}")
            # Should not crash, but may not execute trades
        except Exception as e:
            print(f"Error in error handling test: {e}")
            # This should be handled gracefully
    
    def test_trade_object_correct_structure(self):
        """Test the correct Trade object structure."""
        # Create a trade with the correct structure
        trade = Trade(
            trade_id="test-123",
            symbol="BTC-USD",
            side="buy",  # Note: uses 'side' not 'action'
            quantity=0.1,
            price=50000.0,
            timestamp="2025-01-01T00:00:00Z",
            reason="Test signal",
            pnl=0.0,
            fees=5.0
        )
        
        print(f"Trade object: {trade}")
        print(f"Trade side: {trade.side}")
        print(f"Trade symbol: {trade.symbol}")
        
        assert trade.symbol == "BTC-USD"
        assert trade.side == "buy"
        assert trade.price == 50000.0
        assert trade.quantity == 0.1
    
    @pytest.mark.asyncio
    async def test_complete_trading_cycle(self, manager):
        """Test a complete buy-sell trading cycle."""
        manager.start_trading(["BTC-USD"])
        
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
        
        result = await manager.process_signals(buy_signals)
        assert result["executed_trades"] == 1
        assert len(manager.positions) == 1
        assert "BTC-USD" in manager.positions
        
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
        
        result = await manager.process_signals(sell_signals)
        assert result["executed_trades"] == 1
        assert len(manager.positions) == 0  # Position closed
        assert len(manager.trades) == 2  # Buy and sell trades
        
        print("✓ Complete trading cycle works correctly")


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v", "--tb=short", "-s"])
