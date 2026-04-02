#include "ml/DataCollector.hpp"
#include <algorithm>
#include <chrono>
#include <nlohmann/json.hpp>
#include <pqxx/pqxx>
#include <spdlog/spdlog.h>
#include <utility>

namespace trade {
namespace ml {

DataCollector::DataCollector(const std::string &db_url) : db_url_(db_url) {}

std::vector<OrderBookFeatures> DataCollector::extract_signals(int days_back,
                                                              int limit) {
  std::vector<OrderBookFeatures> signals;
  try {
    pqxx::connection conn(db_url_);
    pqxx::work txn(conn);

    std::string query = "SELECT signal_id, symbol, signal_type, strength, "
                        "price, timestamp, signal_data "
                        "FROM order_book_signals";

    if (days_back > 0) {
      // Calculate timestamp threshold
      auto now = std::chrono::system_clock::now();
      auto threshold = now - std::chrono::hours(24 * days_back);
      long long threshold_ts = std::chrono::duration_cast<std::chrono::seconds>(
                                   threshold.time_since_epoch())
                                   .count();
      query += " WHERE timestamp >= " + std::to_string(threshold_ts);
    }

    query += " ORDER BY timestamp ASC";

    if (limit > 0) {
      query += " LIMIT " + std::to_string(limit);
    }

    pqxx::result res = txn.exec(query);

    for (const auto &row : res) {
      OrderBookFeatures signal;
      signal.timestamp = row["timestamp"].as<long long>();
      signal.symbol = row["symbol"].c_str();
      signal.bid_ask_imbalance = row["strength"].as<double>();
      signal.mid_price = row["price"].as<double>();

      // Parse signal_data JSON when available to populate secondary features.
      signal.spread_percent = 0.001;
      signal.bid_volume = 0.0;
      signal.ask_volume = 0.0;
      signal.order_book_depth = 0;
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

      try {
        if (!row["signal_data"].is_null()) {
          const char *raw = row["signal_data"].c_str();
          if (raw && raw[0] == '{') {
            nlohmann::json j = nlohmann::json::parse(raw, nullptr, false);
            if (j.is_object()) {
              // Spread and best bid/ask derived from JSON when present
              double best_bid = j.value("best_bid", signal.mid_price * 0.999);
              double best_ask = j.value("best_ask", signal.mid_price * 1.001);
              if (best_bid > 0.0 && best_ask > best_bid) {
                signal.spread_percent =
                    (best_ask - best_bid) / ((best_ask + best_bid) / 2.0);
              }

              // Orderbook bids/asks for depth and volumes
              const auto &bids = j.value("bids", nlohmann::json::array());
              const auto &asks = j.value("asks", nlohmann::json::array());

              auto sum_top_levels = [](const nlohmann::json &levels,
                                       std::size_t max_levels) {
                double total = 0.0;
                std::size_t count = 0;
                for (const auto &lvl : levels) {
                  if (!lvl.is_array() || lvl.size() < 2)
                    continue;
                  total += lvl[1].get<double>();
                  if (++count >= max_levels)
                    break;
                }
                return total;
              };

              signal.bid_volume = sum_top_levels(bids, 5);
              signal.ask_volume = sum_top_levels(asks, 5);

              signal.order_book_depth =
                  static_cast<int>(std::max(bids.size(), asks.size()));

              auto detect_large_wall = [](const nlohmann::json &levels,
                                          double threshold) {
                for (const auto &lvl : levels) {
                  if (!lvl.is_array() || lvl.size() < 2)
                    continue;
                  if (lvl[1].get<double>() > threshold)
                    return true;
                }
                return false;
              };

              signal.large_bid_wall = detect_large_wall(bids, 1000.0);
              signal.large_ask_wall = detect_large_wall(asks, 1000.0);

              auto max_volume = [](const nlohmann::json &levels) {
                double max_v = 0.0;
                for (const auto &lvl : levels) {
                  if (!lvl.is_array() || lvl.size() < 2)
                    continue;
                  max_v = std::max(max_v, lvl[1].get<double>());
                }
                return max_v;
              };

              double max_bid_v = max_volume(bids);
              double max_ask_v = max_volume(asks);
              signal.wall_size = std::max(max_bid_v, max_ask_v);

              // VWAP from top-of-book when possible
              double vwap = 0.0;
              double total_vol = 0.0;
              auto accumulate_vwap = [&](const nlohmann::json &levels) {
                for (const auto &lvl : levels) {
                  if (!lvl.is_array() || lvl.size() < 2)
                    continue;
                  double price = lvl[0].get<double>();
                  double vol = lvl[1].get<double>();
                  vwap += price * vol;
                  total_vol += vol;
                }
              };
              accumulate_vwap(bids);
              accumulate_vwap(asks);
              if (total_vol > 0.0) {
                signal.volume_weighted_price = vwap / total_vol;
              }

              // Optional meta fields if present
              signal.volume_24h = j.value("volume_24h", signal.volume_24h);

              const auto &ml_analysis =
                  j.value("ml_analysis", nlohmann::json::object());
              if (ml_analysis.is_object()) {
                signal.prev_win_probability =
                    ml_analysis.value("win_probability",
                                      signal.prev_win_probability);
                signal.prev_expected_return =
                    ml_analysis.value("expected_return",
                                      signal.prev_expected_return);
                signal.prev_confidence =
                    ml_analysis.value("confidence", signal.prev_confidence);
              }
            }
          }
        }
      } catch (const std::exception &e) {
        spdlog::warn("Failed to parse signal_data JSON: {}", e.what());
      }

      signals.push_back(signal);
    }
  } catch (const std::exception &e) {
    spdlog::error("Database error in extract_signals: {}", e.what());
  }
  return signals;
}

std::vector<TradeOutcome> DataCollector::extract_trades(int days_back,
                                                        int limit) {
  std::vector<TradeOutcome> trades;
  try {
    pqxx::connection conn(db_url_);
    pqxx::work txn(conn);

    std::string query =
        "SELECT trade_id, symbol, side, size, price, timestamp, pnl, fees "
        "FROM individual_trades";

    if (days_back > 0) {
      auto now = std::chrono::system_clock::now();
      auto threshold = now - std::chrono::hours(24 * days_back);
      long long threshold_ts = std::chrono::duration_cast<std::chrono::seconds>(
                                   threshold.time_since_epoch())
                                   .count();
      query += " WHERE timestamp >= " + std::to_string(threshold_ts);
    }

    query += " ORDER BY timestamp ASC";

    if (limit > 0) {
      query += " LIMIT " + std::to_string(limit);
    }

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

std::vector<std::pair<OrderBookFeatures, TradeOutcome>>
DataCollector::extract_training_pairs_batch(int days_back, int limit,
                                           int offset) {
  std::vector<std::pair<OrderBookFeatures, TradeOutcome>> pairs;

  try {
    pqxx::connection conn(db_url_);
    pqxx::work txn(conn);

    if (limit <= 0) {
      return pairs;
    }

    std::string where_clause;
    if (days_back > 0) {
      auto now = std::chrono::system_clock::now();
      auto threshold = now - std::chrono::hours(24 * days_back);
      long long threshold_ts = std::chrono::duration_cast<std::chrono::seconds>(
                                   threshold.time_since_epoch())
                                   .count();
      where_clause = "WHERE s.timestamp >= " + std::to_string(threshold_ts);
    }

    std::string query =
        "SELECT "
        "s.symbol AS signal_symbol, s.strength, s.price AS signal_price, "
        "s.timestamp AS signal_timestamp, s.signal_data, "
        "t.trade_id, t.symbol AS trade_symbol, t.side, t.size AS trade_size, "
        "t.price AS trade_price, t.timestamp AS trade_timestamp, t.pnl, t.fees "
        "FROM order_book_signals s "
        "JOIN LATERAL ("
        "  SELECT trade_id, symbol, side, size, price, timestamp, pnl, fees "
        "  FROM individual_trades "
        "  WHERE symbol = s.symbol "
        "    AND timestamp >= s.timestamp "
        "    AND timestamp <= s.timestamp + 300 "
        "  ORDER BY timestamp ASC "
        "  LIMIT 1"
        ") t ON TRUE " +
        where_clause +
        " ORDER BY s.timestamp ASC "
        " LIMIT " +
        std::to_string(limit) + " OFFSET " + std::to_string(std::max(0, offset));

    pqxx::result res = txn.exec(query);
    pairs.reserve(res.size());

    for (const auto &row : res) {
      OrderBookFeatures signal;
      signal.timestamp = row["signal_timestamp"].as<long long>();
      signal.symbol = row["signal_symbol"].c_str();
      signal.bid_ask_imbalance = row["strength"].as<double>();
      signal.mid_price = row["signal_price"].as<double>();

      signal.spread_percent = 0.001;
      signal.bid_volume = 0.0;
      signal.ask_volume = 0.0;
      signal.order_book_depth = 0;
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

      try {
        if (!row["signal_data"].is_null()) {
          const char *raw = row["signal_data"].c_str();
          if (raw && raw[0] == '{') {
            nlohmann::json j = nlohmann::json::parse(raw, nullptr, false);
            if (j.is_object()) {
              double best_bid = j.value("best_bid", signal.mid_price * 0.999);
              double best_ask = j.value("best_ask", signal.mid_price * 1.001);
              if (best_bid > 0.0 && best_ask > best_bid) {
                signal.spread_percent =
                    (best_ask - best_bid) / ((best_ask + best_bid) / 2.0);
              }

              const auto &bids = j.value("bids", nlohmann::json::array());
              const auto &asks = j.value("asks", nlohmann::json::array());

              auto sum_top_levels = [](const nlohmann::json &levels,
                                       std::size_t max_levels) {
                double total = 0.0;
                std::size_t count = 0;
                for (const auto &lvl : levels) {
                  if (!lvl.is_array() || lvl.size() < 2)
                    continue;
                  total += lvl[1].get<double>();
                  if (++count >= max_levels)
                    break;
                }
                return total;
              };

              signal.bid_volume = sum_top_levels(bids, 5);
              signal.ask_volume = sum_top_levels(asks, 5);
              signal.order_book_depth =
                  static_cast<int>(std::max(bids.size(), asks.size()));

              auto detect_large_wall = [](const nlohmann::json &levels,
                                          double threshold) {
                for (const auto &lvl : levels) {
                  if (!lvl.is_array() || lvl.size() < 2)
                    continue;
                  if (lvl[1].get<double>() > threshold)
                    return true;
                }
                return false;
              };

              signal.large_bid_wall = detect_large_wall(bids, 1000.0);
              signal.large_ask_wall = detect_large_wall(asks, 1000.0);

              auto max_volume = [](const nlohmann::json &levels) {
                double max_v = 0.0;
                for (const auto &lvl : levels) {
                  if (!lvl.is_array() || lvl.size() < 2)
                    continue;
                  max_v = std::max(max_v, lvl[1].get<double>());
                }
                return max_v;
              };

              signal.wall_size = std::max(max_volume(bids), max_volume(asks));

              double vwap = 0.0;
              double total_vol = 0.0;
              auto accumulate_vwap = [&](const nlohmann::json &levels) {
                for (const auto &lvl : levels) {
                  if (!lvl.is_array() || lvl.size() < 2)
                    continue;
                  double price = lvl[0].get<double>();
                  double vol = lvl[1].get<double>();
                  vwap += price * vol;
                  total_vol += vol;
                }
              };
              accumulate_vwap(bids);
              accumulate_vwap(asks);
              if (total_vol > 0.0) {
                signal.volume_weighted_price = vwap / total_vol;
              }

              signal.volume_24h = j.value("volume_24h", signal.volume_24h);

              const auto &ml_analysis =
                  j.value("ml_analysis", nlohmann::json::object());
              if (ml_analysis.is_object()) {
                signal.prev_win_probability =
                    ml_analysis.value("win_probability",
                                      signal.prev_win_probability);
                signal.prev_expected_return =
                    ml_analysis.value("expected_return",
                                      signal.prev_expected_return);
                signal.prev_confidence =
                    ml_analysis.value("confidence", signal.prev_confidence);
              }
            }
          }
        }
      } catch (const std::exception &e) {
        spdlog::warn("Failed to parse signal_data JSON in batch extraction: {}",
                     e.what());
      }

      TradeOutcome trade;
      trade.trade_id = row["trade_id"].c_str();
      trade.symbol = row["trade_symbol"].c_str();
      trade.side = row["side"].c_str();
      trade.quantity = row["trade_size"].as<double>();
      trade.entry_price = row["trade_price"].as<double>();
      trade.exit_price = trade.entry_price;
      trade.entry_timestamp = row["trade_timestamp"].as<long long>();
      trade.exit_timestamp = trade.entry_timestamp;
      trade.pnl = row["pnl"].is_null() ? 0.0 : row["pnl"].as<double>();
      trade.fees = row["fees"].is_null() ? 0.0 : row["fees"].as<double>();
      trade.is_win = trade.pnl > 0;

      pairs.push_back({std::move(signal), std::move(trade)});
    }
  } catch (const std::exception &e) {
    spdlog::error("Database error in extract_training_pairs_batch: {}", e.what());
  }

  return pairs;
}

} // namespace ml
} // namespace trade
