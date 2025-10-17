#!/usr/bin/env python3
"""ML Strategy Validation and Backtesting Script."""

import logging
import sys
import os
import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from trade_bot.trading.strategies.orderbook import OrderBookStrategy
from trade_bot.trading.strategies.ml_enhanced_orderbook import MLEnhancedOrderBookStrategy
from trade_bot.core.config import TradingConfig
from trade_bot.backtest.backtester import Backtester

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'outputs/ml_validation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class MLStrategyValidator:
    """Validates ML-enhanced strategy against baseline."""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.results = {}
        
    def run_comparison_backtest(self, start_date: datetime, end_date: datetime, 
                               symbol: str = "BTC-USD") -> Dict[str, Any]:
        """Run backtest comparison between baseline and ML-enhanced strategies."""
        logger.info(f"Running backtest comparison from {start_date} to {end_date}")
        
        # Initialize strategies
        baseline_strategy = OrderBookStrategy(self.config)
        ml_strategy = MLEnhancedOrderBookStrategy(
            config=self.config,
            ml_server_url="http://localhost:8002",
            fallback_to_baseline=True,
            confidence_threshold=0.6
        )
        
        # Initialize backtester
        backtester = Backtester(self.config)
        
        # Run baseline backtest
        logger.info("Running baseline order book strategy backtest...")
        baseline_results = self._run_strategy_backtest(
            backtester, baseline_strategy, start_date, end_date, symbol, "baseline"
        )
        
        # Run ML-enhanced backtest
        logger.info("Running ML-enhanced order book strategy backtest...")
        ml_results = self._run_strategy_backtest(
            backtester, ml_strategy, start_date, end_date, symbol, "ml_enhanced"
        )
        
        # Compare results
        comparison = self._compare_results(baseline_results, ml_results)
        
        return {
            'baseline': baseline_results,
            'ml_enhanced': ml_results,
            'comparison': comparison,
            'validation_timestamp': datetime.now().isoformat()
        }
    
    def _run_strategy_backtest(self, backtester: Backtester, strategy, 
                              start_date: datetime, end_date: datetime, 
                              symbol: str, strategy_name: str) -> Dict[str, Any]:
        """Run backtest for a specific strategy."""
        try:
            # Configure backtester
            backtester.set_strategy(strategy)
            backtester.set_time_range(start_date, end_date)
            backtester.set_symbol(symbol)
            
            # Run backtest
            results = backtester.run_backtest()
            
            # Calculate additional metrics
            metrics = self._calculate_strategy_metrics(results, strategy_name)
            
            return {
                'strategy_name': strategy_name,
                'backtest_results': results,
                'metrics': metrics,
                'strategy_info': strategy.get_strategy_info()
            }
            
        except Exception as e:
            logger.error(f"Error running {strategy_name} backtest: {e}")
            return {
                'strategy_name': strategy_name,
                'error': str(e),
                'metrics': {}
            }
    
    def _calculate_strategy_metrics(self, backtest_results: Dict[str, Any], 
                                   strategy_name: str) -> Dict[str, Any]:
        """Calculate comprehensive strategy metrics."""
        try:
            trades = backtest_results.get('trades', [])
            equity_curve = backtest_results.get('equity_curve', [])
            
            if not trades:
                return {'error': 'No trades found'}
            
            # Convert to DataFrame for easier analysis
            trades_df = pd.DataFrame(trades)
            equity_df = pd.DataFrame(equity_curve)
            
            # Basic metrics
            total_trades = len(trades_df)
            winning_trades = len(trades_df[trades_df['pnl'] > 0])
            losing_trades = len(trades_df[trades_df['pnl'] < 0])
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            
            # P&L metrics
            total_pnl = trades_df['pnl'].sum()
            total_fees = trades_df['fees'].sum()
            net_pnl = total_pnl - total_fees
            
            avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
            avg_loss = trades_df[trades_df['pnl'] < 0]['pnl'].mean() if losing_trades > 0 else 0
            
            # Risk metrics
            if len(equity_df) > 1:
                returns = equity_df['equity'].pct_change().dropna()
                volatility = returns.std() * np.sqrt(252)  # Annualized
                sharpe_ratio = (returns.mean() * 252) / (returns.std() * np.sqrt(252)) if returns.std() > 0 else 0
                
                # Maximum drawdown
                peak = equity_df['equity'].expanding().max()
                drawdown = (equity_df['equity'] - peak) / peak
                max_drawdown = drawdown.min()
            else:
                volatility = 0
                sharpe_ratio = 0
                max_drawdown = 0
            
            # Profit factor
            gross_profit = trades_df[trades_df['pnl'] > 0]['pnl'].sum()
            gross_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum())
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            
            return {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'total_fees': total_fees,
                'net_pnl': net_pnl,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'profit_factor': profit_factor,
                'volatility': volatility,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown,
                'strategy_name': strategy_name
            }
            
        except Exception as e:
            logger.error(f"Error calculating metrics for {strategy_name}: {e}")
            return {'error': str(e)}
    
    def _compare_results(self, baseline_results: Dict[str, Any], 
                        ml_results: Dict[str, Any]) -> Dict[str, Any]:
        """Compare baseline and ML-enhanced results."""
        try:
            baseline_metrics = baseline_results.get('metrics', {})
            ml_metrics = ml_results.get('metrics', {})
            
            if 'error' in baseline_metrics or 'error' in ml_metrics:
                return {'error': 'Cannot compare due to errors in results'}
            
            # Calculate improvements
            improvements = {}
            
            # P&L improvement
            baseline_pnl = baseline_metrics.get('net_pnl', 0)
            ml_pnl = ml_metrics.get('net_pnl', 0)
            pnl_improvement = ml_pnl - baseline_pnl
            pnl_improvement_pct = (pnl_improvement / abs(baseline_pnl) * 100) if baseline_pnl != 0 else 0
            
            # Win rate improvement
            baseline_win_rate = baseline_metrics.get('win_rate', 0)
            ml_win_rate = ml_metrics.get('win_rate', 0)
            win_rate_improvement = ml_win_rate - baseline_win_rate
            
            # Sharpe ratio improvement
            baseline_sharpe = baseline_metrics.get('sharpe_ratio', 0)
            ml_sharpe = ml_metrics.get('sharpe_ratio', 0)
            sharpe_improvement = ml_sharpe - baseline_sharpe
            
            # Profit factor improvement
            baseline_pf = baseline_metrics.get('profit_factor', 0)
            ml_pf = ml_metrics.get('profit_factor', 0)
            pf_improvement = ml_pf - baseline_pf
            
            improvements = {
                'pnl_improvement': pnl_improvement,
                'pnl_improvement_pct': pnl_improvement_pct,
                'win_rate_improvement': win_rate_improvement,
                'sharpe_improvement': sharpe_improvement,
                'profit_factor_improvement': pf_improvement,
                'ml_outperforms': pnl_improvement > 0
            }
            
            return improvements
            
        except Exception as e:
            logger.error(f"Error comparing results: {e}")
            return {'error': str(e)}
    
    def generate_validation_report(self, results: Dict[str, Any]) -> str:
        """Generate a comprehensive validation report."""
        report = []
        report.append("=" * 80)
        report.append("ML STRATEGY VALIDATION REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Baseline results
        baseline = results.get('baseline', {})
        baseline_metrics = baseline.get('metrics', {})
        
        report.append("BASELINE ORDER BOOK STRATEGY")
        report.append("-" * 40)
        if 'error' in baseline_metrics:
            report.append(f"Error: {baseline_metrics['error']}")
        else:
            report.append(f"Total Trades: {baseline_metrics.get('total_trades', 0)}")
            report.append(f"Win Rate: {baseline_metrics.get('win_rate', 0):.2f}%")
            report.append(f"Net P&L: ${baseline_metrics.get('net_pnl', 0):.2f}")
            report.append(f"Profit Factor: {baseline_metrics.get('profit_factor', 0):.2f}")
            report.append(f"Sharpe Ratio: {baseline_metrics.get('sharpe_ratio', 0):.2f}")
            report.append(f"Max Drawdown: {baseline_metrics.get('max_drawdown', 0):.2f}%")
        report.append("")
        
        # ML-enhanced results
        ml_enhanced = results.get('ml_enhanced', {})
        ml_metrics = ml_enhanced.get('metrics', {})
        
        report.append("ML-ENHANCED ORDER BOOK STRATEGY")
        report.append("-" * 40)
        if 'error' in ml_metrics:
            report.append(f"Error: {ml_metrics['error']}")
        else:
            report.append(f"Total Trades: {ml_metrics.get('total_trades', 0)}")
            report.append(f"Win Rate: {ml_metrics.get('win_rate', 0):.2f}%")
            report.append(f"Net P&L: ${ml_metrics.get('net_pnl', 0):.2f}")
            report.append(f"Profit Factor: {ml_metrics.get('profit_factor', 0):.2f}")
            report.append(f"Sharpe Ratio: {ml_metrics.get('sharpe_ratio', 0):.2f}")
            report.append(f"Max Drawdown: {ml_metrics.get('max_drawdown', 0):.2f}%")
        report.append("")
        
        # Comparison
        comparison = results.get('comparison', {})
        
        report.append("COMPARISON")
        report.append("-" * 40)
        if 'error' in comparison:
            report.append(f"Error: {comparison['error']}")
        else:
            report.append(f"P&L Improvement: ${comparison.get('pnl_improvement', 0):.2f}")
            report.append(f"P&L Improvement %: {comparison.get('pnl_improvement_pct', 0):.2f}%")
            report.append(f"Win Rate Improvement: {comparison.get('win_rate_improvement', 0):.2f}%")
            report.append(f"Sharpe Ratio Improvement: {comparison.get('sharpe_improvement', 0):.2f}")
            report.append(f"Profit Factor Improvement: {comparison.get('profit_factor_improvement', 0):.2f}")
            report.append("")
            
            if comparison.get('ml_outperforms', False):
                report.append("✅ ML-ENHANCED STRATEGY OUTPERFORMS BASELINE")
            else:
                report.append("❌ ML-ENHANCED STRATEGY DOES NOT OUTPERFORM BASELINE")
        report.append("")
        
        # Strategy info
        ml_strategy_info = ml_enhanced.get('strategy_info', {})
        report.append("ML STRATEGY INFO")
        report.append("-" * 40)
        report.append(f"ML Server URL: {ml_strategy_info.get('ml_server_url', 'N/A')}")
        report.append(f"Fallback Enabled: {ml_strategy_info.get('fallback_to_baseline', 'N/A')}")
        report.append(f"Confidence Threshold: {ml_strategy_info.get('confidence_threshold', 'N/A')}")
        
        ml_stats = ml_strategy_info.get('ml_stats', {})
        report.append(f"ML Requests: {ml_stats.get('total_requests', 0)}")
        report.append(f"ML Failures: {ml_stats.get('total_failures', 0)}")
        report.append(f"Success Rate: {ml_stats.get('success_rate', 0):.2f}")
        
        return "\n".join(report)


def main():
    """Main validation function."""
    parser = argparse.ArgumentParser(description='Validate ML-enhanced trading strategy')
    parser.add_argument('--start-date', type=str, required=True,
                       help='Start date for backtest (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, required=True,
                       help='End date for backtest (YYYY-MM-DD)')
    parser.add_argument('--symbol', type=str, default='BTC-USD',
                       help='Trading symbol to test')
    parser.add_argument('--output-file', type=str,
                       help='Output file for validation report')
    
    args = parser.parse_args()
    
    logger.info("Starting ML strategy validation")
    logger.info(f"Configuration: {vars(args)}")
    
    try:
        # Parse dates
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
        
        # Create trading config
        config = TradingConfig()
        config.product_id = args.symbol
        
        # Initialize validator
        validator = MLStrategyValidator(config)
        
        # Run validation
        logger.info("Running strategy comparison...")
        results = validator.run_comparison_backtest(start_date, end_date, args.symbol)
        
        # Generate report
        report = validator.generate_validation_report(results)
        
        # Output report
        if args.output_file:
            with open(args.output_file, 'w') as f:
                f.write(report)
            logger.info(f"Validation report saved to {args.output_file}")
        else:
            print(report)
        
        # Save results as JSON
        results_file = f"outputs/ml_validation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        import json
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        logger.info(f"Validation results saved to {results_file}")
        
        logger.info("ML strategy validation completed successfully")
        return 0
        
    except Exception as e:
        logger.error(f"Error during validation: {e}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
