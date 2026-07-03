#include "trading/TradingStatsCalculator.hpp"

#include "ml/Metrics.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <ctime>
#include <limits>
#include <numeric>
#include <sstream>
#include <string>

namespace trade {
namespace trading {
namespace {

std::string currentUtcDate() {
  const auto now = std::chrono::system_clock::now();
  const std::time_t now_time = std::chrono::system_clock::to_time_t(now);
  std::tm utc{};
#if defined(_WIN32)
  gmtime_s(&utc, &now_time);
#else
  gmtime_r(&now_time, &utc);
#endif
  char buffer[11] = {0};
  if (std::strftime(buffer, sizeof(buffer), "%F", &utc) == 0) {
    return {};
  }
  return buffer;
}

} // namespace

TradingStats calculateTradingStats(const std::vector<TradePerformanceInput> &trades,
                                   const std::string &today_utc) {
  TradingStats stats;
  if (trades.empty()) {
    return stats;
  }

  const std::string today = today_utc.empty() ? currentUtcDate() : today_utc;
  std::vector<double> pnl_values;
  std::vector<double> positive_pnls;
  std::vector<double> negative_pnls;
  double cumulative_pnl = 0.0;
  double peak_pnl = 0.0;
  double best_trade = std::numeric_limits<double>::lowest();
  double worst_trade = std::numeric_limits<double>::max();

  for (const auto &trade : trades) {
    const double pnl = trade.pnl;
    const double fees = trade.fees;
    const double volume = trade.quantity * trade.price;

    stats.total_pnl += pnl;
    stats.total_fees += fees;
    stats.total_volume += volume;
    stats.total_trades += 1;
    stats.last_trade_time = trade.timestamp_iso.empty() ? stats.last_trade_time : trade.timestamp_iso;

    pnl_values.push_back(pnl);

    if (pnl > 0.0) {
      stats.winning_trades += 1;
      positive_pnls.push_back(pnl);
    } else if (pnl < 0.0) {
      stats.losing_trades += 1;
      negative_pnls.push_back(pnl);
    }

    best_trade = std::max(best_trade, pnl);
    worst_trade = std::min(worst_trade, pnl);

    cumulative_pnl += pnl;
    peak_pnl = std::max(peak_pnl, cumulative_pnl);
    stats.max_drawdown = std::max(stats.max_drawdown, peak_pnl - cumulative_pnl);

    if (!today.empty() && !trade.timestamp_iso.empty() && trade.timestamp_iso.rfind(today, 0) == 0) {
      stats.trades_today += 1;
    }
  }

  stats.net_pnl = stats.total_pnl - stats.total_fees;
  stats.win_rate = static_cast<double>(stats.winning_trades) / static_cast<double>(stats.total_trades) * 100.0;
  stats.avg_trade_size = stats.total_volume / static_cast<double>(stats.total_trades);

  if (!positive_pnls.empty()) {
    stats.avg_win = std::accumulate(positive_pnls.begin(), positive_pnls.end(), 0.0) /
                    static_cast<double>(positive_pnls.size());
  }
  if (!negative_pnls.empty()) {
    stats.avg_loss = std::accumulate(negative_pnls.begin(), negative_pnls.end(), 0.0) /
                     static_cast<double>(negative_pnls.size());
  }

  stats.best_trade = best_trade == std::numeric_limits<double>::lowest() ? 0.0 : best_trade;
  stats.worst_trade = worst_trade == std::numeric_limits<double>::max() ? 0.0 : worst_trade;
  stats.profit_factor = trade::ml::Metrics::calculate_profit_factor(pnl_values);
  stats.sharpe_ratio = trade::ml::Metrics::calculate_sharpe_ratio(pnl_values);
  return stats;
}

} // namespace trading
} // namespace trade
