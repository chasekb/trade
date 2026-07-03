#include "trading/TradingStatsCalculator.hpp"

#include <cmath>
#include <iostream>
#include <vector>

using trade::trading::TradePerformanceInput;
using trade::trading::calculateTradingStats;

int main() {
  const std::vector<TradePerformanceInput> trades{
      {10.0, 2.0, 1.0, 100.0, "2026-06-18T10:00:00Z"},
      {-6.0, 1.0, 2.0, 120.0, "2026-06-18T11:00:00Z"},
      {4.0, 0.5, 1.0, 50.0, "2026-06-17T12:00:00Z"},
  };

  const auto stats = calculateTradingStats(trades, "2026-06-18");

  auto expect_close = [](double actual, double expected, double eps, const char *label) {
    if (std::fabs(actual - expected) > eps) {
      std::cerr << label << " expected " << expected << " got " << actual << std::endl;
      return false;
    }
    return true;
  };

  if (stats.total_trades != 3 || stats.winning_trades != 2 || stats.losing_trades != 1) {
    std::cerr << "Unexpected trade counts" << std::endl;
    return 1;
  }
  if (!expect_close(stats.total_pnl, 8.0, 1e-9, "total_pnl") ||
      !expect_close(stats.total_fees, 3.5, 1e-9, "total_fees") ||
      !expect_close(stats.net_pnl, 4.5, 1e-9, "net_pnl") ||
      !expect_close(stats.win_rate, 66.6666666667, 1e-6, "win_rate") ||
      !expect_close(stats.avg_win, 7.0, 1e-9, "avg_win") ||
      !expect_close(stats.avg_loss, -6.0, 1e-9, "avg_loss") ||
      !expect_close(stats.best_trade, 10.0, 1e-9, "best_trade") ||
      !expect_close(stats.worst_trade, -6.0, 1e-9, "worst_trade") ||
      !expect_close(stats.total_volume, 390.0, 1e-9, "total_volume") ||
      !expect_close(stats.avg_trade_size, 130.0, 1e-9, "avg_trade_size") ||
      !expect_close(stats.max_drawdown, 6.0, 1e-9, "max_drawdown") ||
      !expect_close(stats.profit_factor, 14.0 / 6.0, 1e-9, "profit_factor")) {
    return 1;
  }

  if (stats.trades_today != 2) {
    std::cerr << "Unexpected trades_today: " << stats.trades_today << std::endl;
    return 1;
  }
  if (stats.last_trade_time != "2026-06-17T12:00:00Z") {
    std::cerr << "Unexpected last_trade_time: " << stats.last_trade_time << std::endl;
    return 1;
  }

  return 0;
}
