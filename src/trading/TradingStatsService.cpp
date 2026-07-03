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

TradingStats TradingStatsService::getTradingStats() const {
  try {
    auto table_exists = DatabaseManager::getInstance().query(
        "SELECT to_regclass('public.individual_trades') AS relname");
    if (table_exists.empty() || table_exists[0]["relname"].is_null()) {
      return {};
    }

    auto res = DatabaseManager::getInstance().query(
        "SELECT trade_id, symbol, side, size, price, timestamp, pnl, fees "
        "FROM individual_trades ORDER BY timestamp ASC");

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
    return calculateTradingStats(trades, today);
  } catch (const std::exception &e) {
    TR_LOG_ERROR("Failed to compute trading stats: {}", e.what());
  }

  return {};
}

} // namespace trading
} // namespace trade