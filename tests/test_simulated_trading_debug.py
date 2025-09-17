#!/usr/bin/env python3
"""
Debug tests to identify exactly why simulated trading is not executing trades.
"""

import pytest
import asyncio
import sys
import os
from unittest.mock import Mock, patch

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.trade_bot.simulated_trading_manager import SimulatedTradingManager, Position, Trade, Portfolio


class TestSimulatedTradingDebug:
    """Debug tests for simulated trading issues."""
    
    @pytest.fixture
    def manager(self):
        """Create a simulated trading manager for testing."""
        return SimulatedTradingManager(
            initial_balance=10000.0,
            max_positions=5,
            position_size_percent=20.0,
            trading_fee=0.001
        )
    
    def test_manager_initialization(self, manager):
        """Test manager initialization."""
        print(f"Initial balance: {manager.initial_balance}")
        print(f"Cash balance: {manager.cash_balance}")
        print(f"Max positions: {manager.max_positions}")
        print(f"Position size percent: {manager.position_size_percent}")
        print(f"Trading fee: {manager.trading_fee}")
        print(f"Is trading: {manager.is_trading}")
        print(f"Symbols to trade: {manager.symbols_to_trade}")
        print(f"Positions: {manager.positions}")
        print(f"Trades: {manager.trades}")
        
        assert manager.initial_balance == 10000.0
        assert manager.cash_balance == 10000.0
        assert not manager.is_trading
    
    def test_start_trading(self, manager):
        """Test starting trading."""
        symbols = ["BTC-USD", "ETH-USD"]
        manager.start_trading(symbols)
        
        print(f"After start_trading:")
        print(f"Is trading: {manager.is_trading}")
        print(f"Symbols to trade: {manager.symbols_to_trade}")
        
        assert manager.is_trading
        assert manager.symbols_to_trade == symbols
    
    @pytest.mark.asyncio
    async def test_process_signals_not_trading(self, manager):
        """Test processing signals when not trading."""
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
        
        print(f"Result when not trading: {result}")
        
        # Check what the actual return value is
        assert result["status"] == "not_trading"  # This is the actual return value
        assert result["executed_trades"] == 0
    
    @pytest.mark.asyncio
    async def test_process_signals_trading_active(self, manager):
        """Test processing signals when trading is active."""
        # Start trading
        manager.start_trading(["BTC-USD"])
        
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
        
        print(f"Before processing signals:")
        print(f"Is trading: {manager.is_trading}")
        print(f"Symbols to trade: {manager.symbols_to_trade}")
        print(f"Cash balance: {manager.cash_balance}")
        
        result = await manager.process_signals(signals)
        
        print(f"After processing signals:")
        print(f"Result: {result}")
        print(f"Positions: {manager.positions}")
        print(f"Trades: {manager.trades}")
        print(f"Cash balance: {manager.cash_balance}")
        
        # Check what actually happened
        assert result["status"] == "processed"
        print(f"Executed trades: {result['executed_trades']}")
        print(f"Number of positions: {len(manager.positions)}")
        print(f"Number of trades: {len(manager.trades)}")
    
    @pytest.mark.asyncio
    async def test_process_signals_with_zero_price(self, manager):
        """Test processing signals with zero price (division by zero)."""
        manager.start_trading(["BTC-USD"])
        
        signals = [
            {
                "symbol": "BTC-USD",
                "price": 0.0,  # Zero price
                "signal": "buy",
                "signal_generated": True,
                "signal_type": "test",
                "signal_reason": "Test signal"
            }
        ]
        
        try:
            result = await manager.process_signals(signals)
            print(f"Result with zero price: {result}")
        except Exception as e:
            print(f"Error with zero price: {e}")
            # This should handle the division by zero error
    
    @pytest.mark.asyncio
    async def test_process_signals_with_missing_fields(self, manager):
        """Test processing signals with missing required fields."""
        manager.start_trading(["BTC-USD"])
        
        signals = [
            {
                "symbol": "BTC-USD",
                # Missing price
                "signal": "buy",
                "signal_generated": True,
                "signal_type": "test",
                "signal_reason": "Test signal"
            }
        ]
        
        try:
            result = await manager.process_signals(signals)
            print(f"Result with missing price: {result}")
        except Exception as e:
            print(f"Error with missing price: {e}")
    
    def test_trade_object_structure(self, manager):
        """Test the Trade object structure."""
        # Create a trade manually to see its structure
        trade = Trade(
            trade_id="test-123",
            symbol="BTC-USD",
            action="buy",
            price=50000.0,
            quantity=0.1,
            timestamp="2025-01-01T00:00:00Z",
            pnl=0.0,
            fees=5.0,
            status="executed"
        )
        
        print(f"Trade object: {trade}")
        print(f"Trade attributes: {dir(trade)}")
        
        # Check what attributes are actually available
        assert hasattr(trade, 'symbol')
        assert hasattr(trade, 'price')
        assert hasattr(trade, 'quantity')
        assert hasattr(trade, 'timestamp')
        
        # Check if action exists
        if hasattr(trade, 'action'):
            print(f"Trade has action attribute: {trade.action}")
        else:
            print("Trade does NOT have action attribute")
    
    @pytest.mark.asyncio
    async def test_signal_processing_step_by_step(self, manager):
        """Test signal processing step by step to identify the issue."""
        manager.start_trading(["BTC-USD"])
        
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
        
        print("=== STEP BY STEP SIGNAL PROCESSING ===")
        print(f"1. Manager is trading: {manager.is_trading}")
        print(f"2. Symbols to trade: {manager.symbols_to_trade}")
        print(f"3. Cash balance: {manager.cash_balance}")
        print(f"4. Max positions: {manager.max_positions}")
        print(f"5. Position size percent: {manager.position_size_percent}")
        
        # Process signals
        result = await manager.process_signals(signals)
        
        print(f"6. Result: {result}")
        print(f"7. Positions after: {manager.positions}")
        print(f"8. Trades after: {manager.trades}")
        print(f"9. Cash balance after: {manager.cash_balance}")
        
        # Check each step of the process
        if result["status"] == "processed":
            print("✓ Signals were processed")
            if result["executed_trades"] > 0:
                print("✓ Trades were executed")
            else:
                print("✗ No trades were executed")
        else:
            print(f"✗ Signals were not processed: {result['status']}")
    
    @pytest.mark.asyncio
    async def test_direct_signal_processing(self, manager):
        """Test direct signal processing without the wrapper method."""
        manager.start_trading(["BTC-USD"])
        
        # Test the internal methods directly
        symbol = "BTC-USD"
        current_price = 50000.0
        signal_strength = 0.8
        signal = {
            "symbol": "BTC-USD",
            "price": 50000.0,
            "signal": "buy",
            "signal_generated": True,
            "signal_type": "test",
            "signal_reason": "Test signal"
        }
        
        print("=== DIRECT SIGNAL PROCESSING ===")
        print(f"Symbol: {symbol}")
        print(f"Current price: {current_price}")
        print(f"Signal strength: {signal_strength}")
        print(f"Signal: {signal}")
        
        # Test the internal buy signal processing
        try:
            result = await manager._process_buy_signal(symbol, current_price, signal_strength, signal)
            print(f"Buy signal result: {result}")
        except Exception as e:
            print(f"Error in buy signal processing: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v", "--tb=short", "-s"])
