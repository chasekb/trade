#include "trading/TradingStatsService.hpp"

#include "db/DatabaseManager.hpp"
#include "ml/Metrics.hpp"
#include "utils/Logger.hpp"

#include <algorithm>
#include <chrono>
#include <ctime>
#include <iomanip>
#include <limits>
#include <pqxx/pqxx>
#include <sstream>
#include <vector>

namespace trade {
namespace trading {

TradingStatsService &TradingStatsService::getInstance() {
  static TradingStatsService instance;
  return instance;
}

namespace {

double getDoubleOrDefault(const pqxx::row &row, const char *column) {
  try {
    if (row[column].is_null()) {
      return 0.0;
    }
    return row[column].as<double>();
  } catch (...) {
    return 0.0;
  }
}

long long getLongLongOrDefault(const pqxx::row &row, const char *column) {
  try {
    if (row[column].is_null()) {
      return 0;
    }
    return row[column].as<long long>();
  } catch (...) {
    return 0;
  }
}

std::string formatUtcDateFromEpoch(long long epoch_seconds) {
  std::time_t raw = static_cast<std::time_t>(epoch_seconds);
  std::tm utc_tm{};
#ifdef _WIN32
  gmtime_s(&utc_tm, &raw);
#else
  gmtime_r(&raw, &utc_tm);
#endif
  std::ostringstream oss;
  oss << std::put_time(&utc_tm, "%Y-%m-%d");
  return oss.str();
}

std::string formatUtcIsoFromEpoch(long long epoch_seconds) {
  std::time_t raw = static_cast<std::time_t>(epoch_seconds);
  std::tm utc_tm{};
#ifdef _WIN32
  gmtime_s(&utc_tm, &raw);
#else
  gmtime_r(&raw, &utc_tm);
#endif
  std::ostringstream oss;
  oss << std::put_time(&utc_tm, "%Y-%m-%dT%H:%M:%SZ");
  return oss.str();
}

} // namespace

TradingStats TradingStatsService::getTradingStats() const {
  TradingStats stats;

  try {
    auto table_exists = DatabaseManager::getInstance().query(
        "SELECT to_regclass('public.individual_trades') AS relname");
    if (table_exists.empty() || table_exists[0]["relname"].is_null()) {
      return stats;
    }

    auto res = DatabaseManager::getInstance().query(
        "SELECT trade_id, symbol, side, size, price, timestamp, pnl, fees "
        "FROM individual_trades ORDER BY timestamp ASC");

    if (res.empty()) {
      return stats;
    }

    const auto now = std::chrono::system_clock::now();
    const std::string today = formatUtcDateFromEpoch(
        std::chrono::duration_cast<std::chrono::seconds>(now.time_since_epoch()).count());
    std::vector<double> pnl_values;
    std::vector<double> positive_pnls;
    std::vector<double> negative_pnls;
    double cumulative_pnl = 0.0;
    double peak_pnl = 0.0;

    stats.total_trades = static_cast<int>(res.size());
    stats.best_trade = std::numeric_limits<double>::lowest();
    stats.worst_trade = std::numeric_limits<double>::max();

    for (const auto &row : res) {
      const double pnl = getDoubleOrDefault(row, "pnl");
      const double fees = getDoubleOrDefault(row, "fees");
      const double size = getDoubleOrDefault(row, "size");
      const double price = getDoubleOrDefault(row, "price");
      const long long timestamp_epoch = getLongLongOrDefault(row, "timestamp");
      const std::string timestamp = formatUtcIsoFromEpoch(timestamp_epoch);

      stats.total_pnl += pnl;
      stats.total_fees += fees;
      stats.total_volume += size * price;

      pnl_values.push_back(pnl);

      if (pnl > 0.0) {
        stats.winning_trades++;
        positive_pnls.push_back(pnl);
      } else if (pnl < 0.0) {
        stats.losing_trades++;
        negative_pnls.push_back(pnl);
      }

      stats.best_trade = std::max(stats.best_trade, pnl);
      stats.worst_trade = std::min(stats.worst_trade, pnl);

      cumulative_pnl += pnl;
      peak_pnl = std::max(peak_pnl, cumulative_pnl);
      stats.max_drawdown = std::max(stats.max_drawdown, peak_pnl - cumulative_pnl);

      if (!timestamp.empty()) {
        stats.last_trade_time = timestamp;
        if (timestamp.rfind(today, 0) == 0) {
          stats.trades_today++;
        }
      }
    }

    stats.net_pnl = stats.total_pnl - stats.total_fees;
    stats.win_rate = stats.total_trades > 0
                         ? static_cast<double>(stats.winning_trades) /
                               static_cast<double>(stats.total_trades) * 100.0
                         : 0.0;
    stats.avg_trade_size = stats.total_trades > 0
                               ? stats.total_volume /
                                     static_cast<double>(stats.total_trades)
                               : 0.0;

    if (!positive_pnls.empty()) {
      double gross_wins = 0.0;
      for (double value : positive_pnls) {
        gross_wins += value;
      }
      stats.avg_win = gross_wins / static_cast<double>(positive_pnls.size());
    }

    if (!negative_pnls.empty()) {
      double gross_losses = 0.0;
      for (double value : negative_pnls) {
        gross_losses += value;
      }
      stats.avg_loss = gross_losses / static_cast<double>(negative_pnls.size());
    }

    stats.profit_factor = trade::ml::Metrics::calculate_profit_factor(pnl_values);
    stats.sharpe_ratio = trade::ml::Metrics::calculate_sharpe_ratio(pnl_values);

    if (stats.best_trade == std::numeric_limits<double>::lowest()) {
      stats.best_trade = 0.0;
    }
    if (stats.worst_trade == std::numeric_limits<double>::max()) {
      stats.worst_trade = 0.0;
    }
  } catch (const std::exception &e) {
    TR_LOG_ERROR("Failed to compute trading stats: {}", e.what());
  }

  return stats;
}

} // namespace trading
} // namespace trade