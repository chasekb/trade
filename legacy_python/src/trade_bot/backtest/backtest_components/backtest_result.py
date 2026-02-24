"""Backtest result data structure."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional


@dataclass
class BacktestResult:
    """Results from a backtest run."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_return: float
    max_drawdown: float
    sharpe_ratio: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    total_fees: float
    net_profit: float
    start_date: datetime
    end_date: datetime
    initial_balance: float
    final_balance: float
    # Signal statistics
    total_signals: int = 0
    signals_by_type: Optional[Dict[str, int]] = None
    signal_rate: float = 0.0
    no_signal_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.win_rate,
            'total_return': self.total_return,
            'max_drawdown': self.max_drawdown,
            'sharpe_ratio': self.sharpe_ratio,
            'profit_factor': self.profit_factor,
            'avg_win': self.avg_win,
            'avg_loss': self.avg_loss,
            'largest_win': self.largest_win,
            'largest_loss': self.largest_loss,
            'total_fees': self.total_fees,
            'net_profit': self.net_profit,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'initial_balance': self.initial_balance,
            'final_balance': self.final_balance,
            'total_signals': self.total_signals,
            'signals_by_type': self.signals_by_type or {},
            'signal_rate': self.signal_rate,
            'no_signal_count': self.no_signal_count
        }
    
    def get_summary(self) -> str:
        """Get a summary string of the results."""
        return f"""
Backtest Results Summary:
========================
Total Trades: {self.total_trades}
Win Rate: {self.win_rate:.2f}%
Total Return: {self.total_return:.2f}%
Max Drawdown: {self.max_drawdown:.2f}%
Sharpe Ratio: {self.sharpe_ratio:.2f}
Profit Factor: {self.profit_factor:.2f}
Net Profit: ${self.net_profit:.2f}
Total Fees: ${self.total_fees:.2f}
Initial Balance: ${self.initial_balance:.2f}
Final Balance: ${self.final_balance:.2f}
        """.strip()
