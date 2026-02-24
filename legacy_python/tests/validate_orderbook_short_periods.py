#!/usr/bin/env python3
"""
Validation test for OrderBookStrategy across short time periods and fine granularities.
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime

class OrderBookShortPeriodValidator:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        
        # Test configurations for short periods and fine granularities
        # Since API requires integer days, we'll use 1 day and test different granularities
        self.time_periods = [1]  # 1 day (minimum)
        self.granularities = [60, 300, 900, 1800, 3600]  # 1m, 5m, 15m, 30m, 1h in seconds
        self.granularity_names = {60: "1m", 300: "5m", 900: "15m", 1800: "30m", 3600: "1h"}
        
        # Strategy parameters
        self.strategy_params = {
            "order_book_level": 2,
            "trade_history_limit": 100,
            "bid_ask_spread_threshold": 0.001,
            "volume_imbalance_threshold": 0.6,
            "large_trade_threshold": 10000.0
        }
        
        self.results = []
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_orderbook_strategy(self, days, granularity):
        """Test OrderBookStrategy for a specific time period and granularity."""
        print(f"Testing OrderBookStrategy: {days} day(s), {self.granularity_names[granularity]} granularity")
        
        payload = {
            "strategy_type": "orderbook",
            "product_id": "BTC-USD",
            "days": days,
            "granularity": granularity,
            "strategy_params": self.strategy_params
        }
        
        start_time = time.time()
        
        try:
            async with self.session.post(f"{self.base_url}/api/run-backtest", 
                                       json=payload) as response:
                response_time = time.time() - start_time
                
                if response.status == 200:
                    data = await response.json()
                    result = data.get('result', {})
                    
                    # Extract key metrics
                    test_result = {
                        'days': days,
                        'granularity': granularity,
                        'granularity_name': self.granularity_names[granularity],
                        'status': 'success',
                        'response_time': round(response_time, 2),
                        'total_signals': result.get('total_signals', 0),
                        'total_trades': result.get('total_trades', 0),
                        'winning_trades': result.get('winning_trades', 0),
                        'win_rate': result.get('win_rate', 0),
                        'total_return': result.get('total_return', 0),
                        'max_drawdown': result.get('max_drawdown', 0),
                        'sharpe_ratio': result.get('sharpe_ratio', 0),
                        'signal_breakdown': result.get('signal_breakdown', {}),
                        'data_points': result.get('data_points', 0),
                        'strategy_processed_points': result.get('strategy_processed_points', 0)
                    }
                    
                    print(f"  ✅ Success: {test_result['total_signals']} signals, {test_result['total_trades']} trades, {test_result['win_rate']:.1f}% win rate")
                    return test_result
                    
                else:
                    error_text = await response.text()
                    print(f"  ❌ Failed: HTTP {response.status} - {error_text[:100]}")
                    return {
                        'days': days,
                        'granularity': granularity,
                        'granularity_name': self.granularity_names[granularity],
                        'status': 'error',
                        'response_time': round(response_time, 2),
                        'error': f"HTTP {response.status}: {error_text[:100]}"
                    }
                    
        except Exception as e:
            response_time = time.time() - start_time
            print(f"  ❌ Exception: {str(e)[:100]}")
            return {
                'days': days,
                'granularity': granularity,
                'granularity_name': self.granularity_names[granularity],
                'status': 'exception',
                'response_time': round(response_time, 2),
                'error': str(e)
            }
    
    async def run_all_tests(self):
        """Run OrderBookStrategy tests for all combinations of short periods and fine granularities."""
        print("🚀 Starting OrderBookStrategy short period validation tests...")
        print(f"Testing {len(self.time_periods)} time periods × {len(self.granularities)} granularities = {len(self.time_periods) * len(self.granularities)} total tests")
        print()
        
        total_tests = len(self.time_periods) * len(self.granularities)
        completed_tests = 0
        
        for days in self.time_periods:
            for granularity in self.granularities:
                result = await self.test_orderbook_strategy(days, granularity)
                self.results.append(result)
                completed_tests += 1
                
                # Progress indicator
                progress = (completed_tests / total_tests) * 100
                print(f"Progress: {completed_tests}/{total_tests} ({progress:.1f}%)")
                print()
                
                # Small delay to avoid overwhelming the server
                await asyncio.sleep(0.5)
        
        return self.results
    
    def analyze_results(self):
        """Analyze test results and generate summary."""
        print("📊 Analysis Results:")
        print("=" * 60)
        
        # Overall statistics
        total_tests = len(self.results)
        successful_tests = len([r for r in self.results if r['status'] == 'success'])
        failed_tests = len([r for r in self.results if r['status'] != 'success'])
        
        print(f"Total Tests: {total_tests}")
        print(f"Successful: {successful_tests} ({successful_tests/total_tests*100:.1f}%)")
        print(f"Failed: {failed_tests} ({failed_tests/total_tests*100:.1f}%)")
        print()
        
        if successful_tests > 0:
            # Signal analysis
            successful_results = [r for r in self.results if r['status'] == 'success']
            
            print("📈 Signal Analysis:")
            print("-" * 30)
            
            total_signals = sum(r['total_signals'] for r in successful_results)
            total_trades = sum(r['total_trades'] for r in successful_results)
            avg_signals_per_test = total_signals / successful_tests
            avg_trades_per_test = total_trades / successful_tests
            
            print(f"Total Signals Generated: {total_signals}")
            print(f"Total Trades Executed: {total_trades}")
            print(f"Average Signals per Test: {avg_signals_per_test:.1f}")
            print(f"Average Trades per Test: {avg_trades_per_test:.1f}")
            print()
            
            # Signal type breakdown
            signal_breakdown = {}
            for result in successful_results:
                for signal_type, count in result.get('signal_breakdown', {}).items():
                    signal_breakdown[signal_type] = signal_breakdown.get(signal_type, 0) + count
            
            print("🎯 Signal Type Breakdown:")
            print("-" * 30)
            for signal_type, count in sorted(signal_breakdown.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / total_signals * 100) if total_signals > 0 else 0
                print(f"{signal_type}: {count} ({percentage:.1f}%)")
            print()
            
            # Performance by time period
            print("⏰ Performance by Time Period:")
            print("-" * 30)
            for days in sorted(set(r['days'] for r in successful_results)):
                period_results = [r for r in successful_results if r['days'] == days]
                avg_signals = sum(r['total_signals'] for r in period_results) / len(period_results)
                avg_trades = sum(r['total_trades'] for r in period_results) / len(period_results)
                print(f"{days:2d} day(s): {avg_signals:5.1f} signals, {avg_trades:4.1f} trades avg")
            print()
            
            # Performance by granularity
            print("📊 Performance by Granularity:")
            print("-" * 30)
            for granularity in sorted(set(r['granularity'] for r in successful_results)):
                gran_results = [r for r in successful_results if r['granularity'] == granularity]
                avg_signals = sum(r['total_signals'] for r in gran_results) / len(gran_results)
                avg_trades = sum(r['total_trades'] for r in gran_results) / len(gran_results)
                print(f"{self.granularity_names[granularity]:2s}: {avg_signals:5.1f} signals, {avg_trades:4.1f} trades avg")
            print()
            
            # Response time analysis
            avg_response_time = sum(r['response_time'] for r in successful_results) / successful_tests
            max_response_time = max(r['response_time'] for r in successful_results)
            min_response_time = min(r['response_time'] for r in successful_results)
            
            print("⚡ Response Time Analysis:")
            print("-" * 30)
            print(f"Average: {avg_response_time:.2f}s")
            print(f"Fastest: {min_response_time:.2f}s")
            print(f"Slowest: {max_response_time:.2f}s")
            print()
            
            # Data points analysis
            avg_data_points = sum(r['data_points'] for r in successful_results) / successful_tests
            print("📊 Data Points Analysis:")
            print("-" * 30)
            print(f"Average data points per test: {avg_data_points:.1f}")
            
            # Check for data consistency
            expected_vs_actual = []
            for result in successful_results:
                if result['data_points'] > 0 and result['strategy_processed_points'] > 0:
                    ratio = result['strategy_processed_points'] / result['data_points']
                    expected_vs_actual.append(ratio)
            
            if expected_vs_actual:
                avg_ratio = sum(expected_vs_actual) / len(expected_vs_actual)
                print(f"Strategy processing ratio: {avg_ratio:.3f} (should be close to 1.0)")
                if avg_ratio < 0.9:
                    print("⚠️  WARNING: Strategy may not be processing all data points")
                elif avg_ratio > 1.1:
                    print("⚠️  WARNING: Strategy may be processing data points multiple times")
                else:
                    print("✅ Strategy processing ratio looks good")
            print()
        
        # Failed tests analysis
        if failed_tests > 0:
            print("❌ Failed Tests:")
            print("-" * 30)
            for result in self.results:
                if result['status'] != 'success':
                    print(f"{result['days']:2d} day(s), {result['granularity_name']:2s}: {result.get('error', 'Unknown error')}")
            print()
        
        return {
            'total_tests': total_tests,
            'successful_tests': successful_tests,
            'failed_tests': failed_tests,
            'success_rate': successful_tests / total_tests * 100,
            'total_signals': total_signals if successful_tests > 0 else 0,
            'total_trades': total_trades if successful_tests > 0 else 0,
            'signal_breakdown': signal_breakdown if successful_tests > 0 else {}
        }
    
    def save_results(self, filename="orderbook_short_period_results.json"):
        """Save detailed results to JSON file."""
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"💾 Detailed results saved to {filename}")

async def main():
    """Main test execution."""
    async with OrderBookShortPeriodValidator() as validator:
        # Run all tests
        await validator.run_all_tests()
        
        # Analyze and display results
        analysis = validator.analyze_results()
        
        # Save results
        validator.save_results()
        
        # Final summary
        print("🎉 OrderBookStrategy Short Period Validation Complete!")
        print(f"Success Rate: {analysis['success_rate']:.1f}%")
        if analysis['successful_tests'] > 0:
            print(f"Total Signals: {analysis['total_signals']}")
            print(f"Total Trades: {analysis['total_trades']}")
        
        return analysis['success_rate'] >= 80.0  # Consider 80%+ success rate as passing

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
