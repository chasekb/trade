#pragma once

#include "trading/TradingStatsService.hpp"

#include <string>
#include <vector>

namespace trade {
namespace trading {

struct TradePerformanceInput {
  double pnl = 0.0;
  double fees = 0.0;
  double quantity = 0.0;
  double price = 0.0;
  std::string timestamp_iso;
};

TradingStats calculateTradingStats(const std::vector<TradePerformanceInput> &trades,
                                   const std::string &today_utc = "");

} // namespace trading
} // namespace trade
