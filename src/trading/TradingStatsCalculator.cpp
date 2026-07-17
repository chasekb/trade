#include "trading/TradingStatsCalculator.hpp"

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

double calculateProfitFactor(const std::vector<double> &pnl_values) {
  if (pnl_values.empty()) {
    return 0.0;
  }

  double gross_profit = 0.0;
  double gross_loss = 0.0;
  for (double pnl : pnl_values) {
    if (pnl > 0.0) {
      gross_profit += pnl;
    } else if (pnl < 0.0) {
      gross_loss += std::abs(pnl);
    }
  }

  if (gross_loss == 0.0) {
    return gross_profit > 0.0 ? 999.0 : 0.0;
  }

  return gross_profit / gross_loss;
}

double calculateSharpeRatio(const std::vector<double> &returns) {
  if (returns.empty()) {
    return 0.0;
  }

  const double mean_return = std::accumulate(returns.begin(), returns.end(), 0.0) /
                             static_cast<double>(returns.size());
  double variance = 0.0;
  for (double r : returns) {
    const double diff = r - mean_return;
    variance += diff * diff;
  }
  variance /= static_cast<double>(returns.size());

  const double std_dev = std::sqrt(variance);
  if (std_dev == 0.0) {
    return 0.0;
  }

  // Per-trade Sharpe (mean/std of trade PnL). The trade series is not a daily
  // return series, so no sqrt(252) annualization; the frontend derives the
  // same convention.
  return mean_return / std_dev;
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
  const double completed_trades = static_cast<double>(stats.winning_trades + stats.losing_trades);
  stats.win_rate = completed_trades > 0.0
                       ? static_cast<double>(stats.winning_trades) / completed_trades * 100.0
                       : 0.0;
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
  stats.profit_factor = calculateProfitFactor(pnl_values);
  stats.sharpe_ratio = calculateSharpeRatio(pnl_values);
  return stats;
}

} // namespace trading
} // namespace trade
