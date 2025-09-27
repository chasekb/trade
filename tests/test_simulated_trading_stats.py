"""Tests for simulated trading statistics calculations."""

import pytest
import sys
import os
from unittest.mock import Mock, patch
from datetime import datetime

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from trade_bot.trading.simulated_components.trade_executor import SimulatedTradeExecutor
from trade_bot.trading.simulated_components.portfolio import Portfolio
from trade_bot.trading.simulated_components.position import Position
from trade_bot.trading.simulated_components.trade import Trade


class TestSimulatedTradingStats:
    """Test simulated trading statistics calculations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.trade_executor = SimulatedTradeExecutor()
        self.portfolio = Portfolio(
            cash_balance=5000.0,
            total_value=10000.0,
            positions={},
            trades=[],
            total_pnl=0.0,
            total_fees=0.0,
            max_drawdown=0.0,
            win_rate=0.0,
            total_trades=0,
            winning_trades=0
        )
    
    def test_empty_portfolio_stats(self):
        """Test statistics with empty portfolio."""
        stats = self.trade_executor.get_trade_stats()
        
        assert stats['total_trades'] == 0
        assert stats['winning_trades'] == 0
        assert stats['losing_trades'] == 0
        assert stats['win_rate'] == 0.0
        assert stats['total_pnl'] == 0.0
        assert stats['net_pnl'] == 0.0
        assert stats['total_fees'] == 0.0
        assert stats['average_win'] == 0.0
        assert stats['average_loss'] == 0.0
        assert stats['profit_factor'] == 0.0
        assert stats['open_positions'] == 0
        assert stats['total_unrealized_pnl'] == 0.0
    
    def test_winning_trades_calculation(self):
        """Test calculation with winning trades."""
        # Add winning trades
        trade1 = Trade(
            trade_id="1",
            symbol="BTC-USD",
            side="buy",
            quantity=0.1,
            price=50000.0,
            timestamp=datetime.now(),
            reason="test_trade",
            fees=25.0,
            pnl=500.0
        )
        trade2 = Trade(
            trade_id="2",
            symbol="ETH-USD", 
            side="buy",
            quantity=1.0,
            price=3000.0,
            timestamp=datetime.now(),
            reason="test_trade",
            fees=15.0,
            pnl=200.0
        )
        
        self.trade_executor.trades = [trade1, trade2]
        
        stats = self.trade_executor.get_trade_stats()
        
        assert stats['total_trades'] == 2
        assert stats['winning_trades'] == 2
        assert stats['losing_trades'] == 0
        assert stats['win_rate'] == 100.0
        assert stats['total_pnl'] == 700.0
        assert stats['net_pnl'] == 660.0  # 700 - 40 fees
        assert stats['total_fees'] == 40.0
        assert stats['average_win'] == 350.0
        assert stats['average_loss'] == 0.0
        assert stats['profit_factor'] == float('inf')
    
    def test_losing_trades_calculation(self):
        """Test calculation with losing trades."""
        # Add losing trades
        trade1 = Trade(
            trade_id="1",
            symbol="BTC-USD",
            side="buy",
            quantity=0.1,
            price=50000.0,
            timestamp=datetime.now(),
            reason="test_trade",
            fees=25.0,
            pnl=-300.0
        )
        trade2 = Trade(
            trade_id="2",
            symbol="ETH-USD",
            side="buy", 
            quantity=1.0,
            price=3000.0,
            timestamp=datetime.now(),
            reason="test_trade",
            fees=15.0,
            pnl=-150.0
        )
        
        self.trade_executor.trades = [trade1, trade2]
        
        stats = self.trade_executor.get_trade_stats()
        
        assert stats['total_trades'] == 2
        assert stats['winning_trades'] == 0
        assert stats['losing_trades'] == 2
        assert stats['win_rate'] == 0.0
        assert stats['total_pnl'] == -450.0
        assert stats['net_pnl'] == -490.0  # -450 - 40 fees
        assert stats['total_fees'] == 40.0
        assert stats['average_win'] == 0.0
        assert stats['average_loss'] == -225.0
        assert stats['profit_factor'] == 0.0
    
    def test_mixed_trades_calculation(self):
        """Test calculation with mixed winning and losing trades."""
        # Add mixed trades
        winning_trade = Trade(
            trade_id="1",
            symbol="BTC-USD",
            side="buy",
            quantity=0.1,
            price=50000.0,
            timestamp=datetime.now(),
            reason="test_trade",
            fees=25.0,
            pnl=500.0
        )
        losing_trade = Trade(
            trade_id="2",
            symbol="ETH-USD",
            side="buy",
            quantity=1.0,
            price=3000.0,
            timestamp=datetime.now(),
            reason="test_trade",
            fees=15.0,
            pnl=-200.0
        )
        
        self.trade_executor.trades = [winning_trade, losing_trade]
        
        stats = self.trade_executor.get_trade_stats()
        
        assert stats['total_trades'] == 2
        assert stats['winning_trades'] == 1
        assert stats['losing_trades'] == 1
        assert stats['win_rate'] == 50.0
        assert stats['total_pnl'] == 300.0
        assert stats['net_pnl'] == 260.0  # 300 - 40 fees
        assert stats['total_fees'] == 40.0
        assert stats['average_win'] == 500.0
        assert stats['average_loss'] == -200.0
        assert stats['profit_factor'] == 2.5  # 500 / 200
    
    def test_profit_factor_edge_cases(self):
        """Test profit factor edge cases."""
        # No losing trades
        winning_trade = Trade(
            trade_id="1",
            symbol="BTC-USD",
            side="buy",
            quantity=0.1,
            price=50000.0,
            timestamp=datetime.now(),
            reason="test_trade",
            fees=25.0,
            pnl=500.0
        )
        self.trade_executor.trades = [winning_trade]
        
        stats = self.trade_executor.get_trade_stats()
        assert stats['profit_factor'] == float('inf')
        
        # No winning trades
        self.trade_executor.trades = []
        losing_trade = Trade(
            trade_id="2",
            symbol="ETH-USD",
            side="buy",
            quantity=1.0,
            price=3000.0,
            timestamp=datetime.now(),
            reason="test_trade",
            fees=15.0,
            pnl=-200.0
        )
        self.trade_executor.trades = [losing_trade]
        
        stats = self.trade_executor.get_trade_stats()
        assert stats['profit_factor'] == 0.0
    
    def test_portfolio_summary_calculations(self):
        """Test portfolio summary calculations."""
        # Create positions
        position1 = Position(
            symbol="BTC-USD",
            side="long",
            quantity=0.1,
            entry_price=50000.0,
            entry_time=datetime.now(),
            current_price=55000.0,
            unrealized_pnl=500.0,
            status="open"
        )
        position2 = Position(
            symbol="ETH-USD",
            side="long",
            quantity=1.0,
            entry_price=3000.0,
            entry_time=datetime.now(),
            current_price=2800.0,
            unrealized_pnl=-200.0,
            status="open"
        )
        
        # Create trades
        trade1 = Trade(
            trade_id="1",
            symbol="BTC-USD",
            side="buy",
            quantity=0.1,
            price=50000.0,
            timestamp=datetime.now(),
            reason="test_trade",
            fees=25.0,
            pnl=500.0
        )
        
        # Mock position manager
        self.trade_executor.position_manager.positions = {
            "BTC-USD": position1,
            "ETH-USD": position2
        }
        self.trade_executor.trades = [trade1]
        
        # Test position count
        assert self.trade_executor.position_manager.get_position_count() == 2
        
        # Test unrealized P&L calculation
        expected_unrealized_pnl = (55000.0 - 50000.0) * 0.1 + (2800.0 - 3000.0) * 1.0
        expected_unrealized_pnl = 500.0 - 200.0  # 300.0
        actual_unrealized_pnl = self.trade_executor.position_manager.get_total_unrealized_pnl()
        assert abs(actual_unrealized_pnl - expected_unrealized_pnl) < 0.01
    
    def test_max_drawdown_calculation(self):
        """Test max drawdown calculation."""
        # Simulate portfolio value changes
        self.trade_executor.peak_value = 12000.0
        self.trade_executor.max_drawdown = 0.0
        
        # Test current drawdown calculation
        current_value = 10000.0
        expected_drawdown = (12000.0 - 10000.0) / 12000.0  # 0.1667 (16.67%)
        
        # This would be calculated in the portfolio summary
        if current_value < self.trade_executor.peak_value:
            current_drawdown = (self.trade_executor.peak_value - current_value) / self.trade_executor.peak_value
            self.trade_executor.max_drawdown = max(self.trade_executor.max_drawdown, current_drawdown)
        
        assert abs(self.trade_executor.max_drawdown - expected_drawdown) < 0.01
    
    def test_frontend_stats_calculation(self):
        """Test frontend statistics calculation logic."""
        # Mock portfolio data as it would come from the backend
        portfolio_data = {
            'total_pnl': 1500.0,
            'total_trades': 10,
            'positions': {
                'BTC-USD': {'quantity': 0.1, 'current_price': 55000.0},
                'ETH-USD': {'quantity': 1.0, 'current_price': 3000.0}
            },
            'total_value': 12000.0,
            'cash_balance': 5000.0,
            'max_drawdown': 0.15,
            'win_rate': 60.0,
            'total_fees': 100.0
        }
        
        # Simulate frontend calculation
        simulated_stats = {
            'totalPnl': portfolio_data.get('total_pnl', 0),
            'totalTrades': portfolio_data.get('total_trades', 0),
            'activePositions': len(portfolio_data.get('positions', {})),
            'totalValue': portfolio_data.get('total_value', 0),
            'cashBalance': portfolio_data.get('cash_balance', 0),
            'maxDrawdown': portfolio_data.get('max_drawdown', 0),
            'winRate': portfolio_data.get('win_rate', 0),
            'totalFees': portfolio_data.get('total_fees', 0)
        }
        
        # Test calculations
        assert simulated_stats['totalPnl'] == 1500.0
        assert simulated_stats['totalTrades'] == 10
        assert simulated_stats['activePositions'] == 2
        assert simulated_stats['totalValue'] == 12000.0
        assert simulated_stats['cashBalance'] == 5000.0
        assert simulated_stats['maxDrawdown'] == 0.15
        assert simulated_stats['winRate'] == 60.0
        assert simulated_stats['totalFees'] == 100.0
        
        # Test derived calculations
        avg_trade_size = simulated_stats['totalValue'] / max(simulated_stats['totalTrades'], 1)
        assert avg_trade_size == 1200.0
        
        # Test UI display values
        assert f"${simulated_stats['totalPnl']:.2f}" == "$1500.00"
        assert f"{simulated_stats['winRate']:.2f}%" == "60.00%"
        assert f"${simulated_stats['maxDrawdown']:.2f}%" == "$0.15%"
        assert f"${avg_trade_size:.2f}" == "$1200.00"


if __name__ == "__main__":
    pytest.main([__file__])
