#pragma once

#include <string>

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

class TradingStatsService {
public:
  TradingStats getTradingStats() const;
};

} // namespace trading
} // namespace trade