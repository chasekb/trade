#include "ml/DataCollector.hpp"
#include <chrono>
#include <pqxx/pqxx>
#include <spdlog/spdlog.h>

namespace trade {
namespace ml {

DataCollector::DataCollector(const std::string &db_url) : db_url_(db_url) {}

std::vector<OrderBookFeatures> DataCollector::extract_signals(int days_back) {
  std::vector<OrderBookFeatures> signals;
  try {
    pqxx::connection conn(db_url_);
    pqxx::work txn(conn);

    // Calculate timestamp threshold
    auto now = std::chrono::system_clock::now();
    auto threshold = now - std::chrono::hours(24 * days_back);
    long long threshold_ts = std::chrono::duration_cast<std::chrono::seconds>(
                                 threshold.time_since_epoch())
                                 .count();

    std::string query = "SELECT signal_id, symbol, signal_type, strength, "
                        "price, timestamp, signal_data "
                        "FROM order_book_signals WHERE timestamp >= " +
                        std::to_string(threshold_ts) +
                        " ORDER BY timestamp ASC";

    pqxx::result res = txn.exec(query);

    for (const auto &row : res) {
      OrderBookFeatures signal;
      signal.timestamp = row["timestamp"].as<long long>();
      signal.symbol = row["symbol"].c_str();
      signal.bid_ask_imbalance = row["strength"].as<double>();
      signal.mid_price = row["price"].as<double>();

      // Note: In a real implementation, we'd parse the signal_data JSON.
      // For now, we use defaults for the secondary features.
      signal.spread_percent = 0.001;
      signal.bid_volume = 1.0;
      signal.ask_volume = 1.0;
      signal.order_book_depth = 2;
      signal.large_bid_wall = false;
      signal.large_ask_wall = false;
      signal.wall_size = 0.0;
      signal.volume_weighted_price = signal.mid_price;
      signal.price_momentum = 0.0;
      signal.volatility = 0.0;
      signal.volume_24h = 0.0;
      signal.prev_win_probability = 0.5;
      signal.prev_expected_return = 0.0;
      signal.prev_confidence = 0.0;

      signals.push_back(signal);
    }
  } catch (const std::exception &e) {
    spdlog::error("Database error in extract_signals: {}", e.what());
  }
  return signals;
}

std::vector<TradeOutcome> DataCollector::extract_trades(int days_back) {
  std::vector<TradeOutcome> trades;
  try {
    pqxx::connection conn(db_url_);
    pqxx::work txn(conn);

    auto now = std::chrono::system_clock::now();
    auto threshold = now - std::chrono::hours(24 * days_back);
    long long threshold_ts = std::chrono::duration_cast<std::chrono::seconds>(
                                 threshold.time_since_epoch())
                                 .count();

    std::string query =
        "SELECT trade_id, symbol, side, size, price, timestamp, pnl, fees "
        "FROM individual_trades WHERE timestamp >= " +
        std::to_string(threshold_ts) + " ORDER BY timestamp ASC";

    pqxx::result res = txn.exec(query);

    for (const auto &row : res) {
      TradeOutcome trade;
      trade.trade_id = row["trade_id"].c_str();
      trade.symbol = row["symbol"].c_str();
      trade.side = row["side"].c_str();
      trade.quantity = row["size"].as<double>();
      trade.entry_price = row["price"].as<double>();
      trade.exit_price = trade.entry_price; // Simplified
      trade.entry_timestamp = row["timestamp"].as<long long>();
      trade.exit_timestamp = trade.entry_timestamp;
      trade.pnl = row["pnl"].is_null() ? 0.0 : row["pnl"].as<double>();
      trade.fees = row["fees"].is_null() ? 0.0 : row["fees"].as<double>();
      trade.is_win = trade.pnl > 0;

      trades.push_back(trade);
    }
  } catch (const std::exception &e) {
    spdlog::error("Database error in extract_trades: {}", e.what());
  }
  return trades;
}

std::vector<std::pair<OrderBookFeatures, TradeOutcome>>
DataCollector::match_signals_to_trades(
    const std::vector<OrderBookFeatures> &signals,
    const std::vector<TradeOutcome> &trades) {
  std::vector<std::pair<OrderBookFeatures, TradeOutcome>> pairs;

  // Match each signal with the NEXT trade for that symbol within 5 minutes
  // (300s). Assumes trades are already sorted by timestamp.
  for (const auto &signal : signals) {
    for (const auto &trade : trades) {
      if (trade.symbol == signal.symbol &&
          trade.entry_timestamp >= signal.timestamp &&
          trade.entry_timestamp <= signal.timestamp + 300) {
        pairs.push_back({signal, trade});
        break; // First trade after signal
      }
    }
  }

  return pairs;
}

} // namespace ml
} // namespace trade
