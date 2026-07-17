#pragma once

#include <chrono>
#include <map>
#include <mutex>
#include <string>
#include <utility>

namespace trade {
namespace trading {

struct TradingStats {
  double total_pnl = 0.0;
  double total_fees = 0.0;
  double net_pnl = 0.0;
  double win_rate = 0.0;
  int total_trades = 0;
  int winning_trades = 0;
  int losing_trades = 0;
  double avg_win = 0.0;
  double avg_loss = 0.0;
  double best_trade = 0.0;
  double worst_trade = 0.0;
  double profit_factor = 0.0;
  double sharpe_ratio = 0.0;
  double max_drawdown = 0.0;
  double total_volume = 0.0;
  double avg_trade_size = 0.0;
  int trades_today = 0;
  std::string last_trade_time;
};

// Optional scoping for stats aggregation. Empty fields mean "all"; the
// default therefore preserves the historical whole-table behavior.
struct TradingStatsFilter {
  std::string trade_type;
  std::string session_id;
};

class TradingStatsService {
public:
  static TradingStatsService &getInstance();

  TradingStats getTradingStats(const TradingStatsFilter &filter = {}) const;

private:
  TradingStatsService() = default;
  ~TradingStatsService() = default;
  TradingStatsService(const TradingStatsService &) = delete;
  TradingStatsService &operator=(const TradingStatsService &) = delete;

  // Short-TTL cache so hot paths (status polls, per-open position sizing)
  // never trigger repeated table scans.
  mutable std::mutex cache_mutex_;
  mutable std::map<std::string,
                   std::pair<std::chrono::steady_clock::time_point, TradingStats>>
      cache_;
};

} // namespace trading
} // namespace trade