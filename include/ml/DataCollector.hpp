#pragma once

#include <memory>
#include <nlohmann/json.hpp>
#include <pqxx/pqxx>
#include <string>
#include <vector>
#include <xtensor/containers/xarray.hpp>

namespace trade {
namespace ml {

struct OrderBookFeatures {
  long long timestamp;
  std::string symbol;
  double bid_ask_imbalance;
  double spread_percent;
  double mid_price;
  double bid_volume;
  double ask_volume;
  int order_book_depth;
  bool large_bid_wall;
  bool large_ask_wall;
  double wall_size;
  double volume_weighted_price;
  double price_momentum;
  double volatility;
  double volume_24h;
  double prev_win_probability;
  double prev_expected_return;
  double prev_confidence;
};

struct TradeOutcome {
  std::string trade_id;
  std::string symbol;
  std::string side;
  double entry_price;
  double exit_price;
  double quantity;
  double pnl;
  double fees;
  int duration_seconds;
  std::string signal_type;
  double signal_strength;
  long long entry_timestamp;
  long long exit_timestamp;
  bool is_win;
};

class DataCollector {
public:
  explicit DataCollector(const std::string &db_url);

  std::vector<OrderBookFeatures> extract_signals(int days_back,
                                                 int limit = 0);
  std::vector<TradeOutcome> extract_trades(int days_back, int limit = 0);

  std::vector<std::pair<OrderBookFeatures, TradeOutcome>>
  match_signals_to_trades(const std::vector<OrderBookFeatures> &signals,
                          const std::vector<TradeOutcome> &trades);

private:
  std::string db_url_;
};

} // namespace ml
} // namespace trade
