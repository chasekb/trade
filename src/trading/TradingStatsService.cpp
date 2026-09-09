#include "trading/TradingStatsService.hpp"
#include "trading/TradingStatsCalculator.hpp"

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

TradePerformanceInput toTradePerformanceInput(const pqxx::row &row) {
  TradePerformanceInput input;
  input.pnl = getDoubleOrDefault(row, "pnl");
  input.fees = getDoubleOrDefault(row, "fees");
  input.quantity = getDoubleOrDefault(row, "size");
  input.price = getDoubleOrDefault(row, "price");
  const long long timestamp_epoch = getLongLongOrDefault(row, "timestamp");
  input.timestamp_iso = formatUtcIsoFromEpoch(timestamp_epoch);
  return input;
}

} // namespace

namespace {

constexpr std::chrono::seconds kStatsCacheTtl{5};

} // namespace

TradingStats TradingStatsService::getTradingStats(const TradingStatsFilter &filter) const {
  const std::string cache_key = filter.trade_type + "|" + filter.session_id;
  const auto now_steady = std::chrono::steady_clock::now();
  {
    std::lock_guard<std::mutex> lock(cache_mutex_);
    const auto it = cache_.find(cache_key);
    if (it != cache_.end() && now_steady - it->second.first < kStatsCacheTtl) {
      return it->second.second;
    }
  }

  try {
    auto table_exists = DatabaseManager::getInstance().query(
        "SELECT to_regclass('public.individual_trades') AS relname");
    if (table_exists.empty() || table_exists[0]["relname"].is_null()) {
      return {};
    }

    // Request-derived filter values are bound as parameters, never inlined.
    std::ostringstream sql;
    sql << "SELECT trade_id, symbol, side, size, price, timestamp, pnl, fees "
        << "FROM individual_trades";
    std::vector<std::string> bound;
    std::string separator = " WHERE ";
    if (!filter.trade_type.empty()) {
      bound.push_back(filter.trade_type);
      sql << separator << "trade_type=$" << bound.size();
      separator = " AND ";
    }
    if (!filter.session_id.empty()) {
      bound.push_back(filter.session_id);
      sql << separator << "session_id=$" << bound.size();
    }
    sql << " ORDER BY timestamp ASC";

    auto res = bound.empty() ? DatabaseManager::getInstance().query(sql.str())
                             : DatabaseManager::getInstance().execParams(sql.str(), bound);

    if (res.empty()) {
      return {};
    }

    std::vector<TradePerformanceInput> trades;
    trades.reserve(res.size());
    for (const auto &row : res) {
      trades.push_back(toTradePerformanceInput(row));
    }

    const auto now = std::chrono::system_clock::now();
    const std::string today = formatUtcDateFromEpoch(
        std::chrono::duration_cast<std::chrono::seconds>(now.time_since_epoch()).count());
    const TradingStats stats = calculateTradingStats(trades, today);
    {
      std::lock_guard<std::mutex> lock(cache_mutex_);
      cache_[cache_key] = {now_steady, stats};
    }
    return stats;
  } catch (const std::exception &e) {
    TR_LOG_ERROR("Failed to compute trading stats: {}", e.what());
  }

  return {};
}

} // namespace trading
} // namespace trade