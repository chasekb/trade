#include "ml/DataCollector.hpp"
#include <algorithm>
#include <chrono>
#include <cstddef>
#include <nlohmann/json.hpp>
#include <string>
#include <pqxx/pqxx>
#include <spdlog/spdlog.h>
#include <utility>

namespace trade {
namespace ml {

DataCollector::DataCollector(const std::string &db_url) : db_url_(db_url) {}

bool DataCollector::ensure_training_inputs_table() {
  try {
    pqxx::connection conn(db_url_);

    {
      pqxx::work txn(conn);

      txn.exec(R"SQL(
        CREATE TABLE IF NOT EXISTS individual_trades (
          trade_id TEXT PRIMARY KEY,
          session_id TEXT,
          symbol TEXT NOT NULL,
          side TEXT NOT NULL,
          size DOUBLE PRECISION,
          price DOUBLE PRECISION NOT NULL,
          timestamp BIGINT NOT NULL,
          strategy_type TEXT,
          signal_reason TEXT,
          pnl DOUBLE PRECISION,
          fees DOUBLE PRECISION,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          win_probability DOUBLE PRECISION,
          expected_return DOUBLE PRECISION,
          model_confidence DOUBLE PRECISION,
          trade_type TEXT DEFAULT 'live'
        )
      )SQL");

      txn.exec(
          "CREATE INDEX IF NOT EXISTS idx_individual_trades_timestamp "
          "ON individual_trades(timestamp)");
      txn.exec(
          "CREATE INDEX IF NOT EXISTS idx_individual_trades_symbol_timestamp "
          "ON individual_trades(symbol, timestamp)");

      txn.exec(R"SQL(
        CREATE TABLE IF NOT EXISTS ml_training_inputs (
          signal_id TEXT PRIMARY KEY,
          trade_id TEXT NOT NULL,
          symbol TEXT NOT NULL,
          signal_timestamp BIGINT NOT NULL,
          trade_timestamp BIGINT NOT NULL,
          bid_ask_imbalance DOUBLE PRECISION NOT NULL,
          spread_percent DOUBLE PRECISION NOT NULL DEFAULT 0.001,
          mid_price DOUBLE PRECISION NOT NULL,
          bid_volume DOUBLE PRECISION NOT NULL DEFAULT 0.0,
          ask_volume DOUBLE PRECISION NOT NULL DEFAULT 0.0,
          order_book_depth INTEGER NOT NULL DEFAULT 0,
          large_bid_wall BOOLEAN NOT NULL DEFAULT FALSE,
          large_ask_wall BOOLEAN NOT NULL DEFAULT FALSE,
          wall_size DOUBLE PRECISION NOT NULL DEFAULT 0.0,
          volume_weighted_price DOUBLE PRECISION NOT NULL DEFAULT 0.0,
          price_momentum DOUBLE PRECISION NOT NULL DEFAULT 0.0,
          volatility DOUBLE PRECISION NOT NULL DEFAULT 0.0,
          volume_24h DOUBLE PRECISION NOT NULL DEFAULT 0.0,
          prev_win_probability DOUBLE PRECISION NOT NULL DEFAULT 0.5,
          prev_expected_return DOUBLE PRECISION NOT NULL DEFAULT 0.0,
          prev_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
          side TEXT,
          trade_size DOUBLE PRECISION,
          trade_price DOUBLE PRECISION,
          pnl DOUBLE PRECISION NOT NULL DEFAULT 0.0,
          fees DOUBLE PRECISION NOT NULL DEFAULT 0.0,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
      )SQL");

      txn.exec(
          "CREATE INDEX IF NOT EXISTS idx_ml_training_inputs_signal_ts "
          "ON ml_training_inputs(signal_timestamp)");
      txn.exec(
          "CREATE INDEX IF NOT EXISTS idx_ml_training_inputs_symbol_signal_ts "
          "ON ml_training_inputs(symbol, signal_timestamp)");
      txn.exec(
          "CREATE INDEX IF NOT EXISTS idx_ml_training_inputs_trade_ts "
          "ON ml_training_inputs(trade_timestamp)");

      txn.commit();
    }

    {
      pqxx::work txn(conn);
      const auto relation_exists = txn.exec(
          "SELECT to_regclass('public.individual_trades') AS relname");
      const bool has_individual_trades = !relation_exists.empty() &&
                                         !relation_exists[0]["relname"].is_null();
      if (!has_individual_trades) {
        txn.commit();
        spdlog::warn(
            "Skipping ml_training_inputs trade trigger setup because individual_trades is unavailable");
        return true;
      }

      txn.exec(R"SQL(
        CREATE OR REPLACE FUNCTION fn_upsert_ml_training_inputs_from_trade()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        AS $$
        BEGIN
          INSERT INTO ml_training_inputs (
            signal_id,
            trade_id,
            symbol,
            signal_timestamp,
            trade_timestamp,
            bid_ask_imbalance,
            mid_price,
            volume_weighted_price,
            side,
            trade_size,
            trade_price,
            pnl,
            fees,
            updated_at
          )
          SELECT
            s.signal_id,
            NEW.trade_id,
            NEW.symbol,
            s.timestamp,
            NEW.timestamp,
            s.strength,
            s.price,
            s.price,
            NEW.side,
            NEW.size,
            NEW.price,
            COALESCE(NEW.pnl, 0.0),
            COALESCE(NEW.fees, 0.0),
            NOW()
          FROM order_book_signals s
          WHERE s.symbol = NEW.symbol
            AND s.timestamp <= NEW.timestamp
            AND s.timestamp >= (NEW.timestamp - 300)
            AND NOT EXISTS (
              SELECT 1
              FROM individual_trades t_prev
              WHERE t_prev.symbol = s.symbol
                AND t_prev.timestamp >= s.timestamp
                AND t_prev.timestamp < NEW.timestamp
            )
          ON CONFLICT (signal_id) DO UPDATE
            SET
              trade_id = EXCLUDED.trade_id,
              symbol = EXCLUDED.symbol,
              trade_timestamp = EXCLUDED.trade_timestamp,
              side = EXCLUDED.side,
              trade_size = EXCLUDED.trade_size,
              trade_price = EXCLUDED.trade_price,
              pnl = EXCLUDED.pnl,
              fees = EXCLUDED.fees,
              updated_at = NOW()
            WHERE EXCLUDED.trade_timestamp < ml_training_inputs.trade_timestamp;

          RETURN NEW;
        END;
        $$
      )SQL");

      txn.exec(
          "DROP TRIGGER IF EXISTS trg_upsert_ml_training_inputs_from_trade "
          "ON individual_trades");
      txn.exec(R"SQL(
        CREATE TRIGGER trg_upsert_ml_training_inputs_from_trade
        AFTER INSERT ON individual_trades
        FOR EACH ROW
        EXECUTE FUNCTION fn_upsert_ml_training_inputs_from_trade()
      )SQL");

      txn.commit();
    }

    return true;
  } catch (const std::exception &e) {
    spdlog::error("Failed to ensure ml_training_inputs table/trigger: {}",
                  e.what());
    return false;
  }
}

std::size_t DataCollector::sync_training_inputs(int days_back, int batch_size) {
  if (!ensure_training_inputs_table()) {
    return 0;
  }

  if (batch_size <= 0) {
    batch_size = 5000;
  }

  std::size_t inserted_total = 0;

  try {
    pqxx::connection conn(db_url_);

    long long incremental_threshold_ts = 0;
    {
      pqxx::work txn(conn);
      pqxx::result r = txn.exec(
          "SELECT COALESCE(MAX(signal_timestamp), 0) AS max_signal_ts "
          "FROM ml_training_inputs");
      if (!r.empty()) {
        incremental_threshold_ts = r[0]["max_signal_ts"].as<long long>();
      }
      txn.commit();
    }

    if (incremental_threshold_ts > 0) {
      incremental_threshold_ts = std::max(0LL, incremental_threshold_ts - 300);
    }

    std::string where_clause = "WHERE 1=1";
    if (days_back > 0) {
      auto now = std::chrono::system_clock::now();
      auto threshold = now - std::chrono::hours(24 * days_back);
      long long threshold_ts = std::chrono::duration_cast<std::chrono::seconds>(
                                   threshold.time_since_epoch())
                                   .count();
      where_clause += " AND s.timestamp >= " + std::to_string(threshold_ts);
    }
    if (incremental_threshold_ts > 0) {
      where_clause +=
          " AND s.timestamp >= " + std::to_string(incremental_threshold_ts);
    }

    for (int offset = 0;; offset += batch_size) {
      pqxx::work txn(conn);

      std::string query =
          "SELECT "
          "s.signal_id, s.symbol AS signal_symbol, s.strength, "
          "s.price AS signal_price, s.timestamp AS signal_timestamp, "
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
          std::to_string(batch_size) + " OFFSET " +
          std::to_string(std::max(0, offset));

      pqxx::result res = txn.exec(query);
      if (res.empty()) {
        txn.commit();
        break;
      }

      std::size_t inserted_batch = 0;
      for (const auto &row : res) {
        const std::string signal_id = row["signal_id"].c_str();
        const std::string trade_id = row["trade_id"].c_str();
        const std::string symbol = row["trade_symbol"].c_str();
        const long long signal_ts = row["signal_timestamp"].as<long long>();
        const long long trade_ts = row["trade_timestamp"].as<long long>();
        const double imbalance = row["strength"].as<double>();
        const double signal_price = row["signal_price"].as<double>();
        const std::string side = row["side"].c_str();
        const double trade_size = row["trade_size"].as<double>();
        const double trade_price = row["trade_price"].as<double>();
        const double pnl = row["pnl"].is_null() ? 0.0 : row["pnl"].as<double>();
        const double fees =
            row["fees"].is_null() ? 0.0 : row["fees"].as<double>();

        pqxx::result upsert_res = txn.exec_params(
            "INSERT INTO ml_training_inputs ("
            "  signal_id, trade_id, symbol, signal_timestamp, trade_timestamp,"
            "  bid_ask_imbalance, spread_percent, mid_price,"
            "  bid_volume, ask_volume, order_book_depth,"
            "  large_bid_wall, large_ask_wall, wall_size,"
            "  volume_weighted_price, price_momentum, volatility, volume_24h,"
            "  prev_win_probability, prev_expected_return, prev_confidence,"
            "  side, trade_size, trade_price, pnl, fees, updated_at"
            ") VALUES ("
            "  $1, $2, $3, $4, $5,"
            "  $6, $7, $8,"
            "  $9, $10, $11,"
            "  $12, $13, $14,"
            "  $15, $16, $17, $18,"
            "  $19, $20, $21,"
            "  $22, $23, $24, $25, $26, NOW()"
            ")"
            "ON CONFLICT (signal_id) DO NOTHING"
            " RETURNING signal_id",
            signal_id, trade_id, symbol, signal_ts, trade_ts, imbalance, 0.001,
            signal_price, 0.0, 0.0, 0, false, false, 0.0, signal_price, 0.0,
            0.0, 0.0, 0.5, 0.0, 0.0, side, trade_size, trade_price, pnl, fees);

        if (!upsert_res.empty()) {
          ++inserted_batch;
        }
      }

      txn.commit();
      inserted_total += inserted_batch;

      spdlog::info(
          "DataCollector: sync_training_inputs batch offset={} rows={} inserted={}"
          " total_inserted={}",
          offset, res.size(), inserted_batch, inserted_total);
    }
  } catch (const std::exception &e) {
    spdlog::error("Database error in sync_training_inputs: {}", e.what());
  }

  return inserted_total;
}

std::size_t DataCollector::count_training_inputs(int days_back) {
  if (!ensure_training_inputs_table()) {
    return 0;
  }

  try {
    pqxx::connection conn(db_url_);
    pqxx::work txn(conn);

    std::string query = "SELECT COUNT(*) AS c FROM ml_training_inputs";
    if (days_back > 0) {
      auto now = std::chrono::system_clock::now();
      auto threshold = now - std::chrono::hours(24 * days_back);
      long long threshold_ts = std::chrono::duration_cast<std::chrono::seconds>(
                                   threshold.time_since_epoch())
                                   .count();
      query += " WHERE signal_timestamp >= " + std::to_string(threshold_ts);
    }

    pqxx::result res = txn.exec(query);
    txn.commit();
    if (res.empty()) {
      return 0;
    }
    return static_cast<std::size_t>(res[0]["c"].as<long long>());
  } catch (const std::exception &e) {
    spdlog::error("Database error in count_training_inputs: {}", e.what());
    return 0;
  }
}

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

  if (!ensure_training_inputs_table()) {
    return pairs;
  }

  try {
    pqxx::connection conn(db_url_);
    pqxx::work txn(conn);

    if (limit <= 0) {
      return pairs;
    }

    std::string where_clause = "WHERE 1=1";
    if (days_back > 0) {
      auto now = std::chrono::system_clock::now();
      auto threshold = now - std::chrono::hours(24 * days_back);
      long long threshold_ts = std::chrono::duration_cast<std::chrono::seconds>(
                                   threshold.time_since_epoch())
                                   .count();
      where_clause +=
          " AND signal_timestamp >= " + std::to_string(threshold_ts);
    }

    std::string query =
        "SELECT "
        "signal_id, symbol, bid_ask_imbalance, spread_percent, mid_price, "
        "bid_volume, ask_volume, order_book_depth, large_bid_wall, "
        "large_ask_wall, wall_size, volume_weighted_price, price_momentum, "
        "volatility, volume_24h, prev_win_probability, prev_expected_return, "
        "prev_confidence, side, trade_size, trade_price, signal_timestamp, "
        "trade_timestamp, trade_id, pnl, fees "
        "FROM ml_training_inputs " +
        where_clause +
        " ORDER BY signal_timestamp ASC "
        " LIMIT " +
        std::to_string(limit) + " OFFSET " + std::to_string(std::max(0, offset));

    pqxx::result res = txn.exec(query);
    pairs.reserve(res.size());

    for (const auto &row : res) {
      OrderBookFeatures signal;
      signal.timestamp = row["signal_timestamp"].as<long long>();
      signal.symbol = row["symbol"].c_str();
      signal.bid_ask_imbalance = row["bid_ask_imbalance"].as<double>();
      signal.spread_percent = row["spread_percent"].as<double>();
      signal.mid_price = row["mid_price"].as<double>();
      signal.bid_volume = row["bid_volume"].as<double>();
      signal.ask_volume = row["ask_volume"].as<double>();
      signal.order_book_depth = row["order_book_depth"].as<int>();
      signal.large_bid_wall = row["large_bid_wall"].as<bool>();
      signal.large_ask_wall = row["large_ask_wall"].as<bool>();
      signal.wall_size = row["wall_size"].as<double>();
      signal.volume_weighted_price = row["volume_weighted_price"].as<double>();
      signal.price_momentum = row["price_momentum"].as<double>();
      signal.volatility = row["volatility"].as<double>();
      signal.volume_24h = row["volume_24h"].as<double>();
      signal.prev_win_probability = row["prev_win_probability"].as<double>();
      signal.prev_expected_return = row["prev_expected_return"].as<double>();
      signal.prev_confidence = row["prev_confidence"].as<double>();

      TradeOutcome trade;
      trade.trade_id = row["trade_id"].c_str();
      trade.symbol = row["symbol"].c_str();
      trade.side = row["side"].c_str();
      trade.quantity = row["trade_size"].is_null() ? 0.0 : row["trade_size"].as<double>();
      trade.entry_price = row["trade_price"].is_null() ? 0.0 : row["trade_price"].as<double>();
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
